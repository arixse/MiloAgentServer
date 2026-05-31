import os
import re
import tempfile
import zipfile
from urllib.parse import urljoin

import httpx
import yaml
from bs4 import BeautifulSoup
from daytona import Daytona, DaytonaConfig
from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from playwright.sync_api import sync_playwright

load_dotenv()


# =============================================================================
# Common helpers
# =============================================================================

def _get_filename_from_url(url: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(url).path
    return os.path.basename(path) or "skill.zip"


def _parse_skill_name_from_zip(zip_path: str) -> str | None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        skill_md = None
        for name in zf.namelist():
            if name.endswith("SKILL.md") or name.endswith("skill.md"):
                skill_md = name
                break
        if not skill_md:
            return None
        content = zf.read(skill_md).decode("utf-8")

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    frontmatter = yaml.safe_load(match.group(1))
    return frontmatter.get("name") if isinstance(frontmatter, dict) else None


def _get_sandbox(config: RunnableConfig):
    thread_id = config["configurable"]["thread_id"]
    sandbox_name = f"sandbox_{thread_id}"
    daytona = Daytona(config=DaytonaConfig(api_key=os.getenv("DAYTONA_API_KEY")))
    return daytona.get(sandbox_name)


def _download_and_install_skill(download_url: str, config: RunnableConfig) -> str:
    """Common flow: download zip → parse skill name → upload → unzip → cleanup."""
    filename = _get_filename_from_url(download_url)
    local_tmpdir = tempfile.mkdtemp(prefix="skill_download_")
    local_zip = os.path.join(local_tmpdir, filename)

    try:
        with httpx.Client(follow_redirects=True, timeout=120) as http:
            with http.stream("GET", download_url) as resp:
                resp.raise_for_status()
                with open(local_zip, "wb") as f:
                    for chunk in resp.iter_bytes(64 * 1024):
                        f.write(chunk)

        sandbox = _get_sandbox(config)

        skill_name = _parse_skill_name_from_zip(local_zip)
        if not skill_name:
            return "无法从 SKILL.md 中解析 skill name"

        remote_zip = f"/skills/{filename}"
        sandbox.fs.upload_file(local_zip, remote_zip)

        result = sandbox.process.exec(
            f"mkdir -p /skills/{skill_name}"
            f" && unzip -o /skills/{filename} -d /skills/{skill_name}"
            f" && rm -f /skills/{filename}"
        )
        if result.exit_code != 0:
            return f"解压失败: {result.result}"

        import shutil
        shutil.rmtree(local_tmpdir, ignore_errors=True)

        return f"skill 安装成功，已解压至 sandbox /skills/{skill_name}/ 目录（来源: {download_url}）"

    except Exception as e:
        import shutil
        shutil.rmtree(local_tmpdir, ignore_errors=True)
        return f"skill 安装失败: {e}"


# =============================================================================
# Site-specific download URL parsers
# =============================================================================

def _get_clawhub_download_url(page_html: str, base_url: str) -> str | None:
    soup = BeautifulSoup(page_html, "html.parser")
    candidates: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        text = a_tag.get_text(strip=True).lower()
        if "download" in text and href.endswith(".zip"):
            return urljoin(base_url, href)
        if href.endswith(".zip"):
            candidates.append(urljoin(base_url, href))

    if candidates:
        return candidates[0]

    for btn in soup.find_all(["button", "a"]):
        text = btn.get_text(strip=True).lower()
        if "download" in text:
            href = btn.get("href", "").strip()
            if href:
                return urljoin(base_url, href)
            data_url = btn.get("data-url", "").strip()
            if data_url:
                return urljoin(base_url, data_url)

    for el in soup.find_all(attrs={"onclick": True}):
        onclick = el.get("onclick", "")
        match = re.search(r"""['"]((https?://|/)[^'"]*\.zip)['"]""", onclick)
        if match:
            return urljoin(base_url, match.group(1))

    return None


def _get_modelscope_download_url(skill_url: str) -> str | None:
    """Use Playwright to render the ModelScope page (exec JS), then parse <a download> tag."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(skill_url, wait_until="networkidle", timeout=30000)
            # 额外等待确保动态内容渲染完成
            page.wait_for_timeout(2000)
            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, "html.parser")

    for a_tag in soup.find_all("a", attrs={"download": True}, href=True):
        href = a_tag.get("href", "").strip()
        if href:
            return urljoin(skill_url, href)

    # Fallback: look for any href containing .zip
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        if ".zip" in href:
            return urljoin(skill_url, href)

    return None


def _get_skillhub_download_url(skill_url: str) -> str | None:
    """Extract slug from URL and call the SkillHub download API."""
    slug = skill_url.rstrip("/").rsplit("/", 1)[-1]
    api_url = f"https://api.skillhub.cn/api/v1/download?slug={slug}"

    with httpx.Client(follow_redirects=True, timeout=30) as http:
        resp = http.get(
            api_url,
            headers={
                "accept": "*/*",
                "origin": "https://skillhub.cn",
                "referer": "https://skillhub.cn/",
            },
        )
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "zip" in ct or "octet-stream" in ct:
                return api_url  # the API URL itself is the download URL

    return None


# =============================================================================
# Tools
# =============================================================================

@tool
def install_skill_from_clawhub_url(skill_url: str, config: RunnableConfig) -> str:
    """从指定 clawhub 地址安装 skill。

    例如 https://clawhub.ai/chindden/skill-creator

    Args:
        skill_url: clawhub skill 页面的 URL。
        config: LangChain 运行时配置（自动注入）。

    Returns:
        skill 安装状态描述。
    """
    with httpx.Client(follow_redirects=True, timeout=30) as http:
        resp = http.get(skill_url)
        resp.raise_for_status()
        page_html = resp.text

    download_url = _get_clawhub_download_url(page_html, skill_url)
    if not download_url:
        return f"未在页面 {skill_url} 中找到 skill 下载链接"

    print(f"[clawhub] 下载链接: {download_url}")
    return _download_and_install_skill(download_url, config)


@tool
def install_skill_from_modelscope_url(skill_url: str, config: RunnableConfig) -> str:
    """从指定 ModelScope 地址安装 skill。

    例如 https://modelscope.cn/skills/@anthropics/skill-creator

    Args:
        skill_url: ModelScope skill 页面的 URL。
        config: LangChain 运行时配置（自动注入）。

    Returns:
        skill 安装状态描述。
    """
    download_url = _get_modelscope_download_url(skill_url)
    if not download_url:
        return f"未在页面 {skill_url} 中找到 skill 下载链接"

    print(f"[modelscope] 下载链接: {download_url}")
    return _download_and_install_skill(download_url, config)


@tool
def install_skill_from_skillhub_url(skill_url: str, config: RunnableConfig) -> str:
    """从指定 SkillHub 地址安装 skill。

    例如 https://skillhub.cn/skills/baidu-search

    Args:
        skill_url: SkillHub skill 页面的 URL。
        config: LangChain 运行时配置（自动注入）。

    Returns:
        skill 安装状态描述。
    """
    download_url = _get_skillhub_download_url(skill_url)
    if not download_url:
        return f"未在页面 {skill_url} 中找到 skill 下载链接"

    print(f"[skillhub] 下载链接: {download_url}")
    return _download_and_install_skill(download_url, config)

# 获取 skill相关的工具
def get_skill_tools():
    return [install_skill_from_clawhub_url, install_skill_from_modelscope_url, install_skill_from_skillhub_url]