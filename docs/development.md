# 开发指南

## 环境准备

- Python 3.10+

## 本地开发

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r backend/requirements.txt
pip install -e "backend/.[dev]"   # 安装 pytest/ruff（或手动 pip install pytest ruff httpx）

cp backend/.env.example backend/.env   # 填入 LLM_API_KEY
python start.py                # 一键启动（根目录入口，自动进入 backend/）
# 或手动：cd backend && python main.py
```

## 运行测试

```bash
cd backend
pytest tests/              # 全量
pytest tests/test_token_utils.py -v   # 单文件
pytest -m unit             # 只跑单元测试
```

测试通过 `backend/tests/conftest.py` 强制注入测试 `SECRET_KEY`，避免触碰真实 `.env`。

## 代码质量

```bash
cd backend
ruff check .               # 静态检查
```

当前 ruff 只启用关键检查（E9/F63/F7/F82），`E501`/`B008`/`F401` 已放行，待存量代码收敛后收紧。

## 服务端部署

见 [deploy/README.md](../deploy/README.md)。

## 架构约定

- 新增路由 → `backend/app/api/`，在 `backend/main.py` 注册。
- 新增业务逻辑 → `backend/app/services/`。
- 新增聊天技能 → `backend/app/tools/skills_registry.py` 的 `SKILL_CATALOG`/`SKILL_TOOLS` 注册。
- 新增数据库表 → `backend/app/core/db/models.py`；迁移/seed → `backend/app/core/db/seed.py`。
- 新增配置 → 见 [config.md](config.md)。
- 路径推导统一走 `backend/app/core/paths.py`，不要在业务代码里硬编码相对路径。
