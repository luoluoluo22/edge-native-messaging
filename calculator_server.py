from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from mcp.server.sse import SseServerTransport

# 创建一个MCP服务器实例
mcp = FastMCP("计算器")

@mcp.tool()
def add(a: float, b: float) -> float:
    """
    计算两个数的和

    Args:
        a: 第一个数字
        b: 第二个数字
        
    Returns:
        计算结果
    """
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """
    计算两个数的差

    Args:
        a: 被减数
        b: 减数
        
    Returns:
        计算结果
    """
    return a - b

@mcp.tool()
def multiply(a: float, b: float) -> float:
    """
    计算两个数的乘积

    Args:
        a: 第一个因数
        b: 第二个因数
        
    Returns:
        计算结果
    """
    return a * b

@mcp.tool()
def divide(a: float, b: float) -> float:
    """
    计算两个数的商

    Args:
        a: 被除数
        b: 除数（不能为0）
        
    Returns:
        计算结果
    """
    if b == 0:
        raise ValueError("除数不能为0！")
    return a / b

@mcp.resource("calculator://help")
def get_help() -> str:
    """提供计算器的使用说明"""
    return """
    这是一个简单的计算器，提供以下功能：
    1. add(a, b): 计算两个数的和
    2. subtract(a, b): 计算两个数的差
    3. multiply(a, b): 计算两个数的乘积
    4. divide(a, b): 计算两个数的商（b不能为0）
    """

@mcp.prompt()
def calculate_prompt(operation: str, a: float, b: float) -> str:
    """创建计算提示"""
    return f"请使用{operation}工具计算{a}和{b}的结果。"

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

if __name__ == "__main__":
    # 使用uvicorn在8013端口运行
    uvicorn.run(app, host="0.0.0.0", port=8013) 