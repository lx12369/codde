# Linux 轻量服务器部署说明

本文档基于当前仓库结构整理：

- 前端：`frontend/`，Vite 构建产物为 `frontend/dist/`
- 后端：`backend/`，Flask API 默认监听 `5000`
- 推荐部署方式：`Nginx + Gunicorn + Flask + SQLite`

适用场景：

- 单台 Ubuntu 轻量应用服务器
- 对外通过域名或公网 IP 访问
- 中小规模内部系统或低并发业务

## 1. 部署拓扑

- `Nginx` 对外监听 `80/443`
- `Nginx` 提供前端静态文件
- `Nginx` 将 `/api/*` 反向代理到 `127.0.0.1:5000`
- `Gunicorn` 运行 Flask 应用
- `SQLite` 数据文件保存在服务器磁盘

## 2. 前提条件

服务器建议：

- Ubuntu 22.04 或 24.04
- 已开放安全组端口：`80`、`443`
- 如需 HTTPS，已解析域名到服务器公网 IP

确认基础工具：

预期：能看到版本号。

```bash
python3 --version
node -v
npm -v
git --version
nginx -v
```

如果 `nginx` 未安装，可执行：

预期：安装完成后 `nginx -v` 可用。

```bash
sudo apt update
sudo apt install -y nginx python3-venv python3-pip
```

## 3. 拉取项目

建议目录：`/opt/codde`

预期：目录下包含 `frontend/` 和 `backend/`。

```bash
cd /opt
sudo git clone <你的仓库地址> codde
cd /opt/codde
ls
```

如果仓库是私有的，可先在服务器上配置 GitHub 凭据，或直接上传代码压缩包。

## 4. 配置后端

### 4.1 创建虚拟环境并安装依赖

项目仓库当前依赖文件是 [requirements.txt](C:\Users\PC\Desktop\codde\backend\requirements.txt)，生产环境还需要 `gunicorn`。

预期：安装完成，无报错。

```bash
cd /opt/codde/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### 4.2 创建生产环境变量

当前后端配置来自 [config.py](C:\Users\PC\Desktop\codde\backend\config.py)，关键变量包括：

- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `DATABASE_URL`
- `AMAP_WEATHER_KEY`（可选）

建议创建 `backend/.env`：

预期：文件创建成功，密钥不再使用默认值。

```bash
cat > /opt/codde/backend/.env << 'EOF'
SECRET_KEY=replace-with-a-random-secret
JWT_SECRET_KEY=replace-with-a-random-jwt-secret
DATABASE_URL=sqlite:////opt/codde/backend/instance/app.db
AMAP_WEATHER_KEY=
AMAP_WEATHER_LOCATION=宁波市鄞州区下应街道
AMAP_WEATHER_ADCODE=
AMAP_WEATHER_CITY_LABEL=宁波市鄞州区下应街道
EOF
```

说明：

- 不要在生产环境使用默认的 `dev-secret-key-change-in-production`
- `DATABASE_URL` 建议使用绝对路径，避免工作目录变化导致数据库写到错误位置
- 如果不需要天气功能，可以先留空 `AMAP_WEATHER_KEY`

### 4.3 创建数据库目录

仓库当前已有本地数据库文件位于 `backend/instance/`，生产环境也建议继续使用该目录。

预期：目录存在且运行用户可写。

```bash
mkdir -p /opt/codde/backend/instance
sudo chown -R www-data:www-data /opt/codde/backend
```

## 5. 构建前端

前端当前通过 [vite.config.js](C:\Users\PC\Desktop\codde\frontend\vite.config.js) 将 `/api` 代理到本地 `5000`，生产环境保持这个路径即可，不需要改前端接口地址。

预期：生成 `frontend/dist/`。

```bash
cd /opt/codde/frontend
npm install
npm run build
ls /opt/codde/frontend/dist
```

## 6. 启动 Flask 服务

当前后端入口在 [app.py](C:\Users\PC\Desktop\codde\backend\app.py)，生产环境应通过 Gunicorn 调用：

```python
app:create_app('production')
```

### 6.1 创建 systemd 服务

预期：服务文件写入成功。

```bash
sudo tee /etc/systemd/system/codde-backend.service > /dev/null << 'EOF'
[Unit]
Description=Codde Flask Backend
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/codde/backend
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/codde/backend/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app('production')"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
```

### 6.2 启动服务

预期：状态为 `active (running)`。

```bash
sudo systemctl daemon-reload
sudo systemctl enable codde-backend
sudo systemctl start codde-backend
sudo systemctl status codde-backend
```

如启动失败，查看日志：

预期：能看到 Python 异常或启动信息。

```bash
sudo journalctl -u codde-backend -n 100 --no-pager
```

## 7. 配置 Nginx

### 7.1 写入站点配置

预期：配置文件创建成功。

```bash
sudo tee /etc/nginx/sites-available/codde > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    root /opt/codde/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:5000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
EOF
```

### 7.2 启用配置

预期：`nginx -t` 显示 successful。

```bash
sudo ln -sf /etc/nginx/sites-available/codde /etc/nginx/sites-enabled/codde
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl status nginx
```

## 8. 配置 HTTPS

如果你有域名，建议加 HTTPS。

安装 Certbot：

预期：安装成功。

```bash
sudo apt install -y certbot python3-certbot-nginx
```

申请证书：

预期：Nginx 自动写入 HTTPS 配置，浏览器可通过 `https://你的域名` 访问。

```bash
sudo certbot --nginx -d 你的域名
```

检查续期：

预期：看到定时续期测试通过。

```bash
sudo certbot renew --dry-run
```

## 9. 验证步骤

### 9.1 本机验证后端

预期：返回 `404`、`401` 或 JSON 都算后端已响应，不应连接失败。

```bash
curl http://127.0.0.1:5000/api/
curl http://127.0.0.1:5000/api/auth/login
```

### 9.2 本机验证 Nginx

预期：返回前端 HTML。

```bash
curl http://127.0.0.1
```

### 9.3 外网验证

预期：

- 打开 `http://服务器IP` 或 `https://你的域名`
- 能看到登录页
- 浏览器开发者工具中 `/api/*` 请求返回正常

## 10. 常见问题

### 10.1 页面能打开，但接口 502

原因通常是：

- Gunicorn 没启动
- Gunicorn 启动失败
- Nginx 反代地址不对

排查命令：

```bash
sudo systemctl status codde-backend
sudo journalctl -u codde-backend -n 100 --no-pager
sudo nginx -t
```

### 10.2 登录后接口报 500

优先检查：

- `.env` 是否存在
- `SECRET_KEY` 和 `JWT_SECRET_KEY` 是否设置
- SQLite 文件目录是否可写

### 10.3 静态页面正常，刷新子路由 404

说明 `try_files $uri $uri/ /index.html;` 未生效，重新检查 Nginx 站点配置。

## 11. 数据与备份建议

当前默认数据库是 SQLite，至少要备份以下内容：

- `/opt/codde/backend/instance/app.db`
- `/opt/codde/backend/.env`

可以先做最简单的每日备份：

预期：生成带日期的数据库备份文件。

```bash
mkdir -p /opt/backups/codde
cp /opt/codde/backend/instance/app.db /opt/backups/codde/app-$(date +%F).db
```

## 12. 更新部署流程

后续代码更新可按以下顺序：

预期：代码更新、前端重建、后端重启完成。

```bash
cd /opt/codde
git pull

cd /opt/codde/frontend
npm install
npm run build

cd /opt/codde/backend
source .venv/bin/activate
pip install -r requirements.txt

sudo systemctl restart codde-backend
sudo systemctl reload nginx
```

如果后续要做更稳定的生产部署，建议下一步改造为：

- PostgreSQL 替代 SQLite
- CI 自动构建前端
- Docker Compose 一键部署
