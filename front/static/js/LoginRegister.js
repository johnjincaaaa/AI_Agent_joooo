// 内置煤球头像与默认头像（必须最先定义：登录态加载时会立即调用 initUserProfile，const 有 TDZ）
const BUILTIN_AVATARS = [
    '/static/avatars/1.png', '/static/avatars/2.png', '/static/avatars/3.png',
    '/static/avatars/4.png', '/static/avatars/5.png', '/static/avatars/6.png',
];
const DEFAULT_AVATAR = '/static/a.png';

// 打开/关闭弹窗
const openBtn = document.getElementById('openLoginBtn');
const closeBtn = document.getElementById('closeLoginBtn');
const modal = document.getElementById('loginModal');
/* global marked */
// 验证登录状态
const isLogining = window.localStorage.getItem('token');
if (isLogining) {
    openBtn.textContent = t('logged_in');
    openBtn.disabled = true;
    openBtn.style.cursor = 'not-allowed';
    openBtn.style.opacity = '0.3';
    initUserProfile();
    initHistory().then(r => {});
} else {
    openBtn.textContent = t('not_logged_in');
    showLoginExpiredModal(t('please_login'), 'error');
}
openBtn.onclick = () => {
    modal.style.display = 'block';
};

closeBtn.onclick = () => {
    modal.style.display = 'none';
};

// 密码可视切换
document.querySelectorAll('.pwd-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const input = document.getElementById(btn.dataset.target);
        if (!input) return;
        const show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        btn.classList.toggle('visible', show);
    });
});


// 登录/注册 切换
const tabs = document.querySelectorAll('.tab');
const forms = document.querySelectorAll('.form-box');

tabs.forEach(tab => {
    tab.onclick = () => {
        tabs.forEach(t => t.classList.remove('active'));
        forms.forEach(f => f.classList.remove('show'));
        tab.classList.add('active');
        const type = tab.dataset.tab;
        document.getElementById(type + 'Form').classList.add('show');
    };
});

// =============== 登录方式切换 ===============
let loginMode = 'account';   // 'account' | 'phone'
let secretMode = 'password';  // 'password' | 'code'

// 账号/手机号切换
document.querySelectorAll('.login-type').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.login-type').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        loginMode = tab.dataset.ltype;
        if (loginMode === 'account') {
            document.getElementById('loginAccountField').style.display = '';
            document.getElementById('loginPhoneField').style.display = 'none';
        } else {
            document.getElementById('loginAccountField').style.display = 'none';
            document.getElementById('loginPhoneField').style.display = '';
        }
    });
});

// 密码/验证码切换
document.getElementById('loginSecretSwitch').addEventListener('click', () => {
    if (secretMode === 'password') {
        // 切到验证码
        secretMode = 'code';
        document.getElementById('loginSecretLabel').textContent = '验证码';
        document.getElementById('loginSecretSwitch').textContent = '密码登录';
        document.getElementById('loginPwdField').style.display = 'none';
        document.getElementById('loginCodeField').style.display = 'flex';
    } else {
        // 切到密码
        secretMode = 'password';
        document.getElementById('loginSecretLabel').textContent = '密码';
        document.getElementById('loginSecretSwitch').textContent = '短信验证码登录';
        document.getElementById('loginPwdField').style.display = '';
        document.getElementById('loginCodeField').style.display = 'none';
    }
});

// =============== 登录请求 ===============
function handleLoginSuccess(data, fallbackName) {
    localStorage.setItem('token', data.token);
    const displayName = data.username || fallbackName;
    localStorage.setItem('username', displayName);
    if (data.user_id) localStorage.setItem('user_id', data.user_id);
    document.getElementById("userName").textContent = displayName;
    modal.style.display = 'none';
    openBtn.textContent = t('logged_in');
    // 支持 next query 参数回跳（登录后回来源页用）
    try {
        const params = new URLSearchParams(window.location.search);
        const next = params.get('next');
        if (next && /^\/[A-Za-z0-9_\-/?=&.%#@]*$/.test(next)) { // 只允许同源相对路径
            window.location.replace(next);
            return; // 跳转后不执行 reload / initHistory
        }
    } catch(_) {}
    window.location.reload();
    initUserProfile();
    refreshUserProfile();
    initHistory().then(r => {});
}

document.getElementById('doLogin').onclick = async () => {
    try {
        if (secretMode === 'code') {
            // 短信验证码登录
            let phone;
            if (loginMode === 'phone') {
                phone = document.getElementById('login_phone').value.trim();
            } else {
                // 账号模式下用验证码也要求输入账号为手机号
                const acc = document.getElementById('login_username').value.trim();
                if (/^1\d{10}$/.test(acc)) {
                    phone = acc;
                } else {
                    alert('短信验证码登录需要使用手机号，请切换到手机号登录');
                    return;
                }
            }
            const code = document.getElementById('login_code').value.trim();
            if (!phone) { alert('请输入手机号'); return; }
            if (!/^1\d{10}$/.test(phone)) { alert('请输入正确的11位手机号'); return; }
            if (!code) { alert('请输入验证码'); return; }

            const res = await fetch(`${config.API_BASE_URL}/login/sms`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({phone, code})
            });
            const data = await res.json();
            if (data.code === 200) {
                handleLoginSuccess(data, phone);
            } else {
                alert('登录失败：' + (data.msg || '未知错误'));
            }
        } else {
            // 密码登录
            const account = loginMode === 'account'
                ? document.getElementById('login_username').value.trim()
                : document.getElementById('login_phone').value.trim();
            const pwd = document.getElementById('login_pwd').value.trim();
            if (!account) { alert('请输入账号或手机号'); return; }
            if (!pwd) { alert('请输入密码'); return; }

            const res = await fetch(`${config.API_BASE_URL}/login`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: account, password: pwd})
            });
            const data = await res.json();
            if (data.code === 200) {
                handleLoginSuccess(data, account);
            } else {
                alert('登录失败：' + (data.msg || '未知错误'));
            }
        }
    } catch (err) {
        console.error(err);
        alert('网络错误，请稍后重试');
    }
};

// =============== 登录页发送验证码 ===============
let loginCodeCountdown = 0;
const loginSendCodeBtn = document.getElementById('loginSendCodeBtn');
if (loginSendCodeBtn) {
    loginSendCodeBtn.onclick = async () => {
        if (loginCodeCountdown > 0) return;
        let phone;
        if (loginMode === 'phone') {
            phone = document.getElementById('login_phone').value.trim();
        } else {
            const acc = document.getElementById('login_username').value.trim();
            if (/^1\d{10}$/.test(acc)) {
                phone = acc;
            } else {
                alert('请输入正确的11位手机号，或切换到「手机号登录」');
                return;
            }
        }
        if (!/^1\d{10}$/.test(phone)) { alert('请输入正确的11位手机号'); return; }

        try {
            const res = await fetch(`${config.API_BASE_URL}/sms/send-code`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({phone})
            });
            const data = await res.json();
            if (data.code === 200) {
                if (data.debug_code) {
                    alert(`验证码已发送（开发模式）：${data.debug_code}`);
                } else {
                    alert('验证码已发送，请注意查收');
                }
                loginCodeCountdown = 60;
                loginSendCodeBtn.disabled = true;
                loginSendCodeBtn.style.opacity = '0.5';
                loginSendCodeBtn.style.cursor = 'not-allowed';
                const timer = setInterval(() => {
                    loginCodeCountdown--;
                    if (loginCodeCountdown <= 0) {
                        clearInterval(timer);
                        loginSendCodeBtn.textContent = '获取验证码';
                        loginSendCodeBtn.disabled = false;
                        loginSendCodeBtn.style.opacity = '';
                        loginSendCodeBtn.style.cursor = '';
                    } else {
                        loginSendCodeBtn.textContent = `${loginCodeCountdown}s 后重试`;
                    }
                }, 1000);
            } else {
                alert(data.msg || '发送失败');
            }
        } catch (err) {
            console.error(err);
            alert('网络错误');
        }
    };
}

// =============== 发送验证码（注册页） ===============
let codeCountdown = 0;
const sendCodeBtn = document.getElementById('sendCodeBtn');
if (sendCodeBtn) {
    sendCodeBtn.onclick = async () => {
        if (codeCountdown > 0) return;
        const phone = document.getElementById('reg_phone').value.trim();
        if (!/^1\d{10}$/.test(phone)) { alert('请输入正确的11位手机号'); return; }

        try {
            const res = await fetch(`${config.API_BASE_URL}/sms/send-code`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({phone})
            });
            const data = await res.json();
            if (data.code === 200) {
                // 开发模式：直接显示验证码
                if (data.debug_code) {
                    alert(`验证码已发送（开发模式）：${data.debug_code}`);
                } else {
                    alert('验证码已发送，请注意查收');
                }
                codeCountdown = 60;
                sendCodeBtn.disabled = true;
                sendCodeBtn.style.opacity = '0.5';
                sendCodeBtn.style.cursor = 'not-allowed';
                const timer = setInterval(() => {
                    codeCountdown--;
                    if (codeCountdown <= 0) {
                        clearInterval(timer);
                        sendCodeBtn.textContent = '获取验证码';
                        sendCodeBtn.disabled = false;
                        sendCodeBtn.style.opacity = '';
                        sendCodeBtn.style.cursor = '';
                    } else {
                        sendCodeBtn.textContent = `${codeCountdown}s 后重试`;
                    }
                }, 1000);
            } else {
                alert(data.msg || '发送失败');
            }
        } catch (err) {
            console.error(err);
            alert('网络错误');
        }
    };
}

// =============== 手机号注册 ===============
document.getElementById('doRegister').onclick = async () => {
    const phone = document.getElementById('reg_phone').value.trim();
    const code = document.getElementById('reg_code').value.trim();
    const pwd = document.getElementById('reg_pwd').value.trim();
    const repwd = document.getElementById('reg_repwd').value.trim();

    if (!/^1\d{10}$/.test(phone)) { alert('请输入正确的11位手机号'); return; }
    if (!code) { alert('请输入验证码'); return; }
    if (!pwd) { alert('请输入密码'); return; }
    if (pwd.length < 6) { alert('密码至少6位'); return; }
    if (!repwd) { alert('请再次输入密码'); return; }
    if (pwd !== repwd) { alert('两次密码不一致'); return; }

    try {
        const res = await fetch(`${config.API_BASE_URL}/register/phone`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({phone, code, password: pwd, confirm_password: repwd})
        });
        const data = await res.json();

        if (data.code === 200) {
            alert('注册成功！已自动登录');
            localStorage.setItem('token', data.token);
            const displayName = data.nickname || data.username;
            localStorage.setItem('username', displayName);
            if (data.user_id) localStorage.setItem('user_id', data.user_id);
            document.getElementById("userName").textContent = displayName;
            modal.style.display = 'none';
            refreshUserProfile();
            // 同样支持 next 回跳
            try {
                const params = new URLSearchParams(window.location.search);
                const next = params.get('next');
                if (next && /^\/[A-Za-z0-9_\-/?=&.%#@]*$/.test(next)) {
                    window.location.replace(next);
                    return;
                }
            } catch(_) {}
            window.location.reload();
        } else {
            alert('注册失败：' + (data.msg || '未知错误'));
        }
    } catch (err) {
        console.error(err);
        alert('网络错误，请稍后重试');
    }
};


// =============== 初始化历史会话记录 ===============
async function initHistory() {
    const token = window.localStorage.getItem('token');
    const res = await fetch(
        `${config.API_BASE_URL}/ai/chat/history?is_Load_All=true`,
        {
            headers: {
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            }
        }
    );
    if (res.status === 200) {
        const result = await res.json();
        const sideBar = document.getElementById('sideBar');

        result['chat_sessions'].forEach(e => {
            // 主对话（chat_type=main / session_time=0）是固定入口，不进历史列表
            if (e['chat_type'] === 'main' || String(e['session_time']) === '0') {
                // 仍缓存主对话历史，供「主对话」入口加载
                window.localStorage.setItem(String(e['session_time']), JSON.stringify(e['messages']));
                return;
            }
            const item = document.createElement("div");
            item.title = e['session_time'];
            item.className = `history title`;

            // 名称 span + ··· 菜单按钮（与 enhanceExistingHistoryItems 结构一致）
            const nameSpan = document.createElement("span");
            nameSpan.className = "history-name";
            nameSpan.textContent = e['session_name'];
            item.appendChild(nameSpan);

            const moreBtn = document.createElement("button");
            moreBtn.className = "history-more-btn";
            moreBtn.innerHTML = "···";
            moreBtn.title = t('chat_rename') + " / " + t('chat_delete');
            moreBtn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                if (typeof showHistoryMenu === 'function') {
                    showHistoryMenu(item, item.title, nameSpan.textContent, moreBtn);
                }
            });
            item.appendChild(moreBtn);

            sideBar.appendChild(item);

            // 切换历史会话：统一走 renderHistoryChat→addMessage（带时间戳/反应/右键菜单）
            nameSpan.addEventListener('click', async function () {
                if (typeof exitJobHuntMode === 'function') exitJobHuntMode();
                if (typeof exitWalletMode === 'function') exitWalletMode();
                // 历史会话一律是 secondary（标准助手）
                if (typeof currentChatType !== 'undefined') currentChatType = 'secondary';
                document.getElementById("chatBox").querySelectorAll(".message").forEach(el => el.remove());
                document.querySelectorAll('.history').forEach(h => h.classList.remove('active'));
                document.querySelectorAll('.sidebar-nav-item').forEach(n => n.classList.remove('active'));
                item.classList.add('active');
                window.localStorage.setItem('thisSessionTime', item.title);
                const stored = localStorage.getItem(String(item.title));
                chatData = stored ? JSON.parse(stored) : (e['messages'] || []);
                document.getElementById('chatSession').textContent = nameSpan.textContent;
                if (typeof renderHistoryChat === 'function') {
                    renderHistoryChat(chatData);
                }
                document.getElementById('emptyState')?.classList.toggle('hidden', chatData.length > 0);
            });
            window.localStorage.setItem(e['session_time'], JSON.stringify(e['messages']));
        });
    } else if (res.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("username");
        localStorage.removeItem("user_id");
        clearChatCache();
        profileDropdown.classList.remove("show");
        window.location.reload();
    }
}

// =============== 头像 ===============
function currentUserAvatar() {
    return localStorage.getItem('avatar') || DEFAULT_AVATAR;
}

// 同步所有头像展示位（侧边栏 + 设置预览 + 内置网格高亮 + 聊天区用户消息头像）
function updateAvatarUI() {
    const avatarUrl = currentUserAvatar();
    const img = document.getElementById('avatarImg');
    if (img) img.src = avatarUrl;
    const preview = document.getElementById('profileAvatarPreview');
    if (preview) preview.src = avatarUrl;
    document.querySelectorAll('.avatar-item').forEach(item => {
        item.classList.toggle('active', item.dataset.avatar === avatarUrl);
    });
    // 聊天区里所有已渲染的用户消息头像，实时切换为新头像
    document.querySelectorAll('.message.user .msg-avatar img').forEach(avImg => {
        avImg.src = avatarUrl;
    });
}

// 登录后从服务器拉取最新资料（头像/昵称），同步到本地
async function refreshUserProfile() {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
        const res = await fetch(`${config.API_BASE_URL}/user/info`, {
            headers: { "Authorization": "Bearer " + token }
        });
        const data = await res.json();
        if (data.code === 200 && data.data) {
            if (data.data.avatar) localStorage.setItem('avatar', data.data.avatar);
            const nick = data.data.nickname;
            if (nick) {
                localStorage.setItem('username', nick);
                const userNameEl = document.getElementById('userName');
                if (userNameEl) userNameEl.textContent = nick;
            }
            updateAvatarUI();
        }
    } catch (err) { console.error(err); }
}

// =============== 初始化用户头像状态 ===============
function initUserProfile() {
    const token = localStorage.getItem("token");
    const username = localStorage.getItem("username");
    const avatarImg = document.getElementById("avatarImg");
    const userName = document.getElementById("userName");

    if (token && username) {
        userName.textContent = username;
        avatarImg.src = currentUserAvatar();
        refreshUserProfile();
    } else {
        localStorage.removeItem('avatar');
        userName.textContent = t('not_logged_in');
        avatarImg.src = DEFAULT_AVATAR;
    }
}

// --------------- 头像菜单控制逻辑 ---------------
const profileMenuBtn = document.getElementById("profileMenuBtn");
const profileDropdown = document.getElementById("profileDropdown");
const logoutBtn = document.getElementById("logoutBtn");
const settingsBtn = document.getElementById("settingsBtn");

profileMenuBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    profileDropdown.classList.toggle("show");
});

document.addEventListener("click", () => {
    profileDropdown.classList.remove("show");
});

// --------------- 系统设置 ---------------
const settingsModal = document.getElementById("settingsModal");
const closeSettingsBtn = document.getElementById("closeSettingsBtn");

if (settingsBtn && settingsModal) {
    settingsBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        profileDropdown.classList.remove("show");
        settingsModal.style.display = 'block';
        renderAvatarGrid();
        updateAvatarUI();
        // 加载用户信息
        const token = localStorage.getItem("token");
        if (token) {
            try {
                const res = await fetch(`${config.API_BASE_URL}/user/info`, {
                    headers: { "Authorization": "Bearer " + token }
                });
                const data = await res.json();
                if (data.code === 200) {
                    document.getElementById("setAccount").value = data.data.username || '';
                    document.getElementById("setPhone").value = data.data.phone || '';
                    document.getElementById("setNickname").value = data.data.nickname || '';
                    if (data.data.avatar) localStorage.setItem('avatar', data.data.avatar);
                    updateAvatarUI();
                }
            } catch (err) { console.error(err); }
        }
    });
}

if (closeSettingsBtn && settingsModal) {
    closeSettingsBtn.onclick = () => { settingsModal.style.display = 'none'; };
}

// 设置选项卡切换
document.querySelectorAll('.settings-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.settings-pane').forEach(p => p.classList.remove('show'));
        tab.classList.add('active');
        const stab = tab.dataset.stab;
        document.getElementById('stab-' + stab).classList.add('show');
    });
});

// 保存昵称
const saveNicknameBtn = document.getElementById("saveNicknameBtn");
if (saveNicknameBtn) {
    saveNicknameBtn.onclick = async () => {
        const nickname = document.getElementById("setNickname").value.trim();
        if (!nickname) { alert('昵称不能为空'); return; }
        const token = localStorage.getItem("token");
        try {
            const res = await fetch(`${config.API_BASE_URL}/user/nickname`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({nickname})
            });
            const data = await res.json();
            if (data.code === 200) {
                alert('昵称修改成功');
                localStorage.setItem('username', nickname);
                document.getElementById("userName").textContent = nickname;
            } else {
                alert('修改失败：' + (data.msg || '未知错误'));
            }
        } catch (err) { console.error(err); alert('网络错误'); }
    };
}

// 修改密码
const savePasswordBtn = document.getElementById("savePasswordBtn");
if (savePasswordBtn) {
    savePasswordBtn.onclick = async () => {
        const old_pwd = document.getElementById("setOldPwd").value;
        const new_pwd = document.getElementById("setNewPwd").value;
        const confirm_pwd = document.getElementById("setConfirmPwd").value;
        if (!old_pwd || !new_pwd || !confirm_pwd) { alert('请填写所有密码字段'); return; }
        if (new_pwd.length < 6) { alert('新密码至少6位'); return; }
        if (new_pwd !== confirm_pwd) { alert('两次新密码不一致'); return; }
        const token = localStorage.getItem("token");
        try {
            const res = await fetch(`${config.API_BASE_URL}/user/password`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({old_password: old_pwd, new_password: new_pwd, confirm_password: confirm_pwd})
            });
            const data = await res.json();
            if (data.code === 200) {
                alert('密码修改成功');
                document.getElementById("setOldPwd").value = '';
                document.getElementById("setNewPwd").value = '';
                document.getElementById("setConfirmPwd").value = '';
            } else {
                alert('修改失败：' + (data.msg || '未知错误'));
            }
        } catch (err) { console.error(err); alert('网络错误'); }
    };
}

// --------------- 退出登录逻辑 ---------------
// 清除所有会话缓存：主对话固定 key '0' + 各历史会话的 session_time 数字 key + 会话重命名 '_name' 后缀。
// 退出登录后若不清，主对话记录（localStorage['0']）会残留，换账号仍能看到上一个账号的对话。
function clearChatCache() {
    // 先清固定 key
    localStorage.removeItem('0');
    localStorage.removeItem('thisSessionTime');
    // 遍历清掉所有「纯数字 key」（历史会话 session_time）及其重命名 key
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (!key) continue;
        if (/^\d+$/.test(key)) {
            keysToRemove.push(key);
            keysToRemove.push(key + '_name');
        }
    }
    keysToRemove.forEach(k => localStorage.removeItem(k));
}

logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    localStorage.removeItem("user_id");
    localStorage.removeItem("avatar");
    // AI 配置缓存（含 api_key 明文）：退出登录必须一起清掉，
    // 否则退出后打开设置弹窗会回显上一个账号的 key（切换账号残留）。
    localStorage.removeItem("jingent_llm_config");
    localStorage.removeItem("jingent_voice_settings");
    clearChatCache();
    profileDropdown.classList.remove("show");
    window.location.reload();
});


// =============== 头像：内置选择 + 上传 ===============
function renderAvatarGrid() {
    const grid = document.getElementById('avatarGrid');
    if (!grid) return;
    const cur = currentUserAvatar();
    grid.innerHTML = BUILTIN_AVATARS.map((src, i) =>
        `<div class="avatar-item ${src === cur ? 'active' : ''}" data-avatar="${src}" title="内置煤球头像 ${i + 1}">
            <img src="${src}" alt="煤球头像${i + 1}" loading="lazy">
        </div>`).join('');
    grid.querySelectorAll('.avatar-item').forEach(item => {
        item.addEventListener('click', async () => {
            const token = localStorage.getItem('token');
            if (!token) { showAvatarMsg('请先登录', false); return; }
            try {
                const res = await fetch(`${config.API_BASE_URL}/user/avatar/select`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
                    body: JSON.stringify({ avatar: item.dataset.avatar })
                });
                const data = await res.json();
                if (data.code === 200) {
                    localStorage.setItem('avatar', data.url);
                    updateAvatarUI();
                    showAvatarMsg('已切换为内置头像', true);
                } else {
                    showAvatarMsg(data.msg || '切换失败', false);
                }
            } catch (err) { console.error(err); showAvatarMsg('网络错误', false); }
        });
    });
}

function showAvatarMsg(text, ok) {
    const msg = document.getElementById('avatarMsg');
    if (!msg) return;
    msg.className = 'llm-test-result ' + (ok ? 'ok' : 'err');
    msg.textContent = text;
}

const uploadAvatarBtn = document.getElementById('uploadAvatarBtn');
const avatarFileInput = document.getElementById('avatarFileInput');
if (uploadAvatarBtn && avatarFileInput) {
    uploadAvatarBtn.onclick = () => avatarFileInput.click();
    avatarFileInput.onchange = async () => {
        const file = avatarFileInput.files[0];
        if (!file) { return; }
        if (!/\.(png|jpe?g|webp|gif)$/i.test(file.name)) {
            showAvatarMsg('仅支持 PNG/JPG/WEBP/GIF 格式', false);
            avatarFileInput.value = '';
            return;
        }
        if (file.size > 2 * 1024 * 1024) {
            showAvatarMsg('图片不能超过 2MB', false);
            avatarFileInput.value = '';
            return;
        }
        const token = localStorage.getItem('token');
        if (!token) { showAvatarMsg('请先登录', false); avatarFileInput.value = ''; return; }
        showAvatarMsg('上传中…', true);
        const fd = new FormData();
        fd.append('file', file);
        try {
            const res = await fetch(`${config.API_BASE_URL}/user/avatar`, {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token },
                body: fd
            });
            const data = await res.json();
            if (data.code === 200) {
                localStorage.setItem('avatar', data.url);
                updateAvatarUI();
                showAvatarMsg('上传成功，头像已更新', true);
            } else {
                showAvatarMsg(data.msg || '上传失败', false);
            }
        } catch (err) { console.error(err); showAvatarMsg('网络错误，请稍后重试', false); }
        avatarFileInput.value = '';
    };
}
