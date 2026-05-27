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

load_dotenv()


def _get_download_url(page_html: str, base_url: str) -> str | None:
    """从 clawhub 页面中解析出 Download button 指向的 zip 下载链接。"""
    soup = BeautifulSoup(page_html, "html.parser")

    candidates: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "").strip()
        text = a_tag.get_text(strip=True).lower()
        if "download" in text and href.endswith(".zip"):
            return urljoin(base_url, href)
        if href.endswith(".zip"):
            candidates.append(urljoin(base_url, href))

    # 如果没找到 text 含 "download" 的链接，回退到第一个 .zip 链接
    if candidates:
        return candidates[0]

    # 再用 button 尝试
    for btn in soup.find_all(["button", "a"]):
        text = btn.get_text(strip=True).lower()
        if "download" in text:
            href = btn.get("href", "").strip()
            if href:
                return urljoin(base_url, href)
            data_url = btn.get("data-url", "").strip()
            if data_url:
                return urljoin(base_url, data_url)

    # 最后检查 onclick 中的链接
    for el in soup.find_all(attrs={"onclick": True}):
        onclick = el.get("onclick", "")
        match = re.search(r"""['"]((https?://|/)[^'"]*\.zip)['"]""", onclick)
        if match:
            return urljoin(base_url, match.group(1))

    return None


def _get_filename_from_url(url: str) -> str:
    """从 URL 中提取文件名。"""
    from urllib.parse import urlparse

    path = urlparse(url).path
    return os.path.basename(path) or "skill.zip"


def _parse_skill_name_from_zip(zip_path: str) -> str | None:
    """从 zip 包中的 SKILL.md frontmatter 里提取 name 字段。"""
    with zipfile.ZipFile(zip_path, "r") as zf:
        # 查找 SKILL.md（可能在子目录中）
        skill_md = None
        for name in zf.namelist():
            if name.endswith("SKILL.md") or name.endswith("skill.md"):
                skill_md = name
                break

        if not skill_md:
            return None

        content = zf.read(skill_md).decode("utf-8")

    # 匹配 YAML frontmatter（--- ... ---）
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    frontmatter = yaml.safe_load(match.group(1))
    return frontmatter.get("name") if isinstance(frontmatter, dict) else None


@tool
def install_skill_from_url(skill_url: str, config: RunnableConfig) -> str:
    """从指定 clawhub 地址安装 skill：爬取页面获取下载链接 → 下载 zip →
    上传至 Daytona sandbox 的 /skills 目录并解压 → 清理临时文件。

    Args:
        skill_url: clawhub skill 页面的 URL。
        config: LangChain 运行时配置（自动注入），用于获取 sandbox。

    Returns:
        skill 安装状态描述。
    """
    thread_id = config["configurable"]["thread_id"]
    sandbox_name = f"sandbox_{thread_id}"

    # 1. 爬取 clawhub 页面，提取下载链接
    with httpx.Client(follow_redirects=True, timeout=30) as http:
        resp = http.get(skill_url)
        resp.raise_for_status()
        page_html = resp.text

    download_url = _get_download_url(page_html, skill_url)
    print(f"下载链接: {download_url}")
    if not download_url:
        return f"未在页面 {skill_url} 中找到 skill 下载链接"

    filename = _get_filename_from_url(download_url)
    local_tmpdir = tempfile.mkdtemp(prefix="skill_download_")
    local_zip = os.path.join(local_tmpdir, filename)

    # 2. 下载 zip 到本地临时目录
    try:
        with httpx.Client(follow_redirects=True, timeout=120) as http:
            with http.stream("GET", download_url) as resp:
                resp.raise_for_status()
                with open(local_zip, "wb") as f:
                    for chunk in resp.iter_bytes(64 * 1024):
                        f.write(chunk)

        # 3. 获取 Daytona sandbox
        daytona = Daytona(config=DaytonaConfig(
            api_key=os.getenv("DAYTONA_API_KEY")
        ))
        sandbox = daytona.get(sandbox_name)

        # 4. 从 SKILL.md frontmatter 的 name 字段获取 skill 名称
        skill_name = _parse_skill_name_from_zip(local_zip)
        if not skill_name:
            return "无法从 SKILL.md 中解析 skill name"

        # 5. 上传 zip 到 sandbox 的 /skills 目录
        remote_zip = f"/skills/{filename}"
        sandbox.fs.upload_file(local_zip, remote_zip)

        # 6. 解压到 /skills/{skill_name}/ 目录，清理 zip
        result = sandbox.process.exec(
            f"mkdir -p /skills/{skill_name}"
            f" && unzip -o /skills/{filename} -d /skills/{skill_name}"
            f" && rm -f /skills/{filename}"
        )
        if result.exit_code != 0:
            return f"解压失败: {result.result}"

        # 7. 清理本地临时文件
        import shutil
        shutil.rmtree(local_tmpdir, ignore_errors=True)

        return f"skill 安装成功，已解压至 sandbox /skills 目录（来源: {download_url}）"

    except Exception as e:
        import shutil
        shutil.rmtree(local_tmpdir, ignore_errors=True)
        return f"skill 安装失败: {e}"
