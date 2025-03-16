var launch_message;

// 创建通知元素样式
const notificationStyle = `
.plugin-notification {
    position: fixed;
    top: 20px;
    right: 20px;
    background-color: #4CAF50;
    color: white;
    padding: 16px;
    border-radius: 4px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    z-index: 10000;
    opacity: 0;
    transition: opacity 0.3s ease-in-out;
    max-width: 300px;
    font-size: 14px;
    font-family: 'Arial', sans-serif;
}
.plugin-notification.show {
    opacity: 1;
}
.plugin-notification.error {
    background-color: #f44336;
}
.plugin-notification.warning {
    background-color: #ff9800;
}
.plugin-notification.success {
    background-color: #4CAF50;
}
`;

// 添加样式到页面
const styleEl = document.createElement('style');
styleEl.textContent = notificationStyle;
document.head.appendChild(styleEl);

// 页面加载完成时显示通知
document.addEventListener('DOMContentLoaded', function() {
    console.log('页面加载完成，插件已准备就绪');
    
    // 延迟显示通知，让页面有时间完全渲染
    setTimeout(() => {
        showNotification('页面已加载，Markdown转换服务已自动连接', 'info', 3000);
    }, 1500);
});

// 显示通知函数
function showNotification(message, type = 'success', duration = 4000) {
    // 移除任何现有通知
    const existingNotifications = document.querySelectorAll('.plugin-notification');
    existingNotifications.forEach(el => document.body.removeChild(el));
    
    // 创建新通知
    const notification = document.createElement('div');
    notification.className = `plugin-notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // 显示通知
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // 定时关闭通知
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            try {
                document.body.removeChild(notification);
            } catch (e) {
                console.log('通知元素已被移除');
            }
        }, 300);
    }, duration);
}

// Listen for custom events (myCustomEvent1 through myCustomEvent4)
for (let i = 1; i <= 4; i++) {
    document.addEventListener('myCustomEvent' + i, function(evt) {
        // Send message to background.js
        chrome.runtime.sendMessage({
            type: "用户点击了按钮",
            message: evt.detail
        }, function(response) {});
    }, false);
}

// Listen for messages from background.js
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    console.log('内容脚本收到消息:', request);
    
    // 处理插件激活消息
    if (typeof request === 'object' && request.type === 'plugin_activated') {
        console.log('收到插件激活通知:', request.message);
        showNotification(request.message, 'success');
        sendResponse({ status: "success", message: "通知已显示" });
        return false;
    }
    
    // 处理获取页面源码请求
    if (typeof request === 'object' && request.type === 'get_page_source') {
        console.log('收到获取页面源码请求，ID:', request.request_id);
        
        try {
            // 获取页面的完整HTML
            const html = document.documentElement.outerHTML;
            console.log(`获取到页面源码，长度: ${html.length}`);
            
            // 发送源码回背景脚本
            sendResponse({
                source_code: html,
                request_id: request.request_id
            });
        } catch (error) {
            console.error('获取页面源码时出错:', error);
            sendResponse({
                error: error.message,
                request_id: request.request_id
            });
        }
        
        return true; // 保持消息通道开放，以便异步响应
    }
    
    // 处理其他消息（显示在页面上）
    try {
        // 处理消息对象
        let messageObj;
        if (typeof request === 'string') {
            // 如果是字符串，尝试解析为JSON
            try {
                messageObj = JSON.parse(request);
            } catch (e) {
                // 如果解析失败，直接使用字符串
                messageObj = { content: request };
            }
        } else {
            // 直接使用对象
            messageObj = request;
        }
        
        // 显示消息
        const message = document.querySelector('.message');
        if (message) {
            const newH3 = document.createElement('h3');
            newH3.textContent = typeof messageObj === 'object' ? 
                JSON.stringify(messageObj) : String(messageObj);
            message.appendChild(newH3);
            console.log('消息已显示在页面上');
        } else {
            console.log('未找到.message元素，无法显示消息，使用通知显示:', messageObj);
            showNotification(
                typeof messageObj === 'object' ? JSON.stringify(messageObj) : String(messageObj),
                'info'
            );
        }
    } catch (error) {
        console.error('处理消息时出错:', error);
    }
    
    // 不需要异步响应，所以不返回true
    return false;
});