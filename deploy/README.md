# 服务端部署

一次性初始化，之后每次发版由 CI（`.github/workflows/release.yml` 的 `server` job）自动完成。

## 首次安装

```bash
# 1. 专用用户 + 目录
sudo useradd -r -s /bin/false jingent
sudo mkdir -p /opt/jingent /var/lib/jingent /var/log/jingent /etc/jingent
sudo chown -R jingent:jingent /var/lib/jingent /var/log/jingent

# 2. 拉代码 + 装依赖
sudo git clone https://github.com/johnjincaaaa/AI_Agent_joooo.git /opt/jingent
cd /opt/jingent
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements.txt
sudo chown -R jingent:jingent /opt/jingent

# 3. 生产配置（不进 git，权限收紧到只有 root 可读）
sudo tee /etc/jingent/jingent.env >/dev/null <<EOF
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))")
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_API_KEY=<填你的 key>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<填强密码>
RUNTIME_ENV=prod
CORS_ORIGINS=https://your-domain
SQLALCHEMY_DATABASE_URL=sqlite:////var/lib/jingent/app.db
EOF
sudo chmod 600 /etc/jingent/jingent.env

# 4. 注册服务
sudo cp deploy/jingent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jingent
curl -fsS http://127.0.0.1:8000/health   # 期望 {"status":"ok"}
```

`SECRET_KEY` 这里是自动生成的 —— 不要用 `.env.example` 里的占位符，那样所有部署共用同一密钥，JWT 可被伪造。

## 启用 CI 自动部署

1. 仓库 Settings → Secrets 添加 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_SSH_KEY`
2. 给部署用户免密重启服务的权限：
   ```bash
   echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart jingent" | sudo tee /etc/sudoers.d/jingent
   ```
3. 删掉 `release.yml` 里 `server` job 的 `if: false`

## 反向代理

后端只监听 `127.0.0.1:8000`，对外由 nginx + HTTPS 暴露。`/admin` 建议再加一层 IP 白名单或 basic auth。

## 排查

```bash
sudo systemctl status jingent
sudo journalctl -u jingent -n 50 --no-pager
tail -50 /var/log/jingent/error.log
```
