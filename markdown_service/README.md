# Markdown服务管理脚本

这个文件夹包含了用于管理Markdown转换服务的PM2脚本，可以方便地启动、停止和重启服务。

## 前提条件

在使用这些脚本之前，您需要安装：

1. [Node.js](https://nodejs.org/)（包含npm）
2. PM2全局安装：`npm install -g pm2`
3. Python 3及必要的库：
   - html2text
   - uvicorn
   - starlette
   - mcp

## 快速开始

只需运行 `setup.bat` 一键配置环境，这将：
1. 检查 Node.js 是否已安装
2. 安装 PM2（如果需要）
3. 检查 Python 是否已安装
4. 安装所需的 Python 库

安装完成后，运行 `start.bat` 启动服务。

## 脚本说明

- **setup.bat**: 自动配置必要的环境和依赖
- **start.bat**: 启动Markdown服务
- **stop.bat**: 停止Markdown服务
- **restart.bat**: 重启Markdown服务
- **status.bat**: 查看Markdown服务状态
- **logs.bat**: 查看服务日志

## 使用方法

1. 配置环境：双击运行 `setup.bat`
2. 启动服务：双击运行 `start.bat`
3. 停止服务：双击运行 `stop.bat`
4. 重启服务：双击运行 `restart.bat`
5. 查看状态：双击运行 `status.bat`
6. 查看日志：双击运行 `logs.bat`

## 服务信息

- 服务名称：markdown-service
- 服务地址：http://localhost:8014
- 日志位置：./logs/

## API使用方法

服务启动后，可以通过以下方式获取当前浏览器标签页的Markdown内容：

1. 通过 MCP 客户端调用 `get_current_tab_markdown` 方法
2. 访问 API 端点: `http://localhost:8888/api/get-current-tab-markdown`

## 常用PM2命令

```bash
# 查看所有应用状态
pm2 status

# 查看应用日志
pm2 logs markdown-service

# 监控应用资源使用
pm2 monit
```

## 故障排除

如果服务无法启动，请检查：

1. 端口8014是否被占用
   - 使用命令 `netstat -ano | findstr 8014` 查看
   - 使用 `taskkill /F /PID <进程ID>` 关闭占用端口的进程

2. 检查日志文件获取更多信息
   - 查看 `./logs/markdown-service-error.log`
   - 运行 `logs.bat` 查看实时日志

3. 确保必要的Python库已安装
   - 运行 `setup.bat` 自动安装

## 注意事项

- 服务启动后会自动在后台运行
- 如果修改了markdown_server.py，需要重启服务生效
- 请确保markdown_server.py和ecosystem.config.js在同一目录下
- 如果遇到PM2相关问题，可以使用 `pm2 kill` 杀死所有PM2进程后重新启动 