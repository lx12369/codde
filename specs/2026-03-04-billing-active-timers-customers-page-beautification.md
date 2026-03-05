# 计费规则、正在计时、客户管理页面联合美化（可执行规格）

### 1. Summary
- 在不改动后端接口与依赖的前提下，统一美化 `frontend/src/views/Billing.vue`、`frontend/src/views/ActiveTimers.vue`、`frontend/src/views/Customers.vue` 的信息架构与交互层级，提升高频运营流程的效率与可读性。
- 这三页分别承载“计费参数配置、计时过程管理、客户与交易入口”，当前风格和反馈机制存在不一致，增加跨页面操作的认知切换成本。

### 2. Goals / Non-goals
- Goals
  - 统一三页的页面骨架（头部总览、主操作区、内容区、反馈区），形成一致的后台视觉语言。
  - 提升表单可读性与操作安全感（主次按钮、禁用态、风险动作提示一致）。
  - 提升列表/卡片信息密度与层级，让关键字段可快速扫描。
  - 统一加载、空态、失败、成功反馈机制，减少分散 `alert`/`confirm` 体验。
  - 优化 375px 小屏与 >=1280px 大屏布局稳定性，避免横向溢出与按钮拥挤。
  - 保持现有接口契约不变，保证业务行为与数据语义不回归。
- Non-goals
  - 不修改后端业务规则、数据库结构或日志规则。
  - 不新增第三方依赖，不修改 `package.json`、lock 文件或 Python 依赖文件。
  - 不在本需求内新增导出、报表、权限系统等新业务能力。
  - 不改造以上三页之外的业务页面。

### 3. Current State & Constraints
- Current state
  - `Billing.vue`：
    - 接口契约：`GET /billing-rules`、`PUT /billing-rules`（`backend/routes/billing.py`）。
    - 页面以长表单分组呈现（限时套餐、工作日/周末、素材费用、加班费用），视觉层级较平。
  - `ActiveTimers.vue`：
    - 接口契约：`GET/POST /active-timers`、`PUT /active-timers/{id}`、`POST /active-timers/{id}/settle`、`DELETE /active-timers/{id}`（`backend/routes/active_timers.py`）。
    - 逻辑复杂（筛选、暂停/继续、编辑、结算、多弹窗），页面体量大，反馈机制仍混用 `alert/confirm`。
  - `Customers.vue`：
    - 接口契约：`GET/POST /customers`、`GET/PUT/DELETE /customers/{id}`、`GET /customers/{id}/balance`（`backend/routes/customers.py`）。
    - 同页包含客户 CRUD、详情、充值、消费、批量删除，弹窗密度高且交互风格不统一。
  - 导航入口：`/billing-rules`、`/active-timers`、`/customers`，定义于 `frontend/src/router/index.js` 和 `frontend/src/layouts/MainLayout.vue`。
- Constraints
  - 环境约束：Windows + PowerShell。
  - 技术约束：Vue 3 + Vite + Tailwind，优先在现有样式体系内改造。
  - 风险约束：禁止自动安装依赖；未经批准不得修改依赖声明/锁文件。
  - 流程约束：`/spec` 阶段仅产出文档，不改源码。

### 4. Requirements
- Functional requirements
  - P0（必须）
    - 三页统一“头部 + 主操作 + 内容区 + 状态反馈”结构。
    - 保持全部现有业务入口可用：
      - 计费规则加载/保存；
      - 计时新增、编辑、暂停/继续、结算、结束；
      - 客户新增/编辑/删除、充值、消费、批量删除。
    - 统一失败反馈可见化（页面反馈条或同层提示），避免仅控制台报错。
    - 高风险动作（二次确认类）视觉语义明确，避免误触。
  - P1（应实现）
    - `Billing.vue`：增强分组可读性（分区标题、说明、字段行高和留白一致）。
    - `ActiveTimers.vue`：优化筛选区、计时卡片信息层级、弹窗主次按钮一致性。
    - `Customers.vue`：优化客户列表卡片/表格可读性与详情-充值-消费弹窗一致性。
    - 三页统一按钮尺寸、圆角、焦点态、禁用态，避免视觉割裂。
  - P2（可选增强）
    - 轻量过渡动效（区块入场、反馈条淡入、卡片 hover），不影响性能和可访问性。
- Non-functional requirements
  - 可访问性：键盘可达、焦点可见、文本与背景对比度清晰。
  - 性能：不新增额外后端请求；维持原有请求频次和分页/筛选策略。
  - 可维护性：减少重复样式与分散状态判断，提高模板结构清晰度。
  - 一致性：和已有后台页面（如数据管理、系统日志）保持统一视觉方向。
- Compatibility / migration requirements
  - 保持现有前后端字段映射和接口参数名不变（snake_case/camelCase 兼容逻辑不回归）。
  - 不进行数据迁移，不改变 ID 语义（例如客户 ID、计时 ID、活动/交易关联行为）。

### 5. Design
- Overall approach
  - 采用“统一后台工作台”设计策略：
    - 头部：页面定位 + 关键动作；
    - 主体：筛选/表单与数据展示分层；
    - 反馈：成功/失败/加载/空态统一表达。
  - 先统一样式和反馈层，再逐页修整信息架构，最后做响应式收口。
- Key decisions
  - 决策 1：仅前端页面重构，后端契约零改动，降低联调风险。
  - 决策 2：优先单文件内重构（对应三个页面文件），控制变更面。
  - 决策 3：先保业务一致性再做视觉增强，避免“好看但回归”。
- Alternatives and trade-offs
  - 方案 A（推荐）：在三页内完成结构重排与样式统一，不拆新组件。
    - 优点：交付快、改动集中、回归范围可控。
    - 缺点：文件体量继续偏大，长期复用性一般。
  - 方案 B：抽离通用组件（统一头部、反馈条、弹窗底栏、筛选控件）。
    - 优点：后续维护更优，风格统一更彻底。
    - 缺点：短期改动面更广，联调与回归成本更高。
- Impact scope
  - 主要影响：
    - `frontend/src/views/Billing.vue`
    - `frontend/src/views/ActiveTimers.vue`
    - `frontend/src/views/Customers.vue`
  - 关联参考：
    - `frontend/src/router/index.js`
    - `frontend/src/layouts/MainLayout.vue`
    - `backend/routes/billing.py`
    - `backend/routes/active_timers.py`
    - `backend/routes/customers.py`

### 6. Acceptance Criteria
- AC1：三个页面均具备清晰的“头部/内容/反馈”分层，视觉语言一致。
- AC2：`/billing-rules` 可正常加载与保存规则，保存成功后可见反馈且数据回写正确。
- AC3：`/billing-rules` 各分区（限时套餐/工作日周末/素材费用/加班费用）可读性明显提升，字段无丢失。
- AC4：`/active-timers` 的筛选、列表、暂停/继续、结算、结束流程全部可用且无行为回归。
- AC5：`/active-timers` 弹窗（新增/编辑/结算）主次操作统一，提交中禁用态明确。
- AC6：`/customers` 的客户查询、详情、新增、编辑、删除、批量删除流程可用。
- AC7：`/customers` 充值与消费流程可用，余额相关提示与错误提示可见。
- AC8：三页加载中、空数据、请求失败场景均有可见反馈，不仅依赖 `alert` 或控制台。
- AC9：高风险操作（删除、结束计时、批量删除等）保留二次确认且视觉语义明确。
- AC10：375px 下三页关键操作按钮可见可点，无遮挡/严重溢出；>=1280px 下布局不拥挤。
- AC11：三页中文文案可读、无乱码、术语一致。
- AC12：前端构建通过，关键流程下无新增未处理异常（网络失败除外，需有可见反馈）。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 工具检查
    ```powershell
    Get-Command node
    Get-Command npm
    Get-Command python
    ```
    预期：返回可执行路径。
  - 前端构建验证
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
    预期：后端成功启动，可响应三页相关 API。
    ```powershell
    Set-Location frontend
    npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：可访问 `/billing-rules`、`/active-timers`、`/customers` 并按 AC1-AC12 手工验收。
- 用户执行并粘贴输出（依赖缺失时）
  - 以下命令会安装依赖，需用户执行并粘贴输出日志：
    ```powershell
    Set-Location frontend
    npm install
    ```
    ```powershell
    Set-Location backend
    ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
    ```

### 8. Risks & Rollback
- Risks
  - `ActiveTimers.vue` 与 `Customers.vue` 逻辑复杂，重构样式时可能触发表单联动回归。
  - 统一反馈机制过程中可能遗漏边缘分支，导致个别失败场景仍无提示。
  - 响应式改造可能导致小屏局部溢出或弹窗操作遮挡。
- Rollback
  - 以页面为回滚单元：
    - `frontend/src/views/Billing.vue`
    - `frontend/src/views/ActiveTimers.vue`
    - `frontend/src/views/Customers.vue`
  - 若仅局部回归，可分区回退（头部/筛选区/列表区/弹窗区），保留已验证稳定部分。

### 9. Open Questions
- 是否要求三页头部统一采用与“数据管理”一致的 Hero 风格，还是仅统一组件层级和间距即可？
- 客户管理页在移动端是否允许从“网格卡片”降级为“单列列表”以优先可读性？
- 计时页与客户页中的确认框，是否要求全部替换为自定义风险弹窗（完全移除原生 `confirm`）？

### 10. References
- `frontend/src/views/Billing.vue`
- `frontend/src/views/ActiveTimers.vue`
- `frontend/src/views/Customers.vue`
- `frontend/src/router/index.js`
- `frontend/src/layouts/MainLayout.vue`
- `backend/routes/billing.py`
- `backend/routes/active_timers.py`
- `backend/routes/customers.py`
