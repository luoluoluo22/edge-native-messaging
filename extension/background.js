var port = null;
let isPolling = false;

// 启动轮询
function startPolling() {
    if (isPolling) return;
    isPolling = true;
    console.log('开始轮询本地应用消息...');
    pollMessages();
}

// 停止轮询
function stopPolling() {
    isPolling = false;
    console.log('停止轮询本地应用消息');
}

// 轮询消息
function pollMessages() {
    if (!isPolling) return;

    if (port === null) {
        connectToNativeHost({ action: "check_messages" });
    } else {
        console.log('发送轮询请求到本地应用');
        port.postMessage({ action: "check_messages" });
    }

    // 每3秒轮询一次
    setTimeout(pollMessages, 3000);
}

// 确保连接存在
function ensureConnection() {
    if (port === null) {
        connectToNativeHost({ action: "init" });
        return true;
    }
    return false;
}

// Listen for messages from content.js
chrome.runtime.onMessage.addListener(function(request, sender, sendResponse) {
    console.log('收到来自content.js的消息:', request);
    if (request.type == "用户点击了按钮") {
        console.log('用户触发了按钮点击事件，消息内容:', request.message);
        // 如果没有连接，先建立连接
        const isNewConnection = ensureConnection();
        // 如果不是新连接，直接发送消息
        if (!isNewConnection) {
            console.log('使用现有连接发送消息:', request.message);
            port.postMessage(request.message);
        }
    } else if (request.type == "开始轮询") {
        startPolling();
    } else if (request.type == "停止轮询") {
        stopPolling();
    }
    return true;
});

// Handle disconnection
function onDisconnected() {
    console.log('与本地应用的连接已断开');
    console.log('断开原因:', chrome.runtime.lastError);
    port = null;
    
    // 如果正在轮询，尝试重新连接
    if (isPolling) {
        console.log('将在3秒后尝试重新连接...');
        setTimeout(() => {
            connectToNativeHost({ action: "check_messages" });
        }, 3000);
    }
}

// Handle messages from native application
async function onNativeMessage(message) {
    console.log('收到来自本地应用的消息:', JSON.stringify(message, null, 2));
    try {
        // 处理心跳消息
        if (message.type === 'heartbeat') {
            console.log('收到心跳消息，发送响应');
            port.postMessage({ action: "heartbeat" });
            return;
        }
        
        const tabId = await getCurrentTabId();
        console.log('当前标签页ID:', tabId);
        if (tabId) {
            chrome.tabs.sendMessage(tabId, JSON.stringify(message), function(response) {
                console.log('消息已发送到content script');
            });
        } else {
            console.warn('未能获取到当前标签页ID');
        }
    } catch (error) {
        console.error('处理本地应用消息时出错:', error);
    }
}

// Get current tab ID
function getCurrentTabId() {
    console.log('正在获取当前标签页ID...');
    return new Promise((resolve, reject) => {
        chrome.tabs.query({
            active: true,
            currentWindow: true
        }, function(tabs) {
            if (tabs.length) {
                console.log('成功获取当前标签页:', tabs[0]);
                resolve(tabs[0].id);
            } else {
                console.warn('未找到活动标签页');
                resolve(null);
            }
        });
    });
}

// Connect to native host and establish communication port
function connectToNativeHost(msg) {
    if (port !== null) {
        try {
            port.postMessage(msg);
            console.log('已存在连接，直接发送消息');
            return;
        } catch (error) {
            console.error('发送消息失败，重新建立连接:', error);
            port = null;
        }
    }

    console.log('正在连接本地应用...');
    var nativeHostName = "com.my_company.my_application";
    try {
        port = chrome.runtime.connectNative(nativeHostName);
        console.log('已成功创建与本地应用的连接');
        
        port.onMessage.addListener(onNativeMessage);
        port.onDisconnect.addListener(onDisconnected);
        
        console.log('正在发送消息到本地应用:', msg);
        port.postMessage(msg);
    } catch (error) {
        console.error('连接本地应用时出错:', error);
        port = null;
    }
}