# 本地消息推送服务

这是一个基于Python的本地消息推送服务，支持通过Server-Sent Events (SSE)向Chrome插件推送消息。

## 功能特点

- 支持SSE连接实时推送消息
- 提供REST API接口发送消息
- 支持心跳检测
- 优雅的服务启动和关闭机制
- 完整的日志记录

## 安装要求

- Python 3.7+
- uvicorn
- starlette
- fastmcp

## 安装步骤

1. 克隆仓库：
```bash
git clone https://github.com/luoluoluo22/local-message-push-service.git
cd local-message-push-service
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

1. 启动服务器：
```bash
python app/main.py
```

2. 通过SSE连接接收消息：
- 连接地址：`http://localhost:8888/sse`

3. 发送消息：
- 发送POST请求到：`http://localhost:8888/messages/`
- 消息格式：
```json
{
    "method": "send_notification",
    "params": {
        "message": "你的消息内容"
    }
}
```

## 配置说明

- 服务器默认运行在 `127.0.0.1:8888`
- 日志文件位于 `logs` 目录下
  - `app.log`: 主程序日志
  - `sse_service.log`: SSE服务日志

## 许可证

MIT License 