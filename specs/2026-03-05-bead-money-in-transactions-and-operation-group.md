# 1. Summary
将“豆子入库（买豆）”按豆料市场价自动折算为真实支出并写入“交易记录”，同时把“交易记录”菜单归入“运营管理”分组；“损耗”仅保留在豆仓库存流水中。

业务意义：当前会员交易与豆仓流水分离，经营者无法在同一入口直观看到豆子对应的资金影响，影响日常对账与经营分析。

# 2. Goals / Non-goals
## Goals
- G1：交易记录页面支持“会员交易 / 豆子交易”两类数据查看，支持一键切换。
- G2：仅“入库（买豆）”按豆料市场价（元/500g）和入库克数自动折算金额，并记入交易记录。
- G3：“损耗/常规出库/盘点调整”不进入交易记录，只保留在豆仓库存流水。
- G4：交易记录菜单项从“会员管理”移动到“运营管理”。
- G5：保留现有会员交易新增/取消/详情能力，不引入行为回归。

## Non-goals
- NG1：本次不改豆仓盘点/损耗业务规则本身。
- NG2：本次不新增财务总账、利润报表、会计科目体系。
- NG3：本次不引入新的第三方依赖或数据库引擎迁移。
- NG4：本次不改历史流水结构（仅在展示层/接口聚合层适配）。

# 3. Current State & Constraints
- 当前状态（关键路径）：
  - 会员交易页：`frontend/src/views/Transactions.vue`
  - 豆仓页（含流水）：`frontend/src/views/BeadInventory.vue`
  - 前端 API：`frontend/src/api/index.js`
  - 主布局菜单分组：`frontend/src/layouts/MainLayout.vue`
  - 豆仓后端路由：`backend/routes/bead_inventory.py`（`/ledger`）
  - 豆料模型含市场价：`backend/models/models.py`（`market_price_per_500g`）
- 约束：
  - Windows + PowerShell 开发环境。
  - 不自动执行依赖安装/恢复；不修改 lock/dependency 文件。
  - 兼容既有交易页交互（充值、消费、取消交易）。
  - 现有历史流水可能来自旧数据，需考虑价格字段缺失或异常值兜底。

# 4. Requirements
## Functional Requirements
### P0
- P0-1：当执行豆仓“入库（买豆）”时，系统自动生成一条真实交易记录（支出）。
- P0-2：入库交易金额自动换算：
  - 换算公式：`入库金额 = 入库克数 * (market_price_per_500g / 500)`
  - 金额保留 2 位小数用于展示与存储（按现有交易金额精度规则）。
- P0-3：入库交易记录需可在交易记录页查询，且可区分于会员充值/消费。
- P0-4：损耗/常规出库/盘点调整不生成交易记录，仅在豆仓库存流水中保留。
- P0-5：侧边栏“交易记录”移至“运营管理”分组。

### P1
- P1-1：入库生成的交易记录需携带可追溯信息（豆料ID/名称、入库克数、对应库存流水单号）。
- P1-2：无市场价或异常时使用兜底策略：按 `0` 金额记账并写明“价格缺失/异常”提示字段或描述。

### P2
- P2-1：后续支持导出豆子交易（CSV/Excel）的接口预留，不在本次实现。

## Non-functional Requirements
- NFR1：页面切换与筛选响应时间不劣化（同量级数据下与当前交易页相近）。
- NFR2：移动端与桌面端均可正常查看核心字段。
- NFR3：不影响现有鉴权与登录态处理。
- NFR4：金额计算前后端口径一致（如前端展示、后端可选返回一致）。

## Compatibility / Migration
- C1：历史豆仓流水无须迁移；仅新发生的“入库（买豆）”产生交易记录。若价格为空，按默认 0 处理。
- C2：菜单路径不变（仍为 `/transactions`），仅分组归属改变，避免外部链接失效。

# 5. Design
## Overall Approach
- 在豆仓入库后端流程中增加“交易落账”步骤：
  - 读取豆料市场价 `market_price_per_500g`
  - 根据入库克数换算支出金额
  - 写入交易记录（类型建议新增如 `bead_purchase`，或在既有类型体系内做可辨识扩展）
  - 交易描述关联库存流水单号，保证可追溯
- 交易记录页面沿用既有列表，增加对“豆子入库交易”的展示与筛选支持。
- 布局层调整菜单分组，将“交易记录”归入 `operation`。

## Key Decisions
- D1：金额折算采用入库当时豆料价格字段 `market_price_per_500g`。
- D2：入库即记交易，定义为真实交易，避免仅展示层“估算金额”造成账实不一致。
- D3：损耗不入交易记录，仅作为库存行为，保持业务口径清晰。

## Alternatives & Trade-offs
- 方案A（选用）：后端入库时同步生成交易记录并落库金额。
  - 优点：真实交易口径统一、跨端一致、可审计。
  - 缺点：需要改后端入库逻辑与交易模型映射。
- 方案B：前端仅展示估算金额，不落交易。
  - 优点：实现快。
  - 缺点：不满足“真实交易”要求，账目不可用于对账。

## Impact Scope
- `frontend/src/views/Transactions.vue`
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/api/index.js`（若需补充交易类型筛选）
- `backend/routes/bead_inventory.py`（入库后同步生成交易）
- `backend/routes/transactions.py`（交易类型展示与筛选兼容）
- `backend/models/models.py`（若需扩展交易类型/描述字段使用约定）

# 6. Acceptance Criteria
- AC1：每次豆仓入库成功后，交易记录中新增一条对应“买豆支出”记录。
- AC2：入库交易金额计算符合公式 `入库克数 * (market_price_per_500g / 500)`。
- AC3：损耗/常规出库/盘点调整不会新增交易记录。
- AC4：交易记录菜单显示在“运营管理”分组，不再出现在“会员管理”。
- AC5：会员交易原有能力（新增充值、消费、取消交易、详情查看）可正常使用。
- AC6：当豆料价格缺失时流程不报错，入库交易金额按 0 记账并可识别异常原因。

# 7. Validation Strategy
候选验证命令（PowerShell）：
```powershell
# 前端构建检查
cd frontend; npm run build

# 后端语法检查（若后端有改动）
python -m py_compile backend\routes\bead_inventory.py
python -m py_compile backend\models\models.py

# 运行后手工验证路径
# 1) 登录 -> 豆仓管理，执行一笔入库（有价格）
# 2) 打开交易记录，确认新增“买豆支出”且金额正确
# 3) 执行一笔损耗，确认交易记录无新增，仅豆仓库存流水新增
```

说明：如本地缺少依赖导致命令失败，按仓库规则由用户手动执行依赖恢复并回传输出。

# 8. Risks & Rollback
- 风险R1：价格缺失导致入库交易金额异常。
  - 缓解：价格空值按 0 兜底并标记异常来源。
- 风险R2：入库与记账非原子操作导致“入库成功但交易失败”。
  - 缓解：同事务提交或失败回滚；至少记录补偿日志。
- 风险R3：菜单分组调整影响习惯路径。
  - 缓解：URL 不变，必要时在发布说明提示位置变化。

回滚策略：
- 回滚后端入库联动记账逻辑与交易类型扩展，恢复“仅库存流水”旧行为。
- 回滚前端 `Transactions.vue` 与 `MainLayout.vue` 菜单/展示改动。

# 9. Open Questions
None

# 10. References
- `specs/2026-03-04-bean-warehouse-management-module.md`
- `frontend/src/views/Transactions.vue`
- `frontend/src/views/BeadInventory.vue`
- `backend/routes/bead_inventory.py`
