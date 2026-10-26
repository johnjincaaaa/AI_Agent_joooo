# Jingent AI

AI 聊天 + 代码写作助手（FastAPI 后端 + LangChain 聊天 Agent）。

## 项目简介

- **聊天**：多场景 AI 对话（日常/办公/学习/生活），支持图片/文档附件、技能包、联网搜索。
- **聊天技能**：图片/文档解析工具 + 20 个提示词技能（翻译/文案/编程/生活等），支持自定义技能包。
- **推广拉新**：邀请制奖励、签到、提现、后台管理。
- **求职**：简历生成、岗位匹配、模拟面试。

## 目录结构

```
根/
├── main.py               # FastAPI 入口（薄装配层，唯一入口）
├── app/                  # 应用代码（核心）
│   ├── config/           # 配置：settings(env) + scenes(业务) + constants(常量)
│   ├── core/             # 基础设施：paths/logging/middleware/security/db
│   ├── api/              # 路由层
│   ├── services/         # 业务逻辑（推广/求职 mock）
│   └── tools/            # 云端工具（联网/图片/文档/技能管理）
├── static/               # 前端静态资源
├── templates/            # Jinja2 模板
├── tests/                # pytest 测试
├── deploy/               # systemd 服务 + 部署文档
├── docs/                 # 架构与配置文档
└── start.py / start.bat  # 一键启动（开发）
```

## 快速开始

### 本地开发

```bash
# 1. 准备环境
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate        # Linux/macOS

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 .env（首次会自动从 .env.example 生成，也可手动复制）
cp .env.example .env   # 填入 LLM_API_KEY 等

# 4. 启动
python start.py        # 或 python main.py
# 访问 http://127.0.0.1:8000/chat
```

### 测试

```bash
pytest tests/
```

## 文档

- [架构说明](docs/architecture.md)
- [配置说明](docs/config.md)
- [开发指南](docs/development.md)

## 配置

所有运行时配置项见 [docs/config.md](docs/config.md)。核心配置通过 `.env` 加载。
