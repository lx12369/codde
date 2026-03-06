# /plan：交易记录新增经营视角支出功能

- 计划日期：2026-03-06
- 对应规格：[specs/2026-03-06-transactions-manual-expense-feature.md](/C:/Users/PC/Desktop/codde/specs/2026-03-06-transactions-manual-expense-feature.md)

## 1. Scope / Out-of-scope
### Scope
- 新增独立交易类型 `expense`（经营视角真实支出）。
- 新增后端接口 `POST /api/transactions/expense`，仅接收金额和备注。
- 交易列表支持 `expense` 查询、展示、筛选与详情。
- 交易取消逻辑支持 `expense`，取消时不触发客户余额或库存回滚。
- 前端交易页新增“新增支出”入口和支出弹窗（字段仅金额+备注）。
- 新增支出/取消支出的日志类型与文案映射。

### Out-of-scope
- 不新增报销分类、审批流、附件上传。
- 不改客户消费、充值活动、会员余额主流程。
- 不新增财务报表页面。
- 不修改依赖声明与 lock 文件。

## 2. 实施前提与关键假设
- `/do` 阶段仅按本计划执行；如设计需调整，先回到 `/plan` 更新。
- 采用低风险数据策略：使用“系统占位客户”承载 `expense`，避免直接修改 `transactions.customer_id` 非空约束。
- 占位客户 ID 暂定 `C998`（实现时做“若不存在则创建”），并设置明确名称（如“系统经营支出”）避免与 `C000`（豆仓相关）语义混淆。

## 3. Implementation Steps (Ordered / Verifiable / Reversible)
### Step 1：后端支出基础能力（类型、占位客户、日志映射）
- 目标：让系统可识别 `expense` 类型并具备审计标签。
- 变更位置：
  - `backend/routes/transactions.py`
  - `backend/utils/audit_log.py`
- 变更要点：
  - 在交易模块新增 `expense` 类型常量和“占位客户获取/创建”辅助函数。
  - 在日志元数据映射中新增：
    - `expense`（创建支出）
    - `transaction_cancel_expense`（取消支出）
- 可验证：
  - 服务启动后日志筛选中可识别新类型标签。
  - 占位客户首次创建后可被重复复用。
- 可回退：
  - 保留数据库数据不删，仅下线 `expense` 类型分支与日志映射。

### Step 2：新增支出创建接口
- 目标：提供独立支出录入 API（金额+备注）。
- 变更位置：
  - `backend/routes/transactions.py`
- 变更要点：
  - 新增 `POST /transactions/expense`。
  - 请求字段仅校验：
    - `amount > 0`
    - `description` 非空
  - 写入交易：
    - `type='expense'`
    - `customer_id=EXPENSE_SYSTEM_CUSTOMER_ID`
    - `status='completed'`
  - 写入日志：`expense`，描述包含金额和备注摘要。
- 可验证：
  - 合法请求返回 201，交易列表可查到 `expense` 记录。
  - 非法金额/空备注返回 400。
- 可回退：
  - 删除该路由与调用入口，不影响原有充值/消费接口。

### Step 3：扩展交易查询与取消分支
- 目标：`expense` 在列表/取消流程中行为正确。
- 变更位置：
  - `backend/routes/transactions.py`
- 变更要点：
  - `GET /transactions` 类型筛选支持 `expense`。
  - 取消交易分支新增 `expense`：
    - 仅执行“交易取消”动作和日志记录；
    - 不修改 `Balance`；
    - 不调用杂项库存或豆仓库存回滚。
  - 取消日志类型使用 `transaction_cancel_expense`。
- 可验证：
  - `type=expense` 可筛出支出记录。
  - 取消支出后无客户余额变化、无库存变化。
- 可回退：
  - 移除 `expense` 取消分支，原有三类交易取消逻辑保持不变。

### Step 4：前端交易页接入支出录入
- 目标：在交易记录页完成“新增支出”完整交互。
- 变更位置：
  - `frontend/src/views/Transactions.vue`
  - `frontend/src/api/index.js`
- 变更要点：
  - API 层新增 `createExpense`（调用 `/transactions/expense`）。
  - 交易页新增：
    - “新增支出”按钮
    - 支出弹窗（金额、备注）
    - 表单校验与提交
  - 交易类型映射与筛选新增“支出”。
  - 列表/详情里 `expense` 展示为“支出”。
- 可验证：
  - 页面可录入支出并成功入账。
  - 筛选“支出”仅显示该类型。
- 可回退：
  - 移除支出按钮和弹窗，保留原有充值/消费流程。

### Step 5：联调与回归收口
- 目标：确保新功能不破坏旧交易链路。
- 校验重点：
  - 充值、消费、买豆支出创建与取消流程回归正常。
  - 取消 `expense` 不影响余额和库存。
  - 日志页可正确显示 `expense` 与 `transaction_cancel_expense` 标签。
- 可回退：
  - 按步骤逆序回撤（先前端入口，再后端路由，再日志映射）。

## 4. Validation Commands (PowerShell) + Expected Results
```powershell
# 1) 工具检查（预期：返回路径）
Get-Command node
Get-Command npm
Get-Command python
```

```powershell
# 2) 后端语法检查（预期：无输出，退出码 0）
python -m py_compile backend\routes\transactions.py
python -m py_compile backend\utils\audit_log.py
```

```powershell
# 3) 前端构建检查（预期：Vite build 成功，无 error）
cd frontend
npm run build
```

```powershell
# 4) 接口冒烟（预期：创建成功并可筛选到 expense）
# 先启动后端后执行
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:5000/api/transactions/expense" `
  -Headers @{ Authorization = "Bearer <TOKEN>" } `
  -ContentType "application/json" `
  -Body '{"amount":88.5,"description":"房租"}'

Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:5000/api/transactions?type=expense&page=1&page_size=10" `
  -Headers @{ Authorization = "Bearer <TOKEN>" }
```

## 5. Manual Validation Checklist
1. 在交易记录页点击“新增支出”，仅看到金额与备注输入。
2. 录入一笔支出后，列表显示类型“支出”，金额正确，详情可见备注和操作人。
3. 类型筛选切换为“支出”时，仅显示 `expense` 记录。
4. 取消一笔支出，确认交易状态/结果正确且无余额、库存副作用。
5. 回归测试充值、消费、买豆支出创建与取消，确保行为未回归。

## 6. User-run Commands (Only if dependencies are missing)
```powershell
cd frontend
npm install
```

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 7. 进入 /do 门槛
- [x] 已关联 spec
- [x] 已明确 scope / out-of-scope
- [x] 步骤有序、可验证、可回退
- [x] 包含 PowerShell 验证命令与预期结果
- [x] 明确“支出与消费语义分离”实现路径
