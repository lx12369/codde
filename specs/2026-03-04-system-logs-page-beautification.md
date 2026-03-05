# 系统日志页面美化（/system-logs）可执行规格

### 1. Summary
- 在不改动后端日志接口与依赖的前提下，重构并美化 `frontend/src/views/SystemLogs.vue` 的信息架构与视觉层级，提升日志检索、阅读与分页浏览效率。
- 系统日志属于高频排障入口，当前界面可用但层次偏平、状态反馈不足，会增加定位问题时的认知成本。

### 2. Goals / Non-goals
- Goals
  - 将页面结构重组为“头部总览 + 筛选区 + 日志列表区 + 分页区”，让用户快速识别主流程。
  - 提升筛选体验（模块、操作、操作员、关键字）与结果反馈一致性。
  - 提升表格可读性：时间、模块、操作、类型、描述、操作员信息层级更清晰。
  - 统一加载、空态、失败反馈，避免仅依赖控制台错误。
  - 优化 375px 小屏与 >=1280px 大屏的布局稳定性和可读性。
  - 保持现有接口契约不变：`/logs`（分页与筛选参数保持兼容）。
- Non-goals
  - 不修改后端日志写入规则、日志模型、日志映射字典或数据库结构。
  - 不新增第三方依赖，不修改 `package.json`、lock 文件或 Python 依赖文件。
  - 不改造非系统日志页面（如 `Settings.vue`、`Transactions.vue`、`Activities.vue`）。
  - 不在本需求内新增日志导出、批量删除、日志详情后端接口。

### 3. Current State & Constraints
- Current state
  - 路由入口为 `/system-logs`，定义于 `frontend/src/router/index.js`。
  - 页面实现集中在 `frontend/src/views/SystemLogs.vue`，含筛选、分页、日志表格、刷新行为。
  - 当前日志查询接口为 `GET /logs`，支持 `page`、`page_size`、`module`、`action`、`operator`、`keyword`，后端位于 `backend/routes/logs.py`。
  - 页面目前缺少统一错误提示层；请求失败仅清空列表并输出控制台错误。
  - 桌面端以宽表格为主（`min-w-[980px]`），移动端体验有改进空间。
- Constraints
  - 环境约束：Windows + PowerShell。
  - 技术约束：Vue 3 + Vite + Tailwind，优先复用现有后台视觉语言。
  - 风险约束：禁止自动安装依赖；未经批准不得修改依赖声明/锁文件。
  - 实施约束：`/spec` 阶段仅产出文档，不改源码。

### 4. Requirements
- Functional requirements
  - P0
    - 重构页面头部为“页面标题 + 更新时间 + 刷新主操作 + 关键指标（可选）”的清晰层级。
    - 保持四项筛选字段（模块/操作/操作员/关键字）及“重置/查询”行为不变，优化控件布局和可读性。
    - 保持日志列表核心字段与排序语义不变（时间倒序）。
    - 统一页面状态反馈：加载中、空数据、请求失败、刷新成功（至少覆盖前三种）。
    - 保持分页能力（上一页/下一页/页码/每页条数）与现有行为一致。
  - P1
    - 增强模块与操作标签视觉语义，提升不同日志类型的扫描效率。
    - 优化列表区密度与表头层级（可含 sticky header 或分区标题强化）。
    - 优化移动端展示策略（允许卡片化降级或保留横向滚动但增强可读提示）。
    - 增加“当前显示范围/总记录数”的可见反馈一致性。
  - P2
    - 增加轻量过渡动效（筛选区/反馈条/列表行 hover）提升交互感知，不影响性能。
- Non-functional requirements
  - 可访问性：交互控件焦点可见，按钮禁用态可辨识，文字对比可读。
  - 性能：不新增后端请求次数；筛选仍基于单次接口请求。
  - 可维护性：减少分散样式堆叠，提升模板结构清晰度。
  - 一致性：视觉风格与后台其余页面（如数据管理/活动管理）保持统一方向。
- Compatibility / migration requirements
  - 保持前后端字段映射兼容（`type_label`、`module_label`、`action_label`、`timestamp` 等）。
  - 保持 `/logs` 返回结构兼容：`items`、`pagination`、`filters`。
  - 不引入数据迁移，不改变日志 ID、分页语义和筛选参数名称。

### 5. Design
- Overall approach
  - 采用“日志控制台”布局：顶部信息与刷新入口前置，筛选区独立卡片化，日志区强调可扫描性，分页区固定在列表底部。
  - 列表保持桌面端表格为主；小屏允许卡片降级或优化横向滚动提示，保证关键字段可读。
  - 增加统一反馈层（消息条/提示区）承接请求失败与刷新结果，替代沉默失败。
- Key decisions
  - 决策 1：不改后端接口，前端仅做展示层和交互层优化，降低联调风险。
  - 决策 2：沿用单文件改造路径（`SystemLogs.vue`）控制改动范围。
  - 决策 3：分页与筛选语义保持不变，避免行为回归。
- Alternatives and trade-offs
  - 方案 A（推荐）：在 `SystemLogs.vue` 内完成结构重排和样式升级。
    - 优点：交付快、影响面小、回归路径明确。
    - 缺点：单文件继续增长，长期维护性一般。
  - 方案 B：拆分为 `LogsHeader`、`LogsFilters`、`LogsTable`、`LogsPagination` 子组件。
    - 优点：职责更清晰、后续复用更好。
    - 缺点：短期改动面更大，联调与回归成本更高。
- Impact scope
  - 主要影响：`frontend/src/views/SystemLogs.vue`
  - 关联参考：`frontend/src/router/index.js`、`backend/routes/logs.py`、`frontend/src/utils/dateTime.js`

### 6. Acceptance Criteria
- AC1：访问 `/system-logs` 后，页面可清晰识别头部、筛选区、日志区、分页区。
- AC2：四个筛选字段可正常输入/选择，点击“查询/重置”后列表结果符合预期。
- AC3：刷新按钮可用，刷新后“最后更新时间”更新且列表数据正确。
- AC4：日志列表字段完整显示（时间、模块、操作、类型、描述、操作员）。
- AC5：模块与操作标签具有清晰可区分的视觉语义，不同类型可快速识别。
- AC6：加载中、空数据、请求失败三种状态均有可见反馈，不仅依赖控制台日志。
- AC7：分页操作（上一页/下一页/页码/每页条数）均可用，显示范围与总条数计算正确。
- AC8：当筛选后总页数变化导致当前页超界时，页面能回退到有效页并正确加载数据。
- AC9：375px 下无严重布局错位，核心字段可读可操作；>=1280px 下表格密度适中。
- AC10：刷新、筛选、分页流程中无新增未处理异常（网络失败除外，需有可见提示）。
- AC11：前端构建通过，无编译错误。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 工具检查
    ```powershell
    Get-Command node
    Get-Command npm
    Get-Command python
    ```
    预期：返回可执行路径，可运行前后端命令。
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
    预期：后端服务启动，可响应 `/api/logs`。
    ```powershell
    Set-Location frontend
    npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：可访问 `/system-logs` 并完成 AC1-AC10 手工验收。
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
  - 表格结构重排可能导致列宽与文本截断行为回归。
  - 分页区样式重构可能引入边界页禁用态异常。
  - 移动端降级策略选择不当会影响日志可读性。
- Rollback
  - 以 `frontend/src/views/SystemLogs.vue` 作为主回滚单元，必要时整文件回退到改造前版本。
  - 如局部回归，可分区回退（筛选区/表格区/分页区）并保留已验证稳定部分。

### 9. Open Questions
- 是否需要在本次改造中加入“时间范围”筛选 UI（后端已支持 `start_time/end_time` 参数）？
- 小屏更偏好“卡片化日志”还是“保留横向滚动表格 + 引导提示”？
- 是否需要加入“刷新成功”提示条，还是仅更新时间戳即可？

### 10. References
- `frontend/src/views/SystemLogs.vue`
- `frontend/src/router/index.js`
- `backend/routes/logs.py`
- `frontend/src/utils/dateTime.js`
