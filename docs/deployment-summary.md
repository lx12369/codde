# 线上部署总结

本文档记录 2026-03-06 已成功跑通的服务器部署方案，面向当前仓库实际结构，不是通用模板。

适用对象：

- 单台阿里云轻量应用服务器
- Linux 系统，已安装宝塔面板
- Web 服务使用 `Tengine`
- 后端运行在 `Gunicorn + Flask`
- 前端使用 `Vue + Vite`
- 数据库存储为服务器本地 `SQLite`

## 1. 当前线上结构

- 服务器公网地址：`http://47.112.117.203/`
- 项目目录：`/www/wwwroot/codde`
- 前端源码目录：`/www/wwwroot/codde/frontend`
- 前端构建目录：`/www/wwwroot/codde/frontend/dist`
- 后端源码目录：`/www/wwwroot/codde/backend`
- 后端虚拟环境：`/www/wwwroot/codde/backend/.venv`
- 数据目录：`/www/wwwroot/codde/backend/instance`
- SQLite 数据库：`/www/wwwroot/codde/backend/instance/app.db`
- 后端环境变量：`/www/wwwroot/codde/backend/.env`
- Gunicorn 监听地址：`127.0.0.1:5000`

## 2. 首次部署步骤

### 2.1 服务器准备

放行以下端口：

- `22`
- `80`
- `443`
- `8888`

安装并确认基础工具：

```bash
python3.11 --version
node -v
npm -v
git --version
tengine -v
```

### 2.2 上传代码

将项目上传到：

```bash
/www/wwwroot/codde
```

要求目录下至少包含：

- `frontend/`
- `backend/`

### 2.3 配置后端环境变量

在服务器创建：

```bash
/www/wwwroot/codde/backend/.env
```

示例：

```bash
cat > /www/wwwroot/codde/backend/.env << 'EOF'
SECRET_KEY=replace-with-a-random-secret
JWT_SECRET_KEY=replace-with-a-random-jwt-secret
DATABASE_URL=sqlite:////www/wwwroot/codde/backend/instance/app.db
AMAP_WEATHER_KEY=
AMAP_WEATHER_LOCATION=宁波市鄞州区下应街道
AMAP_WEATHER_ADCODE=
AMAP_WEATHER_CITY_LABEL=宁波市鄞州区下应街道
EOF
```

说明：

- 不要使用默认开发密钥
- `DATABASE_URL` 必须使用绝对路径
- `.env` 需要长期保留，更新代码时不能覆盖

### 2.4 配置数据目录

```bash
mkdir -p /www/wwwroot/codde/backend/instance
```

### 2.5 构建前端

```bash
cd /www/wwwroot/codde/frontend
npm install
chmod +x /www/wwwroot/codde/frontend/node_modules/.bin/vite
npm run build
```

预期结果：

- 成功生成 `/www/wwwroot/codde/frontend/dist`

### 2.6 创建后端虚拟环境

必须使用 `python3.11`，不要使用系统默认 `python3.6`。

```bash
cd /www/wwwroot/codde/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

当前仓库生产依赖需要包含：

- `Flask-SQLAlchemy>=3.1.1`
- `gunicorn>=21.2.0`

### 2.7 启动后端

```bash
cd /www/wwwroot/codde/backend
source .venv/bin/activate
nohup /www/wwwroot/codde/backend/.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app('production')" >/tmp/codde-backend.log 2>&1 &
sleep 3
```

验证：

```bash
curl -I http://127.0.0.1:5000/
tail -n 30 /tmp/codde-backend.log
```

预期结果：

- `curl` 返回 HTTP 响应，通常是 `404`
- 日志中没有 Python 启动异常

### 2.8 配置 Tengine

当前实际方案是：

- `Tengine` 对外监听 `80`
- 站点根目录指向 `/www/wwwroot/codde/frontend/dist`
- `/api/` 反向代理到 `127.0.0.1:5000`

核心配置逻辑：

```nginx
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
```

### 2.9 验证站点

```bash
curl -I http://127.0.0.1/
curl -I http://127.0.0.1:5000/
```

浏览器验证：

- 打开 `http://47.112.117.203/`
- 能正常显示前端页面
- 页面里的 `/api` 请求可正常返回

## 3. 更新部署步骤

当前服务器不能稳定直连 GitHub，因此更新采用“本地打包 zip -> 上传服务器 -> 服务器解压部署”的方式。

### 3.1 本机打包

在本机项目根目录执行：

```powershell
cd C:\Users\PC\Desktop\codde
if (Test-Path C:\Users\PC\Desktop\codde.zip) { Remove-Item C:\Users\PC\Desktop\codde.zip -Force }
Compress-Archive -Path C:\Users\PC\Desktop\codde -DestinationPath C:\Users\PC\Desktop\codde.zip
```

### 3.2 上传 zip 到服务器

建议上传到：

```bash
/home/admin/codde.zip
```

然后在服务器执行：

```bash
sudo mv /home/admin/codde.zip /www/wwwroot/codde.zip
```

### 3.3 关键原则

更新代码时，必须保留以下服务器本地数据：

- `/www/wwwroot/codde/backend/instance`
- `/www/wwwroot/codde/backend/.env`

不能直接删掉整个项目目录后无保护覆盖，否则会丢失线上数据库和配置。

## 4. 更新脚本

仓库内已提供两个脚本：

- [server-update.sh](C:\Users\PC\Desktop\codde\scripts\server-update.sh)
- [deploy-codde-zip.sh](C:\Users\PC\Desktop\codde\scripts\deploy-codde-zip.sh)

### 4.1 `server-update.sh`

作用：

- 修正项目目录权限
- 前端重新安装依赖并构建
- 后端用 `python3.11` 重建 `.venv`
- 安装后端依赖
- 强制终止旧 Gunicorn
- 启动新 Gunicorn
- 验证前后端服务

执行方式：

```bash
cd /www/wwwroot/codde
sudo chmod +x scripts/server-update.sh
./scripts/server-update.sh
```

### 4.2 `deploy-codde-zip.sh`

作用：

- 解压 `/www/wwwroot/codde.zip`
- 备份当前线上项目到 `/www/backup/codde/`
- 保留 `backend/instance`
- 保留 `backend/.env`
- 替换项目代码
- 调用 `server-update.sh`
- 清理临时目录和 zip 包

执行方式：

```bash
cd /www/wwwroot/codde
sudo chmod +x scripts/deploy-codde-zip.sh
./scripts/deploy-codde-zip.sh
```

说明：

- 如果服务器当前代码里还没有这两个脚本，第一次需要先从新上传的 zip 中解压并复制到线上项目目录

## 5. 标准更新流程

以后每次上线按这个顺序执行。

### 5.1 本机

```powershell
cd C:\Users\PC\Desktop\codde
if (Test-Path C:\Users\PC\Desktop\codde.zip) { Remove-Item C:\Users\PC\Desktop\codde.zip -Force }
Compress-Archive -Path C:\Users\PC\Desktop\codde -DestinationPath C:\Users\PC\Desktop\codde.zip
```

将 `codde.zip` 上传到服务器：

```bash
/home/admin/codde.zip
```

### 5.2 服务器

```bash
sudo mv /home/admin/codde.zip /www/wwwroot/codde.zip
cd /www/wwwroot/codde
sudo chmod +x scripts/deploy-codde-zip.sh
./scripts/deploy-codde-zip.sh
```

### 5.3 验证

```bash
curl -I http://127.0.0.1/
curl -I http://127.0.0.1:5000/
```

浏览器验证：

- 打开 `http://47.112.117.203/`
- 检查更新后的功能页面

## 6. 常见问题

### 6.1 `vite: Permission denied`

原因：

- `node_modules/.bin/vite` 没有执行权限

处理：

```bash
chmod +x /www/wwwroot/codde/frontend/node_modules/.bin/vite
```

### 6.2 `.venv/bin/activate: No such file or directory`

原因：

- 新代码覆盖后，旧虚拟环境已经不存在

处理：

```bash
cd /www/wwwroot/codde/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 6.3 Gunicorn 启动时报 `Address already in use`

原因：

- 旧 Gunicorn 仍占用 `127.0.0.1:5000`

处理：

```bash
pkill -9 -f gunicorn
sleep 2
```

然后再重新启动 Gunicorn。

### 6.4 数据丢失风险

风险来源：

- 直接删除 `/www/wwwroot/codde` 再覆盖

必须保留：

- `/www/wwwroot/codde/backend/instance`
- `/www/wwwroot/codde/backend/.env`

## 7. 当前维护建议

- 所有生产更新统一走 zip 上传方式
- 所有生产更新统一保留 `backend/instance` 和 `.env`
- 后端固定使用 `python3.11`
- 如后续稳定运行，建议再补 `systemd` 托管 Gunicorn，替代手动 `nohup`
