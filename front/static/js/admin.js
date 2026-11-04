// 后台管理前端（原生 JS，无外部依赖）
(function () {
    const API = window.location.origin;
    const TOKEN_KEY = "admin_token";

    // 配置项的中文标签、控件类型与提示
    const CONFIG_META = {
        reward_base:          {label: "单人推广奖励（元）", type: "input"},
        tier_threshold:       {label: "阶梯人数阈值（人）", type: "input"},
        tier_bonus:           {label: "阶梯额外奖励（元）", type: "input"},
        tier_membership_days: {label: "赠送会员天数（-1 = 永久）", type: "input"},
        link_cache_days:      {label: "推广链接有效期（天）", type: "input"},
        landing_base_url:     {label: "专属链接跳转地址", type: "input", hint: "用户复制链接后落地到的页面。"},
        promo_enabled:        {label: "分享 / 横幅总开关", type: "switch", hint: "关闭后所有分享入口与横幅不展示。"},
        input_promo_enabled:  {label: "输入框推广文案开关", type: "switch", hint: "关闭后聊天输入框不再显示推广文案。"},
        popup_intro_zh:       {label: "分享弹窗介绍 · 中文", type: "textarea"},
        popup_intro_en:       {label: "分享弹窗介绍 · 英文", type: "textarea"},
        input_promo_zh:       {label: "输入框推广文案 · 中文", type: "textarea"},
        input_promo_en:       {label: "输入框推广文案 · 英文", type: "textarea"},
    };

    const CONFIG_GROUPS = [
        {
            id: "reward",
            title: "推广奖励",
            desc: "每带来 1 位有效注册立刻发钱；同一位推广人累计满阶梯人数，再发一次额外奖励。",
            keys: ["reward_base", "tier_threshold", "tier_bonus", "tier_membership_days"],
        },
        {
            id: "entry",
            title: "分享入口",
            desc: "控制分享弹窗与输入框文案是否出现，以及专属链接的有效期。",
            keys: ["link_cache_days", "landing_base_url", "promo_enabled", "input_promo_enabled"],
        },
        {
            id: "copy",
            title: "分享文案",
            desc: "用户分享时看到的中英文案，两行以内最稳妥。",
            keys: ["popup_intro_zh", "popup_intro_en", "input_promo_zh", "input_promo_en"],
        },
    ];

    const TAB_LABELS = {
        dashboard: "数据看板", server: "服务器信息", logs: "实时日志", userinfo: "用户信息",
        approvals: "审批处理", withdraws: "提现审核", "memory-audit": "记忆体审核",
        users: "用户管理", voices: "音色管理", config: "配置管理",
    };

    const state = {
        tab: "dashboard",
        metric: "pv",
        trend: null,
        cfg: null,
        withdrawStatus: "",
        memoryStatus: "",
        balance: null,
        logKind: "startpy",      // 当前日志板块
        logForceBottom: false,   // 切换板块时强制滚到底部
        logOffset: {startpy: 0, voicestudio: 0},  // 增量读取的字节偏移（0=下次全量）
        uinfoKind: "registered", // 用户信息当前分类
        logsTimer: null,         // 日志自动刷新定时器
        serverTimer: null,       // 服务器信息自动刷新定时器
    };

    function token() { return sessionStorage.getItem(TOKEN_KEY); }
    function setToken(t) { sessionStorage.setItem(TOKEN_KEY, t); }
    function clearToken() { sessionStorage.removeItem(TOKEN_KEY); }

    function authHeaders() {
        return {"Content-Type": "application/json", "Authorization": "Bearer " + token()};
    }

    // 统一请求：401 自动回登录框
    async function api(path, opts) {
        opts = opts || {};
        opts.headers = Object.assign(authHeaders(), opts.headers || {});
        const res = await fetch(API + path, opts);
        if (res.status === 401) {
            clearToken();
            showLogin();
            throw new Error("登录已过期，请重新登录");
        }
        return res;
    }

    function esc(s) {
        return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
            {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
    }

    const intFmt = new Intl.NumberFormat("zh-CN");
    const fmtInt = v => intFmt.format(Number(v) || 0);
    const money = v => "¥" + (Number(v) || 0).toFixed(2);
    const signed = v => (v > 0 ? "+" : v < 0 ? "\u2212" : "") + fmtInt(Math.abs(v));
    const dash = () => '<span class="dash">\u2014</span>';
    const numOr = (v, fb) => {
        const n = parseFloat(v);
        return Number.isFinite(n) ? n : fb;
    };

    function errState(label, e) {
        return `<div class="state state-error"><span>${esc(label)}</span>` +
            `<span class="state-msg">${esc(e && e.message ? e.message : "网络或接口异常")}</span></div>`;
    }

    function markFresh() {
        const d = new Date();
        const p = n => String(n).padStart(2, "0");
        document.getElementById("freshness").textContent =
            "更新于 " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
    }

    // ---------------- 登录 ----------------
    function showLogin() {
        document.getElementById("adminLogin").hidden = false;
        document.getElementById("adminShell").hidden = true;
    }

    function showShell() {
        document.getElementById("adminLogin").hidden = true;
        document.getElementById("adminShell").hidden = false;
        switchTab("dashboard");
    }

    async function doLogin() {
        const u = document.getElementById("adminUser").value.trim();
        const p = document.getElementById("adminPass").value;
        const err = document.getElementById("adminLoginErr");
        err.textContent = "";
        try {
            const res = await fetch(API + "/admin/api/login", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({username: u, password: p}),
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.token) {
                setToken(data.token);
                state.cfg = null;
                state.stats = null;
                showShell();
            } else {
                err.textContent = (data.detail && data.detail.msg) || data.msg || "登录失败";
            }
        } catch (e) {
            err.textContent = "网络错误，请重试";
        }
    }

    // ---------------- 数据看板 ----------------
    async function ensureConfig(force) {
        if (state.cfg && !force) return state.cfg;
        const res = await api("/admin/api/config");
        const d = await res.json();
        state.cfg = d.config || {};
        return state.cfg;
    }

    async function loadDashboard() {
        const grid = document.getElementById("statGrid");
        if (!grid.children.length) {
            grid.innerHTML = Array.from({length: 5}, (_, i) =>
                `<div class="kpi${i === 0 ? " kpi-lead" : ""}">` +
                `<div class="sk sk-line"></div><div class="sk sk-value"></div></div>`).join("");
        }
        document.getElementById("trendChart").innerHTML = '<div class="state">正在读取近 7 天访问…</div>';

        try {
            const statsRes = await api("/admin/api/stats");
            const d = await statsRes.json();
            const cfg = await ensureConfig(true).catch(() => state.cfg || {});
            const usersData = await api("/admin/api/users?limit=6")
                .then(r => r.json()).catch(() => null);

            renderKpis(d);
            renderFinding(d);
            renderChart(d.trend || []);
            renderTodo(d);
            renderLadder(d, cfg);
            renderRules(cfg);
            if (usersData) renderRecent(usersData.users || [], usersData.total || 0);
            markFresh();
        } catch (e) {
            document.getElementById("trendChart").innerHTML = errState("看板读取失败", e);
            document.getElementById("dashFinding").textContent = "数据没拿到，稍后点右上角「刷新」再试。";
        }
    }

    function kpiCell(label, value, cap, lead) {
        return `<div class="kpi${lead ? " kpi-lead" : ""}">
            <div class="kpi-label">${esc(label)}</div>
            <div class="kpi-value">${value}</div>
            ${cap != null && String(cap) !== "" ? `<div class="kpi-cap">${esc(cap)}</div>` : ""}
        </div>`;
    }

    function renderKpis(d) {
        const t = d.trend || [];
        const today = t[t.length - 1] || {pv: 0, uv: 0};
        const yest = t[t.length - 2] || null;
        const pvDelta = today.pv - (yest ? yest.pv : 0);
        const uvDelta = today.uv - (yest ? yest.uv : 0);

        document.getElementById("statGrid").innerHTML = [
            kpiCell("今日 PV", fmtInt(today.pv), `累计 ${fmtInt(d.pv_total)} · 较昨日 ${signed(pvDelta)}`, true),
            kpiCell("今日访客 UV", fmtInt(today.uv), `累计 ${fmtInt(d.uv_total)} · 较昨日 ${signed(uvDelta)}`),
            kpiCell("注册用户", fmtInt(d.total_users), `今日 +${fmtInt(d.today_users)}`),
            kpiCell("待审核提现", `${fmtInt(d.withdraw_pending_count)} 笔`, money(d.withdraw_pending_amount)),
            kpiCell("累计发放", money(d.rewarded_total),
                `有效推广 ${fmtInt(d.referral_total)} · 下载 ${fmtInt(d.download_total)}`),
        ].join("");

        const badge = document.getElementById("navWithdrawCount");
        const pending = Number(d.withdraw_pending_count) || 0;
        badge.textContent = fmtInt(pending);
        badge.hidden = !pending;
    }

    function renderFinding(d) {
        const t = d.trend || [];
        const today = t[t.length - 1] || {pv: 0, uv: 0};
        const pending = Number(d.withdraw_pending_count) || 0;
        const parts = [];
        parts.push(today.pv
            ? `今天 ${fmtInt(today.pv)} 次访问、${fmtInt(today.uv)} 位访客`
            : "今天还没有人访问");
        parts.push(pending
            ? `有 ${fmtInt(pending)} 笔提现等审核（${money(d.withdraw_pending_amount)}）`
            : "待审核提现已清空");
        document.getElementById("dashFinding").textContent = parts.join("；") + "。";
    }

    // 纯 SVG 柱状图：单系列，今天用品牌紫，零值不画桩
    function ticks(max) {
        const steps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000];
        const rough = max / 4;
        const step = steps.find(s => s >= rough) || Math.ceil(rough / 5000) * 5000;
        const top = Math.ceil(max / step) * step;
        const out = [];
        for (let v = 0; v <= top + 1e-9; v += step) out.push(v);
        return out;
    }

    function renderChart(trend) {
        state.trend = trend;
        const box = document.getElementById("trendChart");
        const key = state.metric;
        const maxV = Math.max(0, ...trend.map(d => Number(d[key]) || 0));

        const first = trend.find(d => (Number(d[key]) || 0) > 0);
        document.getElementById("chartNote").textContent =
            first ? `数据从 ${first.date} 起有记录` : "近 7 天还没有记录";

        if (!trend.length || maxV === 0) {
            box.innerHTML = `<div class="empty">
                <div class="empty-title">近 7 天还没有${key === "pv" ? "访问" : "访客"}记录</div>
                <div class="empty-note">用户打开页面后，这里会按天累计。</div>
            </div>`;
            return;
        }
        drawChart(box, trend, key);
    }

    function drawChart(box, trend, key) {
        const W = Math.max(280, Math.round(box.clientWidth || 560));
        const H = 224, padL = 38, padR = 10, padT = 18, padB = 30;
        const plotW = W - padL - padR, plotH = H - padT - padB;
        const values = trend.map(d => Number(d[key]) || 0);
        const maxV = Math.max(...values);
        const tk = ticks(maxV);
        const top = tk[tk.length - 1];
        const yAt = v => padT + plotH - (v / top) * plotH;
        const slot = plotW / trend.length;
        const barW = Math.min(30, slot * 0.46);

        let grid = "";
        tk.forEach(v => {
            const y = yAt(v);
            grid += `<line x1="${padL}" x2="${W - padR}" y1="${y}" y2="${y}" stroke="var(--grid)" stroke-width="1"></line>`;
            grid += `<text x="${padL - 10}" y="${y + 4}" text-anchor="end" font-size="11" fill="var(--faint)">${fmtInt(v)}</text>`;
        });

        let bars = "";
        trend.forEach((d, i) => {
            const v = Number(d[key]) || 0;
            const cx = padL + slot * i + slot / 2;
            const isToday = i === trend.length - 1;
            if (v > 0) {
                const y = yAt(v);
                bars += `<rect class="kbar ${isToday ? "bar-today" : "bar-past"}" x="${cx - barW / 2}" y="${y}" ` +
                    `width="${barW}" height="${padT + plotH - y}">` +
                    `<title>${esc(d.date)} ${key.toUpperCase()} ${fmtInt(v)}</title></rect>`;
                if (isToday) {
                    bars += `<text x="${cx}" y="${y - 6}" text-anchor="middle" font-size="12" ` +
                        `font-weight="600" fill="var(--text)">${fmtInt(v)}</text>`;
                }
            }
            bars += `<text x="${cx}" y="${H - 8}" text-anchor="middle" font-size="11" ` +
                `fill="${isToday ? "var(--text)" : "var(--faint)"}">${esc(d.date)}</text>`;
        });

        const today = values[values.length - 1] || 0;
        box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" ` +
            `aria-label="近 7 天每日 ${key.toUpperCase()} 柱状图，今天 ${fmtInt(today)}">` +
            `${grid}${bars}</svg>`;
    }

    let chartRO = null, chartW = 0, chartRaf = 0;

    function watchChart() {
        const box = document.getElementById("trendChart");
        if (!box || chartRO) return;
        chartRO = new ResizeObserver(() => {
            const w = Math.round(box.clientWidth);
            if (!w || w === chartW) return;
            chartW = w;
            if (state.tab !== "dashboard" || !state.trend) return;
            if (!state.trend.some(d => (Number(d[state.metric]) || 0) > 0)) return;
            cancelAnimationFrame(chartRaf);
            chartRaf = requestAnimationFrame(() => drawChart(box, state.trend, state.metric));
        });
        chartRO.observe(box);
    }

    function renderTodo(d) {
        const count = Number(d.withdraw_pending_count) || 0;
        document.getElementById("todoWithdraw").textContent = fmtInt(count) + " 笔";
        const note = document.getElementById("todoWithdrawState");
        note.textContent = count ? money(d.withdraw_pending_amount) + " 待批" : "全部处理完";
        note.className = count ? "todo-label" : "todo-ok";
    }

    function renderLadder(d, cfg) {
        const base = numOr(cfg.reward_base, 3);
        const need = Math.max(1, numOr(cfg.tier_threshold, 5));
        const bonus = numOr(cfg.tier_bonus, 20);
        const days = numOr(cfg.tier_membership_days, -1);
        const mem = days === -1 ? "永久会员" : days > 0 ? `${days} 天会员` : "会员";

        document.getElementById("ladderSteps").innerHTML = `
            <li class="step"><span class="step-rung"></span>
                <div class="step-body"><b>${money(base)}</b><span>每带来 1 位有效注册</span></div></li>
            <li class="step"><span class="step-rung"></span>
                <div class="step-body"><b>满 ${fmtInt(need)} 人再 +${money(bonus)}</b><span>另送${esc(mem)}</span></div></li>`;

        document.getElementById("ladderPeople").textContent =
            `累计推广 ${fmtInt(d.referral_total)} 次`;
        document.getElementById("ladderNote").textContent =
            `阶梯按单个推广人计算：同一位累计满 ${fmtInt(need)} 人时自动发放。`;
    }

    function renderRules(cfg) {
        const rows = [
            ["最低提现金额", money(numOr(cfg.risk_withdraw_min, 10))],
            ["新用户等待", `${fmtInt(numOr(cfg.risk_new_user_withdraw_hours, 48))} 小时`],
            ["单 IP 每日上限", `${fmtInt(numOr(cfg.risk_ip_daily_limit, 10))} 次`],
            ["奖励冻结", `${fmtInt(numOr(cfg.risk_reward_freeze_hours, 24))} 小时`],
            ["审核方式", "人工审核"],
            ["到账方式", "PayPal 手动打款"],
        ];
        document.getElementById("withdrawRules").innerHTML = rows.map(([k, v]) =>
            `<div class="kv-row"><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("");
    }

    function renderQueueRules(cfg) {
        const rows = [
            ["最低提现金额", money(numOr(cfg.risk_withdraw_min, 10))],
            ["新用户等待", `${fmtInt(numOr(cfg.risk_new_user_withdraw_hours, 48))} 小时`],
            ["单 IP 每日上限", `${fmtInt(numOr(cfg.risk_ip_daily_limit, 10))} 次`],
            ["奖励冻结", `${fmtInt(numOr(cfg.risk_reward_freeze_hours, 24))} 小时`],
            ["审核方式", "人工审核"],
            ["到账方式", "PayPal 手动打款"],
            ["驳回处理", "金额退回用户余额"],
        ];
        document.getElementById("withdrawQueueRules").innerHTML = rows.map(([k, v]) =>
            `<div class="kv-row"><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("");
    }

    function hue(name) {
        let h = 0;
        for (const ch of String(name)) h = (h * 31 + ch.codePointAt(0)) % 360;
        return h;
    }

    function renderRecent(users, total) {
        const box = document.getElementById("recentUsersBox");
        const note = document.getElementById("recentNote");
        note.textContent = total
            ? `共 ${fmtInt(total)} 位注册用户，这里是最新 ${fmtInt(users.length)} 位`
            : "按 ID 倒序的最新账号";

        if (!users.length) {
            box.innerHTML = `<div class="empty">
                <div class="empty-title">还没有注册用户</div>
                <div class="empty-note">用户注册后出现在这里。</div>
            </div>`;
            return;
        }

        box.innerHTML = `<ul class="people">` + users.map(u => {
            const initial = esc(String(u.username || "?").slice(0, 1));
            const when = u.register_time ? String(u.register_time).slice(5) : "";
            return `<li class="person">
                <span class="avatar" style="--h:${hue(u.username)}" aria-hidden="true">${initial}</span>
                <div class="person-body">
                    <span class="person-name">${esc(u.username)}</span>
                    <span class="person-meta">#${u.id}${when ? " · 注册 " + esc(when) : ""}</span>
                </div>
            </li>`;
        }).join("") + `</ul>`;
    }

    // ---------------- 提现审批 ----------------
    function syncWithdrawTabs(status) {
        document.querySelectorAll("#panel-withdraws .tab").forEach(t =>
            t.classList.toggle("is-active", (t.dataset.status || "") === (status || "")));
    }

    async function loadWithdraws(status) {
        if (status === undefined) status = state.withdrawStatus || "";
        state.withdrawStatus = status;
        syncWithdrawTabs(status);

        const box = document.getElementById("withdrawState");
        const frame = document.getElementById("withdrawFrame");
        const ref = document.getElementById("withdrawRef");
        const count = document.getElementById("withdrawCount");
        box.innerHTML = '<div class="state">正在读取提现申请…</div>';
        frame.hidden = true;
        ref.hidden = true;
        count.textContent = "—";

        try {
            const res = await api("/admin/api/withdraws" + (status ? "?status=" + encodeURIComponent(status) : ""));
            const d = await res.json();
            const rows = d.withdraws || [];
            count.textContent = `共 ${fmtInt(rows.length)} 笔`;

            if (!rows.length) {
                box.innerHTML = `<div class="empty">
                    <div class="empty-title">${status ? "这个状态下没有记录" : "还没有提现申请"}</div>
                    <div class="empty-note">用户提交提现后出现在这里；通过会标记打款，驳回会把金额退回余额。</div>
                </div>`;
                ref.hidden = false;
                const cfg = await ensureConfig().catch(() => state.cfg || {});
                renderQueueRules(cfg);
                markFresh();
                return;
            }

            box.innerHTML = "";
            frame.hidden = false;
            document.getElementById("withdrawTbody").innerHTML = rows.map(w => {
                const pending = w.status === "pending";
                const actions = pending
                    ? `<button class="btn btn-ghost btn-sm" type="button" data-approve="${w.id}">通过</button>
                       <button class="btn btn-quiet btn-sm" type="button" data-reject="${w.id}">驳回</button>`
                    : `<span class="ident-sub">${w.reviewed_at ? "处理于 " + esc(w.reviewed_at) : dash()}</span>`;
                return `<tr>
                    <td class="col-id">#${w.id}</td>
                    <td>${esc(w.username)}</td>
                    <td class="num">${money(w.amount)}</td>
                    <td>${w.paypal_email ? esc(w.paypal_email) : dash()}</td>
                    <td><span class="pill pill-${esc(w.status)}">${esc(statusZh(w.status))}</span></td>
                    <td class="col-time">${esc(w.created_at) || dash()}</td>
                    <td class="col-actions"><div class="cell-actions">${actions}</div></td>
                </tr>`;
            }).join("");
            markFresh();
        } catch (e) {
            box.innerHTML = errState("提现申请读取失败", e);
        }
    }

    function statusZh(s) {
        return {pending: "待审核", paid: "已到账", rejected: "已驳回"}[s] || s;
    }

    async function handleWithdrawAction(id, action) {
        const verb = action === "approve" ? "通过" : "驳回";
        if (!confirm(`确认${verb}提现 #${id}？` + (action === "reject" ? "\n驳回后金额会退回用户余额。" : ""))) return;
        try {
            const res = await api(`/admin/api/withdraws/${id}/${action}`, {method: "POST"});
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
                loadWithdraws();
            } else {
                alert((d.detail && d.detail.msg) || "操作失败");
            }
        } catch (e) { /* 401 已处理 */ }
    }

    // ---------------- 审批处理（概览） ----------------
    async function loadApprovals() {
        const box = document.getElementById("approvalSummary");
        box.innerHTML = '<div class="state">正在汇总待办…</div>';
        try {
            const [wd, md] = await Promise.all([
                api("/admin/api/withdraws?status=pending").then(r => r.json()).catch(() => ({withdraws: []})),
                api("/admin/api/memory-audit?status=pending").then(r => r.json()).catch(() => ({characters: []})),
            ]);
            const wPending = (wd.withdraws || []).length;
            const mPending = (md.characters || []).length;
            box.innerHTML =
                kpiCell("待审核提现", fmtInt(wPending) + " 笔", "点击下方入口进入处理", true) +
                kpiCell("待审核记忆体", fmtInt(mPending) + " 个", "通过后方可供用户使用", false);
            document.getElementById("approvalWithdrawCount").textContent = fmtInt(wPending);
            document.getElementById("approvalMemoryCount").textContent = fmtInt(mPending);
            const navCount = document.getElementById("navApproveCount");
            const total = wPending + mPending;
            navCount.textContent = fmtInt(total);
            navCount.hidden = !total;
            markFresh();
        } catch (e) {
            box.innerHTML = errState("审批汇总读取失败", e);
        }
    }

    // ---------------- 记忆体审核 ----------------
    function memoryStatusZh(s) {
        return {draft: "草稿", pending: "待审核", approved: "已通过", rejected: "已拒绝"}[s] || s;
    }

    function syncMemoryTabs(status) {
        document.querySelectorAll("#panel-memory-audit .tab").forEach(t =>
            t.classList.toggle("is-active", (t.dataset.mstatus || "") === status));
    }

    async function loadMemoryAudit(status) {
        if (status === undefined) status = state.memoryStatus || "";
        state.memoryStatus = status;
        syncMemoryTabs(status);

        const box = document.getElementById("memoryState");
        const frame = document.getElementById("memoryFrame");
        const count = document.getElementById("memoryCount");
        box.innerHTML = '<div class="state">正在读取记忆体…</div>';
        frame.hidden = true;
        count.textContent = "—";

        try {
            const res = await api("/admin/api/memory-audit" + (status ? "?status=" + encodeURIComponent(status) : ""));
            const d = await res.json();
            const rows = d.characters || [];
            count.textContent = `共 ${fmtInt(rows.length)} 个`;

            if (!rows.length) {
                box.innerHTML = `<div class="empty">
                    <div class="empty-title">${status ? "这个状态下没有记忆体" : "还没有记忆体"}</div>
                    <div class="empty-note">用户创建的记忆体提交审核后出现在这里；通过后用户才能使用。</div>
                </div>`;
                const navCount = document.getElementById("navMemoryCount");
                navCount.textContent = fmtInt(rows.length);
                navCount.hidden = true;
                markFresh();
                return;
            }

            box.innerHTML = "";
            frame.hidden = false;
            document.getElementById("memoryTbody").innerHTML = rows.map(m => {
                const pending = m.status === "pending";
                const actions = pending
                    ? `<button class="btn btn-ghost btn-sm" type="button" data-mapprove="${m.npc_id}">通过</button>
                       <button class="btn btn-quiet btn-sm" type="button" data-mreject="${m.npc_id}">拒绝</button>`
                    : `<span class="ident-sub">${dash()}</span>`;
                return `<tr>
                    <td class="col-id">${esc(m.npc_id)}</td>
                    <td><b>${esc(m.name)}</b><br><span class="ident-sub">${esc((m.description || "").slice(0, 40)) || dash()}</span></td>
                    <td>${esc(m.username || "—")}</td>
                    <td><span class="pill pill-${esc(m.status)}">${esc(memoryStatusZh(m.status))}</span></td>
                    <td class="col-time">${esc(m.updated_at) || dash()}</td>
                    <td class="col-actions"><div class="cell-actions">${actions}</div></td>
                </tr>`;
            }).join("");

            const navCount = document.getElementById("navMemoryCount");
            const pendingCount = rows.filter(r => r.status === "pending").length;
            navCount.textContent = fmtInt(pendingCount);
            navCount.hidden = !pendingCount;
            markFresh();
        } catch (e) {
            box.innerHTML = errState("记忆体读取失败", e);
        }
    }

    async function handleMemoryAction(npcId, action) {
        const verb = action === "approve" ? "通过" : "拒绝";
        if (!confirm(`确认${verb}记忆体 ${npcId}？` + (action === "reject" ? "\n拒绝后该记忆体不可使用。" : "\n通过后用户即可使用该记忆体对话。"))) return;
        try {
            const res = await api(`/admin/api/memory-audit/${npcId}/${action}`, {method: "POST"});
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
                loadMemoryAudit();
                loadApprovals();
            } else {
                alert((d.detail && d.detail.msg) || "操作失败");
            }
        } catch (e) { /* 401 已处理 */ }
    }

    // ---------------- 音色管理 ----------------
    async function loadVoices() {
        const box = document.getElementById("voicesState");
        const frame = document.getElementById("voicesFrame");
        box.innerHTML = '<div class="state">正在读取音色…</div>';
        frame.hidden = true;

        try {
            const res = await api("/admin/api/voices");
            const d = await res.json();
            const rows = d.voices || [];
            if (!rows.length) {
                box.innerHTML = `<div class="empty">
                    <div class="empty-title">没有音色</div>
                    <div class="empty-note">VoiceStudio 服务未运行或没有音色数据。</div>
                </div>`;
                return;
            }

            box.innerHTML = "";
            frame.hidden = false;
            document.getElementById("voicesTbody").innerHTML = rows.map(v => {
                const typeZh = v.type === "profile" ? "用户音色" : "内置别名";
                const actions = v.deletable
                    ? `<button class="btn btn-quiet btn-sm" type="button" data-voicedel="${esc(v.voice_id)}">删除</button>`
                    : `<span class="ident-sub">不可删</span>`;
                return `<tr>
                    <td class="col-id">${esc(v.voice_id)}</td>
                    <td><b>${esc(v.name)}</b></td>
                    <td>${esc(typeZh)}</td>
                    <td class="col-actions"><div class="cell-actions">${actions}</div></td>
                </tr>`;
            }).join("");
        } catch (e) {
            box.innerHTML = errState("音色读取失败", e);
        }
    }

    async function handleVoiceDelete(voiceId) {
        if (!confirm(`确认删除音色 ${voiceId}？\n删除会同时清掉对应的音频文件，不可恢复。`)) return;
        try {
            const res = await api(`/admin/api/voices/${encodeURIComponent(voiceId)}`, {method: "DELETE"});
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
                loadVoices();
            } else {
                alert((d.detail && d.detail.msg) || "删除失败");
            }
        } catch (e) { /* 401 已处理 */ }
    }

    // ---------------- 用户管理 ----------------
    async function loadUsers() {
        const q = document.getElementById("userSearch").value.trim();
        const box = document.getElementById("userState");
        const frame = document.getElementById("userFrame");
        const count = document.getElementById("userCount");
        box.innerHTML = '<div class="state">正在读取用户…</div>';
        frame.hidden = true;
        count.textContent = "—";

        try {
            const res = await api("/admin/api/users?limit=100&q=" + encodeURIComponent(q));
            const d = await res.json();
            const rows = d.users || [];
            const total = Number(d.total) || 0;
            count.textContent = `共 ${fmtInt(total)} 位` + (total > rows.length ? ` · 显示最新 ${fmtInt(rows.length)} 位` : "");

            if (!rows.length) {
                box.innerHTML = `<div class="empty">
                    <div class="empty-title">${q ? "没有匹配的用户" : "还没有用户"}</div>
                    <div class="empty-note">${q ? "换个关键词，或清空搜索看全部。" : "用户注册后出现在这里。"}</div>
                </div>`;
                return;
            }

            box.innerHTML = "";
            frame.hidden = false;
            document.getElementById("userTbody").innerHTML = rows.map(u => {
                const when = u.register_time ? String(u.register_time).slice(5) : "";
                return `<tr>
                    <td><div class="cell-ident">
                        <span class="ident-name">${esc(u.username)}</span>
                        <span class="ident-sub">#${u.id}${when ? " · " + esc(when) : ""}</span>
                    </div></td>
                    <td class="num">${money(u.balance)}</td>
                    <td class="num">${fmtInt(u.referral_count)}</td>
                    <td>${u.referral_code ? esc(u.referral_code) : dash()}</td>
                    <td>${u.membership_expire_at ? esc(u.membership_expire_at) : dash()}</td>
                    <td class="col-actions"><div class="cell-actions">
                        <button class="btn btn-quiet btn-sm" type="button" data-adjust="${u.id}"
                            data-name="${esc(u.username)}" data-bal="${esc(u.balance)}">调整余额</button>
                    </div></td>
                </tr>`;
            }).join("");
            markFresh();
        } catch (e) {
            box.innerHTML = errState("用户读取失败", e);
        }
    }

    function openBalance(uid, username, bal) {
        state.balance = {uid: uid, username: username};
        document.getElementById("balanceSub").textContent =
            `${username} · 当前余额 ${money(bal)}`;
        document.getElementById("balanceAmount").value = "";
        document.getElementById("balanceErr").textContent = "";
        const dlg = document.getElementById("balanceDialog");
        if (typeof dlg.showModal === "function") dlg.showModal();
        document.getElementById("balanceAmount").focus();
    }

    async function submitBalance() {
        const target = state.balance;
        if (!target) return;
        const input = document.getElementById("balanceAmount");
        const err = document.getElementById("balanceErr");
        const amount = parseFloat(input.value.trim());

        if (!Number.isFinite(amount) || amount === 0) {
            err.textContent = "请输入非 0 的数字：正数加钱，负数扣钱";
            return;
        }
        err.textContent = "";
        const btn = document.getElementById("balanceConfirm");
        btn.disabled = true;
        try {
            const res = await api(`/admin/api/users/${target.uid}/balance`, {
                method: "POST",
                body: JSON.stringify({amount: amount, reason: "admin adjust"}),
            });
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
                document.getElementById("balanceDialog").close();
                loadUsers();
            } else {
                err.textContent = (d.detail && d.detail.msg) || d.msg || "调整失败";
            }
        } catch (e) {
            err.textContent = e && e.message ? e.message : "网络或接口异常";
        } finally {
            btn.disabled = false;
        }
    }

    // ---------------- 配置管理 ----------------
    function fieldHtml(key, val) {
        const meta = CONFIG_META[key] || {label: key, type: "input"};
        const hint = meta.hint ? `<span class="field-hint">${esc(meta.hint)}</span>` : "";
        const label = `<span class="field-label">${esc(meta.label)}</span>`;
        const v = val == null ? "" : String(val);

        if (meta.type === "switch") {
            const on = v === "1";
            return `<div class="field-row full switch-row">
                <div class="switch-text">${label}${hint}</div>
                <button class="switch" type="button" role="switch" aria-checked="${on}"
                    data-switch="${key}" aria-label="${esc(meta.label)}"></button>
            </div>`;
        }
        if (meta.type === "textarea") {
            return `<label class="field-row"><span class="field-label">${esc(meta.label)}</span>` +
                `<textarea data-key="${key}">${esc(v)}</textarea></label>`;
        }
        const full = key === "landing_base_url" ? " full" : "";
        return `<label class="field-row${full}">${label}` +
            `<input type="text" data-key="${key}" value="${esc(v)}"></label>`;
    }

    function previewText(values) {
        const base = numOr(values.reward_base, 3);
        const need = Math.max(1, numOr(values.tier_threshold, 5));
        const bonus = numOr(values.tier_bonus, 20);
        const days = numOr(values.tier_membership_days, -1);
        const mem = days === -1 ? "永久会员" : days > 0 ? `${days} 天会员` : "会员";
        return `每 1 位有效注册发 ${money(base)}；同一位推广人满 ${fmtInt(need)} 人，` +
            `再发 ${money(bonus)} 并送${mem}。`;
    }

    function renderConfig(cfg) {
        document.getElementById("configForm").innerHTML = CONFIG_GROUPS.map(g => {
            const preview = g.id === "reward"
                ? `<div class="preview"><span class="preview-label">实时预览</span>` +
                  `<span class="preview-text" data-preview>${esc(previewText(cfg))}</span></div>`
                : "";
            const fields = g.keys.map(k => fieldHtml(k, cfg[k])).join("");
            return `<section class="setting-row">
                <div class="setting-label">
                    <h2>${esc(g.title)}</h2>
                    <p class="setting-desc">${esc(g.desc)}</p>
                </div>
                <div class="setting-panel">${preview}<div class="fields">${fields}</div></div>
            </section>`;
        }).join("");
    }

    async function loadConfig() {
        const host = document.getElementById("configForm");
        if (!host.innerHTML) host.innerHTML = '<div class="state">正在读取配置…</div>';
        try {
            const cfg = await ensureConfig(true);
            renderConfig(cfg);
            markFresh();
        } catch (e) {
            host.innerHTML = errState("配置读取失败", e);
        }
    }

    function currentValues() {
        const host = document.getElementById("configForm");
        const items = {};
        host.querySelectorAll("[data-key]").forEach(el => {
            items[el.getAttribute("data-key")] = el.value;
        });
        host.querySelectorAll("[data-switch]").forEach(el => {
            items[el.getAttribute("data-switch")] = el.getAttribute("aria-checked") === "true" ? "1" : "0";
        });
        return items;
    }

    function updatePreview() {
        const el = document.querySelector("#configForm [data-preview]");
        if (el) el.textContent = previewText(currentValues());
    }

    async function saveConfig() {
        const items = currentValues();
        const status = document.getElementById("configStatus");
        const btn = document.getElementById("configSaveBtn");
        btn.disabled = true;
        try {
            const res = await api("/admin/api/config", {method: "POST", body: JSON.stringify({items: items})});
            const d = await res.json().catch(() => ({}));
            if (res.ok) {
                state.cfg = Object.assign({}, state.cfg || {}, items);
                status.textContent = "已保存 " + (d.updated ? d.updated.length : 0) + " 项配置";
                status.className = "save-note ok";
            } else {
                status.textContent = (d.detail && d.detail.msg) || d.msg || "保存失败";
                status.className = "save-note err";
            }
        } catch (e) {
            status.textContent = e && e.message ? e.message : "网络或接口异常";
            status.className = "save-note err";
        } finally {
            btn.disabled = false;
        }
        setTimeout(() => {
            status.textContent = "";
            status.className = "save-note";
        }, 4000);
    }

    // ---------------- 标签切换 ----------------
    function switchTab(tab) {
        state.tab = tab;
        document.querySelectorAll(".nav-item").forEach(n => {
            const on = n.dataset.tab === tab;
            n.classList.toggle("is-active", on);
            if (on) n.setAttribute("aria-current", "page");
            else n.removeAttribute("aria-current");
        });
        document.querySelectorAll(".panel").forEach(p =>
            p.classList.toggle("is-active", p.id === "panel-" + tab));

        const label = TAB_LABELS[tab] || tab;
        document.getElementById("crumbCurrent").textContent = label;
        document.title = label + " · Jingent AI 后台";

        // 离开 server/logs 页时停掉自动刷新定时器
        if (tab !== "server" && state.serverTimer) { clearInterval(state.serverTimer); state.serverTimer = null; }
        if (tab !== "logs" && state.logsTimer) { clearInterval(state.logsTimer); state.logsTimer = null; }

        if (tab === "dashboard") loadDashboard();
        else if (tab === "server") loadServerInfo();
        else if (tab === "logs") loadLogs();
        else if (tab === "userinfo") loadUsersInfo();
        else if (tab === "approvals") loadApprovals();
        else if (tab === "withdraws") loadWithdraws(state.withdrawStatus);
        else if (tab === "memory-audit") loadMemoryAudit();
        else if (tab === "users") loadUsers();
        else if (tab === "voices") loadVoices();
        else if (tab === "config") loadConfig();
    }

    function refreshCurrent() {
        if (state.tab === "dashboard") loadDashboard();
        else if (state.tab === "server") loadServerInfo();
        else if (state.tab === "logs") loadLogs();
        else if (state.tab === "userinfo") loadUsersInfo();
        else if (state.tab === "approvals") loadApprovals();
        else if (state.tab === "withdraws") loadWithdraws(state.withdrawStatus);
        else if (state.tab === "memory-audit") loadMemoryAudit();
        else if (state.tab === "users") loadUsers();
        else if (state.tab === "voices") loadVoices();
        else loadConfig();
    }

    // ---------------- 服务器信息 ----------------
    const fmtBytes = v => {
        const n = Number(v) || 0;
        if (n >= 1024 * 1024 * 1024) return (n / 1024 / 1024 / 1024).toFixed(2) + " GB";
        if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
        if (n >= 1024) return (n / 1024).toFixed(1) + " KB";
        return n + " B";
    };

    function serverCell(label, value, sub, bar) {
        return `<div class="kpi">
            <div class="kpi-label">${esc(label)}</div>
            <div class="kpi-value">${value}</div>
            ${bar != null ? `<div class="meter"><div class="meter-fill" style="width:${Math.max(0, Math.min(100, bar))}%"></div></div>` : ""}
            ${sub ? `<div class="kpi-note">${sub}</div>` : ""}
        </div>`;
    }

    async function loadServerInfo() {
        const grid = document.getElementById("serverGrid");
        const sub = document.getElementById("serverSub");
        try {
            const res = await api("/admin/api/server-info");
            const d = await res.json();
            const memPct = d.mem_percent != null ? d.mem_percent : 0;
            const diskPct = d.disk_percent != null ? d.disk_percent : 0;
            const cpuPct = d.cpu_percent != null ? d.cpu_percent : 0;
            grid.innerHTML =
                serverCell("CPU 使用率", cpuPct + "%", "逻辑核心 " + d.cpu_count, cpuPct) +
                serverCell("内存", fmtBytes(d.mem_used) + " / " + fmtBytes(d.mem_total), "使用率 " + memPct + "%", memPct) +
                serverCell("磁盘", fmtBytes(d.disk_used) + " / " + fmtBytes(d.disk_total), "使用率 " + diskPct + "%", diskPct) +
                serverCell("进程内存", fmtBytes(d.process_rss), "当前 Python 服务占用", null) +
                serverCell("进程 CPU", (d.process_cpu != null ? d.process_cpu : "—") + "%", "线程数 " + (d.process_threads || 0), null) +
                serverCell("进程运行时长", d.process_uptime_human || "—", "系统启动于 " + (d.boot_time || "—"), null) +
                serverCell("主机", esc(d.hostname || "—"), esc(d.platform || ""), null) +
                serverCell("服务时间", d.server_time || "—", "Python " + (d.python || ""), null);
            sub.textContent = d.psutil_error
                ? "已降级基础指标（psutil 未就绪：" + esc(d.psutil_error) + "）"
                : "实时采集 CPU / 内存 / 磁盘 / 进程运行状态。";
            markFresh();
            // 自动刷新（每 3 秒）
            if (!state.serverTimer) {
                state.serverTimer = setInterval(() => { if (state.tab === "server") loadServerInfo(); }, 3000);
            }
        } catch (e) {
            grid.innerHTML = errState("服务器信息读取失败", e);
        }
    }

    // ---------------- 实时日志 ----------------
    async function loadLogs() {
        const kind = state.logKind;
        const view = document.getElementById("logView");
        const meta = document.getElementById("logMeta");
        const title = document.getElementById("logTitle");
        title.textContent = kind === "startpy" ? "Python start.py 服务日志" : "VoiceStudio 服务日志";
        // 刷新前记录：用户是否在底部（在底部附近才自动跟底，往上翻则不打扰）
        const wasAtBottom = view.scrollHeight - view.scrollTop - view.clientHeight < 60;
        try {
            const path = kind === "startpy" ? "/admin/api/logs/startpy" : "/admin/api/logs/voicestudio";
            const offset = state.logOffset[kind] || 0;
            // 首次（offset=0）全量尾部；之后增量读取，拿到新内容用文本节点追加，不重写 DOM，杜绝闪烁
            const res = await api(path + "?lines=300&offset=" + offset);
            const d = await res.json();

            if (offset === 0 || d.truncated) {
                // 全量加载 / 文件被轮转重置：整体替换一次
                view.textContent = d.content || "（暂无日志内容）";
                state.logOffset[kind] = d.offset || 0;
                if (wasAtBottom || state.logForceBottom) {
                    view.scrollTop = view.scrollHeight;
                }
            } else if (d.content) {
                // 增量追加：只 append 新增文本节点，屏幕不闪、滚动自然
                view.appendChild(document.createTextNode(d.content));
                state.logOffset[kind] = d.offset || offset;
                if (wasAtBottom || state.logForceBottom) {
                    view.scrollTop = view.scrollHeight;
                }
            }
            // 兜底：日志太长时裁掉旧内容，避免 DOM 无限膨胀
            if (view.textContent.length > 200000) {
                view.textContent = view.textContent.slice(-150000);
            }

            state.logForceBottom = false;
            meta.textContent = (d.exists ? ("路径 " + d.path + " · " + fmtBytes(d.size)) : ("未找到日志文件：" + d.path));
            markFresh();
            // 自动刷新（每 2 秒，尊重 checkbox）
            const autoCb = document.getElementById("logsAutoRefresh");
            const auto = autoCb ? autoCb.checked : true;
            if (auto && !state.logsTimer) {
                state.logsTimer = setInterval(() => {
                    if (state.tab === "logs") loadLogs();
                }, 2000);
            } else if (!auto && state.logsTimer) {
                clearInterval(state.logsTimer);
                state.logsTimer = null;
            }
        } catch (e) {
            view.textContent = "日志读取失败：" + (e && e.message ? e.message : "网络或接口异常");
        }
    }

    // ---------------- 用户信息 ----------------
    async function loadUsersInfo() {
        const tbody = document.getElementById("userinfoTbody");
        const thead = document.getElementById("userinfoThead");
        const count = document.getElementById("userinfoCount");
        const summaryBox = document.getElementById("userinfoSummary");
        tbody.innerHTML = '<tr><td colspan="6"><div class="state">正在读取用户信息…</div></td></tr>';
        try {
            const res = await api("/admin/api/users-info");
            const d = await res.json();
            const s = d.summary || {};
            summaryBox.innerHTML =
                kpiCell("注册用户", fmtInt(s.registered_count || 0), null, true) +
                kpiCell("访客数", fmtInt(s.visitor_count || 0), null, false) +
                kpiCell("用户请求", fmtInt(s.user_requests || 0), null, false) +
                kpiCell("访客请求", fmtInt(s.visitor_requests || 0), null, false) +
                kpiCell("输入 token", fmtInt(s.tokens_in_total || 0), null, false) +
                kpiCell("输出 token", fmtInt(s.tokens_out_total || 0), null, false);

            const isRegistered = state.uinfoKind === "registered";
            const rows = isRegistered ? (d.registered || []) : (d.visitors || []);
            count.textContent = fmtInt(rows.length);

            if (isRegistered) {
                thead.innerHTML = `<tr>
                    <th>ID</th><th>用户名</th><th>IP</th><th>请求头（UA）</th>
                    <th class="num">请求数</th><th class="num">输入 token</th>
                    <th class="num">输出 token</th><th class="col-time">最近活跃</th></tr>`;
                tbody.innerHTML = rows.length ? rows.map(u => `<tr>
                    <td>${u.id}</td>
                    <td><b>${esc(u.username)}</b>${u.nickname ? `<br><span class="dash">${esc(u.nickname)}</span>` : ""}</td>
                    <td class="mono">${esc(u.ip || "—")}</td>
                    <td class="ua-cell" title="${esc(u.user_agent || "")}">${esc(u.user_agent || "—")}</td>
                    <td class="num">${fmtInt(u.requests)}</td>
                    <td class="num">${fmtInt(u.tokens_in)}</td>
                    <td class="num">${fmtInt(u.tokens_out)}</td>
                    <td class="col-time">${esc(u.last_time || "—")}</td></tr>`).join("")
                    : '<tr><td colspan="8"><div class="state">暂无注册用户</div></td></tr>';
            } else {
                thead.innerHTML = `<tr>
                    <th>IP</th><th>请求头（UA）</th>
                    <th class="num">请求数</th><th class="num">输入 token</th>
                    <th class="num">输出 token</th><th class="col-time">最近活跃</th></tr>`;
                tbody.innerHTML = rows.length ? rows.map(v => `<tr>
                    <td class="mono">${esc(v.ip)}</td>
                    <td class="ua-cell" title="${esc(v.user_agent || "")}">${esc(v.user_agent || "—")}</td>
                    <td class="num">${fmtInt(v.requests)}</td>
                    <td class="num">${fmtInt(v.tokens_in)}</td>
                    <td class="num">${fmtInt(v.tokens_out)}</td>
                    <td class="col-time">${esc(v.last_time || "—")}</td></tr>`).join("")
                    : '<tr><td colspan="6"><div class="state">暂无访客记录</div></td></tr>';
            }
            markFresh();
        } catch (e) {
            tbody.innerHTML = '<tr><td colspan="8">' + errState("用户信息读取失败", e) + "</td></tr>";
        }
    }

    // ---------------- 初始化 ----------------
    function init() {
        document.getElementById("loginForm").addEventListener("submit", e => {
            e.preventDefault();
            doLogin();
        });

        document.querySelectorAll(".nav-item").forEach(n =>
            n.addEventListener("click", () => switchTab(n.dataset.tab)));

        document.getElementById("refreshBtn").addEventListener("click", refreshCurrent);
        document.getElementById("userSearchBtn").addEventListener("click", loadUsers);
        document.getElementById("userSearch").addEventListener("keydown", e => {
            if (e.key === "Enter") loadUsers();
        });

        document.querySelectorAll(".seg-item").forEach(b =>
            b.addEventListener("click", () => {
                state.metric = b.dataset.metric;
                document.querySelectorAll(".seg-item").forEach(x =>
                    x.classList.toggle("is-active", x === b));
                if (state.trend) renderChart(state.trend);
            }));

        document.querySelectorAll("#panel-withdraws .tab").forEach(t =>
            t.addEventListener("click", () => loadWithdraws(t.dataset.status || "")));

        document.getElementById("withdrawTbody").addEventListener("click", e => {
            const ap = e.target.getAttribute("data-approve");
            const rj = e.target.getAttribute("data-reject");
            if (ap) handleWithdrawAction(ap, "approve");
            if (rj) handleWithdrawAction(rj, "reject");
        });

        document.querySelectorAll("#panel-memory-audit .tab").forEach(t =>
            t.addEventListener("click", () => loadMemoryAudit(t.dataset.mstatus || "")));
        document.getElementById("memoryRefreshBtn").addEventListener("click", () => loadMemoryAudit());
        document.getElementById("memoryTbody").addEventListener("click", e => {
            const ap = e.target.getAttribute("data-mapprove");
            const rj = e.target.getAttribute("data-mreject");
            if (ap) handleMemoryAction(ap, "approve");
            if (rj) handleMemoryAction(rj, "reject");
        });

        document.getElementById("voicesRefreshBtn").addEventListener("click", () => loadVoices());
        document.getElementById("voicesTbody").addEventListener("click", e => {
            const del = e.target.getAttribute("data-voicedel");
            if (del) handleVoiceDelete(del);
        });

        document.getElementById("userTbody").addEventListener("click", e => {
            const el = e.target.closest("[data-adjust]");
            if (!el) return;
            openBalance(el.getAttribute("data-adjust"), el.getAttribute("data-name"), el.getAttribute("data-bal"));
        });

        document.getElementById("balanceForm").addEventListener("submit", e => {
            e.preventDefault();
            submitBalance();
        });
        document.getElementById("balanceCancel").addEventListener("click", () =>
            document.getElementById("balanceDialog").close());

        document.getElementById("configSaveBtn").addEventListener("click", saveConfig);
        document.getElementById("configForm").addEventListener("click", e => {
            const sw = e.target.closest("[data-switch]");
            if (!sw) return;
            sw.setAttribute("aria-checked", sw.getAttribute("aria-checked") === "true" ? "false" : "true");
            updatePreview();
        });
        document.getElementById("configForm").addEventListener("input", updatePreview);

        // 服务器信息：手动刷新
        document.getElementById("serverRefreshBtn").addEventListener("click", loadServerInfo);

        // 实时日志：板块切换 + 手动刷新 + 自动刷新开关
        document.querySelectorAll(".logs-tab").forEach(t =>
            t.addEventListener("click", () => {
                state.logKind = t.dataset.log;
                state.logForceBottom = true;   // 切换板块后从头看最新，强制滚到底部
                state.logOffset[t.dataset.log] = 0;  // 切换板块 → 全量重载
                document.querySelectorAll(".logs-tab").forEach(x =>
                    x.classList.toggle("is-active", x === t));
                loadLogs();
            }));
        document.getElementById("logsRefreshBtn").addEventListener("click", loadLogs);
        document.getElementById("logsAutoRefresh").addEventListener("change", e => {
            if (e.target.checked) {
                if (!state.logsTimer) loadLogs();
            } else {
                if (state.logsTimer) { clearInterval(state.logsTimer); state.logsTimer = null; }
            }
        });

        // 用户信息：分类切换 + 手动刷新
        document.querySelectorAll("#panel-userinfo .tab").forEach(t =>
            t.addEventListener("click", () => {
                state.uinfoKind = t.dataset.uinfo;
                document.querySelectorAll("#panel-userinfo .tab").forEach(x =>
                    x.classList.toggle("is-active", x === t));
                loadUsersInfo();
            }));
        document.getElementById("userinfoRefreshBtn").addEventListener("click", loadUsersInfo);

        // 跨页跳转 + 退出（侧栏与顶栏各一个退出按钮）
        document.addEventListener("click", e => {
            const link = e.target.closest("[data-tab-link]");
            if (link) {
                switchTab(link.dataset.tabLink);
                window.scrollTo({top: 0});
                return;
            }
            if (e.target.closest("[data-logout]")) {
                clearToken();
                state.cfg = null;
                state.trend = null;
                document.getElementById("statGrid").innerHTML = "";
                showLogin();
            }
        });

        watchChart();

        if (token()) showShell();
        else showLogin();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
