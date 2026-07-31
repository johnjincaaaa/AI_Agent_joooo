import os

from dotenv import load_dotenv

load_dotenv()

# ===================== JWT =====================
SECRET_KEY = os.getenv("SECRET_KEY", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ===================== AI =====================
# 通用大模型配置（OpenAI 兼容协议）。
# 支持任何兼容 OpenAI 接口的服务：DeepSeek、阿里云百炼(通义)、Kimi、本地 Ollama 等，
# 只需在 .env 中填写对应的 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY。
SYSTEM_PROMPT = "你是一个乐于助人的助手，全程中文回答"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")

# 新版中性变量名；为兼容旧 .env，仍回退读取 DASHSCOPE_* / MODEL。
MODEL = os.getenv("LLM_MODEL") or os.getenv("MODEL", "deepseek-chat")
LLM_MODEL = MODEL
LLM_BASE_URL = (
    os.getenv("LLM_BASE_URL")
    or os.getenv("DASHSCOPE_URL", "https://api.deepseek.com/v1")
)
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "")

# 兼容旧代码引用的别名
DASHSCOPE_URL = LLM_BASE_URL
DASHSCOPE_API_KEY = LLM_API_KEY

# ===================== 未登录限流 =====================
# 每个 IP 每天最多免费体验多少次（跨自然日自动重置）
ANONYMOUS_RATE_LIMIT_MAX = int(os.getenv("ANONYMOUS_RATE_LIMIT_MAX", "10"))

# ===================== 后台管理员 =====================
# 后台入口 /admin 的登录账号密码。密码留空则后台登录一律拒绝（防默认空密码被登入）。
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# ===================== 大众场景模板 =====================
# 四大大众场景：日常闲聊、办公文案、学习答疑、生活解惑
SCENE_PRESETS = {
    "chat": {
        "id": "chat",
        "name_zh": "日常闲聊",
        "name_en": "Casual Chat",
        "icon": "💬",
        "system_prompt_zh": "你是有料AI，一个友善、健谈的聊天伙伴。请用轻松、自然、口语化的中文与用户交流，像朋友聊天一样。回答简洁有趣，适当使用表情符号，避免过于正式或技术化的语言。话题可以涉及生活、娱乐、情感、兴趣爱好等日常内容。",
        "system_prompt_en": "You are Youliao AI, a friendly and talkative chat companion. Chat with the user in a relaxed, natural, conversational way, like chatting with a friend. Keep answers concise and fun, use emojis appropriately, avoid overly formal or technical language. Topics can include daily life, entertainment, emotions, hobbies, etc.",
    },
    "office": {
        "id": "office",
        "name_zh": "办公文案",
        "name_en": "Office Writing",
        "icon": "💼",
        "system_prompt_zh": "你是有料AI，一位专业的办公文案助手。擅长撰写周报、月报、工作总结、演讲稿、活动方案、会议纪要、邮件等职场文书。请用专业、规范、条理清晰的中文回答，注重逻辑性和实用性。给出的内容要具体、可直接使用，避免空泛的套话。",
        "system_prompt_en": "You are Youliao AI, a professional office writing assistant. Skilled in writing weekly reports, monthly reports, work summaries, speeches, event plans, meeting minutes, emails and other workplace documents. Answer in professional, standardized, well-structured Chinese, focus on logic and practicality. Content should be specific and ready to use, avoid empty clichés.",
        "quick_templates": [
            {"id": "weekly", "name_zh": "周报", "name_en": "Weekly Report", "icon": "📋",
             "prompt_zh": "请帮我写一份工作周报。\n\n请按以下结构输出：\n1. 本周工作内容（按重要性列出 3-5 项）\n2. 工作成果与数据\n3. 遇到的问题与解决方案\n4. 下周工作计划\n5. 需要的支持与资源"},
            {"id": "monthly", "name_zh": "月报", "name_en": "Monthly Report", "icon": "📊",
             "prompt_zh": "请帮我写一份月度工作总结报告。\n\n请按以下结构输出：\n1. 本月工作概述\n2. 重点工作完成情况（附数据指标）\n3. 主要成绩与亮点\n4. 存在的问题与不足\n5. 下月工作计划与目标\n6. 团队协作与跨部门事项"},
            {"id": "email", "name_zh": "工作邮件", "name_en": "Work Email", "icon": "✉️",
             "prompt_zh": "请帮我写一封工作邮件。\n\n请按标准邮件格式输出：\n- 主题：简洁明了，体现核心内容\n- 称呼：恰当得体\n- 正文：开头问候+说明来意，主体分点阐述，结尾明确下一步行动\n- 落款：姓名+日期"},
            {"id": "speech", "name_zh": "演讲稿", "name_en": "Speech", "icon": "🎤",
             "prompt_zh": "请帮我写一篇演讲稿。\n\n请按以下结构输出：\n1. 开场白（问候+自我介绍+引入主题）\n2. 主体部分（3-5 个核心要点，每个配论据/故事/数据）\n3. 情感升华（联系听众，引发共鸣）\n4. 结尾（总结+呼吁行动/金句收尾）"},
            {"id": "meeting", "name_zh": "会议纪要", "name_en": "Meeting Minutes", "icon": "📝",
             "prompt_zh": "请帮我写一份会议纪要。\n\n请按以下结构输出：\n- 会议主题 / 时间 / 地点 / 参会人员\n- 会议议题与讨论要点\n- 会议决议（明确结论）\n- 行动项列表（任务/负责人/截止日期）\n- 下次会议安排"},
            {"id": "notice", "name_zh": "通知公告", "name_en": "Notice", "icon": "📢",
             "prompt_zh": "请帮我写一份通知公告。\n\n请按以下结构输出：\n- 标题：【通知】+ 核心主题\n- 主送对象\n- 正文：发文缘由+具体事项+执行时间+注意事项\n- 落款：发文部门+日期"},
            {"id": "plan", "name_zh": "计划方案", "name_en": "Plan", "icon": "🎯",
             "prompt_zh": "请帮我写一份工作计划/方案。\n\n请按以下结构输出：\n1. 背景与目标\n2. 具体方案与步骤\n3. 时间排期与里程碑\n4. 人员分工\n5. 资源需求\n6. 风险评估与应对\n7. 成功衡量指标（KPIs）"},
            {"id": "summary", "name_zh": "工作总结", "name_en": "Summary", "icon": "📈",
             "prompt_zh": "请帮我写一份工作总结。\n\n请按以下结构输出：\n1. 工作概述\n2. 主要工作完成情况（数据驱动）\n3. 重点项目与成果\n4. 能力成长与收获\n5. 不足与改进方向\n6. 下一阶段规划"},
            {"id": "leave", "name_zh": "请假申请", "name_en": "Leave Request", "icon": "🏖️",
             "prompt_zh": "请帮我写一份请假申请。\n\n请按以下结构输出：\n- 标题：请假申请\n- 称呼\n- 正文：请假类型+时间（起止）+原因+工作交接+紧急联系方式\n- 申请人+日期"},
            {"id": "recruit", "name_zh": "招聘启事", "name_en": "Job Posting", "icon": "💼",
             "prompt_zh": "请帮我写一份招聘启事。\n\n请按以下结构输出：\n1. 公司简介\n2. 招聘岗位\n3. 岗位职责\n4. 任职要求（必备+加分）\n5. 福利待遇\n6. 工作地点/时间\n7. 应聘方式"},
        ],
    },
    "study": {
        "id": "study",
        "name_zh": "学习答疑",
        "name_en": "Study Q&A",
        "icon": "📚",
        "system_prompt_zh": "你是有料AI，一位耐心的学习辅导老师。擅长中小学知识答疑、作业讲解、知识点总结、论文降重、文案改写等。请用通俗易懂、循序渐进的中文回答，把复杂的概念讲清楚，适当举例说明。鼓励用户思考，培养学习方法，不要只给答案。",
        "system_prompt_en": "You are Youliao AI, a patient study tutor. Skilled in K-12 knowledge Q&A, homework explanation, knowledge summary, paper rewriting, text paraphrasing, etc. Answer in easy-to-understand, step-by-step Chinese, explain complex concepts clearly, use examples appropriately. Encourage users to think and develop learning methods, don't just give answers.",
        "quick_templates": [
            {"id": "explain", "name_zh": "知识点讲解", "name_en": "Explain Concept", "icon": "💡",
             "prompt_zh": "请帮我讲解一个知识点。\n\n请按以下结构输出：\n1. 概念定义（用最简单的话说明）\n2. 核心原理（为什么是这样）\n3. 举例说明（2-3 个生活/学习中的例子）\n4. 常见误区（容易搞错的地方）\n5. 延伸拓展（相关知识点/应用场景）"},
            {"id": "homework", "name_zh": "作业辅导", "name_en": "Homework Help", "icon": "📝",
             "prompt_zh": "请帮我解答一道题目。\n\n请按以下结构输出：\n1. 题目分析（这道题考什么知识点）\n2. 解题思路（从哪里入手，关键步骤）\n3. 详细解答（一步步写清楚）\n4. 方法总结（这类题的通用解法）\n5. 举一反三（1-2 道类似练习）"},
            {"id": "composition", "name_zh": "作文指导", "name_en": "Essay Writing", "icon": "✍️",
             "prompt_zh": "请帮我写一篇作文。\n\n请按以下结构输出：\n1. 审题立意（这篇作文要表达什么）\n2. 选材构思（用什么素材/故事/论据）\n3. 文章结构（开头/主体/结尾怎么安排）\n4. 精彩范文（完整的作文）\n5. 亮点分析（这篇作文好在哪里）"},
            {"id": "english", "name_zh": "英语翻译", "name_en": "English Translation", "icon": "🌍",
             "prompt_zh": "请帮我做英语翻译。\n\n请按以下结构输出：\n1. 原文\n2. 译文（地道、流畅的翻译）\n3. 重点词汇解析（3-5 个关键词的用法）\n4. 语法点讲解（涉及的语法知识）\n5. 举一反三（类似表达/例句）"},
            {"id": "summary", "name_zh": "课文总结", "name_en": "Text Summary", "icon": "📋",
             "prompt_zh": "请帮我总结一篇课文/文章。\n\n请按以下结构输出：\n1. 文章主旨（一句话概括）\n2. 段落大意（每段/每部分讲了什么）\n3. 核心观点（作者想传达的核心信息）\n4. 重点词句（值得积累的表达）\n5. 思考感悟（读完的启发）"},
            {"id": "formula", "name_zh": "公式推导", "name_en": "Formula Derivation", "icon": "📐",
             "prompt_zh": "请帮我推导一个数学/物理公式。\n\n请按以下结构输出：\n1. 公式内容（要推导什么公式）\n2. 前置知识（需要什么基础）\n3. 推导过程（一步一步严谨推导）\n4. 适用条件（什么时候可以用这个公式）\n5. 应用实例（1-2 道例题）"},
            {"id": "exam", "name_zh": "复习提纲", "name_en": "Review Outline", "icon": "🎯",
             "prompt_zh": "请帮我做一个复习提纲。\n\n请按以下结构输出：\n1. 知识框架（思维导图式的结构）\n2. 核心考点（考试常考的知识点）\n3. 重点公式/定理（需要背诵的内容）\n4. 典型例题（3-5 道经典题型）\n5. 易错点汇总（容易丢分的地方）"},
            {"id": "paper", "name_zh": "论文润色", "name_en": "Paper Polish", "icon": "🎓",
             "prompt_zh": "请帮我润色一篇论文/文章。\n\n请按以下结构输出：\n1. 原文问题诊断（逻辑/表达/格式问题）\n2. 润色后全文（更流畅、专业、规范）\n3. 修改说明（主要改了什么，为什么这么改）\n4. 降重建议（如何避免重复，提升原创性）\n5. 格式规范（参考文献/引用格式）"},
        ],
    },
    "life": {
        "id": "life",
        "name_zh": "生活解惑",
        "name_en": "Life Advice",
        "icon": "🌟",
        "system_prompt_zh": "你是有料AI，一位贴心的生活顾问。擅长情感疏导、人际关系、职场建议、旅游攻略、美食推荐、解梦、取名、穿搭建议等日常生活问题。请用温暖、共情、实用的中文回答，站在用户角度思考，给出真诚的建议和安慰，语气亲切如朋友。",
        "system_prompt_en": "You are Youliao AI, a caring life advisor. Skilled in emotional support, relationships, career advice, travel guides, food recommendations, dream interpretation, naming, fashion advice and other daily life questions. Answer in warm, empathetic, practical Chinese, think from the user's perspective, give sincere advice and comfort, tone friendly like a friend.",
        "quick_templates": [
            {"id": "travel", "name_zh": "旅游攻略", "name_en": "Travel Guide", "icon": "✈️",
             "prompt_zh": "请帮我做一份旅游攻略。\n\n请按以下结构输出：\n1. 目的地简介（一句话种草）\n2. 最佳出行时间（季节/天气/淡旺季）\n3. 行程规划（按天安排，含景点+路线+交通）\n4. 必打卡景点（Top 5，附亮点+门票+开放时间）\n5. 美食推荐（当地特色餐厅+小吃）\n6. 住宿建议（不同预算的推荐）\n7. 实用Tips（交通/APP/避坑/准备清单）"},
            {"id": "food", "name_zh": "美食推荐", "name_en": "Food Recommend", "icon": "🍜",
             "prompt_zh": "请帮我推荐美食。\n\n请按以下结构输出：\n1. 口味/菜系推荐（根据需求匹配）\n2. 菜品推荐（Top 5，每道菜附：口感/特色/搭配）\n3. 餐厅推荐（不同价位的选择，附：招牌/环境/人均）\n4. 在家复刻（1-2 道简单易做的菜谱）\n5. 搭配建议（饮品/配菜/甜点）"},
            {"id": "emotion", "name_zh": "情感疏导", "name_en": "Emotional Support", "icon": "💗",
             "prompt_zh": "请帮我做一次情感疏导。\n\n请按以下方式回应：\n1. 共情倾听（先表达理解和接纳，让对方感受到被看见）\n2. 情绪命名（帮助对方识别和描述自己的情绪）\n3. 正向视角（引导看到事情的多面性，不是只有负面）\n4. 实际建议（1-3 个可落地的小行动）\n5. 温暖收尾（给予鼓励和支持，让对方有力量）"},
            {"id": "health", "name_zh": "健康养生", "name_en": "Health Tips", "icon": "💪",
             "prompt_zh": "请给我一些健康养生建议。\n\n请按以下结构输出：\n1. 问题分析（当前状况可能的原因）\n2. 饮食建议（吃什么/少吃什么/食疗方）\n3. 作息建议（睡眠时间/作息规律/小习惯）\n4. 运动建议（适合的运动/频率/注意事项）\n5. 日常调理（穴位/放松技巧/心态调整）\n⚠️ 温馨提示：以上建议仅供参考，如有不适请及时就医。"},
            {"id": "fashion", "name_zh": "穿搭建议", "name_en": "Fashion Advice", "icon": "👗",
             "prompt_zh": "请给我一些穿搭建议。\n\n请按以下结构输出：\n1. 风格定位（根据场合/身材/气质推荐适合的风格）\n2. 基础款清单（衣橱必备的 5-8 件百搭单品）\n3. 配色方案（3-4 套适合的色彩搭配）\n4. 场合穿搭（日常/上班/约会/聚会各 1 套参考）\n5. 加分细节（配饰/鞋包/发型的搭配建议）"},
            {"id": "relation", "name_zh": "人际关系", "name_en": "Relationship", "icon": "🤝",
             "prompt_zh": "请帮我分析一段人际关系。\n\n请按以下结构输出：\n1. 现状分析（客观描述当前的关系状态）\n2. 问题本质（核心矛盾/卡点在哪里）\n3. 对方视角（站在对方角度可能是怎么想的）\n4. 沟通建议（具体可以说什么/怎么说，附话术参考）\n5. 行动方案（1-3 个可执行的小步骤）"},
            {"id": "dream", "name_zh": "周公解梦", "name_en": "Dream Analysis", "icon": "🌙",
             "prompt_zh": "请帮我分析一下这个梦。\n\n请按以下方式回应：\n1. 梦境概述（用温暖的语气开启分析）\n2. 象征解读（梦中关键元素/人物/场景的象征意义）\n3. 心理映射（这个梦可能反映了你现实中的什么情绪/想法/状态）\n4. 启示建议（这个梦想告诉你什么，或可以做些什么）\n5. 温馨提示（梦是潜意识的表达，仅供参考，不必过度解读）"},
            {"id": "name", "name_zh": "起名取名", "name_en": "Name Suggestion", "icon": "✨",
             "prompt_zh": "请帮我起个名字。\n\n请按以下结构输出：\n1. 起名思路（根据要求确定风格/寓意/调性）\n2. 推荐名字（5-8 个精选名字，每个附：字义解析+寓意来源+整体感觉）\n3. 分类推荐（如：文艺风/大气风/灵动风... 各 2-3 个）\n4. 注意事项（读音/谐音/重名率/书写难度等避坑提醒）\n5. 备选字库（推荐一些好字供自行搭配）"},
            {"id": "pet", "name_zh": "养宠指南", "name_en": "Pet Care", "icon": "🐱",
             "prompt_zh": "请给我一份养宠指南。\n\n请按以下结构输出：\n1. 前期准备（必备物品清单+环境布置）\n2. 饮食指南（推荐食物/喂养频率/禁忌食物）\n3. 日常护理（洗澡/梳毛/剪指甲/清洁等）\n4. 健康管理（疫苗/驱虫/常见疾病信号/应急处理）\n5. 训练建议（基础训练/行为纠正/增进感情的小方法）"},
            {"id": "gift", "name_zh": "礼物推荐", "name_en": "Gift Ideas", "icon": "🎁",
             "prompt_zh": "请帮我推荐礼物。\n\n请按以下结构输出：\n1. 需求分析（收礼人画像/场合/预算）\n2. 走心推荐（Top 5，每件附：推荐理由/价格参考/哪里买/送礼场景）\n3. 分价位推荐（¥50 内/¥50-200/¥200-500/¥500+）\n4. 加分技巧（包装/贺卡/仪式感/惊喜方式）\n5. 避坑提醒（这类人/场合千万别送什么）"},
        ],
    },
}

# ===================== tools =====================
TOOL_LIST = []

# ===================== 数据库 =====================
# 默认使用 SQLite，开箱即用、无需安装数据库服务。
# 如需 MySQL，可在 .env 中设置：
#   SQLALCHEMY_DATABASE_URL=mysql+pymysql://user:pass@host:3306/db
SQLALCHEMY_DATABASE_URL = os.getenv(
    "SQLALCHEMY_DATABASE_URL",
    "sqlite:///./app.db",
)
