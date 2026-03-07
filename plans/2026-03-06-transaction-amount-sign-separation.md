# /plan：交易金额与余额变动符号解耦

- 计划日期：2026-03-06
- 对应规格：[specs/2026-03-06-transaction-amount-sign-separation.md](/C:/Users/PC/Desktop/codde/specs/2026-03-06-transaction-amount-sign-separation.md)

## 1. Scope / Out-of-scope
### Scope
- 保持 `transactions.amount` 为业务金额正值，不改数据库历史数据。
- 后端交易返回新增派生字段 `balance_delta`，统一表达客户余额变动方向。
- 交易中心页面新增或调整“余额变动”展示，保留“业务金额”独立语义。
- 客户详情页交易记录同步采用相同金额口径。
- 校验首页统计继续按消费正值金额汇总，不混入余额方向语义。

### Out-of-scope
- 不新增数据库字段，不做历史数据迁移。
- 不改充值、消费、计时结算、支出录入的业务流程本身。
- 不新增财务总账、应收应付、会计科目模块。
- 不修改依赖声明与 lock 文件。

## 2. 实施前提与关键假设
- `/do` 阶段仅按本计划执行；如执行中发现需要改数据库结构或改变既有交易语义，先回到 `/plan`。
- `expense` 与 `bead_purchase` 默认视为“不影响客户余额”的交易类型，其 `balance_delta` 固定为 `0`。
- 优先在后端统一生成 `balance_delta`，避免前端重复推导造成口径漂移。

## 3. Implementation Steps (Ordered / Verifiable / Reversible)
### Step 1：梳理并固化后端余额变动映射
- 目标：在后端单点定义“交易类型 -> 余额变动”的映射规则。
- 变更位置：
  - `backend/models/models.py`
  - 如需要，`backend/routes/transactions.py`
- 变更要点：
  - 为 `Transaction.to_dict()` 或等价序列化层新增 `balance_delta`。
  - 规则固定为：
    - `recharge`: `amount + bonus_amount`
    - `consumption`: `-amount`
    - `expense`: `0`
    - `bead_purchase`: `0`
    - 其他未知类型：`0`
- 可验证：
  - 列表和详情接口都能拿到 `balance_delta`。
  - 同一交易在不同接口返回的 `balance_delta` 一致。
- 可回退：
  - 仅移除新增派生字段，不影响现有数据库内容和交易逻辑。

### Step 2：核对交易相关后端接口兼容性
- 目标：确保新增派生字段不会破坏现有交易查询、重算、取消逻辑。
- 变更位置：
  - `backend/routes/transactions.py`
- 变更要点：
  - 校验 `GET /transactions`、`GET /transactions/<id>`、计时重算返回中均包含 `balance_delta`。
  - 不改变创建、取消时对余额的真实加减逻辑，只补充返回口径。
  - 如现有某些返回路径绕过 `to_dict()`，补齐统一序列化。
- 可验证：
  - 充值、消费、支出、买豆支出、取消后的返回结构都可稳定读取 `balance_delta`。
- 可回退：
  - 回退额外序列化封装，不影响原业务入账与回滚。

### Step 3：交易中心页面拆分“业务金额”与“余额变动”
- 目标：消除单列金额通过 `+/-` 承载双重语义的问题。
- 变更位置：
  - `frontend/src/views/Transactions.vue`
- 变更要点：
  - 保留“交易金额/业务金额”展示 `transaction.amount` 原值。
  - 新增“余额变动”展示 `transaction.balance_delta`。
  - 调整颜色、前缀和标签逻辑，使充值/消费/非余额交易一眼可区分。
  - 详情弹窗同步展示 `balance_delta`。
- 可验证：
  - 同一笔消费显示“业务金额 = 正值”“余额变动 = 负值”。
  - 同一笔充值显示“业务金额 = 正值”“余额变动 = 正值”。
  - `expense`、`bead_purchase` 显示 `balance_delta = 0` 或明确“不影响余额”。
- 可回退：
  - 移除新增列/字段展示，恢复旧 UI，但后端字段可暂时保留。

### Step 4：客户详情页交易记录同步口径
- 目标：客户详情页与交易中心页保持一致，避免页面间解释冲突。
- 变更位置：
  - `frontend/src/views/Customers.vue`
- 变更要点：
  - 交易记录列表从“充值加号、其他减号”的简单规则改为读取 `balance_delta`。
  - 保留交易类型标签与业务金额展示。
  - 对 `expense`、`bead_purchase` 做明确降级展示，避免误导为客户余额扣减。
- 可验证：
  - 客户详情页与交易中心对同一笔交易显示的金额语义一致。
- 可回退：
  - 单独回退客户详情页展示逻辑，不影响交易中心和后端接口。

### Step 5：统计与回归验证
- 目标：确认首页统计继续按收入口径使用 `amount`，未被新字段扰动。
- 变更位置：
  - `backend/routes/dashboard.py`（仅在发现需要显式注释或微调时）
  - `frontend/src/views/Dashboard.vue`（仅回归验证，不预设改动）
- 变更要点：
  - 验证 `today_consumption_amount` 仍汇总消费正值金额。
  - 验证交易列表展示改动不影响首页、计时重算、取消交易与支出录入。
- 可验证：
  - 首页“今日消费金额”与消费流水正值总和一致。
  - 充值/消费/支出/买豆支出/取消交易回归正常。
- 可回退：
  - 若仅 UI 改动引发歧义，优先回退前端展示层，不触动后端既有统计。

## 4. Validation Commands (PowerShell) + Expected Results
```powershell
# 1) 工具检查（预期：返回路径）
Get-Command python
Get-Command node
Get-Command npm
```

```powershell
# 2) 后端语法检查（预期：无输出，退出码 0）
python -m py_compile backend\models\models.py
python -m py_compile backend\routes\transactions.py
python -m py_compile backend\routes\dashboard.py
```

```powershell
# 3) 前端构建检查（预期：Vite build 成功，无 error）
cd frontend
npm run build
```

```powershell
# 4) 手工接口核对（预期：列表返回包含 amount 和 balance_delta，且符号符合口径）
# 先启动服务并登录后执行
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:5000/api/transactions?page=1&page_size=10" `
  -Headers @{ Authorization = "Bearer <TOKEN>" }
```

## 5. Manual Validation Checklist
1. 交易中心列表中，同一笔消费显示“交易金额”为正、“余额变动”为负。
2. 交易中心列表中，同一笔充值显示“交易金额”为正、“余额变动”为正。
3. 交易详情弹窗能同时看到业务金额与余额变动。
4. 客户详情页交易记录与交易中心同口径展示。
5. 首页“今日消费金额”与消费流水按正值汇总结果一致。
6. 创建充值、消费、支出、买豆支出，以及取消交易、计时重算流程均无回归。

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
- [x] 明确“业务金额”和“余额变动”分离落地路径
