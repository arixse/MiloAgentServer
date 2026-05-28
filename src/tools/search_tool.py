import os

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

@tool
def search_tool(query: str) -> str:
    """根据 query 内容搜索网络内容。

    Args:
        query: 需要搜索的内容。

    Returns:
        搜索的最终结果（摘要或相关网页内容）。
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "搜索失败: 未配置 TAVILY_API_KEY 环境变量"

    try:
        with httpx.Client(timeout=30) as http:
            resp = http.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if not results:
            return f"未找到与 '{query}' 相关的结果"

        lines = [f"搜索 '{query}' 的结果:"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")
            lines.append(f"\n{i}. {title}\n   URL: {url}\n   {content}")

        return "\n".join(lines)

    except Exception as e:
        return f"搜索失败: {e}"


@tool
def fetch_content(url: str) -> str:
    """根据 url 获取网页纯文本内容。

    Args:
        url: 需要获取内容的网页 URL。

    Returns:
        纯文本网页内容。
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as http:
            resp = http.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 移除 script / style 标签
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        # 压缩连续空行
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return text

    except Exception as e:
        return f"获取网页内容失败: {e}"
