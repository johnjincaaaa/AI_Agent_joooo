/**
 * Jinclaw Agent — TRAE-style three-panel agent
 * Data: Project (workspace folder) → Tasks (conversations with nicknames)
 */
/* global marked, config */

// ── 默认浏览器空白占位页（黑色背景 + 有趣 CSS/SVG 动画 + 文案）────────────────────────────────
// 单源 HTML，静态 browserFrame-0 和动态新建 iframe 都用同一个 encode 后的 dataURL
const BLANK_BROWSER_HTML = `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>about:blank · Jinclaw</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%;width:100%;background:#000;color:#cdd6f4;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;-webkit-font-smoothing:antialiased}
  .stage{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px;padding:32px;text-align:center}
  /* ——— 动画 1：AI 思考球（12 个像素块组成的旋转环 + 逐块高亮）——— */
  .brain{position:relative;width:120px;height:120px}
  .brain .ring{position:absolute;inset:0;animation:brSpin 6.4s linear infinite}
  .brain .dot{position:absolute;left:50%;top:50%;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:3px;background:#181825;border:1px solid rgba(137,180,250,.22)}
  .brain .dot.on{background:linear-gradient(135deg,#89b4fa,#cba6f7);border-color:transparent;box-shadow:0 0 18px rgba(137,180,250,.65)}
  @keyframes brSpin{to{transform:rotate(360deg)}}
  /* ——— 动画 2：脉冲核心 ——— */
  .core{position:absolute;left:50%;top:50%;width:38px;height:38px;margin:-19px 0 0 -19px;border-radius:50%;
    background:radial-gradient(circle at 35% 30%,#f5c2e7 0%,#cba6f7 40%,#89b4fa 100%);
    filter:blur(1px);animation:brPulse 1.8s ease-in-out infinite}
  .core::after{content:"";position:absolute;inset:-10px;border-radius:50%;
    background:radial-gradient(circle,rgba(137,180,250,.28),transparent 70%);
    animation:brHalo 1.8s ease-in-out infinite}
  @keyframes brPulse{0%,100%{transform:scale(.86);opacity:.75}50%{transform:scale(1.08);opacity:1}}
  @keyframes brHalo{0%,100%{transform:scale(.8);opacity:.5}50%{transform:scale(1.35);opacity:.08}}
  /* ——— 文案 ——— */
  .title{font-size:17px;letter-spacing:.02em;color:#cdd6f4}
  .title b{background:linear-gradient(135deg,#89b4fa,#cba6f7 55%,#f5c2e7);-webkit-background-clip:text;background-clip:text;color:transparent}
  .sub{font-size:12.5px;color:#6c7086;margin-top:-6px}
  /* ——— 动画 3：打字指示 ——— */
  .dots{display:inline-flex;gap:8px;margin-top:4px}
  .dots i{display:block;width:8px;height:8px;border-radius:50%;background:#89b4fa;opacity:.25;
    animation:brDot 1.4s ease-in-out infinite;
    box-shadow:0 0 10px rgba(137,180,250,.4)}
  .dots i:nth-child(2){animation-delay:.2s;background:#cba6f7;box-shadow:0 0 10px rgba(203,166,247,.4)}
  .dots i:nth-child(3){animation-delay:.4s;background:#f5c2e7;box-shadow:0 0 10px rgba(245,194,231,.4)}
  @keyframes brDot{0%,80%,100%{transform:translateY(0) scale(.8);opacity:.25}40%{transform:translateY(-5px) scale(1.15);opacity:1}}
  /* ——— 动画 4：背景流星 ——— */
  .bg{position:absolute;inset:0;overflow:hidden;pointer-events:none}
  .shoot{position:absolute;top:50%;left:-20%;width:160px;height:1px;
    background:linear-gradient(90deg,transparent,rgba(137,180,250,.7),transparent);
    transform:rotate(18deg);animation:brShoot 3.8s ease-in infinite;opacity:0}
  .shoot.s2{top:22%;animation-delay:1.3s;width:220px;
    background:linear-gradient(90deg,transparent,rgba(203,166,247,.55),transparent)}
  .shoot.s3{top:78%;animation-delay:2.5s;width:130px;
    background:linear-gradient(90deg,transparent,rgba(245,194,231,.6),transparent)}
  @keyframes brShoot{0%{transform:translateX(-10%) rotate(18deg);opacity:0}10%{opacity:1}70%{opacity:.6}100%{transform:translateX(130%) rotate(18deg);opacity:0}}
</style>
</head>
<body>
  <div class="bg">
    <div class="shoot"></div><div class="shoot s2"></div><div class="shoot s3"></div>
  </div>
  <div class="stage">
    <div class="brain" aria-hidden="true">
      <div class="core"></div>
      <div class="ring" id="ring"></div>
    </div>
    <div class="title"><b>暂无网页预览</b>，让 AI 生成一些内容看看吧！</div>
    <div class="sub">prompt 一句话 → HTML / React / Vue 直接在右边渲染</div>
    <div class="dots" aria-hidden="true"><i></i><i></i><i></i></div>
  </div>
<script>
  // 生成 12 个点按 30° 分布，并做逐块流水点亮（不依赖任何外部库）
  (function(){
    var ring=document.getElementById('ring');
    var i=0, N=12, frag=document.createDocumentFragment();
    for(;i<N;i++){
      var d=document.createElement('div');d.className='dot';
      var r=46;
      var a=i*(360/N)*Math.PI/180;
      d.style.transform='translate('+(Math.cos(a)*r).toFixed(2)+'px,'+(Math.sin(a)*r).toFixed(2)+'px)';
      d.dataset.i=i;
      frag.appendChild(d);
    }
    ring.appendChild(frag);
    var dots=ring.children;
    var cur=0;
    setInterval(function(){
      for(var j=0;j<dots.length;j++) dots[j].classList.remove('on');
      dots[cur%dots.length].classList.add('on');
      dots[(cur+1)%dots.length].classList.add('on');
      dots[(cur+11)%dots.length].classList.add('on');
      cur++;
    }, 220);
  })();
</script>
</body>
</html>`;
const BLANK_BROWSER_SRC = 'data:text/html;charset=utf-8,' + encodeURIComponent(BLANK_BROWSER_HTML);

var API = {
    chat:    config.API_BASE_URL + '/ai/jinclaw/chat',
    projects:config.API_BASE_URL + '/ai/jinclaw/projects',
    tasks:   config.API_BASE_URL + '/ai/jinclaw/tasks',
    diffs:   config.API_BASE_URL + '/ai/jinclaw/diffs',
    wsTree:  config.API_BASE_URL + '/ai/jinclaw/workspace/tree',
    wsRead:  config.API_BASE_URL + '/ai/jinclaw/workspace/read',
    wsFsAction: config.API_BASE_URL + '/ai/jinclaw/workspace/fs_action',
    shell:   config.API_BASE_URL + '/ai/jinclaw/shell',
    chatRename: config.API_BASE_URL + '/ai/chat',
};

// 构造 auth header：优先用 chat 页约定的 localStorage key `token`，再兜底 jinclaw 自有的 jingent_token / auth_token / jingent_session
function _authHeaders() {
    var out = {};
    var tok = null;
    try {
        tok = tok || localStorage.getItem('token');          // chat.js / LoginRegister.js 写入的主 token（全项目通用）
        tok = tok || localStorage.getItem('jingent_token');  // jinclaw 内嵌登录写入
        tok = tok || localStorage.getItem('auth_token');     // 后端 cookie 同步 fallback（非 http-only）
        tok = tok || localStorage.getItem('jingent_session');
    } catch(_) {}
    if (tok) { out['Authorization'] = 'Bearer ' + tok; }
    out['X-Requested-With'] = 'XMLHttpRequest';
    return out;
}

var S = {
    isDesktop: false,
    currentProjectId: null,
    currentTaskId: null,
    chatHistory: [],
    isSending: false,
    openFiles: [],
    currentTab: 'chat',
    currentPrev: 'browser-0',
    browserTabCount: 1,
    termHistory: [], termHistoryIdx: -1,
    planItems: [],          // current plan steps
    planStepIndex: -1,       // which step is currently executing
    lastTaskId: null,
    lastProjectId: null,
    terminalCdMap: {},       // idx -> cwd, to track cd across commands
};

// ── Init ───────────────────────────────────────────────────
function init() {
    var params = new URLSearchParams(location.search);
    S.isDesktop = params.get('is_desktop') === '1';
    if (!S.isDesktop) {
        document.getElementById('lockScreen').style.display = '';
        return;
    }
    document.getElementById('lockScreen').style.display = 'none';
    document.getElementById('appShell').style.display = '';

    // 初始化 i18n + 语言切换（必须在 bindEvents 之前，确保 label 同步）
    if (typeof applyStaticI18n === 'function') applyStaticI18n();
    if (typeof updateLangToggleLabel === 'function') updateLangToggleLabel();
    if (window.addEventListener) {
        window.addEventListener('langchange', function() {
            if (typeof applyStaticI18n === 'function') applyStaticI18n();
        });
    }

    bindEvents();

    // Fix: theme-bar.js sets accent-theme colors as inline styles on <html>.
    // Inline styles beat CSS selectors, so [data-theme="light"] has no effect.
    // Observe data-color-mode attribute changes and clear inline overrides in light mode.
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            if (m.attributeName === 'data-color-mode') {
                var mode = document.documentElement.getAttribute('data-color-mode');
                if (mode === 'light') {
                    var root = document.documentElement;
                    ['--bg-app','--bg-sidebar','--bg-chat','--bg-elevated','--bg-hover',
                     '--topbar-bg','--theme-bg','--theme-bg-alpha','--theme-bg-sidebar',
                     '--theme-bg-elevated','--theme-bg-hover'].forEach(function(v) {
                        root.style.removeProperty(v);
                    });
                }
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-color-mode'] });
    // Auto-restore last session
    try {
        S.lastTaskId = localStorage.getItem('jinclaw_lastTaskId');
        S.lastProjectId = localStorage.getItem('jinclaw_lastProjectId');
    } catch(e) {}
    loadProjectsAndTasks().then(function() {
        if (S.lastTaskId && S.lastProjectId) {
            switchTask(S.lastTaskId, S.lastProjectId);
        }
    });
}

function bindEvents() {
    var input = document.getElementById('userInput');
    document.getElementById('sendBtn').addEventListener('click', sendMessage);
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); sendMessage(); }
        else if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    input.addEventListener('input', function() {
        input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    });
    input.focus();

    // ── Toolbar buttons ──
    var shell = document.getElementById('appShell');
    var toggleLeft = document.getElementById('toggleLeftBtn');
    var toggleRight = document.getElementById('toggleRightBtn');
    function setPanelBtnStates() {
        if (!toggleLeft || !shell) return;
        toggleLeft.classList.toggle('active', !shell.classList.contains('no-left'));
        toggleRight.classList.toggle('active', !shell.classList.contains('no-right'));
    }
    toggleLeft && toggleLeft.addEventListener('click', function() {
        shell.classList.toggle('no-left');
        try { localStorage.setItem('jinclaw_panel_left', shell.classList.contains('no-left') ? '0' : '1'); } catch(e){}
        setPanelBtnStates();
    });
    toggleRight && toggleRight.addEventListener('click', function() {
        shell.classList.toggle('no-right');
        try { localStorage.setItem('jinclaw_panel_right', shell.classList.contains('no-right') ? '0' : '1'); } catch(e){}
        setPanelBtnStates();
    });
    // Restore last panel state
    try {
        if (localStorage.getItem('jinclaw_panel_left') === '0') shell.classList.add('no-left');
        if (localStorage.getItem('jinclaw_panel_right') === '0') shell.classList.add('no-right');
    } catch(e){}
    setPanelBtnStates();

    // Global hotkeys: Ctrl+B = left panel, Ctrl+. = right panel, Ctrl+Shift+N = new task
    document.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'b') { e.preventDefault(); toggleLeft.click(); }
        else if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === '.' || e.key === '>')) { e.preventDefault(); toggleRight.click(); }
        else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'n') { e.preventDefault(); document.getElementById('newTaskBtn') && document.getElementById('newTaskBtn').click(); }
    });

    // 清空对话
    document.getElementById('clearBtn') && document.getElementById('clearBtn').addEventListener('click', function() {
        if (S.chatHistory.length === 0 || confirm('确定要清空当前对话吗？')) { clearChat(); bindSuggestions(); }
    });

    // 新对话
    document.getElementById('newTaskBtn') && document.getElementById('newTaskBtn').addEventListener('click', async function() {
        if (S.currentProjectId) { await createTaskInProject(S.currentProjectId); }
        else { await ensureDefaultProject(''); }
    });

    // 主题切换（Jinclaw 内部，不依赖站点头顶 theme-bar）
    document.getElementById('themeToggleBtn') && document.getElementById('themeToggleBtn').addEventListener('click', function() {
        var root = document.documentElement;
        var current = root.getAttribute('data-theme') || root.getAttribute('data-color-mode') || 'dark';
        var next = (current === 'light' ? 'dark' : 'light');
        root.setAttribute('data-theme', next);
        root.setAttribute('data-color-mode', next);
        try { localStorage.setItem('jingent_colormode', next); localStorage.setItem('app_theme', next); } catch(e){}
        // Clear inline overrides forced by theme-bar.js
        ['--bg-app','--bg-sidebar','--bg-chat','--bg-elevated','--bg-hover',
         '--topbar-bg','--theme-bg','--theme-bg-alpha','--theme-bg-sidebar',
         '--theme-bg-elevated','--theme-bg-hover'].forEach(function(v) { root.style.removeProperty(v); });
    });

    document.getElementById('selectFolderBtn').addEventListener('click', openFolderModal);
    document.getElementById('folderModalOk').addEventListener('click', confirmFolderSelection);
    document.getElementById('folderModalCancel').addEventListener('click', closeFolderModal);
    document.getElementById('folderModal').addEventListener('click', function(e) {
        if (e.target === this) closeFolderModal();
    });
    document.getElementById('fileTreeBackBtn').addEventListener('click', showProjectList);


    document.getElementById('prevTabsInner').addEventListener('click', function(e) {
        var btn = e.target.closest('.jc-prev-tab');
        if (!btn) return;
        document.querySelectorAll('.jc-prev-tab').forEach(function(t) { t.classList.remove('active'); });
        btn.classList.add('active');
        S.currentPrev = btn.dataset.prev;
        document.querySelectorAll('.jc-prev-content').forEach(function(c) { c.classList.remove('active'); });
        var el = document.getElementById('prev-' + S.currentPrev);
        if (el) el.classList.add('active');
        if (S.currentPrev === 'terminal') updateTermCwd();
    });

    // Split dropdown: Main = new browser, Toggle = open menu
    var addMain = document.getElementById('addTabMain');
    var addToggle = document.getElementById('addTabToggle');
    var addMenu = document.getElementById('addTabMenu');
    if (addMain) {
        addMain.addEventListener('click', function(e) {
            e.stopPropagation();
            // 主按钮：默认新建浏览器（最常用）
            var fake = { currentTarget: { getAttribute: function() { return 'browser'; } } };
            try { fake.currentTarget.dataset = { add: 'browser' }; } catch(_) {}
            addPreviewTab(fake);
        });
    }
    if (addToggle) {
        addToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            if (!addMenu) return;
            var show = addMenu.style.display === 'none' || !addMenu.style.display;
            addMenu.style.display = show ? 'block' : 'none';
        });
    }
    // Dropdown items
    if (addMenu) {
        addMenu.querySelectorAll('[data-add]').forEach(function(item) {
            item.addEventListener('click', function(e) {
                e.stopPropagation();
                addMenu.style.display = 'none';
                var kind = item.dataset.add;
                var fake = { currentTarget: { getAttribute: function() { return kind; } } };
                try { fake.currentTarget.dataset = { add: kind }; } catch(_) {}
                addPreviewTab(fake);
            });
        });
    }
    // 点击外部关闭 dropdown
    document.addEventListener('click', function() {
        if (addMenu && addMenu.style.display === 'block') addMenu.style.display = 'none';
    });

    document.getElementById('closePreviewBtn').addEventListener('click', function() {
        document.getElementById('toggleRightBtn') && document.getElementById('toggleRightBtn').click();
    });
    document.getElementById('termInput').addEventListener('keydown', handleTerminalKey);

    // 附件 / 截图按钮 —— 直接绑定 + stopPropagation，避免 SVG 穿透没响应
    var attachBtn = document.getElementById('attachBtn');
    if (attachBtn) {
        attachBtn.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            var input = document.getElementById('jcHiddenFileInput');
            if (!input) {
                input = document.createElement('input');
                input.type = 'file'; input.id = 'jcHiddenFileInput'; input.multiple = true;
                input.style.display = 'none';
                document.body.appendChild(input);
            }
            input.click();
        });
    }
    var screenshotBtn = document.getElementById('screenshotBtn');
    if (screenshotBtn) {
        screenshotBtn.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            takeScreenshotAndAttach();
        });
    }
    // 附件 input change：读取文件并加入预览
    document.addEventListener('change', function(e) {
        var inp = e.target;
        if (!inp || inp.id !== 'jcHiddenFileInput' || !inp.files) return;
        var files = Array.prototype.slice.call(inp.files);
        files.forEach(function(f) { _addAttachmentFromFile(f); });
        inp.value = '';
        renderAttachments();
    });

    // ── 编辑器多 Tab：并列排布 + 切换 + hover 变 × 关闭（事件委托）──
    var editorTabs = document.getElementById('jcEditorTabs');
    if (editorTabs) {
        editorTabs.addEventListener('click', function(e) {
            var btn = e.target.closest && e.target.closest('.jc-editor-tab');
            if (!btn) return;
            e.preventDefault(); e.stopPropagation();
            var path = btn.dataset.path;
            if (!path) return;
            // 优先判断用户是否点在了"关闭图标"上（hover 时才显示的 ×），走关闭分支
            var onCloseIcon = e.target.closest('.jc-editor-tab-close');
            if (onCloseIcon) {
                closeEditorTab(path);
                return;
            }
            // 否则切换到该文件
            activateEditorTab(path);
        });
    }

    // ── 三栏 Resizer 拖拽宽度 ──
    bindResizers();

    // ── 右键菜单：先绑定全局 document 关闭 + ctxItem click，文件树统一事件委托（click + contextmenu），不逐个节点绑
    bindContextMenu();
    // 文件树委托绑定到 #fileTree，捕获冒泡；新展开的子节点也自动命中
    var fileTree = document.getElementById('fileTree');
    if (fileTree) {
        fileTree.addEventListener('click', _ftDelegatedClick);
        fileTree.addEventListener('contextmenu', _ftDelegatedContextMenu);
    }

    // ── 登录按钮：与 chat 全局共享登录弹窗 ──
    var loginBtn = document.getElementById('openLoginBtnInner');
    if (loginBtn) {
        loginBtn.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            openGlobalLoginOrRedirect();
        });
    }

    document.addEventListener('click', function(e) {
        // Suggestion chip
        var sg = e.target.closest && e.target.closest('.jc-sg');
        if (sg) {
            sg.classList.add('jc-sg-firing');
            setTimeout(function(){ sg.classList.remove('jc-sg-firing'); }, 260);
            document.getElementById('userInput').value = sg.dataset.text || '';
            document.getElementById('appShell').classList.remove('no-left','no-right');
            setPanelBtnStates();
            sendMessage();
            return;
        }
        // Copy button inside code blocks
        var copyBtn = e.target.closest && e.target.closest('.jc-code-copy');
        if (copyBtn) {
            e.stopPropagation();
            var pre = copyBtn.closest('pre');
            var code = pre ? pre.querySelector('code') : null;
            var text = code ? code.innerText : (pre ? pre.innerText : '');
            try {
                navigator.clipboard.writeText(text);
                var orig = copyBtn.textContent;
                // SVG 勾选图标替换为 OK SVG
                copyBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;margin-right:3px"><polyline points="20 6 9 17 4 12"/></svg>已复制';
                setTimeout(function() { copyBtn.textContent = orig || '复制'; }, 1400);
            } catch(_) { /* ignore */ }
            return;
        }
        // Model modal overlay click close
        if (e.target && e.target.id === 'modelModal') {
            e.target.style.display = 'none';
            document.querySelector('.jc-mm-body').classList.remove('show-form');
        }
    });

    document.getElementById('downloadBtn').addEventListener('click', function(e) {
        e.preventDefault(); alert('桌面端下载链接（请配置 APP_DOWNLOAD_URL）');
    });

    // ── Project/Task list delegation (bound once, handles all dynamic content) ──
    document.getElementById('projectTaskList').addEventListener('click', function(e) {
        var actBtn = e.target.closest('.jc-proj-act-btn');
        if (actBtn) {
            e.stopPropagation();
            if (actBtn.dataset.action === 'delproj') deleteProject(actBtn.dataset.pid);
            return;
        }
        var newTaskBtn = e.target.closest('.jc-proj-new-task-btn');
        if (newTaskBtn) {
            e.stopPropagation();
            createTaskInProject(newTaskBtn.dataset.pid).then(function() {
                loadTasksForProject(newTaskBtn.dataset.pid);
            });
            return;
        }
        var taskFiles = e.target.closest('.jc-task-files');
        if (taskFiles) {
            e.stopPropagation();
            openFileTree(taskFiles.dataset.pid, '');
            return;
        }
        var delBtn = e.target.closest('.jc-task-del');
        if (delBtn) {
            e.stopPropagation();
            deleteTask(delBtn.dataset.tid);
            return;
        }
        var taskItem = e.target.closest('.jc-task-item');
        if (taskItem) {
            switchTask(taskItem.dataset.tid, taskItem.dataset.pid);
            return;
        }
        var hdr = e.target.closest('.jc-proj-group-header');
        if (hdr) {
            toggleProject(hdr);
        }
    });

    // ── 中英切换按钮（jinclaw 页面内部 id="langToggleBtn"，防止 i18n.js 加载时机差导致漏绑）──
    var langBtn = document.getElementById('langToggleBtn');
    if (langBtn) {
        langBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (typeof toggleLang === 'function') toggleLang();
            else if (typeof setLang === 'function') setLang(getLang() === 'en' ? 'zh' : 'en');
            // 同步小标签
            var lbl = document.getElementById('langLabel');
            if (lbl && typeof getLang === 'function') {
                lbl.textContent = getLang() === 'en' ? '中' : 'EN';
            }
        });
    }

    // ── 模型管理 ──
    initModelManagement();

    // ── 内嵌登录/注册弹窗（Tauri + 浏览器通用入口） ──
    bindInlineLoginDialog();
}

// =============================================================
// 模型管理：本地存储 + 列表渲染 + 切换 + 添加 + 删除
// =============================================================
var MODEL_STORAGE_KEY = 'jinclaw_models_v1';
var MODEL_CURRENT_KEY = 'jinclaw_model_current_v1';

var DEFAULT_MODELS = [
    { id: 'deepseek-chat', displayName: 'DeepSeek V3 (默认)', apiFormat: 'openai', baseUrl: 'https://api.deepseek.com/v1', apiKey: '', family: 'deepseek', ctxWin: 128000, multimodal: false, builtin: true },
    { id: 'gpt-4o-mini', displayName: 'GPT-4o Mini', apiFormat: 'openai', baseUrl: 'https://api.openai.com/v1', apiKey: '', family: 'gpt', ctxWin: 128000, multimodal: true, builtin: true },
    { id: 'qwen-plus', displayName: '通义千问 Plus', apiFormat: 'openai', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', apiKey: '', family: 'qwen', ctxWin: 128000, multimodal: true, builtin: true },
];

function getStoredModels() {
    try {
        var raw = localStorage.getItem(MODEL_STORAGE_KEY);
        if (!raw) return JSON.parse(JSON.stringify(DEFAULT_MODELS));
        var parsed = JSON.parse(raw);
        if (!Array.isArray(parsed) || parsed.length === 0) return JSON.parse(JSON.stringify(DEFAULT_MODELS));
        return parsed;
    } catch(e) { return JSON.parse(JSON.stringify(DEFAULT_MODELS)); }
}
function saveStoredModels(models) {
    try { localStorage.setItem(MODEL_STORAGE_KEY, JSON.stringify(models)); } catch(e) {}
}
function getCurrentModelId() {
    var m = localStorage.getItem(MODEL_CURRENT_KEY);
    if (m) return m;
    var all = getStoredModels();
    return all.length ? all[0].id : '';
}
function setCurrentModelId(id) {
    try { localStorage.setItem(MODEL_CURRENT_KEY, id); } catch(e) {}
}

function initModelManagement() {
    var list = getStoredModels();
    var cur = getCurrentModelId();
    // 保证当前 id 存在
    if (!list.some(function(x) { return x.id === cur; })) {
        cur = list.length ? list[0].id : '';
        setCurrentModelId(cur);
    }
    renderModelIndicator();
    renderModelList();
    bindModelModalEvents();
}

function findModelById(id) {
    return getStoredModels().find(function(x) { return x.id === id; }) || null;
}

function renderModelIndicator() {
    var id = getCurrentModelId();
    var m = findModelById(id);
    var label = document.getElementById('currentModelLabel');
    if (!label) return;
    if (m) label.textContent = m.displayName || m.id;
    else label.textContent = '未选择模型';
}

function renderModelList() {
    var box = document.getElementById('modelList');
    if (!box) return;
    var list = getStoredModels();
    var cur = getCurrentModelId();
    box.innerHTML = list.map(function(m) {
        var isActive = m.id === cur;
        return '<div class="jc-mm-item' + (isActive ? ' active' : '') + '" data-mid="' + esc(m.id) + '">'
            + '<div class="jc-mm-item-icon">'
            + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>'
            + '</div>'
            + '<div class="jc-mm-item-body">'
            + '<div class="jc-mm-item-name">' + esc(m.displayName || m.id) + '</div>'
            + '<div class="jc-mm-item-sub">' + esc(m.baseUrl || '') + ' · ' + esc(m.id) + '</div>'
            + '</div>'
            + '<div class="jc-mm-item-act">'
            + (m.builtin ? '' : '<button type="button" class="jc-mm-item-del" data-del="' + esc(m.id) + '" title="删除模型" aria-label="删除">'
                + '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
                + '</button>')
            + '</div>'
            + '</div>';
    }).join('');

    // 点击项目 = 切换当前模型
    box.querySelectorAll('.jc-mm-item').forEach(function(el) {
        el.addEventListener('click', function(e) {
            if (e.target.closest('.jc-mm-item-del')) return;
            var mid = el.dataset.mid;
            setCurrentModelId(mid);
            renderModelList();
            renderModelIndicator();
        });
    });
    // 删除按钮
    box.querySelectorAll('[data-del]').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            var mid = btn.getAttribute('data-del');
            if (!confirm('确定删除这个自定义模型？')) return;
            var all = getStoredModels().filter(function(x) { return x.id !== mid; });
            saveStoredModels(all);
            if (getCurrentModelId() === mid) {
                setCurrentModelId(all.length ? all[0].id : '');
            }
            renderModelList();
            renderModelIndicator();
        });
    });
}

function bindModelModalEvents() {
    // 打开 / 关闭弹窗
    var indicator = document.getElementById('modelIndicatorBtn');
    var modal = document.getElementById('modelModal');
    var closeBtn = document.getElementById('modelModalClose');
    var body = document.querySelector('.jc-mm-body');
    if (indicator) {
        indicator.addEventListener('click', function(e) {
            e.stopPropagation();
            if (modal) modal.style.display = '';
        });
    }
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (modal) modal.style.display = 'none';
            if (body) body.classList.remove('show-form');
            resetAddModelForm();
        });
    }

    // 左侧：添加自定义模型 按钮 → 滑入右侧表单
    var openAdd = document.getElementById('openAddModelBtn');
    var formPane = document.getElementById('addModelFormPane');
    if (openAdd && body && formPane) {
        openAdd.addEventListener('click', function(e) {
            e.stopPropagation();
            body.classList.add('show-form');
            formPane.style.display = '';
            // 默认选中 ID，方便编辑
            setTimeout(function() { var i = document.getElementById('addModelId'); if (i) i.focus(); }, 60);
        });
    }
    // 取消添加
    var cancelBtn = document.getElementById('cancelAddModelBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (body) body.classList.remove('show-form');
            resetAddModelForm();
        });
    }
    // 提交
    var submitBtn = document.getElementById('submitAddModelBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            submitAddModel();
        });
    }

    // URL / 完整 URL 切换提示文案
    var fullUrl = document.getElementById('fullUrlToggle');
    if (fullUrl) {
        fullUrl.addEventListener('change', function() {
            var hint = document.getElementById('urlHintText');
            if (!hint) return;
            if (fullUrl.checked) {
                hint.textContent = '请填写完整的 chat completions URL（例如 https://api.openai.com/v1/chat/completions），程序将原样请求，不会再附加路径。';
            } else {
                hint.textContent = '请填写兼容 OpenAI API 的服务端点地址，不要以斜杠结尾。/chat/completions 将会被补充到你填写的地址末尾。';
            }
        });
    }
}

function resetAddModelForm() {
    ['addModelBaseUrl','addModelId','addModelApiKey','addModelDisplayName','addModelCtxWin'].forEach(function(id) {
        var el = document.getElementById(id); if (el) el.value = '';
    });
    var fmt = document.getElementById('addModelApiFormat'); if (fmt) fmt.value = 'openai';
    var fam = document.getElementById('addModelFamily'); if (fam) fam.value = 'auto';
    var fu = document.getElementById('fullUrlToggle'); if (fu) fu.checked = false;
    var mm = document.getElementById('multimodalToggle'); if (mm) mm.checked = true;
    var cw = document.getElementById('addModelCtxWin'); if (cw) cw.value = '128000';
}

function submitAddModel() {
    var baseUrl = (document.getElementById('addModelBaseUrl').value || '').trim();
    var modelId = (document.getElementById('addModelId').value || '').trim();
    var apiKey  = (document.getElementById('addModelApiKey').value || '').trim();
    var fmt     = (document.getElementById('addModelApiFormat').value || 'openai').trim();
    var disp    = (document.getElementById('addModelDisplayName').value || '').trim();
    var fam     = (document.getElementById('addModelFamily').value || 'auto').trim();
    var cw      = parseInt((document.getElementById('addModelCtxWin').value || '128000').trim(), 10);
    var multi   = !!document.getElementById('multimodalToggle').checked;

    if (!baseUrl) { alert('请填写 API 请求地址'); return; }
    if (!modelId) { alert('请填写模型 ID'); return; }

    var all = getStoredModels();
    // 若 id 重复则覆盖
    all = all.filter(function(x) { return x.id !== modelId; });
    var m = {
        id: modelId,
        displayName: disp || modelId,
        apiFormat: fmt,
        baseUrl: baseUrl,
        apiKey: apiKey,
        family: fam,
        ctxWin: isFinite(cw) && cw > 0 ? cw : 128000,
        multimodal: multi,
        builtin: false
    };
    all.push(m);
    saveStoredModels(all);
    setCurrentModelId(modelId);
    renderModelList();
    renderModelIndicator();

    // 收起表单
    var body = document.querySelector('.jc-mm-body');
    if (body) body.classList.remove('show-form');
    resetAddModelForm();
}

// =============================================================
// 通用 SVG 片段（避免 emoji）
// =============================================================
var SVG = {
    folder: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
    file: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
    chat: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    files: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    chevronRight: '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>',
    chevronDown: '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 6"/></svg>',
    browser: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    terminal: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
    sg_search: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    sg_doc: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    sg_wrench: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    sg_branch: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    sg_plan: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 11 22 2 13 21 11 13 3 11"/></svg>',
    sg_shield: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
    planClipboard: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
    refresh: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
    close: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    overflow: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>',
};

// ── Workspace helpers ──────────────────────────────────────
function getWorkspace() {
    // Derive from current project
    return S._projectsMap && S.currentProjectId
        ? (S._projectsMap[S.currentProjectId] || {}).workspace_path || ''
        : '';
}

function updateTermCwd() {
    document.getElementById('termCwd').textContent = getWorkspace() || '~';
}

// ── Modal ──────────────────────────────────────────────────
function openFolderModal() {
    document.getElementById('folderModalInput').value = getWorkspace() || '';
    document.getElementById('folderModal').style.display = '';
    document.getElementById('folderModalInput').focus();
    document.getElementById('folderModalInput').select();
}
function closeFolderModal() { document.getElementById('folderModal').style.display = 'none'; }
function confirmFolderSelection() {
    closeFolderModal();
    var val = document.getElementById('folderModalInput').value.trim().replace(/\\/g, '/');
    createProject(val);
}

// ── Projects ───────────────────────────────────────────────
async function createProject(ws) {
    try {
        var resp = await fetch(API.projects + '?workspace_path=' + encodeURIComponent(ws || '_default_'), { method: 'POST' });
        var d = await resp.json();
        if (d.code === 200) {
            S.currentProjectId = d.project.id;
            // Also create first task
            await createTaskInProject(S.currentProjectId);
            await loadProjectsAndTasks();
            // Expand this project
            var hdr = document.querySelector('.jc-proj-group-header[data-pid="' + S.currentProjectId + '"]');
            if (hdr) hdr.click();
        }
    } catch(e) { console.error(e); }
}

async function loadProjectsAndTasks() {
    var container = document.getElementById('projectTaskList');
    var empty = document.getElementById('projectEmpty');
    try {
        var resp = await fetch(API.projects);
        var d = await resp.json();
        if (d.code !== 200 || !d.projects.length) {
            if (empty) empty.style.display = '';
            return;
        }
        if (empty) empty.style.display = 'none';

        // Cache workspace paths
        S._projectsMap = {};
        d.projects.forEach(function(p) { S._projectsMap[p.id] = p; });

        // If no active project, pick the first one
        if (!S.currentProjectId && d.projects && d.projects.length > 0) {
            S.currentProjectId = d.projects[0].id;
        }

        // Render project groups — active one pre-expanded
        container.innerHTML = d.projects.map(function(p) {
            var isActive = p.id === S.currentProjectId;
            var isDefault = !p.workspace_path || p.workspace_path.indexOf('work-mode-projects') > -1;
            var displayName = p.name || (isDefault ? '默认项目' : p.workspace_path.split(/[\\/]/).pop());
            var ctx = p.context || {};
            var ctxLine = '';
            if (ctx.languages && ctx.languages.length) ctxLine = ctx.languages.slice(0,2).join(' · ');
            if (ctx.frameworks && ctx.frameworks.length) ctxLine += (ctxLine ? ' · ' : '') + ctx.frameworks.slice(0,3).join(' · ');
            if (!ctxLine && ctx.project_type && ctx.project_type !== 'unknown') ctxLine = ctx.project_type;
            return '<div class="jc-proj-group" data-loaded="' + (isActive ? '1' : '0') + '">'
                + '<div class="jc-proj-group-header' + (isActive ? ' active expanded' : '') + '" data-pid="' + p.id + '">'
                + '<span class="jc-proj-icon">' + SVG.folder + '</span>'
                + '<div class="jc-proj-info">'
                + '<div class="jc-proj-name" title="' + esc(p.workspace_path || '默认') + '">' + esc(displayName) + '</div>'
                + (ctxLine ? '<div class="jc-proj-ctx">' + esc(ctxLine) + '</div>' : '')
                + '</div>'
                + '<span class="jc-proj-chevron">' + (isActive ? SVG.chevronDown : SVG.chevronRight) + '</span>'
                + '<div class="jc-proj-actions">'
                + '<button class="jc-proj-act-btn danger" title="删除项目" data-action="delproj" data-pid="' + p.id + '" aria-label="删除">' + SVG.close + '</button>'
                + '</div>'
                + '</div>'
                + '<div class="jc-task-items" data-pid="' + p.id + '" style="' + (isActive ? '' : 'display:none') + '">' + (isActive ? '<div class="jc-empty-state-mini"><p>加载中...</p></div>' : '') + '</div>'
                + '<div class="jc-proj-new-task" style="' + (isActive ? '' : 'display:none') + '"><button class="jc-proj-new-task-btn" data-action="newtask" data-pid="' + p.id + '">'
                + SVG.planClipboard + '<span style="margin-left:4px">新建任务</span></button></div>'
                + '</div>';
        }).join('');

        // Load tasks for the active project
        if (S.currentProjectId) {
            loadTasksForProject(S.currentProjectId);
        }
    } catch(e) { console.error(e); }
}

function toggleProject(hdr) {
    var pid = hdr.dataset.pid;
    var group = hdr.closest('.jc-proj-group');
    var taskItems = group.querySelector('.jc-task-items');
    var newTaskRow = group.querySelector('.jc-proj-new-task');
    var chevron = hdr.querySelector('.jc-proj-chevron');
    var isOpen = hdr.classList.contains('expanded');
    if (isOpen) {
        hdr.classList.remove('expanded');
        if (chevron) chevron.innerHTML = SVG.chevronRight;
        taskItems.style.display = 'none';
        newTaskRow.style.display = 'none';
    } else {
        hdr.classList.add('expanded');
        if (chevron) chevron.innerHTML = SVG.chevronDown;
        taskItems.style.display = '';
        newTaskRow.style.display = '';
        if (group.dataset.loaded !== '1') {
            group.dataset.loaded = '1';
            loadTasksForProject(pid);
        }
    }
}

async function loadTasksForProject(pid) {
    var taskEl = document.querySelector('.jc-task-items[data-pid="' + pid + '"]');
    if (!taskEl) return;
    try {
        var resp = await fetch(API.tasks + '?project_id=' + pid);
        var d = await resp.json();
        if (d.code !== 200 || !d.tasks.length) {
            taskEl.innerHTML = '<div class="jc-task-item" style="color:var(--text-muted);font-style:italic">暂无任务</div>';
            return;
        }
        taskEl.innerHTML = d.tasks.map(function(t) {
        var isActive = t.id === S.currentTaskId;
        return '<div class="jc-task-item' + (isActive ? ' active' : '') + '" data-tid="' + t.id + '" data-pid="' + pid + '">'
            + '<span style="width:22px;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:var(--accent)">' + SVG.chat + '</span>'
            + '<span class="jc-task-name">' + esc(t.name) + '</span>'
            + '<span class="jc-task-actions">'
            + '<button class="jc-task-files" title="文件管理" data-action="files" data-pid="' + pid + '" aria-label="文件管理">' + SVG.files + '</button>'
            + '<button class="jc-task-del" data-tid="' + t.id + '" aria-label="删除">' + SVG.close + '</button>'
            + '</span>'
            + '</div>';
    }).join('');
    } catch(e) { /* silent */ }
}

async function createTaskInProject(pid) {
    try {
        var resp = await fetch(API.tasks + '?project_id=' + pid + '&name=新任务', { method: 'POST' });
        var d = await resp.json();
        if (d.code === 200) {
            S.currentTaskId = d.task.id;
            S.currentProjectId = pid;
            clearChat();
            // Refresh task list under this project
            loadTasksForProject(pid);
        }
        return d;
    } catch(e) { return {}; }
}

async function switchTask(tid, pid) {
    S.currentTaskId = tid;
    S.currentProjectId = pid;
    S.chatHistory = [];
    S.planItems = [];
    S.planStepIndex = -1;
    // Save to localStorage for auto-restore
    try { localStorage.setItem('jinclaw_lastTaskId', tid); localStorage.setItem('jinclaw_lastProjectId', pid); } catch(e) {}
    // Clean DOM
    var box = document.getElementById('chatBox');
    box.querySelectorAll('.jc-msg,.jc-tc').forEach(function(el) { el.remove(); });
    var empty = document.getElementById('emptyState');
    if (empty) empty.style.display = '';

    updateTermCwd();
    // Highlight
    document.querySelectorAll('.jc-task-item').forEach(function(el) { el.classList.remove('active'); });
    var el = document.querySelector('.jc-task-item[data-tid="' + tid + '"]');
    if (el) el.classList.add('active');
    document.querySelectorAll('.jc-proj-group-header').forEach(function(h) { h.classList.remove('active'); });
    var hdr = document.querySelector('.jc-proj-group-header[data-pid="' + pid + '"]');
    if (hdr) hdr.classList.add('active');

    // Load chat history and rebuild chatHistory array
    try {
        var resp = await fetch(API.tasks + '/' + tid + '/chat');
        var d = await resp.json();
        if (d.code === 200 && d.events && d.events.length) {
            S.chatHistory = [];
            d.events.forEach(function(ev) {
                renderHistoryEvent(ev);
                if (ev.type === 'user_msg') {
                    S.chatHistory.push({ role: 'user', message: ev.message || '' });
                } else if (ev.type === 'message_chunk') {
                    var last = S.chatHistory[S.chatHistory.length - 1];
                    if (last && last.role === 'ai') {
                        last.message += (ev.content || '');
                    } else {
                        S.chatHistory.push({ role: 'ai', message: ev.content || '' });
                    }
                } else if (ev.type === 'tool_call') {
                    var lst = S.chatHistory[S.chatHistory.length - 1];
                    if (lst && lst.role === 'ai') {
                        if (!lst.tool_calls) lst.tool_calls = [];
                        lst.tool_calls.push(ev.tool);
                    }
                }
            });
            // Hide empty state if we have messages
            var emptyEl = document.getElementById('emptyState');
            if (emptyEl && S.chatHistory.length > 0) {
                emptyEl.style.display = 'none';
            }
        }
    } catch(e) {}
}

async function deleteTask(tid) {
    if (!confirm('删除此任务？')) return;
    await fetch(API.tasks + '/' + tid, { method: 'DELETE' });
    if (S.currentTaskId === tid) { S.currentTaskId = null; clearChat(); }
    // Refresh the parent project's task list
    var item = document.querySelector('.jc-task-item[data-tid="' + tid + '"]');
    var pid = item ? item.dataset.pid : null;
    if (pid) loadTasksForProject(pid);
}

async function deleteProject(pid) {
    if (!confirm('删除此项目及其所有任务？')) return;
    await fetch(API.projects + '/' + pid, { method: 'DELETE' });
    if (S.currentProjectId === pid) { S.currentProjectId = null; S.currentTaskId = null; clearChat(); }
    loadProjectsAndTasks();
}

// ── File Tree ──────────────────────────────────────────────
async function openFileTree(pid, ws) {
    S.currentProjectId = pid;
    // Ensure we have workspace info (could be stale or missing)
    if ((!ws || ws === '_default_') && pid) {
        try {
            var resp = await fetch(API.projects);
            var d = await resp.json();
            if (d.code === 200) {
                d.projects.forEach(function(p) {
                    S._projectsMap[p.id] = p;
                    if (p.id === pid) ws = p.workspace_path;
                });
            }
        } catch(e) {}
    }
    if (ws && ws !== '_default_') S.workspace = ws;
    document.getElementById('projectListView').style.display = 'none';
    document.getElementById('fileTreeView').style.display = '';
    document.getElementById('fileTreeBackLabel').textContent = '返回项目列表';
    refreshFileTree(ws);
}

function showProjectList() {
    document.getElementById('fileTreeView').style.display = 'none';
    document.getElementById('projectListView').style.display = '';
    loadProjectsAndTasks();
}

async function refreshFileTree(ws) {
    var tree = document.getElementById('fileTree');
    ws = ws || getWorkspace();
    if (!ws || ws === '_default_') {
        tree.innerHTML = '<div class="jc-empty-state-mini"><p>请先在左侧展开项目并创建对话</p><p style="font-size:11px;color:var(--text-muted)">文件管理需要绑定工作文件夹</p></div>';
        return;
    }
    tree.innerHTML = '<div class="jc-empty-state-mini"><p>加载中...</p></div>';
    try {
        var resp = await fetch(API.wsTree + '?path=' + encodeURIComponent(ws) + '&depth=1&offset=0&limit=60', {
            credentials: 'include',
            headers: _authHeaders(),
        });
        var d = await resp.json();
        if (d.code === 200 && d.tree) {
            renderCollapsedTree(tree, d.tree);
        } else {
            tree.innerHTML = '<div class="jc-empty-state-mini"><p>加载失败</p><p style="font-size:11px;color:var(--text-muted)">' + esc(d.detail?.msg || d.detail || '服务器错误') + '</p></div>';
        }
    } catch(e) {
        tree.innerHTML = '<div class="jc-empty-state-mini"><p>加载失败</p><p style="font-size:11px;color:var(--text-muted)">' + esc(e.message) + '</p></div>';
    }
}

function renderCollapsedTree(container, items, level, _startIdx) {
    level = level || 0;
    var MAX_DEPTH = 6;
    var BATCH_SIZE = 60;

    // 第一次调用：清空容器，用 DocumentFragment 批量处理
    if (_startIdx === undefined) {
        container.innerHTML = '';
        _startIdx = 0;
    }

    // 深度超限：截断，显示一条提示
    if (level > MAX_DEPTH) {
        var tip = document.createElement('div');
        tip.className = 'jc-ft-item jc-ft-overflow';
        tip.style.paddingLeft = (12 + level * 14) + 'px';
        tip.innerHTML = '<span style="width:14px"></span>'
            + '<span class="jc-ft-icon" style="display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;color:var(--text-muted)">' + SVG.overflow + '</span>'
            + '<span class="jc-ft-name" style="color:var(--text-muted)">··· 深度超过 ' + MAX_DEPTH + ' 层，建议在资源管理器中查看</span>';
        container.appendChild(tip);
        return;
    }

    var frag = document.createDocumentFragment();
    var endIdx = Math.min(items.length, _startIdx + BATCH_SIZE);

    for (var i = _startIdx; i < endIdx; i++) {
        var item = items[i];
        if (!item) continue;
        var div = document.createElement('div');
        div.className = 'jc-ft-item' + (item._overflow ? ' jc-ft-overflow' : '');
        div.style.paddingLeft = (12 + level * 14) + 'px';
        // 保存 item 元数据：事件委托从 dataset 读
        div.dataset.path = item.path || '';
        div.dataset.name = item.name || '';
        div.dataset.isDir = item.is_dir ? '1' : '0';
        if (item._overflow) {
            div.dataset.overflow = '1';
            div.dataset.offset = item._offset || 0;
            div.dataset.limit = item._limit || 60;
            div.dataset.total = item._total || 0;
            div.dataset.level = level;
        }

        var hasChildren = item.is_dir || item.has_children;
        var chevron = hasChildren ? ('<span class="jc-ft-chevron">' + SVG.chevronRight + '</span>') : '<span style="width:14px;flex-shrink:0;display:inline-block"></span>';
        var iconSvg = item._overflow ? SVG.overflow : (item.is_dir ? SVG.folder : SVG.file);
        div.innerHTML = chevron
            + '<span class="jc-ft-icon" style="display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;color:var(--accent)">' + iconSvg + '</span>'
            + '<span class="jc-ft-name">' + esc(item.name) + '</span>';
        frag.appendChild(div);
        if (hasChildren && !item._overflow) {
            var wrap = document.createElement('div'); wrap.className = 'jc-ft-children'; wrap.style.display = 'none';
            frag.appendChild(wrap);
        }
    }

    container.appendChild(frag);

    // 若本批次后仍有剩余，则异步处理下一批，避免主线程阻塞
    if (endIdx < items.length) {
        var next = function() { renderCollapsedTree(container, items, level, endIdx); };
        if (typeof requestIdleCallback === 'function') requestIdleCallback(next, { timeout: 60 });
        else setTimeout(next, 0);
    }
}

// 容器级事件委托（click + contextmenu）：在 bindEvents 里绑到 #fileTree / 子容器
function _ftDelegatedClick(e) {
    var item = e.target.closest && e.target.closest('.jc-ft-item');
    if (!item) return;
    var container = item.parentElement;
    if (!container) return;
    e.stopPropagation();

    // overflow: 点击加载更多分页
    if (item.dataset.overflow === '1') {
        var level = parseInt(item.dataset.level || '0', 10);
        var offset = parseInt(item.dataset.offset || '0', 10);
        var limit = parseInt(item.dataset.limit || '60', 10);
        var path = item.dataset.path;
        e.preventDefault();
        var oldText = item.querySelector('.jc-ft-name');
        if (oldText) oldText.textContent = '加载中…';
        fetch(API.wsTree + '?path=' + encodeURIComponent(path) + '&depth=1&offset=' + offset + '&limit=' + limit, { credentials: 'include' })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.code !== 200 || !d.tree) return;
                // 在当前 overflow 前面插入下一批节点（append 到 container，再移除 overflow）
                var nextItems = d.tree.filter(function(x) { return !x._overflow; });
                var overflow = d.tree.find(function(x) { return x._overflow; });
                // 批量插入（用临时 fragment + renderCollapsedTree 直接渲染新节点）
                var tmpHolder = document.createElement('div');
                container.insertBefore(tmpHolder, item);
                renderCollapsedTree(tmpHolder, nextItems, level);
                // 把 tmpHolder 的子节点搬出来
                while (tmpHolder.firstChild) container.insertBefore(tmpHolder.firstChild, item);
                container.removeChild(tmpHolder);
                // 移除旧 overflow；有新 overflow 就追加在末尾
                container.removeChild(item);
                if (overflow) {
                    var ovDiv = document.createElement('div');
                    ovDiv.className = 'jc-ft-item jc-ft-overflow';
                    ovDiv.style.paddingLeft = (12 + level * 14) + 'px';
                    ovDiv.dataset.overflow = '1';
                    ovDiv.dataset.path = overflow.path || path;
                    ovDiv.dataset.offset = overflow._offset;
                    ovDiv.dataset.limit = overflow._limit || 60;
                    ovDiv.dataset.total = overflow._total || 0;
                    ovDiv.dataset.level = level;
                    ovDiv.innerHTML = '<span style="width:14px"></span>'
                        + '<span class="jc-ft-icon" style="display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;color:var(--text-muted)">' + SVG.overflow + '</span>'
                        + '<span class="jc-ft-name" style="color:var(--text-muted)">' + esc(overflow.name) + '</span>';
                    container.appendChild(ovDiv);
                }
            })
            .catch(function() { if (oldText) oldText.textContent = '加载失败，点击重试'; });
        return;
    }

    // chevron 点击 → 只展开
    if (e.target.closest('.jc-ft-chevron')) { toggleTreeChildren(item, null, level); return; }

    // 文件夹 → 展开；文件 → 打开编辑器
    if (item.dataset.isDir === '1') toggleTreeChildren(item, null, level);
    else openFileInEditor(item.dataset.path, item.dataset.name);
}

function _ftDelegatedContextMenu(e) {
    var item = e.target.closest && e.target.closest('.jc-ft-item');
    if (!item) return;
    if (item.dataset.overflow === '1') return; // overflow 行不出菜单
    e.preventDefault(); e.stopPropagation();
    showCtxMenu(e.clientX, e.clientY, {
        path: item.dataset.path || '',
        name: item.dataset.name || '',
        isDir: item.dataset.isDir === '1',
    });
}

async function toggleTreeChildren(div, item, level) {
    var next = div.nextElementSibling;
    if (!next || !next.classList.contains('jc-ft-children')) return;

    // Already expanded → collapse
    if (next.style.display !== 'none') {
        next.style.display = 'none';
        div.classList.remove('expanded');
        var cv = div.querySelector('.jc-ft-chevron');
        if (cv) cv.innerHTML = SVG.chevronRight;
        return;
    }

    // Expand
    div.classList.add('expanded');
    var cv = div.querySelector('.jc-ft-chevron');
    if (cv) cv.innerHTML = SVG.chevronDown;

    // Lazy-load children from API if not loaded yet
    if (!next.dataset.loaded) {
        next.innerHTML = '<div class="jc-empty-state-mini"><p>加载中...</p></div>';
        next.style.display = '';
        next.dataset.loaded = '1';
        // 支持两种入参来源：旧的 item.path 或新的 div.dataset.path
        var path = (item && item.path) ? item.path : (div.dataset.path || '');
        try {
            var resp = await fetch(API.wsTree + '?path=' + encodeURIComponent(path) + '&depth=1&offset=0&limit=60', { credentials: 'include' });
            var d = await resp.json();
            if (d.code === 200) renderCollapsedTree(next, d.tree, level + 1);
        } catch(e) { next.innerHTML = '<div class="jc-empty-state-mini"><p>加载失败</p></div>'; }
    } else {
        next.style.display = '';
    }
}

// ── File Viewer ────────────────────────────────────────────
// 多文件并列 Tab 模式：点文件加入 openFiles，已存在则切换；并列展示在 tab bar 中
async function openFileInEditor(path, name) {
    // 已打开 → 直接切到它（不重复读网络）
    var existing = (S.openFiles || []).find(function(f) { return f.path === path; });
    if (existing) {
        activateEditorTab(path);
        return;
    }
    try {
        var resp = await fetch(API.wsRead + '?path=' + encodeURIComponent(path));
        var d = await resp.json();
        if (d.code !== 200) return;
        var file = { path: path, name: name, content: d.content, language: d.language };
        S.openFiles = S.openFiles || [];
        S.openFiles.push(file);
        S.currentFile = file;
        updateCodeBadge();
        showCodeTab();
        renderEditorTabs();
        renderCodeView(path, name, d.content, d.language);
    } catch(e) {}
}

function showCodeTab() {
    S.currentPrev = 'code';
    document.querySelectorAll('.jc-prev-tab').forEach(function(t) { t.classList.remove('active'); });
    var codeTab = document.querySelector('.jc-prev-tab[data-prev="code"]');
    if (codeTab) codeTab.classList.add('active');
    document.querySelectorAll('.jc-prev-content').forEach(function(c) { c.classList.remove('active'); });
    var codeView = document.getElementById('prev-code');
    if (codeView) codeView.classList.add('active');
}

// 并列渲染所有打开的 Tab：每个按钮带 data-path，事件委托统一处理点击/关闭
function renderEditorTabs() {
    var host = document.getElementById('jcEditorTabs');
    if (!host) return;
    var list = S.openFiles || [];
    var frag = document.createDocumentFragment();
    for (var i = 0; i < list.length; i++) {
        var f = list[i];
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'jc-editor-tab' + (S.currentFile && S.currentFile.path === f.path ? ' active' : '');
        btn.dataset.path = f.path;
        btn.title = f.path + '（悬停图标变为 × 可关闭）';
        btn.setAttribute('role', 'tab');
        btn.setAttribute('aria-selected', S.currentFile && S.currentFile.path === f.path ? 'true' : 'false');
        btn.innerHTML =
            '<span class="jc-editor-tab-icon" aria-hidden="true">'
            + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'
            + '</span>'
            + '<span class="jc-editor-tab-close" aria-hidden="true" style="display:none">'
            + '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
            + '</span>'
            + '<span class="jc-editor-filename">' + esc(f.name) + '</span>';
        frag.appendChild(btn);
    }
    host.innerHTML = '';
    if (frag.childNodes.length) host.appendChild(frag);
}

function activateEditorTab(path) {
    var f = (S.openFiles || []).find(function(x) { return x.path === path; });
    if (!f) return;
    S.currentFile = f;
    renderEditorTabs();
    updateCodeBadge();
    showCodeTab();
    renderCodeView(f.path, f.name, f.content, f.language);
}

function closeEditorTab(path) {
    S.openFiles = (S.openFiles || []).filter(function(f) { return f.path !== path; });
    var codeContainer = document.getElementById('editorContainer');
    var placeholder = document.getElementById('codePlaceholder');
    if (S.openFiles.length === 0) {
        S.currentFile = null;
        if (codeContainer) codeContainer.style.display = 'none';
        if (placeholder) placeholder.style.display = '';
        var mount = document.getElementById('editorMount');
        if (mount) mount.innerHTML = '';
    } else if (S.currentFile && S.currentFile.path === path) {
        // 关的是当前 tab → 切回上一个（数组最后一个）
        var next = S.openFiles[S.openFiles.length - 1];
        S.currentFile = next;
        showCodeTab();
        renderCodeView(next.path, next.name, next.content, next.language);
    }
    renderEditorTabs();
    updateCodeBadge();
}

function renderCodeView(path, name, content, language) {
    var ph = document.getElementById('codePlaceholder');
    var cc = document.getElementById('editorContainer');
    if (ph) ph.style.display = 'none';
    if (cc) cc.style.display = '';
    // editorFileName 在多 tab 模式下已用 jcEditorTabs 代替，但保留它不显示以防其他地方引用
    var editorFileName = document.getElementById('editorFileName');
    if (editorFileName) editorFileName.textContent = name;
    document.getElementById('editorApplyBtn').style.display = 'none';
    document.getElementById('editorRevertBtn').style.display = 'none';
    var mount = document.getElementById('editorMount');
    mount.innerHTML = '';
    var pre = document.createElement('pre');
    pre.style.cssText = 'padding:16px;margin:0;overflow:auto;height:100%;font-family:Consolas,monospace;font-size:12px;line-height:1.6;color:var(--code-text);background:var(--code-bg);tab-size:4;white-space:pre-wrap';
    pre.innerHTML = hlCode(content, language);
    mount.appendChild(pre);
    S.editorOriginal = content;
}

function hlCode(code, lang) {
    var s = esc(code);
    if (lang === 'python') {
        s = s.replace(/(#.*)/g, '<span style="color:#6b7280">$1</span>');
        s = s.replace(/("""[\s\S]*?"""|'''[\s\S]*?''')/g, '<span style="color:#22c55e">$1</span>');
        s = s.replace(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g, '<span style="color:#22c55e">$1</span>');
        s = s.replace(/\b(def|class|import|from|return|if|else|elif|for|while|try|except|with|as|yield|async|await|raise|pass|break|continue|and|or|not|in|is|None|True|False|lambda)\b/g, '<span style="color:#c084fc">$1</span>');
    }
    return s;
}
function updateCodeBadge() {
    var b = document.getElementById('codeTabBadge');
    if (!b) return;
    var n = (S.openFiles || []).length;
    b.style.display = n > 0 ? '' : 'none';
    b.textContent = String(n);
}

// ── Chat ────────────────────────────────────────────────────
async function sendMessage() {
    var input = document.getElementById('userInput');
    var text = input.value.trim();
    var hasAttach = S.attachments && S.attachments.length > 0;
    if (!text && !hasAttach || S.isSending) return;
    input.value = ''; input.style.height = 'auto';
    S.isSending = true;
    var sendBtn = document.getElementById('sendBtn');
    sendBtn.disabled = true;
    // Loading 状态：把发送按钮换成 spinner + 收缩动画
    sendBtn.dataset.origHtml = sendBtn.innerHTML;
    sendBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation:jcSpin .8s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>';
    setStatus('思考中…', 'busy');

    var empty = document.getElementById('emptyState');
    if (empty) empty.style.display = 'none';

    // 把附件（文件 / 截图）编码到用户消息里：图片带 dataURL，小文件内嵌 base64，大文件只给文件名+大小
    var attPrefix = '';
    if (hasAttach) {
        var attLines = [];
        var MAX_EMBED_BYTES = 100 * 1024; // 100KB 以内才内联 base64，其他仅元数据
        for (var ixA = 0; ixA < S.attachments.length; ixA++) {
            var a = S.attachments[ixA];
            try {
                if (a.kind === 'image') {
                    if (a.preview) attLines.push('📎 [图片附件 ' + (ixA + 1) + '] name=' + (a.name || 'image.png') + ' size=' + (a.size || 0) + ' data=' + a.preview);
                    else attLines.push('📎 [图片附件 ' + (ixA + 1) + '] name=' + (a.name || 'image.png') + ' size=' + (a.size || 0));
                } else {
                    var size = typeof a.size === 'number' ? a.size : (a.file && a.file.size) || 0;
                    if (size <= MAX_EMBED_BYTES && a.file) {
                        var b64 = await _fileToBase64(a.file);
                        attLines.push('📎 [文件附件 ' + (ixA + 1) + '] name=' + (a.name || a.file.name) + ' size=' + size + ' data=' + b64);
                    } else {
                        attLines.push('📎 [文件附件 ' + (ixA + 1) + '] name=' + (a.name || (a.file && a.file.name)) + ' size=' + size);
                    }
                }
            } catch(_) { attLines.push('📎 [附件 ' + (ixA + 1) + '] name=' + (a.name || '')); }
        }
        if (attLines.length) attPrefix = '【附件：\n' + attLines.join('\n') + '\n】\n';
    }
    var fullText = attPrefix + (text || '');

    addMessage('user', fullText);
    S.chatHistory.push({ role: 'user', message: fullText });
    // 发送后清空附件预览
    if (hasAttach) { S.attachments = []; renderAttachments(); }

    // Ensure project + task exist before sending
    if (!S.currentProjectId) {
        await ensureDefaultProject(fullText);
    }
    if (S.currentProjectId && !S.currentTaskId) {
        await createTaskInProject(S.currentProjectId);
    }

    // Save user message to disk
    if (S.currentTaskId) {
        try {
            await fetch(API.tasks + '/' + S.currentTaskId + '/chat/save', {
                method: 'POST',
                credentials: 'include',
                headers: Object.assign({ 'Content-Type': 'application/json' }, _authHeaders()),
                body: JSON.stringify({ type: 'user_msg', role: 'user', message: fullText, uid: _lastSyncUid || undefined }),
            });
        } catch(e) {}
    }

    var agentDiv = createAgentMessage();
    var body = agentDiv.querySelector('.jc-msg-bd');
    body.appendChild(createThink());

    try {
        var resp = await fetch(API.chat, {
            method: 'POST',
            credentials: 'include',
            headers: Object.assign({ 'Content-Type': 'application/json' }, _authHeaders()),
            body: JSON.stringify({
                history: S.chatHistory.slice(0, -1),
                newMessage: fullText, task_id: S.currentTaskId, lang: 'zh', uid: _lastSyncUid || undefined,
            }),
        });
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var reader = resp.body.getReader(), decoder = new TextDecoder();
        var buf = '', fullReply = '', toolCalls = [];

        while (true) {
            var r = await reader.read();
            if (r.done) break;
            buf += decoder.decode(r.value, { stream: true });
            var lines = buf.split('\n'); buf = lines.pop();
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                if (!line.startsWith('data: ')) continue;
                var data = line.slice(6).trim();
                if (data === '[DONE]') break;
                try {
                    var ev = JSON.parse(data);
                    handleEvent(ev, body);
                    if (ev.type === 'message_chunk') fullReply += (ev.content || '');
                    if (ev.type === 'tool_call') toolCalls.push(ev.tool);
                } catch(e) {}
            }
            scrollChat();
        }
        S.chatHistory.push({ role: 'ai', message: fullReply, tool_calls: toolCalls });

        // AI-generate task nickname after first meaningful reply
        if (S.currentTaskId && S.chatHistory.length <= 3) {
            autoRenameTask(S.currentTaskId, S.chatHistory);
        }
    } catch(e) {
        var errEl = document.createElement('div');
        errEl.style.cssText = 'color:#ef4444;font-size:12px;padding:4px 0';
        errEl.textContent = '发送失败: ' + e.message;
        body.appendChild(errEl);
        setStatus('发送失败', 'error');
    } finally {
        S.isSending = false;
        var sendBtn = document.getElementById('sendBtn');
        sendBtn.disabled = false;
        if (sendBtn.dataset.origHtml) { sendBtn.innerHTML = sendBtn.dataset.origHtml; delete sendBtn.dataset.origHtml; }
        setStatus('就绪');
        document.getElementById('userInput').focus(); scrollChat();
    }
}

async function ensureDefaultProject(firstMsg) {
    try {
        // Check if any projects exist
        var r = await fetch(API.projects);
        var d = await r.json();
        if (d.code === 200 && d.projects.length > 0) {
            // Use first project
            S.currentProjectId = d.projects[0].id;
            await createTaskInProject(S.currentProjectId);
        } else {
            // Create default project (AppData)
            var pr = await fetch(API.projects + '?workspace_path=_default_&name=默认项目', { method: 'POST' });
            var pd = await pr.json();
            if (pd.code === 200) {
                S.currentProjectId = pd.project.id;
                await createTaskInProject(S.currentProjectId);
            }
        }
        loadProjectsAndTasks();
    } catch(e) {}
}

async function autoRenameTask(tid, history) {
    // Simple rename based on user's first message
    var firstUserMsg = '';
    for (var i = 0; i < history.length; i++) {
        if (history[i].role === 'user' && history[i].message) {
            firstUserMsg = history[i].message;
            break;
        }
    }
    // Take first 20 chars of user message as fallback name
    var fallbackName = firstUserMsg.replace(/[\n\r]/g, ' ').trim().slice(0, 20);
    if (!fallbackName || fallbackName.length < 2) return;

    // Try AI rename via old chat endpoint, fallback to simple truncation
    try {
        var resp = await fetch(API.chatRename, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                history: history.slice(-4),
                newMessage: '请根据以上对话生成一个8-12字的中文标题。简洁概括、无标点。只返回标题。',
                lang: 'zh',
            }),
        });
        if (resp.ok) {
            var d = await resp.json();
            var title = (d.content || '').trim().slice(0, 30);
            if (title && title.length >= 2) {
                await fetch(API.tasks + '/' + tid + '/rename?name=' + encodeURIComponent(title), { method: 'PUT' });
                if (S.currentProjectId) loadTasksForProject(S.currentProjectId);
                return;
            }
        }
    } catch(e) { /* fallback */ }

    // Fallback: use first message as name
    await fetch(API.tasks + '/' + tid + '/rename?name=' + encodeURIComponent(fallbackName), { method: 'PUT' });
    if (S.currentProjectId) loadTasksForProject(S.currentProjectId);
}

function _jc_heuristic_error(result) {
    if (!result) return false;
    if (typeof result !== 'string') return false;
    var head = result.slice(0, 800);
    return /Traceback|ERROR|Error[:\s]|Exception[:\s]|failed|失败|non-zero exit|exit_code[^0]*[1-9]/.test(head);
}
function handleEvent(ev, body) {
    var think = body.querySelector('.jc-think'); if (think) think.remove();
    switch (ev.type) {
        case 'plan': body.appendChild(createPlanCard(ev)); break;
        case 'tool_call': body.appendChild(createToolCard(ev.tool, ev.args)); markPlanStepDone(); break;
        case 'tool_result': {
            var isErr = !!ev.is_error || _jc_heuristic_error(ev.result);
            updateLastToolCard(body, ev.result, isErr);
            break;
        }
        case 'message_chunk': var d = document.createElement('div'); d.innerHTML = renderMD(ev.content); body.appendChild(d); break;
        case 'error': var e = document.createElement('div'); e.style.cssText = 'color:#ef4444;font-size:12px'; e.textContent = '错误: ' + (ev.content || ''); body.appendChild(e); break;
    }
}

function createPlanCard(ev) {
    S.planItems = ev.items || [];
    S.planStepIndex = 0;
    var card = document.createElement('div');
    card.className = 'jc-plan-card';
    card.innerHTML = '<div class="jc-plan-hd"><span style="display:inline-flex;align-items:center;gap:7px">' + SVG.planClipboard + ' 执行计划</span></div>'
        + '<div class="jc-plan-items">' + S.planItems.map(function(s,i) {
            return '<div class="jc-plan-item" data-step="' + i + '"><span class="jc-plan-num">' + (i+1) + '</span><span class="jc-plan-text">' + esc(s) + '</span></div>';
        }).join('') + '</div>';
    if (ev.content) {
        card.innerHTML += '<div class="jc-plan-msg">' + renderMD(ev.content) + '</div>';
    }
    return card;
}

function markPlanStepDone() {
    if (S.planStepIndex < 0 || S.planStepIndex >= S.planItems.length) return;
    var step = document.querySelector('.jc-plan-item[data-step="' + S.planStepIndex + '"]');
    if (step) {
        step.classList.add('done');
        var num = step.querySelector('.jc-plan-num');
        if (num) num.textContent = '✓';
    }
    S.planStepIndex++;
}

function renderHistoryEvent(ev) {
    var box = document.getElementById('chatBox');
    switch (ev.type) {
        case 'user_msg': addMessage('user', ev.message || ''); break;
        case 'plan': box.appendChild(createPlanCard(ev)); break;
        case 'tool_call': box.appendChild(createToolCard(ev.tool, ev.args)); break;
        case 'tool_result': updateLastToolCard(box, ev.result); break;
        case 'message_chunk': addMessage('agent', ev.content); break;
    }
}

// ── 状态 pill 助手 ──────────────────────────────────────────
function setStatus(text, state) {
    var pill = document.getElementById('statusPill');
    if (!pill) return;
    pill.innerText = text;
    pill.title = text;
    pill.style.background = state === 'error' ? 'rgba(239,68,68,.15)' :
                           state === 'busy'  ? 'linear-gradient(135deg,rgba(253,186,116,.2),rgba(139,92,246,.18))' : '';
    pill.style.color = state === 'error' ? '#ef4444' :
                       state === 'busy'  ? '#d97706' : '';
}

// ── 消息 HTML 模板：头像 + 主容器 ───────────────────────────
var AGENT_AVATAR = '<div class="jc-avatar agent" title="Jinclaw" aria-label="Jinclaw">'
    + '<svg viewBox="0 0 64 64" fill="none" aria-hidden="true">'
    + '<defs>'
    + '<linearGradient id="jcAvatarGrad" x1="6" y1="6" x2="58" y2="58" gradientUnits="userSpaceOnUse">'
    + '<stop stop-color="#4c8dff"/><stop offset="0.55" stop-color="#6d5cff"/><stop offset="1" stop-color="#8b5cf6"/>'
    + '</linearGradient>'
    + '</defs>'
    + '<rect x="6" y="6" width="52" height="52" rx="14" stroke="#fff" stroke-width="3.4" opacity="0.95"/>'
    + '<rect x="18" y="22" width="26" height="4" rx="2" fill="#fff" opacity="0.85"/>'
    + '<rect x="18" y="30" width="18" height="4" rx="2" fill="#fff" opacity="0.65"/>'
    + '<rect x="18" y="38" width="22" height="4" rx="2" fill="#fff" opacity="0.45"/>'
    + '<circle cx="46" cy="46" r="8" fill="#fff" opacity="0.95"/>'
    + '<path d="M44 46h4M46 44v4" stroke="url(#jcAvatarGrad)" stroke-width="2.3" stroke-linecap="round"/>'
    + '</svg></div>';
var USER_AVATAR = '<div class="jc-avatar user" title="你" aria-label="你">你</div>';

function addMessage(role, text) {
    var isUser = role === 'user';
    var d = document.createElement('div'); d.className = 'jc-msg ' + role;
    var avatar = isUser ? USER_AVATAR : AGENT_AVATAR;
    var roleName = isUser ? '你' : 'Jinclaw';
    d.innerHTML = avatar
        + '<div class="jc-msg-main">'
            + '<div class="jc-msg-hd"><span class="jc-role">' + roleName + '</span></div>'
            + '<div class="jc-msg-bd">' + (isUser ? esc(text) : renderMD(text)) + '</div>'
        + '</div>';
    document.getElementById('chatBox').appendChild(d);
}
function createAgentMessage() {
    var d = document.createElement('div'); d.className = 'jc-msg agent';
    d.innerHTML = AGENT_AVATAR
        + '<div class="jc-msg-main">'
            + '<div class="jc-msg-hd"><span class="jc-role">Jinclaw</span></div>'
            + '<div class="jc-msg-bd"></div>'
        + '</div>';
    document.getElementById('chatBox').appendChild(d); return d;
}
function createThink() {
    var d = document.createElement('div'); d.className = 'jc-think';
    d.innerHTML = '<span class="jc-think-avatar" aria-hidden="true">'
        + '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>'
        + '</span><span>思考中…</span><div class="jc-think-dots" aria-hidden="true"><b></b><b></b><b></b></div>';
    return d;
}
function createToolCard(name, args) {
    var t0 = new Date();
    var c = document.createElement('div'); c.className = 'jc-tc';
    c.dataset.state = 'running';
    c.innerHTML = '<div class="jc-tc-hd">'
        + '<span class="jc-tc-icon" title="工具调用"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" style="animation:jcSpin 1s linear infinite"><circle cx="12" cy="12" r="9" stroke-dasharray="42" stroke-dashoffset="14"/></svg></span>'
        + '<span class="jc-tc-meta">'
            + '<span class="jc-tc-name">' + esc(name) + '</span>'
            + '<span class="jc-tc-status">执行中…</span>'
        + '</span>'
        + '<span class="jc-tc-time" title="调用时间">' + String(t0.getHours()).padStart(2,'0') + ':' + String(t0.getMinutes()).padStart(2,'0') + '</span>'
        + '<span class="jc-tc-chev">▼</span>'
        + '</div><div class="jc-tc-bd">'
        + (args && Object.keys(args).length ? '<div class="jc-tc-result-block"><div class="jc-tc-block-label">参数</div><pre class="jc-tc-block-pre">' + esc(JSON.stringify(args,null,2)) + '</pre></div>' : '')
        + '</div>';
    c.querySelector('.jc-tc-hd').addEventListener('click', function() { c.classList.toggle('expanded'); });
    return c;
}
function updateLastToolCard(container, result, isError) {
    var cards = container.querySelectorAll('.jc-tc'); var last = cards[cards.length - 1];
    if (!last) return;
    var hasContent = result && String(result).trim().length > 0;
    if (hasContent) {
        var block = document.createElement('div'); block.className = 'jc-tc-result-block';
        var label = document.createElement('div'); label.className = 'jc-tc-block-label';
        label.textContent = isError ? '错误输出' : '执行结果';
        label.style.color = isError ? '#ef4444' : '';
        var pre = document.createElement('pre'); pre.className = 'jc-tc-block-pre' + (isError ? ' err' : '');
        pre.textContent = String(result || '').slice(0, 5000);
        block.appendChild(label); block.appendChild(pre);
        last.querySelector('.jc-tc-bd').appendChild(block);
    }
    var status = last.querySelector('.jc-tc-status');
    var icon = last.querySelector('.jc-tc-icon');
    last.dataset.state = isError ? 'error' : 'done';
    if (status) status.innerText = isError ? '执行失败 ✕' : '执行成功 ✓';
    if (icon) icon.innerHTML = isError
        ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.4" stroke-linecap="round"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>'
        : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    last.classList.add('expanded');
}

var EMPTY_STATE_HTML = '<div class="jc-chat-inner"><div class="jc-empty-state" id="emptyState">'
    + '<div class="jc-empty-logo">'
    + '<svg viewBox="0 0 64 64" fill="none"><rect x="6" y="6" width="52" height="52" rx="14" stroke="#fff" stroke-width="3" opacity="0.95"/>'
    + '<rect x="20" y="22" width="26" height="4" rx="2" fill="#fff" opacity="0.85"/><rect x="20" y="30" width="18" height="4" rx="2" fill="#fff" opacity="0.65"/>'
    + '<rect x="20" y="38" width="22" height="4" rx="2" fill="#fff" opacity="0.45"/>'
    + '<circle cx="46" cy="46" r="8" fill="#fff" opacity="0.95"/>'
    + '<path d="M44 46h4M46 44v4" stroke="#4c8dff" stroke-width="2" stroke-linecap="round"/></svg></div>'
    + '<h2>Jinclaw — 你的代码级 AI 搭档</h2><p>我能直接读写本地文件、运行 Shell / Git 命令、浏览网页、逐行审查代码变更</p>'
    + '<div class="jc-sg-category"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> 快速开始</div>'
    + '<div class="jc-suggestions">'
    + '<button class="jc-sg" type="button" data-text="先列出当前目录（即项目根）的文件结构，然后给我一份项目概览：用了什么技术栈、代码主要分布在哪几个文件夹、入口文件在哪。"><span class="jc-sg-icon">' + SVG.sg_search + '</span><span class="jc-sg-main"><span class="jc-sg-title">认识我的项目</span><span class="jc-sg-desc">扫描目录结构 + 技术栈分析</span></span></button>'
    + '<button class="jc-sg" type="button" data-text="读取 AGENTS.md 的内容，摘要里面关于代码风格、工作流、必须遵守的约束，用 5 条以内要点概括。"><span class="jc-sg-icon">' + SVG.sg_doc + '</span><span class="jc-sg-main"><span class="jc-sg-title">学习开发规范</span><span class="jc-sg-desc">从 AGENTS.md 摘要工作约定</span></span></button>'
    + '<button class="jc-sg" type="button" data-text="请在当前项目下创建一个 hello.py：使用 FastAPI 写一个 GET /health 返回 {status:ok}，然后运行它测试。"><span class="jc-sg-icon">' + SVG.sg_wrench + '</span><span class="jc-sg-main"><span class="jc-sg-title">写一个 HTTP 服务</span><span class="jc-sg-desc">Python FastAPI · 含运行验证</span></span></button>'
    + '<button class="jc-sg" type="button" data-text="检查当前 Git 仓库的状态：列出所有未跟踪 / 已修改 / 已暂存的文件，并对变更做一句话说明。"><span class="jc-sg-icon">' + SVG.sg_branch + '</span><span class="jc-sg-main"><span class="jc-sg-title">查看 Git 变更</span><span class="jc-sg-desc">diff 摘要 + 风险提示</span></span></button>'
    + '</div>'
    + '<div class="jc-sg-category"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg> 深度工作</div>'
    + '<div class="jc-suggestions">'
    + '<button class="jc-sg" type="button" data-text="我想做一个功能。先不要写代码！先给出一份 3-5 步的执行计划，每步标注可能的风险和回滚策略，等我确认再动手。"><span class="jc-sg-icon">' + SVG.sg_plan + '</span><span class="jc-sg-main"><span class="jc-sg-title">先 Plan 再动手</span><span class="jc-sg-desc">把需求拆成可控的小步</span></span></button>'
    + '<button class="jc-sg" type="button" data-text="审查 main.py 的路由注册部分：检查是否有未捕获异常、未授权即可访问的敏感接口、SQL 注入风险。用清单方式列出来，严重程度高的给修复建议。"><span class="jc-sg-icon">' + SVG.sg_shield + '</span><span class="jc-sg-main"><span class="jc-sg-title">代码安全审查</span><span class="jc-sg-desc">查漏洞 → 按严重分级</span></span></button>'
    + '</div></div></div>';

function clearChat() {
    S.chatHistory = []; S.planItems = []; S.planStepIndex = -1;
    document.getElementById('chatBox').innerHTML = EMPTY_STATE_HTML;
}
function bindSuggestions() { /* placeholder for future rebind */ }

function scrollChat() { var b = document.getElementById('chatBox'); b.scrollTop = b.scrollHeight; }

// ── Tabs ────────────────────────────────────────────────────
// ── Preview ─────────────────────────────────────────────────
// Dropdown 菜单传入 e.target.dataset.add ∈ { 'browser', 'terminal' }
function addPreviewTab(e) {
    var kind;
    // 优先取 dataset.add（dropdown 项 / 主按钮都可能带）
    try {
        if (e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.add) kind = e.currentTarget.dataset.add;
    } catch(_) {}
    if (!kind) {
        try {
            var fake = e.currentTarget && e.currentTarget.getAttribute && e.currentTarget.getAttribute('data-add');
            if (fake) kind = fake;
        } catch(_) {}
    }
    // 兜底：如果是 addMain 按钮点击，默认浏览器
    if (!kind) kind = 'browser';
    if (kind === 'terminal') addTerminalTab();
    else addBrowserTab();
}

function addBrowserTab() {
    var idx = S.browserTabCount++, id = 'browser-' + idx;
    var tabs = document.getElementById('prevTabsInner');
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'jc-prev-tab';
    btn.dataset.prev = id;
    btn.innerHTML = SVG.browser + '<span class="jc-tab-badge" style="display:none;margin-left:4px">' + idx + '</span>';
    btn.title = '浏览器 ' + idx;
    // Insert before last element (terminal tab area)
    var terminalTab = tabs.querySelector('[data-prev^="terminal"]');
    if (terminalTab) tabs.insertBefore(btn, terminalTab);
    else tabs.appendChild(btn);

    var content = document.createElement('div'); content.className = 'jc-prev-content'; content.id = 'prev-' + id;
    content.innerHTML = '<div class="jc-browser-bar">'
        + SVG.browser.replace('width="14"','width="13"').replace('height="14"','height="13"')
        + '<input type="text" class="jc-browser-url jc-browser-url-' + idx + '" value="about:blank" placeholder="输入 URL 并回车">'
        + '<button type="button" class="jc-icon-btn jc-browser-refresh-' + idx + '" title="刷新" aria-label="刷新">' + SVG.refresh + '</button>'
        + '<button type="button" class="jc-icon-btn jc-br-close" title="关闭" aria-label="关闭" style="color:#ef4444">' + SVG.close + '</button>'
        + '</div><iframe class="jc-browser-iframe" id="browserFrame-' + idx + '" src="' + BLANK_BROWSER_SRC + '" sandbox="allow-scripts allow-forms allow-same-origin allow-popups allow-modals"></iframe>';
    document.getElementById('previewPanel').appendChild(content);
    var ui = content.querySelector('.jc-browser-url'), ifr = content.querySelector('.jc-browser-iframe');
    ui.addEventListener('keydown', function(e) {
      if (e.key !== 'Enter') return;
      var v = (ui.value || '').trim();
      if (!v || v === 'about:blank') { ifr.src = BLANK_BROWSER_SRC; return; }
      ifr.src = v;
    });
    content.querySelector('.jc-browser-refresh-' + idx).addEventListener('click', function() {
      var v = (ui.value || '').trim();
      if (!v || v === 'about:blank') { ifr.src = BLANK_BROWSER_SRC; return; }
      ifr.src = v;
    });
    content.querySelector('.jc-br-close').addEventListener('click', function() {
        content.remove(); btn.remove();
        var first = document.querySelector('.jc-prev-tab[data-prev^="browser"]');
        if (first) first.click();
        else {
            var t = document.querySelector('.jc-prev-tab[data-prev^="terminal"]');
            if (t) t.click();
        }
    });
    btn.click();
}

function addTerminalTab() {
    var idx = S.browserTabCount++, id = 'terminal-' + idx;
    var tabs = document.getElementById('prevTabsInner');
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'jc-prev-tab';
    btn.dataset.prev = id;
    btn.innerHTML = SVG.terminal;
    btn.title = 'PowerShell ' + idx;
    // Insert before the original terminal tab (keep it last)
    var origTerminal = tabs.querySelector('[data-prev="terminal"]');
    if (origTerminal) tabs.insertBefore(btn, origTerminal);
    else tabs.appendChild(btn);

    var content = document.createElement('div'); content.className = 'jc-prev-content'; content.id = 'prev-' + id;
    content.innerHTML = '<div class="jc-term-bar"><span class="jc-term-cwd" style="color:var(--accent)">PowerShell</span> <span class="jc-term-cwd-term' + idx + '" style="color:var(--text-muted)">' + esc(S.workspace || '~') + '</span></div>'
        + '<div class="jc-term-mount jc-term-mount-' + idx + '"><div class="jc-term-placeholder"><pre>PowerShell 终端 #' + idx + '\n───────────────\n输入命令并按 Enter 执行。\n输入 \'clear\' 清屏。</pre></div></div>'
        + '<div class="jc-term-input-row">'
        + SVG.terminal.replace('width="14"','width="12"').replace('height="14"','height="12"').replace(/stroke-width="2"/,'stroke-width="3"')
        + '<input type="text" class="jc-term-input jc-term-input-' + idx + '" placeholder="输入命令..." autocomplete="off" spellcheck="false">'
        + '</div>';
    document.getElementById('previewPanel').appendChild(content);

    var input = content.querySelector('.jc-term-input');
    input.addEventListener('keydown', function(e) { handleTerminalKeyGeneric(e, idx); });
    btn.click();
}

// Generic terminal handler for multi-tab terminals
function handleTerminalKeyGeneric(e, idx) {
    if (e.key === 'Enter') {
        var cmd = e.target.value.trim(); if (!cmd) return;
        S.termHistory.push(cmd); S.termHistoryIdx = S.termHistory.length; e.target.value = '';
        execTermCmdGeneric(cmd, idx);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (S.termHistoryIdx > 0) { S.termHistoryIdx--; e.target.value = S.termHistory[S.termHistoryIdx] || ''; }
    } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (S.termHistoryIdx < S.termHistory.length - 1) { S.termHistoryIdx++; e.target.value = S.termHistory[S.termHistoryIdx] || ''; }
        else { S.termHistoryIdx = S.termHistory.length; e.target.value = ''; }
    }
}

async function execTermCmdGeneric(cmd, idx) {
    var term = document.querySelector('.jc-term-mount-' + idx); if (!term) return;
    var ph = term.querySelector('.jc-term-placeholder'); if (ph) ph.style.display = 'none';
    if (cmd === 'clear' || cmd === 'cls') { term.querySelectorAll('.jc-term-output,.jc-term-cmd').forEach(function(el){el.remove()}); return; }
    var cwd = S.terminalCdMap[idx] || S.workspace || '.';
    var cmdEl = document.createElement('div'); cmdEl.className = 'jc-term-cmd'; cmdEl.textContent = 'PS> ' + cmd;
    term.appendChild(cmdEl); term.scrollTop = term.scrollHeight;
    try {
        // Run command + echo cwd for cd tracking
        var fullCmd = cmd + '; if ($?) { $global:LASTEXITCODE = 0 }; Write-Host "%%CWD%%$(Get-Location)"';
        var resp = await fetch(API.shell + '?command=' + encodeURIComponent(fullCmd) + '&cwd=' + encodeURIComponent(cwd) + '&shell_type=powershell');
        var d = await resp.json();
        var outText = (d.stdout || '') + (d.stderr || '');
        // Extract and hide the cwd marker line
        var cwdMatch = outText.match(/%%CWD%%.*/);
        if (cwdMatch) {
            var newCwd = cwdMatch[0].replace('%%CWD%%', '').trim();
            if (newCwd) { S.terminalCdMap[idx] = newCwd; var cwdEl = document.querySelector('.jc-term-cwd-term' + idx); if (cwdEl) cwdEl.textContent = newCwd; }
            outText = outText.replace(/%%CWD%%.*/g, '').trim();
        }
        var out = document.createElement('div'); out.className = 'jc-term-output ' + (d.exit_code === 0 ? 'stdout' : 'stderr');
        out.textContent = outText || '(无输出)'; term.appendChild(out); term.scrollTop = term.scrollHeight;
    } catch(e) { var er = document.createElement('div'); er.className = 'jc-term-output stderr'; er.textContent = '错误: ' + e.message; term.appendChild(er); }
}

// Keep original execTermCmd for the first terminal tab
async function execTermCmd(cmd) { execTermCmdGeneric(cmd, 0); }

// Wire first terminal
(function w0(){ var t0 = document.getElementById('termInput'); if (t0) t0.addEventListener('keydown', function(e) { handleTerminalKeyGeneric(e, 0); }); })();
function togglePreviewPanel() {
    var panel = document.getElementById('previewPanel');
    panel.style.display = panel.style.display === 'none' ? '' : 'none';
    document.querySelector('.jc-shell').style.gridTemplateColumns = panel.style.display === 'none' ? '280px 1fr' : '280px 1fr 1fr';
}
(function wireB0(){
    var u=document.querySelector('.jc-browser-url-0'),f=document.getElementById('browserFrame-0');
    if(!u||!f)return;
    // 启动时立刻把默认 about:blank 换成动画占位页（消除白底闪烁）
    try { f.src = BLANK_BROWSER_SRC; } catch(_) {}
    // 当用户在 URL 框里输入 about:blank 回车时，也回填动画页而不是原生白底
    u.addEventListener('keydown',function(e){
      if(e.key!=='Enter')return;
      var v=(u.value||'').trim();
      if(!v || v==='about:blank' || v==='about:blank/'){ f.src=BLANK_BROWSER_SRC; return; }
      f.src=v;
    });
    var r=document.querySelector('.jc-browser-refresh-0');
    if(r)r.addEventListener('click',function(){
      var v=(u.value||'').trim();
      if(!v || v==='about:blank'){ f.src=BLANK_BROWSER_SRC; return; }
      f.src=v;
    });
})();

// ── Terminal ────────────────────────────────────────────────
function handleTerminalKey(e) {
    if (e.key === 'Enter') { var cmd = e.target.value.trim(); if (!cmd) return; S.termHistory.push(cmd); S.termHistoryIdx = S.termHistory.length; e.target.value = ''; execTermCmd(cmd); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); if (S.termHistoryIdx > 0) { S.termHistoryIdx--; e.target.value = S.termHistory[S.termHistoryIdx] || ''; } }
    else if (e.key === 'ArrowDown') { e.preventDefault(); if (S.termHistoryIdx < S.termHistory.length - 1) { S.termHistoryIdx++; e.target.value = S.termHistory[S.termHistoryIdx] || ''; } else { S.termHistoryIdx = S.termHistory.length; e.target.value = ''; } }
}
async function execTermCmd(cmd) {
    var term = document.getElementById('terminal'), ph = document.getElementById('termPlaceholder');
    if (ph) ph.style.display = 'none';
    if (cmd === 'clear' || cmd === 'cls') { term.querySelectorAll('.jc-term-output,.jc-term-cmd').forEach(function(el){el.remove()}); return; }
    var cwd = getWorkspace() || '.';
    var cmdEl = document.createElement('div'); cmdEl.className = 'jc-term-cmd'; cmdEl.textContent = '> ' + cmd; term.appendChild(cmdEl); term.scrollTop = term.scrollHeight;
    try {
        var resp = await fetch(API.shell + '?command=' + encodeURIComponent(cmd) + '&cwd=' + encodeURIComponent(cwd));
        var d = await resp.json();
        var out = document.createElement('div'); out.className = 'jc-term-output ' + (d.exit_code === 0 ? 'stdout' : 'stderr');
        out.textContent = d.stdout || d.stderr || '(无输出)'; term.appendChild(out); term.scrollTop = term.scrollHeight;
        updateTermCwd();
    } catch(e) { var er = document.createElement('div'); er.className = 'jc-term-output stderr'; er.textContent = '错误: ' + e.message; term.appendChild(er); }
}

// ── Helpers ─────────────────────────────────────────────────
function _jc_detect_lang(classAttr) {
    if (!classAttr) return '';
    var m = classAttr.match(/language-([\w+-]+)/i);
    return m ? m[1] : '';
}

function renderMD(text) {
    if (typeof marked === 'undefined') return esc(text);
    marked.setOptions({ breaks: true, gfm: true });
    var raw = marked.parse(text);

    // Wrap in a div to query-select all pre > code blocks, then inject language bar + copy btn
    var tmp = document.createElement('div');
    tmp.innerHTML = raw;
    tmp.querySelectorAll('pre').forEach(function(pre) {
        if (pre.querySelector('.jc-code-lang')) return; // already processed
        var code = pre.querySelector('code');
        var lang = code ? _jc_detect_lang(code.className) : '';
        if (code && !lang) lang = 'text';

        var bar = document.createElement('div');
        bar.className = 'jc-code-lang';
        var left = document.createElement('span');
        left.textContent = lang || 'text';
        var copyBtn = document.createElement('button');
        copyBtn.className = 'jc-code-copy';
        copyBtn.type = 'button';
        copyBtn.dataset.lang = lang || 'text';
        copyBtn.textContent = '复制';
        bar.appendChild(left);
        bar.appendChild(copyBtn);

        pre.insertBefore(bar, pre.firstChild);
    });
    return tmp.innerHTML;
}
function esc(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

// =============================================================
// 附件：文件 + 截图统一管理
// =============================================================
function _addAttachmentFromFile(file) {
    if (!file) return;
    S.attachments = S.attachments || [];
    // 图片类：生成预览 dataURL
    var isImg = /^image\//.test(file.type) || /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(file.name || '');
    var rec = { file: file, name: file.name, size: file.size, kind: isImg ? 'image' : 'file', preview: null };
    if (isImg) {
        try {
            var reader = new FileReader();
            reader.onload = function(ev) { rec.preview = ev.target && ev.target.result; renderAttachments(); };
            reader.readAsDataURL(file);
        } catch(_) {}
    }
    S.attachments.push(rec);
}
function _fileToBase64(file) {
    return new Promise(function(resolve, reject) {
        var r = new FileReader();
        r.onload = function() { resolve(r.result); };
        r.onerror = function() { reject(r.error || new Error('read_fail')); };
        r.readAsDataURL(file);
    });
}
function renderAttachments() {
    var wrap = document.getElementById('attachmentsPreview');
    if (!wrap) return;
    wrap.innerHTML = '';
    if (!S.attachments || S.attachments.length === 0) { wrap.style.display = 'none'; return; }
    wrap.style.display = '';
    var closeSvg = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    S.attachments.forEach(function(a, idx) {
        var item = document.createElement('div');
        item.className = 'jc-att-item';
        if (a.kind === 'image' && a.preview) {
            var img = document.createElement('img');
            img.src = a.preview;
            img.alt = a.name || 'screenshot';
            item.appendChild(img);
        } else {
            var f = document.createElement('div');
            f.className = 'jc-att-file';
            f.innerHTML = SVG.file + '<div class="jc-att-name" title="' + esc(a.name || '') + '">' + esc(a.name || '文件') + '</div>';
            item.appendChild(f);
        }
        var del = document.createElement('button');
        del.className = 'jc-att-del'; del.type = 'button'; del.title = '移除附件';
        del.innerHTML = closeSvg;
        del.addEventListener('click', function(e) {
            e.preventDefault(); e.stopPropagation();
            S.attachments.splice(idx, 1);
            renderAttachments();
        });
        item.appendChild(del);
        wrap.appendChild(item);
    });
}

// =============================================================
// 截图功能：真实 getDisplayMedia 捕获屏幕，生成 Blob 附件
// =============================================================
async function takeScreenshotAndAttach() {
    var statusPill = document.getElementById('statusPill');
    if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        alert('当前浏览器不支持屏幕截取 API。请使用最新版 Chrome / Edge。');
        return;
    }
    try {
        if (statusPill) { statusPill.textContent = '正在选择屏幕…'; statusPill.dataset.state = 'warn'; }
        var stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
        var track = stream.getVideoTracks()[0];
        if (!track) return;
        // 用 ImageCapture 或 canvas 抓一帧
        var video = document.createElement('video');
        video.autoplay = true;
        video.muted = true;
        video.srcObject = stream;
        await new Promise(function(res, rej) {
            video.onloadedmetadata = function() { try { video.play(); setTimeout(res, 180); } catch(e) { res(); } };
            video.onerror = rej;
        });
        var canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        // 停掉 stream
        try { track.stop(); stream.getTracks().forEach(function(t){t.stop();}); video.srcObject = null; } catch(_) {}

        var dataUrl = canvas.toDataURL('image/png');
        canvas.toBlob(function(blob) {
            if (!blob) return;
            var file = new File([blob], 'screenshot_' + Date.now() + '.png', { type: 'image/png' });
            S.attachments = S.attachments || [];
            S.attachments.push({ file: file, preview: dataUrl, kind: 'image' });
            renderAttachments();
            if (statusPill) { statusPill.textContent = '截图已附加'; statusPill.dataset.state = 'ok'; }
            setTimeout(function() { if (statusPill) statusPill.textContent = '就绪'; }, 1600);
        }, 'image/png');
    } catch(e) {
        if (statusPill) statusPill.textContent = '就绪';
        if (e && (e.name === 'NotAllowedError' || e.message && e.message.indexOf('denied') !== -1)) return; // 用户取消不提示
        console.error('[screenshot]', e);
    }
}

// =============================================================
// 三栏 Resizer 拖拽（直接改 CSS var）
// =============================================================
function bindResizers() {
    var minLeft = 200, maxLeft = 560;
    var minRight = 260, maxRight = 900;
    var root = document.documentElement;
    var left = document.querySelector('.jc-resizer-left');
    var right = document.querySelector('.jc-resizer-right');
    function bindOne(el, dir) {
        if (!el) return;
        el.addEventListener('mousedown', function(e) {
            e.preventDefault();
            el.classList.add('active');
            document.body.style.cursor = 'col-resize';
            var startX = e.clientX;
            var startLeftPx = -1, startRightPx = -1;
            try {
                var cs = getComputedStyle(root);
                startLeftPx = parseFloat(cs.getPropertyValue('--jc-panel-left'));
                startRightPx = parseFloat(cs.getPropertyValue('--jc-panel-right'));
            } catch(_) {}
            if (isNaN(startLeftPx)) startLeftPx = 260;
            if (isNaN(startRightPx)) startRightPx = 400;
            function onMove(ev) {
                var dx = ev.clientX - startX;
                if (dir === 'left') {
                    var nL = Math.max(minLeft, Math.min(maxLeft, startLeftPx + dx));
                    root.style.setProperty('--jc-panel-left', nL + 'px');
                } else {
                    // 右 resizer：向右拉 → right 变小（因为增加 1fr）
                    var nR = Math.max(minRight, Math.min(maxRight, startRightPx - dx));
                    root.style.setProperty('--jc-panel-right', nR + 'px');
                }
            }
            function onUp() {
                document.removeEventListener('mousemove', onMove);
                document.removeEventListener('mouseup', onUp);
                el.classList.remove('active');
                document.body.style.cursor = '';
            }
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        });
    }
    bindOne(left, 'left');
    bindOne(right, 'right');
}

// =============================================================
// 右键菜单（文件树）
// =============================================================
var _ctxTarget = null;
function bindContextMenu() {
    document.addEventListener('click', hideCtxMenu);
    document.addEventListener('keydown', function(e) { if (e.key === 'Escape') hideCtxMenu(); });
    var menu = document.getElementById('ctxMenu');
    if (!menu) return;
    menu.addEventListener('click', function(e) {
        var item = e.target.closest && e.target.closest('.jc-ctx-item');
        if (!item || !_ctxTarget) return;
        e.stopPropagation();
        ctxActionHandler(item.dataset.action, _ctxTarget);
        hideCtxMenu();
    });
}
function showCtxMenu(x, y, meta) {
    var menu = document.getElementById('ctxMenu');
    if (!menu) return;
    _ctxTarget = meta;
    menu.style.display = '';
    var vw = window.innerWidth, vh = window.innerHeight;
    var mw = menu.offsetWidth, mh = menu.offsetHeight;
    if (x + mw + 8 > vw) x = Math.max(0, vw - mw - 8);
    if (y + mh + 8 > vh) y = Math.max(0, vh - mh - 8);
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
}
function hideCtxMenu() {
    var menu = document.getElementById('ctxMenu');
    if (menu) menu.style.display = 'none';
    _ctxTarget = null;
}
async function ctxActionHandler(action, meta) {
    if (!meta) return;
    var path = meta.path, name = meta.name, isDir = !!meta.isDir;
    switch(action) {
        case 'copy_path':
            try { await navigator.clipboard.writeText(path || name); showTempStatus('路径已复制'); }
            catch(_) { showTempStatus('复制失败'); }
            break;
        case 'add_to_chat':
            var ui = document.getElementById('userInput');
            if (ui) {
                var cur = ui.value ? ui.value + '\n' : '';
                ui.value = cur + '（文件路径：' + (path || name) + '）';
                ui.focus();
            }
            showTempStatus('已加入对话');
            break;
        case 'explore':
            try {
                var r = await fetch(API.wsFsAction, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'explore', path: path })
                });
                var d = await r.json();
                if (d.code !== 200) showTempStatus('无法打开资源管理器：' + (d.detail?.msg || d.detail || ''));
                else showTempStatus('已打开');
            } catch(e) { showTempStatus('打开失败'); }
            break;
        case 'rename':
            var newName = window.prompt('重命名', name);
            if (!newName || newName === name) return;
            try {
                var r = await fetch(API.wsFsAction, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'rename', path: path, new_name: newName })
                });
                var d = await r.json();
                if (d.code !== 200) { showTempStatus('重命名失败：' + (d.detail?.msg || d.detail || '')); return; }
                refreshFileTree();
            } catch(e) { showTempStatus('重命名失败'); }
            break;
        case 'delete':
            var ok = window.confirm('确定删除 ' + (isDir ? '文件夹 ' : '文件 ') + (name || path) + '？此操作不可撤销。');
            if (!ok) return;
            try {
                var r = await fetch(API.wsFsAction, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'delete', path: path })
                });
                var d = await r.json();
                if (d.code !== 200) { showTempStatus('删除失败：' + (d.detail?.msg || d.detail || '')); return; }
                // 多 Tab 模式：如果被删的文件在 openFiles 中（不管是否激活），都把对应的 Tab 关掉
                var isOpened = (S.openFiles || []).some(function(f) { return f.path === path; });
                if (isOpened) closeEditorTab(path);
                refreshFileTree();
                showTempStatus('已删除');
            } catch(e) { showTempStatus('删除失败'); }
            break;
    }
}
function showTempStatus(msg) {
    var p = document.getElementById('statusPill');
    if (!p) return;
    var orig = p.textContent;
    p.textContent = msg;
    p.dataset.state = 'warn';
    clearTimeout(showTempStatus._t);
    showTempStatus._t = setTimeout(function() { p.textContent = orig || '就绪'; p.dataset.state = ''; }, 1800);
}

// =============================================================
// 内嵌登录/注册弹窗：网页端 + Tauri 端统一入口，不依赖 window.open / 不跳转页面
// =============================================================
function showInlineLoginDialog(initialTab) {
    var dlg = document.getElementById('loginDialog');
    if (!dlg) return openGlobalLoginOrRedirect_fallback();
    initialTab = initialTab || 'login';
    // tab reset
    dlg.querySelectorAll('.jc-login-tab').forEach(function(t) {
        t.classList.toggle('active', t.dataset.tab === initialTab);
    });
    var confirmPwdField = dlg.querySelector('[data-register-only]');
    if (confirmPwdField) confirmPwdField.style.display = initialTab === 'register' ? '' : 'none';
    var submitLabel = dlg.querySelector('.jc-login-submit-label');
    if (submitLabel) submitLabel.textContent = initialTab === 'register' ? '创建账户' : '登 录';
    // 错误信息 & 表单清空
    var errEl = dlg.querySelector('#loginErrorMsg');
    if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
    var form = dlg.querySelector('#loginForm');
    if (form) {
        form.reset();
        var firstInput = form.querySelector('input[name="username"]');
        setTimeout(function() { if (firstInput) firstInput.focus({ preventScroll: true }); }, 60);
    }
    dlg.style.display = '';
    document.body.style.overflow = 'hidden';
}
function hideInlineLoginDialog() {
    var dlg = document.getElementById('loginDialog');
    if (!dlg) return;
    dlg.style.display = 'none';
    document.body.style.overflow = '';
}

function bindInlineLoginDialog() {
    var dlg = document.getElementById('loginDialog');
    if (!dlg) return;

    // 关闭按钮
    var closeBtn = dlg.querySelector('#loginCloseBtn');
    if (closeBtn) closeBtn.addEventListener('click', hideInlineLoginDialog);
    // 点击遮罩层（非卡片区域）关闭
    dlg.addEventListener('click', function(e) {
        if (e.target === dlg) hideInlineLoginDialog();
    });
    // Esc 关闭
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && dlg.style.display !== 'none') hideInlineLoginDialog();
    });
    // Tab 切换
    dlg.querySelectorAll('.jc-login-tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            var which = tab.dataset.tab;
            dlg.querySelectorAll('.jc-login-tab').forEach(function(t) { t.classList.toggle('active', t === tab); });
            var confirmPwdField = dlg.querySelector('[data-register-only]');
            if (confirmPwdField) confirmPwdField.style.display = which === 'register' ? '' : 'none';
            var submitLabel = dlg.querySelector('.jc-login-submit-label');
            if (submitLabel) submitLabel.textContent = which === 'register' ? '创建账户' : '登 录';
            var errEl = dlg.querySelector('#loginErrorMsg');
            if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
        });
    });

    // 表单提交：登录 or 注册
    var form = dlg.querySelector('#loginForm');
    var submitBtn = dlg.querySelector('#loginSubmitBtn');
    var errEl = dlg.querySelector('#loginErrorMsg');
    if (!form) return;

    function _setBusy(busy, msg) {
        if (submitBtn) {
            submitBtn.disabled = !!busy;
            var spinner = submitBtn.querySelector('.jc-login-submit-spinner');
            var label = submitBtn.querySelector('.jc-login-submit-label');
            if (spinner) spinner.style.display = busy ? '' : 'none';
            if (label) label.style.opacity = busy ? .7 : '';
        }
        if (errEl) {
            if (!msg) { errEl.style.display = 'none'; errEl.textContent = ''; }
            else { errEl.style.display = ''; errEl.textContent = msg; }
        }
    }

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        e.stopPropagation();
        var activeTab = (dlg.querySelector('.jc-login-tab.active') || {}).dataset.tab || 'login';
        var fd = new FormData(form);
        var username = String(fd.get('username') || '').trim();
        var password = String(fd.get('password') || '');
        var password2 = String(fd.get('password2') || '');

        if (username.length < 2) return _setBusy(false, '请输入用户名/手机号');
        if (password.length < 6) return _setBusy(false, '密码至少 6 位');
        if (activeTab === 'register') {
            if (password !== password2) return _setBusy(false, '两次输入的密码不一致');
        }

        _setBusy(true); // 开始 loading

        try {
            var endpoint = activeTab === 'register' ? '/register' : '/login';
            var payload = { username: username, password: password };
            var resp = await fetch(endpoint, {
                method: 'POST',
                credentials: 'include', // 允许浏览器写入响应 Set-Cookie（jingent_token HTTP-only）
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                body: JSON.stringify(payload),
            });
            var text = await resp.text();
            var data = null;
            try { data = JSON.parse(text); } catch(_) { data = { msg: '服务器返回了非 JSON 响应: ' + text.slice(0, 80) }; }

            if (!resp.ok || !data || data.code !== 200) {
                var msg = data && (data.msg || data.message) ? (data.msg || data.message) : ('请求失败 HTTP ' + resp.status);
                return _setBusy(false, msg);
            }

            // 成功：同步 token 到 localStorage — 必须同时写入 chat 页面的通用 key（token / username / user_id）才能跨 tab 共享登录态
            var token = data && data.token;
            if (token) {
                // chat 通用 key（LoginRegister.js / floatDock.js / fileAttachment.js 等都读这个）
                try { localStorage.setItem('token', token); } catch(_) {}
                // jinclaw 自有的冗余 key
                try { localStorage.setItem('jingent_token', token); } catch(_) {}
                try { localStorage.setItem('auth_token', token); } catch(_) {}
            }
            if (data.user_id) {
                try { localStorage.setItem('user_id', String(data.user_id)); } catch(_) {}
                try { localStorage.setItem('jingent_uid', String(data.user_id)); } catch(_) {}
            }
            if (data.username) {
                try { localStorage.setItem('username', String(data.username)); } catch(_) {}
                try { localStorage.setItem('jingent_uname', String(data.username)); } catch(_) {}
            }

            // 强制刷新 profile（读 cookie + header 双渠道）
            try { syncUserProfileGlobally && await syncUserProfileGlobally(); } catch(_) {}

            // 通知其他 tab / chat 页面：storage 事件 + postMessage
            try {
                // 写一个 timestamp 键触发 storage event
                localStorage.setItem('jingent_login_at', String(Date.now()));
            } catch(_) {}
            try { window.postMessage({ type: 'jingent:login', token: token || null }, location.origin); } catch(_) {}

            _setBusy(false);
            hideInlineLoginDialog();
            showTempStatus(activeTab === 'register' ? '注册并登录成功 ✓' : '登录成功 ✓', 'success');
        } catch(err) {
            return _setBusy(false, '网络错误: ' + (err && err.message ? err.message : String(err)));
        }
    });
}

// =============================================================
// 登录：优先用内嵌 dialog；都不可用再走 chat 弹窗 / window.open / 同窗口跳转
// =============================================================
function openGlobalLoginOrRedirect() {
    // 1) 优先用内嵌登录弹窗 — 不跳页面、不依赖 window.open，Tauri 和浏览器端通用
    if (document.getElementById('loginDialog')) {
        showInlineLoginDialog('login');
        return;
    }
    openGlobalLoginOrRedirect_fallback();
}
function openGlobalLoginOrRedirect_fallback() {
    // 2) 如果 chat 页面注册过全局 openLoginModal（theme-bar.js / page_chat.js 里挂在 window），直接调用
    if (typeof window.openLoginModal === 'function') {
        try { window.openLoginModal(syncUserProfileGlobally); return; } catch(_) {}
    }
    // 3) 如果有 loginBtnFromHome / showLoginModal 等变体
    if (typeof window.showLoginModal === 'function') { try { window.showLoginModal(syncUserProfileGlobally); return; } catch(_) {} }
    // 4) 兜底：跳转到 /?force_login=1 并带上返回 URL，登录后跳回来
    var back = encodeURIComponent(location.pathname + location.search);
    var loginUrl = '/?force_login=1&next=' + back;
    // 优先用宽度 520×640 的居中小窗（如果允许 open）
    try {
        var w = 520, h = 640;
        var l = (screen.availWidth - w) / 2, t = Math.max(40, (screen.availHeight - h) / 2 - 40);
        var child = window.open(loginUrl, 'jingent_login_popup', 'width='+w+',height='+h+',left='+l+',top='+t+',menubar=no,toolbar=no,location=yes,status=no,resizable=yes,scrollbars=yes');
        if (child) {
            var _timer = setInterval(function() {
                try {
                    if (child.closed) { clearInterval(_timer); syncUserProfileGlobally(); }
                } catch(_) { clearInterval(_timer); syncUserProfileGlobally(); }
            }, 600);
            return;
        }
    } catch(_) {}
    // 5) 再兜底：同窗口跳转
    location.href = loginUrl;
}

// =============================================================
// 全局用户状态同步：读取当前登录 cookie / 调 /api/me，然后刷新 userProfileBar
// =============================================================
var _lastSyncUid = null;
async function syncUserProfileGlobally() {
    var nameEl = document.getElementById('userNameText');
    var quotaEl = document.getElementById('userQuotaText');
    var loginBtn = document.getElementById('openLoginBtnInner');
    var avatarWrap = document.querySelector('.jc-up-avatar');
    try {
        // 同时尝试：/user/info → /api/me，带 Authorization 头（读 localStorage token）+ cookie
        var resp = fetch('/user/info?ts=' + Date.now(), {
            credentials: 'include',
            headers: _authHeaders(),
        }).then(function(r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .catch(function() {
            return fetch('/api/me?ts=' + Date.now(), {
                credentials: 'include',
                headers: _authHeaders(),
            }).then(function(r2) { return r2.ok ? r2.json() : Promise.reject(r2.status); });
        });
        var d = await resp;
        var me = (d && d.data) || d || null;
        if (me && (me.username || me.nickname || me.phone || me.uid || me.id)) {
            // 已登录
            var uidKey = me.uid || me.id || me.username || null;
            var changedUser = (_lastSyncUid !== null) && (_lastSyncUid !== uidKey);
            var firstLogin = (_lastSyncUid === null) && uidKey;
            var displayName = me.nickname || me.username || me.phone || ('用户 ' + (me.uid || me.id || ''));
            if (nameEl) { nameEl.textContent = displayName; nameEl.removeAttribute('data-i18n'); }
            var quotaText = '免费';
            if (me.plan && me.plan !== 'free') quotaText = me.plan_name || me.plan;
            else if (typeof me.credits === 'number' || (me.quota && typeof me.quota.balance === 'number')) {
                var bal = (typeof me.credits === 'number') ? me.credits : me.quota.balance;
                quotaText = bal + ' 积分';
            }
            if (quotaEl) quotaEl.textContent = quotaText;
            if (loginBtn) { loginBtn.style.display = 'none'; }
            // 头像：有 avatar URL 就替换 SVG 为 <img>
            if (avatarWrap && me.avatar) {
                var hasImg = avatarWrap.querySelector('img');
                if (!hasImg) {
                    avatarWrap.innerHTML = '';
                    var img = document.createElement('img');
                    img.src = me.avatar;
                    img.alt = displayName;
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.borderRadius = '50%';
                    img.style.objectFit = 'cover';
                    avatarWrap.appendChild(img);
                }
            }
            // ============== 账号切换：清空上一个用户的所有 UI/缓存 ==============
            if (changedUser) {
                _resetAllUserState();
            }
            if (changedUser || firstLogin) {
                // 拉取当前这个用户的项目/任务（重渲染左侧栏）
                try { if (typeof loadProjectsAndTasks === 'function') await loadProjectsAndTasks(); } catch(_) {}
            }
            _lastSyncUid = uidKey;
            return;
        }
    } catch(_) {}
    // 未登录
    var wasLoggedIn = _lastSyncUid !== null;
    if (nameEl) { nameEl.textContent = nameEl.dataset.i18n === 'not_logged_in' ? '未登录' : (nameEl.textContent || '未登录'); }
    if (quotaEl) quotaEl.textContent = '—';
    if (loginBtn) { loginBtn.style.display = ''; }
    if (avatarWrap && avatarWrap.querySelector('img')) {
        avatarWrap.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
    }
    // 已登录→登出：清空缓存态 + 重拉（匿名/未登录用户只会看到自己 user_id=NULL 的项目）
    if (wasLoggedIn) {
        _resetAllUserState();
        try { if (typeof loadProjectsAndTasks === 'function') await loadProjectsAndTasks(); } catch(_) {}
    }
    _lastSyncUid = null;
}

/** 切号/登出时重置所有「用户专属」的运行态内存与可见 UI，防止上一个账号残留。 */
function _resetAllUserState() {
    // 1) 对话历史
    try { S.chatHistory = []; } catch(_) {}
    try { S.currentTaskId = null; } catch(_) {}
    try { S.currentProjectId = null; } catch(_) {}
    try {
        if (S.lastTaskId) { try { localStorage.removeItem('jinclaw_lastTaskId'); } catch(_) {} }
        if (S.lastProjectId) { try { localStorage.removeItem('jinclaw_lastProjectId'); } catch(_) {} }
        S.lastTaskId = null;
        S.lastProjectId = null;
    } catch(_) {}
    try { clearChat && clearChat(); } catch(_) {}
    // 2) 编辑器打开的文件 Tab / 内容
    try {
        S.openFiles = [];
        S.currentFile = null;
        S.editorOriginal = '';
        var cc = document.getElementById('editorContainer');
        var ph = document.getElementById('codePlaceholder');
        var mt = document.getElementById('editorMount');
        var tabs = document.getElementById('jcEditorTabs');
        if (cc) cc.style.display = 'none';
        if (ph) ph.style.display = '';
        if (mt) mt.innerHTML = '';
        if (tabs) tabs.innerHTML = '';
        if (typeof updateCodeBadge === 'function') updateCodeBadge();
    } catch(_) {}
    // 3) 聊天区空白态
    try {
        var empty = document.getElementById('emptyState');
        if (empty) empty.style.display = '';
    } catch(_) {}
}

// init 收尾：profile 初始化 + 登录状态事件监听
var _origInitTail = null;
(function wrapInitForProfile() {
    var orig = window.init;
    if (typeof orig !== 'function') return;
    window.init = function() {
        var ret = orig.apply(this, arguments);
        // 登录按钮、用户状态栏同步：立即 + 每 15s + postMessage
        syncUserProfileGlobally();
        clearInterval(window._profileSync);
        window._profileSync = setInterval(syncUserProfileGlobally, 15000);
        window.addEventListener('storage', function(ev) {
            if (!ev) return;
            if (ev.key === 'jingent_user' || ev.key === 'jingent_session' || ev.key === 'jingent_token' || ev.key === 'auth_token') syncUserProfileGlobally();
        });
        window.addEventListener('message', function(ev) {
            if (!ev || !ev.data) return;
            if (ev.data.type === 'jingent:login' || ev.data.type === 'jingent:logout' || ev.data.type === 'userUpdated') syncUserProfileGlobally();
        });
        return ret;
    };
})();

document.addEventListener('DOMContentLoaded', init);
