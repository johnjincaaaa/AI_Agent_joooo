// ==============================
// 技能选择：指定 LLM 工具链
// ==============================

const SKILL_ICONS = {
    image: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
        <circle cx="8.5" cy="8.5" r="1.5"></circle>
        <polyline points="21 15 16 10 5 21"></polyline>
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

function getSkillIcon(iconKey) {
    return SKILL_ICONS[iconKey] || SKILL_ICONS.default;
}

function persistEnabledSkills() {
    localStorage.setItem('enabledSkills', JSON.stringify([...enabledSkills]));
}

function updateSkillsBtnLabel() {
    if (!skillsBtn) return;
    const count = enabledSkills.size;
    skillsBtn.classList.toggle('active', count > 0);
    const label = skillsBtn.querySelector('.skills-btn-label');
    if (label) {
        label.textContent = count > 0 ? `技能 · ${count}` : '技能';
    }
}

function renderSkillsList(skills) {
    if (!skillsList) return;
    skillsList.innerHTML = '';

    if (!skills.length) {
        skillsList.innerHTML = '<div class="skills-empty">暂无可用技能</div>';
        return;
    }

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

async function loadSkillsCatalog() {
    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/skills`);
        if (!res.ok) throw new Error('fetch skills failed');
        const data = await res.json();
        renderSkillsList(data.skills || []);
    } catch (err) {
        console.error('加载技能列表失败：', err);
        renderSkillsList([]);
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

window.getEnabledSkills = getEnabledSkills;
window.enableSkill = enableSkill;
