# 交易记录新增经营视角支出功能可执行规格

### 1. Summary
- 在交易记录模块新增“支出”录入能力，用于登记系统使用者视角下的真实经营支出，录入字段仅包含金额和备注。
- 当前系统只有“充值/消费/买豆支出”三类交易，其中“消费”从门店经营视角属于收入，无法表达房租、水电、耗材采购等真实现金流出，导致账目口径不完整。

### 2. Goals / Non-goals
- Goals
  - 在交易记录页面新增独立“支出”录入入口，与“消费”明确区分。
  - 支出记录仅要求输入金额和备注，不要求选择客户。
  - 支出记录在交易列表、详情、筛选、统计口径中可被识别为真实支出。
  - 支出记录可取消，取消后按真实支出语义回滚。
  - 保持现有充值、消费、买豆支出逻辑不回归。
- Non-goals
  - 不把“支出”并入现有“消费”流程或复用消费者视角文案。
  - 不新增复杂分类、审批流、附件上传、报销流程。
  - 不改会员余额、客户消费、活动赠送规则。
  - 不在本期引入新的财务报表模块或多维会计科目。

### 3. Current State & Constraints
- Current state
  - 后端交易入口集中在 [transactions.py](C:\Users\PC\Desktop\codde\backend\routes\transactions.py)，当前显式支持 `recharge`、`consumption`、`bead_purchase`。
  - 前端交易记录页集中在 [Transactions.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Transactions.vue)，当前筛选项仅有“充值/消费/买豆支出”，弹窗仅有充值和消费。
  - 交易模型定义在 [models.py](C:\Users\PC\Desktop\codde\backend\models\models.py)，`transactions.customer_id` 为必填字段，意味着新“支出”若不绑定客户，需要明确建模方案。
  - 现有取消交易逻辑已区分普通删除与软取消，`bead_purchase` 走软取消；充值/消费走余额与库存回滚。
- Environment/platform constraints
  - Windows + PowerShell。
  - 前端 Vue 3 + Vite，后端 Flask + SQLAlchemy + SQLite。
- Risk constraints
  - `/spec` 阶段仅允许修改 `specs/`。
  - 不自动安装或恢复依赖，不修改依赖声明文件。
  - 新功能不能与现有“消费=收入”口径混淆，文案和类型命名必须清晰。

### 4. Requirements
- Functional requirements
  - P0
    - 新增独立交易类型 `expense`，语义定义为“系统使用者视角的真实支出”。
    - 交易记录页面提供“新增支出”入口，表单字段仅包含：
      - `amount`：支出金额，必填，`> 0`
      - `description`：备注，必填，非空
    - 新增后端创建支出接口，建议为 `POST /api/transactions/expense`。
    - 支出记录不要求选择客户，前后端需有一致的数据归属方案。
    - 支出记录在交易列表中可展示，且交易类型文案明确为“支出”。
    - 交易筛选类型中新增“支出”选项。
    - 支出记录详情弹窗能展示金额、备注、时间、操作人、状态。
    - 支出记录支持取消；取消后不应影响会员余额，不应触发消费库存逻辑。
    - 取消支出后需记录日志，且列表状态与展示口径一致。
  - P1
    - 交易首页 KPI、后续统计接口若区分收入/支出，应为 `expense` 预留明确口径。
    - 支出记录在移动端卡片视图与桌面表格视图中均有清晰类型标识。
    - 支出创建成功后有正向反馈，并刷新交易列表。
  - P2
    - 支出弹窗视觉结构与现有充值/消费弹窗风格一致，但字段更简洁。
- Non-functional requirements
  - 数据正确性：金额必须为有效正数；备注去除纯空白；后端兜底校验不能仅依赖前端。
  - 语义清晰：文案必须把“消费”与“支出”区分开，避免把经营收入误登记为支出。
  - 可维护性：新增类型时，交易类型映射、筛选、详情、取消逻辑采用集中扩展方式，避免散落条件分支失控。
  - 兼容性：现有 `recharge`、`consumption`、`bead_purchase` 数据与页面行为不应改变。
  - 可审计性：支出创建/取消需写日志，日志描述应包含金额与备注摘要。
- Compatibility / migration requirements
  - 由于 `transactions.customer_id` 当前为非空，必须明确兼容方案。推荐两种候选：
    - 方案 A：为经营视角支出引入固定系统客户 ID（类似 `C000`），专用于非客户交易。
    - 方案 B：调整交易模型，允许 `expense` 的 `customer_id` 为空，并同步修正查询与序列化逻辑。
  - 本期推荐优先评估方案 A，以降低数据库结构变更和兼容风险；若采用方案 B，必须补充迁移与旧数据兼容设计。

### 5. Design
- Overall approach
  - 后端
    - 在交易路由中新增 `expense` 创建逻辑。
    - 在交易取消逻辑中新增 `expense` 分支：仅做状态/记录回滚，不涉及余额和库存。
    - 在交易类型映射、日志记录、列表查询中纳入 `expense`。
  - 前端
    - 在交易记录页新增“支出”按钮与弹窗。
    - 在类型筛选、类型标签、详情展示中增加 `expense`。
    - 提交成功后刷新列表，并保持与现有充值/消费交互一致。
  - 数据建模
    - 若采用固定系统客户方案，则新增或复用一个系统占位客户标识，专门承载非客户交易。
    - 若采用可空客户方案，则对列表、详情、日志、筛选逻辑补齐“无客户”兼容。
- Key decisions
  - 决策 1：支出必须是独立交易类型 `expense`，不能复用 `consumption`，否则业务语义长期混乱。
  - 决策 2：支出表单最小化，只保留金额和备注，先满足录账需求，避免功能膨胀。
  - 决策 3：取消支出只回滚支出记录本身，不触达会员余额与库存模块。
  - 决策 4：优先采用“固定系统客户占位”方案，避免直接修改 `transactions.customer_id` 非空约束。
- Alternatives and trade-offs
  - 方案 A（推荐）：新增 `expense` 类型 + 固定系统客户占位 ID。
    - 优点：无需调整现有数据库字段约束，落地快，兼容风险低。
    - 缺点：数据层仍存在“伪客户”承载非客户交易，需要在展示层特殊处理。
  - 方案 B：新增 `expense` 类型 + `customer_id` 改为可空。
    - 优点：模型语义更干净，真实表达“无客户支出”。
    - 缺点：需要结构迁移，并影响所有依赖 `customer_id` 非空的旧逻辑。
  - 方案 C：把“支出”记成负数消费。
    - 优点：实现最省。
    - 缺点：语义错误，统计与列表都会混乱，不可接受。
- Impact scope
  - 前端
    - [Transactions.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Transactions.vue)
    - [index.js](C:\Users\PC\Desktop\codde\frontend\src\api\index.js)
  - 后端
    - [transactions.py](C:\Users\PC\Desktop\codde\backend\routes\transactions.py)
    - [models.py](C:\Users\PC\Desktop\codde\backend\models\models.py)
    - [logs.py](C:\Users\PC\Desktop\codde\backend\routes\logs.py)（如需支持日志回滚或展示）
  - 相关统计
    - [dashboard.py](C:\Users\PC\Desktop\codde\backend\routes\dashboard.py)（若首页统计要纳入真实支出）

### 6. Acceptance Criteria
- AC1：交易记录页面出现“新增支出”入口，点击可打开支出弹窗。
- AC2：支出弹窗只显示金额和备注两个必填字段，不显示客户选择。
- AC3：输入合法金额和备注后可成功创建支出记录。
- AC4：交易列表类型筛选新增“支出”，且能筛出 `expense` 记录。
- AC5：支出记录在列表中显示为“支出”，金额展示口径与充值/消费可清晰区分。
- AC6：查看支出详情时，可见金额、备注、时间、操作人、状态。
- AC7：取消支出后，不影响任何客户余额，不触发杂项库存/豆仓库存回滚。
- AC8：取消支出后，记录状态或展示结果符合系统既有取消策略，且日志已写入。
- AC9：现有充值、消费、买豆支出流程回归正常。
- AC10：前端构建通过，后端相关文件语法检查通过。

### 7. Validation Strategy
- Candidate validation commands
  - 工具存在性检查
    ```powershell
    Get-Command node
    Get-Command npm
    Get-Command python
    ```
    预期：能返回有效可执行路径。
  - 后端语法检查
    ```powershell
    python -m py_compile backend\routes\transactions.py backend\routes\logs.py backend\models\models.py
    ```
    预期：无输出，退出码为 0。
  - 前端构建检查
    ```powershell
    cd frontend
    npm run build
    ```
    预期：Vite 构建成功，无编译错误。
  - 手工验证
    ```powershell
    cd backend
    ..\.venv\Scripts\python.exe app.py
    ```
    ```powershell
    cd frontend
    npm run dev
    ```
    预期：可按 AC1-AC9 完成录入、筛选、详情、取消回归验证。
- User-run with pasted output
  - 若本地缺前端或后端依赖，仅允许用户执行：
    ```powershell
    cd frontend
    npm install
    ```
    ```powershell
    cd backend
    ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
    ```

### 8. Risks & Rollback
- Risks
  - `customer_id` 非空约束若处理不当，会导致 `expense` 无法入库或查询异常。
  - 前端若仍沿用“消费”相关文案，用户容易误录账。
  - 取消逻辑若误入消费分支，可能错误回滚余额或库存。
  - 首页统计若未区分 `expense`，后续可能继续把真实支出遗漏在经营口径外。
- Rollback
  - 前端：移除“新增支出”按钮、弹窗、筛选项和类型映射。
  - 后端：移除 `expense` 路由和分支逻辑；若采用固定系统客户方案，保留占位客户不会影响现有业务。
  - 数据：已录入的 `expense` 记录可通过软取消处理，不要求物理删除。

### 9. Open Questions
- 是否需要把 `expense` 纳入首页经营统计，并与“消费收入”做净额对比？本规格默认“预留口径，但不强制本期首页展示”。
- 若采用固定系统客户占位方案，占位客户 ID 是否复用 `C000`，还是新增专用 ID（推荐新增专用 ID，避免与买豆支出语义混用）？

### 10. References
- [transactions.py](C:\Users\PC\Desktop\codde\backend\routes\transactions.py)
- [models.py](C:\Users\PC\Desktop\codde\backend\models\models.py)
- [Transactions.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Transactions.vue)
- [logs.py](C:\Users\PC\Desktop\codde\backend\routes\logs.py)
- [dashboard.py](C:\Users\PC\Desktop\codde\backend\routes\dashboard.py)

## /spec Completion Checklist (self-check)
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
