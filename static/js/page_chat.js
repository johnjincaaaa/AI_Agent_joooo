/* global marked */
const API_AI_CHAT = `${config.API_BASE_URL}/ai/chat`;
const API_AI_CHAT_savaToDb = `${config.API_BASE_URL}/ai/chat/savaToDb`;
const API_AI_CHAT_history = `${config.API_BASE_URL}/ai/chat/history`;
const API_AI_CHAT_STREAM = `${config.API_BASE_URL}/ai/chatStream`; // 流式接口

function buildAuthHeaders() {
    const headers = {"Content-Type": "application/json"};
    const token = localStorage.getItem("token");
    if (token && token !== "null") {
        headers["Authorization"] = "Bearer " + token;
    }
    return headers;
}

function parseApiErrorMessage(data, fallback) {
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (data.detail?.msg) return data.detail.msg;
    if (data.msg) return data.msg;
    return fallback;
}

// 点击按钮发送
// 全局锁：防止重复发送
let isSending = false;
let chatData = [];
let div;
// 流式控制：用于中止请求
let abortController = null;


async function sendMessage() {
    const input = document.getElementById("userInput");
    const content = input.value.trim();
    const chatSession = document.getElementById('chatSession');
    const sideBar = document.getElementById('sideBar');
    const sendMessage_ele = document.getElementById("sendMessage");
    // ==============================================
    // 🔥 核心修复1：先判断【停止】，再判断【发送】
    // ==============================================
    if (isSending && abortController) {
        console.log("🛑 手动停止AI输出");
        abortController.abort();
        isSending = false;
        sendMessage_ele.textContent = "➤";
        return;
    }


    // 🔥 锁已经打开 → 直接拒绝！绝对不会执行第二次
    if (isSending) {
        return;
    }
    if (!content) {
        return;
    }

    // 显示用户消息
    addMessage(content, "user");

    input.value = "";
    isSending = true;
    sendMessage_ele.textContent = "⏹️";
    // 创建AI消息占位框（流式实时更新）
    const box = document.getElementById("chatBox");


    const currentAiMessageDiv = document.createElement("div");
    currentAiMessageDiv.className = "message ai";
    box.appendChild(currentAiMessageDiv);
    let aiFullReply = "";


    try {
        abortController = new AbortController();
        const isOnline = document.getElementById('searchBtn').classList.contains('active');
        const signal = abortController.signal;
        // 🔥 核心：调用流式接口
        const response = await fetch(API_AI_CHAT_STREAM + "?temperature=0.7", {
            method: "POST",
            headers: buildAuthHeaders(),
            body: JSON.stringify({
                history: chatData,
                newMessage: content,
                open_online: isOnline
            }),
            signal: signal
        });

        if (response.status === 429) {
            currentAiMessageDiv.remove();
            const errData = await response.json();
            addMessage(parseApiErrorMessage(errData, "未登录用户免费体验次数已用完，请注册或登录后继续使用"), "ai");
            showLoginExpiredModal("🔐 免费体验次数已用完，请注册或登录！", "error");
            return;
        }
        if (!response.ok) {
            currentAiMessageDiv.remove();
            addMessage("AI出错了，请检查API Key", "ai");
            return;
        }

        const decoder = new TextDecoder("utf-8");
        const reader = response.body.getReader();
        let buffer = "";

        signal.addEventListener("abort", () => {
            reader.cancel();
        });

        while (true) {


            const {done, value} = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, {stream: true});
            const lines = buffer.split("\n");
            // 专门解决网络传输中数据分包 / 不完整行的问题，没有它会导致消息解析错乱、内容丢失或格式错误。
            buffer = lines.pop() || "";

            for (const line of lines) {
                const trimLine = line.trim();
                if (!trimLine.startsWith("data: ")) continue;
                const data = trimLine.replace("data: ", "").trim();

                // 结束
                if (data === "[DONE]") continue;
                // 接收完整历史
                if (data.startsWith("[HISTORY]")) {
                    const historyJson = data.replace("[HISTORY] ", "");
                    chatData = JSON.parse(historyJson);
                    continue;
                }
                // 流式输出文字
                aiFullReply += data;
                marked.setOptions({breaks: true, gfm: true});
                currentAiMessageDiv.innerHTML = marked.parse(aiFullReply);
                box.scrollTop = box.scrollHeight;
            }
        }

        if (chatSession.textContent.trim() === "新对话") {

            div = document.createElement("div");
            div.title = String(new Date().getTime());
            window.localStorage.setItem('thisSessionTime', div.title);
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
                window.localStorage.setItem('thisSessionTime', this.title);
                const messageList = JSON.parse(window.localStorage.getItem(session_time) || '[]');
                chatData = messageList;
                chatSession.textContent = this.textContent;

                renderHistoryChat(chatData);
            });
            if (chatSession.textContent.trim() !== "新对话") {
                sideBar.insertBefore(div, sideBar.children[1]);
            }
        }

        // try {
        //     // 调用AI接口
        //     // params = {
        //     //     "message": content,
        //     // };
        //     // const queryString = new URLSearchParams(params).toString();
        //
        //     // 判断是否联网
        //     const isOnline = document.getElementById('searchBtn').classList.contains('active');
        //     const response = await fetch(`${API_AI_CHAT}`, {
        //         method: "POST",
        //         headers: {
        //             "Content-Type": "application/json"
        //         },
        //
        //         body: JSON.stringify({
        //             "history": chatData,
        //             "newMessage": content,
        //             "open_online": isOnline
        //
        //         })
        //     });
        //
        //     const data = await response.json();
        //     const aiReply = data.content;
        //     chatData = data['new_history'];
        //     addMessage(aiReply, "ai");
        //
        //
        //     if (chatSession.textContent.trim() === "新对话") {
        //
        //         div = document.createElement("div");
        //         div.title = String(new Date().getTime());
        //         window.localStorage.setItem('thisSessionTime', div.title);
        //         // 改为ai分析第一句话的标题，指定提示词
        //         let aiGenerateContent = await generateTitleFromTwoRounds(chatData || []);
        //
        //         chatSession.textContent = aiGenerateContent;
        //         div.className = `history title active`;
        //         div.textContent = aiGenerateContent;
        //         // 对历史会话操作：拉取数据库对话数据到对话框 && 清除class active 并激活点击历史对话
        //         div.addEventListener('click', async function () {
        //             // 清空当前右边聊天记录,清空chatSession,调取数据库存入全部聊天记录，chatDate取全部聊天记录
        //             document.getElementById("chatBox").querySelectorAll(".message").forEach(el => el.remove());
        //             const histories = document.querySelectorAll('.history');
        //             histories.forEach(h => {
        //                 h.classList.remove('active')
        //             });
        //             this.classList.add('active');
        //             const session_time = this.title;
        //             window.localStorage.setItem('thisSessionTime', this.title);
        //             const messageList = JSON.parse(window.localStorage.getItem(session_time) || []);
        //             chatData = messageList;
        //             chatSession.textContent = this.textContent;
        //
        //             renderHistoryChat(chatData);
        //         });
        //         if (chatSession.textContent.trim() !== "新对话") {
        //             sideBar.insertBefore(div, sideBar.children[1]);
        //         }
        //     }

    } catch (err) {
        // ==============================================
        // 🔥 修复：用户主动停止，不报错
        // ==============================================
        if (err.name === "AbortError") {
            console.log("✅ 手动停止输出");
            return;
        }
        addMessage("AI出错了，请检查API Key", "ai");
        console.error(err);

    } finally {
        if (chatData.at(-1)?.role === "ai" && currentAiMessageDiv.isConnected) {
            currentAiMessageDiv.innerHTML = marked.parse(chatData.at(-1).message);
        } else if (currentAiMessageDiv.isConnected && !currentAiMessageDiv.textContent.trim()) {
            currentAiMessageDiv.remove();
        }
        isSending = false;
        sendMessage_ele.disabled = false;
        sendMessage_ele.textContent = "➤";
        if (chatSession.textContent.trim() !== "新对话") {
            window.localStorage.setItem(window.localStorage.getItem('thisSessionTime'), JSON.stringify(chatData));
            await postToDb(chatData, window.localStorage.getItem('thisSessionTime'), chatSession.textContent);
        }
    }
}

// 根据前两轮对话生成 8～12 字标题
async function generateTitleFromTwoRounds(dialogue) {

    // AI 生成标题
    const res = await fetch(`${API_AI_CHAT}?temperature=1.5`, {
        method: "POST",
        headers: buildAuthHeaders(),
        body: JSON.stringify({
            "history": dialogue,
            "newMessage": `
                    请根据以上2轮对话，生成一个8-12字的对话标题。
                    要求：简洁概括、无标点、不换行。
                    只返回标题，不要任何多余内容。
                    `.trim()
        })
    });
    if (res.status === 429) {
        return '新对话';
    }
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
        // div.textContent = msg.message;
        marked.setOptions({breaks: true, gfm: true}); // 换行生效、支持表格列表
        div.innerHTML = marked.parse(msg.message);
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
            showLoginExpiredModal('🔐 登录已过期，请重新登录！', 'error');
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
    // div.textContent = text;
    marked.setOptions({breaks: true, gfm: true}); // 换行生效、支持表格列表
    div.innerHTML = marked.parse(text);
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
    const userprofile = document.getElementById('userProfile');
    // 切换侧边栏（假设 sideBar 是侧边栏元素，需确保已正确获取）
    sideBar.classList.toggle('hidden');
    // 切换用户信息栏
    userprofile.classList.toggle('hidden');
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

