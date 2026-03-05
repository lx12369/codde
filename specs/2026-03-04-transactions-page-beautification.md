# 交易记录页面美化（/transactions）可执行规格

### 1. Summary
- 在不改动后端交易接口和依赖的前提下，重构并美化 `frontend/src/views/Transactions.vue` 的信息架构与交互层级，提升交易查询与录入效率。
- 该页面是“充值/消费/取消交易”的高频操作入口，当前界面密度高、反馈分散，会增加误操作和审阅成本。

### 2. Goals / Non-goals
- Goals
  - 将页面结构重组为“页面头部 + 筛选区 + 列表区 + 弹窗工作流”，让用户能快速理解主流程。
  - 提升筛选、分页、表格可读性，降低交易记录定位成本。
  - 保持充值/消费/详情弹窗功能完整，并优化视觉一致性与操作反馈。
  - 统一加载、空态、错误、成功反馈风格，减少突兀弹窗体验。
  - 优化移动端（375px）与桌面端（>=1280px）下的布局稳定性。
  - 保持现有路由与接口契约不变：`/transactions`、`/transactions/recharge`、`/transactions/consumption`、`/transactions/{id}/cancel`。
- Non-goals
  - 不修改后端交易业务规则、余额回滚逻辑、活动赠送策略。
  - 不新增第三方依赖，不修改 `package.json` 或 lock 文件。
  - 不改动非交易页面（如 `Customers.vue`、`ActiveTimers.vue`）业务逻辑。
  - 不在本需求内新增导出业务能力（仅处理既有入口的可用性与呈现）。

### 3. Current State & Constraints
- Current state
  - 路由入口：`/transactions`，定义于 `frontend/src/router/index.js`，导航项在 `frontend/src/layouts/MainLayout.vue`。
  - 页面实现集中在 `frontend/src/views/Transactions.vue`，单文件承载筛选、表格、分页、三类弹窗与复杂消费模式逻辑。
  - 当前交互以 `alert` / `window.confirm` 为主，缺少统一状态反馈层。
  - 列表查询依赖后端分页接口：`backend/routes/transactions.py@get_transactions`。
  - 充值、消费、取消交易依赖后端接口并直接影响客户余额，属于高风险操作链路。
- Constraints
  - 环境约束：Windows + PowerShell。
  - 技术约束：Vue 3 + Vite + Tailwind，优先在现有技术栈内优化。
  - 风险约束：禁止自动安装依赖；未经批准不得修改依赖声明/锁文件。
  - 实施约束：`/spec` 阶段仅产出文档，不改源码。

### 4. Requirements
- Functional requirements
  - P0
    - 重构页面视觉层级：头部操作区（充值/消费）与筛选区、列表区分层明确。
    - 提升筛选区可读性：字段分组清晰，筛选与重置按钮主次明确。
    - 提升表格可读性：金额、状态、类型标签对比明显，长文本截断与提示策略明确。
    - 统一状态反馈：加载中、无数据、提交成功、提交失败、取消交易反馈风格一致。
    - 保持三种消费模式（手动/自动/计时）完整可用，且模式切换后的字段状态清晰。
    - 保持取消交易流程高可见风险提示，避免误触。
  - P1
    - 优化分页交互密度与信息提示（当前显示区间、总记录数、跳页反馈）。
    - 优化弹窗结构（标题区、正文区、操作区一致化），确保多弹窗视觉风格统一。
    - 将 `handleExport` 入口调整为禁用态并给出“待实现”提示，避免误导用户。
    - 在移动端允许交易列表降级为卡片化展示（桌面端保留表格），提升小屏可读性。
  - P2
    - 增加轻量动画（区块入场、按钮状态切换）增强操作感知，不影响性能。
- Non-functional requirements
  - 可访问性：键盘可达、焦点可见、主要操作按钮具备清晰禁用态。
  - 性能：不新增高成本接口请求；保持现有分页查询模式。
  - 可维护性：减少模板重复样式堆叠，提升结构可读性。
  - 一致性：遵循现有后台视觉语言，不引入割裂风格。
- Compatibility / migration requirements
  - 保持现有前后端字段映射兼容（含 snake_case / camelCase 归一化逻辑）。
  - 不引入数据迁移，不更改交易记录 ID、状态语义及余额影响规则。

### 5. Design
- Overall approach
  - 采用“交易工作台”设计：主操作前置、筛选次级、结果列表核心、弹窗工作流闭环。
  - 对高风险动作（取消交易）使用更明确的危险语义和二次确认文案。
  - 对多模式消费表单采用分段式视觉组织，降低认知负担。
  - 将取消交易确认从浏览器 `confirm` 升级为统一风格的自定义风险弹窗。
- Key decisions
  - 决策 1：不拆后端逻辑，前端重构仅聚焦布局、反馈、交互细节。
  - 决策 2：维持单文件实现作为本次落地路径，降低改动面与联调风险。
  - 决策 3：优先统一反馈机制，替代分散 `alert`，提升一致性。
- Alternatives and trade-offs
  - 方案 A（推荐）：在 `Transactions.vue` 内集中完成重构与美化。
    - 优点：交付快、改动范围可控、接口联调成本低。
    - 缺点：文件体量继续偏大，长期维护压力仍在。
  - 方案 B：拆分为 `TransactionsFilter`、`TransactionsTable`、`TransactionDialogs` 子组件。
    - 优点：职责清晰、可测试性与可维护性更好。
    - 缺点：短期改动面更广，回归与联调周期增加。
- Impact scope
  - 主要影响：`frontend/src/views/Transactions.vue`
  - 关联参考：`frontend/src/api/index.js`、`backend/routes/transactions.py`、`frontend/src/layouts/MainLayout.vue`

### 6. Acceptance Criteria
- AC1：进入 `/transactions` 后，页面主结构清晰，操作区、筛选区、列表区层级明确。
- AC2：筛选（类型/日期/客户）可用，点击“筛选/重置”后列表更新符合预期。
- AC3：列表在加载中、空数据、有数据三种状态下均有明确且一致的视觉反馈。
- AC4：充值弹窗可正常打开、校验、提交；成功后列表和客户数据刷新。
- AC5：消费弹窗三种模式（手动/自动/计时）可切换并完成对应提交流程。
- AC6：交易详情弹窗信息字段完整且排版清晰（类型、金额、状态、时间、操作员等）。
- AC7：取消交易操作有明确风险提示和处理中状态，成功后列表刷新且余额回滚行为不变。
- AC8：375px 下页面无明显横向溢出，关键按钮可见可点；移动端可用卡片化列表替代表格；>=1280px 下布局不拥挤。
- AC9：页面中文文案一致且可读，无乱码。
- AC10：`导出` 按钮为禁用态并有“待实现”提示，不触发误导性操作。
- AC11：取消交易使用自定义风险弹窗（非浏览器原生 `confirm`），并保留二次确认语义。
- AC12：前端构建通过，关键流程下控制台无新增未处理异常（网络错误除外，需有可见反馈）。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 工具检查
    ```powershell
    Get-Command node
    Get-Command npm
    ```
    预期：返回可执行路径。
  - 构建验证
    ```powershell
    Set-Location frontend
    npm run build
    ```
    预期：Vite 构建成功，无编译错误。
  - 联调验证
    ```powershell
    Set-Location backend
    ..\.venv\Scripts\python.exe app.py
    ```
    预期：后端服务启动并可响应交易相关 API。
    ```powershell
    Set-Location frontend
    npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：可访问 `/transactions` 并完成 AC1-AC9 手工验收。
- 用户执行并粘贴输出（依赖缺失时）
  - 以下命令会安装依赖，需用户执行：
    ```powershell
    Set-Location frontend
    npm install
    ```

### 8. Risks & Rollback
- Risks
  - 单文件重构过程中，可能引入表单联动回归（例如消费模式切换后状态残留）。
  - 反馈机制替换 `alert` 时，可能遗漏个别异常分支。
  - 表格与弹窗同时美化可能导致移动端局部溢出。
- Rollback
  - 以 `frontend/src/views/Transactions.vue` 为主回滚单元，必要时整文件回退到改造前版本。
  - 若出现局部回归，可先回退对应区块（筛选区/表格区/弹窗区）并保留已验证稳定部分。

### 9. Open Questions
- None

### 10. References
- `frontend/src/views/Transactions.vue`
- `frontend/src/router/index.js`
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/api/index.js`
- `backend/routes/transactions.py`
