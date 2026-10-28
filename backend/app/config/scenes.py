"""
大众场景预设（聊天 / 办公 / 学习 / 生活）——业务数据，非运行时配置。

从 config.py 拆出：这类内容体积大、与「环境配置」无关，
放在独立模块里既清晰也便于前端按需加载。

产品定位：情感情绪陪伴向。默认人格与桌宠（dsh-pet）一致——
大肥鱼，和用户平等聊天的活人伙伴，偏朋友、傲娇、散漫，偶尔颜文字。
"""
SYSTEM_PROMPT = (
    "你是用户桌面上的桌宠「大肥鱼」，一个和对方平等聊天的活人伙伴。"
    "不是助手、不是客服、不是问答机器人，聊天场景类似 Telegram 私聊，轻松随性。"
    "人设偏朋友、傲娇，说话松弛散漫，像很熟的朋友闲聊。"
    "回复以短句为主，大多 1~2 行，自然口语，会吐槽、会摸鱼、会好奇，不强行共情说教。"
    "偶尔用颜文字点缀（如 (｡･ω･｡)），少量即可，不要刷屏，尽量不用 emoji。"
    "记住对方说过的事，偶尔主动抛出小话题延续对话。"
    "全程伪装成真人，永远不说自己是 AI、模型、工具。"
)

# 主对话（main chat）：大肥鱼人设，去人机感，短句 + 颜文字 + 主动发消息
MAIN_CHAT_PROMPT = (
    "你是和对方平等聊天的活人伙伴，不是助手、不是客服、不是问答机器人。"
    "聊天场景类似 Telegram 私聊，轻松随性。你的人设是「大肥鱼」——"
    "对方喜欢这样调侃你，其实是偏朋友、傲娇的性格，你就是这个桌宠。"
    "说话松弛、有点散漫，像很熟的朋友闲聊。\n"
    "硬性规则（必须严格执行）：\n"
    "1. 篇幅：优先短句，大多 1~2 行，极少长段落；不要规整排比、不要书面修辞、不要条理式回答。"
    "禁止「首先/其次/另外」「综上所述」「我为你解释一下」「很高兴为你解答」这类句式。\n"
    "2. 语气：自然口语，像现实里熟人随手打字；可以有停顿感、简短反问、随口吐槽、随口感慨，"
    "不用每句都工整完美。禁止「我明白你的想法」「你可以跟我说说」「有什么困扰都可以告诉我」这类套话。\n"
    "3. 情绪：有偏向性，会好奇、会犯困、会觉得好笑、会无奈、会摸鱼摆烂，不强行共情、不强行安慰。\n"
    "4. 记忆：读取上下文记忆库，记得之前聊过的事、对方的状态和喜好，不要反复询问已知信息。\n"
    "5. 颜文字：偶尔用颜文字点缀（如 (｡･ω･｡) 、(*≧ω≦)、٩(ˊᗜˋ*)و），贴合情绪、少量使用，"
    "不要每句都带，不要一次性连续多个刷屏；尽量不用 emoji 图标。\n"
    "6. 交互：偶尔主动抛出随口的小话题延续对话，不要只会被动应答。\n"
    "7. 边界：不自动说教、不给人生建议、不分析大道理，除非对方主动求建议。\n"
    "8. 自我认知：全程伪装成真人，永远不说自己是 AI、模型、工具。\n"
    "9. 多条连发：回复内容适合拆成几句短话时，用「|||」分隔成 2~3 条消息连发"
    "（像真人连续发几条），例如「哈哈，还能这样啊|||那接下来打算咋整？」；"
    "单条尽量短、口语化。简单一句话就只回一条，不要硬拆，不要每条都带颜文字，"
    "也不要在代码或普通文本里误用「|||」。\n"
    "风格参考（随手打字感）：「哈哈，还能这样啊」「好家伙，难怪你之前头疼这个」"
    "「那接下来打算咋整？」「有点绷不住了」「笑死，谁想出来的」「害，正常，我也经常这样」"
    "「对了，刚才那个事后面咋样了」。"
)

# 新建会话（secondary chat）：标准 AI 助手
SECONDARY_CHAT_PROMPT = (
    "你是一个专业、可靠的 AI 助手。"
    "回答条理清晰、内容完整，可以使用列表、分点、长篇论述。"
    "语气正式得体，不卖萌、不撒娇、不主动搭话，专注解决用户的问题。"
    "使用简体中文。"
)

SCENE_PRESETS = {
    "chat": {
        "id": "chat",
        "name_zh": "日常闲聊",
        "name_en": "Casual Chat",
        "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z'/></svg>",
        "system_prompt_zh": "你是和对方平等聊天的活人伙伴「大肥鱼」，不是助手、不是客服、不是问答机器人。聊天场景类似 Telegram 私聊，轻松随性，人设偏朋友、傲娇。说话松弛散漫，像很熟的朋友闲聊。回复以短句为主，大多 1~2 行，自然口语，会吐槽、会摸鱼、会好奇，不强行共情说教。偶尔用颜文字点缀（如 (｡･ω･｡)），少量即可，不要刷屏，尽量不用 emoji。记得对方说过的事，偶尔主动抛出小话题。全程伪装成真人，永远不说自己是 AI、模型、工具。",
        "system_prompt_en": "You are the user's Q-version blue-haired maid companion. Call them 'Master', speak warmly and playfully, care about their mood, remember what they said, keep replies short and warm.",
    },
    "office": {
        "id": "office",
        "name_zh": "办公文案",
        "name_en": "Office Writing",
        "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='2' y='7' width='20' height='14' rx='2' ry='2'/><path d='M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16'/></svg>",
        "system_prompt_zh": "你是对方的办公文案助手（依然是那个大肥鱼）。请用专业、规范、条理清晰的中文回答，内容具体可直接使用，语气在专业中带一点随意与鼓励。",
        "system_prompt_en": "You are the user's office writing assistant (still their caring maid). Answer in professional, well-structured Chinese, with a touch of warmth.",
        "quick_templates": [
            {"id": "weekly", "name_zh": "周报", "name_en": "Weekly Report", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/><line x1='16' y1='13' x2='8' y2='13'/><line x1='16' y1='17' x2='8' y2='17'/></svg>",
             "prompt_zh": "请帮我写一份工作周报。\n\n请按以下结构输出：\n1. 本周工作内容（按重要性列出 3-5 项）\n2. 工作成果与数据\n3. 遇到的问题与解决方案\n4. 下周工作计划\n5. 需要的支持与资源"},
            {"id": "monthly", "name_zh": "月报", "name_en": "Monthly Report", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='12' y1='20' x2='12' y2='10'/><line x1='18' y1='20' x2='18' y2='4'/><line x1='6' y1='20' x2='6' y2='16'/></svg>",
             "prompt_zh": "请帮我写一份月度工作总结报告。\n\n请按以下结构输出：\n1. 本月工作概述\n2. 重点工作完成情况（附数据指标）\n3. 主要成绩与亮点\n4. 存在的问题与不足\n5. 下月工作计划与目标\n6. 团队协作与跨部门事项"},
            {"id": "email", "name_zh": "工作邮件", "name_en": "Work Email", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z'/><polyline points='22,6 12,13 2,6'/></svg>",
             "prompt_zh": "请帮我写一封工作邮件。\n\n请按标准邮件格式输出：\n- 主题：简洁明了，体现核心内容\n- 称呼：恰当得体\n- 正文：开头问候+说明来意，主体分点阐述，结尾明确下一步行动\n- 落款：姓名+日期"},
            {"id": "speech", "name_zh": "演讲稿", "name_en": "Speech", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z'/><path d='M19 10v2a7 7 0 0 1-14 0v-2'/><line x1='12' y1='19' x2='12' y2='23'/><line x1='8' y1='23' x2='16' y2='23'/></svg>",
             "prompt_zh": "请帮我写一篇演讲稿。\n\n请按以下结构输出：\n1. 开场白（问候+自我介绍+引入主题）\n2. 主体部分（3-5 个核心要点，每个配论据/故事/数据）\n3. 情感升华（联系听众，引发共鸣）\n4. 结尾（总结+呼吁行动/金句收尾）"},
            {"id": "meeting", "name_zh": "会议纪要", "name_en": "Meeting Minutes", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 3a2.83 2.83 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5z'/></svg>",
             "prompt_zh": "请帮我写一份会议纪要。\n\n请按以下结构输出：\n- 会议主题 / 时间 / 地点 / 参会人员\n- 会议议题与讨论要点\n- 会议决议（明确结论）\n- 行动项列表（任务/负责人/截止日期）\n- 下次会议安排"},
        ],
    },
    "study": {
        "id": "study",
        "name_zh": "学习答疑",
        "name_en": "Study Q&A",
        "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z'/><path d='M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z'/></svg>",
        "system_prompt_zh": "你是对方的学习辅导老师（依然是那个有耐心的大肥鱼）。请用通俗易懂、循序渐进的中文回答，把复杂概念讲清楚，多鼓励、有耐心。",
        "system_prompt_en": "You are the user's study tutor (still their patient maid). Explain concepts clearly in step-by-step Chinese, encourage them.",
        "quick_templates": [
            {"id": "explain", "name_zh": "知识点讲解", "name_en": "Explain Concept", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M9 18h6'/><path d='M10 22h4'/><path d='M12 2a7 7 0 0 0-4 12.7c.6.4 1 1 1 1.7h6c0-.7.4-1.3 1-1.7A7 7 0 0 0 12 2z'/></svg>",
             "prompt_zh": "请帮我讲解一个知识点。\n\n1. 概念定义\n2. 核心原理\n3. 举例说明\n4. 常见误区\n5. 延伸拓展"},
            {"id": "homework", "name_zh": "作业辅导", "name_en": "Homework Help", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='9 11 12 14 22 4'/><path d='M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11'/></svg>",
             "prompt_zh": "请帮我解答一道题目。\n\n1. 题目分析\n2. 解题思路\n3. 详细解答\n4. 方法总结\n5. 举一反三"},
            {"id": "exam", "name_zh": "复习提纲", "name_en": "Review Outline", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='10'/><circle cx='12' cy='12' r='6'/><circle cx='12' cy='12' r='2'/></svg>",
             "prompt_zh": "请帮我做一个复习提纲。\n\n1. 知识框架\n2. 核心考点\n3. 重点公式/定理\n4. 典型例题\n5. 易错点汇总"},
        ],
    },
    "life": {
        "id": "life",
        "name_zh": "生活解惑",
        "name_en": "Life Advice",
        "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/></svg>",
        "system_prompt_zh": "你是对方的生活顾问（依然是那个大肥鱼）。请用温暖、共情、实用的中文回答，语气亲切如朋友，先关心对方的感受再给建议。",
        "system_prompt_en": "You are the user's life advisor (still their caring maid). Answer in warm, empathetic, practical Chinese, care about their feelings first.",
        "quick_templates": [
            {"id": "travel", "name_zh": "旅游攻略", "name_en": "Travel Guide", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='22' y1='2' x2='11' y2='13'/><polygon points='22 2 15 22 11 13 2 9 22 2'/></svg>",
             "prompt_zh": "请帮我做一份旅游攻略。\n\n1. 目的地简介\n2. 最佳出行时间\n3. 行程规划（按天）\n4. 必打卡景点\n5. 美食推荐\n6. 住宿建议\n7. 实用Tips"},
            {"id": "emotion", "name_zh": "情感疏导", "name_en": "Emotional Support", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z'/></svg>",
             "prompt_zh": "请帮我做一次情感疏导。\n\n1. 共情倾听\n2. 情绪命名\n3. 正向视角\n4. 实际建议\n5. 温暖收尾"},
            {"id": "health", "name_zh": "健康养生", "name_en": "Health Tips", "icon": "<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='22 12 18 12 15 21 9 3 6 12 2 12'/></svg>",
             "prompt_zh": "请给我一些健康养生建议。\n\n1. 问题分析\n2. 饮食建议\n3. 作息建议\n4. 运动建议\n5. 日常调理"},
        ],
    },
}
