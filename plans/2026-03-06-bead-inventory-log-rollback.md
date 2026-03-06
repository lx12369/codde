# /plan：豆仓系统日志回滚（含交易软撤销）执行计划

- 计划日期：2026-03-06
- 对应规格：`specs/2026-03-06-bead-inventory-log-rollback.md`

## 1. Scope / Out-of-scope
### Scope
- 系统日志回滚支持以下豆仓库存日志：
  - `bead_inventory_inbound`
  - `bead_inventory_outbound`
  - `bead_inventory_loss`
  - `bead_inventory_stocktake`
- 系统日志回滚支持以下豆料主数据日志：
  - `bead_material_create`
  - `bead_material_update`
  - `bead_material_delete`
- 回滚出库/损耗关联买豆交易时，保留交易记录并标记为 `cancelled`，不再物理删除。
- 日志列表返回准确的回滚元信息（`rollback_supported/rollback_label/rollback_reason`）。
- 同一源日志幂等：禁止重复回滚，并给出明确提示。

### Out-of-scope
- 不支持批量配置类豆仓日志回滚（`bead_material_import_mard`、批量更新换算标准/市场价/安全库存）。
- 不重做系统日志页面交互，仅复用现有回滚按钮与提示区域。
- 不引入第三方依赖，不修改依赖声明与 lock 文件。

## 2. 实施前提
- `/do` 阶段仅按本计划执行；若实现中发现需调整方案，先回到 `/plan` 更新文档。
- 回滚必须事务化：库存、流水、交易状态、日志写入在同一事务内提交。
- 历史日志无结构化快照时，必须返回“不可回滚原因”，不能做猜测性文本回滚。

## 3. Implementation Steps (Ordered / Verifiable / Reversible)
### Step 1：数据承载与兼容迁移
- 目标：为“交易软撤销”和“日志结构化快照”提供稳定字段。
- 变更位置：
  - `backend/models/models.py`
  - `backend/models/init_db.py`
- 变更要点：
  - `Transaction` 增加撤销承载字段（至少 `status`，并补充撤销时间/原因字段用于审计）。
  - `Log` 增加结构化上下文字段（JSON）用于记录前后快照、关联单号、关联交易等。
  - 在 `init_db` 增加列存在性检查与 `ALTER TABLE` 兼容逻辑；历史交易默认状态回填为 `completed`。
- 可验证：老库启动后可自动补齐字段；查询历史交易时 `status` 不为空。
- 可回退：保留新增列但停用新字段读取逻辑，业务仍可回到“仅旧回滚能力”。

### Step 2：豆仓日志写入结构化上下文
- 目标：让库存日志与主数据日志可被稳定回滚（不依赖自然语言解析）。
- 变更位置：
  - `backend/utils/audit_log.py`
  - `backend/routes/bead_inventory.py`
- 变更要点：
  - `write_log` 支持 `context` 入参并落库（描述文本保持兼容）。
  - 入库/出库/损耗/盘点日志写入最小可回滚上下文：
    - `material_id`
    - `reference_no`
    - `delta_grams`
    - `balance_before/balance_after`
    - 关联买豆交易 ID（如有）
  - 豆料创建/更新/删除日志写入前后快照（字段白名单），用于回滚恢复。
- 可验证：新产生豆仓日志可读到结构化上下文；描述文本仍可正常展示。
- 可回退：保留 `write_log` 兼容签名，回退调用方到“仅 description”写法。

### Step 3：扩展系统日志回滚分发与执行器
- 目标：在 `/api/logs/{log_id}/rollback` 中接入豆仓类型回滚。
- 变更位置：
  - `backend/routes/logs.py`
- 变更要点：
  - 扩展 `ROLLBACK_SUPPORTED_TYPES` 与 `_resolve_rollback_context`，纳入豆仓库存/主数据日志。
  - 新增豆仓库存回滚执行器：
    - 入库回滚：反向扣减库存并追加反向流水；
    - 出库/损耗回滚：反向回补库存并追加反向流水；
    - 盘点回滚：按原差异反向调整并追加流水。
  - 新增豆料主数据回滚执行器：
    - `create -> delete`
    - `update -> restore before snapshot`
    - `delete -> restore before snapshot`
  - 对“历史无快照日志”返回明确 `rollback_reason`（例如“历史日志缺少快照”）。
  - 回滚成功返回摘要信息（例如 `reference_no/material_id/transaction_status_changed`）。
- 可验证：豆仓日志列表可显示“可回滚/不可回滚原因”；执行后库存和流水同步变化。
- 可回退：从支持集合移除豆仓类型，保持原交易日志回滚能力不变。

### Step 4：买豆交易从“物理删除”改为“软撤销”
- 目标：满足“保留交易并标记已撤销”要求，并与日志回滚行为一致。
- 变更位置：
  - `backend/routes/transactions.py`
  - `backend/routes/logs.py`（回滚出库/损耗联动部分）
- 变更要点：
  - 买豆交易取消与日志回滚联动时，不再 `db.session.delete(transaction)`。
  - 改为更新 `status='cancelled'`，并写入撤销来源（手动取消/日志回滚）、撤销时间、撤销原因。
  - 查询交易列表时返回状态字段；必要时增加 `status` 过滤参数（`completed/cancelled/all`）。
  - 避免重复撤销：已 `cancelled` 交易再次取消应返回明确错误。
- 可验证：取消/回滚后交易仍可查询，状态为 `cancelled`，且库存已按规则回滚。
- 可回退：保留字段不使用，恢复旧取消逻辑（仅用于紧急降级）。

### Step 5：前端状态展示与操作约束
- 目标：让“已撤销买豆交易”在交易记录页可见且可区分。
- 变更位置：
  - `frontend/src/views/Transactions.vue`
  - （按需）`frontend/src/api/index.js`
- 变更要点：
  - 使用后端返回的 `status` 展示状态标签（`completed/cancelled`）。
  - 对 `cancelled` 交易禁用“取消交易”按钮，避免误操作。
  - 如后端支持状态筛选，前端筛选区接入状态过滤项。
- 可验证：取消后的买豆交易不消失，状态显示“已取消”，且无法再次取消。
- 可回退：隐藏状态筛选，保留状态文案兜底显示。

### Step 6：联调与回归
- 目标：确认豆仓回滚链路不影响既有充值/消费回滚与交易流程。
- 校验重点：
  - 豆仓四类库存日志回滚结果正确；
  - 豆料三类主数据日志在有快照时可回滚；
  - 无快照历史日志给出不可回滚原因；
  - 充值/消费日志回滚行为保持原有预期。
- 可回退：按步骤粒度逐步回撤（先下线主数据回滚，再下线库存回滚）。

## 4. Validation Commands (PowerShell) + Expected Results
```powershell
# 1) 环境命令检查（预期：返回命令路径）
Get-Command python
Get-Command node
Get-Command npm
```

```powershell
# 2) 后端语法检查（预期：无输出/退出码 0）
Set-Location backend
..\.venv\Scripts\python.exe -m py_compile models\models.py
..\.venv\Scripts\python.exe -m py_compile models\init_db.py
..\.venv\Scripts\python.exe -m py_compile utils\audit_log.py
..\.venv\Scripts\python.exe -m py_compile routes\bead_inventory.py
..\.venv\Scripts\python.exe -m py_compile routes\logs.py
..\.venv\Scripts\python.exe -m py_compile routes\transactions.py
```

```powershell
# 3) 前端构建检查（预期：build 成功，无 error）
Set-Location frontend
npm run build
```

```powershell
# 4) 回滚接口冒烟（用户执行并回传输出）
# 预期：
# - 豆仓目标日志 rollback_supported 为 true
# - 回滚成功后返回 action/result 摘要
# - 关联买豆交易仍存在且 status=cancelled
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:5000/api/logs?page=1&page_size=20&module=bead_inventory" -Headers @{ Authorization = "Bearer <TOKEN>" }
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:5000/api/logs/<LOG_ID>/rollback" -Headers @{ Authorization = "Bearer <TOKEN>" }
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:5000/api/transactions?type=bead_purchase" -Headers @{ Authorization = "Bearer <TOKEN>" }
```

```powershell
# 5) 本地联调（用户执行并回传结果）
# 预期：系统日志页可执行豆仓回滚；交易页能看到已取消买豆交易
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

## 5. Manual Validation Checklist
1. 先做一笔豆仓出库（或损耗），确认生成买豆交易（`bead_purchase`）。
2. 在系统日志找到对应 `bead_inventory_outbound` / `bead_inventory_loss`，执行回滚。
3. 校验库存与流水：库存回补，新增反向流水，单号与原因可追溯。
4. 打开交易记录：原买豆交易仍存在，状态为“已取消（cancelled）”，不可重复取消。
5. 对 `bead_inventory_inbound`、`bead_inventory_stocktake` 各做一次回滚，验证方向与数值正确。
6. 对豆料创建/更新/删除各做一次，验证有快照时可回滚；构造旧日志验证“不可回滚原因”提示。
7. 回归充值/消费回滚，确认原流程未被破坏。

## 6. 风险与回滚策略
- 风险：历史日志缺少快照导致主数据回滚不可执行。
  - 应对：在日志元信息中明确 `rollback_reason`，不做不安全回滚。
- 风险：交易状态迁移遗漏导致旧数据显示异常。
  - 应对：初始化时统一回填 `completed`，查询层做空值兜底。
- 风险：库存反向流水与交易软撤销提交顺序不一致。
  - 应对：同事务提交，任何异常整体回滚。
- 回滚策略：
  - 代码层：先下线豆料主数据回滚，再下线豆仓库存回滚，最后恢复旧回滚类型集合。
  - 数据层：保留新增字段，功能降级为“不可回滚”而不是删库字段。

## 7. 进入 /do 门槛
- [x] 已关联 spec
- [x] 已给出 scope / out-of-scope
- [x] 步骤有序、可验证、可回退
- [x] 含 PowerShell 验证命令与预期结果
- [x] 明确“保留交易并标记已撤销”的执行路径
