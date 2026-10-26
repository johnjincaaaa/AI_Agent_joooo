# 配置说明

## 配置文件位置

| 配置类型 | 位置 | 说明 |
|---|---|---|
| 运行时环境 | `.env`（开发）/ `/etc/jingent/jingent.env`（生产） | 因部署而异，不进 git |
| 环境模板 | `.env.example`（根） | 首次运行自动复制并注入随机 `SECRET_KEY` |
| 应用常量 | `app/config/constants.py` | 不随部署变化的固定值 |
| 场景预设 | `app/config/scenes.py` | 业务数据，非配置 |
| 部署 | `deploy/jingent.service` | systemd 单元 |
| 测试/质量 | `pyproject.toml` | pytest + ruff 统一配置 |

## 环境变量清单

所有环境变量通过 `app/config/settings.py` 读取。字段名、默认值、说明如下：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SECRET_KEY` | （空，必填） | JWT 签名密钥。服务端必须显式设置强随机串 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | 用户 token 有效期（分钟） |
| `LLM_MODEL` / `MODEL` | `deepseek-chat` | 大模型名 |
| `LLM_BASE_URL` / `DASHSCOPE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容 API 地址 |
| `LLM_API_KEY` / `DASHSCOPE_API_KEY` | （空） | API Key |
| `ANONYMOUS_RATE_LIMIT_MAX` | `10` | 匿名用户每 IP 每日免费次数 |
| `ADMIN_USERNAME` | `admin` | 后台账号 |
| `ADMIN_PASSWORD` | （空） | 后台密码，空则后台登录一律拒绝 |
| `SQLALCHEMY_DATABASE_URL` | `sqlite:///{data_dir}/app.db` | 数据库连接串 |
| `RUNTIME_ENV` | `dev` | `dev`/`prod`，影响 CORS 策略 |
| `CORS_ORIGINS` | `http://localhost:*` | 生产环境 CORS 白名单（逗号分隔） |

## 启动校验

`validate_config(strict=True)` 在 `main.py` 启动时执行：

- **FATAL**（strict 下直接拒绝启动）：`SECRET_KEY` 缺失、`LLM_BASE_URL`/`LLM_MODEL` 为空、数值配置非法。
- **WARN**（仅提示）：`LLM_API_KEY` 缺失、`ADMIN_PASSWORD` 为空。

开发模式（`RUNTIME_ENV=dev`）自动降级为 `strict=False`；生产（`prod`）严格校验。

## 修改配置

1. **本地开发**：编辑 `.env`，重启服务生效。
2. **生产**：编辑 `/etc/jingent/jingent.env`，`sudo systemctl restart jingent`。

## 新增配置项

1. 在 `app/config/settings.py` 加 `XXX = os.getenv("XXX", "默认值")`。
2. 在 `.env.example` 补充说明（含注释）。
3. 如需启动校验，在 `validate_config()` 添加对应 Warning。
4. 在本文档更新清单。
