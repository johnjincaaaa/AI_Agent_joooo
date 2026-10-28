# 架构说明

## 总览

Jingent AI 是单体 FastAPI 应用，采用「薄入口 + 分层包」结构。

物理布局：后端代码在 `backend/`，前端资源在 `front/`，运维运行时数据在 `ops/`。

```
请求 → backend/main.py（装配）→ backend/app/api/ → backend/app/services/ → backend/app/core/db/
                                                          ↓
                                                 聊天 Agent（LangChain + backend/app/tools/ 技能）
```

## 分层职责

| 层 | 位置 | 职责 | 依赖方向 |
|---|---|---|---|
| 入口装配 | `backend/main.py` | 初始化日志/配置/app，注册路由与中间件 | 引用所有层 |
| 路由层 | `backend/app/api/*_routes.py` | HTTP 端点、参数校验、鉴权、响应 | → services / core |
| 业务层 | `backend/app/services/` | 推广拉新、求职 mock 等纯业务逻辑 | → core/db |
| 技能层 | `backend/app/tools/` | 聊天技能注册表、图片/文档解析、联网搜索、技能包管理 | → core |
| 基础设施 | `backend/app/core/` | 路径、日志、中间件、安全、数据库 | 无（最底层） |
| 配置 | `backend/app/config/` | env 加载、场景预设、常量 | → core/paths |

## 目录结构

```
根/
├── backend/               # 后端代码（main.py + app/ + tests/ + .env 等）
├── front/                 # 前端资源（static/ + templates/）
├── ops/                   # 运维运行时数据（logs/temp/uploads/data，不进 git）
├── deploy/                # systemd 服务 + 部署文档
├── docs/                  # 架构与配置文档
├── start.py / start.bat   # 一键启动（根目录入口）
└── README.md / AGENTS.md
```

路径统一由 `backend/app/core/paths.py` 锚定推导（不依赖 cwd），详见该模块注释。

## 关键设计

### 配置分层（`backend/app/config/`）

- **`settings.py`** — 运行时环境配置（从 `backend/.env` 读），含 `validate_config()` 启动校验。
- **`scenes.py`** — 场景预设业务数据（`SCENE_PRESETS`），与运行配置解耦。
- **`constants.py`** — 不随部署变化的应用常量（上传白名单、`TOOL_LIST`）。
- `__init__.py` 聚合导出，保持 `from app.config import X` 的调用方式不变。

### 数据库分层（`backend/app/core/db/`）

原 `sqlOrm.py` 拆分：

- **`models.py`** — engine/SessionLocal/Base + 全部 ORM 模型 + `get_db`。
- **`seed.py`** — `PROMO_CONFIG_DEFAULTS`、补列迁移、配置 seed、`init_db()`。

### 用户数据隔离

`ChatSession` 等业务表带 `user_id` 列；匿名用户 `user_id=None` 走限流与临时会话。

### 聊天技能链

`/ai/chatStream` 通过 `backend/app/tools/skills_registry.py` 聚合技能：工具类（`image_parsing`、`document_parsing`）+ 20 个提示词类技能；联网搜索走 `tool_intelligent_networking.py` 的 `online`/`online_intensive`。自定义技能包由 `skill_package_manager.py` 管理。

## 数据流示例

### 聊天流（`POST /ai/chatStream`）

```
前端 → chat_routes.chat_stream
     → ensure_chat_access（匿名限流）
     → build_system_prompt + resolve_enabled_skills
     → create_agent（langchain）
     → agent.astream → SSE 流式返回
```

### 代码任务流

代码类任务建议通过终端使用 Claude Code 等外部 CLI 工具完成（自研 Jinclaw Agent 已移除）。

## 安全模型

- **JWT**：HS256，用户 token 与 admin token 共用 `SECRET_KEY`，admin 带 `role=admin` 声明。
- **匿名限流**：`app/core/rate_limit.py`，每 IP 每日 `ANONYMOUS_RATE_LIMIT_MAX` 次。
- **CORS**：dev 全开，prod 读 `CORS_ORIGINS`。
- **密码**：bcrypt 哈希（`app/core/password_utils.py`）。
