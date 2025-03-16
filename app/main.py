import json
import sys
import struct
import time
import atexit
import threading
from datetime import datetime
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from typing import Dict
import logging
import os
from logging.handlers import RotatingFileHandler
import signal
import asyncio
from starlette.responses import JSONResponse
import uuid
import re
import html2text
import httpx

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
    
    # 创建一个专门用于API服务的文件处理器
    api_log_file = os.path.join(log_dir, 'api_service.log')
    api_file_handler = RotatingFileHandler(
        api_log_file,
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
    api_file_handler.setFormatter(formatter)
    
    # 添加处理器到记录器
    logger.addHandler(file_handler)
    
    # 创建API专用记录器
    api_logger = logging.getLogger('api')
    api_logger.setLevel(logging.DEBUG)
    api_logger.addHandler(api_file_handler)
    
    return logger, api_logger

# 创建日志记录器
logger, api_logger = setup_logger()

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

# 向 stdout 写入消息
def send_message(encoded_message):
    try:
        # 检查输出流是否可用
        if not hasattr(sys.stdout, 'buffer') or not sys.stdout.buffer.writable():
            logger.error("输出流不可用")
            return False
    
        # 写入消息长度
        sys.stdout.buffer.write(encoded_message)
        sys.stdout.buffer.flush()
        return True
    except Exception as e:
        logger.error(f"发送消息时出错: {str(e)}")
        return False

# 将消息编码为二进制格式
def encode_message(message):
    try:
        # 将消息转换为JSON字符串
        if isinstance(message, dict) or isinstance(message, list):
            json_str = json.dumps(message, ensure_ascii=False)
        else:
            json_str = str(message)
            
        # 编码为二进制
        encoded_content = json_str.encode("utf-8")
        encoded_length = struct.pack('=I', len(encoded_content))
        
        return encoded_length + encoded_content
    except Exception as e:
        logger.error(f"编码消息时出错: {str(e)}")
        return None

def send_notification(message):
    """发送通知消息到Chrome插件"""
    try:
        notification_message = {
            "type": "notification",
            "content": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 编码消息
        encoded_msg = encode_message(notification_message)
        if not encoded_msg:
            logger.error("通知消息编码失败")
            return False
            
        # 发送消息
        send_result = send_message(encoded_msg)
        if send_result:
            logger.info(f"已发送通知消息: {message}")
        else:
            logger.error("通知消息发送失败")
            
        return send_result
    except Exception as e:
        logger.error(f"发送通知消息时出错: {str(e)}")
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

# 全局回调字典
callbacks = {}

# 全局存储字典，用于存储页面源码及转换结果
page_sources = {}

# 转换HTML为Markdown
def convert_html_to_markdown(html_content):
    """将HTML内容转换为Markdown格式"""
    try:
        # 创建html2text转换器实例
        converter = html2text.HTML2Text()
        # 配置转换器
        converter.ignore_links = False
        converter.ignore_images = False
        converter.body_width = 0  # 不限制宽度
        converter.protect_links = True  # 保护链接
        converter.unicode_snob = True  # 正确处理Unicode字符
        converter.single_line_break = True  # 使用单行换行
        
        # 转换HTML为Markdown
        markdown = converter.handle(html_content)
        
        # 一些简单的清理
        # 减少多余空行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)
        
        return markdown
    except Exception as e:
        api_logger.error(f"HTML转Markdown转换失败: {str(e)}")
        return f"转换失败: {str(e)}"

async def handle_index(request):
    """处理首页请求"""
    return JSONResponse({
        "message": "本地消息推送服务已启动",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "endpoints": {
            "发送通知": "/api/send-notification",
            "获取页面源码": "/api/get-page-source",
            "获取Markdown格式": "/api/get-webpage-markdown"
        }
    })

async def handle_send_notification(request):
    """处理发送通知请求"""
    try:
        body = await request.json()
        message = body.get("message")
        
        if not message:
            return JSONResponse({
                "status": "error",
                "message": "请提供通知消息"
            }, status_code=400)
        
        success = send_notification(message)
        
        if success:
            return JSONResponse({
                "status": "success",
                "message": "消息已发送"
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": "消息发送失败"
            }, status_code=500)
            
    except Exception as e:
        error_msg = f"处理通知请求时出错: {str(e)}"
        api_logger.error(error_msg)
        return JSONResponse({
            "status": "error",
            "message": error_msg
        }, status_code=500)

async def handle_get_page_source(request):
    """处理获取页面源码请求"""
    try:
        body = await request.json()
        request_id = body.get("request_id")
        
        # 如果没有请求ID，生成一个
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:8]}"
            
        api_logger.info(f"收到获取页面源码请求，ID: {request_id}")
        
        # 创建请求消息
        request_message = {
            "type": "get_page_source",
            "request_id": request_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 创建事件用于等待响应
        response_event = threading.Event()
        response_data = {"response": None}
        
        # 定义回调函数
        def handle_response(message):
            if isinstance(message, dict) and message.get("request_id") == request_id:
                response_data["response"] = message
                response_event.set()
        
        # 注册回调
        callbacks[request_id] = handle_response
        
        # 通过标准输出发送消息到插件
        encoded_msg = encode_message(request_message)
        if not encoded_msg:
            return JSONResponse({
                "status": "error",
                "message": "请求消息编码失败",
                "request_id": request_id
            }, status_code=500)
            
        send_result = send_message(encoded_msg)
        
        if not send_result:
            return JSONResponse({
                "status": "error", 
                "message": "页面源码请求发送失败", 
                "request_id": request_id
            }, status_code=500)
        
        # 创建一个后台任务来处理长时间等待的响应
        def wait_for_response():
            try:
                # 等待响应，最多等待60秒
                if response_event.wait(60):  # 修改超时时间为60秒
                    response = response_data["response"]
                    # 处理响应，可以保存到文件或执行其他操作
                    api_logger.info(f"收到页面源码响应，ID: {request_id}, URL: {response.get('url', '未知')}, 源码长度: {len(response.get('source_code', ''))}")
                else:
                    api_logger.error(f"等待页面源码响应超时，ID: {request_id}")
            except Exception as e:
                api_logger.error(f"处理页面源码响应时出错: {str(e)}")
            finally:
                # 清理回调
                if request_id in callbacks:
                    del callbacks[request_id]
                    
        # 启动后台线程
        bg_thread = threading.Thread(target=wait_for_response)
        bg_thread.daemon = True
        bg_thread.start()
        
        # 立即返回请求已接收的响应
        return JSONResponse({
            "status": "pending",
            "message": "页面源码请求已发送，等待响应",
            "request_id": request_id
        })
            
    except Exception as e:
        error_msg = f"请求页面源码时出错: {str(e)}"
        api_logger.error(error_msg)
        return JSONResponse({
            "status": "error",
            "message": error_msg
        }, status_code=500)

async def handle_page_source_result(request):
    """获取页面源码结果"""
    try:
        body = await request.json()
        request_id = body.get("request_id")
        
        if not request_id:
            return JSONResponse({
                "status": "error",
                "message": "缺少请求ID"
            }, status_code=400)
            
        # 检查是否有结果可用
        if request_id in callbacks:
            return JSONResponse({
                "status": "pending",
                "message": "页面源码请求仍在处理中"
            })
        elif request_id in page_sources:
            # 从存储中获取结果
            page_data = page_sources[request_id]
            return JSONResponse({
                "status": "success",
                "message": "页面源码请求已完成",
                "request_id": request_id,
                "url": page_data.get("url", "unknown"),
                "source_code_length": len(page_data.get("source_code", "")),
                "received_time": page_data.get("received_time")
            })
        else:
            # 检查是否已有结果保存
            return JSONResponse({
                "status": "completed",
                "message": "页面源码请求已完成，但结果不可用"
            })
            
    except Exception as e:
        error_msg = f"获取页面源码结果时出错: {str(e)}"
        api_logger.error(error_msg)
        return JSONResponse({
            "status": "error",
            "message": error_msg
        }, status_code=500)

async def handle_get_markdown(request):
    """获取页面源码的Markdown格式"""
    try:
        body = await request.json()
        request_id = body.get("request_id")
        
        if not request_id:
            return JSONResponse({
                "status": "error",
                "message": "缺少请求ID"
            }, status_code=400)
            
        # 检查是否有结果可用
        if request_id in page_sources:
            page_data = page_sources[request_id]
            
            # 检查是否已经有转换过的markdown
            if "markdown" not in page_data:
                # 如果没有转换过，就现在转换
                html_content = page_data.get("source_code", "")
                if html_content:
                    markdown = convert_html_to_markdown(html_content)
                    page_data["markdown"] = markdown
                    page_data["markdown_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    return JSONResponse({
                        "status": "error",
                        "message": "页面源码为空，无法转换"
                    }, status_code=400)
            
            # 返回markdown结果
            return JSONResponse({
                "status": "success",
                "message": "成功获取Markdown内容",
                "request_id": request_id,
                "url": page_data.get("url", "unknown"),
                "markdown_length": len(page_data["markdown"]),
                "markdown_time": page_data.get("markdown_time"),
                "markdown": page_data["markdown"]
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": "找不到指定请求ID的页面源码",
                "request_id": request_id
            }, status_code=404)
            
    except Exception as e:
        error_msg = f"获取Markdown结果时出错: {str(e)}"
        api_logger.error(error_msg)
        return JSONResponse({
            "status": "error",
            "message": error_msg
        }, status_code=500)

async def handle_get_webpage_markdown(request):
    """直接获取网页并转换为Markdown"""
    try:
        body = await request.json()
        url = body.get("url")
        
        if not url:
            return JSONResponse({
                "status": "error",
                "message": "请提供网页URL"
            }, status_code=400)
            
        # 生成一个请求ID
        request_id = f"md_{uuid.uuid4().hex[:8]}"
        api_logger.info(f"收到直接获取网页Markdown请求，ID: {request_id}, URL: {url}")
            
        # 创建一个后台任务来获取网页并转换
        def fetch_and_convert():
            try:
                api_logger.info(f"开始获取网页，ID: {request_id}, URL: {url}")
                
                # 使用httpx获取网页内容
                with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                    response = client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    })
                    
                    if response.status_code != 200:
                        api_logger.error(f"获取网页失败，状态码: {response.status_code}, ID: {request_id}")
                        page_sources[request_id] = {
                            "url": url,
                            "error": f"获取网页失败，状态码: {response.status_code}",
                            "status": "error"
                        }
                        return
                    
                    html_content = response.text
                    
                    # 保存网页源码
                    page_sources[request_id] = {
                        "url": url,
                        "source_code": html_content,
                        "received_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "completed"
                    }
                    
                    # 转换为Markdown
                    api_logger.info(f"开始转换为Markdown，ID: {request_id}")
                    markdown = convert_html_to_markdown(html_content)
                    page_sources[request_id]["markdown"] = markdown
                    page_sources[request_id]["markdown_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    page_sources[request_id]["status"] = "success"
                    api_logger.info(f"网页已转换为Markdown，ID: {request_id}, Markdown长度: {len(markdown)}")
                    
            except Exception as e:
                error_msg = f"获取并转换网页时出错: {str(e)}"
                api_logger.error(error_msg)
                page_sources[request_id] = {
                    "url": url,
                    "error": error_msg,
                    "status": "error"
                }
                
        # 启动后台线程
        bg_thread = threading.Thread(target=fetch_and_convert)
        bg_thread.daemon = True
        bg_thread.start()
        
        # 立即返回请求已接收的响应
        return JSONResponse({
            "status": "pending",
            "message": "网页Markdown请求已发送，正在处理中",
            "request_id": request_id,
            "url": url
        })
            
    except Exception as e:
        error_msg = f"请求网页Markdown时出错: {str(e)}"
        api_logger.error(error_msg)
        return JSONResponse({
            "status": "error",
            "message": error_msg
        }, status_code=500)

# 处理从插件返回的页面源码
def handle_page_source_response(message):
    """处理从插件返回的页面源码"""
    try:
        if not isinstance(message, dict):
            api_logger.error("页面源码响应格式无效")
            return False
            
        request_id = message.get("request_id")
        source_code = message.get("source_code")
        url = message.get("url", "未知URL")
        
        if not request_id or not source_code:
            api_logger.error("页面源码响应缺少必要字段")
            return False
            
        api_logger.info(f"收到页面源码响应，ID: {request_id}, URL: {url}, 源码长度: {len(source_code)}")
        
        # 保存页面源码到全局存储中
        page_sources[request_id] = {
            "url": url,
            "source_code": source_code,
            "received_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 预先转换为Markdown（在后台线程中进行）
        def convert_in_background():
            try:
                markdown = convert_html_to_markdown(source_code)
                page_sources[request_id]["markdown"] = markdown
                page_sources[request_id]["markdown_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                api_logger.info(f"页面源码已转换为Markdown，ID: {request_id}, Markdown长度: {len(markdown)}")
            except Exception as e:
                api_logger.error(f"后台转换Markdown时出错: {str(e)}")
        
        # 启动转换线程
        convert_thread = threading.Thread(target=convert_in_background)
        convert_thread.daemon = True
        convert_thread.start()
        
        # 调用回调函数
        if request_id in callbacks:
            callbacks[request_id](message)
            return True
        else:
            api_logger.warning(f"收到页面源码响应，但没有对应的回调函数，ID: {request_id}")
            return False
        
    except Exception as e:
        api_logger.error(f"处理页面源码响应时出错: {str(e)}")
        return False

def handle_set_active_page(message):
    """处理从插件发送的设置活跃页面请求"""
    try:
        if not isinstance(message, dict):
            logger.error("设置活跃页面请求格式无效")
            return False
            
        url = message.get("url", "")
        title = message.get("title", "")
        html_content = message.get("html_content", "")
        
        if not url or not html_content:
            logger.error("设置活跃页面请求缺少必要字段")
            return False
            
        logger.info(f"处理设置活跃页面请求，URL: {url}, 标题: {title}, 内容长度: {len(html_content)}")
        
        # 向MCP服务器发送设置活跃页面请求
        try:
            # 使用httpx发送POST请求到MCP服务器
            import httpx
            
            set_page_url = "http://localhost:8014/messages/"
            payload = {
                "type": "function_call",
                "id": str(uuid.uuid4()),
                "function": "set_active_page",
                "arguments": {
                    "url": url,
                    "html_content": html_content,
                    "title": title
                }
            }
            
            # 异步发送请求
            def send_request():
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(set_page_url, json=payload)
                        if response.status_code != 202:
                            logger.error(f"MCP服务器返回错误状态码: {response.status_code}")
                            return False
                        
                        logger.info("成功设置活跃页面")
                        
                        # 发送确认消息到浏览器插件
                        confirm_message = {
                            "type": "active_page_set",
                            "url": url,
                            "title": title,
                            "status": "success",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        send_message(encode_message(confirm_message))
                        return True
                except Exception as e:
                    logger.error(f"向MCP服务器发送设置活跃页面请求时出错: {str(e)}")
                    
                    # 发送错误消息到浏览器插件
                    error_message = {
                        "type": "active_page_set",
                        "url": url,
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    send_message(encode_message(error_message))
                    return False
            
            # 启动一个线程来发送请求
            thread = threading.Thread(target=send_request)
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"设置活跃页面时出错: {str(e)}")
            return False
        
    except Exception as e:
        logger.error(f"处理设置活跃页面请求时出错: {str(e)}")
        return False

def graceful_shutdown(signum, frame):
    """优雅关闭服务器"""
    api_logger.info("收到关闭信号，开始优雅关闭...")
    
    try:
        # 发送退出消息
        exit_message = {
            "type": "system",
            "content": "服务器即将关闭",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        send_message(encode_message(exit_message))
    except Exception as e:
        api_logger.error(f"发送关闭消息失败: {str(e)}")
    
    # 等待一段时间让消息发送完成
    time.sleep(2)
    
    # 关闭服务器
    sys.exit(0)

# 将handle_get_current_tab_markdown函数从文件末尾移到此处，
# 放在handle_get_webpage_markdown函数之后，
# routes列表定义之前

async def handle_get_current_tab_markdown(request):
    """直接获取当前标签页的Markdown内容"""
    try:
        # 生成一个唯一的请求ID
        request_id = f"current_tab_{uuid.uuid4().hex[:8]}"
        api_logger.info(f"收到获取当前标签页Markdown请求，ID: {request_id}")
        
        # 获取当前页面源码
        page_source_result = get_page_source(request_id)
        
        if page_source_result.get("status") != "success":
            error_msg = page_source_result.get("message", "获取页面源码失败")
            api_logger.error(f"获取页面源码失败: {error_msg}")
            return JSONResponse({
                "status": "error",
                "message": error_msg,
                "request_id": request_id
            }, status_code=500)
        
        # 成功获取源码，开始转换为Markdown
        source_code = page_source_result.get("source_code", "")
        url = page_source_result.get("url", "未知URL")
        
        if not source_code:
            api_logger.error("获取到的页面源码为空")
            return JSONResponse({
                "status": "error",
                "message": "获取到的页面源码为空",
                "request_id": request_id
            }, status_code=500)
        
        # 转换为Markdown
        api_logger.info(f"开始转换为Markdown，ID: {request_id}, URL: {url}")
        markdown = convert_html_to_markdown(source_code)
        
        # 保存结果到全局存储
        page_sources[request_id] = {
            "url": url,
            "source_code": source_code,
            "markdown": markdown,
            "received_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "markdown_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        api_logger.info(f"页面已转换为Markdown，ID: {request_id}, Markdown长度: {len(markdown)}")
        
        # 返回Markdown内容
        return JSONResponse({
            "status": "success",
            "message": "成功获取当前标签页Markdown内容",
            "request_id": request_id,
            "url": url,
            "markdown_length": len(markdown),
            "markdown": markdown
        })
        
    except Exception as e:
        error_msg = f"获取当前标签页Markdown时出错: {str(e)}"
        api_logger.error(error_msg)
        return JSONResponse({
            "status": "error",
            "message": error_msg
        }, status_code=500)

# 创建路由
routes = [
    Route("/", endpoint=handle_index),
    Route("/api/send-notification", endpoint=handle_send_notification, methods=["POST"]),
    Route("/api/get-page-source", endpoint=handle_get_page_source, methods=["POST"]),
    Route("/api/page-source-result", endpoint=handle_page_source_result, methods=["POST"]),
    Route("/api/get-markdown", endpoint=handle_get_markdown, methods=["POST"]),
    Route("/api/get-webpage-markdown", endpoint=handle_get_webpage_markdown, methods=["POST"]),
    Route("/api/get-current-tab-markdown", endpoint=handle_get_current_tab_markdown, methods=["POST"]),
]

# 创建Starlette应用
app = Starlette(routes=routes)

def start_api_server():
    """启动API服务器"""
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
        
        api_logger.info("API服务器正在启动...")
        
        # 使用异步方式运行服务器
        try:
            asyncio.run(server.serve())
        except RuntimeError as e:
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                # 如果已经在事件循环中，使用不同的方法启动
                api_logger.warning("检测到已有事件循环，使用替代方法启动服务器")
                loop = asyncio.get_event_loop()
                loop.run_until_complete(server.serve())
            else:
                raise
        
    except Exception as e:
        api_logger.error(f"API服务器启动失败: {str(e)}")
        # 记录详细的异常信息
        import traceback
        api_logger.error(traceback.format_exc())

def get_page_source(request_id: str = None) -> Dict:
    """请求获取当前浏览器页面的源码"""
    try:
        # 如果没有请求ID，生成一个
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:8]}"
            
        logger.info(f"收到获取页面源码请求，ID: {request_id}")
        
        # 创建请求消息
        request_message = {
            "type": "get_page_source",
            "request_id": request_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 创建事件用于等待响应
        response_event = threading.Event()
        response_data = {"response": None}
        
        # 定义回调函数
        def handle_response(message):
            if isinstance(message, dict) and message.get("request_id") == request_id:
                response_data["response"] = message
                response_event.set()
        
        # 注册回调
        callbacks[request_id] = handle_response
        
        # 通过标准输出发送消息到插件
        encoded_msg = encode_message(request_message)
        if not encoded_msg:
            return {
                "status": "error",
                "message": "请求消息编码失败",
                "request_id": request_id
            }
            
        send_result = send_message(encoded_msg)
        
        if not send_result:
            return {
                "status": "error", 
                "message": "页面源码请求发送失败", 
                "request_id": request_id
            }
        
        # 发送通知
        logger.info(f"页面源码请求已发送，等待响应，ID: {request_id}")
        
        # 等待响应，最多等待60秒
        if response_event.wait(60):
            response = response_data["response"]
            return {
                "status": "success",
                "message": "成功获取页面源码",
                "request_id": request_id,
                "url": response.get("url", "unknown"),
                "source_code": response.get("source_code", "")
            }
        else:
            return {
                "status": "timeout",
                "message": "等待页面源码响应超时",
                "request_id": request_id
            }
            
    except Exception as e:
        error_msg = f"请求页面源码时出错: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg, "request_id": request_id if request_id else "unknown"}
    finally:
        # 清理回调
        if request_id in callbacks:
            del callbacks[request_id]

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
            
            # 启动API服务器线程
            api_logger.info("正在启动API服务器线程...")
            server_thread = threading.Thread(target=start_api_server, daemon=True)
            server_thread.start()
            
            # 等待服务器启动
            api_logger.info("等待API服务器启动...")
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
                        elif message.get("type") == "page_source_response":
                            # 处理页面源码响应
                            logger.info("收到页面源码响应")
                            handle_page_source_response(message)
                            continue
                        elif message.get("type") == "button_click":
                            button_message = message.get("message", "")
                            logger.info(f"收到按钮点击消息: {button_message}")
                            response = f"来自exe程序的消息：收到 {button_message}"
                            send_message(encode_message(response))
                            continue
                        elif message.get("type") == "set_active_page":
                            # 处理设置活跃页面请求
                            logger.info("收到设置活跃页面请求")
                            handle_set_active_page(message)
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

if __name__ == "__main__":
    main()