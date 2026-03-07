# 服务器压缩包更新说明

适用环境：

- 服务器：宝塔 Linux 面板
- 项目目录：`/www/wwwroot/codde`
- 后端：Flask + Gunicorn
- 数据库：MySQL/MariaDB
- 更新方式：上传压缩包到服务器后在宝塔终端执行脚本

当前服务器已经采用“代码更新不覆盖运行数据”的策略，以下内容会保留：

- `backend/.env`
- `backend/.venv`
- `backend/instance`
- `.git`

## 一、更新前提

服务器上需要有这两个脚本：

- `scripts/deploy-codde-zip.sh`
- `scripts/server-update.sh`

它们职责分别是：

- `deploy-codde-zip.sh`
  - 解压更新包
  - 替换项目代码
  - 保留 `.env`、`.venv`、`instance`
  - 调用重启脚本

- `server-update.sh`
  - 停止旧的 Gunicorn
  - 启动新的 Gunicorn
  - 校验后端是否正常读取 MySQL 配置

## 二、本地打包规范

建议上传的压缩包直接包含项目根目录内容：

- `backend/`
- `frontend/`
- `docs/`
- `scripts/`
- 其他源码文件

不要包含这些运行时内容：

- `.git/`
- `.venv/`
- `backend/.venv/`
- `backend/.env`
- `backend/instance/`
- 本地日志
- 备份文件

前端如果有生产静态文件，压缩包中应包含：

- `frontend/dist/`

如果压缩包里没有 `frontend/dist/`，服务器虽然能完成更新，但前端静态页不会随代码一起刷新。

## 三、标准更新步骤

### 1. 上传压缩包

把压缩包上传到服务器，文件名固定为：

```bash
/tmp/codde.zip
```

预期：

```bash
ls -lh /tmp/codde.zip
```

应能看到文件存在。

### 2. 在宝塔终端执行更新

执行：

```bash
cd /www/wwwroot/codde
bash scripts/deploy-codde-zip.sh /tmp/codde.zip
```

预期：

- 输出 `Deploy complete.`
- 输出一份项目备份路径
- Gunicorn 被重新拉起

### 3. 验证后端

执行：

```bash
cd /www/wwwroot/codde/backend
./.venv/bin/python -c "from app import create_app; app=create_app('production'); print(app.config['SQLALCHEMY_DATABASE_URI'])"
```

预期：

- 输出 `mysql+pymysql://...`
- 不应出现 `sqlite:///...`

### 4. 验证公网站点

执行：

```bash
curl -I -H 'Host: 47.112.117.203' http://127.0.0.1/
curl -s -H 'Host: 47.112.117.203' http://127.0.0.1/api/data/storage-info
```

预期：

- 首页返回 `HTTP/1.1 200 OK`
- `/api/data/storage-info` 未登录时返回 `401`
- 返回 `401` 说明请求已经进入 Flask，而不是落到默认站点

## 四、当前线上运行方式

当前线上后端启动方式：

```bash
./.venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 "app:create_app('production')"
```

当前线上反向代理配置：

- 配置文件：`/www/server/panel/vhost/nginx/codde.conf`
- 前端静态目录：`/www/wwwroot/codde/frontend/dist`
- API 代理：`/api/ -> http://127.0.0.1:5000/api/`

## 五、不要做的事

不要在每次更新时做这些操作：

- 不要删除 `backend/.venv`
- 不要删除 `backend/.env`
- 不要删除 `backend/instance`
- 不要重新安装 LNMP/LAMP 套件
- 不要在宝塔里重新创建一个空站点覆盖当前目录
- 不要在宝塔数据库页点击“安装Mysql环境”来替代当前 MariaDB

## 六、出问题时回滚

每次执行 `deploy-codde-zip.sh` 都会生成项目备份，例如：

```bash
/www/backup/codde/project_2026-03-07-101500.tar.gz
```

需要回滚时：

```bash
cd /www/wwwroot
sudo rm -rf /www/wwwroot/codde
sudo tar -xzf /www/backup/codde/project_2026-03-07-101500.tar.gz -C /www/wwwroot
cd /www/wwwroot/codde
bash scripts/server-update.sh
```

## 七、推荐的以后更新命令

以后固定只做这两步：

```bash
cd /www/wwwroot/codde
bash scripts/deploy-codde-zip.sh /tmp/codde.zip
```

如果只想单独重启后端：

```bash
cd /www/wwwroot/codde
bash scripts/server-update.sh
```
