// ==============================
// 技能选择：指定 LLM 工具链
// ==============================

const SKILL_ICONS = {
    image: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <circle cx="8.5" cy="8.5" r="1.5"></circle>
        <polyline points="21 15 16 10 5 21"></polyline>
    </svg>`,
    document: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
    </svg>`,
    globe: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
    </svg>`,
    mail: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
        <polyline points="22,6 12,13 2,6"></polyline>
    </svg>`,
    clipboard: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
        <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
    </svg>`,
    'file-text': `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line>
        <line x1="10" y1="9" x2="8" y2="9"></line>
    </svg>`,
    pen: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 19l7-7 3 3-7 7-3-3z"></path><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path>
        <path d="M2 2l7.586 7.586"></path><circle cx="11" cy="11" r="2"></circle>
    </svg>`,
    sparkles: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 3l1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2z"></path>
        <path d="M19 3l.9 2.7L23 7l-3.1 1.3L19 11l-.9-2.7L15 7l3.1-1.3z"></path>
        <path d="M5 15l.6 1.8L8 18l-2.4.8L5 21l-.6-2.2L2 18l2.4-.8z"></path>
    </svg>`,
    video: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="23 7 16 12 23 17 23 7"></polygon>
        <rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect>
    </svg>`,
    book: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
    </svg>`,
    target: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="6"></circle>
        <circle cx="12" cy="12" r="2"></circle>
    </svg>`,
    'message-circle': `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
    </svg>`,
    code: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>
    </svg>`,
    database: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
    </svg>`,
    search: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </svg>`,
    chef: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 13.87A4 4 0 0 1 7.41 6a5.11 5.11 0 0 1 1.05-1.54 5 5 0 0 1 7.08 0A5.11 5.11 0 0 1 16.59 6 4 4 0 0 1 18 13.87V21H6Z"></path>
        <line x1="6" y1="17" x2="18" y2="17"></line>
    </svg>`,
    map: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>
        <line x1="8" y1="2" x2="8" y2="18"></line><line x1="16" y1="6" x2="16" y2="22"></line>
    </svg>`,
    dumbbell: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6.5 6.5l11 11"></path><path d="M21 21l-1-1"></path><path d="M3 3l1 1"></path>
        <path d="M18 22l4-4"></path><path d="M2 6l4-4"></path>
        <path d="M3 10l7-7"></path><path d="M14 21l7-7"></path>
    </svg>`,
    heart: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
    </svg>`,
    moon: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
    </svg>`,
    default: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>
    </svg>`,
};

const skillsBtn = document.getElementById('skillsBtn');
const skillsDropdown = document.getElementById('skillsDropdown');
const skillsList = document.getElementById('skillsList');

/** @type {Set<string>} */
const enabledSkills = new Set(
    JSON.parse(localStorage.getItem('enabledSkills') || '[]')
);

// 已安装的自定义技能（从 localStorage 加载）
let installedSkills = JSON.parse(localStorage.getItem('installedSkills') || '[]');

function getSkillIcon(iconKey) {
    return SKILL_ICONS[iconKey] || SKILL_ICONS.default;
}

function persistEnabledSkills() {
    localStorage.setItem('enabledSkills', JSON.stringify([...enabledSkills]));
}

function persistInstalledSkills() {
    localStorage.setItem('installedSkills', JSON.stringify(installedSkills));
}

function updateSkillsBtnLabel() {
    if (!skillsBtn) return;
    const count = enabledSkills.size;
    skillsBtn.classList.toggle('active', count > 0);
    const label = skillsBtn.querySelector('.skills-btn-label');
    if (label) {
        label.textContent = count > 0 ? `${t('skills_btn')} · ${count}` : t('skills_btn');
    }
}

function renderSkillsList(skills) {
    if (!skillsList) return;
    skillsList.innerHTML = '';

    if (!skills.length) {
        skillsList.innerHTML = `<div class="skills-empty">${t('skills_empty')}</div>`;
        return;
    }

    // 添加「技能市场」入口
    const marketEntry = document.createElement('button');
    marketEntry.type = 'button';
    marketEntry.className = 'skills-item skills-market-entry';
    marketEntry.innerHTML = `
        <span class="skills-item-icon">${getSkillIcon('sparkles')}</span>
        <span class="skills-item-text">
            <span class="skills-item-name">${t('skills_market') || '技能市场'}</span>
            <span class="skills-item-desc">${t('skills_market_desc') || '发现更多技能，一键安装使用'}</span>
        </span>
        <span class="skills-item-arrow" aria-hidden="true">›</span>
    `;
    marketEntry.addEventListener('click', (e) => {
        e.stopPropagation();
        openSkillMarket();
    });
    skillsList.appendChild(marketEntry);

    // 分隔线
    const divider = document.createElement('div');
    divider.className = 'skills-divider';
    skillsList.appendChild(divider);

    skills.forEach(skill => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'skills-item' + (enabledSkills.has(skill.id) ? ' selected' : '');
        item.dataset.skillId = skill.id;
        item.title = skill.description || skill.name;
        item.innerHTML = `
            <span class="skills-item-icon">${getSkillIcon(skill.icon)}</span>
            <span class="skills-item-text">
                <span class="skills-item-name">${skill.name}</span>
                ${skill.description ? `<span class="skills-item-desc">${skill.description}</span>` : ''}
            </span>
            <span class="skills-item-check" aria-hidden="true">✓</span>
        `;
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSkill(skill.id, item);
        });
        skillsList.appendChild(item);
    });
}

function toggleSkill(skillId, itemEl) {
    if (enabledSkills.has(skillId)) {
        enabledSkills.delete(skillId);
        itemEl?.classList.remove('selected');
    } else {
        enabledSkills.add(skillId);
        itemEl?.classList.add('selected');
    }
    persistEnabledSkills();
    updateSkillsBtnLabel();
}

function buildFallbackSkills() {
    return [
        {
            id: 'image_parsing',
            name: t('skill_image_name'),
            description: t('skill_image_desc'),
            icon: 'image',
            category: '工具类',
            type: 'tool',
        },
        {
            id: 'document_parsing',
            name: t('skill_doc_name'),
            description: t('skill_doc_desc'),
            icon: 'document',
            category: '工具类',
            type: 'tool',
        },
        ...installedSkills,
    ];
}

// 已知内置技能的本地化映射
const SKILL_I18N = {
    image_parsing: { name: 'skill_image_name', desc: 'skill_image_desc' },
    document_parsing: { name: 'skill_doc_name', desc: 'skill_doc_desc' },
};

function localizeSkill(skill) {
    const map = SKILL_I18N[skill.id];
    if (!map) return skill;
    return { ...skill, name: t(map.name), description: t(map.desc) };
}

// 记住最近一次技能目录，语言切换时重新渲染
let lastSkills = [];

function mergeSkills(apiSkills) {
    const map = new Map();
    [...buildFallbackSkills(), ...(apiSkills || [])].forEach(skill => {
        map.set(skill.id, skill);
    });
    return [...map.values()].map(localizeSkill);
}

async function loadSkillsCatalog() {
    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/skills`);
        if (!res.ok) throw new Error('fetch skills failed');
        const data = await res.json();
        lastSkills = mergeSkills(data.skills || []);
        renderSkillsList(lastSkills);
    } catch (err) {
        console.error('加载技能列表失败：', err);
        lastSkills = buildFallbackSkills().map(localizeSkill);
        renderSkillsList(lastSkills);
    }
    updateSkillsBtnLabel();
}

function getEnabledSkills() {
    return [...enabledSkills];
}

function enableSkill(skillId) {
    if (enabledSkills.has(skillId)) return;
    enabledSkills.add(skillId);
    persistEnabledSkills();
    updateSkillsBtnLabel();
    const item = skillsList?.querySelector(`[data-skill-id="${skillId}"]`);
    item?.classList.add('selected');
}

// ============================================
// 技能包导入
// ============================================
let skillImportModal = null;
let previewSkillData = null;

function openSkillImport() {
    buildSkillImportModal();
    skillImportModal.classList.add('show');
}

function closeSkillImport() {
    skillImportModal?.classList.remove('show');
    previewSkillData = null;
}

function buildSkillImportModal() {
    if (skillImportModal) return;
    skillImportModal = document.createElement('div');
    skillImportModal.className = 'skill-market-overlay skill-import-overlay';
    skillImportModal.innerHTML = `
        <div class="skill-market-modal skill-import-modal">
            <div class="skill-market-header">
                <div class="skill-market-title">${t('skills_import_title') || '导入技能包'}</div>
                <button class="skill-market-close" id="skillImportClose">×</button>
            </div>
            <div class="skill-import-body">
                <div class="skill-import-drop" id="skillImportDrop">
                    <div class="skill-import-drop-icon">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" y1="3" x2="12" y2="15"></line>
                        </svg>
                    </div>
                    <div class="skill-import-drop-title">${t('skills_import_drop') || '点击或拖拽 zip 包到这里'}</div>
                    <div class="skill-import-drop-desc">${t('skills_import_support') || '支持 .zip 格式，含 skill.json 或 SKILL.md'}</div>
                    <input type="file" id="skillImportFile" accept=".zip" hidden>
                </div>
                <div class="skill-import-preview" id="skillImportPreview" style="display:none;"></div>
            </div>
            <div class="skill-import-footer" id="skillImportFooter" style="display:none;">
                <button class="skill-import-btn cancel" id="skillImportCancel">${t('cancel') || '取消'}</button>
                <button class="skill-import-btn confirm" id="skillImportConfirm">${t('skills_install_confirm') || '安装技能'}</button>
            </div>
        </div>
    `;
    document.body.appendChild(skillImportModal);

    skillImportModal.addEventListener('click', (e) => {
        if (e.target === skillImportModal) closeSkillImport();
    });
    skillImportModal.querySelector('#skillImportClose').addEventListener('click', closeSkillImport);

    const dropArea = skillImportModal.querySelector('#skillImportDrop');
    const fileInput = skillImportModal.querySelector('#skillImportFile');

    dropArea.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) handleSkillFile(e.target.files[0]);
    });

    // 拖拽支持
    ['dragenter', 'dragover'].forEach(ev => {
        dropArea.addEventListener(ev, (e) => {
            e.preventDefault();
            dropArea.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach(ev => {
        dropArea.addEventListener(ev, (e) => {
            e.preventDefault();
            dropArea.classList.remove('dragover');
        });
    });
    dropArea.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file) handleSkillFile(file);
    });

    skillImportModal.querySelector('#skillImportCancel').addEventListener('click', closeSkillImport);
    skillImportModal.querySelector('#skillImportConfirm').addEventListener('click', installUploadedSkill);
}

async function handleSkillFile(file) {
    if (!file.name.endsWith('.zip')) {
        alert(t('skills_import_invalid') || '请上传 zip 格式的技能包');
        return;
    }

    const preview = document.getElementById('skillImportPreview');
    const dropArea = document.getElementById('skillImportDrop');
    const footer = document.getElementById('skillImportFooter');

    // 显示加载中
    dropArea.style.display = 'none';
    preview.style.display = 'block';
    preview.innerHTML = `<div class="skill-import-loading">${t('loading') || '解析中...'}</div>`;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`${config.API_BASE_URL}/ai/skills/preview`, {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (data.code === 200 && data.valid) {
            previewSkillData = data.skill;
            preview.innerHTML = renderSkillPreview(data.skill);
            footer.style.display = 'flex';
        } else {
            preview.innerHTML = `<div class="skill-import-error">
                <div class="error-icon">!</div>
                <div>${t('skills_import_error') || '解析失败'}：${data.error || '未知错误'}</div>
                <button class="skill-import-retry" id="skillImportRetry">${t('retry') || '重新选择'}</button>
            </div>`;
            footer.style.display = 'none';
            preview.querySelector('#skillImportRetry').addEventListener('click', resetImportView);
        }
    } catch (e) {
        preview.innerHTML = `<div class="skill-import-error">
            <div class="error-icon">!</div>
            <div>${t('skills_import_net_error') || '网络错误，请重试'}</div>
            <button class="skill-import-retry" id="skillImportRetry">${t('retry') || '重新选择'}</button>
        </div>`;
        footer.style.display = 'none';
        preview.querySelector('#skillImportRetry').addEventListener('click', resetImportView);
    }
}

function resetImportView() {
    const preview = document.getElementById('skillImportPreview');
    const dropArea = document.getElementById('skillImportDrop');
    const footer = document.getElementById('skillImportFooter');
    const fileInput = document.getElementById('skillImportFile');
    dropArea.style.display = 'flex';
    preview.style.display = 'none';
    footer.style.display = 'none';
    if (fileInput) fileInput.value = '';
    previewSkillData = null;
}

function renderSkillPreview(skill) {
    return `
        <div class="skill-preview-card">
            <div class="skill-preview-icon">${getSkillIcon(skill.icon)}</div>
            <div class="skill-preview-name">${skill.name}</div>
            <div class="skill-preview-meta">
                ${skill.version ? `<span class="skill-meta-item">v${skill.version}</span>` : ''}
                ${skill.author ? `<span class="skill-meta-item">${skill.author}</span>` : ''}
                <span class="skill-meta-item">${skill.category || '其他'}</span>
            </div>
            ${skill.description ? `<div class="skill-preview-desc">${skill.description}</div>` : ''}
            ${skill.tags && skill.tags.length ? `<div class="skill-preview-tags">${skill.tags.map(t => `<span class="skill-tag">${t}</span>`).join('')}</div>` : ''}
            <div class="skill-preview-prompt-title">${t('skills_preview_prompt') || '系统提示词预览'}：</div>
            <div class="skill-preview-prompt">${skill.systemPrompt ? skill.systemPrompt.slice(0, 300) + (skill.systemPrompt.length > 300 ? '...' : '') : (t('skills_no_prompt') || '无')}</div>
        </div>
    `;
}

async function installUploadedSkill() {
    const fileInput = document.getElementById('skillImportFile');
    if (!fileInput?.files[0]) return;

    const confirmBtn = document.getElementById('skillImportConfirm');
    const originalText = confirmBtn.textContent;
    confirmBtn.disabled = true;
    confirmBtn.textContent = t('installing') || '安装中...';

    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        const res = await fetch(`${config.API_BASE_URL}/ai/skills/install`, {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (data.code === 200) {
            const skill = data.skill;
            // 更新已安装列表
            const existingIdx = installedSkills.findIndex(s => s.id === skill.id);
            if (existingIdx >= 0) {
                installedSkills[existingIdx] = skill;
            } else {
                installedSkills.push(skill);
            }
            persistInstalledSkills();
            await loadSkillsCatalog();
            enableSkill(skill.id);

            closeSkillImport();
            resetImportView();
            closeSkillMarket();
            alert(`${skill.name} ${t('skills_installed') || '安装成功，已自动启用！'}`);
        } else {
            alert(`${t('skills_install_failed') || '安装失败'}：${data.error || '未知错误'}`);
        }
    } catch (e) {
        alert(t('skills_import_net_error') || '网络错误，请重试');
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.textContent = originalText;
    }
}

// ============================================
// 技能市场
// ============================================
let marketSkills = [];
let skillMarketModal = null;

async function openSkillMarket() {
    skillsDropdown?.classList.remove('open');
    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/skills/market`);
        const data = await res.json();
        if (data.code === 200) {
            marketSkills = data.market || [];
        }
    } catch (e) {
        console.error('加载技能市场失败:', e);
    }
    buildSkillMarketModal();
    skillMarketModal.classList.add('show');
}

function closeSkillMarket() {
    skillMarketModal?.classList.remove('show');
}

function buildSkillMarketModal() {
    if (skillMarketModal) return;
    skillMarketModal = document.createElement('div');
    skillMarketModal.className = 'skill-market-overlay';
    skillMarketModal.innerHTML = `
        <div class="skill-market-modal">
            <div class="skill-market-header">
                <div class="skill-market-title">${t('skills_market_title') || '技能市场'}</div>
                <div class="skill-market-header-actions">
                    <button class="skill-market-import-btn" id="skillImportBtn">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                            <polyline points="17 8 12 3 7 8"></polyline>
                            <line x1="12" y1="3" x2="12" y2="15"></line>
                        </svg>
                        ${t('skills_import') || '导入技能包'}
                    </button>
                    <button class="skill-market-close" id="skillMarketClose">×</button>
                </div>
            </div>
            <div class="skill-market-cats" id="skillMarketCats"></div>
            <div class="skill-market-grid" id="skillMarketGrid"></div>
        </div>
    `;
    document.body.appendChild(skillMarketModal);

    skillMarketModal.addEventListener('click', (e) => {
        if (e.target === skillMarketModal) closeSkillMarket();
    });
    skillMarketModal.querySelector('#skillMarketClose').addEventListener('click', closeSkillMarket);
    skillMarketModal.querySelector('#skillImportBtn').addEventListener('click', openSkillImport);
}

let currentMarketCat = 'all';

function renderSkillMarket() {
    const grid = document.getElementById('skillMarketGrid');
    const cats = document.getElementById('skillMarketCats');
    if (!grid || !marketSkills.length) return;

    // 按分类分组
    const categories = {};
    marketSkills.forEach(s => {
        const cat = s.category || '其他';
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push(s);
    });

    // 渲染分类标签
    const allCats = ['all', ...Object.keys(categories)];
    cats.innerHTML = allCats.map(cat => `
        <button class="skill-market-cat ${currentMarketCat === cat ? 'active' : ''}" data-cat="${cat}">
            ${cat === 'all' ? (t('skills_all') || '全部') : cat}
        </button>
    `).join('');
    cats.querySelectorAll('.skill-market-cat').forEach(btn => {
        btn.addEventListener('click', () => {
            currentMarketCat = btn.dataset.cat;
            renderSkillMarket();
        });
    });

    // 渲染技能卡片
    const list = currentMarketCat === 'all'
        ? marketSkills
        : categories[currentMarketCat] || [];

    const installedIds = new Set([
        'image_parsing', 'document_parsing',
        ...installedSkills.map(s => s.id),
    ]);

    grid.innerHTML = list.map(skill => {
        const isInstalled = installedIds.has(skill.id);
        const isEnabled = enabledSkills.has(skill.id);
        return `
            <div class="skill-market-card" data-skill-id="${skill.id}">
                <div class="skill-market-card-icon">${getSkillIcon(skill.icon)}</div>
                <div class="skill-market-card-name">${skill.name}</div>
                <div class="skill-market-card-desc">${skill.description || ''}</div>
                ${skill.tags && skill.tags.length ? `<div class="skill-market-card-tags">${skill.tags.slice(0,3).map(tg => `<span class="skill-tag">${tg}</span>`).join('')}</div>` : ''}
                <div class="skill-market-card-actions">
                    ${isInstalled
                        ? `<button class="skill-market-btn ${isEnabled ? 'active' : ''}" data-action="${isEnabled ? 'disable' : 'enable'}">${isEnabled ? (t('skills_enabled') || '已启用') : (t('skills_enable') || '启用')}</button>`
                        : `<button class="skill-market-btn install" data-action="install">${t('skills_install') || '安装'}</button>`
                    }
                </div>
            </div>
        `;
    }).join('');

    grid.querySelectorAll('.skill-market-card').forEach(card => {
        const btn = card.querySelector('.skill-market-btn');
        if (!btn) return;
        btn.addEventListener('click', () => {
            const skillId = card.dataset.skillId;
            const action = btn.dataset.action;
            const skill = marketSkills.find(s => s.id === skillId);
            if (!skill) return;

            if (action === 'install') {
                installedSkills.push(skill);
                persistInstalledSkills();
                loadSkillsCatalog();
                enableSkill(skillId);
            } else if (action === 'enable') {
                enableSkill(skillId);
            } else if (action === 'disable') {
                enabledSkills.delete(skillId);
                persistEnabledSkills();
                updateSkillsBtnLabel();
            }
            renderSkillMarket();
        });
    });
}

// 覆写 openSkillMarket，在打开时渲染
const _openSkillMarket = openSkillMarket;
openSkillMarket = async function() {
    await _openSkillMarket();
    currentMarketCat = 'all';
    renderSkillMarket();
};

if (skillsBtn && skillsDropdown) {
    skillsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        skillsDropdown.classList.toggle('open');
    });

    document.addEventListener('click', () => {
        skillsDropdown.classList.remove('open');
    });

    skillsDropdown.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    loadSkillsCatalog();
}

// 语言切换时重新渲染技能名与按钮标签
document.addEventListener('langchange', () => {
    lastSkills = lastSkills.map(localizeSkill);
    renderSkillsList(lastSkills);
    updateSkillsBtnLabel();
});

window.getEnabledSkills = getEnabledSkills;
window.enableSkill = enableSkill;
