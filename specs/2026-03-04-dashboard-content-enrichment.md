# 仪表盘内容充实规格（在保留核心能力前提下增强信息展示）

## 1. Summary
- 在保留“计费日类型切换 + 今日消费金额/今日消费人数”的前提下，为仪表盘补充可读、可用的运营信息展示模块，解决页面过于空旷的问题。
- 价值：提高首屏信息密度与可操作性，让用户进入仪表盘后可直接获取关键经营状态并快速跳转常用页面。

## 2. Goals / Non-goals
### Goals
- 保留并继续可用：计费日类型显示与切换、刷新动作、今日消费金额、今日消费人数。
- 新增至少 3 个内容展示模块（例如：运营总览卡片、结构洞察、最近活动、快捷入口），并形成清晰层级。
- 新增内容优先复用现有接口（`/dashboard/stats`、`/dashboard/recent-activities`、可选 `/dashboard/charts`），不增加后端改造成本。
- 页面在移动端（360px）和桌面端都保持信息可读且无明显横向溢出。
- 增强状态反馈：加载中、数据为空、接口失败时均有可见降级表现。

### Non-goals
- 不修改后端统计口径与聚合逻辑（`backend/routes/dashboard.py`）。
- 不改动非仪表盘页面的业务行为。
- 不引入新 UI 库或图表库，不修改依赖声明与锁文件。

## 3. Current State & Constraints
- 当前状态：
  - `frontend/src/views/Dashboard.vue` 现为“简化核心版”，仅有头部、2 个核心 KPI 和一个占位扩展区。
  - 当前已保留计费日切换与两项核心指标，但除核心指标外缺乏辅助信息模块，页面视觉和信息密度偏低。
  - 可用数据源：
    - `GET /api/dashboard/stats`：`total_customers`、`today_transactions`、`today_amount`、`today_consumptions`、`today_consumption_people`、`today_consumption_amount`、`total_transactions`、`active_timers_count`
    - `GET /api/dashboard/recent-activities`
    - `GET /api/dashboard/charts`（可选）
- 环境约束：
  - Windows + PowerShell 开发流程。
  - 仪表盘入口仍为 `/dashboard` 路由。
- 风险约束：
  - 不自动执行依赖安装/恢复/更新。
  - 未获批准不修改依赖文件与 lock 文件。
  - `/spec` 阶段仅允许变更 `specs/`。

## 4. Requirements
### Functional Requirements
- P0
  - 保留并稳定运行以下能力：
    - 计费日类型显示（工作日/周末）与手动切换。
    - “今日消费金额”“今日消费人数”展示。
    - 刷新按钮触发重新拉取仪表盘数据。
  - 新增“运营总览”模块：至少展示 4 个来自 `/dashboard/stats` 的指标（如客户总数、今日充值笔数、今日充值金额、活跃计时数）。
  - 新增“最近活动”模块（精简版列表或表格），数据来自 `/dashboard/recent-activities`。
  - 新增“快捷入口”模块（跳转到客户、交易、计时等高频页面）。
- P1
  - 新增“结构洞察”展示（例如消费/充值金额对比、消费人次与消费笔数关系），可用百分比条或文本摘要实现，不强制图表。
  - 最近活动支持空态提示（无数据时显示“暂无活动”）。
  - 接口异常时，新增模块需降级显示而非整页空白。
- P2
  - 可加入轻量视觉增强（分区标题、背景层次、图标/标签），提升可扫读性，但不影响性能与交互清晰度。

### Non-functional Requirements
- 不引入新增依赖，保持现有打包链路可通过。
- 保持主要交互元素触达尺寸与可点击性（移动端按钮最小可触达高度约 44px）。
- 信息层级清晰：核心指标优先级高于辅助模块，避免喧宾夺主。
- 可维护性：模块化组织 `Dashboard.vue` 中的状态与计算，避免无用变量残留。

### Compatibility / Migration
- 兼容当前 API 响应结构（Axios 拦截器后仍可能出现 `response.data` 或平铺对象，需兼容处理）。
- 兼容已有本地存储键 `billing_day_type_override`，不变更迁移策略。

## 5. Design
### Overall Approach
- 页面结构采用“1 个核心头部 + 4 个内容分区”：
  - 分区 A：头部控制区（标题、计费日状态、切换、刷新、最后更新时间）。
  - 分区 B：核心 KPI（今日消费金额、今日消费人数）。
  - 分区 C：运营总览（4~6 个小卡片，来自 `/dashboard/stats`）。
  - 分区 D：结构洞察（金额或笔数对比摘要，可视条形占比）。
  - 分区 E：最近活动 + 快捷入口（双列或上下布局，按屏宽自适应）。
- 数据策略：
  - 首次加载与刷新统一走 `refreshData()`，并行获取 `stats` 与 `recent-activities`（若实现洞察趋势可追加 `charts`）。
  - 失败降级时保留核心框架，局部显示错误提示与兜底值。

### Key Decisions
- 决策 1：继续以 `/dashboard/stats` 作为主数据源扩展展示，不拆分新接口。
  - 原因：后端已具备足够字段，前端可直接构建信息模块。
- 决策 2：结构洞察优先用“文本+占比条”，而不是强依赖图表。
  - 原因：实现成本低、移动端可读性高、依赖与性能风险小。
- 决策 3：最近活动做“精简展示”而非完整管理表格。
  - 原因：仪表盘以概览为主，详细操作仍在专属页面完成。

### Alternatives & Trade-offs
- 方案 A：恢复原先复杂仪表盘（双图表 + 大表格 + 多卡片）。
  - 优点：信息非常全面。
  - 缺点：开发与维护成本高，视觉负担重，可能重回“噪音过多”。
- 方案 B（推荐）：在当前核心版上增量添加 3~5 个轻量模块。
  - 优点：保留当前清晰骨架，按需补充内容，风险可控。
  - 缺点：需要对信息优先级做取舍，不能一次覆盖所有细节场景。

### Impact Scope
- 主要影响：
  - `frontend/src/views/Dashboard.vue`
- 可能复用但不预期修改：
  - `frontend/src/utils/dayType.js`
  - `frontend/src/api/index.js`
- 非预期影响（应避免）：
  - `backend/routes/dashboard.py`
  - 路由与鉴权配置文件

## 6. Acceptance Criteria
- AC1：进入 `/dashboard` 后，仍可见计费日类型、切换按钮、刷新按钮，切换可立即生效并持久化。
- AC2：页面显示“今日消费金额”“今日消费人数”两项核心指标，数值来自 `/api/dashboard/stats`。
- AC3：页面新增至少 3 个非核心展示模块，且每个模块均有实质内容（非纯占位文案）。
- AC4：运营总览模块至少展示 4 个来自 `stats` 的字段，且字段标签与值映射正确。
- AC5：最近活动模块能展示接口返回记录；无记录时显示空态；接口失败时显示错误提示或兜底提示。
- AC6：移动端 360px 与桌面端下均无明显横向溢出，核心信息和新增模块可读。
- AC7：构建通过（`npm run build`），页面无运行时报错。

## 7. Validation Strategy
- 候选验证命令（供 `/plan` 与 `/do` 阶段执行）：

```powershell
Get-Command node
Get-Command npm
```

预期：命令存在并返回路径。

```powershell
Set-Location frontend
npm run build
```

预期：前端构建成功，无编译错误。

```powershell
Set-Location backend
..\.venv\Scripts\python.exe app.py
```

预期：后端启动成功，`/api/dashboard/stats` 与 `/api/dashboard/recent-activities` 可返回数据。

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

预期：前端启动成功，可在浏览器手工验收新增模块展示与交互。

- 如果缺少依赖导致构建/启动失败，以下命令标记为“用户执行并粘贴输出”：

```powershell
Set-Location frontend
npm install
```

预期：依赖安装完成后，重新执行构建和运行命令。

- 手工验收要点：
  - 计费日切换与刷新是否正常。
  - 核心双 KPI 是否正常渲染。
  - 新增模块是否均有真实内容且层级清晰。
  - 异常/空态文案是否可见。

## 8. Risks & Rollback
### Risks
- 新增模块过多导致再次拥挤，信息层级混乱。
- 指标字段映射错误，造成展示误导。
- 最近活动或洞察模块在空数据时出现布局塌陷。

### Rollback Strategy
- 回退 `frontend/src/views/Dashboard.vue` 到当前核心版（仅头部 + 双 KPI + 扩展区）。
- 若分阶段提交，按模块粒度回退（先回退最近活动，再回退洞察，再回退总览），保留核心能力不受影响。

## 9. Open Questions
- None

## 10. References
- `frontend/src/views/Dashboard.vue`
- `backend/routes/dashboard.py`
- `frontend/src/api/index.js`
- `frontend/src/utils/dayType.js`
- `plans/2026-03-04-dashboard-ui-refactor.md`
- `specs/2026-03-04-dashboard-ui-refactor.md`

---

## /spec Completion Checklist (self-check)
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable (not vague)
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
