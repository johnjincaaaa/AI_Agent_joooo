// ==============================
// 找工作：个人画像 · 简历 · 岗位推荐
// ==============================

let isJobHuntMode = false;
let selectedTemplateId = 'classic';
let currentResume = '';

const PROFILE_FIELDS = [
    { key: 'name', label: '姓名', type: 'text', placeholder: '张三' },
    { key: 'gender', label: '性别', type: 'select', options: ['', '男', '女'] },
    { key: 'age', label: '年龄', type: 'text', placeholder: '24' },
    { key: 'education', label: '学历', type: 'select', options: ['', '大专', '本科', '硕士', '博士'] },
    { key: 'major', label: '专业', type: 'text', placeholder: '计算机科学与技术' },
    { key: 'school', label: '毕业院校', type: 'text', placeholder: 'XX大学' },
    { key: 'experience_years', label: '工作年限', type: 'select', options: ['', '在校/应届', '1-3年', '3-5年', '5-10年'] },
    { key: 'target_city', label: '期望城市', type: 'text', placeholder: '北京' },
    { key: 'target_role', label: '期望岗位', type: 'text', placeholder: 'Java开发工程师' },
    { key: 'skills', label: '技能标签', type: 'text', placeholder: 'Java,Spring Boot,MySQL', full: false },
    { key: 'work_experience', label: '工作经历', type: 'textarea', full: true, placeholder: '公司、岗位、时间、主要工作内容…' },
    { key: 'project_experience', label: '项目经历', type: 'textarea', full: true, placeholder: '项目名称、职责、技术栈、成果…' },
    { key: 'self_intro', label: '自我评价', type: 'textarea', full: true, placeholder: '简要介绍优势与求职动机…' },
    { key: 'preset_resume', label: '预设简历草稿（AI 将在此基础上完善）', type: 'textarea', full: true, placeholder: '可粘贴现有简历内容，AI 会自动润色补全…' },
];

function getProfileStorageKey() {
    const userId = localStorage.getItem('user_id');
    const username = localStorage.getItem('username');
    return `jobProfile_${userId || username || 'guest'}`;
}

function readProfileFromForm() {
    const profile = {};
    PROFILE_FIELDS.forEach(field => {
        const el = document.getElementById(`jobField_${field.key}`);
        profile[field.key] = el ? el.value.trim() : '';
    });
    return profile;
}

function fillProfileForm(profile) {
    PROFILE_FIELDS.forEach(field => {
        const el = document.getElementById(`jobField_${field.key}`);
        if (el && profile[field.key] !== undefined) {
            el.value = profile[field.key];
        }
    });
}

function saveProfileLocal(profile) {
    localStorage.setItem(getProfileStorageKey(), JSON.stringify({
        profile,
        template_id: selectedTemplateId,
        resume_content: currentResume,
    }));
}

function loadProfileLocal() {
    try {
        return JSON.parse(localStorage.getItem(getProfileStorageKey()) || '{}');
    } catch {
        return {};
    }
}

function buildAuthHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    const token = localStorage.getItem('token');
    if (token && token !== 'null') {
        headers['Authorization'] = 'Bearer ' + token;
    }
    return headers;
}

function isLoggedIn() {
    const token = localStorage.getItem('token');
    return token && token !== 'null';
}

function setJobStatus(elId, text, type = '') {
    const el = document.getElementById(elId);
    if (!el) return;
    el.textContent = text || '';
    el.className = 'job-status-tip' + (type ? ` ${type}` : '');
}

function renderProfileForm() {
    const container = document.getElementById('jobProfileForm');
    if (!container) return;

    container.innerHTML = PROFILE_FIELDS.map(field => {
        const fullClass = field.full ? 'job-field full-width' : 'job-field';
        let inputHtml = '';
        if (field.type === 'select') {
            inputHtml = `<select id="jobField_${field.key}">${field.options.map(opt =>
                `<option value="${opt}">${opt || '请选择'}</option>`).join('')}</select>`;
        } else if (field.type === 'textarea') {
            inputHtml = `<textarea id="jobField_${field.key}" placeholder="${field.placeholder || ''}"></textarea>`;
        } else {
            inputHtml = `<input id="jobField_${field.key}" type="text" placeholder="${field.placeholder || ''}">`;
        }
        return `<div class="${fullClass}"><label for="jobField_${field.key}">${field.label}</label>${inputHtml}</div>`;
    }).join('');
}

async function loadTemplates() {
    const grid = document.getElementById('jobTemplateGrid');
    if (!grid) return;

    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/job/templates`);
        const data = await res.json();
        const templates = data.templates || [];
        grid.innerHTML = templates.map(t => `
            <div class="template-card${selectedTemplateId === t.id ? ' selected' : ''}" data-template-id="${t.id}">
                <h4>${t.name}</h4>
                <p>${t.description}</p>
            </div>
        `).join('');

        grid.querySelectorAll('.template-card').forEach(card => {
            card.addEventListener('click', () => {
                selectedTemplateId = card.dataset.templateId;
                grid.querySelectorAll('.template-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                updateStepTags(2);
            });
        });
    } catch (err) {
        grid.innerHTML = '<p class="job-status-tip error">模板加载失败</p>';
    }
}

async function loadUserProfile() {
    const cached = loadProfileLocal();
    if (cached.profile) {
        fillProfileForm(cached.profile);
        selectedTemplateId = cached.template_id || 'classic';
        currentResume = cached.resume_content || '';
        renderResumePreview(currentResume);
    }

    if (!isLoggedIn()) return;

    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/job/profile`, {
            headers: buildAuthHeaders(),
        });
        if (res.status === 401) return;
        if (!res.ok) return;
        const data = await res.json();
        if (data.profile && Object.keys(data.profile).length) {
            fillProfileForm(data.profile);
            selectedTemplateId = data.template_id || selectedTemplateId;
            currentResume = data.resume_content || currentResume;
            renderResumePreview(currentResume);
            saveProfileLocal(data.profile);
        }
    } catch (err) {
        console.warn('加载云端画像失败', err);
    }
}

async function saveProfile() {
    const profile = readProfileFromForm();
    saveProfileLocal(profile);
    setJobStatus('jobSaveStatus', '已保存到本地', 'success');

    if (!isLoggedIn()) {
        setJobStatus('jobSaveStatus', '已保存到本地（登录后可同步云端）', 'success');
        return;
    }

    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/job/profile`, {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({
                profile,
                template_id: selectedTemplateId,
                resume_content: currentResume,
            }),
        });
        if (res.status === 401) {
            setJobStatus('jobSaveStatus', '登录已过期，仅保存到本地', 'error');
            return;
        }
        if (!res.ok) throw new Error('save failed');
        setJobStatus('jobSaveStatus', '已同步到云端', 'success');
    } catch {
        setJobStatus('jobSaveStatus', '云端同步失败，已保存到本地', 'error');
    }
}

function renderResumePreview(text) {
    const box = document.getElementById('jobResumePreview');
    if (!box) return;
    if (!text) {
        box.className = 'resume-preview empty';
        box.innerHTML = '点击「AI 完善简历」生成专业简历';
        return;
    }
    box.className = 'resume-preview';
    box.innerHTML = typeof renderMarkdown === 'function' ? renderMarkdown(text) : text;
}

async function generateResume() {
    const profile = readProfileFromForm();
    if (!profile.name && !profile.target_role && !profile.preset_resume) {
        setJobStatus('jobResumeStatus', '请至少填写姓名、期望岗位或预设简历草稿', 'error');
        return;
    }

    const btn = document.getElementById('jobGenerateBtn');
    btn.disabled = true;
    setJobStatus('jobResumeStatus', 'AI 正在完善简历，请稍候…');

    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/job/generate-resume`, {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({ profile, template_id: selectedTemplateId }),
        });
        if (res.status === 429) {
            setJobStatus('jobResumeStatus', '免费次数已用完，请登录后继续使用', 'error');
            return;
        }
        if (!res.ok) throw new Error('generate failed');
        const data = await res.json();
        currentResume = data.resume || '';
        renderResumePreview(currentResume);
        saveProfileLocal(profile);
        updateStepTags(3);
        setJobStatus('jobResumeStatus', '简历已生成', 'success');
    } catch (err) {
        setJobStatus('jobResumeStatus', '简历生成失败，请稍后重试', 'error');
        console.error(err);
    } finally {
        btn.disabled = false;
    }
}

function renderJobCards(jobs) {
    const list = document.getElementById('jobRecommendList');
    if (!list) return;

    if (!jobs.length) {
        list.innerHTML = '<p class="job-status-tip">暂无匹配岗位，请完善画像后重试</p>';
        return;
    }

    list.innerHTML = jobs.map(job => `
        <a class="job-card" href="${job.url}" target="_blank" rel="noopener noreferrer">
            <div class="job-card-top">
                <div class="job-card-title">
                    ${job.title}
                    <span class="job-source-badge">${job.source || 'BOSS直聘'}</span>
                </div>
                <div class="job-card-salary">${job.salary}</div>
            </div>
            <div class="job-card-company">${job.company}</div>
            <div class="job-card-meta">
                <span>${job.city}</span>
                <span>${job.experience}</span>
                <span>${job.education}</span>
            </div>
            <div class="job-card-tags">
                ${(job.tags || []).map(tag => `<span class="job-tag">${tag}</span>`).join('')}
            </div>
            <div class="job-match">
                <span class="job-match-score">匹配度 ${job.match_score}%</span>
                <span class="job-match-reason">${job.match_reason || ''}</span>
            </div>
        </a>
    `).join('');
}

async function matchJobs() {
    const profile = readProfileFromForm();
    if (!profile.target_role && !profile.skills) {
        setJobStatus('jobMatchStatus', '请填写期望岗位或技能标签', 'error');
        return;
    }

    const btn = document.getElementById('jobMatchBtn');
    btn.disabled = true;
    setJobStatus('jobMatchStatus', '正在匹配 BOSS 直聘岗位（虚拟数据）…');

    try {
        const res = await fetch(`${config.API_BASE_URL}/ai/job/match`, {
            method: 'POST',
            headers: buildAuthHeaders(),
            body: JSON.stringify({
                profile,
                resume_content: currentResume,
            }),
        });
        if (res.status === 429) {
            setJobStatus('jobMatchStatus', '免费次数已用完，请登录后继续使用', 'error');
            return;
        }
        if (!res.ok) throw new Error('match failed');
        const data = await res.json();
        renderJobCards(data.jobs || []);
        updateStepTags(4);
        setJobStatus('jobMatchStatus', `已推荐 ${(data.jobs || []).length} 个对口岗位`, 'success');
    } catch (err) {
        setJobStatus('jobMatchStatus', '岗位匹配失败，请稍后重试', 'error');
        console.error(err);
    } finally {
        btn.disabled = false;
    }
}

function updateStepTags(activeStep) {
    document.querySelectorAll('.job-step-tag').forEach((tag, index) => {
        const step = index + 1;
        tag.classList.remove('active', 'done');
        if (step < activeStep) tag.classList.add('done');
        if (step === activeStep) tag.classList.add('active');
    });
}

function enterJobHuntMode() {
    isJobHuntMode = true;

    document.querySelectorAll('.history.title').forEach(el => el.classList.remove('active'));
    document.getElementById('jobHuntEntry')?.classList.add('active');

    document.getElementById('chatSession').textContent = '找工作';
    document.querySelectorAll('#chatBox .message').forEach(el => el.remove());
    document.getElementById('emptyState')?.classList.add('hidden');

    if (typeof chatData !== 'undefined') chatData = [];
    if (typeof clearPendingAttachments === 'function') clearPendingAttachments();

    document.getElementById('chatBox')?.classList.add('hidden');
    document.getElementById('jobHuntPanel')?.classList.remove('hidden');
    document.querySelector('.input-area')?.classList.add('hidden');
    document.getElementById('scrollBottomBtn')?.classList.add('hidden');

    loadUserProfile();
    loadTemplates();
    updateStepTags(1);
}

function exitJobHuntMode() {
    if (!isJobHuntMode) return;
    isJobHuntMode = false;

    document.getElementById('jobHuntEntry')?.classList.remove('active');
    document.getElementById('jobHuntPanel')?.classList.add('hidden');
    document.getElementById('chatBox')?.classList.remove('hidden');
    document.querySelector('.input-area')?.classList.remove('hidden');
    document.getElementById('scrollBottomBtn')?.classList.remove('hidden');

    const hasMessages = document.querySelectorAll('#chatBox .message').length > 0;
    const emptyState = document.getElementById('emptyState');
    if (emptyState) {
        emptyState.classList.toggle('hidden', hasMessages);
    }
}

function initJobHunt() {
    renderProfileForm();

    document.getElementById('jobHuntEntry')?.addEventListener('click', enterJobHuntMode);
    document.getElementById('jobSaveProfileBtn')?.addEventListener('click', saveProfile);
    document.getElementById('jobGenerateBtn')?.addEventListener('click', generateResume);
    document.getElementById('jobMatchBtn')?.addEventListener('click', matchJobs);

    const cached = loadProfileLocal();
    if (cached.profile) {
        fillProfileForm(cached.profile);
        selectedTemplateId = cached.template_id || 'classic';
        currentResume = cached.resume_content || '';
    }
}

window.enterJobHuntMode = enterJobHuntMode;
window.exitJobHuntMode = exitJobHuntMode;
window.isJobHuntMode = () => isJobHuntMode;
window.refreshJobProfile = loadUserProfile;

document.addEventListener('DOMContentLoaded', initJobHunt);
