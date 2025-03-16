from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from mcp.server.sse import SseServerTransport
from typing import Dict
import requests

# 创建一个MCP服务器实例
mcp = FastMCP("网页Markdown转换服务")

@mcp.tool()
async def get_current_tab_markdown() -> Dict:
    """
    获取当前标签页的Markdown内容
    
    Returns:
        包含当前标签页Markdown内容的字典
    """
    try:
        # 检查是否有当前活跃页面
        url = "http://localhost:8888/api/get-current-tab-markdown"
        response = requests.post(url, json={}).json()
        print(response)
        
        # 返回Markdown内容
        return {
            "status": "success",
            "message": response
        }
        
    except Exception as e:
        error_msg = f"获取当前标签页Markdown时出错: {str(e)}"
        return {
            "status": "error",
            "message": error_msg
        }


@mcp.resource("markdown://help")
def get_help() -> str:
    """提供服务的帮助信息"""
    help_text = """
# 网页服务

这个服务可以获取当前标签页的网页内容转换为Markdown格式。

## 可用功能

- **get_current_tab_markdown**: 获取当前标签页的Markdown内容

## 如何使用

1. 使用浏览器插件浏览到您想要转换的网页
2. 点击插件按钮自动设置当前活跃页面
3. 调用 `get_current_tab_markdown()` 获取Markdown内容
"""
    return help_text

@mcp.prompt()
def markdown_prompt() -> str:
    """创建一个转换提示"""
    return """
你现在正在使用查看当前浏览器活动标签页服务，可以获取当前标签页相关内容。
可以尝试以下操作：
1. 使用get_current_tab_markdown()获取当前标签页的Markdown内容
"""

# 创建SSE传输层
sse = SseServerTransport("/messages/")

# 定义SSE处理函数
async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp._mcp_server.run(read_stream, write_stream, mcp._mcp_server.create_initialization_options())

# 创建路由
routes = [
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=sse.handle_post_message),
]

# 创建Starlette应用
app = Starlette(routes=routes)

# 启动服务器
if __name__ == "__main__":
    API_URL = "http://localhost:8888"
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=8014) 