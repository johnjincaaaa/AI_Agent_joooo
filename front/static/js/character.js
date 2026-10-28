/* global config */
/* 角色系统前端 —— 角色市场 + 人设参数设置 + 会话绑定角色 */

window.currentCharacterId = window.currentCharacterId || null;

const CharacterAPI = {
    list: () => `${config.API_BASE_URL}/ai/characters`,
    import: () => `${config.API_BASE_URL}/ai/characters/import`,
    favorite: () => `${config.API_BASE_URL}/ai/characters/favorite`,
    pin: () => `${config.API_BASE_URL}/ai/characters/pin`,
    select: () => `${config.API_BASE_URL}/ai/characters/select`,
    settings: () => `${config.API_BASE_URL}/ai/character-settings`,
};

// ── 角色市场：加载 + 渲染 ──────────────────────────────────
async function loadCharacters() {
    const listEl = document.getElementById('characterMarketList');
    if (!listEl) return;
    listEl.innerHTML = '<div class="memory-empty">加载中…</div>';
    try {
        const res = await fetch(CharacterAPI.list(), { headers: buildAuthHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '加载失败');
        window.currentCharacterId = data.current_character || null;
        renderCharacterList(data.characters || []);
    } catch (err) {
        listEl.innerHTML = '<div class="memory-empty">加载失败，请刷新重试</div>';
        console.error(err);
    }
}

function renderCharacterList(chars) {
    const listEl = document.getElementById('characterMarketList');
    if (!listEl) return;
    if (!chars.length) {
        listEl.innerHTML = '<div class="memory-empty">暂无角色</div>';
        return;
    }
    listEl.innerHTML = chars.map(c => characterCardHTML(c)).join('');

    // 绑定卡片事件
    listEl.querySelectorAll('.character-card').forEach(card => {
        const cid = card.dataset.id;
        card.addEventListener('click', (e) => {
            // 点击操作按钮不触发选择
            if (e.target.closest('.character-action-btn') || e.target.closest('.character-use-btn')) return;
            selectCharacter(cid);
        });
    });
    listEl.querySelectorAll('[data-act="favorite"]').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); toggleFavorite(btn.dataset.id); });
    });
    listEl.querySelectorAll('[data-act="pin"]').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); togglePin(btn.dataset.id); });
    });
    listEl.querySelectorAll('[data-act="share"]').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); shareCharacter(btn.dataset.id); });
    });
    listEl.querySelectorAll('.character-use-btn').forEach(btn => {
        btn.addEventListener('click', (e) => { e.stopPropagation(); selectCharacter(btn.dataset.id); });
    });
}

function characterCardHTML(c) {
    const isCurrent = c.is_current;
    const favCls = c.is_favorite ? 'active' : '';
    const pinCls = c.is_pinned ? 'active' : '';
    const badge = c.builtin ? '<span class="character-badge">内置</span>' : '';
    const tags = (c.tags || []).join(' · ');
    return `
    <div class="character-card ${isCurrent ? 'current' : ''} ${c.is_pinned ? 'pinned' : ''}" data-id="${c.id}">
        <div class="character-avatar">
            <img src="${c.avatar}" alt="${c.name}" onerror="this.src='../static/a.png'">
        </div>
        <div class="character-info">
            <div class="character-name-row">
                <span class="character-name">${c.name}</span>
                ${badge}
            </div>
            <div class="character-desc">${c.description || ''}${tags ? ' · ' + tags : ''}</div>
        </div>
        <div class="character-actions">
            <button class="character-action-btn ${favCls}" data-act="favorite" data-id="${c.id}" title="收藏">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="${c.is_favorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
            </button>
            <button class="character-action-btn ${pinCls}" data-act="pin" data-id="${c.id}" title="置顶">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"></line><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24z"></path></svg>
            </button>
            <button class="character-action-btn" data-act="share" data-id="${c.id}" title="分享">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
            </button>
            <button class="character-use-btn ${isCurrent ? 'using' : ''}" data-id="${c.id}">${isCurrent ? '使用中' : '使用'}</button>
        </div>
    </div>`;
}

// ── 选择角色（绑定到主对话 + 重新渲染） ────────────────────
async function selectCharacter(cid) {
    try {
        const res = await fetch(CharacterAPI.select(), {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({ character_id: cid }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '选择失败');
        window.currentCharacterId = cid;
        // 刷新角色市场状态
        await loadCharacters();
        // 换角色 → 重新渲染主对话：清空旧角色的本地缓存与当前对话，展示新角色开场白
        reRenderMainChatForCharacter(data);
        showCharToast(`已切换到「${data.name}」`);
    } catch (err) {
        showCharToast(err.message || '选择失败');
        console.error(err);
    }
}

function reRenderMainChatForCharacter(data) {
    // 1. 清空旧角色主对话的本地缓存（session_time=0），避免读回旧人格的历史
    if (isLoggedIn()) {
        try { localStorage.removeItem('0'); } catch (e) {}
    }
    // 2. 切到主对话视图（清空 chatData + DOM，session_time=0）
    if (typeof backToMainChat === 'function') {
        // 先清掉缓存再走 backToMainChat，它内部 loadMainChatHistory 拉不到旧缓存就显示空态
        backToMainChat();
    } else {
        // 兜底：手动清空
        if (typeof chatData !== 'undefined') chatData = [];
        document.querySelectorAll('#chatBox .message').forEach(el => el.remove());
    }
    // 3. 展示新角色开场白（作为第一条 AI 消息）
    setTimeout(() => {
        if (data && data.opening) {
            if (typeof addMessage === 'function') {
                addMessage(data.opening, 'ai');
            }
        }
        // 空状态隐藏
        const emptyState = document.getElementById('emptyState');
        if (emptyState) emptyState.classList.add('hidden');
    }, 150);
}

// ── 收藏 / 置顶 / 分享 ─────────────────────────────────────
async function toggleFavorite(cid) {
    try {
        const res = await fetch(CharacterAPI.favorite(), {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({ character_id: cid, favorite: true }),
        });
        if (res.status === 401) { showCharToast('请先登录'); return; }
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '操作失败');
        await loadCharacters();
    } catch (err) { showCharToast(err.message || '操作失败'); }
}

async function togglePin(cid) {
    try {
        const res = await fetch(CharacterAPI.pin(), {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({ character_id: cid, pin: true }),
        });
        if (res.status === 401) { showCharToast('请先登录'); return; }
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '操作失败');
        await loadCharacters();
    } catch (err) { showCharToast(err.message || '操作失败'); }
}

async function shareCharacter(cid) {
    try {
        const res = await fetch(`${CharacterAPI.list()}/${cid}/share`, { headers: buildAuthHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '获取链接失败');
        try {
            await navigator.clipboard.writeText(data.url);
            showCharToast('分享链接已复制');
        } catch (e) {
            showCharToast(data.url);
        }
    } catch (err) { showCharToast(err.message || '获取链接失败'); }
}

// ── 导入角色 ───────────────────────────────────────────────
function initCharacterImport() {
    const btn = document.getElementById('importCharacterBtn');
    const fileInput = document.getElementById('characterImportFile');
    if (!btn || !fileInput) return;
    btn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
            const text = await file.text();
            const json = JSON.parse(text);
            const res = await fetch(CharacterAPI.import(), {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ json_data: json }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '导入失败');
            showCharToast(data.preview ? '未登录，仅预览' : '导入成功');
            await loadCharacters();
        } catch (err) {
            showCharToast(err.message || '导入失败，JSON 格式错误');
        } finally {
            fileInput.value = '';
        }
    });
}

// ── 人设参数设置 ───────────────────────────────────────────
async function loadCharacterSettings() {
    try {
        const res = await fetch(CharacterAPI.settings(), { headers: buildAuthHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '加载失败');
        applySettingsToForm(data.settings || {});
    } catch (err) { console.error(err); }
}

function applySettingsToForm(s) {
    const active = document.getElementById('setActiveMessage');
    if (active) active.checked = s.active_message !== false;
    setSeg('setTone', s.tone || 'normal');
    setSeg('setMemeFrequency', s.meme_frequency || 'normal');
    setSeg('setMemorySensitivity', s.memory_sensitivity || 'high');
}

function setSeg(containerId, value) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.querySelectorAll('button').forEach(b => {
        b.classList.toggle('active', b.dataset.value === value);
    });
}

function initCharacterSettings() {
    // 分段选择器点击
    ['setTone', 'setMemeFrequency', 'setMemorySensitivity'].forEach(id => {
        const container = document.getElementById(id);
        if (!container) return;
        container.querySelectorAll('button').forEach(btn => {
            btn.addEventListener('click', () => saveSettings());
        });
    });
    const activeSwitch = document.getElementById('setActiveMessage');
    if (activeSwitch) {
        activeSwitch.addEventListener('change', () => saveSettings());
    }
}

async function saveSettings() {
    const payload = {
        active_message: document.getElementById('setActiveMessage')?.checked,
        tone: getSegValue('setTone'),
        meme_frequency: getSegValue('setMemeFrequency'),
        memory_sensitivity: getSegValue('setMemorySensitivity'),
    };
    const tip = document.getElementById('charSettingTip');
    try {
        const res = await fetch(CharacterAPI.settings(), {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.status === 401) { if (tip) tip.textContent = '请先登录'; return; }
        if (!res.ok) throw new Error(data.detail || '保存失败');
        if (tip) { tip.textContent = '已保存'; setTimeout(() => { tip.textContent = ''; }, 1500); }
    } catch (err) {
        if (tip) tip.textContent = err.message || '保存失败';
    }
}

function getSegValue(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    const active = container.querySelector('button.active');
    return active ? active.dataset.value : null;
}

// ── 弹窗开关 ───────────────────────────────────────────────
function initCharacterModals() {
    const marketModal = document.getElementById('characterMarketModal');
    const settingsModal = document.getElementById('characterSettingsModal');

    const marketEntry = document.getElementById('characterMarketEntry');
    const settingsEntry = document.getElementById('characterSettingsEntry');

    const closeMarket = document.getElementById('closeCharacterMarketBtn');
    const closeSettings = document.getElementById('closeCharacterSettingsBtn');

    if (marketEntry && marketModal) {
        marketEntry.addEventListener('click', () => {
            document.querySelectorAll('.sidebar-nav-item').forEach(n => n.classList.remove('active'));
            marketEntry.classList.add('active');
            marketModal.style.display = 'block';
            loadCharacters();
        });
    }
    if (settingsEntry && settingsModal) {
        settingsEntry.addEventListener('click', () => {
            document.querySelectorAll('.sidebar-nav-item').forEach(n => n.classList.remove('active'));
            settingsEntry.classList.add('active');
            settingsModal.style.display = 'block';
            loadCharacterSettings();
        });
    }
    if (closeMarket && marketModal) closeMarket.addEventListener('click', () => { marketModal.style.display = 'none'; });
    if (closeSettings && settingsModal) closeSettings.addEventListener('click', () => { settingsModal.style.display = 'none'; });

    // 点击遮罩关闭
    if (marketModal) {
        marketModal.querySelector('.modal-overlay')?.addEventListener('click', () => { marketModal.style.display = 'none'; });
    }
    if (settingsModal) {
        settingsModal.querySelector('.modal-overlay')?.addEventListener('click', () => { settingsModal.style.display = 'none'; });
    }
}

// ── 轻提示 ─────────────────────────────────────────────────
function showCharToast(msg) {
    let el = document.getElementById('charToast');
    if (!el) {
        el = document.createElement('div');
        el.id = 'charToast';
        el.style.cssText = 'position:fixed;bottom:90px;left:50%;transform:translateX(-50%);background:var(--bg-elevated,#1b1e25);color:var(--text-primary,#ecedf1);border:1px solid var(--border-strong,rgba(255,255,255,0.12));border-radius:10px;padding:10px 18px;font-size:13px;z-index:999999;transition:opacity 0.2s ease;';
        document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.opacity = '1';
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.style.opacity = '0'; }, 2200);
}

// ── 初始化 ─────────────────────────────────────────────────
function initCharacterSystem() {
    initCharacterModals();
    initCharacterImport();
    initCharacterSettings();
    // 页面加载时预取当前角色 ID，供 sendMessage 携带
    fetch(CharacterAPI.list(), { headers: buildAuthHeaders() })
        .then(r => r.json())
        .then(d => { if (d && d.current_character) window.currentCharacterId = d.current_character; })
        .catch(() => {});
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCharacterSystem);
} else {
    initCharacterSystem();
}
