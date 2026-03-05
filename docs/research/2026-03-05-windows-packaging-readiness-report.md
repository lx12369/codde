# 2026-03-05 Windows 打包可迁移性审计报告（StudioSystem）

## 1. 结论

当前版本 **不能承诺“所有 Windows 电脑都无缝”**，但核心功能已具备较高可迁移性。

- 已验证：打包 EXE 可启动、可登录、可访问关键 API、221 色可自动内置。
- 仍有风险：语音女声依赖目标机系统语音包、5000 端口占用/防火墙提示、天气依赖外网、打包脚本在“重打包场景”存在机器绑定问题。

## 2. 本次已完成的实测（本机）

### 2.1 EXE 启动可用性
- 检查产物存在：`backend/dist/StudioSystem.exe`（约 16MB）
- 运行后探测首页：`http://127.0.0.1:5063/` 返回 `STATUS=200`

### 2.2 登录链路
- 使用打包 EXE 启动后调用登录接口：`/api/auth/login`
- 结果：`LOGIN=OK`（默认管理员可登录）

### 2.3 天气接口稳定性
- 登录后调用：`/api/dashboard/weather/today`
- 结果：`WEATHER=OK;PROVIDER=Amap Weather`
- 说明：天气接口在当前网络可用；网络异常时后端会返回错误并由前端降级提示。

### 2.4 221 色内置验证
- 登录后调用：`/api/bead-inventory/materials?page=1&page_size=1`
- 返回 `pagination.total = 221`
- 结论：Mard 221 色已作为内置数据自动加载，无需在新电脑手工导入。

### 2.5 语法与静态完整性
- `python -m py_compile` 已通过（关键后端文件）
- 打包输入包含：`frontend/dist` 与 `backend/data/mard_palette_v1.json`

## 3. 已确认的“非无缝风险项”

### R1. 语音“女声/拟人感”无法跨机保证一致
- 原因：浏览器 TTS 可用 voice 由目标机系统/浏览器语音包决定。
- 当前实现：已做“中文女声优先 + 多级降级”，但无法保证每台机器都有 `Xiaoxiao Natural/Neural`。
- 影响：可播报，但音色可能与开发机不同。

### R2. 默认端口冲突风险（5000）
- 位置：`backend/desktop_main.py` 默认 `STUDIO_PORT=5000`
- 风险：目标机 5000 被占用时，程序无法正常监听。
- 建议：发布说明中加入“如启动失败，改用 `STUDIO_PORT`（如 5060）”。

### R3. 防火墙弹窗/策略风险
- 位置：`desktop_main.py` 默认 `host=0.0.0.0`
- 风险：首次运行可能触发 Windows 防火墙询问，部分企业机策略会阻断。
- 影响：本机回环通常可用，局域网访问可能受限。

### R4. 天气依赖外网
- 位置：`backend/utils/weather_amap.py`
- 说明：无高德 key 时走 Open-Meteo；有 key 时走高德。
- 风险：断网或 DNS 异常时天气模块不可用（但系统主流程不应崩）。

### R5. “在别的电脑重打包”流程不无缝
- 位置：`backend/build_exe.ps1`
- 问题：`$PythonExe` 默认写死为本机绝对路径。
- 影响：如果在新机器直接执行该脚本，极可能失败。
- 备注：这不影响“把已打好的 EXE 发给别人运行”，只影响“别人重新打包”。

## 4. 建议你在发布包中附带的最小说明

1. 首次启动失败时，检查是否被杀毒软件拦截，放行 `StudioSystem.exe`。
2. 若 5000 端口占用，设置环境变量 `STUDIO_PORT=5060` 后再启动。
3. 若语音音色不理想，在系统中安装中文女声语音包（Edge/Windows 语音）。
4. 天气不可用不影响核心业务，可继续使用系统。
5. 首次登录后立即修改默认管理员密码（`admin/admin123`）。

## 5. 若要进一步逼近“无缝”建议的代码改动（未在本次执行）

1. 给 `desktop_main.py` 增加端口占用自动探测与自增回退（5000->5001->...）。
2. 在启动页增加“运行环境自检面板”（端口、网络、语音、数据库写权限）。
3. 调整默认绑定为 `127.0.0.1`，将 LAN 开关改为可配置项，降低防火墙阻断概率。
4. 将 `build_exe.ps1` 改为自动探测 Python 路径（去掉机器绝对路径依赖）。

## 6. 审计涉及的关键文件

- `backend/desktop_main.py`
- `backend/build_exe.ps1`
- `backend/models/init_db.py`
- `backend/utils/weather_amap.py`
- `backend/routes/bead_inventory.py`
- `backend/data/mard_palette_v1.json`
- `frontend/src/views/ActiveTimers.vue`

