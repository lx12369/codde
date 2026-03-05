# /plan：仪表盘新增下应街道天气卡片执行计划

## 1. 关联规格
- Spec：`specs/2026-03-04-dashboard-wenzhou-weather-card.md`

## 2. 范围与非范围
### Scope
- 新增后端天气聚合接口：`GET /api/dashboard/weather/today`（鉴权保护）。
- 固定接入高德地图天气（Amap Weather），地区固定为“宁波市鄞州区下应街道”。
- 后端实现 5 分钟缓存与异常降级返回。
- 前端仪表盘新增天气卡片，并在初始化与“刷新数据”时同步刷新天气。
- 前端错误态显示“天气数据暂不可用，请稍后重试”，不影响现有统计模块。
- 在天气预报月配额 5000 约束下，通过缓存与调用策略避免超量。

### Out of Scope
- 不实现多城市切换。
- 不实现未来天气预报与历史天气落库。
- 不修改现有统计口径与核心 KPI 逻辑。
- 不改动依赖声明与 lock 文件。

## 3. 执行前提
- 本阶段仅输出计划文档，不做源码实现。
- `/do` 阶段必须按本计划执行；若需求变化，先回到 `/plan` 更新。
- 天气服务密钥由环境变量提供，不写入前端代码。

## 4. 分步实施（有序、可验证、可回退）
### Step 1：后端配置与天气服务封装
- 操作：
  - 在 `backend/config.py` 增加高德天气相关配置项（如 `AMAP_WEATHER_KEY`、`AMAP_WEATHER_API_HOST`、位置配置、缓存秒数=300）。
  - 新增天气服务模块（建议 `backend/utils/weather_amap.py`），封装：请求第三方、字段转换、错误处理、缓存读写。
  - 增加配额控制辅助逻辑（统计当月请求次数或预留阈值判断）。
- 验证：
  - 天气服务函数在输入固定位置参数时，返回统一字段结构（无前端耦合字段）。
  - 5 分钟内重复请求优先命中缓存，不重复消耗上游调用。
- 回退：
  - 回退新增天气模块与配置项，不影响现有 dashboard 路由。

### Step 2：新增后端天气接口
- 操作：
  - 在 `backend/routes/dashboard.py` 增加 `GET /weather/today` 路由并加 `@token_required`。
  - 路由调用天气服务函数，返回标准化字段：`city/weather/temperature/feels_like/temp_min/temp_max/humidity/wind_direction/wind_speed/observed_at/provider`。
  - 当检测到月配额接近上限或上游返回限流时，返回可降级错误文案并保持接口可用。
  - 第三方异常时返回可识别错误信息（建议 502/504），不影响其他路由。
- 验证：
  - 带 token 请求接口返回 `success=true` 且字段完整。
  - 无 token 请求返回 401。
- 回退：
  - 移除新增路由并保留服务模块，或整块回退该路由改动。

### Step 3：前端 API 层接入
- 操作：
  - 在 `frontend/src/api/index.js` 的 `dashboardApi` 中新增 `getWeatherToday` 方法，调用 `/dashboard/weather/today`。
- 验证：
  - 前端可独立调用该方法，拿到统一天气字段对象。
- 回退：
  - 删除 `getWeatherToday` 方法，不影响既有 `dashboardApi` 方法。

### Step 4：仪表盘新增天气卡片与数据流
- 操作：
  - 在 `frontend/src/views/Dashboard.vue` 新增天气状态：`weather`、`weatherError`、`weatherUpdatedAt`。
  - `refreshData()` 中并行请求 `stats` 与 `weather`。
  - 新增“下应街道天气”卡片，展示核心天气字段与更新时间。
  - 天气失败时仅在天气卡片展示错误，不覆盖全局统计错误状态。
- 验证：
  - 页面首次进入可见天气卡片；点击“刷新数据”天气同步更新。
  - 天气接口失败时统计区仍正常。
- 回退：
  - 回退 `Dashboard.vue` 天气区块与对应状态字段，保留 stats 流程。

### Step 5：联调与容错收敛
- 操作：
  - 验证后端缓存 5 分钟命中行为（短时间重复请求返回同一更新时间或缓存标识）。
  - 验证配额控制行为（模拟限流或阈值触发时的降级响应）。
  - 验证登录态过期、401 场景与页面跳转逻辑不回归。
- 验证：
  - 缓存命中、配额降级、异常降级、401 拦截均符合预期。
- 回退：
  - 如缓存引发问题，先降级为无缓存直连（保留接口与 UI）。

## 5. 验证命令（PowerShell）与预期结果
### 5.1 工具可用性
```powershell
Get-Command python
Get-Command node
Get-Command npm
```
预期：均返回命令路径。

### 5.2 后端语法检查
```powershell
python -m py_compile backend\routes\dashboard.py
python -m py_compile backend\utils\weather_amap.py
python -m py_compile backend\config.py
```
预期：无语法错误。

### 5.3 前端构建检查
```powershell
Set-Location frontend
npm run build
```
预期：Vite 构建成功，无 Dashboard 编译错误。

### 5.4 后端接口冒烟（用户执行并回传输出）
```powershell
# 先启动后端后再执行（需有效 token）
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/dashboard/weather/today -Headers @{ Authorization = "Bearer <TOKEN>" }
```
预期：返回 `success=true`，且含 weather/temperature/temp_min/temp_max 等字段。

### 5.5 前端联调（用户执行并回传结果）
```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```
预期：仪表盘可见天气卡片，点击“刷新数据”可刷新天气。

### 5.6 依赖缺失时（用户执行并回传输出）
```powershell
Set-Location frontend
npm install
```
```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
预期：安装成功后继续构建与联调。

## 6. 验收清单（映射 Spec）
- AC1：仪表盘显示“宁波市鄞州区下应街道当天天气”卡片。
- AC2：卡片字段完整显示（天气、当前温度、体感、高低温、湿度、风、更新时间）。
- AC3：刷新按钮可同步刷新统计与天气。
- AC4：天气失败时仅天气卡片降级，统计区不受影响。
- AC5：天气接口受鉴权保护（未登录 401）。
- AC6：缓存策略为 5 分钟并可观察到命中行为。
- AC7：月配额 5000 下具备防超量策略（缓存命中与限流降级）。
- AC8：前后端构建/语法检查通过。

## 7. 风险与应对
- 风险：第三方天气服务限流/超时。
  - 应对：5 分钟缓存 + 接口错误降级文案。
- 风险：高德返回字段变化导致解析失败。
  - 应对：服务层做字段容错与默认值兜底。
- 风险：月配额 5000 在高频刷新下被耗尽。
  - 应对：缓存命中优先、配置限流阈值、超限时走降级提示。
- 风险：天气加载拖慢仪表盘交互。
  - 应对：并行请求 + 卡片独立错误态，避免全页阻塞。

## 8. 进入 /do 门槛
- 已包含：
  - 关联 spec
  - scope / out-of-scope
  - 有序、可验证、可回退步骤
  - PowerShell 验证命令与预期结果
- 计划批准后进入 `/do`。
