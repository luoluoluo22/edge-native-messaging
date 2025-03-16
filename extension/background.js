var port = null;

// 浏览器启动或插件加载时自动连接本地应用
console.log('插件已加载，正在自动连接本地应用...');
connectToNativeHost({ 
    action: "init", 
    message: "插件自动初始化",
    timestamp: new Date().toISOString()
});

// 添加监听browser_action点击事件
chrome.browserAction.onClicked.addListener(function(tab) {
    console.log('插件图标被点击，当前标签页:', tab);
    
    // 如果已经连接，则获取当前页面信息并设置为活跃页面
    if (port !== null) {
        setCurrentPageAsActive().then(success => {
            const message = success ? 
                "已成功将当前页面设置为活跃页面" : 
                "设置活跃页面失败，请检查控制台日志";
            
            // 向当前标签页的content脚本发送通知
            chrome.tabs.sendMessage(tab.id, { 
                type: "plugin_activated",
                message: message
            }, function(response) {
                if (chrome.runtime.lastError) {
                    console.warn('通知content script失败:', chrome.runtime.lastError.message);
                } else {
                    console.log('已通知content script:', response);
                }
            });
        });
    } else {
        // 如果未连接，则建立连接
        connectToNativeHost({ 
            action: "init",
            message: "用户点击了插件图标",
            url: tab.url,
            title: tab.title
        });
        
        // 向当前标签页的content脚本发送通知
        chrome.tabs.sendMessage(tab.id, { 
            type: "plugin_activated",
            message: "插件已激活，正在连接本地服务..."
        }, function(response) {
            if (chrome.runtime.lastError) {
                console.warn('通知content script失败:', chrome.runtime.lastError.message);
            } else {
                console.log('已通知content script插件已激活，响应:', response);
            }
        });
    }
});

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
            // 将消息包装为JSON对象发送，而不是直接发送原始字符串
            port.postMessage({
                type: "button_click",
                message: request.message,
                timestamp: new Date().toISOString()
            });
        }
    }
    return true;
});

// 尝试重新连接的函数
function tryReconnect() {
    console.log('尝试重新连接本地应用...');
    setTimeout(() => {
        connectToNativeHost({ 
            action: "init", 
            message: "自动重新连接尝试",
            timestamp: new Date().toISOString()
        });
    }, 5000); // 5秒后尝试重新连接
}

// Handle disconnection
function onDisconnected() {
    console.log('与本地应用的连接已断开');
    console.log('断开原因:', chrome.runtime.lastError);
    port = null;
    
    // 自动尝试重新连接
    tryReconnect();
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
        
        // 处理获取页面源码请求
        if (message.type === 'get_page_source') {
            console.log('收到获取页面源码请求，ID:', message.request_id);
            handleGetPageSource(message.request_id);
            return;
        }
        
        const tabId = await getCurrentTabId();
        console.log('当前标签页ID:', tabId);
        if (tabId) {
            // 不要将message转换为JSON字符串，直接传递对象
            // 并在处理响应时检查runtime.lastError
            chrome.tabs.sendMessage(tabId, message, function(response) {
                if (chrome.runtime.lastError) {
                    console.warn('向content script发送消息出错:', chrome.runtime.lastError.message);
                } else {
                    console.log('消息已发送到content script，响应:', response);
                }
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

// 增加一个函数用于获取当前页面内容并设置为活跃页面
async function setCurrentPageAsActive() {
    try {
        const tabId = await getCurrentTabId();
        if (!tabId) {
            console.error('无法获取当前标签页ID');
            return false;
        }
        
        // 获取当前标签页信息
        return new Promise((resolve, reject) => {
            chrome.tabs.get(tabId, function(tab) {
                if (chrome.runtime.lastError) {
                    console.error('获取标签页信息失败:', chrome.runtime.lastError);
                    resolve(false);
                    return;
                }
                
                const url = tab.url;
                const title = tab.title;
                console.log('正在获取页面源码以设置活跃页面，URL:', url, '标题:', title);
                
                // 向内容脚本发送获取源码请求
                chrome.tabs.sendMessage(tabId, {
                    type: "get_page_source",
                    request_id: "set_active_page"
                }, function(response) {
                    if (chrome.runtime.lastError) {
                        console.error('向内容脚本发送请求失败:', chrome.runtime.lastError);
                        resolve(false);
                        return;
                    }
                    
                    console.log('收到内容脚本的响应:', response);
                    
                    if (response && response.source_code) {
                        // 发送设置活跃页面的消息到本地应用
                        if (port === null) {
                            console.error('无法设置活跃页面：未连接到本地应用');
                            resolve(false);
                            return;
                        }
                        
                        console.log(`发送设置活跃页面请求，URL: ${url}, 标题: ${title}, 源码长度: ${response.source_code.length}`);
                        port.postMessage({
                            type: "set_active_page",
                            url: url,
                            title: title,
                            html_content: response.source_code
                        });
                        resolve(true);
                    } else {
                        console.error('内容脚本未返回源码');
                        resolve(false);
                    }
                });
            });
        });
    } catch (error) {
        console.error('设置当前页面为活跃页面时出错:', error);
        return false;
    }
}

// 修改连接到本地应用后的初始化流程，自动设置当前页面为活跃页面
function connectToNativeHost(msg) {
    if (port !== null) {
        try {
            port.postMessage(msg);
            console.log('已存在连接，直接发送消息');
            // 如果是初始化消息，尝试设置当前页面为活跃页面
            if (msg.action === "init") {
                setTimeout(() => {
                    setCurrentPageAsActive().then(success => {
                        console.log('自动设置当前页面为活跃页面:', success ? '成功' : '失败');
                        
                        // 获取当前标签页，发送通知
                        getCurrentTabId().then(tabId => {
                            if (tabId) {
                                chrome.tabs.sendMessage(tabId, { 
                                    type: "plugin_activated",
                                    message: "插件已连接到本地服务" + (success ? "，当前页面已设置为活跃页面" : "")
                                }, function(response) {
                                    if (chrome.runtime.lastError) {
                                        console.warn('通知content script失败:', chrome.runtime.lastError.message);
                                    }
                                });
                            }
                        });
                    });
                }, 1000); // 延迟1秒，确保连接已经建立
            }
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
        
        // 如果是初始化消息，尝试设置当前页面为活跃页面
        if (msg.action === "init") {
            setTimeout(() => {
                setCurrentPageAsActive().then(success => {
                    console.log('自动设置当前页面为活跃页面:', success ? '成功' : '失败');
                    
                    // 获取当前标签页，发送通知
                    getCurrentTabId().then(tabId => {
                        if (tabId) {
                            chrome.tabs.sendMessage(tabId, { 
                                type: "plugin_activated",
                                message: "插件已连接到本地服务" + (success ? "，当前页面已设置为活跃页面" : "")
                            }, function(response) {
                                if (chrome.runtime.lastError) {
                                    console.warn('通知content script失败:', chrome.runtime.lastError.message);
                                }
                            });
                        }
                    });
                });
            }, 1000); // 延迟1秒，确保连接已经建立
        }
    } catch (error) {
        console.error('连接本地应用时出错:', error);
        port = null;
    }
}

// 处理获取页面源码请求
async function handleGetPageSource(requestId) {
    try {
        const tabId = await getCurrentTabId();
        if (!tabId) {
            console.error('无法获取当前标签页ID');
            sendPageSourceError(requestId, '无法获取当前标签页');
            return;
        }
        
        // 获取当前标签页信息
        chrome.tabs.get(tabId, function(tab) {
            if (chrome.runtime.lastError) {
                console.error('获取标签页信息失败:', chrome.runtime.lastError);
                sendPageSourceError(requestId, '获取标签页信息失败');
                return;
            }
            
            const url = tab.url;
            console.log('正在获取页面源码，URL:', url);
            
            // 向内容脚本发送获取源码请求
            chrome.tabs.sendMessage(tabId, {
                type: "get_page_source",
                request_id: requestId
            }, function(response) {
                if (chrome.runtime.lastError) {
                    console.error('向内容脚本发送请求失败:', chrome.runtime.lastError);
                    sendPageSourceError(requestId, '向内容脚本发送请求失败');
                    return;
                }
                
                console.log('收到内容脚本的响应:', response);
                
                if (response && response.source_code) {
                    // 发送源码回本地应用
                    sendPageSourceResponse(requestId, url, response.source_code);
                } else {
                    sendPageSourceError(requestId, '内容脚本未返回源码');
                }
            });
        });
    } catch (error) {
        console.error('处理获取页面源码请求时出错:', error);
        sendPageSourceError(requestId, error.message);
    }
}

// 发送页面源码响应到本地应用
function sendPageSourceResponse(requestId, url, sourceCode) {
    if (port === null) {
        console.error('无法发送页面源码响应：未连接到本地应用');
        return;
    }
    
    console.log(`发送页面源码响应，ID: ${requestId}, URL: ${url}, 源码长度: ${sourceCode.length}`);
    
    port.postMessage({
        type: "page_source_response",
        request_id: requestId,
        url: url,
        source_code: sourceCode
    });
}

// 发送页面源码错误响应
function sendPageSourceError(requestId, errorMessage) {
    if (port === null) {
        console.error('无法发送页面源码错误响应：未连接到本地应用');
        return;
    }
    
    console.log(`发送页面源码错误响应，ID: ${requestId}, 错误: ${errorMessage}`);
    
    port.postMessage({
        type: "page_source_response",
        request_id: requestId,
        url: "unknown",
        error: errorMessage,
        source_code: `<html><body><h1>Error: ${errorMessage}</h1></body></html>`
    });
}