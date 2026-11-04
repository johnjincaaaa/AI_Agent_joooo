// ==============================
// 国际化（中英切换）
//  - LANG.zh / LANG.en 为翻译字典
//  - t(key) 取当前语言文案
//  - setLang(lang) 切换语言并广播 'langchange' 事件
//  - applyStaticI18n() 刷新所有带 data-i18n / data-i18n-ph 属性的静态元素
// ==============================

const LANG = {
    zh: {
        // 顶部 / 通用
        brand_name: 'Jingent AI',
        login: '登录',

        // 首页
        home_hero_title: '高性能 · AI 工作台',
        home_hero_subtitle: '一站式 AI 对话 · AI Agent · 岗位匹配',
        home_card_1_title: 'AI 对话',
        home_card_1_desc: '智能聊天 · 多模型支持 · 代码增强',
        home_card_3_title: '推荐',
        home_card_3_desc: 'AI 智能匹配 · 精准职业推荐',

        logged_in: '已登录',
        not_logged_in: '未登录',
        guide_btn: '接入教程',
        lang_toggle_title: '切换中/英文',

        // 主题切换
        theme_toggle_title: '切换亮/暗主题',
        theme_to_light: '切换到亮色主题',
        theme_to_dark: '切换到暗色主题',

        // 右侧悬浮图标
        float_share: '分享APP',
        float_service: '在线客服',
        float_app: '下载App',

        // 分享弹窗
        share_modal_title: '分享APP 赚奖励',
        share_link_label: '你的专属推广链接',
        share_copy_btn: '一键复制',
        share_copied: '已复制',
        share_need_login: '登录后才能获取专属推广链接',
        share_need_login_sub: '登录即可分享赚奖励',

        // 侧边栏
        sidebar_workspace_section: '工作台',
        nav_home: '首页',
        nav_home_title: '返回首页',
        nav_main_chat: '主对话',
        nav_main_chat_title: '主对话（桌宠陪伴）',
        nav_memory_galaxy: '记忆银河',
        nav_memory_galaxy_title: '记忆银河（长期记忆旋臂星系 · 遗忘推演）',
        nav_creation_center: '创作中心',
        nav_creation_center_title: 'Jingent 创作中心（独立记忆体创建 · 宠物模型 · 自定义角色）',
        nav_wallet_title: '推广收益 · 提现',
        settings: '系统设置',
        avatar_alt: '头像',
        sidebar_jobhunt_section: '找工作',
        jobhunt_entry: '简历制作 · 岗位推荐',
        sidebar_wallet_section: '我的收益',
        wallet_entry: '推广钱包 · 提现',
        history_label: '历史会话',
        new_session: '新对话',
        logout: '退出登录',

        // 系统设置弹窗
        settings_title: '系统设置',
        settings_subtitle: '管理你的账户信息',
        settings_tab_profile: '个人资料',
        settings_tab_security: '账号安全',
        settings_tab_llm: 'AI 配置',
        settings_tab_memory: '我的记忆',
        settings_tab_voice: '记忆体语音',
        settings_avatar_current: '当前头像',
        settings_avatar_pick_title: '选择内置煤球头像',
        settings_avatar_upload: '上传自定义头像',
        settings_avatar_upload_tip: '支持 PNG/JPG/WEBP/GIF，≤2MB',
        settings_label_account: '账号',
        settings_label_phone: '手机号',
        settings_label_nickname: '昵称',
        settings_ph_nickname: '请输入昵称',
        settings_save_nickname: '保存昵称',
        settings_old_pwd: '原密码',
        settings_ph_old_pwd: '请输入原密码',
        settings_new_pwd: '新密码',
        settings_ph_new_pwd: '请输入新密码（至少6位）',
        settings_confirm_pwd: '确认新密码',
        settings_ph_confirm_pwd: '请再次输入新密码',
        settings_change_pwd: '修改密码',
        settings_show_pwd: '显示密码',
        settings_llm_base_url: 'API 地址（OpenAI 兼容）',
        settings_llm_model: '模型名',
        settings_llm_api_key: 'API Key',
        settings_llm_tip: '配置仅保存在当前浏览器，AI 对话会使用它；留空的项自动使用服务器默认配置。',
        settings_embedding_subtitle: '向量模型（历史记忆语义检索用，留空则用服务器默认）',
        settings_embedding_base_url: '向量模型 API 地址',
        settings_embedding_model: '向量模型名',
        settings_embedding_api_key: '向量模型 API Key',
        settings_embedding_tip: '向量模型需与服务器向量库维度一致；更换模型后请在服务器端重建向量库。',
        settings_save_config: '保存配置',
        settings_test_conn: '测试连接',
        settings_memory_login_tip: '登录后 AI 才能记住你，并随对话自动积累细节记忆。',
        settings_memory_galaxy_title: '记忆银河',
        settings_memory_galaxy_desc: '把长期记忆画成旋臂星系：核心是钉住的画像，旋臂由内向外是越来越容易被忘掉的记忆，还能推演遗忘。',
        settings_memory_galaxy_open: '打开记忆银河',
        settings_global_memory_label: '全局画像（AI 长期记住的核心信息）',
        settings_global_memory_ph: '例：我叫小舟，目前在深圳实习，喜欢打游戏',
        settings_add: '添加',
        settings_global_memory_title: '全局画像',
        settings_memory_empty: '暂无，添加一条试试',
        settings_detail_memory_title: '细节记忆（对话后自动积累）',
        settings_detail_memory_empty: '暂无细节记忆',
        memory_cat_other: '未分类',
        memory_stars_profile_label: '全局画像',
        memory_stars_hint: '星越亮 = 越被在意 · 悬停看内容 · 点击看详情',
        memory_stars_times: '被想起 {n} 次',
        memory_stars_importance: '重要度 {n}%',
        memory_stars_profile_hint: '长期记住的核心信息',
        memory_stars_empty: '还没有记忆，和 TA 多聊聊就会亮起来',
        memory_stars_delete: '删除',

        // 顶部工具条按钮
        fold_title: '折叠/展开侧边栏',
        new_chat_title: '新建对话',

        // 空状态
        empty_title: '我是 Jingent AI，有什么可以帮你？',
        empty_desc: '输入你的问题，开启一段新的对话',

        // 场景模板
        scene_section: '选择场景，快速开始',
        scene_chat: '日常闲聊',
        scene_chat_desc: '轻松聊天，陪伴解闷',
        scene_office: '办公文案',
        scene_office_desc: '周报/总结/邮件/演讲稿',
        scene_study: '学习答疑',
        scene_study_desc: '作业辅导/知识讲解',
        scene_life: '生活解惑',
        scene_life_desc: '情感/建议/攻略推荐',
        scene_general: '通用模式',
        scene_current: '当前场景：',

        // 对话管理
        chat_rename: '重命名',
        chat_delete: '删除',
        chat_clear: '清空对话',
        chat_search_title: '搜索消息',
        chat_search_ph: '搜索对话消息...',
        chat_clear_confirm: '确定要清空当前对话吗？此操作不可撤销。',
        chat_delete_confirm: '确定要删除这个会话吗？此操作不可撤销。',
        chat_rename_placeholder: '请输入新的会话名称',
        chat_rename_ok: '已重命名',
        chat_delete_ok: '已删除',
        chat_clear_ok: '已清空',
        chat_need_login: '登录后才能管理对话历史',

        // 输入区
        input_placeholder: '输入问题，可粘贴图片/文档或点击附件上传...',
        attach_btn: '附件',
        attach_title: '上传图片或文档',
        voice_btn: '语音',
        voice_input: '语音输入（录音转文字）',
        skills_btn: '技能',
        skills_tip: '选择 AI 技能工具链',
        skills_dropdown_title: '选择技能',
        skills_empty: '暂无可用技能',
        online_btn: '智能联网',
        online_tip: '按需搜索网页',
        net_off: '未联网',
        net_on: '已联网',
        net_status_title: '智能体是否基于网络回答',
        input_tip: '内容由 AI 生成，请注意甄别',
        send_title: '发送',

        // 登录/注册弹窗
        modal_welcome: '欢迎使用 Jingent AI',
        modal_subtitle: '登录后即可保存你的对话历史',
        tab_login: '登录',
        tab_register: '注册',
        label_username: '用户名',
        label_password: '密码',
        label_repassword: '确认密码',
        ph_login_username: '请输入用户名',
        ph_login_pwd: '请输入密码',
        ph_reg_username: '请设置用户名',
        ph_reg_pwd: '请设置密码',
        ph_reg_repwd: '请再次输入密码',
        btn_do_login: '立即登录',
        btn_do_register: '立即注册',
        show_pwd: '显示密码',
        hide_pwd: '隐藏密码',

        // 登录/注册 提示（alert / modal）
        alert_need_username: '请输入用户名！',
        alert_need_pwd: '请输入密码！',
        alert_need_repwd: '请确认密码！',
        alert_pwd_mismatch: '两次输入的密码不一致！',
        alert_login_fail: '登录失败：',
        alert_login_neterr: '网络异常，登录请求失败！',
        alert_reg_success: '注册成功！请登录',
        alert_reg_fail: '注册失败：',
        alert_reg_neterr: '网络异常，注册请求失败！',
        unknown_error: '未知错误',
        please_login: '未登录,请登录！',
        login_expired: '🔐 登录已过期，请重新登录！',

        // 聊天错误 / 限流
        ai_error_key: 'AI出错了，请检查API Key',
        rate_limit_msg: '未登录用户今日免费体验次数已用完，请注册或登录后继续使用',
        rate_limit_modal: '🎁 今日免费体验已用完',
        rate_limit_sub: '注册成为会员，畅享无限次对话；也可联系在线客服咨询。',
        upload_fail: '文件上传失败，请重试',
        modal_default_sub: '请重新登录后继续使用',
        modal_go_register: '立即注册',
        quota_remaining_1: '今日免费体验还剩 ',
        quota_remaining_2: ' 次',
        quota_low_tip: '免费次数快用完啦，注册成为会员可无限畅聊',

        // 推广钱包 / 提现
        wallet_title: '推广钱包',
        wallet_desc: '分享专属链接邀请好友下载APP，即可赚取奖励并提现。',
        wallet_balance: '当前余额',
        wallet_referrals: '累计有效推广',
        wallet_people: ' 人',
        wallet_withdraw_title: '申请提现',
        wallet_withdraw_hint: '提交后将提现全部余额，后台人工审核后打款。',
        wallet_paypal_ph: '请输入你的收款邮箱',
        wallet_withdraw_btn: '提交提现申请',
        wallet_records_title: '提现记录',
        wallet_no_records: '暂无提现记录',
        wallet_status_pending: '待审核',
        wallet_status_paid: '已到账',
        wallet_status_rejected: '已驳回',
        wallet_invalid_email: '请输入有效的邮箱',
        wallet_withdraw_ok: '提现申请已提交，等待人工审核',
        wallet_withdraw_fail: '提现失败，请稍后重试',
        wallet_need_login: '登录后才能查看推广钱包',
        wallet_need_login_sub: '登录即可查看余额并提现',

        // 技能名（前端兜底）
        skill_image_name: '图片解析',
        skill_image_desc: '分析图片内容、尺寸、格式等属性',
        skill_doc_name: '文档解析',
        skill_doc_desc: '读取 PDF、Word、TXT 文件内容',

        // 技能面板（市场/导入/安装）
        skills_market: '技能市场',
        skills_market_title: '技能市场',
        skills_market_desc: '发现更多技能，一键安装使用',
        skills_all: '全部',
        skills_import: '导入技能包',
        skills_import_title: '导入技能包',
        skills_import_drop: '点击或拖拽 zip 包到这里',
        skills_import_support: '支持 .zip 格式，含 skill.json 或 SKILL.md',
        skills_install: '安装',
        skills_install_confirm: '安装技能',
        skills_install_failed: '安装失败',
        skills_installed: '安装成功，已自动启用！',
        skills_enable: '启用',
        skills_enabled: '已启用',
        skills_import_invalid: '请上传 zip 格式的技能包',
        skills_import_error: '解析失败',
        skills_import_net_error: '网络错误，请重试',
        skills_preview_prompt: '系统提示词预览',
        skills_no_prompt: '无',

        // 通用操作（技能面板等）
        cancel: '取消',
        loading: '解析中...',
        retry: '重新选择',
        installing: '安装中...',
        expand_code: '展开/折叠',

        // 找工作面板
        job_panel_title: '找工作',
        job_panel_desc: '完善个人画像 → 选择简历模板 → AI 生成简历 → 匹配 BOSS 直聘对口岗位（当前为虚拟数据）',
        job_step_1: '① 个人画像',
        job_step_2: '② 简历模板',
        job_step_3: '③ AI 简历',
        job_step_4: '④ 岗位推荐',
        job_section_1: '个人画像',
        job_section_2: '挑选简历模板',
        job_section_3: 'AI 完善简历',
        job_section_4: '对口岗位推荐',
        job_save_profile: '保存画像',
        job_resume_empty: '点击「AI 完善简历」生成专业简历',
        job_generate_btn: 'AI 完善简历',
        job_match_default: '完成画像与简历后，点击匹配推荐岗位',
        job_match_btn: '匹配推荐岗位',

        // 找工作表单字段 label
        f_name: '姓名',
        f_gender: '性别',
        f_age: '年龄',
        f_education: '学历',
        f_major: '专业',
        f_school: '毕业院校',
        f_experience_years: '工作年限',
        f_target_city: '期望城市',
        f_target_role: '期望岗位',
        f_skills: '技能标签',
        f_work_experience: '工作经历',
        f_project_experience: '项目经历',
        f_self_intro: '自我评价',
        f_preset_resume: '预设简历草稿（AI 将在此基础上完善）',

        // 找工作表单 placeholder
        ph_name: '张三',
        ph_age: '24',
        ph_major: '计算机科学与技术',
        ph_school: 'XX大学',
        ph_target_city: '北京',
        ph_target_role: 'Java开发工程师',
        ph_skills: 'Java,Spring Boot,MySQL',
        ph_work_experience: '公司、岗位、时间、主要工作内容…',
        ph_project_experience: '项目名称、职责、技术栈、成果…',
        ph_self_intro: '简要介绍优势与求职动机…',
        ph_preset_resume: '可粘贴现有简历内容，AI 会自动润色补全…',

        // 找工作下拉选项
        opt_select: '请选择',
        opt_male: '男',
        opt_female: '女',
        opt_edu_college: '大专',
        opt_edu_bachelor: '本科',
        opt_edu_master: '硕士',
        opt_edu_phd: '博士',
        opt_exp_fresh: '在校/应届',
        opt_exp_1_3: '1-3年',
        opt_exp_3_5: '3-5年',
        opt_exp_5_10: '5-10年',

        // 找工作状态提示
        js_template_fail: '模板加载失败',
        js_save_local: '已保存到本地',
        js_save_local_hint: '已保存到本地（登录后可同步云端）',
        js_save_expired: '登录已过期，仅保存到本地',
        js_save_cloud: '已同步到云端',
        js_save_cloud_fail: '云端同步失败，已保存到本地',
        js_need_resume_fields: '请至少填写姓名、期望岗位或预设简历草稿',
        js_generating: 'AI 正在完善简历，请稍候…',
        js_gen_rate_limit: '免费次数已用完，请登录后继续使用',
        js_resume_done: '简历已生成',
        js_resume_fail: '简历生成失败，请稍后重试',
        js_no_jobs: '暂无匹配岗位，请完善画像后重试',
        js_need_match_fields: '请填写期望岗位或技能标签',
        js_matching: '正在匹配 BOSS 直聘岗位（虚拟数据）…',
        js_match_rate_limit: '免费次数已用完，请登录后继续使用',
        js_match_fail: '岗位匹配失败，请稍后重试',
        js_match_done_1: '已推荐 ',
        js_match_done_2: ' 个对口岗位',
        job_match_score: '匹配度 ',
        job_source_default: 'BOSS直聘',

        // 简历漏洞检测
        job_step_5: '⑤ 简历体检',
        job_step_6: '⑥ 模拟面试',
        job_section_5: 'AI 简历漏洞检测',
        job_section_5_desc: '6 大维度全面扫描简历问题，获取针对性优化建议',
        job_audit_btn: '开始检测',
        job_audit_analyzing: 'AI 正在分析简历...',
        job_audit_score: '简历评分',
        job_audit_summary: '总体评价',
        job_audit_issues: '发现问题',
        job_audit_severity_high: '高风险',
        job_audit_severity_medium: '中风险',
        job_audit_severity_low: '低风险',
        job_audit_category_content: '内容完整性',
        job_audit_category_format: '格式与结构',
        job_audit_category_keyword: '关键词优化',
        job_audit_category_tone: '专业语气',
        job_audit_category_experience: '经历呈现',
        job_audit_category_redflag: '风险信号',
        job_audit_suggestion: '优化建议',
        job_audit_fail: '检测失败，请稍后重试',
        job_audit_need_resume: '请先生成或填写简历内容',

        // 模拟面试
        job_section_6: 'AI 模拟面试',
        job_section_6_desc: '多轮渐进式面试，实时点评答题表现，助你快速提升',
        job_interview_start_btn: '开始模拟面试',
        job_interview_next_btn: '提交回答，下一题',
        job_interview_restart_btn: '重新开始',
        job_interview_round: '第 {n} 轮',
        job_interview_type_general: '开场介绍',
        job_interview_type_technical: '技术面试',
        job_interview_type_behavioral: '行为面试',
        job_interview_type_case: '案例分析',
        job_interview_tips: '答题技巧',
        job_interview_feedback: '上一轮回答点评',
        job_interview_feedback_relevance: '切题程度',
        job_interview_feedback_clarity: '清晰度',
        job_interview_feedback_examples: '实例支撑',
        job_interview_feedback_communication: '表达专业性',
        job_interview_feedback_comment: '综合点评',
        job_interview_input_ph: '请输入你的回答...',
        job_interview_processing: 'AI 正在点评并生成下一题...',
        job_interview_need_answer: '请先输入你的回答',

        // 快捷模板
        template_recent: '最近使用',
        template_favorite: '我的收藏',
        template_favorite_add: '收藏',
        template_favorite_remove: '取消收藏',
        template_search_ph: '搜索模板...',
        template_empty: '暂无模板',
        template_recent_empty: '暂无最近使用',
        template_favorite_empty: '暂无收藏',

        // 签到
        checkin_title: '每日签到',
        checkin_btn: '立即签到',
        checkin_btn_done: '今日已签到',
        checkin_streak: '连续签到 {n} 天',
        checkin_total: '累计签到 {n} 次',
        checkin_reward: '获得 ¥{amount} + {days} 天会员',
        checkin_bonus: '连续 {n} 天额外奖励 ¥{bonus}',
        checkin_fail: '签到失败，请稍后重试',

        // 提现风控
        wallet_available: '可提现金额',
        wallet_cannot_withdraw: '暂不可提现',
        wallet_min_withdraw: '最低提现 ¥{n}',
        wallet_new_user_wait: '新用户需注册满 {h} 小时可提现（还剩 {r} 小时）',
        wallet_reward_freeze: '最近 {h} 小时内有 {n} 笔推广奖励在审核中',

        // 用户体验
        typing_indicator: 'AI 正在思考',
        copy_code: '复制代码',
        copied: '已复制',
        drag_drop_hint: '释放以文件上传',
        shortcut_send: 'Enter 发送，Ctrl+Enter 换行',
    },
    en: {
        brand_name: 'Youliao AI',
        login: 'Sign in',

        // Home page
        home_hero_title: 'High-Performance · AI Workbench',
        home_hero_subtitle: 'All-in-one AI Chat · AI Agent · Job Matching',
        home_card_1_title: 'AI Chat',
        home_card_1_desc: 'Smart conversation · Multi-model · Code enhanced',
        home_card_3_title: 'Recommendations',
        home_card_3_desc: 'AI-powered matching · Precision career advice',

        logged_in: 'Signed in',
        not_logged_in: 'Sign in',
        guide_btn: 'API Guide',
        lang_toggle_title: 'Switch Chinese / English',

        theme_toggle_title: 'Toggle light/dark theme',
        theme_to_light: 'Switch to light theme',
        theme_to_dark: 'Switch to dark theme',

        float_share: 'Share',
        float_service: 'Support',
        float_app: 'Get App',

        share_modal_title: 'Share the App, Earn Rewards',
        share_link_label: 'Your personal referral link',
        share_copy_btn: 'Copy link',
        share_copied: 'Copied',
        share_need_login: 'Sign in to get your referral link',
        share_need_login_sub: 'Sign in to share and earn',

        sidebar_workspace_section: 'Workspace',
        nav_home: 'Home',
        nav_home_title: 'Back to home',
        nav_main_chat: 'Main Chat',
        nav_main_chat_title: 'Main Chat (Desktop Pet Companion)',
        nav_memory_galaxy: 'Memory Galaxy',
        nav_memory_galaxy_title: 'Memory Galaxy (long-term memory spiral arms · forgetting preview)',
        nav_creation_center: 'Creation Center',
        nav_creation_center_title: 'Jingent Creation Center (Independent Memory · Pet Models · Custom Characters)',
        nav_wallet_title: 'Referral Earnings · Withdraw',
        settings: 'Settings',
        avatar_alt: 'Avatar',
        sidebar_jobhunt_section: 'Job Hunt',
        jobhunt_entry: 'Resume Builder · Job Match',
        sidebar_wallet_section: 'My Earnings',
        wallet_entry: 'Wallet · Withdraw',
        history_label: 'History',
        new_session: 'New Chat',
        logout: 'Log out',

        // Settings modal
        settings_title: 'Settings',
        settings_subtitle: 'Manage your account',
        settings_tab_profile: 'Profile',
        settings_tab_security: 'Security',
        settings_tab_llm: 'AI Config',
        settings_tab_memory: 'My Memory',
        settings_tab_voice: 'Memory Voice',
        settings_avatar_current: 'Current avatar',
        settings_avatar_pick_title: 'Choose a built-in avatar',
        settings_avatar_upload: 'Upload custom avatar',
        settings_avatar_upload_tip: 'PNG/JPG/WEBP/GIF, ≤2MB',
        settings_label_account: 'Account',
        settings_label_phone: 'Phone',
        settings_label_nickname: 'Nickname',
        settings_ph_nickname: 'Enter nickname',
        settings_save_nickname: 'Save nickname',
        settings_old_pwd: 'Current password',
        settings_ph_old_pwd: 'Enter current password',
        settings_new_pwd: 'New password',
        settings_ph_new_pwd: 'New password (at least 6 chars)',
        settings_confirm_pwd: 'Confirm new password',
        settings_ph_confirm_pwd: 'Re-enter new password',
        settings_change_pwd: 'Change password',
        settings_show_pwd: 'Show password',
        settings_llm_base_url: 'API URL (OpenAI compatible)',
        settings_llm_model: 'Model name',
        settings_llm_api_key: 'API Key',
        settings_llm_tip: 'Config is stored in this browser only and used for AI chats; empty fields fall back to server defaults.',
        settings_embedding_subtitle: 'Embedding model (for semantic memory search; empty = server default)',
        settings_embedding_base_url: 'Embedding API URL',
        settings_embedding_model: 'Embedding model name',
        settings_embedding_api_key: 'Embedding API Key',
        settings_embedding_tip: 'Embedding model dimension must match the server vector store; rebuild the vector store on the server after changing models.',
        settings_save_config: 'Save config',
        settings_test_conn: 'Test connection',
        settings_memory_login_tip: 'Sign in so the AI can remember you and accumulate detail memories automatically.',
        settings_memory_galaxy_title: 'Memory Galaxy',
        settings_memory_galaxy_desc: 'Paint your long-term memory as a spiral galaxy: pinned profiles in the core, short-term memories drifting outward, with a forgetting-time slider.',
        settings_memory_galaxy_open: 'Open Memory Galaxy',
        settings_global_memory_label: 'Global profile (core info the AI remembers long-term)',
        settings_global_memory_ph: 'e.g. My name is Xiaozhou, interning in Shenzhen, love gaming',
        settings_add: 'Add',
        settings_global_memory_title: 'Global profile',
        settings_memory_empty: 'Nothing yet — add one to try',
        settings_detail_memory_title: 'Detail memory (auto-accumulated after chats)',
        settings_detail_memory_empty: 'No detail memories yet',
        memory_cat_other: 'Other',
        memory_stars_profile_label: 'Profile',
        memory_stars_hint: 'Brighter = more remembered · Hover to preview · Click for details',
        memory_stars_times: 'Recalled {n} times',
        memory_stars_importance: 'Importance {n}%',
        memory_stars_profile_hint: 'Long-term core facts',
        memory_stars_empty: 'No memories yet — chat with me and the stars will light up',
        memory_stars_delete: 'Delete',

        fold_title: 'Collapse / expand sidebar',
        new_chat_title: 'New chat',

        empty_title: "I'm Youliao AI. How can I help?",
        empty_desc: 'Type your question to start a new conversation',

        // 场景模板
        scene_section: 'Choose a scene to get started',
        scene_chat: 'Casual Chat',
        scene_chat_desc: 'Casual, friendly chat',
        scene_office: 'Office Writing',
        scene_office_desc: 'Reports/summaries/emails',
        scene_study: 'Study Q&A',
        scene_study_desc: 'Homework & knowledge help',
        scene_life: 'Life Advice',
        scene_life_desc: 'Emotions/tips/advice',
        scene_general: 'General Mode',
        scene_current: 'Current scene: ',

        // 对话管理
        chat_rename: 'Rename',
        chat_delete: 'Delete',
        chat_clear: 'Clear Chat',
        chat_search_title: 'Search messages',
        chat_search_ph: 'Search conversation messages...',
        chat_clear_confirm: 'Are you sure you want to clear the current chat? This cannot be undone.',
        chat_delete_confirm: 'Are you sure you want to delete this conversation? This cannot be undone.',
        chat_rename_placeholder: 'Enter a new conversation name',
        chat_rename_ok: 'Renamed',
        chat_delete_ok: 'Deleted',
        chat_clear_ok: 'Cleared',
        chat_need_login: 'Sign in to manage chat history',

        input_placeholder: 'Type a message, paste an image/document, or click to attach…',
        attach_btn: 'Attach',
        attach_title: 'Upload image or document',
        voice_btn: 'Voice',
        voice_input: 'Voice input (speech to text)',
        skills_btn: 'Skills',
        skills_tip: 'Choose AI skill tools',
        skills_dropdown_title: 'Choose skills',
        skills_empty: 'No skills available',
        online_btn: 'Web Search',
        online_tip: 'Search the web on demand',
        net_off: 'Offline',
        net_on: 'Online',
        net_status_title: 'Whether the agent answers from the web',
        input_tip: 'Content is AI-generated. Please verify.',
        send_title: 'Send',

        modal_welcome: 'Welcome to Youliao AI',
        modal_subtitle: 'Sign in to save your conversation history',
        tab_login: 'Sign in',
        tab_register: 'Register',
        label_username: 'Username',
        label_password: 'Password',
        label_repassword: 'Confirm password',
        ph_login_username: 'Enter your username',
        ph_login_pwd: 'Enter your password',
        ph_reg_username: 'Choose a username',
        ph_reg_pwd: 'Choose a password',
        ph_reg_repwd: 'Enter the password again',
        btn_do_login: 'Sign in',
        btn_do_register: 'Register',
        show_pwd: 'Show password',
        hide_pwd: 'Hide password',

        alert_need_username: 'Please enter a username!',
        alert_need_pwd: 'Please enter a password!',
        alert_need_repwd: 'Please confirm your password!',
        alert_pwd_mismatch: 'The two passwords do not match!',
        alert_login_fail: 'Sign-in failed: ',
        alert_login_neterr: 'Network error, sign-in request failed!',
        alert_reg_success: 'Registration successful! Please sign in.',
        alert_reg_fail: 'Registration failed: ',
        alert_reg_neterr: 'Network error, registration request failed!',
        unknown_error: 'Unknown error',
        please_login: 'Not signed in. Please sign in!',
        login_expired: '🔐 Session expired. Please sign in again!',

        ai_error_key: 'AI request failed. Please check your API Key.',
        rate_limit_msg: "Today's free trial limit reached. Please register or sign in to continue.",
        rate_limit_modal: '🎁 Free trial used up for today',
        rate_limit_sub: 'Register to chat without limits, or contact online support.',
        upload_fail: 'File upload failed, please try again',
        modal_default_sub: 'Please sign in again to continue',
        modal_go_register: 'Register now',
        quota_remaining_1: 'Free trials left today: ',
        quota_remaining_2: '',
        quota_low_tip: 'Almost out of free trials. Register to chat without limits.',

        wallet_title: 'Referral Wallet',
        wallet_desc: 'Share your link, invite friends to download the App, earn rewards and withdraw.',
        wallet_balance: 'Balance (¥)',
        wallet_referrals: 'Valid Referrals',
        wallet_people: '',
        wallet_withdraw_title: 'Request Withdrawal',
        wallet_withdraw_hint: 'Submitting withdraws your full balance; paid after manual review.',
        wallet_paypal_ph: 'Enter your email for payout',
        wallet_withdraw_btn: 'Submit Withdrawal',
        wallet_records_title: 'Withdrawal Records',
        wallet_no_records: 'No withdrawal records yet',
        wallet_status_pending: 'Pending',
        wallet_status_paid: 'Paid',
        wallet_status_rejected: 'Rejected',
        wallet_invalid_email: 'Please enter a valid email',
        wallet_withdraw_ok: 'Withdrawal request submitted, awaiting review',
        wallet_withdraw_fail: 'Withdrawal failed, please try again later',
        wallet_need_login: 'Sign in to view your wallet',
        wallet_need_login_sub: 'Sign in to see your balance and withdraw',

        skill_image_name: 'Image Analysis',
        skill_image_desc: 'Analyze image content, size, format and more',
        skill_doc_name: 'Document Analysis',
        skill_doc_desc: 'Read content from PDF, Word and TXT files',

        // Skill panel (market / import / install)
        skills_market: 'Skill Market',
        skills_market_title: 'Skill Market',
        skills_market_desc: 'Discover more skills, one-click install',
        skills_all: 'All',
        skills_import: 'Import Skill',
        skills_import_title: 'Import Skill Package',
        skills_import_drop: 'Click or drag a zip here',
        skills_import_support: 'Supports .zip with skill.json or SKILL.md',
        skills_install: 'Install',
        skills_install_confirm: 'Install Skill',
        skills_install_failed: 'Install failed',
        skills_installed: 'Installed and enabled!',
        skills_enable: 'Enable',
        skills_enabled: 'Enabled',
        skills_import_invalid: 'Please upload a zip skill package',
        skills_import_error: 'Parse failed',
        skills_import_net_error: 'Network error, please retry',
        skills_preview_prompt: 'System prompt preview',
        skills_no_prompt: 'None',

        // Generic actions (skill panel etc.)
        cancel: 'Cancel',
        loading: 'Parsing...',
        retry: 'Choose again',
        installing: 'Installing...',
        expand_code: 'Expand / Collapse',

        // Quick templates
        template_recent: 'Recent',
        template_favorite: 'Favorites',
        template_favorite_add: 'Favorite',
        template_favorite_remove: 'Unfavorite',
        template_search_ph: 'Search templates...',
        template_empty: 'No templates',

        job_panel_title: 'Job Hunt',
        job_panel_desc: 'Complete your profile → pick a resume template → generate resume with AI → match relevant jobs (demo data)',
        job_step_1: '① Profile',
        job_step_2: '② Template',
        job_step_3: '③ AI Resume',
        job_step_4: '④ Job Match',
        job_section_1: 'Personal Profile',
        job_section_2: 'Pick a Resume Template',
        job_section_3: 'Polish Resume with AI',
        job_section_4: 'Recommended Jobs',
        job_save_profile: 'Save Profile',
        job_resume_empty: 'Click "Polish Resume with AI" to generate a professional resume',
        job_generate_btn: 'Polish Resume with AI',
        job_match_default: 'After finishing the profile and resume, click to match jobs',
        job_match_btn: 'Match Jobs',

        f_name: 'Name',
        f_gender: 'Gender',
        f_age: 'Age',
        f_education: 'Education',
        f_major: 'Major',
        f_school: 'School',
        f_experience_years: 'Experience',
        f_target_city: 'Target City',
        f_target_role: 'Target Role',
        f_skills: 'Skills',
        f_work_experience: 'Work Experience',
        f_project_experience: 'Project Experience',
        f_self_intro: 'Self Introduction',
        f_preset_resume: 'Resume Draft (AI will build on this)',

        ph_name: 'John Doe',
        ph_age: '24',
        ph_major: 'Computer Science',
        ph_school: 'XX University',
        ph_target_city: 'New York',
        ph_target_role: 'Java Developer',
        ph_skills: 'Java, Spring Boot, MySQL',
        ph_work_experience: 'Company, role, dates, main responsibilities…',
        ph_project_experience: 'Project name, role, tech stack, results…',
        ph_self_intro: 'Briefly describe your strengths and motivation…',
        ph_preset_resume: 'Paste your existing resume; AI will polish and complete it…',

        opt_select: 'Please select',
        opt_male: 'Male',
        opt_female: 'Female',
        opt_edu_college: 'College',
        opt_edu_bachelor: "Bachelor's",
        opt_edu_master: "Master's",
        opt_edu_phd: 'PhD',
        opt_exp_fresh: 'Student / New Grad',
        opt_exp_1_3: '1-3 yrs',
        opt_exp_3_5: '3-5 yrs',
        opt_exp_5_10: '5-10 yrs',

        js_template_fail: 'Failed to load templates',
        js_save_local: 'Saved locally',
        js_save_local_hint: 'Saved locally (sign in to sync to cloud)',
        js_save_expired: 'Session expired, saved locally only',
        js_save_cloud: 'Synced to cloud',
        js_save_cloud_fail: 'Cloud sync failed, saved locally',
        js_need_resume_fields: 'Please fill in at least name, target role or resume draft',
        js_generating: 'AI is polishing your resume, please wait…',
        js_gen_rate_limit: 'Free trial used up. Please sign in to continue.',
        js_resume_done: 'Resume generated',
        js_resume_fail: 'Failed to generate resume, please try again later',
        js_no_jobs: 'No matching jobs yet. Complete your profile and retry.',
        js_need_match_fields: 'Please fill in target role or skills',
        js_matching: 'Matching jobs (demo data)…',
        js_match_rate_limit: 'Free trial used up. Please sign in to continue.',
        js_match_fail: 'Job matching failed, please try again later',
        js_match_done_1: 'Recommended ',
        js_match_done_2: ' matching jobs',
        job_match_score: 'Match ',
        job_source_default: 'Jobs',

        // Resume audit
        job_step_5: '⑤ Resume Audit',
        job_step_6: '⑥ Mock Interview',
        job_section_5: 'AI Resume Audit',
        job_section_5_desc: '6-dimension comprehensive scan to identify resume issues and get targeted suggestions',
        job_audit_btn: 'Start Audit',
        job_audit_analyzing: 'AI is analyzing your resume...',
        job_audit_score: 'Resume Score',
        job_audit_summary: 'Overall Assessment',
        job_audit_issues: 'Issues Found',
        job_audit_severity_high: 'High Priority',
        job_audit_severity_medium: 'Medium Priority',
        job_audit_severity_low: 'Low Priority',
        job_audit_category_content: 'Content Completeness',
        job_audit_category_format: 'Format & Structure',
        job_audit_category_keyword: 'Keyword Optimization',
        job_audit_category_tone: 'Professional Tone',
        job_audit_category_experience: 'Experience Presentation',
        job_audit_category_redflag: 'Red Flags',
        job_audit_suggestion: 'Suggestion',
        job_audit_fail: 'Audit failed, please try again',
        job_audit_need_resume: 'Please generate or fill in your resume first',

        // Mock interview
        job_section_6: 'AI Mock Interview',
        job_section_6_desc: 'Multi-round progressive interview with real-time feedback to help you improve fast',
        job_interview_start_btn: 'Start Interview',
        job_interview_next_btn: 'Submit Answer & Next',
        job_interview_restart_btn: 'Restart',
        job_interview_round: 'Round {n}',
        job_interview_type_general: 'Opening',
        job_interview_type_technical: 'Technical',
        job_interview_type_behavioral: 'Behavioral',
        job_interview_type_case: 'Case Study',
        job_interview_tips: 'Tips',
        job_interview_feedback: 'Last Round Feedback',
        job_interview_feedback_relevance: 'Relevance',
        job_interview_feedback_clarity: 'Clarity',
        job_interview_feedback_examples: 'Examples',
        job_interview_feedback_communication: 'Communication',
        job_interview_feedback_comment: 'Overall Comment',
        job_interview_input_ph: 'Type your answer here...',
        job_interview_processing: 'AI is evaluating and generating the next question...',
        job_interview_need_answer: 'Please type your answer first',

        // Check-in
        checkin_title: 'Daily Check-in',
        checkin_btn: 'Check In',
        checkin_btn_done: 'Checked In Today',
        checkin_streak: '{n} day streak',
        checkin_total: '{n} total check-ins',
        checkin_reward: 'Earned ¥{amount} + {days} days membership',
        checkin_bonus: '{n}-day streak bonus ¥{bonus}',
        checkin_fail: 'Check-in failed, please try again',

        // Withdraw risk
        wallet_available: 'Available to withdraw',
        wallet_cannot_withdraw: 'Cannot withdraw now',
        wallet_min_withdraw: 'Minimum ¥{n} to withdraw',
        wallet_new_user_wait: 'New users need to wait {h}h after registration ({r}h left)',
        wallet_reward_freeze: '{n} referral rewards in the last {h}h are under review',

        // UX
        typing_indicator: 'AI is thinking',
        copy_code: 'Copy code',
        copied: 'Copied',
        drag_drop_hint: 'Drop files to upload',
        shortcut_send: 'Enter to send, Ctrl+Enter for new line',
    },
};

const I18N_STORAGE_KEY = 'app_lang';

function getLang() {
    const saved = localStorage.getItem(I18N_STORAGE_KEY);
	return saved === 'en' ? 'en' : 'zh';
}

function t(key) {
    const lang = getLang();
    // 用 in 判断而非真值，避免空字符串文案被当成缺失而回退到中文
    if (LANG[lang] && key in LANG[lang]) return LANG[lang][key];
    if (key in LANG.zh) return LANG.zh[key];
    return key;
}

function applyStaticI18n() {
    // 文本内容
    document.querySelectorAll('[data-i18n]').forEach(el => {
        el.textContent = t(el.getAttribute('data-i18n'));
    });
    // placeholder（跳过场景模式下的输入框，由场景逻辑自行处理）
    document.querySelectorAll('[data-i18n-ph]').forEach(el => {
        if (el.dataset && el.dataset.scenePh === '1') return;
        el.setAttribute('placeholder', t(el.getAttribute('data-i18n-ph')));
    });
    // title 属性
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
    });
    // data-tip 属性（tooltip）
    document.querySelectorAll('[data-i18n-tip]').forEach(el => {
        el.setAttribute('data-tip', t(el.getAttribute('data-i18n-tip')));
    });
    // <html lang>
    document.documentElement.setAttribute('lang', getLang() === 'en' ? 'en' : 'zh-CN');
}

function setLang(lang) {
    const next = lang === 'en' ? 'en' : 'zh';
    localStorage.setItem(I18N_STORAGE_KEY, next);
    applyStaticI18n();
    updateLangToggleLabel();
    // 广播给动态渲染的模块（技能、找工作、聊天状态等）
    document.dispatchEvent(new CustomEvent('langchange', { detail: { lang: next } }));
}

function toggleLang() {
    setLang(getLang() === 'en' ? 'zh' : 'en');
}

function updateLangToggleLabel() {
    const btn = document.getElementById('langToggleBtn');
    if (btn) {
        // 显示“将切换到的目标语言”，直观易懂
        btn.textContent = getLang() === 'en' ? '中' : 'EN';
    }
}

// 暴露到全局，供其它脚本调用
window.t = t;
window.getLang = getLang;
window.setLang = setLang;
window.applyStaticI18n = applyStaticI18n;

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('langToggleBtn');
    if (btn) {
        btn.addEventListener('click', toggleLang);
    }
    applyStaticI18n();
    updateLangToggleLabel();
});
