/* Jingent 创作中心 · /chat/create
   整合角色系统全部功能：内置角色 + 自定义角色 + 人设参数 + 宠物模型
*/
/* global config */
(function () {
    const API = (typeof config !== 'undefined' && config.API_BASE_URL) || '';

    const CharAPI = {
        list: () => `${API}/ai/characters`,                    // 内置 + 已落盘自定义角色
        favorite: () => `${API}/ai/characters/favorite`,
        pin: () => `${API}/ai/characters/pin`,
        select: () => `${API}/ai/characters/select`,
        del: (id) => `${API}/ai/characters/${id}`,             // 删除角色包 JSON（用户上传角色）
        settings: () => `${API}/ai/character-settings`,
    };
    const CreateAPI = {
        list: () => `${API}/ai/create/characters`,             // 自定义角色（草稿/审核中）
        use: (npc) => `${API}/ai/create/characters/${npc}/use`,
        submit: (npc) => `${API}/ai/create/characters/${npc}/submit`,
        del: (npc) => `${API}/ai/create/characters/${npc}`,
    };
    const PetAPI = {
        upload: () => `${API}/plugins/dsh-pet/upload`,
        userConfig: () => `${API}/plugins/dsh-pet/user-config`,
        resource: () => `${API}/plugins/dsh-pet/resource`,
    };
    const PetMarketAPI = {
        list: () => `${API}/ai/pet-market/pets`,
        install: () => `${API}/ai/pet-market/install`,
        switch: () => `${API}/ai/pet-market/switch`,
        del: (id) => `${API}/ai/pet-market/pets/${id}`,
    };

    let currentStatus = 'all';    // all / draft / pending
    let petCfg = null;            // 用户外观配置缓存

    window.currentCharacterId = window.currentCharacterId || null;

    function buildAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const token = localStorage.getItem('token');
        if (token && token !== 'null') headers['Authorization'] = 'Bearer ' + token;
        return headers;
    }
    function isLoggedIn() {
        const token = localStorage.getItem('token');
        return !!(token && token !== 'null');
    }

    function toast(msg) {
        let el = document.getElementById('createToast');
        if (!el) {
            el = document.createElement('div');
            el.id = 'createToast';
            el.style.cssText = 'position:fixed;bottom:90px;left:50%;transform:translateX(-50%);background:var(--bg-elevated,#1b1e25);color:var(--text-primary,#ecedf1);border:1px solid var(--border-strong,rgba(255,255,255,0.12));border-radius:10px;padding:10px 18px;font-size:13px;z-index:999999;transition:opacity 0.2s ease;';
            document.body.appendChild(el);
        }
        el.textContent = msg;
        el.style.opacity = '1';
        clearTimeout(el._t);
        el._t = setTimeout(() => { el.style.opacity = '0'; }, 2200);
    }

    // ── 左侧分类 Tab ──
    function initCatTabs() {
        const tabs = document.querySelectorAll('#sideBar .sidebar-nav-item[data-cat]');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const cat = tab.dataset.cat;
                document.querySelectorAll('.create-pane').forEach(p => p.classList.remove('active'));
                document.getElementById('paneSoul').classList.toggle('active', cat === 'soul');
                document.getElementById('paneModel').classList.toggle('active', cat === 'model');
                if (cat === 'model') loadPetConfig();
            });
        });
    }

    // ── 状态 Tab ──
    function initStatusTabs() {
        const tabs = document.querySelectorAll('.create-status-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentStatus = tab.dataset.status;
                loadCharacters();
            });
        });
    }

    // ── 加载角色（内置 + 自定义合并） ──
    async function loadCharacters() {
        const grid = document.getElementById('createGrid');
        const empty = document.getElementById('createEmpty');
        if (!grid) return;
        grid.innerHTML = '<div class="create-empty"><p>加载中…</p></div>';

        // 并行拉取内置角色 + 自定义角色
        const results = await Promise.allSettled([
            fetch(CharAPI.list(), { headers: buildAuthHeaders() }).then(r => r.json()),
            fetch(CreateAPI.list(), { headers: buildAuthHeaders() }).then(r => r.json()),
        ]);

        const builtinData = results[0].status === 'fulfilled' ? results[0].value : { characters: [] };
        const customData = results[1].status === 'fulfilled' ? results[1].value : { characters: [] };

        const builtins = (builtinData.characters || []);
        const customs = (customData.characters || []);

        // 缓存每个角色的音色（供音色弹窗回显）
        window.__charVoiceMap = window.__charVoiceMap || {};
        builtins.forEach(c => { if (c.id) window.__charVoiceMap[c.id] = c.voice || ''; });
        customs.forEach(c => { if (c.npc_id) window.__charVoiceMap['npc_' + c.npc_id] = c.voice || ''; });

        // 当前角色 ID（前端本地优先，其次后端）
        if (!window.currentCharacterId) {
            window.currentCharacterId = builtinData.current_character || null;
        }

        // 内置角色始终显示（不受状态过滤）；自定义角色按状态过滤
        let list = [];
        if (currentStatus === 'all') {
            list = [...builtins.map(c => ({ ...c, kind: 'builtin' })), ...customs.map(c => ({ ...c, kind: 'custom' }))];
        } else if (currentStatus === 'favorite') {
            // 收藏：展示已收藏的角色（内置 is_favorite；自定义若带该字段也一并展示）
            list = [
                ...builtins.filter(c => c.is_favorite).map(c => ({ ...c, kind: 'builtin' })),
                ...customs.filter(c => c.is_favorite).map(c => ({ ...c, kind: 'custom' })),
            ];
        } else {
            list = customs.filter(c => c.status === currentStatus).map(c => ({ ...c, kind: 'custom' }));
        }

        if (!list.length) {
            grid.innerHTML = '';
            empty.classList.remove('hidden');
            empty.querySelector('p').textContent =
                currentStatus === 'all' ? '还没有角色，点右上角「捏小人」开始创作'
                : currentStatus === 'favorite' ? '还没有收藏的角色'
                : currentStatus === 'draft' ? '还没有草稿'
                : '还没有审核中的角色';
            return;
        }
        empty.classList.add('hidden');
        renderCards(list);
        prefetchVoiceNames().then(() => renderCards(list));  // 拿到音色名后重渲染一次，刷新音色标签
    }

    function renderCards(list) {
        const grid = document.getElementById('createGrid');
        grid.innerHTML = list.map(cardHTML).join('');

        grid.querySelectorAll('[data-act]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const npc = btn.dataset.npc || btn.dataset.id;
                const act = btn.dataset.act;
                const kind = btn.dataset.kind;
                handleAction(act, npc, kind, btn);
            });
        });
    }

    function cardHTML(c) {
        const isCurrent = c.kind === 'builtin'
            ? (c.id === window.currentCharacterId)
            : (c.npc_id && ('npc_' + c.npc_id) === window.currentCharacterId);
        const isDraft = c.status === 'draft';
        // 真内置（5 个原始角色）：builtin===true；之后落盘的用户创建角色：builtin===false
        const isBuiltin = c.kind === 'builtin' && c.builtin === true;
        const isUploaded = c.kind === 'builtin' && c.builtin !== true;
        const avatar = c.avatar
            ? `<img src="${c.avatar}" alt="${escapeHtml(c.name)}" onerror="this.style.display='none'">`
            : `<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="10" r="3"></circle><path d="M7 20.66V19a5 5 0 0 1 10 0v1.66"></path></svg>`;
        const badge = isBuiltin ? '<span class="character-badge">内置</span>'
            : isUploaded ? '<span class="character-badge">用户上传</span>'
            : `<span class="create-status-badge ${c.status}">${c.status_label || c.status}</span>`;
        const updated = c.updated_at ? new Date(c.updated_at).toLocaleDateString() : '';

        const actions = [];
        // 使用
        actions.push(`<button class="character-use-btn ${isCurrent ? 'using' : ''}" data-act="use" data-id="${c.id || ''}" data-npc="${c.npc_id || ''}" data-kind="${c.kind}">${isCurrent ? '使用中' : '使用'}</button>`);
        if (isBuiltin) {
            // 真内置：收藏/置顶/分享（不可删除）
            actions.push(`<button class="character-action-btn ${c.is_favorite ? 'active' : ''}" data-act="favorite" data-id="${c.id}" data-kind="builtin" title="收藏"><svg width="15" height="15" viewBox="0 0 24 24" fill="${c.is_favorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg></button>`);
            actions.push(`<button class="character-action-btn ${c.is_pinned ? 'active' : ''}" data-act="pin" data-id="${c.id}" data-kind="builtin" title="置顶"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"></line><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24z"></path></svg></button>`);
            actions.push(`<button class="character-action-btn" data-act="share" data-id="${c.id}" data-kind="builtin" title="分享"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg></button>`);
            actions.push(`<button class="character-action-btn" data-act="voice" data-id="${c.id}" data-name="${escapeHtml(c.name)}" data-kind="builtin" title="设置音色"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg></button>`);
        } else if (isUploaded) {
            // 落盘的用户上传角色：分享 + 删除
            actions.push(`<button class="character-action-btn" data-act="share" data-id="${c.id}" data-kind="builtin" title="分享"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg></button>`);
            actions.push(`<button class="character-action-btn" data-act="voice" data-id="${c.id}" data-name="${escapeHtml(c.name)}" data-kind="builtin" title="设置音色"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path></svg></button>`);
            actions.push(`<button class="character-action-btn danger" data-act="delete" data-id="${c.id}" data-kind="builtin" title="删除"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>`);
        } else {
            // 数据库草稿/审核/拒绝：分享 + （草稿：编辑/提交审核）；任何状态都可删除
            actions.push(`<button class="character-action-btn" data-act="share" data-npc="${c.npc_id}" data-kind="custom" title="分享"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg></button>`);
            if (isDraft) {
                actions.push(`<button class="character-action-btn" data-act="submit" data-npc="${c.npc_id}" data-kind="custom" title="提交审核"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></button>`);
                actions.push(`<button class="character-action-btn" data-act="edit" data-npc="${c.npc_id}" data-kind="custom" title="编辑"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg></button>`);
            }
            actions.push(`<button class="character-action-btn danger" data-act="delete" data-npc="${c.npc_id}" data-kind="custom" title="删除"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button>`);
        }

        // 音色标签：显示已绑定的音色名（若有）
        const charVoice = c.voice || '';
        const voiceName = charVoice ? (window.__voiceNameMap && window.__voiceNameMap[charVoice] || charVoice) : '';
        const voiceTag = voiceName ? `<span class="create-card-voice">🔊 ${escapeHtml(voiceName)}</span>` : '';

        return `
        <div class="create-card ${isCurrent ? 'current' : ''}">
            <div class="create-card-avatar">${avatar}</div>
            <div class="create-card-body">
                <div class="create-card-name-row">
                    <span class="create-card-name">${escapeHtml(c.name)}</span>
                    ${badge}
                </div>
                <div class="create-card-desc">${escapeHtml(c.description || '这个人很懒，还没写简介')}</div>
            </div>
            <div class="create-card-meta">
                <span>${updated}</span>
                ${voiceTag}
            </div>
            <div class="create-card-actions">${actions.join('')}</div>
        </div>`;
    }

    async function handleAction(act, target, kind, btn) {
        switch (act) {
            case 'use':
                if (kind === 'builtin') await selectCharacter(target);
                else await useCustomCharacter(target);
                break;
            case 'favorite': await toggleFavorite(target, btn); break;
            case 'pin': await togglePin(target, btn); break;
            case 'share': shareCharacter(target, kind); break;
            case 'edit': location.href = `/chat/create/edit?npc_id=${target}`; break;
            case 'submit': await submitCharacter(target); break;
            case 'delete': await deleteCharacter(target, kind); break;
            case 'voice': openVoiceModal(target, kind); break;
        }
    }

    // ── 音色设置（独立记忆体语音绑定）──
    let voiceModalCharId = null;
    let voiceModalCharKind = null;

    async function loadVoiceOptions() {
        const sel = document.getElementById('voiceModalSelect');
        const tip = document.getElementById('voiceModalTip');
        if (!sel) return;
        if (tip) tip.textContent = '正在加载音色…';
        try {
            const res = await fetch(`${API}/ai/tts/voices`, { headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '加载失败');
            const voices = (data.voices || []).filter(v => v && v.type === 'profile');
            const cur = sel.dataset.saved || '';
            sel.innerHTML = '<option value="">默认音色</option>';
            window.__voiceNameMap = window.__voiceNameMap || {};
            voices.forEach(v => {
                const val = v.voice_id || v.id || v.name || '';
                if (!val) return;
                window.__voiceNameMap[val] = v.name || val;
                const opt = document.createElement('option');
                opt.value = val;
                opt.textContent = v.name || val;
                sel.appendChild(opt);
            });
            if (cur && ![...sel.options].some(o => o.value === cur)) {
                const opt = document.createElement('option');
                opt.value = cur;
                opt.textContent = cur;
                sel.appendChild(opt);
            }
            sel.value = cur;
            if (tip) tip.textContent = '已加载 ' + voices.length + ' 个自定义音色';
        } catch (err) {
            if (tip) tip.textContent = '音色服务不可用（未启动 VoiceStudio）';
        }
    }

    function openVoiceModal(target, kind) {
        voiceModalCharId = target;
        voiceModalCharKind = kind;
        const modal = document.getElementById('voiceModal');
        const nameEl = document.getElementById('voiceModalCharName');
        const sel = document.getElementById('voiceModalSelect');
        const tip = document.getElementById('voiceModalTip');
        if (!modal) return;
        // 回显当前音色（从角色数据里找）
        const btn = document.querySelector(`[data-act="voice"][data-id="${target}"]`);
        const card = btn ? btn.closest('.create-card') : null;
        let saved = '';
        // 尝试从 window.__charVoiceMap 读取（loadCharacters 时缓存）
        if (window.__charVoiceMap && window.__charVoiceMap[target]) saved = window.__charVoiceMap[target];
        if (sel) { sel.dataset.saved = saved; sel.value = saved; }
        if (nameEl) nameEl.textContent = '· ' + (btn ? btn.dataset.name : target);
        if (tip) tip.textContent = '';
        modal.style.display = 'flex';
        loadVoiceOptions();
    }

    async function saveVoice() {
        const sel = document.getElementById('voiceModalSelect');
        const modal = document.getElementById('voiceModal');
        const tip = document.getElementById('voiceModalTip');
        if (!voiceModalCharId) return;
        const voice = sel ? sel.value : '';
        try {
            const res = await fetch(`${API}/ai/characters/${voiceModalCharId}/voice`, {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ voice }),
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '保存失败');
            if (window.__charVoiceMap) window.__charVoiceMap[voiceModalCharId] = voice;
            if (modal) modal.style.display = 'none';
            toast(voice ? '音色已绑定' : '已恢复默认音色');
            await loadCharacters();
        } catch (err) {
            if (tip) tip.textContent = '保存失败：' + (err.message || '未知错误');
            else toast(err.message || '保存失败');
        }
    }

    async function prefetchVoiceNames() {
        // 预取音色映射，供卡片显示音色名（失败静默，不影响主流程）
        try {
            const res = await fetch(`${API}/ai/tts/voices`, { headers: buildAuthHeaders() });
            const data = await res.json();
            if (res.ok && data.ok && Array.isArray(data.voices)) {
                window.__voiceNameMap = window.__voiceNameMap || {};
                data.voices.filter(v => v && v.type === 'profile').forEach(v => {
                    const val = v.voice_id || v.id || v.name || '';
                    if (val) window.__voiceNameMap[val] = v.name || val;
                });
            }
        } catch (e) {}
    }

    async function cloneVoice(audioFile) {
        const tip = document.getElementById('voiceModalTip');
        const sel = document.getElementById('voiceModalSelect');
        const btn = document.getElementById('voiceCloneBtn');
        if (tip) tip.textContent = '正在克隆音色（首次可能较慢，请耐心）…';
        if (btn) { btn.disabled = true; btn.textContent = '克隆中…'; }
        try {
            const fd = new FormData();
            fd.append('file', audioFile);
            fd.append('name', '克隆音色-' + Date.now().toString().slice(-6));
            fd.append('language', 'zh');
            const token = localStorage.getItem('token') || '';
            const res = await fetch(`${API}/ai/tts/clone`, {
                method: 'POST',
                headers: token && token !== 'null' ? { 'Authorization': 'Bearer ' + token } : {},
                body: fd,
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '克隆失败');
            const vid = data.voice_id || (data.profile && data.profile.id);
            if (tip) tip.textContent = '✅ 克隆成功：' + (data.name || vid);
            // 刷新音色列表并选中新音色
            await loadVoiceOptions();
            if (sel && vid) {
                if (![...sel.options].some(o => o.value === vid)) {
                    const opt = document.createElement('option');
                    opt.value = vid;
                    opt.textContent = data.name || vid;
                    sel.appendChild(opt);
                }
                sel.value = vid;
            }
        } catch (err) {
            if (tip) tip.textContent = '克隆失败：' + (err.message || '未知错误');
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '🎙 克隆新音色'; }
        }
    }

    function initVoiceModal() {
        const modal = document.getElementById('voiceModal');
        const cancel = document.getElementById('voiceModalCancel');
        const save = document.getElementById('voiceModalSave');
        const overlay = document.getElementById('voiceModalOverlay');
        const cloneBtn = document.getElementById('voiceCloneBtn');
        const cloneFile = document.getElementById('voiceCloneFile');
        if (!modal) return;
        if (cancel) cancel.addEventListener('click', () => { modal.style.display = 'none'; });
        if (save) save.addEventListener('click', saveVoice);
        if (overlay) overlay.addEventListener('click', () => { modal.style.display = 'none'; });
        if (cloneBtn && cloneFile) {
            cloneBtn.addEventListener('click', () => cloneFile.click());
            cloneFile.addEventListener('change', async () => {
                const f = cloneFile.files && cloneFile.files[0];
                if (!f) return;
                await cloneVoice(f);
                cloneFile.value = '';
            });
        }
    }

    // ── 使用内置角色（绑定到对话） ──
    async function selectCharacter(cid) {
        try {
            const res = await fetch(CharAPI.select(), {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ character_id: cid }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '选择失败');
            window.currentCharacterId = cid;
            await loadCharacters();
            toast(`已切换到「${data.name}」`);
            setTimeout(() => { location.href = '/chat'; }, 800);
        } catch (err) {
            toast(err.message || '选择失败');
        }
    }

    // ── 使用自定义角色（导入到对话） ──
    async function useCustomCharacter(npc) {
        try {
            const res = await fetch(CreateAPI.use(npc), { method: 'POST', headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '使用失败');
            window.currentCharacterId = data.character_id;
            toast(`已使用「${data.name}」，正在跳转主对话…`);
            setTimeout(() => { location.href = '/chat'; }, 800);
        } catch (err) {
            toast(err.message || '使用失败');
        }
    }

    // ── 收藏 / 置顶 / 分享 ──
    async function toggleFavorite(cid, btn) {
        if (!isLoggedIn()) { toast('请先登录'); return; }
        // 根据按钮当前 active 状态取反，实现「再点一次取消收藏」
        const currentlyActive = btn ? btn.classList.contains('active') : false;
        try {
            const res = await fetch(CharAPI.favorite(), {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ character_id: cid, favorite: !currentlyActive }),
            });
            if (!res.ok) throw new Error('操作失败');
            await loadCharacters();
        } catch (err) { toast('收藏操作失败'); }
    }
    async function togglePin(cid, btn) {
        if (!isLoggedIn()) { toast('请先登录'); return; }
        // 根据按钮当前 active 状态取反，实现「再点一次取消置顶」
        const currentlyActive = btn ? btn.classList.contains('active') : false;
        try {
            const res = await fetch(CharAPI.pin(), {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ character_id: cid, pin: !currentlyActive }),
            });
            if (!res.ok) throw new Error('操作失败');
            await loadCharacters();
        } catch (err) { toast('置顶操作失败'); }
    }
    function shareCharacter(target, kind) {
        // 带上当前推广码（分享 app 的 pid），实现分享即推广溯源
        const ref = (typeof getReferral === 'function') ? getReferral() : '';
        const refQs = ref ? `ref=${encodeURIComponent(ref)}` : '';
        let url;
        if (kind === 'builtin') {
            url = `${location.origin}/chat${refQs ? '?' + refQs : ''}`;
        } else {
            const parts = [`npc_id=${encodeURIComponent(target)}`];
            if (refQs) parts.push(refQs);
            url = `${location.origin}/chat/create/edit?${parts.join('&')}`;
        }
        if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(() => toast('链接已复制')).catch(() => toast(url));
        } else {
            toast(url);
        }
    }

    // 导入链接：粘贴别人分享的记忆体链接，解析 npc_id 后跳转编辑页导入
    function importFromLink() {
        const raw = prompt('粘贴记忆体分享链接：');
        if (!raw) return;
        try {
            const u = new URL(raw.trim());
            const npcId = u.searchParams.get('npc_id');
            if (!npcId) {
                toast('链接里没有找到记忆体编号（npc_id）');
                return;
            }
            location.href = `/chat/create/edit?npc_id=${encodeURIComponent(npcId)}&import=1`;
        } catch (e) {
            toast('链接格式不对，请重新粘贴');
        }
    }

    // ── 提交审核 / 删除 ──
    async function submitCharacter(npc) {
        if (!isLoggedIn()) { toast('请先登录'); return; }
        try {
            const res = await fetch(CreateAPI.submit(npc), { method: 'POST', headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '提交失败');
            toast('已提交审核');
            await loadCharacters();
        } catch (err) { toast(err.message || '提交失败'); }
    }
    async function deleteCharacter(target, kind) {
        if (!isLoggedIn()) { toast('请先登录'); return; }
        if (!confirm('确定删除这个角色吗？删除后不可恢复。')) return;
        try {
            const url = kind === 'builtin' ? CharAPI.del(target) : CreateAPI.del(target);
            const res = await fetch(url, { method: 'DELETE', headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '删除失败');
            toast('已删除');
            await loadCharacters();
        } catch (err) { toast(err.message || '删除失败'); }
    }


    // ── 宠物模型 ──
    async function loadPetConfig() {
        try {
            const res = await fetch(PetAPI.userConfig(), { headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || '加载失败');
            petCfg = data.config || {};
            renderPetAssets(data.merged || {});
            renderTriggerConfig(data.merged || {});
        } catch (err) { /* 忽略 */ }
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
                await deletePetAsset(item.dataset.kind, item.dataset.name);
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
            toast('已删除 ' + name);
            await loadPetConfig();
        } catch (err) { toast(err.message || '删除失败'); }
    }
    function renderTriggerConfig(merged) {
        const el = document.getElementById('petTriggerConfig');
        if (!el) return;
        const pools = merged.pools || {};
        const labels = merged.poolLabels || {};
        const userWebms = (merged.userAssets && merged.userAssets.webm) || [];
        const userPools = (petCfg && petCfg.pools) || {};

        el.innerHTML = Object.keys(labels).map(poolKey => {
            const label = labels[poolKey];
            const items = pools[poolKey] || [];
            const userSelected = userPools[poolKey] || [];
            const checkable = userWebms.filter(w => items.indexOf(w) < 0);
            const checkboxes = checkable.map(w => `
                <label class="pet-trigger-item">
                    <input type="checkbox" data-pool="${poolKey}" data-name="${w}" ${userSelected.indexOf(w) >= 0 ? 'checked' : ''}>
                    <span>${w}</span>
                </label>`).join('');
            return `
            <div class="pet-trigger-group">
                <div class="pet-trigger-label">${label} <span class="pet-trigger-count">${items.length} 个动画</span></div>
                <div class="pet-trigger-items">
                    ${checkboxes || '<span class="pet-asset-empty">该池暂无内置动画，可勾选下方上传的动画</span>'}
                </div>
            </div>`;
        }).join('');
    }
    async function uploadPetAssets(kind, inputId) {
        const input = document.getElementById(inputId);
        if (!input || !input.files.length) return;
        if (!isLoggedIn()) { toast('请先登录'); return; }
        const files = Array.from(input.files);
        for (const file of files) {
            try {
                const fd = new FormData();
                fd.append('kind', kind);
                fd.append('file', file);
                const res = await fetch(PetAPI.upload(), {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') },
                    body: fd,
                });
                const data = await res.json();
                if (!res.ok || !data.ok) throw new Error(data.error || '上传失败');
                toast('已上传 ' + data.name);
            } catch (err) { toast(err.message || '上传失败'); }
        }
        input.value = '';
        await loadPetConfig();
    }
    async function savePetConfig() {
        if (!isLoggedIn()) { toast('请先登录'); return; }
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
        } catch (err) { if (tip) tip.textContent = err.message || '保存失败'; }
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

    // ── 宠物插件市场 ──
    let marketCurrentPet = null;

    function marketTip(msg, ok) {
        const tip = document.getElementById('petMarketTip');
        if (!tip) return;
        tip.textContent = msg || '';
        tip.style.color = ok === false ? '#ef4444' : '';
        setTimeout(() => { tip.textContent = ''; tip.style.color = ''; }, 3000);
    }

    async function loadPetMarket() {
        try {
            const res = await fetch(PetMarketAPI.list(), { headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error('加载失败');
            marketCurrentPet = data.current_pet;
            renderInstalledPets(data.installed || []);
            renderPresetPets(data.market || []);
        } catch (err) { /* 忽略 */ }
    }

    function renderInstalledPets(list) {
        const el = document.getElementById('petMarketInstalled');
        if (!el) return;
        // 内置默认大肥鱼：始终在列表最前，可一键切回
        const defaultItem = `
            <div class="pet-market-item default ${!marketCurrentPet ? 'current' : ''}">
                <div class="pet-market-item-avatar"><img src="/plugins/dsh-pet/assets/logo.png" alt="大肥鱼" onerror="this.style.display='none';this.parentNode.textContent='🐟'"></div>
                <div class="pet-market-item-info">
                    <div class="pet-market-item-name">默认大肥鱼</div>
                    <div class="pet-market-item-meta">内置桌宠 · 106 个动画</div>
                </div>
                <div class="pet-market-item-actions">
                    <button class="create-action-btn primary" data-act="use-default">${!marketCurrentPet ? '使用中' : '使用'}</button>
                </div>
            </div>`;
        let html = defaultItem;
        if (list.length) {
            html += list.map(p => {
                const meta = `${p.webm_count} 个动画`;
                return `
                <div class="pet-market-item ${marketCurrentPet === p.pet_id ? 'current' : ''}">
                    <div class="pet-market-item-avatar">${p.preview ? `<img src="${p.preview}" onerror="this.style.display='none';this.parentNode.textContent='🐾'">` : '🐾'}</div>
                    <div class="pet-market-item-info">
                        <div class="pet-market-item-name">${escapeHtml(p.name)}</div>
                        <div class="pet-market-item-meta">${meta}</div>
                    </div>
                    <div class="pet-market-item-actions">
                        <button class="create-action-btn primary" data-act="use" data-pet="${p.pet_id}">${marketCurrentPet === p.pet_id ? '使用中' : '使用'}</button>
                        <button class="create-action-btn danger" data-act="uninstall" data-pet="${p.pet_id}">卸载</button>
                    </div>
                </div>`;
            }).join('');
        } else {
            html += '<div class="pet-asset-empty">暂无已安装的宠物，从下方市场导入或贴 git 链接</div>';
        }
        el.innerHTML = html;
        el.querySelectorAll('[data-act]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const pid = btn.dataset.pet;
                const act = btn.dataset.act;
                if (act === 'use') switchPet(pid);
                else if (act === 'use-default') switchPet(null);
                else if (act === 'uninstall') uninstallPet(pid);
            });
        });
    }

    function renderPresetPets(list) {
        const el = document.getElementById('petMarketPreset');
        if (!el) return;
        el.innerHTML = list.map(p => `
            <div class="pet-market-item preset ${p.installed ? 'installed' : ''}">
                <div class="pet-market-item-avatar">🐾</div>
                <div class="pet-market-item-info">
                    <div class="pet-market-item-name">${escapeHtml(p.name)}</div>
                    <div class="pet-market-item-meta">${escapeHtml(p.desc || '')}</div>
                </div>
                <div class="pet-market-item-actions">
                    <button class="create-action-btn primary" data-act="install" data-git="${escapeHtml(p.git)}" data-pet="${p.pet_id}">${p.installed ? '已装·重装' : '安装'}</button>
                </div>
            </div>`).join('');
        el.querySelectorAll('[data-act="install"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                installPet(btn.dataset.git, btn.dataset.pet, false);
            });
        });
    }

    // 安装过程可视化：遮罩 + 阶段清单 + 计时 + 真实结果
    const INSTALL_STAGES = [
        '连接仓库，拉取文件清单…',
        '下载动画 / 立绘资源…',
        '识别动画池、生成配置…',
        '落盘安装、写入元信息…',
    ];

    function showInstallOverlay(name) {
        let ov = document.getElementById('petInstallOverlay');
        if (!ov) {
            ov = document.createElement('div');
            ov.id = 'petInstallOverlay';
            ov.className = 'pet-install-overlay';
            document.body.appendChild(ov);
        }
        const stagesHtml = INSTALL_STAGES.map((s, i) =>
            `<li class="pet-install-stage" data-stage="${i}"><span class="pis-dot"></span><span class="pis-text">${escapeHtml(s)}</span></li>`
        ).join('');
        ov.innerHTML = `
            <div class="pet-install-card">
                <div class="pet-install-spinner"></div>
                <div class="pet-install-title">正在安装${name ? '「' + escapeHtml(name) + '」' : '宠物'}</div>
                <div class="pet-install-elapsed" id="petInstallElapsed">0.0s</div>
                <ul class="pet-install-stages">${stagesHtml}</ul>
                <div class="pet-install-hint">GitHub 仓库较大时需要几十秒，请耐心等待…</div>
            </div>`;
        ov.style.display = 'flex';
        const t0 = Date.now();
        const elapsedEl = ov.querySelector('#petInstallElapsed');
        const stageEls = ov.querySelectorAll('.pet-install-stage');
        // 阶段推进：按经验时间点逐个点亮（真实后端是单次阻塞请求，这里给出诚实的「预期阶段」动画）
        let stage = 0;
        const markStage = (i) => stageEls.forEach((el, idx) => el.classList.toggle('active', idx <= i));
        markStage(0);
        ov._timer = setInterval(() => {
            const sec = (Date.now() - t0) / 1000;
            if (elapsedEl) elapsedEl.textContent = sec.toFixed(1) + 's';
            // 粗略推进阶段（2s/6s/12s 三个节点），最后一个阶段保留给真实完成
            const next = sec > 12 ? 2 : sec > 6 ? 2 : sec > 2 ? 1 : 0;
            if (next > stage) { stage = next; markStage(stage); }
        }, 100);
        return ov;
    }

    function finishInstallOverlay(ov, result) {
        if (!ov) return;
        clearInterval(ov._timer);
        const ok = result && result.ok;
        const d = (result && result.detail) || {};
        let body;
        if (ok) {
            const typeLabel = d.type === 'spritesheet'
                ? `立绘精灵图${d.sprite_version ? '（v' + d.sprite_version + '）' : ''}`
                : `${d.webm_count || result.webm_count || 0} 个 WebM 动画`;
            const poolLines = Object.entries(d.pool_counts || {})
                .map(([k, n]) => `<span class="pis-chip">${escapeHtml(k)} ${n}</span>`).join('');
            body = `
                <div class="pet-install-done ok">✓</div>
                <div class="pet-install-title">已安装「${escapeHtml(result.name || '')}」</div>
                <div class="pet-install-result">识别到：${typeLabel}</div>
                ${poolLines ? `<div class="pet-install-pools">${poolLines}</div>` : ''}
                <div class="pet-install-hint">已自动切换为当前桌宠，回主对话即可见</div>
                <button class="submit-btn" id="petInstallClose">完成</button>`;
        } else {
            body = `
                <div class="pet-install-done err">✕</div>
                <div class="pet-install-title">安装失败</div>
                <div class="pet-install-result err">${escapeHtml((result && (result.error || result.detail)) || '未知错误')}</div>
                <button class="submit-btn" id="petInstallClose">关闭</button>`;
        }
        ov.querySelector('.pet-install-card').innerHTML = body;
        const closeBtn = ov.querySelector('#petInstallClose');
        if (closeBtn) closeBtn.addEventListener('click', () => { ov.style.display = 'none'; });
    }

    async function installPet(gitUrl, petId, useAi) {
        if (!isLoggedIn()) { toast('请先登录'); return; }
        if (!gitUrl || !gitUrl.startsWith('http')) { marketTip('请输入有效的 git 链接', false); return; }
        const ov = showInstallOverlay(petId);
        let result = null;
        try {
            const res = await fetch(PetMarketAPI.install(), {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ git_url: gitUrl, pet_id: petId, use_ai: useAi }),
            });
            result = await res.json();
            if (!res.ok || !result.ok) {
                finishInstallOverlay(ov, result || { ok: false, error: '安装失败' });
                return;
            }
            finishInstallOverlay(ov, result);
            await loadPetMarket();
            // 自动切换到新安装的宠物
            if (result.pet_id) await switchPet(result.pet_id);
        } catch (err) {
            finishInstallOverlay(ov, { ok: false, error: (err && err.message) || '网络错误' });
        }
    }

    async function switchPet(petId) {
        if (!isLoggedIn()) { toast('请先登录'); return; }
        try {
            const res = await fetch(PetMarketAPI.switch(), {
                method: 'POST',
                headers: buildAuthHeaders(),
                body: JSON.stringify({ pet_id: petId }),
            });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error('切换失败');
            marketCurrentPet = petId;
            marketTip(`已切换，回到主对话刷新桌宠生效`);
            await loadPetMarket();
        } catch (err) { marketTip('切换失败', false); }
    }

    async function uninstallPet(petId) {
        if (!confirm('确定卸载这个宠物吗？')) return;
        try {
            const res = await fetch(PetMarketAPI.del(petId), { method: 'DELETE', headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error('卸载失败');
            marketTip('已卸载');
            await loadPetMarket();
        } catch (err) { marketTip('卸载失败', false); }
    }

    function initPetMarket() {
        const installBtn = document.getElementById('petMarketInstallBtn');
        const aiBtn = document.getElementById('petMarketAiInstallBtn');
        const input = document.getElementById('petMarketGitUrl');
        if (installBtn && input) installBtn.addEventListener('click', () => installPet(input.value.trim(), null, false));
        if (aiBtn && input) aiBtn.addEventListener('click', () => installPet(input.value.trim(), null, true));
        loadPetMarket();
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // ── 初始化 ──
    function init() {
        initCatTabs();
        initStatusTabs();
        initPetUpload();
        initPetMarket();
        initVoiceModal();
        document.getElementById('craftBtn').addEventListener('click', () => {
            location.href = '/chat/create/edit';
        });
        document.getElementById('importLinkBtn').addEventListener('click', importFromLink);
        loadCharacters();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
