# 架构说明

## 总览

Jingent AI 是单体 FastAPI 应用，采用「薄入口 + 分层包」结构。桌面端通过 Tauri 2 把后端打包成 sidecar 运行。

```
请求 → main.py（装配）→ 路由层 app/api/ → 业务层 app/services/ → 数据层 app/core/db/
                                                      ↓
                                             Jinclaw Agent（app/jinclaw/）
                                                      ↓
                                             MCP 工具（app/mcp/ + app/tools/）
```

## 分层职责

| 层 | 位置 | 职责 | 依赖方向 |
|---|---|---|---|
| 入口装配 | `main.py` | 初始化日志/配置/app，注册路由与中间件 | 引用所有层 |
| 路由层 | `app/api/*_routes.py` | HTTP 端点、参数校验、鉴权、响应 | → services / jinclaw / core |
| 业务层 | `app/services/` | 推广拉新、求职 mock 等纯业务逻辑 | → core/db |
| Agent 层 | `app/jinclaw/` | Agent loop、工具注册表、会话存储、系统提示词 | → mcp / tools / core |
| MCP 层 | `app/mcp/` | 本地工具：文件、Shell、Git、浏览器、数据库 | → core |
| 云端工具 | `app/tools/` | 联网、代码沙箱、图片/文档解析、技能管理 | → core |
| 基础设施 | `app/core/` | 路径、日志、中间件、安全、数据库 | 无（最底层） |
| 配置 | `app/config/` | env 加载、场景预设、常量 | → core/paths |

## 关键设计

### 配置分层（`app/config/`）

- **`settings.py`** — 运行时环境配置（从 `.env` 读），含 `validate_config()` 启动校验。
- **`scenes.py`** — 场景预设业务数据（`SCENE_PRESETS`），与运行配置解耦。
- **`constants.py`** — 不随部署变化的应用常量（上传白名单、`TOOL_LIST`）。
- `__init__.py` 聚合导出，保持 `from app.config import X` 的调用方式不变。

### 数据库分层（`app/core/db/`）

原 `sqlOrm.py` 拆分：

- **`models.py`** — engine/SessionLocal/Base + 全部 ORM 模型 + `get_db`。
- **`seed.py`** — `PROMO_CONFIG_DEFAULTS`、补列迁移、配置 seed、`init_db()`。

### 用户数据隔离

Jinclaw 的 projects/tasks/diffs 三张表带 `user_id` 列，存储层（`app/jinclaw/storage.py`）通过 `_uid_cond` 对每个查询注入归属过滤。匿名用户 `user_id=None` 走 legacy 数据。

### Agent 工具链

`app/jinclaw/tool_registry.py` 聚合两类工具：

1. **本地 MCP**（`app/mcp/`，`desktop_only=True`）：`mcp_shell_exec`、`mcp_file_read/write/edit`、`mcp_git_*`、`mcp_browser_*`、`mcp_db_*`。
2. **云端工具**（`app/tools/`）：`web_search`、`code_exec`、`image_parsing`、`document_parsing`、`http_request`。

`AgentLoop`（`agent_loop.py`）对代码类任务执行「探索 → 规划 → 执行 → 验证」四步流程，工具调用上限 30 轮。

## 数据流示例

### 聊天流（`POST /ai/chatStream`）

```
前端 → chat_routes.chat_stream
     → ensure_chat_access（匿名限流）
     → build_system_prompt + resolve_enabled_skills
     → create_agent（langchain）
     → agent.astream → SSE 流式返回
```

### 代码任务流（`POST /ai/jinclaw/chat`）

```
前端 → jinclaw_routes.jinclaw_chat_stream
     → 解析 workspace（task → project → workspace_path）
     → AgentLoop.stream
     → run_agent_loop：探索 → 计划 → 工具调用 → 验证
     → SSE 返回事件（thinking/plan/tool_call/tool_result/message_chunk/done）
```

## 安全模型

- **JWT**：HS256，用户 token 与 admin token 共用 `SECRET_KEY`，admin 带 `role=admin` 声明。
- **匿名限流**：`app/core/rate_limit.py`，每 IP 每日 `ANONYMOUS_RATE_LIMIT_MAX` 次。
- **CORS**：dev 全开，prod 读 `CORS_ORIGINS`。
- **密码**：bcrypt 哈希（`app/core/password_utils.py`）。

> 注意：`/ai/jinclaw/*` 的 workspace 文件操作和 shell 执行端点设计上服务桌面端场景，部署到公网前需确认鉴权与路径沙箱策略（见部署文档）。
