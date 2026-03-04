# 活动管理页面美化（/activities）可执行规格

### 1. Summary
- 在不改动后端活动接口与依赖的前提下，重构并美化 `frontend/src/views/Activities.vue` 的信息架构与视觉层级，提升活动查看、维护与风险操作的效率。
- 该页面是运营活动创建与维护入口，当前交互反馈分散、状态表达粗粒度，易增加管理员判读成本与误操作风险。

### 2. Goals / Non-goals
- Goals
  - 将页面结构明确为“页面头部 + 状态总览 + 筛选区 + 活动卡片区 + 弹窗工作流”，降低首次理解成本。
  - 提升活动状态可读性：区分“进行中 / 即将开始 / 已结束 / 已停用”并提供一致视觉标签。
  - 保持创建、编辑、删除活动主流程完整，且提交后列表刷新及时、反馈明确。
  - 统一加载、空态、成功、失败反馈风格，减少分散式 `alert` 带来的体验割裂。
  - 优化移动端（375px）与桌面端（>=1280px）布局稳定性，避免横向溢出与按钮拥挤。
  - 保持现有 API 契约不变：`/activities`、`/activities/{id}`。
- Non-goals
  - 不修改后端活动业务规则、ID 生成逻辑、日志记录逻辑或数据库结构。
  - 不新增第三方依赖，不修改 `package.json`、lock 文件或 Python 依赖文件。
  - 不改动非活动页面业务逻辑（如 `Transactions.vue`、`Settings.vue`、`ActiveTimers.vue`）。
  - 不在本需求内新增活动效果统计报表或跨页面联动功能。

### 3. Current State & Constraints
- Current state
  - 路由入口为 `/activities`，定义于 `frontend/src/router/index.js`；导航项“活动管理”位于 `frontend/src/layouts/MainLayout.vue`。
  - 页面实现集中在 `frontend/src/views/Activities.vue`：同文件内完成数据拉取、表单校验、创建/编辑/删除、弹窗展示。
  - 列表当前以卡片网格展示，缺少筛选/检索层；状态仅区分 `active` 与 `inactive`。
  - 错误反馈当前仍使用浏览器 `alert`，删除确认已使用自定义弹窗，反馈机制不统一。
  - 接口调用契约来自 `backend/routes/activities.py`，兼容 snake_case 与 camelCase 字段映射。
- Constraints
  - 环境约束：Windows + PowerShell。
  - 技术约束：Vue 3 + Vite + Tailwind，优先在现有样式体系内完成美化。
  - 风险约束：禁止自动安装依赖；未经批准不得修改依赖声明/锁文件。
  - 实施约束：`/spec` 阶段仅产出文档，不改源码。

### 4. Requirements
- Functional requirements
  - P0
    - 重构页面信息层级：头部（标题+主操作）与内容区（总览/筛选/列表）分层明确。
    - 增加活动筛选能力（至少支持按状态筛选；可包含名称关键词检索）并即时刷新展示结果。
    - 活动卡片展示字段统一：名称、描述、门槛金额、赠送金额、活动时间、状态标签、操作按钮。
    - 状态表达升级：在 `status` 基础上结合时间区间给出“进行中/即将开始/已结束/已停用”可视标识。
    - 创建/编辑弹窗保留现有校验规则（名称必填、金额非负、开始日期不晚于结束日期），并统一错误提示样式。
    - 删除流程继续保留二次确认，并在执行中显示禁用态与处理中反馈。
    - 将失败/成功提示统一为页面内可视反馈（避免仅依赖原生 `alert`）。
  - P1
    - 增加页面总览指标（如活动总数、当前进行中数量、停用数量），使用已拉取数据本地计算。
    - 优化加载态与空态（骨架屏或占位态 + 指引文案）。
    - 优化移动端弹窗与表单布局（小屏单列、操作按钮可触达）。
    - 优化卡片操作区视觉主次，降低“编辑/删除”误触概率。
  - P2
    - 增加轻量过渡动画（卡片入场、按钮状态切换）提升交互感知，不影响可读性和性能。
- Non-functional requirements
  - 可访问性：键盘可达、焦点可见、禁用态可辨识。
  - 性能：不新增后端接口请求；列表过滤与统计优先前端本地计算。
  - 可维护性：模板结构与状态逻辑分层清晰，减少重复样式与分散状态判断。
  - 一致性：遵循现有后台视觉语言，不引入与主布局割裂的设计风格。
- Compatibility / migration requirements
  - 保持前后端字段映射兼容（`min_amount`/`minRechargeAmount`、`bonus_amount`/`bonusAmount` 等）。
  - 不进行数据迁移，不变更活动 ID（`A001`）语义和接口返回结构。

### 5. Design
- Overall approach
  - 采用“活动运营工作台”布局：顶部操作入口前置，中部筛选与总览并列，底部卡片列表承载详情与操作。
  - 活动状态采用“双维度判定”：基础状态（active/inactive）+ 时间窗口（未开始/进行中/已结束）形成最终展示标签。
  - 弹窗保持单入口复用（创建/编辑共用），通过模式状态切换标题、按钮文案和默认值。
  - 反馈机制采用统一消息区域或轻量通知组件，覆盖保存成功、删除成功、请求失败场景。
- Key decisions
  - 决策 1：不触碰后端接口，前端以布局与状态表达优化为主，降低联调风险。
  - 决策 2：统计指标基于已获取列表本地计算，避免新增 API 和额外请求开销。
  - 决策 3：优先在单文件内完成重构，控制改动范围与回归面。
- Alternatives and trade-offs
  - 方案 A（推荐）：在 `Activities.vue` 内完成美化与交互升级。
    - 优点：交付快、改动集中、回归路径明确。
    - 缺点：单文件规模增大，长期可维护性一般。
  - 方案 B：拆分为 `ActivitiesHeader`、`ActivitiesFilters`、`ActivityCard`、`ActivityFormDialog` 子组件。
    - 优点：职责清晰、复用性更好、后续测试更方便。
    - 缺点：本次改动面更大，联调和回归成本更高。
- Impact scope
  - 主要影响：`frontend/src/views/Activities.vue`
  - 关联参考：`frontend/src/router/index.js`、`frontend/src/layouts/MainLayout.vue`、`frontend/src/api/index.js`、`backend/routes/activities.py`

### 6. Acceptance Criteria
- AC1：访问 `/activities` 后，页面存在清晰的头部、总览区、筛选区、卡片区分层结构。
- AC2：活动列表支持状态筛选（最少 `all/active/inactive`），筛选结果与展示数量一致。
- AC3：每个活动卡片显示名称、门槛金额、赠送金额、时间区间、状态与操作按钮，字段无缺失。
- AC4：活动状态标签可区分“进行中 / 即将开始 / 已结束 / 已停用”中的至少 3 类，且与活动时间逻辑一致。
- AC5：创建活动表单校验生效，非法输入时给出可见错误提示且阻止提交。
- AC6：编辑活动后列表数据刷新并反映最新值，不需手动刷新页面。
- AC7：删除活动有二次确认，确认后删除成功并从列表移除；失败时有可见错误反馈。
- AC8：页面加载中、空数据、请求失败三种状态均有清晰反馈，不仅依赖浏览器原生弹窗。
- AC9：375px 宽度下页面无明显横向溢出，弹窗表单可完整操作；>=1280px 下卡片布局不拥挤。
- AC10：前端构建通过，活动页操作流程中浏览器控制台无新增未处理异常（网络失败场景除外，需有可见错误提示）。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 环境检查
    ```powershell
    Get-Command node
    Get-Command npm
    Get-Command python
    ```
    预期：返回可执行路径，说明可运行前后端启动/构建命令。
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
    预期：后端服务启动成功，可响应 `/api/activities`。
    ```powershell
    Set-Location frontend
    npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：可访问 `/activities` 并按 AC1-AC10 完成手工验收。
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
  - 状态标签从“两态”扩展到“时间态 + 开关态”时，可能出现边界时间判断偏差。
  - 反馈机制替换过程中可能遗漏异常分支，导致个别失败场景无提示。
  - 移动端弹窗布局调整可能引入局部滚动或遮挡问题。
- Rollback
  - 以 `frontend/src/views/Activities.vue` 作为主回滚单元，必要时整文件回退到改造前版本。
  - 若仅局部问题（筛选区/卡片区/弹窗区）回归，可按功能区块分步回退并重新执行构建与手工验收。

### 9. Open Questions
- 是否要求保留当前“卡片式活动列表”为主视图，还是允许切换为“表格 + 卡片”双视图？
- 筛选区是否必须包含关键词搜索，还是仅做状态筛选即可满足本次目标？
- 成功/失败反馈更偏好顶部全局消息条，还是右上角短暂 toast 形式？

### 10. References
- `frontend/src/views/Activities.vue`
- `frontend/src/router/index.js`
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/api/index.js`
- `backend/routes/activities.py`
