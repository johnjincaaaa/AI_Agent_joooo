# Jingent AI

AI 聊天 + 代码写作助手（FastAPI 后端 + LangChain 聊天 Agent）。

## 项目简介

- **聊天**：多场景 AI 对话（日常/办公/学习/生活），支持图片/文档附件、技能包、联网搜索。
- **聊天技能**：图片/文档解析工具 + 20 个提示词技能（翻译/文案/编程/生活等），支持自定义技能包。
- **个人陪伴**：全局记忆 + 细节记忆（对话后 LLM 自动抽取用户画像）。
- **推广拉新**：邀请制奖励、签到、提现、后台管理。
- **求职**：简历生成、岗位匹配、模拟面试。

## 目录结构

```
根/
├── backend/               # 后端代码
│   ├── main.py            # FastAPI 入口（薄装配层）
│   ├── app/               # 应用代码
│   │   ├── config/        # settings(env) + scenes(业务) + constants(常量)
│   │   ├── core/          # paths/logging/middleware/security/db
│   │   ├── api/           # 路由层
│   │   ├── services/      # 业务逻辑（推广/求职）
│   │   └── tools/         # 聊天技能（图片/文档解析/联网/技能包管理）
│   ├── tests/             # pytest 测试
│   ├── .env / .env.example
│   └── requirements.txt / pyproject.toml
├── front/                 # 前端资源
│   ├── static/            # 静态资源（js/css/img）
│   └── templates/         # Jinja2 模板
├── ops/                   # 运维运行时数据（不进 git）
│   ├── logs/              # 日志
│   ├── temp/              # 临时文件
│   ├── uploads/           # 前端上传的第三方资源
│   └── data/              # 三方资源（技能包等）
├── deploy/                # systemd 服务 + 部署文档
├── docs/                  # 架构与配置文档
├── start.py / start.bat   # 一键启动（入口在根目录）
├── README.md
└── AGENTS.md
```

## 快速开始

### 本地开发

```bash
# 1. 准备环境
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate        # Linux/macOS

# 2. 安装依赖
pip install -r backend/requirements.txt

# 3. 配置 .env（首次会自动从 .env.example 生成，也可手动复制）
cp backend/.env.example backend/.env   # 填入 LLM_API_KEY 等

# 4. 启动
python start.py        # 一键启动（自动进入 backend/）
# 或手动：cd backend && python main.py
# 访问 http://127.0.0.1:8000/chat
```

### 测试

```bash
cd backend
pytest tests/
```

## 文档

- [架构说明](docs/architecture.md)
- [配置说明](docs/config.md)
- [开发指南](docs/development.md)

## 配置

所有运行时配置项见 [docs/config.md](docs/config.md)。核心配置通过 `backend/.env` 加载。
