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

pip install -r requirements.txt
pip install -e ".[dev]"   # 安装 pytest/ruff（或手动 pip install pytest ruff httpx）

cp .env.example .env      # 填入 LLM_API_KEY
python main.py            # 或 python start.py 一键启动
```

## 运行测试

```bash
pytest tests/             # 全量
pytest tests/test_storage.py -v   # 单文件
pytest -m unit            # 只跑单元测试
```

测试通过 `tests/conftest.py` 强制注入测试 `SECRET_KEY`，避免触碰真实 `.env`。

## 代码质量

```bash
ruff check .              # 静态检查
```

当前 ruff 只启用关键检查（E9/F63/F7/F82），`E501`/`B008`/`F401` 已放行，待存量代码收敛后收紧。

## 服务端部署

见 [deploy/README.md](../deploy/README.md)。

## 架构约定

- 新增路由 → `app/api/`，在 `main.py` 注册。
- 新增业务逻辑 → `app/services/`。
- 新增聊天技能 → `app/tools/skills_registry.py` 的 `SKILL_CATALOG`/`SKILL_TOOLS` 注册。
- 新增数据库表 → `app/core/db/models.py`；迁移/seed → `app/core/db/seed.py`。
- 新增配置 → 见 [config.md](config.md)。
