# 1. Summary

在仪表盘新增一个“宁波市鄞州区下应街道当天天气”卡片，实时展示当前天气与今日高低温等核心信息，帮助门店运营快速感知当日天气对到店与消费的影响。

# 2. Goals / Non-goals

## Goals

- 在仪表盘页面新增 1 个天气卡片，默认展示宁波市鄞州区下应街道当天天气。
- 页面刷新或点击“刷新数据”时，同步刷新天气数据。
- 后端提供受鉴权保护的天气聚合接口，前端不直接请求第三方天气服务（固定接入高德地图天气）。
- 天气接口异常时，卡片显示友好降级状态，不影响现有仪表盘统计卡片渲染。
- 天气数据包含：天气描述、当前温度、体感温度、当日最高/最低温、湿度、风向/风速、更新时间。
- 接口响应时间目标：在第三方服务正常情况下，P95 <= 2 秒（本地/内网部署环境下可放宽为 3 秒）。

## Non-goals

- 不实现多城市切换（本期固定宁波市鄞州区下应街道）。
- 不实现未来 7 天预报（本期仅“当日”与“当前”信息）。
- 不实现天气历史数据落库。
- 不改动现有业务统计逻辑（充值/消费/计时等 KPI 计算保持不变）。
- 不突破天气预报月配额 5000（本期以缓存与调用策略控制）。

# 3. Current State & Constraints

## Current behavior/state

- 仪表盘当前通过 `GET /api/dashboard/stats` 获取经营统计，并在 `Dashboard.vue` 渲染多块 KPI 卡片。
- 仪表盘刷新按钮仅触发统计数据刷新。
- 后端 `backend/routes/dashboard.py` 当前仅提供：`/stats`、`/charts`、`/recent-activities`。
- 前端 API 层 `frontend/src/api/index.js` 中 `dashboardApi` 未包含天气接口调用。

## Environment/platform constraints

- 运行环境：Windows + PowerShell。
- 前端：Vue 3 + Vite。
- 后端：Flask + SQLAlchemy。
- 接口均走鉴权（`@token_required`）。

## Risk constraints

- 不自动执行依赖安装/升级操作。
- 未经明确批准，不改依赖声明与 lock 文件。
- 天气第三方服务不可用时必须可降级。
- 天气预报月配额固定为 5000，必须通过 5 分钟缓存降低调用频率。

# 4. Requirements

## Functional requirements

### P0

- 新增后端接口：`GET /api/dashboard/weather/today`（鉴权保护）。
- 接口返回宁波市鄞州区下应街道当天实时天气字段：
  - `city`
  - `weather`
  - `temperature`
  - `feels_like`
  - `temp_min`
  - `temp_max`
  - `humidity`
  - `wind_direction`
  - `wind_speed`
  - `observed_at`
  - `provider`
- 仪表盘新增天气卡片并展示以上字段中的核心信息。
- 仪表盘初始化加载与手动刷新时，天气接口应一起请求。
- 天气接口失败时，前端显示“天气数据暂不可用，请稍后重试”，并保留刷新入口。

### P1

- 后端增加基础超时与错误映射（例如第三方超时、返回格式异常、网络异常）。
- 可配置高德地图天气 API Key 与 API Host（通过环境变量）。
- 天气数据返回包含服务端更新时间（用于前端“最后更新”展示）。

### P2

- 增加短时缓存（固定 5 分钟）以降低第三方调用频率。

## Non-functional requirements

- 安全：第三方 API Key 仅在后端使用，前端不得暴露。
- 可靠性：第三方异常不影响仪表盘其他模块。
- 可维护性：天气提供方适配逻辑集中在独立函数/模块，避免散落在路由层。
- 兼容性：保持现有仪表盘布局在桌面与移动端可读。

## Compatibility/migration requirements

- 不涉及数据库 schema 迁移。
- 对既有 `/api/dashboard/stats` 响应结构无破坏性改动。

# 5. Design

## Overall approach

- 前端：
  - 在 `Dashboard.vue` 新增 `weather` 状态与 `weatherError` 状态。
  - `refreshData()` 中并行拉取 `stats` 与 `weather`。
  - 新增天气卡片 UI，使用当前页面已有卡片风格（圆角、边框、浅背景）。
- 后端：
  - 在 `backend/routes/dashboard.py` 新增 `/weather/today` 路由。
  - 路由调用高德天气服务函数获取宁波市鄞州区下应街道天气，转换为统一响应字段后返回。
  - 对天气结果启用 5 分钟缓存，缓存命中时直接返回缓存数据。
  - 按 5000/月配额约束控制请求频率，超限或上游拒绝时走降级文案。
  - 发生异常返回可识别错误信息与适当状态码（建议 502/504）。

## Key decisions

- 采用“后端聚合 + 前端消费”模式，避免在前端暴露 API Key。
- 天气供应商固定为高德地图天气（本期不做多供应商抽象）。
- 天气接口独立于统计接口，降低耦合，便于未来替换数据源。
- 刷新时并行请求，避免天气阻塞统计渲染。
- 通过 5 分钟缓存控制上游调用，满足 5000/月配额。

## Alternatives and trade-offs

- 方案 A（推荐）：新增独立天气接口 `/dashboard/weather/today`
  - 优点：职责清晰、可独立降级、对统计接口零影响。
  - 缺点：前端多一次请求。
- 方案 B：把天气字段并入 `/dashboard/stats`
  - 优点：单请求。
  - 缺点：统计与天气耦合，第三方天气异常会污染核心经营统计接口。

## Impact scope

- 前端：`frontend/src/views/Dashboard.vue`、`frontend/src/api/index.js`
- 后端：`backend/routes/dashboard.py`（必要时新增 `backend/utils/weather_amap.py`）
- 配置：`backend/config.py`（新增高德天气相关环境变量读取）

# 6. Acceptance Criteria

- 成功登录后进入仪表盘，可见“宁波市鄞州区下应街道当天天气”卡片。
- 正常网络下卡片显示完整天气核心信息（天气、温度、高低温、湿度、风、更新时间）。
- 点击“刷新数据”后，天气信息与统计信息均刷新，且 UI 不阻塞。
- 断网或天气服务异常时：
  - 天气卡片显示明确错误提示；
  - 统计卡片仍正常显示。
- 在日常门店使用下（刷新频率遵循 5 分钟缓存命中），月调用量不超过 5000 配额。
- 未登录访问天气接口返回 401（受现有鉴权保护）。
- 现有仪表盘统计卡片字段与数值逻辑不发生回归。

# 7. Validation Strategy

候选验证命令（PowerShell）：

```powershell
# 1) 前端构建检查（预期：build 成功，无 Dashboard.vue 报错）
cd frontend; npm run build
```

```powershell
# 2) 后端语法检查（预期：无输出或无错误）
python -m py_compile backend\routes\dashboard.py
python -m py_compile backend\utils\weather_amap.py
python -m py_compile backend\config.py
```

```powershell
# 3) 本地接口冒烟（预期：登录后请求天气接口返回 success=true 且含 weather/temperature 等字段）
# 注：需先启动后端服务并准备 token
# 示例：Invoke-RestMethod -Uri http://127.0.0.1:5000/api/dashboard/weather/today -Headers @{ Authorization = "Bearer <TOKEN>" }
```

```powershell
# 4) 前端手工验收（预期：仪表盘出现天气卡片，点击“刷新数据”天气会更新）
cd frontend; npm run dev
```

若运行命令需要额外依赖安装/恢复，则标记为“用户执行并回传输出”。

# 8. Risks & Rollback

## Risks

- 第三方天气 API 限流或不可用，导致天气卡片频繁报错。
- 天气字段格式不稳定，可能导致解析失败。
- 网络延迟导致刷新体验下降。
- 月配额 5000 被快速耗尽导致后续无法获取天气数据。

## Rollback

- 代码回滚：移除新增天气接口与前端天气卡片代码，恢复到仅统计仪表盘。
- 配置回滚：移除/忽略天气环境变量，不影响其他业务模块。
- 运行时降级：保留卡片壳但仅显示“天气服务暂不可用”。
- 配额回滚：当接近月配额上限时，临时延长缓存窗口（例如 15 分钟）减少请求。

# 9. Open Questions

- 天气供应商已确认：高德地图天气（Amap Weather）。
- 地区已确认：宁波市鄞州区下应街道（固定）。
- 缓存窗口已确认：5 分钟。
- 天气预报月配额已确认：5000。

# 10. References

- `frontend/src/views/Dashboard.vue`
- `frontend/src/api/index.js`
- `backend/routes/dashboard.py`
- `backend/config.py`
- 高德天气文档：`https://lbs.amap.com/api/webservice/guide/api/weatherinfo/`

---

## /spec Completion Checklist

- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
