# 运营管理新增杂项计费页面并接入计费系统可执行规格

### 1. Summary
- 在“运营管理”分组下新增“杂项计费”页面，用于维护店内小样类收费规则（例如“钥匙串 ¥X/个”），并将该规则接入现有消费计费链路。
- 当前系统仅支持套餐/素材/附加费，缺少可维护的“按件杂项收费”规则，导致门店靠手工备注和手动加价，容易漏收与记账不一致。

### 2. Goals / Non-goals
- Goals
  - 在侧边栏“运营管理”分组新增“杂项计费”菜单入口与页面路由。
  - 新页面支持杂项规则的新增、编辑、启停、删除、排序（至少按显示顺序可控）。
  - 每条杂项规则至少包含：名称、单价、计价单位（默认“个”）、启用状态。
  - 杂项规则变更后可被计费流程读取并参与金额计算。
  - 在消费结算界面（正在计时、客户管理自动消费、交易记录自动消费）支持选择杂项数量并自动计算杂项费用。
  - 交易落账金额包含杂项费用，消费描述中可读到杂项明细（例如“钥匙串x2”）。
  - 保持现有计费规则（limited/weekday/weekend/materials/overtime）行为不回归。
- Non-goals
  - 不改充值活动、会员余额机制与交易撤销主流程。
  - 不引入新的第三方依赖或修改依赖锁文件。
  - 不重构整套权限系统（仅在本需求范围内定义页面/API访问策略）。
  - 不新增独立“杂项交易类型”；本期仍按消费交易（`consumption`）记账。

### 3. Current State & Constraints
- 当前状态
  - 侧边栏“运营管理”分组定义在 `frontend/src/layouts/MainLayout.vue`，现有菜单包括“交易记录/活动管理/计费规则/豆仓管理”，无“杂项计费”。
  - 路由定义在 `frontend/src/router/index.js`，当前无杂项计费页面路由。
  - 计费规则由 `backend/routes/billing.py` 的 `/api/billing-rules` 统一提供，当前规则类型为 `limited/weekday/weekend/materials/overtime`。
  - 消费金额计算集中在 `frontend/src/utils/consumptionCalculator.js`，当前仅计入基础费、超时费、素材费、附加费。
  - 三个消费入口均复用该计算器并调用消费接口：
    - `frontend/src/views/ActiveTimers.vue`
    - `frontend/src/views/Customers.vue`
    - `frontend/src/views/Transactions.vue`
- 环境/平台约束
  - Windows + PowerShell。
  - 前端 Vue 3 + Vite，后端 Flask + SQLAlchemy + SQLite。
- 风险约束
  - 禁止自动执行依赖安装/恢复；未获用户批准不得修改依赖声明或锁文件。
  - `/spec` 阶段仅允许修改 `specs/`。

### 4. Requirements
- Functional requirements
  - P0
    - 新增页面 `杂项计费`（建议路由：`/misc-billing`），并挂载到“运营管理”分组。
    - 杂项规则维护权限与现有计费规则页一致：登录用户可写（非登录用户不可访问）。
    - 新增杂项规则管理能力（列表 + 新增 + 编辑 + 启停 + 删除 + 排序）。
    - 规则字段定义：
      - `id`：字符串标识（系统生成，页面不可编辑）。
      - `name`：杂项名称（唯一，非空，例如“钥匙串”）。
      - `unit_price`：单价（>=0）。
      - `unit_label`：单位（默认“个”，非空）。
      - `enabled`：是否启用。
      - `sort_order`：排序值（用于前端展示顺序）。
    - 后端计费规则接口支持 `misc` 规则块（作为统一计费配置的一部分持久化），并对历史无 `misc` 数据自动补空结构。
    - 三个消费入口支持“杂项选择”：
      - 基于启用规则渲染数量输入（每项数量默认为 0，且仅允许整数）。
      - 杂项费用自动计入消费总额。
      - 预览区展示“杂项费用”与明细。
    - 交易写入时，`amount` 包含杂项费用；`description` 中包含杂项明细文本，便于对账。
  - P1
    - 杂项规则支持批量清空数量（消费弹窗中一键重置）。
    - 若规则被停用，不再出现在新建消费界面；历史交易描述不受影响。
    - `计费规则`页面保存其他规则时，不应覆盖或丢失 `misc` 规则数据。
    - 关键规则变更写入系统日志（新增/编辑/删除/启停/排序）。
  - P2
    - 杂项计费页视觉风格与现有运营页面一致（hero、反馈条、卡片式表单）。
- Non-functional requirements
  - 安全性：后端需校验输入类型与边界（负数、空名称、重复名称、异常排序值）。
  - 数据正确性：杂项数量仅按整数处理（前端限制 + 后端兜底，非法值按校验失败返回）。
  - 兼容性：维持现有 `/api/billing-rules` 响应结构兼容，旧数据无 `misc` 时前端按空列表处理。
  - 可维护性：计费计算仍集中在 `consumptionCalculator`，避免在多个页面重复计价逻辑。
  - 可观测性：消费描述包含可读明细，便于人工核账与回溯。
- Compatibility / migration requirements
  - 不新增数据库表；复用 `billing_rules` 的 JSON 存储扩展 `misc` 规则块。
  - 兼容已有 `billing_rules` 记录；首次读取自动补齐默认 `misc` 结构（例如 `{ items: [] }`）。

### 5. Design
- Overall approach
  - 配置存储层
    - 在 `billing_rules` 中新增 `rule_type = 'misc'`（或在统一返回结构中新增 `misc` 字段）保存杂项规则列表。
    - 在 `backend/routes/billing.py` 增加 `normalize_misc_rule_data`，统一清洗字段与默认值。
  - 前端入口层
    - `MainLayout.vue` 新增“杂项计费”菜单（`group: 'operation'`）。
    - `router/index.js` 新增 `/misc-billing` 路由。
    - 新增 `views/MiscBilling.vue` 页面，使用 `GET/PUT /billing-rules` 读取与保存 `misc`。
  - 计费计算层
    - `consumptionCalculator.js` 扩展：
      - 输入：`miscSelections`（每项数量，整数）。
      - 规则：`rules.misc.items`。
      - 输出：新增 `miscFee` 与杂项明细项。
      - 总额计算：`baseFee + overtimeFee + materialFee + miscFee + additionalFee`。
  - 消费入口层
    - 在 `ActiveTimers.vue`、`Customers.vue`、`Transactions.vue` 接入杂项数量输入与预览展示。
    - 提交消费时，沿用现有 `createConsumption/settle` 接口，金额与描述包含杂项结果。
- Key decisions
  - 决策 1：复用既有 `billing_rules` 配置中心，不新增独立表，降低迁移与回滚复杂度。
  - 决策 2：复用统一计费计算器，确保三个消费入口计算口径一致。
  - 决策 3：杂项按“规则 + 数量”计算，不引入新的交易主类型，保持交易模型稳定。
- Alternatives and trade-offs
  - 方案 A（推荐）：在 `billing_rules` 中扩展 `misc` 配置并复用现有 `/billing-rules` 接口。
    - 优点：改动集中、兼容当前架构、无新表迁移。
    - 缺点：`billing_rules` JSON 结构变大，规则编辑并发冲突需注意。
  - 方案 B：新增 `misc_billing_items` 独立表与 CRUD 接口。
    - 优点：结构化更强、后续统计更清晰。
    - 缺点：需要新增模型与迁移逻辑，实现和回滚成本更高。
- Impact scope
  - 前端：
    - `frontend/src/layouts/MainLayout.vue`
    - `frontend/src/router/index.js`
    - `frontend/src/views/MiscBilling.vue`（新增）
    - `frontend/src/api/index.js`
    - `frontend/src/utils/consumptionCalculator.js`
    - `frontend/src/views/ActiveTimers.vue`
    - `frontend/src/views/Customers.vue`
    - `frontend/src/views/Transactions.vue`
  - 后端：
    - `backend/routes/billing.py`
    - （可选）`backend/routes/logs.py` 仅用于校验日志展示，不要求改接口

### 6. Acceptance Criteria
- AC1：侧边栏“运营管理”分组出现“杂项计费”菜单，点击可进入页面。
- AC2：杂项计费页可新增规则（示例：`钥匙串`、`单价=5`、`单位=个`），刷新后仍存在。
- AC3：规则可编辑/启停/删除，操作后列表状态与持久化一致。
- AC4：当规则被启用时，在三个消费入口均可看到对应数量输入项。
- AC5：填写数量后，预览区“杂项费用”按规则自动计算，且总金额同步变化。
- AC6：提交消费后，交易记录金额包含杂项费用，描述包含杂项明细（名称与数量）。
- AC7：停用规则后，不再出现在新的消费录入界面；已存在历史交易不受影响。
- AC8：不使用杂项时，现有计费结果与改造前一致（回归校验）。
- AC9：`/api/billing-rules` 在旧库（无 `misc`）场景下仍可正常返回并完成保存。
- AC10：前端构建通过，后端变更文件语法检查通过。
- AC11：登录用户可在“杂项计费”页面执行新增/编辑/删除/启停/排序保存。
- AC12：杂项数量仅接受整数；输入小数或非法值时被拦截并提示，不能提交计费。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 工具存在性检查
    ```powershell
    Get-Command node
    Get-Command npm
    Get-Command python
    ```
    预期：返回可执行路径。
  - 后端语法检查
    ```powershell
    python -m py_compile backend\routes\billing.py
    ```
    预期：无输出且退出码为 0。
  - 前端语法与构建检查
    ```powershell
    node --check frontend\src\utils\consumptionCalculator.js
    node --check frontend\src\api\index.js
    cd frontend; npm run build
    ```
    预期：无语法报错，Vite 构建成功。
  - 联调与手工验收
    ```powershell
    cd backend; ..\.venv\Scripts\python.exe app.py
    cd frontend; npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：按 AC1-AC12 完成页面与计费链路验证。
- 需用户执行并粘贴输出的命令
  - 若本地缺依赖：
    ```powershell
    cd frontend; npm install
    cd backend; ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
    ```

### 8. Risks & Rollback
- Risks
  - 杂项规则与原计费规则合并保存时，若前端 payload 不完整可能导致字段覆盖。
  - 三个消费入口同时改造，存在口径不一致风险（某页面漏加 `miscFee`）。
  - 交易描述拼接不规范会降低对账可读性。
- Rollback
  - 前端回滚：移除“杂项计费”菜单/路由/页面，恢复消费表单中杂项输入与预览。
  - 后端回滚：移除 `misc` 规则读写逻辑，保留原五类规则。
  - 数据回滚：`billing_rules` 中 `misc` 配置可置空（`items=[]`）实现软回退，不影响历史交易。

### 9. Open Questions
- None

### 10. References
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/router/index.js`
- `frontend/src/views/Billing.vue`
- `frontend/src/views/ActiveTimers.vue`
- `frontend/src/views/Customers.vue`
- `frontend/src/views/Transactions.vue`
- `frontend/src/utils/consumptionCalculator.js`
- `frontend/src/api/index.js`
- `backend/routes/billing.py`
- `backend/models/models.py`

## /spec Completion Checklist (self-check)
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
