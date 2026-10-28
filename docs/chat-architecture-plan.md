# 对话体系改造实施计划

> 目标：主对话 vs 新建会话分层，消息原子化，Telegram 式交互，RAG 语义检索，主动发消息。
> 决策：迁移旧数据 / 真向量库（chromadb + Ollama bge-m3）/ 首页=主对话 / 主动发消息。

## 分层总览（三层贯穿）

| 层 | 主对话（main） | 新建会话（secondary） |
|---|---|---|
| 数据 | 消息入向量库；detail 记忆累积 | 不入向量库；只读 global 记忆 |
| 逻辑 | 短回复+表情包+调侃+主动发消息 | 标准助手式 |
| UI | 首页主界面 + 桌宠联动 | 点「新建对话」创建 |

## 分期

### P1 消息原子化 + 数据迁移
- 新增 `Message` 表（id/session_id/user_id/role/content/created_at/reactions/reply_to_id）
- `ChatSession` 加 `chat_type` 字段（main/secondary）
- 迁移：现有 `chat_sessions.messages` JSON 拆成 Message 行
- 后端 savaToDb/history 改读写 Message 表

### P2 主/次对话分层
- 主对话：每个用户唯一（chat_type=main）
- prompt 分化：主对话去人机感（短回复/表情包/调侃/主动），次会话标准助手
- 记忆策略：主对话注入 detail，次会话只读 global

### P3 Telegram 式交互
- 消息右键菜单（回复/复制/引用/反应/删除）
- 时间戳 hover 显示
- 搜索（SQLite LIKE）

### P4 RAG 向量库
- chromadb + Ollama bge-m3 embedding
- 主对话消息入向量库，语义检索历史对话
- 检索结果注入主对话 prompt

### P5 主动发消息
- 主对话 AI 定时主动开启话题
- 后端定时任务 + 桌宠气泡 + 主界面消息展示

## 状态

- [x] P1
- [x] P2
- [x] P3
- [x] P4
- [x] P5
