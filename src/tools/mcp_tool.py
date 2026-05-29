from langchain_mcp_adapters.client import MultiServerMCPClient

mcp_config = {
    "mcp-server-chart": {
        "command": "npx",
        "args": ["-y", "@antv/mcp-server-chart"]
    }
}

async def get_mcp_tools():
    client = MultiServerMCPClient(mcp_config)
    tools = await client.get_tools()
    return tools
