# 1. Summary

新增“豆仓管理”大模块，覆盖拼豆物料的建档、入库、出库、盘点、预警与流水追溯，帮助门店把每一颗拼豆的库存经营细节整理清楚并可审计。

# 2. Goals / Non-goals

## Goals

- 提供独立的“豆仓管理”菜单与页面，支持按颜色/规格/品牌管理豆料。
- 建立库存台账：当前库存、可用库存、在途库存、近 30 天消耗。
- 库存基础计量单位固定为“克”，补货与损耗支持按“袋/瓶”输入并自动换算为克。
- 支持三类核心单据：入库单、出库单、盘点单，并自动生成库存流水。
- 支持低库存预警（按单个豆料阈值）与即将耗尽提醒（按近 7 天平均消耗估算）。
- 提供豆料追溯能力：任一库存变化可回溯到具体单据、操作人、时间。
- 保持现有会员/交易/计时模块行为不变，新增模块独立可用。

## Non-goals

- 不实现供应商在线采购或自动下单（仅管理库存，不对接采购平台）。
- 不实现条码枪/PDA/打印机等硬件集成（本期仅 Web 端录入与查询）。
- 不实现复杂权限分级（沿用现有登录鉴权体系）。
- 不实现跨门店库存调拨（默认单门店场景）。
- 不改动现有充值、消费、计时结算逻辑。

# 3. Current State & Constraints

## Current behavior/state

- 当前系统已有模块：运营概况、正在计时、客户管理、交易记录、活动管理、计费规则、系统日志、数据管理。
- 后端现有模型未包含豆仓相关实体（无库存主表/流水表/盘点表）。
- 前端路由未包含“豆仓管理”页面，侧边菜单无对应入口。
- 现有日志能力可用于记录新增库存操作事件。

## Environment/platform constraints

- 运行环境：Windows + PowerShell。
- 前端：Vue 3 + Vite。
- 后端：Flask + SQLAlchemy + SQLite（当前默认实例）。
- 接口需遵循现有鉴权中间件（`@token_required`）。

## Risk constraints

- 不自动执行依赖安装/升级操作。
- 未经批准不修改依赖声明和 lock 文件。
- 库存为资金相关关键数据，必须保证写操作原子性与可追溯性。
- 库存变更需防止出现负库存（除非明确支持并标记“允许透支”，本期默认不允许）。

# 4. Requirements

## Functional requirements

### P0

- 新增“豆仓管理”导航入口与页面（建议路由：`/bead-inventory`）。
- 新增豆料主数据管理（CRUD）字段：
  - `material_id`（如 `M001`）
  - `name`
  - `color_code`
  - `spec`（如 2.6mm/5mm）
  - `brand`
  - `unit`（固定“克”）
  - `grams_per_bag`（每袋克重）
  - `grams_per_bottle`（每瓶克重）
  - `safe_stock`
  - `status`（active/inactive）
- 新增库存余额查询接口，支持按关键字、颜色、库存状态筛选。
- 新增入库单创建：录入数量、单价（可选）、来源、备注，数量输入支持“克/袋/瓶”，后端统一换算为克后增加库存并写流水。
- 新增出库单创建：录入用途（如活动制作/教学损耗）、数量、备注，数量输入支持“克/袋/瓶”，后端统一换算为克后扣减库存并写流水。
- 出库用途保持自由文本输入，不做固定枚举约束。
- 出库校验：默认不允许扣减后小于 0。
- 新增库存流水查询：按豆料、日期、操作类型（入库/出库/盘点调整）过滤。

### P1

- 新增盘点功能：
  - 录入实盘数量；
  - 自动计算差异；
  - 生成“盘点调整”流水并更新库存；
  - 盘点确认为单人确认流程（不引入双人复核）。
- 新增预警视图：
  - 低于 `safe_stock` 标红；
  - 展示“预计可用天数”（基于近 7 天平均出库）。
- 在运营概况增加“豆仓预警数”与“今日出库总量”摘要卡（如接口已存在可扩展）。

### P2

- 支持豆料导入/导出（CSV）用于初次建仓与线下备份。
- 支持库存操作原因模板（减少手工输入不一致）。

## Non-functional requirements

- 一致性：库存写操作需在单事务内完成“余额更新 + 流水写入”。
- 可审计性：每条流水必须包含操作人、时间、业务类型、关联单据号。
- 可用性：库存查询接口在 10k 级流水下仍可分页返回（P95 < 1.5s，本地环境可放宽到 2s）。
- 易用性：页面支持快速检索与分页，减少高频录入成本。
- 兼容性：不影响现有模块 API 响应结构。

## Compatibility/migration requirements

- 需要新增数据库表（至少：豆料主表、库存余额表、库存流水表、盘点单表）。
- 需要在初始化流程或迁移脚本中处理新表创建（保持老数据可继续使用）。
- 旧接口保持兼容，不对已有路由做破坏性修改。

# 5. Design

## Overall approach

- 后端：
  - 新增 `backend/routes/bead_inventory.py` 提供豆仓 API。
  - 新增模型实体（建议在 `backend/models/models.py` 扩展）：
    - `BeadMaterial`
    - `BeadInventoryBalance`
    - `BeadInventoryLedger`
    - `BeadStocktake`
  - 在路由层通过服务函数封装库存变更事务，统一处理校验、写入、日志。
- 前端：
  - 新增页面 `frontend/src/views/BeadInventory.vue`。
  - 新增 API 封装 `frontend/src/api/index.js` 中 `beadInventoryApi`。
  - 在 `MainLayout.vue` 增加菜单项并接入路由。

## Key decisions

- 使用“余额表 + 流水表”双结构：
  - 余额表用于快速查询；
  - 流水表用于追溯与审计。
- 单据驱动库存变更（入库/出库/盘点），禁止直接手改余额。
- 先做单门店模型，避免提前引入多门店复杂度。

## Alternatives and trade-offs

- 方案 A（推荐）：余额表 + 流水表 + 单据表
  - 优点：查询快、审计完整、后续可扩展多门店。
  - 缺点：模型与接口数量较多，初期开发量更大。
- 方案 B：仅流水表，余额实时聚合计算
  - 优点：模型简单。
  - 缺点：列表查询成本高，历史数据增长后性能压力大。

## Impact scope

- 前端：
  - `frontend/src/router/index.js`
  - `frontend/src/layouts/MainLayout.vue`
  - `frontend/src/views/BeadInventory.vue`（新增）
  - `frontend/src/api/index.js`
- 后端：
  - `backend/models/models.py`
  - `backend/models/__init__.py`
  - `backend/routes/bead_inventory.py`（新增）
  - `backend/routes/__init__.py`
  - `backend/app.py`
- 数据：
  - `backend/instance/` 中 SQLite 新增相关表结构

# 6. Acceptance Criteria

- 登录后侧边栏可见“豆仓管理”入口，点击进入页面正常渲染。
- 可创建豆料主数据并在列表中查询到。
- 对任一豆料设置每袋/每瓶克重后，入库和损耗按“袋/瓶”录入可自动换算为克并正确入账。
- 入库成功后，库存余额增加且可在流水中看到对应记录。
- 出库成功后，库存余额减少且可在流水中看到对应记录。
- 当出库数量大于可用库存时，接口返回明确错误并拒绝写入。
- 盘点后库存余额与实盘一致，并生成“盘点调整”流水。
- 设置安全库存后，低库存豆料在页面可见预警状态。
- 任一流水记录可看到操作人、时间、类型、数量变化、关联单据号。
- 现有客户、交易、计时、天气相关页面行为无回归。

# 7. Validation Strategy

候选验证命令（PowerShell）：

```powershell
# 1) 前端构建检查（预期：build 成功，新增路由和页面无编译错误）
cd frontend; npm run build
```

```powershell
# 2) 后端语法检查（预期：无语法错误）
python -m py_compile backend\routes\bead_inventory.py
python -m py_compile backend\models\models.py
python -m py_compile backend\app.py
```

```powershell
# 3) 接口冒烟（预期：鉴权通过后可完成豆料创建、入库、出库、流水查询）
# 示例（需先登录拿 token）：
# Invoke-RestMethod -Uri http://127.0.0.1:5000/api/bead-inventory/materials -Method Post -Headers @{ Authorization = "Bearer <TOKEN>" } -Body ...
```

```powershell
# 4) 手工验证（预期：导航可进入豆仓管理，库存与流水数据联动正确）
cd frontend; npm run dev
```

若某命令涉及依赖安装/恢复，则标记为“用户执行并回传输出”。

# 8. Risks & Rollback

## Risks

- 库存并发写入导致余额不一致（需要事务与行级更新策略）。
- 历史流水量增长后查询性能下降（需分页与索引）。
- 录入流程复杂导致操作失误（需界面提示与必填校验）。
- 旧数据库初始化逻辑未覆盖新表，导致部署后缺表。

## Rollback

- 代码回滚：移除豆仓模块路由、页面与模型注册，恢复原有菜单。
- 数据回滚：保留新增表但不再使用，或回滚到变更前数据库备份。
- 运行降级：隐藏豆仓菜单入口，仅保留其他业务模块。

# 9. Open Questions

- None

# 10. References

- `frontend/src/router/index.js`
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/api/index.js`
- `backend/models/models.py`
- `backend/routes/`

---

## /spec Completion Checklist

- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
