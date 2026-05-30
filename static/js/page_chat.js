const API_AI_CHAT = `${config.API_BASE_URL}/ai/chat`;
const API_AI_CHAT_savaToDb = `${config.API_BASE_URL}/ai/chat/savaToDb`;
const API_AI_CHAT_history = `${config.API_BASE_URL}/ai/chat/history`;
// 点击按钮发送
// 全局锁：防止重复发送
let isSending = false;
let chatData = [];
let div;

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

    // 显示用户消息
    addMessage(content, "user");

    input.value = "";
    sendMessage.disabled = true;
    isSending = true;
    sendMessage.textContent = "发送中⏹️";
    try {
        // 调用AI接口
        // params = {
        //     "message": content,
        // };
        // const queryString = new URLSearchParams(params).toString();
        const response = await fetch(`${API_AI_CHAT}`, {
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

        if (chatSession.textContent.trim() === "新对话") {

            div = document.createElement("div");
            div.title = String(new Date().getTime());
            window.localStorage.setItem('thisSessionTime',div.title);
            // 改为ai分析第一句话的标题，指定提示词
            let aiGenerateContent = await generateTitleFromTwoRounds(chatData || []);

            chatSession.textContent = aiGenerateContent;
            div.className = `history title active`;
            div.textContent = aiGenerateContent;
            // 对历史会话操作：拉取数据库对话数据到对话框 && 清除class active 并激活点击历史对话
            div.addEventListener('click', async function () {
                // 清空当前右边聊天记录,清空chatSession,调取数据库存入全部聊天记录，chatDate取全部聊天记录
                document.getElementById("chatBox").querySelectorAll(".message").forEach(el => el.remove());
                const histories = document.querySelectorAll('.history');
                histories.forEach(h => {
                    h.classList.remove('active')
                });
                this.classList.add('active');
                const session_time = this.title;
                window.localStorage.setItem('thisSessionTime',this.title);
                const messageList = window.localStorage.getItem(session_time) || [];
                chatData = messageList;
                chatSession.textContent = this.textContent;

                renderHistoryChat(chatData);
            });
            if (chatSession.textContent.trim() !== "新对话") {
                sideBar.insertBefore(div, sideBar.children[1]);
            }
        }

    } catch (err) {
        addMessage("AI出错了，请检查API Key", "ai");
        console.error(err);

    } finally {
        isSending = false;
        sendMessage.disabled = false;
        sendMessage.textContent = "发送🪄";
        if (chatSession.textContent.trim() !== "新对话") {
            await postToDb(chatData, window.localStorage.getItem('thisSessionTime'), chatSession.textContent);
        }
    }
}

// 根据前两轮对话生成 8～12 字标题
async function generateTitleFromTwoRounds(dialogue) {

    // AI 生成标题
    const res = await fetch(`${API_AI_CHAT}?temperature=1.5`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            "history": dialogue,
            "newMessage": `
                    请根据以上2轮对话，生成一个8-12字的对话标题。
                    要求：简洁概括、无标点、不换行。
                    只返回标题，不要任何多余内容。
                    `.trim()
        })
    });
    if (res.status === 200) {
        let resJson = await res.json();
        return resJson.content;
    } else {
        return '新对话'
    }

}


// 渲染历史记录（切换会话时用）
function renderHistoryChat(messages) {
    const box = document.getElementById("chatBox");

    messages.forEach(msg => {

        const sender = msg.role === "user" ? "user" : "ai";
        const div = document.createElement("div");
        div.className = `message ${sender}`;
        div.textContent = msg.message;
        box.appendChild(div);
    });

    // box.scrollTop = box.scrollHeight;
}


// 发送聊天数据到数据库
async function postToDb(chatData, createTime, sessionName) {
    try {
        const token = localStorage.getItem("token");
        const res = await fetch(API_AI_CHAT_savaToDb, {
            method: "POST",
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                chat_data: chatData,
                create_time: createTime,
                session_name: sessionName,
            }),
        });
        if (res.status === 401) {
            window.localStorage.setItem('token', null);
            document.getElementById('openLoginBtn').textContent = '未登录';
            console.log('登录信息已过期❗❗❗');
            return null;
        }
        const result = await res.json();

        console.log("✅ 保存数据成功：", result);
        return result;
    } catch (err) {
        console.error("❌ 保存数据请求失败：", err);
        return null;
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

// 折叠和添加会话按钮
function foldHistorySession() {
    const sideBar = document.getElementById('sideBar');

    sideBar.hidden = !sideBar.hidden;
}

function createNewSession() {
    const chatSession = document.getElementById('chatSession');
    // 清除所有 class="message" 的子元素 并清空缓存
    document.querySelectorAll("#chatBox .message").forEach(el => el.remove());
    chatData = [];
    div = null;
    chatSession.textContent = '新对话';
    const histories = document.querySelectorAll('.history');
    histories.forEach(h => {
        h.classList.remove('active')
    });

}

