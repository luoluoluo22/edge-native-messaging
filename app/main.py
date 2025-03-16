import json
import sys
import struct
import time
import atexit
import threading
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from typing import Dict
import logging
import os
from logging.handlers import RotatingFileHandler
import signal
import asyncio
from starlette.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

# 配置日志
def setup_logger():
    """配置日志记录器"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 创建主日志记录器
    logger = logging.getLogger('main')
    logger.setLevel(logging.DEBUG)
    
    # 创建一个按大小轮转的文件处理器
    log_file = os.path.join(log_dir, 'app.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024*1024,  # 1MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # 创建一个专门用于SSE服务的文件处理器
    sse_log_file = os.path.join(log_dir, 'sse_service.log')
    sse_file_handler = RotatingFileHandler(
        sse_log_file,
        maxBytes=1024*1024,  # 1MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # 创建日志过滤器
    class QuietFilter(logging.Filter):
        def filter(self, record):
            return not getattr(record, 'quiet', False)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    file_handler.addFilter(QuietFilter())  # 添加过滤器
    sse_file_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    
    # 创建SSE专用记录器
    sse_logger = logging.getLogger('sse')
    sse_logger.setLevel(logging.DEBUG)
    sse_logger.addHandler(sse_file_handler)
    
    return logger, sse_logger

# 创建日志记录器
logger, sse_logger = setup_logger()

# 创建MCP服务器实例
mcp = FastMCP("本地消息推送服务")

# 读取来自 stdin 的消息并对其进行解码
def get_message():
    try:
        # 检查输入流是否可用
        if not hasattr(sys.stdin, 'buffer') or not sys.stdin.buffer.readable():
            logger.error("输入流不可用")
            time.sleep(1)
            return None
            
        raw_length = sys.stdin.buffer.read(4)
        if not raw_length:
            # 这是正常的无消息状态，使用最低级别的日志
            logger.debug("等待新消息...", extra={"quiet": True})  # 添加extra参数用于过滤
            time.sleep(1)  # 等待1秒后继续检查
            return None
        
        message_length = struct.unpack('=I', raw_length)[0]
        message = sys.stdin.buffer.read(message_length).decode("utf-8")
        logger.debug(f"收到来自插件的消息: {message}")
        return json.loads(message)
    except struct.error as e:
        logger.error(f"解析消息长度时出错: {str(e)}")
        time.sleep(1)
        return None
    except json.JSONDecodeError as e:
        logger.error(f"解析JSON消息时出错: {str(e)}")
        time.sleep(1)
        return None
    except Exception as e:
        logger.error(f"读取消息时出错: {str(e)}")
        time.sleep(1)
        return None

# 根据信息的内容对信息进行编码以便传输
def encode_message(message_content):
    try:
        if isinstance(message_content, str):
            message_content = {"type": "response", "content": message_content}
            
        # 确保消息内容是字典类型
        if not isinstance(message_content, dict):
            raise ValueError("消息内容必须是字典类型")
            
        # 确保必要的字段存在
        if "type" not in message_content:
            message_content["type"] = "response"
            
        encoded_content = json.dumps(message_content).encode("utf-8")
        encoded_length = struct.pack('=I', len(encoded_content))
        logger.debug(f"编码消息: {message_content}")
        return {'length': encoded_length, 'content': encoded_content}
    except Exception as e:
        logger.error(f"消息编码失败: {str(e)}")
        return None
 
# 向标准输出发送编码好的消息
def send_message(encoded_message):
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # 检查输出流是否可用
            if not sys.stdout or sys.stdout.closed:
                raise IOError("标准输出流已关闭")
                
            if not hasattr(sys.stdout, 'buffer') or not sys.stdout.buffer.writable():
                raise IOError("标准输出流缓冲区不可写")
                
            # 检查消息格式
            if not isinstance(encoded_message, dict) or 'length' not in encoded_message or 'content' not in encoded_message:
                raise ValueError("无效的消息格式")
                
            # 检查消息内容
            if not encoded_message['length'] or not encoded_message['content']:
                raise ValueError("消息内容为空")
                
            # 发送消息长度
            bytes_written = sys.stdout.buffer.write(encoded_message['length'])
            if bytes_written != len(encoded_message['length']):
                raise IOError(f"消息长度写入不完整: {bytes_written}/{len(encoded_message['length'])}")
                
            # 发送消息内容
            bytes_written = sys.stdout.buffer.write(encoded_message['content'])
            if bytes_written != len(encoded_message['content']):
                raise IOError(f"消息内容写入不完整: {bytes_written}/{len(encoded_message['content'])}")
                
            sys.stdout.buffer.flush()
            
            logger.debug(f"发送消息成功: {encoded_message['content'].decode('utf-8')}")
            return True
            
        except (IOError, ValueError) as e:
            error_msg = f"发送消息时出错 (尝试 {retry_count + 1}/{max_retries}): {str(e)}"
            if "Invalid argument" in str(e):
                error_msg += " - 可能是输出流已关闭或损坏"
            logger.error(error_msg)
            
            retry_count += 1
            if retry_count < max_retries:
                time.sleep(1)
                # 尝试重新初始化stdout
                try:
                    sys.stdout = open(sys.stdout.fileno(), mode='wb', buffering=0)
                except Exception as e:
                    logger.error(f"重新初始化stdout失败: {str(e)}")
            
    return False

def send_exit_message():
    """程序退出时发送消息"""
    try:
        exit_message = {
            "type": "system",
            "content": "本地应用程序即将关闭",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        send_message(encode_message(exit_message))
        logger.info("已发送退出消息")
    except Exception as e:
        logger.error(f"发送退出消息时出错: {str(e)}")
        print(f"发送退出消息时出错: {str(e)}", file=sys.stderr)

# 创建SSE传输层
sse = SseServerTransport("/messages/")

# 定义SSE处理函数
async def handle_sse(request):
    try:
        sse_logger.info("收到新的SSE连接请求")
        
        # 记录请求信息
        client_info = {
            "ip": request.client.host if hasattr(request, "client") and hasattr(request.client, "host") else "未知",
            "user_agent": request.headers.get("user-agent", "未知"),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        sse_logger.info(f"客户端信息: {json.dumps(client_info, ensure_ascii=False)}")
        
        # 建立SSE连接
        async with sse.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
            sse_logger.info("SSE连接已建立")
            
            # 不直接发送欢迎消息，让MCP服务器处理通信
            try:
                # 运行MCP服务器
                await mcp._mcp_server.run(read_stream, write_stream, mcp._mcp_server.create_initialization_options())
            except Exception as e:
                sse_logger.error(f"MCP服务器运行出错: {str(e)}")
                # 不抛出异常，让连接正常关闭
            
        sse_logger.info("SSE连接已关闭")
        return Response(status_code=200)
    except Exception as e:
        sse_logger.error(f"SSE连接处理出错: {str(e)}")
        return Response(status_code=500)

# 创建路由
routes = [
    Route("/sse", endpoint=handle_sse),
    Mount("/messages/", app=sse.handle_post_message),
]

# 修改send_notification函数
@mcp.tool()
def send_notification(message: str) -> Dict:
    """发送通知消息到Chrome插件"""
    try:
        if not message or not isinstance(message, str):
            error_msg = "消息内容无效"
            sse_logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        notification = {
            "type": "notification",
            "content": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 通过标准输出发送消息到插件
        encoded_msg = encode_message(notification)
        if not encoded_msg:
            error_msg = "消息编码失败"
            sse_logger.error(error_msg)
            return {"status": "error", "message": error_msg}
            
        send_result = send_message(encoded_msg)
        
        # 同时通过SSE发送消息
        try:
            sse_logger.info(f"通过SSE发送消息: {message}")
            
            # 创建一个线程来运行异步广播函数
            def run_broadcast():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    # 使用更简单的消息格式
                    sse_message = {
                        "jsonrpc": "2.0", 
                        "method": "notification", 
                        "params": {
                            "type": "notification",
                            "content": message,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                    }
                    loop.run_until_complete(sse.broadcast(json.dumps(sse_message)))
                    sse_logger.info("SSE消息广播成功")
                except Exception as e:
                    sse_logger.error(f"SSE广播执行失败: {str(e)}")
                finally:
                    loop.close()
            
            # 启动线程
            broadcast_thread = threading.Thread(target=run_broadcast)
            broadcast_thread.daemon = True
            broadcast_thread.start()
            
        except Exception as e:
            sse_logger.error(f"SSE消息发送失败: {str(e)}")
            # 即使SSE发送失败，只要标准输出发送成功，我们仍然认为消息发送成功
        
        if send_result:
            return {"status": "success", "message": "消息已发送"}
        else:
            return {"status": "error", "message": "消息发送失败"}
            
    except Exception as e:
        error_msg = f"发送消息时出错: {str(e)}"
        sse_logger.error(error_msg)
        return {"status": "error", "message": error_msg}

def graceful_shutdown(signum, frame):
    """优雅关闭服务器"""
    sse_logger.info("收到关闭信号，开始优雅关闭...")
    
    try:
        # 发送退出消息
        exit_message = {
            "type": "system",
            "content": "服务器即将关闭",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        send_message(encode_message(exit_message))
    except Exception as e:
        sse_logger.error(f"发送关闭消息失败: {str(e)}")
    
    # 等待一段时间让消息发送完成
    time.sleep(2)
    
    # 关闭服务器
    sys.exit(0)

# 创建Starlette应用
app = Starlette(routes=routes)

def start_sse_server():
    """启动SSE服务器"""
    try:
        # 保存原始的标准输出流
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        # 配置服务器
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=8888,
            log_level="info",
            log_config=None,  # 禁用uvicorn的默认日志配置
            lifespan="on"
        )
        
        # 创建服务器实例
        server = uvicorn.Server(config)
        
        # 恢复标准输出流
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
        sse_logger.info("SSE服务器正在启动...")
        
        # 使用异步方式运行服务器
        try:
            asyncio.run(server.serve())
        except RuntimeError as e:
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                # 如果已经在事件循环中，使用不同的方法启动
                sse_logger.warning("检测到已有事件循环，使用替代方法启动服务器")
                loop = asyncio.get_event_loop()
                loop.run_until_complete(server.serve())
            else:
                raise
        
    except Exception as e:
        sse_logger.error(f"SSE服务器启动失败: {str(e)}")
        # 记录详细的异常信息
        import traceback
        sse_logger.error(f"异常详情: {traceback.format_exc()}")
        raise
    finally:
        sse_logger.info("SSE服务器已停止")

@mcp.resource("message://help")
def get_help() -> str:
    """提供消息推送服务的使用说明"""
    return """
    这是一个本地消息推送服务，提供以下功能：
    1. send_notification(message): 发送通知消息到Chrome插件
    
    使用方法：
    1. 通过SSE连接接收消息：
       - 连接到 http://localhost:8888/sse
       
    2. 发送消息：
       - 发送POST请求到 http://localhost:8888/messages/
       
    消息格式：
    {
        "method": "send_notification",
        "params": {
            "message": "你的消息内容"
        }
    }
    """

def main():
    # 注册信号处理
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    # 注册退出处理函数
    atexit.register(send_exit_message)
    
    # 保存原始的标准输出流
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    connection_retry_count = 0
    max_connection_retries = 5
    last_connection_check = time.time()
    connection_check_interval = 30
    
    while connection_retry_count < max_connection_retries:
        try:
            # 确保使用原始的标准输出流
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            # 启动SSE服务器线程
            sse_logger.info("正在启动SSE服务器线程...")
            server_thread = threading.Thread(target=start_sse_server, daemon=True)
            server_thread.start()
            
            # 等待服务器启动
            sse_logger.info("等待SSE服务器启动...")
            time.sleep(2)
            
            # 发送启动消息
            startup_message = {
                "type": "system",
                "content": "本地应用程序已启动",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            if not send_message(encode_message(startup_message)):
                raise Exception("无法发送启动消息")
            
            logger.info("本地应用程序已启动")
            
            # 重置连接重试计数
            connection_retry_count = 0
            
            # 持续监听chrome插件发来的消息
            consecutive_errors = 0
            empty_reads = 0
            while True:
                # 确保使用原始的标准输出流
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                
                current_time = time.time()
                
                # 定期检查连接状态
                if current_time - last_connection_check >= connection_check_interval:
                    logger.debug("执行定期连接状态检查")
                    last_connection_check = current_time
                    
                    try:
                        # 发送心跳消息
                        heartbeat = {
                            "type": "heartbeat",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        if not send_message(encode_message(heartbeat)):
                            logger.warning("心跳消息发送失败")
                            raise Exception("心跳消息发送失败")
                    except Exception as e:
                        logger.error(f"心跳检查失败: {str(e)}")
                        break  # 跳出内层循环，触发重连
                
                try:
                    message = get_message()
                    
                    if message is None:
                        empty_reads += 1
                        if empty_reads >= 30:  # 如果连续30次（约30秒）都没有读到消息
                            logger.warning("长时间未收到消息，检查连接状态")
                            empty_reads = 0  # 重置计数器
                        continue
                    
                    empty_reads = 0  # 成功读取消息，重置计数器
                    
                    if isinstance(message, dict):
                        if message.get("action") == "init":
                            logger.info("收到初始化消息")
                            # 发送确认响应
                            init_response = {
                                "type": "system",
                                "content": "初始化成功",
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            send_message(encode_message(init_response))
                            continue
                        elif message.get("action") == "heartbeat":
                            logger.debug("收到心跳响应")
                            continue
                            
                    # 处理常规消息
                    if message == "用户点击了按钮1":
                        send_message(encode_message("来自exe程序的消息：按钮1被点击"))
                    elif message == "用户点击了按钮2":
                        send_message(encode_message("来自exe程序的消息：按钮2被点击"))
                    elif message == "用户点击了按钮3":
                        send_message(encode_message("来自exe程序的消息：按钮3被点击"))
                    elif message == "用户点击了按钮4":
                        time.sleep(3)
                        send_message(encode_message("来自exe程序的消息：按钮4被点击"))
                        
                except Exception as e:
                    logger.error(f"处理消息时出错: {str(e)}")
                    consecutive_errors += 1
                    if consecutive_errors >= 3:  # 如果连续出错3次
                        break  # 跳出内层循环，触发重连
                    continue
                    
                consecutive_errors = 0  # 成功处理消息，重置错误计数
                    
        except Exception as e:
            logger.error(f"程序运行时出错 (尝试 {connection_retry_count + 1}/{max_connection_retries}): {str(e)}")
            connection_retry_count += 1
            if connection_retry_count < max_connection_retries:
                time.sleep(5)  # 等待5秒后重试
            else:
                logger.error("达到最大重试次数，程序退出")
                sys.exit(1)

if __name__ == '__main__':
    main()