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

// 提取页面有效内容的函数
function extractPageContent() {
    // 创建一个新的文档片段来存储处理后的内容
    const cleanDoc = document.implementation.createHTMLDocument();
    const cleanBody = cleanDoc.body;
    
    // 复制原始文档的body内容
    const originalContent = document.body.cloneNode(true);
    
    // 清理函数：移除脚本和样式
    function cleanNode(node) {
        const nodesToRemove = [];
        
        // 遍历所有子节点
        for (let child of node.children) {
            // 移除脚本标签
            if (child.tagName === 'SCRIPT' || 
                child.tagName === 'STYLE' || 
                child.tagName === 'LINK' ||
                child.tagName === 'NOSCRIPT') {
                nodesToRemove.push(child);
                continue;
            }
            
            // 移除隐藏元素
            const style = window.getComputedStyle(child);
            if (style.display === 'none' || style.visibility === 'hidden') {
                nodesToRemove.push(child);
                continue;
            }
            
            // 移除所有内联样式和类名，但保留布局相关属性
            child.removeAttribute('class');
            child.removeAttribute('id');
            
            // 只保留布局相关的样式
            const computedStyle = window.getComputedStyle(child);
            const layoutStyles = {
                display: computedStyle.display,
                position: computedStyle.position,
                float: computedStyle.float,
                margin: computedStyle.margin,
                padding: computedStyle.padding,
                width: computedStyle.width,
                height: computedStyle.height
            };
            
            // 设置简化后的样式
            Object.assign(child.style, layoutStyles);
            
            // 递归处理子元素
            if (child.children.length > 0) {
                cleanNode(child);
            }
        }
        
        // 移除标记的节点
        nodesToRemove.forEach(n => n.parentNode.removeChild(n));
    }
    
    // 清理内容
    cleanNode(originalContent);
    
    // 将清理后的内容添加到新文档中
    cleanBody.appendChild(originalContent);
    
    // 创建基本的HTML结构
    const html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${document.title}</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; }
        img { max-width: 100%; height: auto; }
    </style>
</head>
<body>
    ${cleanBody.innerHTML}
</body>
</html>`;
    
    return html;
}

// 处理base64数据的函数
function processBase64Content(html) {
    // 创建一个临时的DOM元素来解析HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    // 处理所有图片元素
    const images = tempDiv.getElementsByTagName('img');
    for (let img of Array.from(images)) {
        const src = img.getAttribute('src');
        if (src && src.startsWith('data:image')) {
            // 获取图片类型
            const imageType = src.split(';')[0].split('/')[1];
            // 替换为占位符
            img.setAttribute('src', `[base64_image:${imageType}]`);
            // 保存原始尺寸信息
            if (img.width && img.height) {
                img.setAttribute('data-original-size', `${img.width}x${img.height}`);
            }
        }
    }
    
    // 处理CSS中的base64
    const styles = tempDiv.getElementsByTagName('style');
    for (let style of Array.from(styles)) {
        let cssText = style.textContent;
        // 替换CSS中的base64图片
        cssText = cssText.replace(/url\(["']?data:image\/[^;]+;base64,[^"')]+["']?\)/g, 
            (match) => {
                const imageType = match.split(';')[0].split('/')[1];
                return `url("[base64_image:${imageType}]")`;
            }
        );
        style.textContent = cssText;
    }
    
    // 处理内联样式中的base64
    const elementsWithStyle = tempDiv.querySelectorAll('[style*="base64"]');
    for (let el of Array.from(elementsWithStyle)) {
        let styleText = el.getAttribute('style');
        // 替换内联样式中的base64图片
        styleText = styleText.replace(/url\(["']?data:image\/[^;]+;base64,[^"')]+["']?\)/g,
            (match) => {
                const imageType = match.split(';')[0].split('/')[1];
                return `url("[base64_image:${imageType}]")`;
            }
        );
        el.setAttribute('style', styleText);
    }
    
    return tempDiv.innerHTML;
}

// 修改获取页面源码的函数
async function getPageSource() {
    try {
        let html;
        // 尝试获取原始HTML
        try {
            const response = await fetch(window.location.href);
            html = await response.text();
        } catch (error) {
            console.log('获取原始HTML失败，使用DOM方式:', error);
            html = document.documentElement.outerHTML;
        }
        
        // 处理HTML中的base64内容
        console.log('开始处理base64内容...');
        const processedHtml = processBase64Content(html);
        
        // 构建完整的HTML文档
        const finalHtml = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${document.title}</title>
    <!-- Base64 images have been replaced with placeholders -->
</head>
<body>
    ${processedHtml}
</body>
</html>`;
        
        console.log('页面源码处理完成，已替换base64内容');
        return finalHtml;
        
    } catch (error) {
        console.error('处理页面源码时出错:', error);
        return document.documentElement.outerHTML;
    }
}

// 修改消息监听器中的页面源码获取部分
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
        
        // 使用异步方式获取页面源码
        getPageSource().then(html => {
            const stats = {
                originalLength: html.length,
                base64Count: (html.match(/\[base64_image:/g) || []).length
            };
            console.log(`获取到页面源码，长度: ${stats.originalLength}, 替换的base64图片数: ${stats.base64Count}`);
            
            sendResponse({
                source_code: html,
                request_id: request.request_id,
                stats: stats
            });
        }).catch(error => {
            console.error('获取页面源码时出错:', error);
            sendResponse({
                error: error.message,
                request_id: request.request_id
            });
        });
        
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