module.exports = {
  apps: [
    {
      name: 'markdown-service',
      script: 'markdown_server.py', // 直接指定 Python 脚本文件
      interpreter: 'C:\\Program Files\\WindowsApps\\PythonSoftwareFoundation.Python.3.13_3.13.752.0_x64__qbz5n2kfra8p0\\python.exe', // 指定Python解释器绝对路径
      interpreter_args: '-u', // 添加-u参数确保Python输出不缓冲
      cwd: './', // 工作目录
      watch: false, // 不监视文件变化
      instances: 1, // 实例数量
      exec_mode: 'fork', // 执行模式
      max_memory_restart: '200M', // 内存使用超过200M时重启
      env: {
        NODE_ENV: 'production',
        PYTHONIOENCODING: 'utf-8' // 设置Python的编码
      },
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
      error_file: './logs/markdown-service-error.log',
      out_file: './logs/markdown-service-out.log',
      merge_logs: true,
      autorestart: true, // 自动重启
      restart_delay: 5000 // 重启延迟5秒
    }
  ]
}; 