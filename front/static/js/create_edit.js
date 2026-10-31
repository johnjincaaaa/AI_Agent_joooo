/* Jingent 创作中心 · 捏小人编辑器 /chat/create/edit */
(function () {
    const API_BASE = (typeof config !== 'undefined' && config.API_BASE_URL) || '';
    const API_SAVE = `${API_BASE}/ai/create/characters`;
    const API_UPLOAD_IMAGE = `${API_BASE}/ai/upload-image`;
    const API_TTS_VOICES = `${API_BASE}/ai/tts/voices`;

    let editingNpcId = null;   // 编辑已有草稿时的 npc_id；新建为 null

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

    function $id(id) { return document.getElementById(id); }

    // ── 左侧 Tab 切换（联动右侧面板） ──
    function initCatTabs() {
        const tabs = document.querySelectorAll('#sideBar .sidebar-nav-item[data-cat]');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                const cat = tab.dataset.cat;
                $id('paneSoul').classList.toggle('active', cat === 'soul');
                $id('paneModel').classList.toggle('active', cat === 'model');
            });
        });
    }

    // ── 回显已有草稿（含分享链接导入） ──
    async function loadExisting() {
        const params = new URLSearchParams(location.search);
        const npcId = params.get('npc_id');
        if (!npcId) return;
        const wantImport = params.get('import') === '1';
        editingNpcId = npcId;
        $id('editTitle').textContent = '编辑小人';
        $id('editSub').textContent = `npc_id: ${npcId}`;

        // 分享导入：直接走 import 接口读取他人已通过审核的记忆体
        if (wantImport) {
            await importShared(npcId);
            return;
        }

        try {
            const res = await fetch(`${API_SAVE}/${npcId}`, { headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error('加载失败');
            fillForm(data.character);
        } catch (err) {
            // 加载失败（例如别人的记忆体，非本人草稿）→ 尝试按分享链接导入
            await importShared(npcId);
        }
    }

    // 通过分享链接导入：读取公开记忆体，作为新草稿填入表单
    async function importShared(npcId) {
        try {
            const res = await fetch(`${API_SAVE}/${npcId}/import`, { headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '导入失败');
            fillForm(data.character);
            editingNpcId = null;  // 导入的是新草稿，保存时重新生成自己的 npc_id
            $id('editTitle').textContent = '导入记忆体';
            $id('editSub').textContent = `来源 npc_id: ${npcId}`;
            toast('已导入，确认内容后保存即可成为你的记忆体');
        } catch (err) {
            toast('导入失败：' + (err.message || '该记忆体未通过审核或不存在'));
        }
    }

    function setSeg(containerId, value) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.querySelectorAll('button').forEach(b => {
            b.classList.toggle('active', b.dataset.value === value);
        });
    }
    function getSegValue(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return null;
        const active = container.querySelector('button.active');
        return active ? active.dataset.value : null;
    }

    function fillForm(c) {
        $id('inputName').value = c.name || '';
        $id('inputDesc').value = c.description || '';
        $id('inputPersona').value = c.persona || '';
        $id('inputOpening').value = c.opening || '';
        $id('inputRules').value = (c.rules || []).join('\n');
        $id('inputAppearance').value = c.appearance || '';
        $id('inputTags').value = (c.tags || []).join(', ');
        if (c.style) {
            setSeg('inputToneSeg', c.style.tone || 'normal');
            setSeg('inputMemeSeg', c.style.meme_frequency || 'normal');
            setSeg('inputMemorySeg', c.style.memory_sensitivity || 'high');
            if (c.style.active_topics !== undefined) $id('inputActive').checked = !!c.style.active_topics;
            else $id('inputActive').checked = true;
        }
        if (c.avatar) {
            $id('avatarPreview').innerHTML = `<img src="${c.avatar}" alt="avatar">`;
            $id('avatarPreview').dataset.url = c.avatar;
        }
        if (c.voice !== undefined) $id('inputVoice').dataset.saved = c.voice || '';
        syncPreview();
    }

    // ── 上传形象 ──
    function initAvatarUpload() {
        $id('uploadAvatarBtn').addEventListener('click', () => $id('avatarFileInput').click());
        $id('avatarFileInput').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;
            if (!isLoggedIn()) { toast('请先登录'); return; }
            const fd = new FormData();
            fd.append('file', file);
            try {
                const res = await fetch(API_UPLOAD_IMAGE, {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') },
                    body: fd,
                });
                const data = await res.json();
                if (!res.ok || data.code !== 200) throw new Error('上传失败');
                const url = data.url || data.path;
                $id('avatarPreview').innerHTML = `<img src="${url}" alt="avatar">`;
                // 存到隐藏字段（保存时读取）
                $id('avatarPreview').dataset.url = url;
                syncPreview();
                toast('形象已上传');
            } catch (err) {
                toast('上传失败');
            }
        });
    }

    // ── 音色加载（VoiceStudio 本地语音服务）──
    async function refreshVoices() {
        const tip = $id('voiceTip');
        const sel = $id('inputVoice');
        const saved = sel.dataset.saved || '';
        if (tip) tip.textContent = '正在加载音色…';
        try {
            const res = await fetch(API_TTS_VOICES, { headers: buildAuthHeaders() });
            const data = await res.json();
            if (!res.ok || !data.ok) throw new Error(data.detail || '加载失败');
            const voices = (data.voices || []).filter(v => v && v.type === 'profile');
            // 重建选项：默认 + profile 音色
            const cur = saved || sel.value || '';
            sel.innerHTML = '<option value="">默认音色</option>';
            voices.forEach(v => {
                const val = v.voice_id || v.id || v.name || '';
                if (!val) return;
                const opt = document.createElement('option');
                opt.value = val;
                opt.textContent = v.name || val;
                sel.appendChild(opt);
            });
            // 回显已保存的音色（若在列表里；否则临时追加一项保留值）
            if (cur) {
                if (![...sel.options].some(o => o.value === cur)) {
                    const opt = document.createElement('option');
                    opt.value = cur;
                    opt.textContent = cur;
                    sel.appendChild(opt);
                }
                sel.value = cur;
            }
            if (tip) tip.textContent = '音色已加载（' + voices.length + ' 个自定义音色）';
        } catch (err) {
            if (tip) tip.textContent = '音色服务不可用（未启动 VoiceStudio）';
            // 保底：回显已保存值
            if (saved) {
                const opt = document.createElement('option');
                opt.value = saved;
                opt.textContent = saved;
                sel.appendChild(opt);
                sel.value = saved;
            }
        }
    }

    function initVoice() {
        const btn = $id('refreshVoiceBtn');
        if (btn) btn.addEventListener('click', refreshVoices);
        refreshVoices();
    }

    // ── 保存草稿 ──
    function initSave() {
        $id('saveDraftBtn').addEventListener('click', async () => {
            if (!isLoggedIn()) { toast('请先登录'); return; }
            const name = $id('inputName').value.trim();
            if (!name) { toast('角色名称不能为空'); return; }

            const rules = $id('inputRules').value.split('\n').map(s => s.trim()).filter(Boolean);
            const tags = $id('inputTags').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
            const avatar = $id('avatarPreview').dataset.url || '';
            const payload = {
                npc_id: editingNpcId || undefined,
                name,
                description: $id('inputDesc').value.trim(),
                persona: $id('inputPersona').value.trim(),
                opening: $id('inputOpening').value.trim(),
                rules,
                style: {
                    tone: getSegValue('inputToneSeg') || 'normal',
                    meme_frequency: getSegValue('inputMemeSeg') || 'normal',
                    memory_sensitivity: getSegValue('inputMemorySeg') || 'high',
                    active_topics: $id('inputActive').checked,
                    short_sentences: true,
                },
                avatar,
                appearance: $id('inputAppearance').value.trim(),
                tags,
                voice: $id('inputVoice').value || '',
            };

            const btn = $id('saveDraftBtn');
            btn.disabled = true;
            try {
                const res = await fetch(API_SAVE, {
                    method: 'POST',
                    headers: buildAuthHeaders(),
                    body: JSON.stringify(payload),
                });
                const data = await res.json();
                if (!res.ok || !data.ok) throw new Error(data.detail || '保存失败');
                toast('已保存为草稿');
                if (!editingNpcId) {
                    editingNpcId = data.character.npc_id;
                    $id('editTitle').textContent = '编辑小人';
                    $id('editSub').textContent = `npc_id: ${editingNpcId}`;
                    // 更新 URL（不刷新，避免丢未保存内容）
                    history.replaceState(null, '', `/chat/create/edit?npc_id=${editingNpcId}`);
                }
                // 留在编辑页，2 秒后提示可返回列表
                setTimeout(() => toast('可点左上角「返回」查看列表'), 1200);
            } catch (err) {
                toast(err.message || '保存失败');
            } finally {
                btn.disabled = false;
            }
        });
    }

    // ── 实时预览：表单变动 → 预览卡片同步 ──
    const TONE_LABEL = { light: '清淡', normal: '自然', clingy: '黏人' };
    const MEME_LABEL = { low: '表情少', normal: '表情适中', high: '表情多' };

    function syncPreview() {
        const name = $id('inputName').value.trim();
        const desc = $id('inputDesc').value.trim();
        const opening = $id('inputOpening').value.trim();
        const tags = $id('inputTags').value.split(/[,，]/).map(s => s.trim()).filter(Boolean);
        const avatarUrl = $id('avatarPreview').dataset.url
            || ($id('avatarPreview').querySelector('img') && $id('avatarPreview').querySelector('img').src)
            || '';

        $id('pvName').textContent = name || '未命名小人';
        $id('pvDesc').textContent = desc || '这个人很懒，还没写简介';
        $id('pvOpening').textContent = opening || '你好呀，很高兴认识你～';

        // 头像（卡片 + 气泡）
        if (avatarUrl) {
            $id('pvAvatar').innerHTML = `<img src="${avatarUrl}" alt="avatar">`;
            $id('pvBubbleAvatar').innerHTML = `<img src="${avatarUrl}" alt="avatar">`;
        }

        // 标签
        $id('pvTags').innerHTML = tags.slice(0, 6)
            .map(t => `<span class="edit-preview-tag">${escapeHtml(t)}</span>`).join('');

        // 风格 chips（语气/表情频率/主动）
        const chips = [];
        const tone = getSegValue('inputToneSeg');
        if (tone && TONE_LABEL[tone]) chips.push(TONE_LABEL[tone]);
        const meme = getSegValue('inputMemeSeg');
        if (meme && MEME_LABEL[meme]) chips.push(MEME_LABEL[meme]);
        if ($id('inputActive').checked) chips.push('会主动找你');
        $id('pvChips').innerHTML = chips
            .map(c => `<span class="edit-preview-chip">${escapeHtml(c)}</span>`).join('');
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function initPreviewSync() {
        ['inputName', 'inputDesc', 'inputOpening', 'inputTags'].forEach(id => {
            const el = $id(id);
            if (el) el.addEventListener('input', syncPreview);
        });
        // seg / 开关变动也要刷新
        ['inputToneSeg', 'inputMemeSeg'].forEach(id => {
            const c = $id(id);
            if (c) c.addEventListener('click', () => setTimeout(syncPreview, 0));
        });
        const active = $id('inputActive');
        if (active) active.addEventListener('change', syncPreview);
        syncPreview();
    }

    // ── 人设参数 seg 选择器 ──
    function initParamSegs() {
        ['inputToneSeg', 'inputMemeSeg', 'inputMemorySeg'].forEach(id => {
            const container = document.getElementById(id);
            if (!container) return;
            container.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    container.querySelectorAll('button').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                });
            });
        });
    }

    // ── 初始化 ──
    function init() {
        initCatTabs();
        initAvatarUpload();
        initVoice();
        initSave();
        initParamSegs();
        initPreviewSync();
        loadExisting();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
