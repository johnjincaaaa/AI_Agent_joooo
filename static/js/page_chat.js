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

function renderMarkdown(text) {
    marked.setOptions({ breaks: true, gfm: true });
    const html = marked.parse(text);
    return html.replace(/<a /g, '<a target="_blank" rel="noopener noreferrer" ');
}

window.renderMarkdown = renderMarkdown;

// 点击按钮发送
// 全局锁：防止重复发送
let isSending = false;
let chatData = [];
let div;
// 流式控制：用于中止请求
let abortController = null;

// ==================== 免费体验次数（未登录用户）====================
const API_AI_QUOTA = `${config.API_BASE_URL}/ai/quota`;
// null 表示已登录/未知（不限流）；数字表示今日剩余次数
let anonRemaining = null;

function isLoggedIn() {
    const token = localStorage.getItem("token");
    return !!(token && token !== "null");
}

// 刷新底部「今日还剩 N 次」提示
function renderQuotaTip() {
    const tip = document.getElementById("quotaTip");
    if (!tip) return;
    if (isLoggedIn() || anonRemaining === null) {
        tip.hidden = true;
        return;
    }
    tip.hidden = false;
    if (anonRemaining <= 0) {
        tip.textContent = t('rate_limit_msg');
        tip.classList.add('quota-tip-warn');
    } else {
        tip.textContent = t('quota_remaining_1') + anonRemaining + t('quota_remaining_2');
        tip.classList.toggle('quota-tip-warn', anonRemaining <= 3);
    }
}

// 弹出「注册成为会员 + 在线客服」引导弹窗
function showRegisterPrompt() {
    if (typeof showLoginExpiredModal === 'function') {
        showLoginExpiredModal(t('rate_limit_modal'), 'error', {
            goRegister: true,
            showService: true,
            subtitle: t('rate_limit_sub'),
        });
    }
}

// 页面加载时拉取一次剩余次数（仅未登录用户展示）
async function initQuota() {
    if (isLoggedIn()) {
        anonRemaining = null;
        renderQuotaTip();
        return;
    }
    try {
        const res = await fetch(API_AI_QUOTA, {headers: buildAuthHeaders()});
        if (res.ok) {
            const data = await res.json();
            anonRemaining = data.logged_in ? null : data.remaining;
        }
    } catch (e) {
        console.warn("获取免费次数失败", e);
    }
    renderQuotaTip();
}

document.addEventListener('DOMContentLoaded', initQuota);
document.addEventListener('langchange', renderQuotaTip);


// ==================== 推广文案（横幅 + 输入框）====================
const API_PROMO_CONFIG = `${config.API_BASE_URL}/ai/promo/config`;
// 后台配置：{promo_enabled, input_promo_enabled, banner_promo:{zh,en}, input_promo:{zh,en}}
let promoConfig = null;

// 当前输入框里的文案是否是"自动填充的推广文案"（用于判断是否该在用户操作时清空）
function getInputPromoText() {
    if (!promoConfig || !promoConfig.input_promo) return '';
    const lang = typeof getLang === 'function' ? getLang() : 'zh';
    return promoConfig.input_promo[lang] || promoConfig.input_promo.zh || '';
}

function getBannerText() {
    if (!promoConfig || !promoConfig.banner_promo) return '';
    const lang = typeof getLang === 'function' ? getLang() : 'zh';
    return promoConfig.banner_promo[lang] || promoConfig.banner_promo.zh || '';
}

// 渲染空状态推广横幅
function renderPromoBanner() {
    const banner = document.getElementById('promoBanner');
    if (!banner) return;
    const text = getBannerText();
    if (promoConfig && promoConfig.promo_enabled && text) {
        banner.textContent = text;
        banner.hidden = false;
    } else {
        banner.hidden = true;
    }
}

// 若输入框为空且开关开启，则填入推广文案并打标记
function fillInputPromoIfEmpty() {
    const input = document.getElementById('userInput');
    if (!input) return;
    if (!promoConfig || !promoConfig.input_promo_enabled) return;
    const text = getInputPromoText();
    if (!text) return;
    // 仅在输入框为空、或当前内容正是上一次填充的推广文案时才填
    if (input.value.trim() === '' || input.dataset.promoFilled === '1') {
        input.value = text;
        input.dataset.promoFilled = '1';
        input.dispatchEvent(new Event('input'));
    }
}

// 用户开始真正输入时，清掉自动填充的推广文案
function clearInputPromoOnUserAction() {
    const input = document.getElementById('userInput');
    if (!input) return;
    if (input.dataset.promoFilled === '1') {
        input.value = '';
        delete input.dataset.promoFilled;
        input.dispatchEvent(new Event('input'));
    }
}

// 发送前判断：当前内容是否只是未清除的推广文案（视为空，不发给AI）
function inputIsOnlyPromo(content) {
    const input = document.getElementById('userInput');
    return input && input.dataset.promoFilled === '1' && content === getInputPromoText().trim();
}

async function initPromo() {
    try {
        const res = await fetch(API_PROMO_CONFIG);
        if (res.ok) {
            promoConfig = await res.json();
        }
    } catch (e) {
        console.warn('获取推广配置失败', e);
    }
    renderPromoBanner();
    fillInputPromoIfEmpty();

    const input = document.getElementById('userInput');
    if (input) {
        // 用户聚焦或按键即清除推广占位文案（focus 用一次性，避免每次聚焦都清）
        input.addEventListener('focus', clearInputPromoOnUserAction, {once: false});
        input.addEventListener('beforeinput', clearInputPromoOnUserAction);
    }
}

document.addEventListener('DOMContentLoaded', initPromo);
document.addEventListener('langchange', () => {
    renderPromoBanner();
    // 语言切换时，如果输入框仍是自动填充的推广文案，则切换成新语言版本
    const input = document.getElementById('userInput');
    if (input && input.dataset.promoFilled === '1') {
        input.value = getInputPromoText();
        input.dispatchEvent(new Event('input'));
    }
});

// 供 createNewSession 调用：新建会话后重新填充输入框推广文案
window.refillInputPromo = fillInputPromoIfEmpty;


async function sendMessage() {
    const input = document.getElementById("userInput");
    let content = input.value.trim();
    // 若内容只是未清除的推广占位文案，视为未输入
    if (typeof inputIsOnlyPromo === 'function' && inputIsOnlyPromo(content)) {
        content = '';
    }
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

    const hasAttachments = typeof hasPendingAttachments === 'function' && hasPendingAttachments();
    if (!content && !hasAttachments) {
        return;
    }

    // 未登录且今日免费次数已用完：禁止发送，弹注册/客服引导
    if (!isLoggedIn() && anonRemaining !== null && anonRemaining <= 0) {
        showRegisterPrompt();
        return;
    }

    let displayMessage = content;
    let imagePaths = [];
    let documentPaths = [];

    if (hasAttachments) {
        try {
            const uploaded = await uploadPendingAttachments();
            imagePaths = uploaded.imagePaths;
            documentPaths = uploaded.documentPaths;
            displayMessage = buildDisplayMessage(content, uploaded.imageUrls, uploaded.documentNames);
            clearPendingAttachments();
        } catch (uploadErr) {
            if (uploadErr.message === 'RATE_LIMIT') {
                addMessage(t('rate_limit_msg'), "ai");
                anonRemaining = 0;
                renderQuotaTip();
                showRegisterPrompt();
            } else {
                addMessage(uploadErr.message || t('upload_fail'), "ai");
            }
            return;
        }
    }

    // 显示用户消息
    addMessage(displayMessage, "user");

    input.value = "";
    input.dispatchEvent(new Event('input'));
    isSending = true;
    sendMessage_ele.textContent = "⏹️";
    // 创建AI消息占位框（流式实时更新）
    const box = document.getElementById("chatBox");


    const currentAiMessageDiv = document.createElement("div");
    currentAiMessageDiv.className = "message ai";
    // 删除按钮
    const aiDelBtn = document.createElement("button");
    aiDelBtn.className = "msg-delete-btn";
    aiDelBtn.innerHTML = "×";
    aiDelBtn.title = t('chat_delete');
    aiDelBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteSingleMessage(currentAiMessageDiv, chatData.length - 1);
    });
    currentAiMessageDiv.appendChild(aiDelBtn);
    // AI 消息内容 div
    const aiContentDiv = document.createElement("div");
    aiContentDiv.className = "msg-content";
    currentAiMessageDiv.appendChild(aiContentDiv);
    box.appendChild(currentAiMessageDiv);
    // 打字指示器
    const typingDiv = document.createElement("div");
    typingDiv.className = "typing-indicator";
    typingDiv.innerHTML = `<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-text" data-i18n="typing_indicator">${t('typing_indicator')}</span>`;
    aiContentDiv.appendChild(typingDiv);
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
                newMessage: displayMessage,
                open_online: isOnline,
                enabled_skills: typeof getEnabledSkills === 'function' ? getEnabledSkills() : [],
                image_paths: imagePaths,
                document_paths: documentPaths,
                lang: typeof getLang === 'function' ? getLang() : 'zh',
                scene: currentScene
            }),
            signal: signal
        });

        if (response.status === 429) {
            currentAiMessageDiv.remove();
            const errData = await response.json();
            addMessage(parseApiErrorMessage(errData, t('rate_limit_msg')), "ai");
            anonRemaining = 0;
            renderQuotaTip();
            showRegisterPrompt();
            return;
        }
        if (!response.ok) {
            currentAiMessageDiv.remove();
            addMessage(t('ai_error_key'), "ai");
            return;
        }

        // 未登录用户：从响应头同步今日剩余次数
        if (!isLoggedIn()) {
            const remainHeader = response.headers.get("X-Anon-Remaining");
            if (remainHeader !== null) {
                anonRemaining = parseInt(remainHeader, 10);
                renderQuotaTip();
            }
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
                if (typingDiv && typingDiv.parentNode) {
                    typingDiv.remove();
                }
                aiContentDiv.innerHTML = renderMarkdown(aiFullReply);
                box.scrollTop = box.scrollHeight;
                enhanceCodeBlocks(aiContentDiv);
            }
        }

        if (chatSession.textContent.trim() === t('new_session')) {

            div = document.createElement("div");
            div.title = String(new Date().getTime());
            window.localStorage.setItem('thisSessionTime', div.title);
            // 改为ai分析第一句话的标题，指定提示词
            let aiGenerateContent = await generateTitleFromTwoRounds(chatData || []);

            chatSession.textContent = aiGenerateContent;
            div.className = `history title active`;

            // 会话名称 + 操作按钮
            const nameSpan = document.createElement("span");
            nameSpan.className = "history-name";
            nameSpan.textContent = aiGenerateContent;
            div.appendChild(nameSpan);

            const moreBtn = document.createElement("button");
            moreBtn.className = "history-more-btn";
            moreBtn.innerHTML = "···";
            moreBtn.title = t('chat_rename') + " / " + t('chat_delete');
            moreBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                showHistoryMenu(div, div.title, aiGenerateContent, moreBtn);
            });
            div.appendChild(moreBtn);

            // 对历史会话操作：拉取数据库对话数据到对话框 && 清除class active 并激活点击历史对话
            nameSpan.addEventListener('click', async function () {
                if (typeof exitJobHuntMode === 'function') exitJobHuntMode();
                if (typeof exitWalletMode === 'function') exitWalletMode();
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
                document.getElementById('emptyState')?.classList.toggle('hidden', chatData.length > 0);
            });
            if (chatSession.textContent.trim() !== t('new_session')) {
                const firstHistoryItem = sideBar.querySelector('.history.title');
                if (firstHistoryItem) {
                    sideBar.insertBefore(div, firstHistoryItem);
                } else {
                    sideBar.appendChild(div);
                }
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
        addMessage(t('ai_error_key'), "ai");
        console.error(err);

    } finally {
        if (chatData.at(-1)?.role === "ai" && currentAiMessageDiv.isConnected) {
            aiContentDiv.innerHTML = renderMarkdown(chatData.at(-1).message);
        } else if (currentAiMessageDiv.isConnected && !aiContentDiv.textContent.trim()) {
            currentAiMessageDiv.remove();
        }
        isSending = false;
        sendMessage_ele.disabled = false;
        sendMessage_ele.textContent = "➤";
        if (chatSession.textContent.trim() !== t('new_session')) {
            window.localStorage.setItem(window.localStorage.getItem('thisSessionTime'), JSON.stringify(chatData));
            await postToDb(chatData, window.localStorage.getItem('thisSessionTime'), chatSession.textContent);
        }
    }
}

// 根据前两轮对话生成 8～12 字标题
async function generateTitleFromTwoRounds(dialogue) {
    // 未登录用户不保存历史，且标题生成会额外消耗免费次数，这里直接跳过
    if (!isLoggedIn()) {
        return t('new_session');
    }

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
        return t('new_session');
    }
    if (res.status === 200) {
        let resJson = await res.json();
        return resJson.content;
    } else {
        return t('new_session')
    }

}


// 渲染历史记录（切换会话时用）
function renderHistoryChat(messages) {
    const box = document.getElementById("chatBox");

    messages.forEach((msg, i) => {
        const sender = msg.role === "user" ? "user" : "ai";
        addMessage(msg.message, sender, i);
    });
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


// 为消息中的代码块添加复制按钮 + 折叠展开 + 语言标签
function enhanceCodeBlocks(container) {
    if (!container) return;
    const FOLD_THRESHOLD_LINES = 20;
    const FOLD_THRESHOLD_HEIGHT = 400;

    container.querySelectorAll('pre').forEach(pre => {
        if (pre.querySelector('.code-toolbar')) return;
        const code = pre.querySelector('code');
        if (!code) return;

        // 强制内联样式，确保不被 CSS 覆盖
        pre.style.position = 'relative';
        pre.style.paddingTop = '44px';
        pre.style.overflow = 'visible';

        // 提取语言
        let lang = '';
        const langMatch = code.className.match(/language-([\w+-]+)/);
        if (langMatch) lang = langMatch[1];

        // 工具栏容器
        const toolbar = document.createElement('div');
        toolbar.className = 'code-toolbar';

        // 语言标签
        if (lang) {
            const langLabel = document.createElement('span');
            langLabel.className = 'code-lang-label';
            langLabel.textContent = lang.toUpperCase();
            toolbar.appendChild(langLabel);
        }

        // 折叠/展开按钮
        const codeText = code.innerText;
        const lineCount = codeText.split('\n').length;
        const showFoldBtn = lineCount > FOLD_THRESHOLD_LINES;

        const foldBtn = document.createElement('button');
        foldBtn.type = 'button';
        foldBtn.className = 'code-fold-btn';
        foldBtn.title = t('expand_code') || '展开/折叠';
        foldBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
        </svg>`;
        foldBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isFolded = pre.classList.contains('code-folded');
            if (isFolded) {
                pre.classList.remove('code-folded');
                pre.dataset.folded = 'false';
                foldBtn.classList.remove('expanded');
            } else {
                pre.classList.add('code-folded');
                pre.dataset.folded = 'true';
                foldBtn.classList.add('expanded');
            }
        });
        if (!showFoldBtn) foldBtn.style.display = 'none';
        toolbar.appendChild(foldBtn);

        // 复制按钮
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'code-copy-btn';
        btn.setAttribute('data-i18n-tip', 'copy_code');
        btn.title = t('copy_code');
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>`;
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            try {
                await navigator.clipboard.writeText(code.innerText);
                btn.classList.add('copied');
                btn.title = t('copied');
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.title = t('copy_code');
                }, 2000);
            } catch (err) {
                console.error('复制失败：', err);
            }
        });
        toolbar.appendChild(btn);

        pre.appendChild(toolbar);
    });
}

// 全局暴露 + 定时扫描兜底（确保所有代码块都被处理）
window.enhanceCodeBlocks = enhanceCodeBlocks;
(function startCodeBlockWatcher() {
    let lastCount = 0;
    function scan() {
        const pres = document.querySelectorAll('#chatBox pre, .msg-content pre');
        if (pres.length !== lastCount) {
            lastCount = pres.length;
            pres.forEach(pre => {
                if (!pre.querySelector('.code-toolbar')) {
                    const code = pre.querySelector('code');
                    if (code) {
                        const container = pre.closest('.msg-content') || document.body;
                        enhanceCodeBlocks(container);
                    }
                }
            });
        }
    }
    setInterval(scan, 1500);
    setTimeout(scan, 500);
})();

// 添加消息到界面
function addMessage(text, sender, index) {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.className = `message ${sender}`;
    if (typeof index === 'number') div.dataset.msgIndex = index;
    // 删除按钮
    const delBtn = document.createElement("button");
    delBtn.className = "msg-delete-btn";
    delBtn.innerHTML = "×";
    delBtn.title = t('chat_delete');
    delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        deleteSingleMessage(div, index);
    });
    div.appendChild(delBtn);
    // 消息内容
    const contentDiv = document.createElement("div");
    contentDiv.className = "msg-content";
    contentDiv.innerHTML = renderMarkdown(text);
    div.appendChild(contentDiv);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight; // 自动滚动到底部
    enhanceCodeBlocks(contentDiv);
}

// 删除单条消息
function deleteSingleMessage(msgEl, index) {
    if (!confirm(t('chat_delete_confirm'))) return;
    if (typeof index === 'number' && chatData[index]) {
        chatData.splice(index, 1);
    }
    msgEl.remove();
    // 重新索引
    document.querySelectorAll('#chatBox .message').forEach((el, i) => {
        el.dataset.msgIndex = i;
    });
    // 保存
    const sessionTime = localStorage.getItem('thisSessionTime');
    if (sessionTime && isLoggedIn()) {
        localStorage.setItem(sessionTime, JSON.stringify(chatData));
        postToDb(chatData, sessionTime, document.getElementById('chatSession').textContent);
    }
    if (!chatData.length) {
        document.getElementById('emptyState')?.classList.remove('hidden');
    }
}

// Enter 发送，Ctrl+Enter / Shift+Enter 换行
const userInput = document.getElementById("userInput");
userInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.isComposing) {
        if (e.ctrlKey || e.shiftKey) {
            // 换行：默认行为就是插入换行，不做特殊处理
        } else {
            e.preventDefault();
            sendMessage();
        }
    }
});

// Esc 关闭所有打开的面板
document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
        // 关闭场景下拉菜单
        closeSceneDropdown();
        // 关闭快捷模板面板
        document.getElementById('quickTemplates')?.classList.add('hidden');
        // 关闭技能下拉菜单
        document.getElementById('skillsDropdown')?.classList.remove('open');
        // 关闭登录弹窗
        const loginModal = document.getElementById('loginModal');
        if (loginModal && loginModal.style.display !== 'none') {
            closeLoginModal();
        }
    }
});

// 折叠和添加会话按钮
function foldHistorySession() {
    const appShell = document.querySelector('.app-shell');
    const backdrop = document.getElementById('sidebarBackdrop');
    // 移动端（<=768px）：侧边栏为覆盖式抽屉，切换抽屉开合 + 遮罩
    if (window.matchMedia('(max-width: 768px)').matches) {
        const open = appShell.classList.toggle('sidebar-open');
        if (backdrop) backdrop.classList.toggle('show', open);
        return;
    }
    // 桌面端：原有折叠逻辑
    const sideBar = document.getElementById('sideBar');
    const userprofile = document.getElementById('userProfile');
    sideBar.classList.toggle('hidden');
    userprofile.classList.toggle('hidden');
}

// 移动端：点击遮罩关闭侧边栏抽屉
document.addEventListener('DOMContentLoaded', () => {
    const backdrop = document.getElementById('sidebarBackdrop');
    const appShell = document.querySelector('.app-shell');
    function closeMobileDrawer() {
        appShell?.classList.remove('sidebar-open');
        backdrop?.classList.remove('show');
    }
    if (backdrop && appShell) {
        backdrop.addEventListener('click', closeMobileDrawer);
    }
    // 移动端点击历史会话/找工作入口后自动收起抽屉
    const sideBar = document.getElementById('sideBar');
    if (sideBar) {
        sideBar.addEventListener('click', (e) => {
            if (!window.matchMedia('(max-width: 768px)').matches) return;
            if (e.target.closest('.history.title') || e.target.closest('#jobHuntEntry')) {
                closeMobileDrawer();
            }
        });
    }
    // 快捷模板面板收起按钮
    document.getElementById('quickTemplatesClose')?.addEventListener('click', () => {
        document.getElementById('quickTemplates')?.classList.add('hidden');
    });
    // 快捷模板搜索
    document.getElementById('quickTemplatesSearch')?.addEventListener('input', (e) => {
        if (!currentPanelTemplates.length || !currentPanelSceneId) return;
        const kw = e.target.value.trim().toLowerCase();
        const filtered = kw ? filterTemplates(currentPanelTemplates, kw) : currentPanelTemplates;
        renderTemplatesContent(filtered, currentPanelSceneId);
    });
});

function createNewSession() {
    if (typeof exitJobHuntMode === 'function') exitJobHuntMode();
    if (typeof exitWalletMode === 'function') exitWalletMode();
    const chatSession = document.getElementById('chatSession');
    // 清除所有 class="message" 的子元素 并清空缓存
    document.querySelectorAll("#chatBox .message").forEach(el => el.remove());
    chatData = [];
    div = null;
    chatSession.textContent = t('new_session');
    document.getElementById('emptyState')?.classList.remove('hidden');
    const histories = document.querySelectorAll('.history');
    histories.forEach(h => {
        h.classList.remove('active')
    });
    if (typeof clearPendingAttachments === 'function') {
        clearPendingAttachments();
    }
    // 新建会话：重置为通用模式
    if (currentScene !== null) {
        currentScene = null;
        updateSceneButton();
    }
    // 新建会话：恢复输入框默认 placeholder（不填推广文案，避免与场景冲突）
    const input = document.getElementById('userInput');
    if (input) {
        input.value = '';
        delete input.dataset.promoFilled;
        delete input.dataset.scenePh;
        input.placeholder = t('input_placeholder');
    }
    // 新建会话：重新展示横幅
    if (typeof renderPromoBanner === 'function') renderPromoBanner();
}

// ==================== 场景模板 ====================
let currentScene = null;  // 当前场景 id，null 表示通用模式
let sceneList = [];

const API_AI_SCENES = `${config.API_BASE_URL}/ai/scenes`;
const API_AI_SCENE_TEMPLATES = (sceneId) => `${config.API_BASE_URL}/ai/scenes/${sceneId}/templates`;

async function initScenes() {
    try {
        const res = await fetch(API_AI_SCENES);
        if (res.ok) {
            const data = await res.json();
            sceneList = data.scenes || [];
            renderSceneGrid();
            updateSceneButton();  // 场景列表加载完后再更新按钮状态
        }
    } catch (e) {
        console.warn('加载场景模板失败', e);
    }
}

function getSceneName(sceneId) {
    const s = sceneList.find(x => x.id === sceneId);
    if (!s) return '';
    const lang = typeof getLang === 'function' ? getLang() : 'zh';
    return lang === 'en' ? s.name_en : s.name_zh;
}

function renderSceneGrid() {
    const grid = document.getElementById('sceneGrid');
    if (!grid || !sceneList.length) return;
    const lang = typeof getLang === 'function' ? getLang() : 'zh';
    grid.innerHTML = sceneList.map(s => `
        <div class="scene-card" data-scene="${s.id}" title="${lang === 'en' ? s.name_en : s.name_zh}">
            <div class="scene-card-icon">${s.icon}</div>
            <div class="scene-card-name">${lang === 'en' ? s.name_en : s.name_zh}</div>
            <div class="scene-card-desc">${t('scene_' + s.id + '_desc')}</div>
        </div>
    `).join('');

    grid.querySelectorAll('.scene-card').forEach(card => {
        card.addEventListener('click', () => {
            const sceneId = card.dataset.scene;
            setScene(sceneId);
        });
    });
}

function setScene(sceneId) {
    currentScene = sceneId;
    updateSceneButton();
    // 更新快捷模板面板
    updateQuickTemplatesPanel(sceneId);
    // 更新输入框 placeholder
    const input = document.getElementById('userInput');
    if (input) {
        if (sceneId) {
            const name = getSceneName(sceneId);
            if (name) {
                input.placeholder = t('scene_current') + name;
                // 用自定义属性标记"场景模式下的 placeholder"，避免 i18n 覆盖
                input.dataset.scenePh = '1';
            }
        } else {
            // 通用模式：清除标记，恢复 i18n 默认 placeholder
            delete input.dataset.scenePh;
            input.placeholder = t('input_placeholder');
        }
        // 如果输入框里只是推广文案，清掉它让 placeholder 显示
        if (input.dataset.promoFilled === '1') {
            input.value = '';
            delete input.dataset.promoFilled;
        }
        input.focus();
    }
}

// ==================== 快捷模板面板 ====================

const templateCache = {};
const TEMPLATE_FAV_KEY = 'template_favorites';
const TEMPLATE_RECENT_KEY = 'template_recent';
const MAX_RECENT = 8;

function getFavorites() {
    try { return JSON.parse(localStorage.getItem(TEMPLATE_FAV_KEY) || '[]'); }
    catch (e) { return []; }
}

function saveFavorites(list) {
    localStorage.setItem(TEMPLATE_FAV_KEY, JSON.stringify(list));
}

function isFavorite(sceneId, templateId) {
    return getFavorites().some(x => x.sceneId === sceneId && x.templateId === templateId);
}

function toggleFavorite(sceneId, templateId) {
    const favs = getFavorites();
    const idx = favs.findIndex(x => x.sceneId === sceneId && x.templateId === templateId);
    if (idx >= 0) {
        favs.splice(idx, 1);
    } else {
        favs.push({ sceneId, templateId, time: Date.now() });
    }
    saveFavorites(favs);
    return idx < 0;
}

function getRecent() {
    try { return JSON.parse(localStorage.getItem(TEMPLATE_RECENT_KEY) || '[]'); }
    catch (e) { return []; }
}

function saveRecent(list) {
    localStorage.setItem(TEMPLATE_RECENT_KEY, JSON.stringify(list.slice(0, MAX_RECENT)));
}

function addRecent(sceneId, templateId) {
    let recent = getRecent().filter(x => !(x.sceneId === sceneId && x.templateId === templateId));
    recent.unshift({ sceneId, templateId, time: Date.now() });
    saveRecent(recent);
}

function getTemplateName(tmpl) {
    const lang = getLang();
    return lang === 'zh' ? tmpl.name_zh : (tmpl.name_en || tmpl.name_zh);
}

function buildTemplateCard(sceneId, tmpl, showFavBtn = true) {
    const fav = isFavorite(sceneId, tmpl.id);
    const favTitle = fav ? t('template_favorite_remove') : t('template_favorite_add');
    const favIcon = fav ? '★' : '☆';
    return `
        <div class="quick-template-card" data-template-id="${tmpl.id}" data-scene-id="${sceneId}">
            ${showFavBtn ? `<button class="quick-template-fav ${fav ? 'active' : ''}" data-action="fav" title="${favTitle}">${favIcon}</button>` : ''}
            <span class="quick-template-icon">${tmpl.icon}</span>
            <span class="quick-template-name">${getTemplateName(tmpl)}</span>
        </div>
    `;
}

function renderSection(title, templates, sceneId) {
    if (!templates || !templates.length) return '';
    return `
        <div class="quick-templates-section">
            <div class="quick-templates-section-title">${title}</div>
            <div class="quick-templates-grid">
                ${templates.map(x => buildTemplateCard(sceneId, x)).join('')}
            </div>
        </div>
    `;
}

let currentPanelSceneId = null;
let currentPanelTemplates = [];

function updateQuickTemplatesPanel(sceneId) {
    const panel = document.getElementById('quickTemplates');
    const titleEl = document.getElementById('quickTemplatesTitle');
    const contentEl = document.getElementById('quickTemplatesContent');
    const searchEl = document.getElementById('quickTemplatesSearch');
    if (!panel || !contentEl) return;

    currentPanelSceneId = sceneId;

    if (!sceneId) {
        panel.classList.add('hidden');
        return;
    }

    const scene = sceneList.find(s => s.id === sceneId);
    if (!scene || !scene.quick_templates || !scene.quick_templates.length) {
        panel.classList.add('hidden');
        return;
    }

    panel.classList.remove('hidden');
    titleEl.textContent = `${scene.icon} ${getSceneName(sceneId)} · 快捷功能`;

    currentPanelTemplates = scene.quick_templates.slice();
    if (searchEl) searchEl.value = '';

    renderTemplatesContent(currentPanelTemplates, sceneId);
}

function renderTemplatesContent(templates, sceneId) {
    const contentEl = document.getElementById('quickTemplatesContent');
    if (!contentEl) return;

    const favIds = getFavorites().filter(x => x.sceneId === sceneId).map(x => x.templateId);
    const recentIds = getRecent().filter(x => x.sceneId === sceneId).map(x => x.templateId);

    const favTemplates = templates.filter(x => favIds.includes(x.id));
    const recentTemplates = templates.filter(x => recentIds.includes(x.id) && !favIds.includes(x.id));
    const otherTemplates = templates.filter(x => !favIds.includes(x.id) && !recentIds.includes(x.id));

    let html = '';
    html += renderSection(t('template_favorite'), favTemplates, sceneId);
    html += renderSection(t('template_recent'), recentTemplates, sceneId);
    if (otherTemplates.length) {
        html += `<div class="quick-templates-section"><div class="quick-templates-grid">${otherTemplates.map(x => buildTemplateCard(sceneId, x)).join('')}</div></div>`;
    }

    if (!templates.length) {
        html = `<div class="quick-templates-empty">${t('template_empty')}</div>`;
    }

    contentEl.innerHTML = html;
    bindTemplateCardEvents(contentEl);
}

function bindTemplateCardEvents(container) {
    container.querySelectorAll('.quick-template-card').forEach(card => {
        const tid = card.dataset.templateId;
        const sid = card.dataset.sceneId;

        card.addEventListener('click', (e) => {
            if (e.target.closest('[data-action="fav"]')) return;
            fillTemplateToInput(sid, tid);
        });

        const favBtn = card.querySelector('[data-action="fav"]');
        if (favBtn) {
            favBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const nowFav = toggleFavorite(sid, tid);
                favBtn.textContent = nowFav ? '★' : '☆';
                favBtn.classList.toggle('active', nowFav);
                favBtn.title = nowFav ? t('template_favorite_remove') : t('template_favorite_add');
                if (currentPanelTemplates && currentPanelSceneId) {
                    const searchEl = document.getElementById('quickTemplatesSearch');
                    const kw = (searchEl?.value || '').trim().toLowerCase();
                    const filtered = kw ? filterTemplates(currentPanelTemplates, kw) : currentPanelTemplates;
                    renderTemplatesContent(filtered, currentPanelSceneId);
                }
            });
        }
    });
}

function filterTemplates(templates, keyword) {
    if (!keyword) return templates;
    const kw = keyword.toLowerCase();
    return templates.filter(x => {
        const nameZh = (x.name_zh || '').toLowerCase();
        const nameEn = (x.name_en || '').toLowerCase();
        return nameZh.includes(kw) || nameEn.includes(kw);
    });
}

async function fillTemplateToInput(sceneId, templateId) {
    const input = document.getElementById('userInput');
    if (!input) return;

    addRecent(sceneId, templateId);
    if (currentPanelSceneId === sceneId && currentPanelTemplates.length) {
        const searchEl = document.getElementById('quickTemplatesSearch');
        const kw = (searchEl?.value || '').trim().toLowerCase();
        const filtered = kw ? filterTemplates(currentPanelTemplates, kw) : currentPanelTemplates;
        renderTemplatesContent(filtered, sceneId);
    }

    input.value = '加载中...';

    try {
        if (!templateCache[sceneId]) {
            const res = await fetch(API_AI_SCENE_TEMPLATES(sceneId), {headers: buildAuthHeaders()});
            if (res.ok) {
                const data = await res.json();
                templateCache[sceneId] = data.templates || [];
            }
        }

        const templates = templateCache[sceneId] || [];
        const t = templates.find(x => x.id === templateId);
        if (t) {
            const lang = getLang();
            input.value = lang === 'zh' ? t.prompt_zh : (t.prompt_en || t.prompt_zh);
        }
    } catch (e) {
        console.warn('加载模板失败', e);
        input.value = '';
    }

    input.focus();
    setTimeout(() => { input.selectionStart = input.selectionEnd = input.value.length; }, 10);
}

function updateSceneButton() {
    const btn = document.getElementById('sceneToggleBtn');
    const icon = document.getElementById('sceneIcon');
    if (!btn) return;
    if (currentScene) {
        const s = sceneList.find(x => x.id === currentScene);
        if (s) {
            icon.textContent = s.icon;
            btn.title = t('scene_current') + getSceneName(currentScene);
            btn.classList.add('active');
            btn.setAttribute('aria-expanded', 'true');
        }
    } else {
        icon.textContent = '✨';
        btn.title = t('scene_general');
        btn.classList.remove('active');
        btn.setAttribute('aria-expanded', 'false');
    }
}

function renderSceneDropdown() {
    const dd = document.getElementById('sceneDropdown');
    if (!dd) return;
    const lang = getLang();
    let html = `
        <div class="scene-dropdown-item ${!currentScene ? 'active' : ''}" data-scene-id="">
            <span class="scene-dd-icon">✨</span>
            <span class="scene-dd-name">${t('scene_general')}</span>
            ${!currentScene ? '<span class="scene-dd-check">✓</span>' : ''}
        </div>
    `;
    html += sceneList.map(s => `
        <div class="scene-dropdown-item ${currentScene === s.id ? 'active' : ''}" data-scene-id="${s.id}">
            <span class="scene-dd-icon">${s.icon}</span>
            <span class="scene-dd-name">${lang === 'en' ? s.name_en : s.name_zh}</span>
            ${currentScene === s.id ? '<span class="scene-dd-check">✓</span>' : ''}
        </div>
    `).join('');
    dd.innerHTML = html;

    dd.querySelectorAll('.scene-dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            const sid = item.dataset.sceneId || null;
            setScene(sid);
            closeSceneDropdown();
        });
    });
}

function openSceneDropdown() {
    const dd = document.getElementById('sceneDropdown');
    const btn = document.getElementById('sceneToggleBtn');
    if (!dd || !btn) return;
    renderSceneDropdown();
    dd.classList.remove('hidden');
    btn.setAttribute('aria-expanded', 'true');
}

function closeSceneDropdown() {
    const dd = document.getElementById('sceneDropdown');
    const btn = document.getElementById('sceneToggleBtn');
    if (!dd) return;
    dd.classList.add('hidden');
    if (btn) btn.setAttribute('aria-expanded', currentScene ? 'true' : 'false');
}

function toggleSceneDropdown(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }
    const dd = document.getElementById('sceneDropdown');
    if (!dd) return;
    if (dd.classList.contains('hidden')) {
        openSceneDropdown();
    } else {
        closeSceneDropdown();
    }
}

// ==================== 对话管理：清空/重命名/删除 ====================
const API_CHAT_RENAME = `${config.API_BASE_URL}/ai/chat/rename`;
const API_CHAT_DELETE = `${config.API_BASE_URL}/ai/chat/delete`;

function clearCurrentChat() {
    if (!chatData || !chatData.length) return;
    if (!confirm(t('chat_clear_confirm'))) return;
    document.querySelectorAll("#chatBox .message").forEach(el => el.remove());
    chatData = [];
    document.getElementById('emptyState')?.classList.remove('hidden');
    // 保存到本地和数据库
    const sessionTime = localStorage.getItem('thisSessionTime');
    if (sessionTime && isLoggedIn()) {
        localStorage.setItem(sessionTime, JSON.stringify([]));
        postToDb([], sessionTime, document.getElementById('chatSession').textContent);
    }
}

async function renameSession(sessionTime, oldName) {
    if (!isLoggedIn()) {
        alert(t('chat_need_login'));
        return;
    }
    const newName = prompt(t('chat_rename_placeholder'), oldName || '');
    if (newName === null) return;
    const trimmed = newName.trim();
    if (!trimmed) return;

    try {
        const res = await fetch(API_CHAT_RENAME, {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({
                session_time: parseInt(sessionTime, 10),
                session_name: trimmed
            })
        });
        if (res.ok) {
            // 更新侧边栏显示
            const el = document.querySelector(`.history.title[title="${sessionTime}"]`);
            if (el) el.textContent = trimmed;
            // 如果是当前会话，也更新顶部
            const currentTime = localStorage.getItem('thisSessionTime');
            if (String(currentTime) === String(sessionTime)) {
                document.getElementById('chatSession').textContent = trimmed;
            }
            // 更新 localStorage
            localStorage.setItem(sessionTime + '_name', trimmed);
        }
    } catch (e) {
        console.warn('重命名失败', e);
    }
}

async function deleteSession(sessionTime, el) {
    if (!isLoggedIn()) {
        alert(t('chat_need_login'));
        return;
    }
    if (!confirm(t('chat_delete_confirm'))) return;

    try {
        const res = await fetch(`${API_CHAT_DELETE}?session_time=${sessionTime}`, {
            method: 'DELETE',
            headers: buildAuthHeaders()
        });
        if (res.ok) {
            // 从侧边栏移除
            if (el) el.remove();
            localStorage.removeItem(sessionTime);
            localStorage.removeItem(sessionTime + '_name');
            // 如果删除的是当前会话，清空聊天区
            const currentTime = localStorage.getItem('thisSessionTime');
            if (String(currentTime) === String(sessionTime)) {
                createNewSession();
            }
        }
    } catch (e) {
        console.warn('删除失败', e);
    }
}

// 显示历史会话操作菜单（重命名/删除）
function showHistoryMenu(container, sessionTime, sessionName, anchorEl) {
    // 移除已有的菜单
    document.querySelectorAll('.history-menu').forEach(m => m.remove());

    const menu = document.createElement("div");
    menu.className = "history-menu";
    menu.innerHTML = `
        <div class="history-menu-item" data-action="rename">${t('chat_rename')}</div>
        <div class="history-menu-item danger" data-action="delete">${t('chat_delete')}</div>
    `;

    // 定位到按钮旁边
    document.body.appendChild(menu);
    const rect = anchorEl.getBoundingClientRect();
    menu.style.top = (rect.bottom + window.scrollY + 4) + "px";
    menu.style.right = (window.innerWidth - rect.right - window.scrollX) + "px";

    // 处理点击
    menu.querySelector('[data-action="rename"]').addEventListener('click', (e) => {
        e.stopPropagation();
        menu.remove();
        renameSession(sessionTime, sessionName);
    });
    menu.querySelector('[data-action="delete"]').addEventListener('click', (e) => {
        e.stopPropagation();
        menu.remove();
        deleteSession(sessionTime, container);
    });

    // 点击其他地方关闭菜单
    setTimeout(() => {
        document.addEventListener('click', function closeMenu(e) {
            if (!menu.contains(e.target) && e.target !== anchorEl) {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            }
        });
    }, 10);
}

// 给已有的历史会话条目添加 ... 按钮
function enhanceExistingHistoryItems() {
    const sideBar = document.getElementById('sideBar');
    if (!sideBar) return;
    sideBar.querySelectorAll('.history.title').forEach(item => {
        if (item.querySelector('.history-more-btn')) return; // 已添加过
        const sessionTime = item.title;
        const sessionName = item.textContent;

        // 把内容包到 span 里
        const nameSpan = document.createElement("span");
        nameSpan.className = "history-name";
        nameSpan.textContent = sessionName;
        item.innerHTML = "";
        item.appendChild(nameSpan);

        // 添加 ... 按钮
        const moreBtn = document.createElement("button");
        moreBtn.className = "history-more-btn";
        moreBtn.innerHTML = "···";
        moreBtn.title = t('chat_rename') + " / " + t('chat_delete');
        moreBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            showHistoryMenu(item, sessionTime, sessionName, moreBtn);
        });
        item.appendChild(moreBtn);

        // 给名称加点击事件
        nameSpan.addEventListener('click', async function () {
            if (typeof exitJobHuntMode === 'function') exitJobHuntMode();
            if (typeof exitWalletMode === 'function') exitWalletMode();
            document.getElementById("chatBox").querySelectorAll(".message").forEach(el => el.remove());
            const histories = document.querySelectorAll('.history');
            histories.forEach(h => { h.classList.remove('active') });
            item.classList.add('active');
            const session_time = item.title;
            window.localStorage.setItem('thisSessionTime', session_time);
            const messageList = JSON.parse(window.localStorage.getItem(session_time) || '[]');
            chatData = messageList;
            document.getElementById('chatSession').textContent = item.querySelector('.history-name')?.textContent || sessionName;
            renderHistoryChat(chatData);
            document.getElementById('emptyState')?.classList.toggle('hidden', chatData.length > 0);
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initScenes();
    enhanceExistingHistoryItems();
    updateSceneButton();  // 初始化场景按钮状态

    // 场景切换按钮
    const sceneBtn = document.getElementById('sceneToggleBtn');
    if (sceneBtn) {
        sceneBtn.addEventListener('click', toggleSceneDropdown);
    }
    // 智能联网按钮切换
    const searchBtn = document.getElementById('searchBtn');
    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            searchBtn.classList.toggle('active');
            const isActive = searchBtn.classList.contains('active');
            // 更新联网状态显示
            const netStatus = document.getElementById('netStatus');
            if (netStatus) {
                const netText = netStatus.querySelector('.net-text');
                if (isActive) {
                    netStatus.classList.add('online');
                    if (netText) netText.textContent = t('net_on') || '已联网';
                } else {
                    netStatus.classList.remove('online');
                    if (netText) netText.textContent = t('net_off') || '未联网';
                }
            }
        });
    }
    // 点击外部关闭场景下拉菜单
    document.addEventListener('click', (e) => {
        const wrap = document.getElementById('sceneDropdownWrap');
        if (wrap && !wrap.contains(e.target)) {
            closeSceneDropdown();
        }
        // 点击外部关闭快捷模板面板
        const qt = document.getElementById('quickTemplates');
        if (qt && !qt.classList.contains('hidden')) {
            const sceneBtn = document.getElementById('sceneToggleBtn');
            if (!qt.contains(e.target) && !sceneBtn.contains(e.target)) {
                qt.classList.add('hidden');
            }
        }
    });

    // 语言切换时重新渲染场景卡片
    document.addEventListener('langchange', () => {
        renderSceneGrid();
        updateSceneButton();
    });

    // 检测到新的历史条目时，给它加 ... 按钮
    const sideBar = document.getElementById('sideBar');
    if (sideBar) {
        const observer = new MutationObserver(() => {
            enhanceExistingHistoryItems();
        });
        observer.observe(sideBar, { childList: true });
    }

    // 拖拽上传文件
    const chatArea = document.querySelector('.right-side') || document.getElementById('chatBox')?.parentElement;
    const dropOverlay = document.createElement('div');
    dropOverlay.className = 'drag-drop-overlay';
    dropOverlay.innerHTML = `<div class="drag-drop-content"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg><span data-i18n="drag_drop_hint">${t('drag_drop_hint')}</span></div>`;
    document.body.appendChild(dropOverlay);

    if (chatArea) {
        ['dragenter', 'dragover'].forEach(evt => {
            chatArea.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropOverlay.classList.add('active');
            });
        });
        ['dragleave', 'drop'].forEach(evt => {
            chatArea.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (evt === 'dragleave' && chatArea.contains(e.relatedTarget)) return;
                dropOverlay.classList.remove('active');
            });
        });
        chatArea.addEventListener('drop', (e) => {
            e.preventDefault();
            const files = e.dataTransfer?.files;
            if (files && files.length) {
                const fileInput = document.getElementById('fileInput');
                if (fileInput) {
                    const dt = new DataTransfer();
                    for (const f of files) dt.items.add(f);
                    fileInput.files = dt.files;
                    fileInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        });
    }
});

