# 正在计时页面复用交易记录计时消费窗口（可执行规格）

### 1. Summary
- 将 `frontend/src/views/ActiveTimers.vue` 中“新增消费 -> 开始计时”弹窗，改为与 `frontend/src/views/Transactions.vue` 的“消费弹窗第 3 模式（计时消费）”一致的窗口形态与交互逻辑。
- 该改动用于消除同一业务（启动计时消费）在两个页面的重复实现与体验差异，降低后续维护和回归成本。

### 2. Goals / Non-goals
- Goals
  - 统一“计时消费启动”窗口的字段结构、默认值、校验规则、按钮行为和提示文案。
  - 保证两处提交都使用同一业务语义：创建 active timer，接口契约保持一致。
  - 将重复逻辑收敛到可复用实现（优先组件复用），避免后续两处改一处漏一处。
  - 保持“正在计时页”主流程可用：列表刷新、后续暂停/继续/结算流程不受影响。
  - 保持键盘与遮罩关闭行为可用（ESC、点击遮罩关闭、按钮关闭）。
- Non-goals
  - 不修改后端 API、数据库模型与业务规则（例如 `/active-timers` 语义不变）。
  - 不将“交易记录页”的手动消费/自动结算模式迁移到“正在计时页”。
  - 不新增依赖，不修改 `package.json`、lock 文件。
  - 不重做“正在计时页”整体视觉，仅针对“新增消费”弹窗对齐。

### 3. Current State & Constraints
- Current state
  - `frontend/src/views/ActiveTimers.vue` 已有独立“开始计时”弹窗（`showAddModal`、`addForm`、`startTimer`）。
  - `frontend/src/views/Transactions.vue` 的消费弹窗包含三种模式，其中第 3 种为“计时消费”（`timerConsumeForm`、`submitTimerConsume`）。
  - 两处最终都调用 `POST /active-timers`，并在 `notes` 中传递 `note + packagePlan + materials` 的 JSON 结构，业务本质一致。
  - 当前属于“同逻辑多处实现”，存在 UI 与校验策略长期漂移风险。
- Constraints
  - 环境约束：Windows + PowerShell。
  - 技术栈约束：Vue 3 + Vite + Tailwind，优先在现有栈内实现。
  - 风险约束：禁止自动安装依赖；未经批准不改依赖声明/锁文件。
  - 流程约束：`/spec` 阶段仅输出文档，不改源码。

### 4. Requirements
- Functional requirements
  - P0
    - 点击“正在计时”页面的“新增消费”后，弹出与“交易记录 -> 消费 -> 计时消费模式”同构的表单窗口（字段顺序、类型、默认值一致）。
    - 表单字段至少包含：客户、计时类型、套餐方案、大图数量、超量小图、超量大图、备注、底部提示区。
    - 计时类型切换时，套餐方案默认值行为与交易记录页保持一致。
    - 校验规则一致：客户必选、计时类型必选、套餐方案必选，素材数量为非负数。
    - 提交行为一致：构造同结构 `notes` JSON 并请求 `POST /active-timers`。
    - 成功后关闭窗口并刷新“正在计时”列表；失败时给出可见错误反馈。
  - P1
    - 复用实现应支持在两个页面复用（优先抽离组件，避免模板/校验双份维护）。
    - 保持可访问性：焦点可见、ESC 可关闭、禁用态按钮样式明确。
  - P2
    - 对齐文案与微交互细节（提示语、按钮文案、间距），减少页面间认知切换成本。
- Non-functional requirements
  - 可维护性：计时消费弹窗核心逻辑单点维护，不再出现两套独立逻辑分叉。
  - 稳定性：不影响已有计时列表、编辑、结算、暂停/继续等功能路径。
  - 一致性：同业务在不同入口的行为和反馈一致。
- Compatibility / migration requirements
  - 保持现有路由、API 参数、返回处理方式兼容。
  - 不涉及数据迁移，不改变历史计时记录结构。

### 5. Design
- Overall approach
  - 以“复用优先”方式落地：把计时消费表单提炼为可复用的弹窗内容（组件或明确复用片段），由“交易记录页”和“正在计时页”共同使用。
  - “正在计时页”点击新增消费时，直接打开该复用窗口并执行启动计时流程。
  - 提交后统一走 `POST /active-timers`，并由页面上下文决定刷新行为（刷新交易数据或计时列表）。
- Key decisions
  - 决策 1：不改后端接口，前端对齐窗口与表单流程。
  - 决策 2：优先抽离复用组件（建议路径：`frontend/src/components/timers/TimerConsumeDialog.vue`），避免复制粘贴。
  - 决策 3：保持当前业务规则不变，仅做“入口 UI 与交互统一”。
- Alternatives and trade-offs
  - 方案 A（推荐）：抽离复用组件 + 两页接入。
    - 优点：单点维护、长期成本低、行为一致性最高。
    - 缺点：改动面稍大，需要同时调整两个页面绑定。
  - 方案 B：仅把交易记录页第 3 模式模板复制到正在计时页。
    - 优点：实现快、短期改动集中在一个页面。
    - 缺点：继续保留双份逻辑，后续演进仍易漂移。
- Impact scope
  - 主要影响：`frontend/src/views/ActiveTimers.vue`
  - 关联影响：`frontend/src/views/Transactions.vue`
  - 可能新增：`frontend/src/components/timers/TimerConsumeDialog.vue`
  - 可选抽离：`frontend/src/utils/` 下计时消费表单相关复用函数（如校验与 payload 构造）

### 6. Acceptance Criteria
- AC1：在 `/active-timers` 点击“新增消费”后，弹窗字段和布局与 `/transactions` 中“消费 -> 计时消费模式”一致。
- AC2：两处“计时消费”在默认值与联动规则上一致（含计时类型切换导致的套餐默认值变化）。
- AC3：两处校验规则一致，且错误提示在相同场景触发。
- AC4：两处提交时请求同一接口 `POST /active-timers`，并发送同结构 `notes` JSON（含 `note`、`packagePlan`、`materials`）。
- AC5：`/active-timers` 提交成功后弹窗关闭且计时列表立即刷新；失败时显示错误反馈，且不会错误关闭弹窗。
- AC6：按 `ESC`、点击遮罩、点击取消按钮可关闭该弹窗，且不影响其他弹窗流程。
- AC7：原“正在计时”页的编辑、暂停/继续、结算功能回归通过。
- AC8：前端构建通过，控制台无新增未处理异常（网络错误除外，但需有可见反馈）。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 工具存在性检查
    ```powershell
    Get-Command node
    Get-Command npm
    ```
    预期：返回可执行路径。
  - 前端构建验证
    ```powershell
    Set-Location frontend
    npm run build
    ```
    预期：Vite 构建成功，无编译错误。
  - 本地联调验证
    ```powershell
    Set-Location backend
    ..\.venv\Scripts\python.exe app.py
    ```
    预期：后端可正常提供 `/active-timers` 相关 API。
    ```powershell
    Set-Location frontend
    npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：可在 `/active-timers` 与 `/transactions` 手动完成 AC1-AC7 验收。
- 用户执行并粘贴输出（仅在依赖缺失时）
  - 下列命令会安装依赖，需用户手动执行并提供输出：
    ```powershell
    Set-Location frontend
    npm install
    ```

### 8. Risks & Rollback
- Risks
  - 复用改造可能导致两页某一处状态绑定丢失（如默认值或错误状态不同步）。
  - 抽离组件后若事件契约定义不清，可能引入提交后未刷新或关闭时机错误。
  - 弹窗关闭/焦点处理在多弹窗场景下可能出现回退异常。
- Rollback
  - 以 `frontend/src/views/ActiveTimers.vue` 和（如涉及）`frontend/src/views/Transactions.vue` 为回滚单元，按文件回退到改造前版本。
  - 若仅局部异常，可先回退复用接入层，保留原业务 API 调用路径，确保生产流程恢复。

### 9. Open Questions
- None（默认按“窗口字段、布局、交互、校验完全对齐交易记录页第 3 模式”执行）

### 10. References
- `frontend/src/views/ActiveTimers.vue`
- `frontend/src/views/Transactions.vue`
- `frontend/src/api/index.js`
- `backend/routes/active_timers.py`

## /spec Completion Checklist
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable (not vague claims)
- [x] Validation strategy lists candidates and marks user-run install commands
- [x] Risks and rollback are clearly defined
