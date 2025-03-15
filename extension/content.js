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
    const message = document.querySelector('.message');
    const newH3 = document.createElement('h3');
    newH3.innerHTML = request;
    message.appendChild(newH3);
    return true;
});