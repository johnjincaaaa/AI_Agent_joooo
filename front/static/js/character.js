/* global config */
/* 角色系统前端 —— 独立记忆体创建 + 人设参数设置 + 会话绑定角色 */

window.currentCharacterId = window.currentCharacterId || null;
// 当前角色的完整信息（含 avatar），供对话页 AI 头像使用
window.currentCharacter = window.currentCharacter || null;

const CharacterAPI = {
    list: () => `${config.API_BASE_URL}/ai/characters`,
    import: () => `${config.API_BASE_URL}/ai/characters/import`,
    favorite: () => `${config.API_BASE_URL}/ai/characters/favorite`,
    pin: () => `${config.API_BASE_URL}/ai/characters/pin`,
    select: () => `${config.API_BASE_URL}/ai/characters/select`,
    settings: () => `${config.API_BASE_URL}/ai/character-settings`,
};

// ── 独立记忆体创建：加载 + 渲染 ──────────────────────────────────
async function loadCharacters() {
    const listEl = document.getElementById('characterMarketList');
    if (!listEl) return;
    listEl.innerHTML = '<div class="memory-empty">加载中…</div>';
    try {
        const res = await fetch(CharacterAPI.list(), { headers: buildAuthHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '加载失败');
        // 注意：不要在这里覆盖 window.currentCharacterId。
        // 未登录用户切换角色时后端不持久化 current_character（仍返回默认 maid），
        // 若此处覆盖会把用户刚选的新角色冲掉，导致「切换后还是蓝发女仆」。
        // 当前角色 ID 由 initCharacterSystem 预取 + selectCharacter 显式维护。
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
    // 以前端本地 currentCharacterId 为准判断「使用中」，
    // 未登录用户切换角色后后端不持久化，仍返回默认 maid，会导致 UI 高亮错位。
    const localCurrent = window.currentCharacterId;
    const cards = chars.map(c => ({
        ...c,
        is_current: c.id === localCurrent,
    }));
    listEl.innerHTML = cards.map(c => characterCardHTML(c)).join('');

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
            <img src="${c.avatar}" alt="${c.name}" onerror="this.onerror=null;this.src='/static/a.png'">
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
        // 更新当前角色完整信息（含 avatar），供对话页 AI 头像使用
        window.currentCharacter = {
            id: cid,
            name: data.name || cid,
            avatar: data.avatar || '',
            opening: data.opening || '',
            voice: data.voice || '',
        };
        // 刷新角色系统状态
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
    // 切到主对话视图：chatData 清空 + DOM 清空，然后按「新灵魂」加载它的历史。
    // 注意：不要 removeItem('0')——现在主对话按灵魂分 key 缓存（0_<character_id>），
    // 删 '0' 既删不干净新灵魂的缓存，还可能误伤；直接走 backToMainChat 即可，
    // 它内部的 loadMainChatHistory 会按 window.currentCharacterId 读对应灵魂的历史。
    if (typeof backToMainChat === 'function') {
        backToMainChat();
    } else {
        // 兜底：手动清空
        if (typeof chatData !== 'undefined') chatData = [];
        document.querySelectorAll('#chatBox .message').forEach(el => el.remove());
    }
    // 展示新角色开场白（仅当该灵魂没有历史时，作为空对话引导）
    setTimeout(() => {
        const hasHistory = typeof chatData !== 'undefined' && Array.isArray(chatData) && chatData.length > 0;
        if (data && data.opening && !hasHistory) {
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
    if (!btn) return;
    // 【导入角色】→ 跳转 Jingent 创作中心（/chat/create），当前标签页直接跳转
    btn.addEventListener('click', () => {
        window.location.href = '/chat/create';
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
    const settingsModal = document.getElementById('characterSettingsModal');
    const settingsEntry = document.getElementById('characterSettingsEntry');
    const closeSettings = document.getElementById('closeCharacterSettingsBtn');

    if (settingsEntry && settingsModal) {
        settingsEntry.addEventListener('click', () => {
            document.querySelectorAll('.sidebar-nav-item').forEach(n => n.classList.remove('active'));
            settingsEntry.classList.add('active');
            settingsModal.style.display = 'block';
            loadCharacters();
            loadCharacterSettings();
            loadPetConfig();
        });
    }
    if (closeSettings && settingsModal) closeSettings.addEventListener('click', () => { settingsModal.style.display = 'none'; });

    // 点击遮罩关闭
    if (settingsModal) {
        settingsModal.querySelector('.modal-overlay')?.addEventListener('click', () => { settingsModal.style.display = 'none'; });
    }

    // 标签页切换
    initCharTabs();
}

function initCharTabs() {
    const tabs = document.querySelectorAll('#charTabs .char-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            const target = tab.dataset.tab;
            document.querySelectorAll('.char-tab-pane').forEach(p => p.classList.remove('active'));
            const pane = document.getElementById('charPane-' + target);
            if (pane) pane.classList.add('active');
        });
    });
}

// ── 宠物模型自定义 ─────────────────────────────────────────────
const PetAPI = {
    upload: () => `${config.API_BASE_URL}/plugins/dsh-pet/upload`,
    userConfig: () => `${config.API_BASE_URL}/plugins/dsh-pet/user-config`,
    resource: () => `${config.API_BASE_URL}/plugins/dsh-pet/resource`,
};

let petCfg = null;  // 用户配置缓存（pools/memes/sounds/settings）

async function loadPetConfig() {
    try {
        const res = await fetch(PetAPI.userConfig(), { headers: buildAuthHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || data.detail || '加载失败');
        petCfg = data.config || {};
        renderPetAssets(data.merged || {});
        renderTriggerConfig(data.merged || {});
    } catch (err) {
        console.error(err);
    }
}

function renderPetAssets(merged) {
    const ua = merged.userAssets || { webm: [], memes: [], sound: [] };
    renderAssetList('petWebmList', ua.webm || [], 'webm');
    renderAssetList('petMemeList', ua.memes || [], 'meme');
    renderAssetList('petSoundList', ua.sound || [], 'sound');
}

function renderAssetList(listId, items, kind) {
    const el = document.getElementById(listId);
    if (!el) return;
    if (!items.length) {
        el.innerHTML = '<div class="pet-asset-empty">暂无上传</div>';
        return;
    }
    el.innerHTML = items.map(name => `
        <div class="pet-asset-item" data-kind="${kind}" data-name="${name}">
            <span class="pet-asset-name">${name}</span>
            <button class="pet-asset-del" title="删除">删除</button>
        </div>`).join('');
    el.querySelectorAll('.pet-asset-del').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const item = e.target.closest('.pet-asset-item');
            const kind = item.dataset.kind;
            const name = item.dataset.name;
            await deletePetAsset(kind, name);
        });
    });
}

async function deletePetAsset(kind, name) {
    try {
        const res = await fetch(`${PetAPI.resource()}?kind=${encodeURIComponent(kind)}&name=${encodeURIComponent(name)}`, {
            method: 'DELETE',
            headers: buildAuthHeaders(),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) throw new Error(data.error || '删除失败');
        showCharToast('已删除 ' + name);
        await loadPetConfig();
    } catch (err) {
        showCharToast(err.message || '删除失败');
    }
}

function renderTriggerConfig(merged) {
    const el = document.getElementById('petTriggerConfig');
    if (!el) return;
    const pools = merged.pools || {};
    const labels = merged.poolLabels || {};
    const userWebms = (merged.userAssets && merged.userAssets.webm) || [];
    const userPools = (petCfg && petCfg.pools) || {};

    const html = Object.keys(labels).map(poolKey => {
        const label = labels[poolKey];
        const items = pools[poolKey] || [];
        const userSelected = userPools[poolKey] || [];
        // 只允许给用户上传的动画打勾（内置动画已在池里，不重复）
        const checkable = userWebms.filter(w => items.indexOf(w) < 0);
        const checkboxes = checkable.map(w => `
            <label class="pet-trigger-item">
                <input type="checkbox" data-pool="${poolKey}" data-name="${w}" ${userSelected.indexOf(w) >= 0 ? 'checked' : ''}>
                <span>${w}</span>
            </label>`).join('');
        const builtinCount = items.length - userWebms.filter(w => items.indexOf(w) >= 0).length;
        return `
        <div class="pet-trigger-group">
            <div class="pet-trigger-label">${label} <span class="pet-trigger-count">${items.length} 个动画</span></div>
            <div class="pet-trigger-items">
                ${checkboxes || '<span class="pet-asset-empty">该池暂无内置动画，可勾选下方上传的动画</span>'}
            </div>
        </div>`;
    }).join('');

    el.innerHTML = html;
}

async function uploadPetAssets(kind, inputId) {
    const input = document.getElementById(inputId);
    if (!input || !input.files.length) return;
    const files = Array.from(input.files);
    for (const file of files) {
        try {
            const fd = new FormData();
            fd.append('kind', kind);
            fd.append('file', file);
            const res = await fetch(PetAPI.upload(), {
                method: 'POST',
                headers: { 'Authorization': buildAuthHeaders()['Authorization'] || '' },
                body: fd,
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.error || '上传失败');
            showCharToast('已上传 ' + data.name);
        } catch (err) {
            showCharToast(err.message || '上传失败');
        }
    }
    input.value = '';
    await loadPetConfig();
}

async function savePetConfig() {
    const pools = {};
    document.querySelectorAll('#petTriggerConfig input[type=checkbox]').forEach(cb => {
        const pool = cb.dataset.pool;
        if (!pools[pool]) pools[pool] = [];
        if (cb.checked) pools[pool].push(cb.dataset.name);
    });
    const payload = {
        pools,
        memes: (petCfg && petCfg.memes) || {},
        sounds: (petCfg && petCfg.sounds) || {},
        settings: (petCfg && petCfg.settings) || {},
    };
    const tip = document.getElementById('petSaveTip');
    try {
        const res = await fetch(PetAPI.userConfig(), {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (res.status === 401) { if (tip) tip.textContent = '请先登录'; return; }
        if (!res.ok || !data.ok) throw new Error(data.error || '保存失败');
        if (tip) { tip.textContent = '已保存，刷新页面后桌宠生效'; setTimeout(() => { tip.textContent = ''; }, 2500); }
        await loadPetConfig();
    } catch (err) {
        if (tip) tip.textContent = err.message || '保存失败';
    }
}

function initPetUpload() {
    const bind = (btnId, inputId, kind) => {
        const btn = document.getElementById(btnId);
        if (btn) btn.addEventListener('click', () => uploadPetAssets(kind, inputId));
    };
    bind('petUploadWebmBtn', 'petWebmInput', 'webm');
    bind('petUploadMemeBtn', 'petMemeInput', 'meme');
    bind('petUploadSoundBtn', 'petSoundInput', 'sound');

    const saveBtn = document.getElementById('petSaveConfigBtn');
    if (saveBtn) saveBtn.addEventListener('click', savePetConfig);
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
    initPetUpload();
    // 页面加载时预取当前角色 ID + 完整信息，供 sendMessage 携带 & 对话页 AI 头像使用
    const prevCid = window.currentCharacterId;
    fetch(CharacterAPI.list(), { headers: buildAuthHeaders() })
        .then(r => r.json())
        .then(d => {
            if (!d) return;
            if (d.current_character) window.currentCharacterId = d.current_character;
            const chars = d.characters || [];
            const cur = chars.find(c => c.id === window.currentCharacterId)
                || chars.find(c => c.id === 'maid');
            if (cur) {
                window.currentCharacter = {
                    id: cur.id,
                    name: cur.name || cur.id,
                    avatar: cur.avatar || '',
                    opening: cur.opening || '',
                    voice: cur.voice || '',
                };
            }
            // 关键：预取完成后角色 ID 才确定。此前 loadMainChatHistory 可能
            // 用 '0_default' 共享 key 读/写缓存导致「各角色历史串号、头像一样」。
            // 现在重新加载主对话历史（用正确的 '0_<cid>' key），并刷新 AI 头像。
            if (prevCid !== window.currentCharacterId
                && typeof loadMainChatHistory === 'function') {
                // 主对话才需要重载（当前会话是主对话时）
                const st = window.localStorage.getItem('thisSessionTime');
                if (!st || st === 'null' || st === 'undefined' || st === '0') {
                    loadMainChatHistory();
                }
            }
        })
        .catch(() => {});
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCharacterSystem);
} else {
    initCharacterSystem();
}
