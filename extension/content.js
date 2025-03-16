var launch_message;

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
        // 尝试解析JSON字符串
        let messageObj;
        if (typeof request === 'string') {
            messageObj = JSON.parse(request);
        } else {
            messageObj = request;
        }
        
        // 显示消息
        const message = document.querySelector('.message');
        if (message) {
            const newH3 = document.createElement('h3');
            newH3.textContent = JSON.stringify(messageObj);
            message.appendChild(newH3);
        } else {
            console.log('未找到.message元素，无法显示消息');
        }
    } catch (error) {
        console.error('处理消息时出错:', error);
    }
    
    return true;
});