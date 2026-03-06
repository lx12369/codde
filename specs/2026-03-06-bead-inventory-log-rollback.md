# 1. Summary

为“豆仓模块”补齐系统日志回滚能力，覆盖库存单据回滚与豆料主数据回滚；对出库/损耗关联买豆交易采用“保留交易并标记已撤销”，保证库存、流水、交易全链路一致可审计。

# 2. Goals / Non-goals

## Goals

- 系统日志回滚支持豆仓库存类日志：
  - `bead_inventory_inbound`
  - `bead_inventory_outbound`
  - `bead_inventory_loss`
  - `bead_inventory_stocktake`
- 系统日志回滚支持豆料主数据类日志：
  - `bead_material_create`
  - `bead_material_update`
  - `bead_material_delete`
- 豆仓回滚执行后，库存余额与库存流水一致，且写入 `log_rollback`。
- 回滚出库/损耗时，关联买豆交易不删除，改为“已撤销”状态并记录撤销信息。
- 系统日志列表正确显示可回滚性（`rollback_supported/label/reason`）。
- 回滚动作保持幂等（同一源日志禁止重复回滚）。

## Non-goals

- 本期不支持批量配置类豆仓日志回滚：
  - `bead_material_import_mard`
  - `bead_conversion_standard_batch_update`
  - `bead_market_price_batch_update`
  - `bead_safe_stock_batch_update_by_common_color`
- 本期不改动系统日志页面交互框架（仅复用现有回滚按钮）。
- 本期不引入第三方审计中间件或依赖体系改造。

# 3. Current State & Constraints

## Current behavior/state

- 已有回滚入口：`POST /api/logs/{log_id}/rollback`（`backend/routes/logs.py`）。
- 当前回滚仅支持交易日志（充值/消费及其取消），豆仓日志未纳入 `ROLLBACK_SUPPORTED_TYPES`。
- 豆仓模块已有完整日志写入与库存流水（`backend/routes/bead_inventory.py` + `BeadInventoryLedger`）。
- 豆仓出库/损耗会生成买豆交易（`transactions.type='bead_purchase'`）；现有取消交易流程默认是删除交易。
- 现有 `transactions` 表没有“已撤销”状态字段，若要“保留并标记已撤销”需补充状态承载方案。

## Environment/platform constraints

- Windows + PowerShell。
- Flask + SQLAlchemy + SQLite（后端）。
- Vue 3 + Vite（前端）。
- 回滚接口仅管理员可执行（沿用现有鉴权约束）。

## Risk constraints

- 不自动执行依赖安装/升级，不修改依赖声明/lock 文件。
- 回滚必须事务化，任何子步骤失败需整体回滚。
- 豆料主数据“更新/删除”回滚需要旧值快照，若仅靠自然语言日志会不稳定，需结构化上下文。

# 4. Requirements

## Functional requirements

### P0

- 扩展 `backend/routes/logs.py`：
  - 将豆仓库存类与豆料主数据类日志纳入回滚支持集合。
  - 为各类型返回正确回滚元信息（支持状态、文案、原因）。
- 库存类日志回滚规则：
  - 入库回滚：库存扣减同等克重，追加反向库存流水；
  - 出库/损耗回滚：库存回补同等克重，追加反向库存流水；
  - 盘点回滚：按原盘点差异做反向调整并追加流水。
- 出库/损耗回滚时，关联买豆交易处理规则改为：
  - 保留原交易记录；
  - 标记为“已撤销”（建议 `status='cancelled'`）；
  - 写入撤销时间/撤销原因（至少在描述或专用字段可追溯）。
- 交易已撤销后，交易列表与系统日志可区分“正常买豆交易”与“已撤销买豆交易”。
- 同一源日志不可重复回滚，重复请求返回明确错误。

### P1

- 豆料主数据日志回滚规则：
  - `bead_material_create` 回滚为删除该豆料（仅在安全条件满足时执行）；
  - `bead_material_delete` 回滚为恢复豆料记录；
  - `bead_material_update` 回滚为还原旧字段值。
- 为主数据回滚引入结构化上下文（建议）：
  - 在创建/更新/删除日志时记录前后快照（字段白名单）；
  - 回滚接口优先读取结构化快照而非依赖自然语言解析。
- 系统日志回滚成功返回体增加摘要字段（例如 `material_id`、`reference_no`、`before_balance`、`after_balance`、`transaction_status_changed`）。

### P2

- 对历史旧日志（无结构化快照）提供“不可回滚原因”提示策略（如“历史日志缺少快照”）。

## Non-functional requirements

- 原子性：库存、流水、交易状态、日志写入必须同事务提交。
- 一致性：回滚后库存余额等于流水累计结果；出库回滚后交易状态与库存变化一致。
- 幂等性：同日志只可回滚一次。
- 可审计性：回滚链路可追溯到“源日志 -> 回滚动作 -> 结果对象”。
- 兼容性：不破坏现有充值/消费日志回滚行为。

## Compatibility/migration requirements

- 需要为 `transactions` 增加状态承载（若当前无状态字段）：
  - 至少支持 `completed` / `cancelled`；
  - 历史交易默认回填为 `completed`。
- 若引入豆料日志结构化快照，需兼容历史无快照日志（不可回滚并提示原因）。

# 5. Design

## Overall approach

- 在 `backend/routes/logs.py` 扩展“日志类型分发 + 执行器”：
  - 库存类执行器（基于 `reference_no + ledger` 定位目标）；
  - 主数据类执行器（基于结构化快照恢复）。
- 在豆仓写日志处补充可回滚上下文：
  - 创建/更新/删除豆料时写入前后快照；
  - 库存单据日志保证可提取 `reference_no/material_id`。
- 买豆交易联动回滚改造：
  - 回滚不再删除交易；
  - 统一改为标记 `cancelled` 并保留原记录。

## Key decisions

- 库存回滚采用“追加反向流水”，不改历史流水。
- 买豆交易采用“软撤销（保留记录+状态变更）”，不做物理删除。
- 主数据回滚依赖结构化快照，避免文本解析脆弱性。

## Alternatives and trade-offs

- 方案 A（推荐）：结构化快照 + 软撤销交易
  - 优点：审计清晰、回滚稳定、满足“保留交易并标记已撤销”。
  - 缺点：需要补充字段/快照逻辑，改动面略大。
- 方案 B：纯文本解析 + 物理删除交易
  - 优点：实现快。
  - 缺点：不满足业务要求（保留交易），且回滚可靠性差。

## Impact scope

- 后端：
  - `backend/routes/logs.py`
  - `backend/routes/bead_inventory.py`
  - `backend/routes/transactions.py`（若复用或调整交易撤销策略）
  - `backend/models/models.py`（交易状态/回滚上下文承载）
  - `backend/utils/audit_log.py`（必要时补日志类型元信息）
- 前端：
  - `frontend/src/views/SystemLogs.vue`（通常无需结构改动，仅展示既有字段）
  - `frontend/src/views/Transactions.vue`（如需展示 `bead_purchase` 已撤销状态）

# 6. Acceptance Criteria

- `bead_inventory_inbound` 日志可回滚时，执行后库存减少、产生反向流水、返回成功。
- `bead_inventory_outbound` / `bead_inventory_loss` 日志回滚后，库存回补、产生反向流水，关联买豆交易状态变为 `cancelled`（记录仍存在）。
- `bead_inventory_stocktake` 日志回滚后，库存按原差异反向调整并产生流水。
- `bead_material_create/update/delete` 日志在具备快照前提下可回滚，并还原正确主数据状态。
- 无快照或目标对象缺失等场景，日志项显示不可回滚并给出明确原因。
- 同一日志重复回滚返回“已回滚”错误，不产生二次变更。
- 现有充值/消费日志回滚功能可继续正常使用。

# 7. Validation Strategy

候选验证命令（PowerShell）：

```powershell
# 1) 后端语法检查（预期：无语法错误）
cd backend
..\.venv\Scripts\python.exe -m py_compile routes\logs.py
..\.venv\Scripts\python.exe -m py_compile routes\bead_inventory.py
..\.venv\Scripts\python.exe -m py_compile routes\transactions.py
..\.venv\Scripts\python.exe -m py_compile models\models.py
```

```powershell
# 2) 前端构建检查（预期：系统日志/交易页构建通过）
cd frontend
npm run build
```

```powershell
# 3) 回滚接口冒烟（预期：豆仓日志回滚成功；出库回滚后交易仍存在且状态为 cancelled）
# 说明：需先登录并准备测试数据；建议用户执行并回传输出
# Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:5000/api/logs/<LOG_ID>/rollback" -Headers @{ Authorization = "Bearer <TOKEN>" }
```

```powershell
# 4) 手工核验（预期：系统日志按钮、豆仓库存、豆仓流水、交易状态一致）
cd frontend
npm run dev
```

若本地命令受依赖环境限制，则由用户执行相关命令并回传输出后继续。

# 8. Risks & Rollback

## Risks

- 主数据回滚缺少结构化快照会导致不可恢复或恢复错误。
- 交易状态字段改造若处理不当，可能影响历史交易列表筛选/展示。
- 库存回滚与交易软撤销顺序不当可能造成短暂不一致。
- 历史脏数据（单号重复、手工改库）会降低回滚命中率。

## Rollback

- 代码回滚：撤回豆仓类型回滚分发，仅保留交易日志回滚。
- 功能降级：保留日志列表展示，将豆仓日志统一标记“不可回滚”。
- 数据修复：基于 `log_rollback` 与库存流水追踪异常记录，执行人工补偿。

# 9. Open Questions

- None

# 10. References

- `backend/routes/logs.py`
- `backend/routes/bead_inventory.py`
- `backend/routes/transactions.py`
- `backend/models/models.py`
- `backend/utils/audit_log.py`
- `frontend/src/views/SystemLogs.vue`
- `frontend/src/views/Transactions.vue`

---

## /spec Completion Checklist

- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
