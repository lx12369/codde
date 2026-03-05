# 豆仓管理页面美化（/bead-inventory）可执行规格

### 1. Summary
- 在不改动豆仓业务接口与计算逻辑的前提下，重构并美化 `frontend/src/views/BeadInventory.vue`，使其视觉与信息层级对齐系统内已美化页面（如 `Settings`、`ActiveTimers`、`Dashboard`）。
- 豆仓页面承载高频库存操作（入库/损耗/盘点/台账查询），当前视觉一致性和可读性不足会放大误操作概率并影响管理效率。

### 2. Goals / Non-goals
- Goals
  - 页面整体视觉风格与系统现有风格统一：`page-hero` 顶部、卡片化分区、反馈条与状态色体系一致。
  - 明确分层信息架构：概览指标、低库存预警、豆料台账、库存操作区、流水查询区、批量设置弹窗。
  - 强化“选中豆料上下文”：让用户在入库/出库/盘点时始终清楚当前作用对象。
  - 提升表格可读性与操作可达性（桌面与移动端均可快速完成常用操作）。
  - 保持现有功能和接口行为不变，确保上线风险可控。
- Non-goals
  - 不修改后端接口、数据库模型、业务校验与计算规则。
  - 不新增第三方 UI 组件库或样式依赖。
  - 不重写页面为多文件组件拆分（本次优先在现有单文件内重构）。
  - 不扩展新业务功能（例如新增库存审批流、多仓库支持、角色细分权限）。

### 3. Current State & Constraints
- 当前状态
  - 页面文件：`frontend/src/views/BeadInventory.vue`，功能完整但风格偏“功能堆叠”，与近期已美化页面风格差异明显。
  - 页面已包含：概览卡片、预警区、豆料台账、入库/损耗/盘点表单、流水表格、多个弹窗。
  - 页面主要 API：`frontend/src/api/index.js` 中 `beadInventoryApi`（materials/alerts/ledger/inbound/outbound/stocktake/import-mard/batch-*）。
- 约束条件
  - 环境约束：Windows + PowerShell。
  - 工程约束：Vue 3 + Tailwind，优先复用现有页面样式语义（如 `page-hero`、反馈条、卡片动效）。
  - 风险约束：禁止自动安装/恢复依赖；未经用户批准，不改依赖文件。
  - 交付约束：`/spec` 阶段只改 `specs/`，不改任何源码。

### 4. Requirements
- Functional requirements
  - P0
    - 页面采用统一头部 Hero 区，包含标题、副标题与主操作按钮组。
    - 全局反馈区（成功/失败/提示）统一样式与位置，替换零散提示体验。
    - 豆料台账区提供更清晰的“当前选中行”视觉状态，避免误把操作作用到错误豆料。
    - 入库/损耗/盘点三卡片视觉语义区分明显（绿色/橙色/紫色），并与按钮状态一致。
    - 弹窗（新增/编辑豆料、单位换算、批量市场价）统一头部、表单间距、按钮层级与遮罩行为。
  - P1
    - 优化列表与表格在窄屏下的可读性（关键信息优先展示，避免密集难读）。
    - 增强预警区信息表达（预警数量、重点项突出、快速定位对应豆料）。
    - 指标卡增加状态说明（例如低库存/总库存）和一致动效。
  - P2
    - 增加轻量进入动画与悬停反馈，提升页面观感但不影响性能。
- Non-functional requirements
  - 可用性：关键操作按钮在 375px 宽度下可见、可点、无遮挡。
  - 可访问性：焦点可见、颜色对比可读、危险操作有清晰语义。
  - 性能：不新增额外后端请求；保持当前请求数量与时机基本不变。
  - 可维护性：样式命名语义化、避免重复的 Tailwind 大段堆叠。
- Compatibility / migration requirements
  - 接口参数与返回结构保持兼容：不改 `beadInventoryApi` 调用契约。
  - 旧数据无需迁移；页面美化后直接兼容既有数据与流程。

### 5. Design
- Overall approach
  - 采用“总览 -> 预警 -> 台账 -> 操作 -> 流水 -> 弹窗”的稳定信息流，并复用系统已落地的视觉语言：
    - 顶部 `page-hero` + 操作按钮组
    - 统一反馈条
    - 大卡片容器 + 子卡片模块
    - 危险/警告/成功状态色一致
- Key decisions
  - 决策 1：优先复用 `Settings.vue` 和 `ActiveTimers.vue` 已验证样式范式，降低设计分裂风险。
  - 决策 2：保持现有交互路径与表单字段，仅做布局与视觉重排。
  - 决策 3：把“选中豆料上下文”作为核心视觉锚点，贯穿表格行、操作卡片与流水筛选。
- Alternatives and trade-offs
  - 方案 A（推荐）：在 `BeadInventory.vue` 内完成样式与结构重构。
    - 优点：改动集中、联调简单、回滚成本低。
    - 缺点：单文件体量继续偏大。
  - 方案 B：拆分为多个子组件（概览/台账/操作/流水/弹窗）。
    - 优点：长期维护更好，职责清晰。
    - 缺点：本次改动面大，回归范围变广。
- Impact scope
  - 主要：`frontend/src/views/BeadInventory.vue`
  - 参考样式页：`frontend/src/views/Settings.vue`、`frontend/src/views/ActiveTimers.vue`、`frontend/src/views/Dashboard.vue`
  - 接口引用：`frontend/src/api/index.js`（`beadInventoryApi`）

### 6. Acceptance Criteria
- AC1：`/bead-inventory` 顶部改为与系统一致的 Hero 结构，标题与主要操作在首屏清晰可见。
- AC2：页面存在统一反馈条，入库/出库/盘点/保存失败等操作反馈风格一致。
- AC3：豆料台账行选中状态清晰可辨，且操作区明确显示当前选中豆料。
- AC4：三类库存操作卡（入库/损耗/盘点）颜色语义明显，提交按钮禁用态与加载态可区分。
- AC5：新增/编辑豆料、单位换算、批量市场价弹窗风格统一，按钮主次明确。
- AC6：在 375px 移动端与 >=1280px 桌面端均无关键控件遮挡或明显布局错乱。
- AC7：功能回归通过：导入 221 色、豆料新增编辑删除、入库/损耗/盘点、流水筛选分页均可正常执行。
- AC8：前端构建通过且无新增编译错误。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 环境检查
    ```powershell
    Get-Command node
    Get-Command npm
    ```
    预期：可找到命令路径。
  - 构建检查
    ```powershell
    cd frontend; npm run build
    ```
    预期：Vite 构建成功，无编译错误。
  - 本地联调（手工验收）
    ```powershell
    cd frontend; npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：页面可访问，按 AC1-AC7 完成手工核验。
- 需用户执行并粘贴输出的命令
  - 若依赖缺失导致构建失败，以下命令需用户确认后执行：
    ```powershell
    cd frontend; npm install
    ```

### 8. Risks & Rollback
- Risks
  - 大量样式重排可能误伤现有交互（例如表格点击选中、弹窗关闭行为）。
  - 视觉增强过度可能降低密集数据场景下的信息效率。
  - 移动端适配若处理不当，可能导致表格横向滚动体验退化。
- Rollback
  - 以 `frontend/src/views/BeadInventory.vue` 单文件回滚为主。
  - 若出现回归，优先回退视觉层改动，不回退已验证业务逻辑。

### 9. Open Questions
- None

### 10. References
- `frontend/src/views/BeadInventory.vue`
- `frontend/src/views/Settings.vue`
- `frontend/src/views/ActiveTimers.vue`
- `frontend/src/views/Dashboard.vue`
- `frontend/src/api/index.js`
- `specs/2026-03-04-data-management-page-beautification.md`

## /spec Completion Checklist (self-check)
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
