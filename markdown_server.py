from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from mcp.server.sse import SseServerTransport
import html2text
import re
import logging
import os
from datetime import datetime
from typing import Dict
import uuid
from logging.handlers import RotatingFileHandler
import requests
import json

# 配置日志
def setup_logger():
    """配置日志记录器"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建主日志记录器
    logger = logging.getLogger('markdown_server')
    logger.setLevel(logging.DEBUG)
    
    # 创建一个按大小轮转的文件处理器
    log_file = os.path.join(log_dir, 'markdown_server.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024*1024,  # 1MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# 创建日志记录器
logger = setup_logger()


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
        url = f"{API_URL}/api/get-current-tab-markdown"
        response = requests.post(url, json={}).json()
        print(response)
        
        # 返回Markdown内容
        return {
            "status": "success",
            "message": response
        }
        
    except Exception as e:
        error_msg = f"获取当前标签页Markdown时出错: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg
        }


@mcp.resource("markdown://help")
def get_help() -> str:
    """提供Markdown转换服务的帮助信息"""
    help_text = """
# 网页Markdown转换服务

这个服务可以将网页内容转换为Markdown格式。

## 可用功能


- **get_current_tab_markdown**: 获取当前标签页的Markdown内容


## 如何使用

1. 使用浏览器插件浏览到您想要转换的网页
2. 点击插件按钮自动设置当前活跃页面
3. 调用 `get_current_tab_markdown()` 获取Markdown内容

## 示例
```python
# 获取当前标签页的Markdown内容
result = await get_current_tab_markdown()
print(result["markdown"])
```
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
    # 显示启动信息
    logger.info("网页Markdown转换服务启动中...")
    logger.info("服务地址: http://localhost:8014")
    logger.info("MCP接口地址: http://localhost:8014/messages/")

    API_URL = "http://localhost:8888"
    # 启动服务
    uvicorn.run(app, host="127.0.0.1", port=8014) 