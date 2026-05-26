const API_AI_CHAT = "http://127.0.0.1:8000/ai/chat";


//////////////////////////////////  点击按钮发送
// 全局锁：防止重复发送
let isSending = false;
let chatData = [];

async function sendMessage() {
    // 🔥 锁已经打开 → 直接拒绝！绝对不会执行第二次
    if (isSending) {
        return;
    }
    const input = document.getElementById("userInput");
    const content = input.value.trim();
    const chatSession = document.getElementById('chatSession');
    const sideBar = document.getElementById('sideBar');
    const sendMessage = document.getElementById("sendMessage");
    if (!content) {
        return;
    }
    // TODO:ai分析标题结构
    if (!chatSession.textContent.trim()) {
        chatSession.textContent = content;
        // TODO:数据库存储第一条系统索引数据
        // chatData.push({'message': content, 'role': 'system'});
        let div = document.createElement("div");
        div.textContent = content;
        div.title = Date();
        div.className = `history title`;
        // 对历史会话操作：拉取数据库对话数据到对话框
        div.addEventListener('click', function () {
            alert('你点击拉我')
        });
        sideBar.appendChild(div);
    }

    // 显示用户消息
    addMessage(content, "user");

    input.value = "";
    sendMessage.disable = true;
    isSending = true;
    sendMessage.textContent = "发送中⏹️";
    try {
        // 调用AI接口
        // params = {
        //     "message": content,
        // };
        // const queryString = new URLSearchParams(params).toString();
        const response = await fetch(API_AI_CHAT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                "history": chatData,
                "newMessage": content,
            })
        });

        const data = await response.json();
        const aiReply = data.content;
        chatData = data['new_history'];
        addMessage(aiReply, "ai");

    } catch (err) {
        addMessage("AI出错了，请检查API Key", "ai");
        console.error(err);

    } finally {
        isSending = false;
        sendMessage.disable = false;
        sendMessage.textContent = "发送🪄";
    }
}

// 添加消息到界面
function addMessage(text, sender) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = `message ${sender}`;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight; // 自动滚动到底部
}

// 回车发送
document.getElementById("userInput").addEventListener("keypress", e => {
    if (e.key === "Enter") {
        sendMessage();
    }
});

///////////////////////////////// 折叠和添加会话按钮
function foldHistorySession() {
    const sideBar = document.getElementById('sideBar');

    sideBar.hidden = !sideBar.hidden;
}

function createNewSession() {
    const chatSession = document.getElementById('chatSession');
    // 清除所有 class="message" 的子元素 并清空缓存
    document.querySelectorAll("#chatBox .message").forEach(el => el.remove());
    chatData = [];
    chatSession.textContent = null;
}

/////////////////////////////////////