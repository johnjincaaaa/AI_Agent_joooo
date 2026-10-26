# 开发指南

## 环境准备

- Python 3.10+
- （可选）Rust toolchain + Tauri CLI，用于桌面端构建

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

## 打包后端（PyInstaller）

```bash
pyinstaller backend.spec --noconfirm
# 产物：dist/backend.exe
```

`backend.spec` 会打包 `templates/`、`static/`、`AGENTS.md`、`.env.example` 以及 `app/` 包（自动追踪 import）。

## 桌面端构建（Tauri）

```bash
cd src-tauri
cargo tauri dev      # 开发（自动拉起后端）
cargo tauri build    # 打包（需先 pyinstaller 生成 backend.exe 到 binaries/）
```

完整发布流程见 `.github/workflows/release.yml`。

### 后端拉起脚本

`cargo tauri dev` 通过 `beforeDevCommand` 调用 `../start_backend.ps1` 拉起后端（检测端口 → 启动 → 轮询就绪）。

| 脚本 | 用途 |
|---|---|
| `start_backend.ps1` | **唯一实现**，`tauri.conf.json` 依赖它 |
| `start_backend.bat` | 等价 cmd 版本，供 PowerShell 执行策略受限时手动使用 |
| `start.py` / `start.bat` | 一键启动（建 venv + 装依赖 + 起服务 + 开浏览器），面向终端用户，非 dev 流程 |

改后端拉起逻辑时，只改 `start_backend.ps1` 即可（`.bat` 版本保持行为一致）。

## 服务端部署

见 [deploy/README.md](../deploy/README.md)。

## 架构约定

- 新增路由 → `app/api/`，在 `main.py` 注册。
- 新增业务逻辑 → `app/services/`。
- 新增本地工具 → `app/mcp/`，在 `manager.py` 的 `_register_default_tools` 注册。
- 新增云端工具 → `app/tools/`，在 `app/jinclaw/tool_registry.py` 的 `_register_cloud_tools` 注册。
- 新增数据库表 → `app/core/db/models.py`；迁移/seed → `app/core/db/seed.py`。
- 新增配置 → 见 [config.md](config.md)。
