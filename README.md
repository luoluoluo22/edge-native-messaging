# 浏览器插件与本地应用通信

这个项目实现了浏览器插件与本地应用之间的双向通信，支持消息推送和页面源码获取功能。

## 功能特点

1. **消息推送**：本地应用可以向浏览器插件推送消息，显示在网页上
2. **事件响应**：浏览器插件可以捕获网页上的事件，并发送到本地应用
3. **页面源码获取**：本地应用可以请求获取当前浏览器页面的完整源码
4. **SSE通信**：使用Server-Sent Events实现实时通信

## 项目结构

```
.
├── app/                    # 本地应用程序
│   └── main.py             # 主程序
├── extension/              # 浏览器插件
│   ├── background.js       # 后台脚本
│   ├── content.js          # 内容脚本
│   └── manifest.json       # 插件配置
├── test_page.html          # 测试页面
├── test_page_source.py     # 页面源码获取测试脚本
├── test_sse_client.py      # SSE客户端测试脚本
├── simple_sse_test.py      # 简单SSE测试脚本
├── sseclient_test.py       # 使用sseclient库的测试脚本
└── sse_test.html           # SSE测试页面
```

## 安装与配置

### 1. 安装依赖

运行以下命令安装所需依赖：

```bash
pip install fastapi uvicorn starlette requests sseclient-py
```

### 2. 安装浏览器插件

1. 打开Chrome浏览器，进入扩展程序页面 `chrome://extensions/`
2. 开启"开发者模式"
3. 点击"加载已解压的扩展程序"，选择`extension`文件夹

### 3. 配置本地应用

1. 在Chrome浏览器中，确保已安装插件
2. 运行本地应用程序：`python app/main.py`

## 使用方法

### 测试消息推送

1. 打开`test_page.html`测试页面
2. 点击页面上的按钮，触发消息发送到本地应用
3. 本地应用会处理消息并返回响应，显示在页面上

### 测试页面源码获取

运行页面源码获取测试脚本：

```bash
python test_page_source.py
```

测试脚本提供以下功能：

1. 获取当前浏览器页面的源码
2. 保存源码到本地文件
3. 查看源码内容摘要

## 页面源码获取功能说明

### 工作流程

1. 本地应用发送获取页面源码请求到浏览器插件
2. 浏览器插件的后台脚本接收请求并转发到内容脚本
3. 内容脚本获取当前页面的完整HTML源码
4. 源码通过后台脚本返回到本地应用
5. 本地应用通过SSE将源码发送给客户端

### API说明

#### 1. 发送获取页面源码请求

```
POST http://127.0.0.1:8888/messages/
Content-Type: application/json

{
    "jsonrpc": "2.0",
    "method": "get_page_source",
    "params": {
        "request_id": "req_123456789"
    },
    "id": 1
}
```

#### 2. 接收页面源码响应

通过SSE连接 `http://127.0.0.1:8888/sse` 接收响应：

```json
{
    "jsonrpc": "2.0",
    "method": "page_source_response",
    "params": {
        "request_id": "req_123456789",
        "url": "https://example.com",
        "source_code": "<!DOCTYPE html><html>...</html>",
        "timestamp": "2023-05-20 12:34:56"
    }
}
```

## 注意事项

1. 确保浏览器插件已正确安装并启用
2. 本地应用需要有足够的权限运行
3. 页面源码获取功能仅适用于插件有权限访问的页面
4. 某些页面可能限制内容脚本的执行，导致无法获取源码

## 故障排除

1. **无法连接到本地应用**：检查本地应用是否正在运行，端口是否被占用
2. **无法获取页面源码**：检查浏览器插件权限，确保内容脚本能够在目标页面上运行
3. **SSE连接断开**：检查网络连接，可能需要重新连接

## 开发者信息

如有问题或建议，请联系开发者。 