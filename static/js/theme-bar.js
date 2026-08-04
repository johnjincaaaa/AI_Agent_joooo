/* ========= Jingent AI 公共主题系统 & 顶部栏 ========= */

const THEME_CONFIG = {
    celadon:  { primary: '#7dd3c0', bg: '#1a2a28', name: '青瓷',  dot: '#7dd3c0' },
    cinnabar: { primary: '#c8523a', bg: '#2d1412', name: '朱砂',  dot: '#c8523a' },
    ink:      { primary: '#4ade80', bg: '#142818', name: '墨玉',  dot: '#4ade80' },
    azure:    { primary: '#3b82f6', bg: '#142030', name: '藏蓝',  dot: '#3b82f6' },
    amber:    { primary: '#eab308', bg: '#2a2410', name: '琥珀',  dot: '#eab308' },
    rouge:    { primary: '#dc2860', bg: '#3a1020', name: '胭脂',  dot: '#dc2860' },
    hammer:   { primary: '#ef4444', bg: '#2e1414', name: '锤子',  dot: '#ef4444' },
    apple:    { primary: '#007aff', bg: '#1c1c1e', name: '苹果',  dot: '#007aff' },
    sky:      { primary: '#0ea5e9', bg: '#102530', name: '晴空',  dot: '#0ea5e9' },
    neon:     { primary: '#ec4899', bg: '#2a1020', name: '霓虹港', dot: '#ec4899' },
};

// 从 hex 颜色派生一个更亮的同色系颜色（用于 sidebar / elevated / hover）
function lightenHex(hex, amount) {
    var r, g, b;
    if (hex.length === 7) {
        r = parseInt(hex.slice(1, 3), 16);
        g = parseInt(hex.slice(3, 5), 16);
        b = parseInt(hex.slice(5, 7), 16);
    } else {
        r = parseInt(hex.slice(1, 2) + hex.slice(1, 2), 16);
        g = parseInt(hex.slice(2, 3) + hex.slice(2, 3), 16);
        b = parseInt(hex.slice(3, 4) + hex.slice(3, 4), 16);
    }
    r = Math.min(255, r + amount);
    g = Math.min(255, g + amount);
    b = Math.min(255, b + amount);
    return '#' + [r, g, b].map(function(v) { return v.toString(16).padStart(2, '0'); }).join('');
}

const LANG_CONFIG = {
    'zh-CN': { flag: '🇨🇳', label: '简体中文' },
    'en':    { flag: '🇬🇧', label: 'English' },
};

function applyTheme(themeName) {
    const t = THEME_CONFIG[themeName] || THEME_CONFIG.cinnabar;
    const root = document.documentElement;

    // 主要 CSS 变量
    root.style.setProperty('--theme-primary', t.primary);
    root.style.setProperty('--theme-bg', t.bg);
    root.style.setProperty('--theme-dot', t.dot);
    root.style.setProperty('--theme-bg-alpha', t.primary);

    // 派生背景色：从 --theme-bg 逐层提亮，用于侧边栏、卡片、悬浮层
    root.style.setProperty('--theme-bg-sidebar', lightenHex(t.bg, 12));
    root.style.setProperty('--theme-bg-elevated', lightenHex(t.bg, 22));
    root.style.setProperty('--theme-bg-hover', lightenHex(t.bg, 35));

    // 更新 CSS 变量列表中的 --bg-*，让各组件自动跟随
    const isDark = document.documentElement.getAttribute('data-color-mode') !== 'light';
    if (isDark) {
        root.style.setProperty('--bg-app', t.bg);
        root.style.setProperty('--bg-chat', t.bg);
        root.style.setProperty('--bg-sidebar', lightenHex(t.bg, 12));
        root.style.setProperty('--bg-elevated', lightenHex(t.bg, 22));
        root.style.setProperty('--bg-hover', lightenHex(t.bg, 35));
        root.style.setProperty('--topbar-bg', lightenHex(t.bg, 18) + 'd9');
    }

    // 清除所有内联背景样式，让 CSS 变量接管
    document.body.style.cssText = (document.body.style.cssText || '').replace(/background[^;]*;?/gi, '');
    document.documentElement.style.cssText = (document.documentElement.style.cssText || '').replace(/background[^;]*;?/gi, '');

    // 暗主题：强制设置背景色（确保覆盖 CSS 中的硬编码值）
    if (isDark) {
        document.body.style.setProperty('background-color', t.bg, 'important');
        document.documentElement.style.setProperty('background-color', t.bg, 'important');
    }

    document.body.style.transition = 'background-color 0.5s ease, color 0.3s ease';

    // 主题切换组件里的点颜色（选择器里的第一个点，不是下拉里的）
    const themeDot = document.querySelector('#themeSelector > .theme-dot');
    if (themeDot) {
        themeDot.style.background = t.dot;
        themeDot.style.boxShadow = `0 0 8px ${t.dot}`;
        themeDot.style.transition = 'all 0.3s ease';
    }
    const themeNameEl = document.querySelector('#themeSelector > .theme-name');
    if (themeNameEl) themeNameEl.textContent = t.name;

    // 高亮当前
    document.querySelectorAll('.theme-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.theme === themeName);
    });

    localStorage.setItem('jingent_theme', themeName);
}

function applyLang(langKey) {
    const l = LANG_CONFIG[langKey] || LANG_CONFIG['zh-CN'];
    const langFlag = document.querySelector('.lang-selector .lang-flag');
    const langLabel = document.querySelector('.lang-selector .lang-label');
    if (langFlag) langFlag.textContent = l.flag;
    if (langLabel) langLabel.textContent = l.label;

    // 高亮当前
    document.querySelectorAll('.lang-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.lang === langKey);
    });

    localStorage.setItem('jingent_lang', langKey);

    // 如果有 i18n 系统就触发切换
    if (window.i18n && typeof window.i18n.setLocale === 'function') {
        window.i18n.setLocale(langKey);
    } else if (typeof window.setLang === 'function') {
        window.setLang(langKey);
    } else {
        // 尝试触发原 EN 按钮的点击事件
        const oldBtn = document.getElementById('langToggleBtn');
        if (oldBtn) {
            const target = langKey === 'en' ? 'EN' : '中文';
            if (oldBtn.textContent.trim() !== target) oldBtn.click();
        }
    }
}

function initThemeSystem() {
    const savedTheme = localStorage.getItem('jingent_theme') || 'cinnabar';
    applyTheme(savedTheme);

    // 主题切换按钮
    const ts = document.getElementById('themeSelector');
    const td = document.getElementById('themeDropdown');
    if (ts) {
        ts.addEventListener('click', (e) => {
            e.stopPropagation();
            td?.classList.toggle('show');
            document.getElementById('langDropdown')?.classList.remove('show');
        });
    }
    document.querySelectorAll('.theme-option').forEach(opt => {
        opt.addEventListener('click', (e) => {
            e.stopPropagation();
            applyTheme(opt.dataset.theme);
            td?.classList.remove('show');
        });
    });

    // 语言切换
    const ls = document.getElementById('langSelector');
    const ld = document.getElementById('langDropdown');
    if (ls) {
        ls.addEventListener('click', (e) => {
            e.stopPropagation();
            ld?.classList.toggle('show');
            document.getElementById('themeDropdown')?.classList.remove('show');
        });
    }
    document.querySelectorAll('.lang-option').forEach(opt => {
        opt.addEventListener('click', (e) => {
            e.stopPropagation();
            applyLang(opt.dataset.lang);
            ld?.classList.remove('show');
        });
    });

    document.addEventListener('click', () => {
        td?.classList.remove('show');
        ld?.classList.remove('show');
    });
}

// 顶部栏 HTML 模板
const TOP_BAR_HTML = `
<header class="top-bar">
    <div class="top-bar-left">
        <a href="/" class="top-bar-logo">
            <div class="logo-mark">
                <img src="../static/a.png" alt="Jingent AI">
            </div>
            <span class="logo-text">Jingent</span>
        </a>
    </div>
    <div class="top-bar-right">
        <div class="lang-selector" id="langSelector">
            <span class="lang-flag">🇨🇳</span>
            <span class="lang-label hidden-sm">简体中文</span>
            <svg class="chev-down" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
            <div class="lang-dropdown" id="langDropdown">
                <div class="lang-option active" data-lang="zh-CN">
                    <span class="lang-flag">🇨🇳</span>简体中文
                </div>
                <div class="lang-option" data-lang="en">
                    <span class="lang-flag">🇬🇧</span>English
                </div>
            </div>
        </div>
        <button class="brightness-btn" id="lightDarkBtn" title="切换亮/暗主题">
            <svg class="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
            </svg>
            <svg class="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none">
                <circle cx="12" cy="12" r="4"></circle>
                <line x1="12" y1="1" x2="12" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="23"></line>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
                <line x1="1" y1="12" x2="3" y2="12"></line>
                <line x1="21" y1="12" x2="23" y2="12"></line>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
            </svg>
        </button>
        <div class="theme-selector" id="themeSelector">
            <span class="theme-dot"></span>
            <span class="theme-name">朱砂</span>
            <svg class="chev-down" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
            <div class="theme-dropdown" id="themeDropdown">
                ${Object.entries(THEME_CONFIG).map(([k, v]) => `
                <div class="theme-option" data-theme="${k}">
                    <span class="theme-dot" style="--dot:${v.dot}"></span>${v.name}
                </div>`).join('')}
            </div>
        </div>
    </div>
</header>`;

function mountTopBar() {
    if (!document.getElementById('appTopBar')) {
        const wrapper = document.createElement('div');
        wrapper.id = 'appTopBar';
        wrapper.innerHTML = TOP_BAR_HTML;
        document.body.insertBefore(wrapper, document.body.firstChild);
    }
    // 给 body 加 class 便于调整 padding
    document.body.classList.add('has-top-bar');

    // 亮/暗主题切换
    const ldBtn = document.getElementById('lightDarkBtn');
    if (ldBtn) {
        const iconMoon = ldBtn.querySelector('.icon-moon');
        const iconSun = ldBtn.querySelector('.icon-sun');

        function applyLightDark(mode) {
            if (mode === 'light') {
                document.documentElement.setAttribute('data-color-mode', 'light');
                document.documentElement.setAttribute('data-theme', 'light');
                document.body.classList.add('light-mode');
                iconMoon.style.display = 'none';
                iconSun.style.display = '';
            } else {
                document.documentElement.setAttribute('data-color-mode', 'dark');
                document.documentElement.removeAttribute('data-theme');
                document.body.classList.remove('light-mode');
                iconMoon.style.display = '';
                iconSun.style.display = 'none';
            }
            localStorage.setItem('jingent_colormode', mode);
            // 同步旧系统的存储 key，避免冲突
            localStorage.setItem('app_theme', mode);
            // 重新应用主题色（暗主题时 body 背景需要跟随主题色）
            const savedTheme = localStorage.getItem('jingent_theme') || 'cinnabar';
            applyTheme(savedTheme);
            // 广播主题变更事件
            document.dispatchEvent(new CustomEvent('themechange', { detail: { theme: mode } }));
        }

        // 初始化
        const savedMode = localStorage.getItem('jingent_colormode') || 'dark';
        applyLightDark(savedMode);

        ldBtn.addEventListener('click', () => {
            const cur = localStorage.getItem('jingent_colormode') || 'dark';
            applyLightDark(cur === 'dark' ? 'light' : 'dark');
        });
    }

    initThemeSystem();

    // 初始化语言
    const savedLang = localStorage.getItem('jingent_lang') || 'zh-CN';
    setTimeout(() => applyLang(savedLang), 0);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountTopBar);
} else {
    mountTopBar();
}
