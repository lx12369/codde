# 仪表盘界面重构规格（保留计费日切换与今日消费核心指标）

## 1. Summary
- 将 `Dashboard` 页面重构为更精简、可扩展的结构，必须保留“计费日类型切换”与“今日消费金额/今日消费人数”展示能力。
- 价值：减少信息噪音，突出运营核心指标，同时为后续自由增删模块留出稳定骨架。

## 2. Goals / Non-goals
### Goals
- 保留并可用：计费日类型切换按钮、当前计费日标签、切换后状态即时可见。
- 保留并可用：`今日消费金额` 与 `今日消费人数` 两个核心指标卡片，且来自真实接口数据。
- 允许删除当前仪表盘其余模块（如趋势图、最近活动、其他统计卡）且不影响页面可用性。
- 允许新增任意非核心展示模块，但不得破坏核心功能与路由访问。
- 页面在桌面与移动端（最小宽度 360px）均可正常阅读，无明显布局溢出。

### Non-goals
- 不修改后端统计口径与计算逻辑（`backend/routes/dashboard.py`）。
- 不重构非仪表盘页面（如 `Customers.vue`、`Transactions.vue`）。
- 不引入新依赖，不修改依赖声明与锁文件。

## 3. Current State & Constraints
- 当前状态：
  - `frontend/src/views/Dashboard.vue` 同时包含 7 个统计卡、2 张趋势图、最近活动表，并已包含计费日切换与刷新逻辑。
  - 计费日类型逻辑在 `frontend/src/utils/dayType.js`，通过 `localStorage` 键 `billing_day_type_override` 持久化手动覆盖值。
  - 核心数据来自 `GET /api/dashboard/stats`，字段包括 `today_consumption_amount`、`today_consumption_people`。
- 环境约束：
  - Windows + PowerShell 工作流。
  - 路由入口固定为 `frontend/src/router/index.js` 中的 `/dashboard`。
- 风险约束：
  - 不自动执行依赖安装/恢复/更新。
  - 未获批准不改依赖文件与锁文件。
  - `/spec` 阶段仅允许变更 `specs/`。

## 4. Requirements
### Functional Requirements
- P0
  - `Dashboard` 页面必须保留计费日类型状态显示（工作日/周末）与切换动作。
  - 点击切换后，UI 状态应立即更新，并写入/读取 `localStorage` 覆盖值。
  - 页面必须显示两个核心指标：
    - `今日消费金额`（映射 `today_consumption_amount`）
    - `今日消费人数`（映射 `today_consumption_people`）
  - 核心指标必须来自 `/api/dashboard/stats` 返回值，而非硬编码或 mock。
  - 除上述功能外，其他区域允许自由删除或新增。
- P1
  - 保留“刷新”能力，用于手动重新拉取数据并更新展示。
  - 在数据加载失败时提供可见的降级表现（例如占位值、提示文案或错误态）。
- P2
  - 可新增信息块（如快捷入口、说明卡片、运营提示）作为扩展区域，但不影响 P0/P1。

### Non-functional Requirements
- 保持现有鉴权与路由行为不变。
- 不新增后端接口、不修改现有接口契约。
- 组件内状态与数据映射应清晰，避免保留无用变量/方法。
- 基础可维护性：重构后结构应便于继续“增删模块”。

### Compatibility / Migration
- 兼容现有后端响应结构（`response.data` 下的统计对象）。
- 兼容已有计费日类型存储键，不做迁移。

## 5. Design
### Overall Approach
- 采用“核心优先”布局：
  - 顶部：页面标题 + 当前计费日类型 + 切换按钮 + 刷新按钮。
  - 中部：仅保留两个核心指标卡片（今日消费金额、今日消费人数）。
  - 底部（可选）：可扩展区域（允许新增或留空）。
- 文本化高层流程：
  - `/dashboard` 路由进入 `Dashboard.vue`
  - 初始化时读取 `dayType`（含本地覆盖）并请求 `/dashboard/stats`
  - 将返回字段映射到两个核心 KPI 卡片
  - 用户可执行“切换计费日类型”与“刷新数据”

### Key Decisions
- 决策 1：以“保留两项核心业务能力”为唯一硬约束，其余模块全部可变。
  - 原因：与需求“其他随意删除与添加”一致，降低改造阻力。
- 决策 2：复用现有 `dayType` 工具函数，不重写计费日逻辑。
  - 原因：当前实现已覆盖自然日与手动覆盖场景，稳定且可复用。
- 决策 3：继续使用 `/dashboard/stats` 单接口拉取核心指标。
  - 原因：避免接口扩散与后端改动。

### Alternatives & Trade-offs
- 方案 A：仅在现有页面隐藏非核心模块，尽量不改结构。
  - 优点：开发快、回归风险小。
  - 缺点：代码仍臃肿，可维护性差，“重构”收益有限。
- 方案 B（推荐）：重写 `Dashboard.vue` 布局骨架，仅保留核心逻辑与必要状态。
  - 优点：结构清晰，后续增删模块成本低。
  - 缺点：一次性变更面更大，需要更细致验证。

### Impact Scope
- 主要影响：
  - `frontend/src/views/Dashboard.vue`
- 复用但不预期修改：
  - `frontend/src/utils/dayType.js`
  - `frontend/src/api/index.js`（`dashboardApi` 或 `api.get('/dashboard/stats')`）
- 非预期影响（应避免）：
  - `backend/routes/dashboard.py`
  - 其他页面与路由配置

## 6. Acceptance Criteria
- AC1：访问 `/dashboard` 页面后，可看到“当前计费日类型”与“切换为X”按钮。
- AC2：点击计费日切换后，标签在“工作日/周末”之间切换，刷新页面后状态仍与 `localStorage` 一致。
- AC3：页面可见且仅需保证以下两项核心指标可读：
  - `今日消费金额` 显示金额格式（含货币符号或固定小数格式）
  - `今日消费人数` 显示人数数值
- AC4：核心指标数据由 `/api/dashboard/stats` 返回字段驱动，接口返回变化可反映到页面。
- AC5：除核心能力外，原有其他模块可被删除或替换，且页面无运行时报错。
- AC6：在 360px 宽度与常见桌面宽度下，页面无明显横向溢出，核心信息可见。

## 7. Validation Strategy
- 候选验证命令（供 `/plan` 阶段落地执行）：

```powershell
Get-Command node
Get-Command npm
```

预期：命令能返回可执行路径，确认前端构建工具可用。

```powershell
Set-Location frontend
npm run build
```

预期：前端构建成功，输出无编译错误（用于验证重构后语法与打包通过）。

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

预期：开发服务启动成功，可在浏览器访问仪表盘进行手工验收。

```powershell
Set-Location backend
..\.venv\Scripts\python.exe app.py
```

预期：后端 API 在本地启动成功，`/api/dashboard/stats` 可返回统计数据。

- 若本地缺少前端依赖导致 `npm run build`/`npm run dev` 无法执行，以下命令属于“会改变依赖状态”的用户执行项（需用户手动运行并粘贴输出）：

```powershell
Set-Location frontend
npm install
```

预期：依赖安装成功，随后可继续执行构建/运行验证命令。

- 手工验收要点：
  - 打开 `/dashboard`，观察两项核心指标渲染。
  - 点击计费日切换，确认标签变更与持久化。
  - 点击刷新，确认核心指标可重新拉取。

## 8. Risks & Rollback
### Risks
- 重构时删除旧模块后残留无效状态/引用，导致编译或运行错误。
- 指标字段映射写错（例如拼写错误）导致显示为 `0` 或空值。
- 过度调整样式导致移动端布局溢出。

### Rollback Strategy
- 以单文件回退为主：回退 `frontend/src/views/Dashboard.vue` 到改造前版本。
- 若采用分步提交，可按提交粒度回退仪表盘重构提交，恢复旧界面行为。

## 9. Open Questions
- None

## 10. References
- `frontend/src/views/Dashboard.vue`
- `frontend/src/utils/dayType.js`
- `frontend/src/api/index.js`
- `backend/routes/dashboard.py`
- `frontend/src/router/index.js`

---

## /spec Completion Checklist (self-check)
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable (not vague)
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
