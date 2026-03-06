# 交易金额与余额变动符号解耦可执行规格

### 1. Summary
- 将交易金额与账户余额变动口径彻底拆分：`transactions.amount` 始终表示业务金额（正值），客户余额变化使用独立派生值表示（充值为正、消费为负）。
- 当前页面通过同一金额字段在不同场景加减号展示，容易造成“同字段多语义”混淆，影响交易认知、报表解释与后续功能扩展。

### 2. Goals / Non-goals
- Goals
  - 明确并固化金额语义：`transactions.amount` 仅表示交易业务金额，禁止按场景翻转字段符号。
  - 在交易查询结果中提供余额变动口径（建议 `balance_delta` 派生字段）。
  - 报表收入统计继续以消费金额正值汇总，不受余额变动符号影响。
  - 前端交易列表/详情可同时表达“业务金额”和“余额变动”，避免误解。
  - 保持现有充值、消费、计时重算、取消交易逻辑不回归。
- Non-goals
  - 不修改历史交易记录原始金额符号（不做离线数据迁移）。
  - 不引入完整会计科目体系（应收、应付、总账）。
  - 不在本期重构所有报表模块，仅覆盖交易记录与首页统计口径一致性。

### 3. Current State & Constraints
- Current state
  - 后端已要求充值/消费/支出入参金额为正值：
    - [transactions.py](C:\Users\PC\Desktop\codde\backend\routes\transactions.py) `create_recharge/create_consumption/create_expense` 均校验 `amount > 0`。
  - 后端余额变更已是独立操作语义：
    - 充值 `balance += amount + bonus`
    - 消费 `balance -= amount`
  - 首页统计按交易类型汇总金额：
    - [dashboard.py](C:\Users\PC\Desktop\codde\backend\routes\dashboard.py) 统计 `today_consumption_amount` 为消费金额汇总（正值）。
  - 前端交易展示仍将同一 `transaction.amount` 通过前缀 `+/-` 表达不同含义：
    - [Transactions.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Transactions.vue) `isIncomeTransaction/getTransactionAmountPrefix`
    - [Customers.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Customers.vue) 客户详情交易金额列使用 `transaction.type === 'recharge' ? '+' : '-'`。
- Environment/platform constraints
  - Windows + PowerShell。
  - 前端 Vue 3 + Vite，后端 Flask + SQLAlchemy + SQLite。
- Risk constraints
  - `/spec` 阶段仅允许修改 `specs/`。
  - 不自动安装/恢复依赖，不修改依赖声明与锁文件。

### 4. Requirements
- Functional requirements
  - P0
    - 定义统一口径并体现在接口返回：
      - `amount`：业务金额（始终非负，消费收入在报表中按正值统计）。
      - `balance_delta`：客户余额变动（充值为正，消费为负）。
    - `GET /api/transactions` 与 `GET /api/transactions/<id>` 返回 `balance_delta`（可派生，不要求落库）。
    - 交易列表增加“余额变动”展示位，消费显示负值、充值显示正值。
    - 交易详情增加“余额变动”字段，语义与列表一致。
    - 首页统计维持“消费收入正值”口径，不被 `balance_delta` 影响。
  - P1
    - 统一交易类型映射规则，覆盖 `recharge`、`consumption`、`expense`、`bead_purchase`、已取消状态。
    - 客户详情页交易记录与交易中心保持同一金额语义。
  - P2
    - 导出/打印（如存在）补充“余额变动”列，避免业务方二次解释。
- Non-functional requirements
  - 一致性：同一字段在所有页面保持同一业务含义。
  - 可回溯性：新增字段为派生值时，必须可由原始交易数据稳定重建。
  - 可维护性：余额变动计算逻辑应集中在后端单点函数，避免多处复制。
  - 兼容性：旧前端读取 `amount` 的路径不应崩溃；新字段按向后兼容方式追加。
- Compatibility / migration requirements
  - 优先采用“接口派生字段”方案，不改数据库结构。
  - 若后续选择落库（新增 `amount_sign` 或 `balance_delta` 列），需补充迁移脚本与历史回填策略（本期不做）。

### 5. Design
- Overall approach
  - 后端
    - 在交易序列化阶段统一计算 `balance_delta`：
      - `recharge`: `amount + bonus_amount`
      - `consumption`: `-amount`
      - `expense` / `bead_purchase`: `0`（不影响客户余额）
      - 其他类型默认 `0`，并保留扩展点。
    - 保持 `amount` 原值（正值）不变。
  - 前端
    - 交易列表“交易金额”展示业务金额（不再用该列承载余额方向语义）。
    - 新增“余额变动”展示列或等价视觉分组，用于显示 `balance_delta`。
    - 客户详情页交易表同步该规则。
  - 报表
    - 首页与统计继续按 `type=consumption` 汇总 `amount`（正值）作为消费收入。
- Key decisions
  - 决策 1：`amount` 只承载业务金额，不承载余额方向。
  - 决策 2：余额方向通过独立字段表达，避免 UI 人工拼接符号带来的语义漂移。
  - 决策 3：优先派生字段，降低迁移风险与实施成本。
- Alternatives and trade-offs
  - 方案 A（推荐）：接口派生 `balance_delta`，数据库不变。
    - 优点：改动小、上线快、兼容性高。
    - 缺点：跨系统直连数据库时看不到该字段，需经过 API。
  - 方案 B：数据库新增 `balance_delta` 持久化列。
    - 优点：查询与导出更直接。
    - 缺点：需要迁移和历史回填，出错面更大。
  - 方案 C：继续仅靠前端前缀 `+/-` 表达。
    - 优点：零后端改动。
    - 缺点：同字段多语义问题持续存在，不满足本需求。
- Impact scope
  - 后端
    - [transactions.py](C:\Users\PC\Desktop\codde\backend\routes\transactions.py)
    - [models.py](C:\Users\PC\Desktop\codde\backend\models\models.py)（如在 `to_dict` 增加派生字段）
  - 前端
    - [Transactions.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Transactions.vue)
    - [Customers.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Customers.vue)
  - 统计
    - [dashboard.py](C:\Users\PC\Desktop\codde\backend\routes\dashboard.py)（仅做口径确认与回归验证）

### 6. Acceptance Criteria
- AC1：`transactions.amount` 在充值、消费、支出、买豆记录中均保持正值存储与返回。
- AC2：交易接口返回 `balance_delta`，且充值为正、消费为负、不影响余额类型为 0。
- AC3：交易列表可同时看见“业务金额”和“余额变动”，两者不混用。
- AC4：客户详情页交易记录采用同口径展示，不再依赖单列 `+/-` 推断业务含义。
- AC5：首页“今日消费金额”仍为正值汇总，且与交易明细消费金额口径一致。
- AC6：取消充值/消费后，余额回滚逻辑与展示口径不冲突。
- AC7：现有创建充值、创建消费、计时重算、支出录入流程回归通过。

### 7. Validation Strategy
- Candidate validation commands
  - 工具存在性检查
    ```powershell
    Get-Command python
    Get-Command node
    Get-Command npm
    ```
    预期：返回可执行路径。
  - 后端语法检查
    ```powershell
    python -m py_compile backend\routes\transactions.py backend\models\models.py backend\routes\dashboard.py
    ```
    预期：无输出且退出码为 0。
  - 前端语法/构建检查
    ```powershell
    cd frontend
    npm run build
    ```
    预期：构建成功，无编译报错。
  - 手工验收（核心场景）
    ```powershell
    cd backend
    ..\.venv\Scripts\python.exe app.py
    ```
    ```powershell
    cd frontend
    npm run dev
    ```
    预期：按 AC1-AC7 验收通过。
- User-run with pasted output
  - 若依赖缺失，仅由用户执行并粘贴输出：
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
  - 若 `balance_delta` 规则遗漏某些交易类型，可能出现展示为 0 或方向错误。
  - 前端若仅局部改造，交易中心与客户详情页可能口径不一致。
  - 旧代码依赖 `+/-` 前缀语义时，可能在短期内出现用户认知偏差。
- Rollback
  - 回退前端新增“余额变动”展示，恢复原列表结构。
  - 回退后端新增派生字段（保留 `amount` 既有逻辑不变）。
  - 回退不涉及数据库结构和历史数据变更，风险可控。

### 9. Open Questions
- 是否将 `expense`、`bead_purchase` 的 `balance_delta` 固定定义为 `0`（推荐）并在 UI 标注“非客户余额交易”？
- 交易列表是否需要把“业务金额”改名为“交易金额（业务口径）”以减少运营误解？

### 10. References
- [transactions.py](C:\Users\PC\Desktop\codde\backend\routes\transactions.py)
- [models.py](C:\Users\PC\Desktop\codde\backend\models\models.py)
- [Transactions.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Transactions.vue)
- [Customers.vue](C:\Users\PC\Desktop\codde\frontend\src\views\Customers.vue)
- [dashboard.py](C:\Users\PC\Desktop\codde\backend\routes\dashboard.py)

## /spec Completion Checklist (self-check)
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable (not vague)
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
