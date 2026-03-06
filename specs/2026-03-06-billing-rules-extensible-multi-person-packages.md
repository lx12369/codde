# 1. Summary

将计费规则从“固定单人/双人字段”升级为“可扩展不限板套餐列表”，支持在计费规则页面新增多人不限板套餐（如 3 人、4 人等）并在计时消费全链路生效，避免后续每次新增人数都要改代码。

# 2. Goals / Non-goals

## Goals

- 计费规则页支持动态新增、编辑、删除、排序工作日/周末“多人不限板”套餐项，不再仅限当前单人/双人固定项。
- 套餐项至少包含：唯一编码、展示名称、人数、价格、所属时段（工作日/周末）、是否启用。
- ActiveTimers、Customers、Transactions 中的套餐选择与计费逻辑使用动态套餐项。
- 保存规则后，新增套餐可立即用于计时结算，金额计算正确。
- 向后兼容历史规则（`singleUnlimited/doubleUnlimited/singleLimited`）与历史交易展示。
- 保持现有限时套餐（1h/2h）与加班费规则不变。
- 保持“单人不限时限板”规则继续存在且不纳入多人扩展。

## Non-goals

- 本期不改动桌位占用模型为“按人数占多席位”的复杂模型（例如 3 人自动占 3 个座位）。
- 本期不支持“多人限板”套餐，仅扩展“多人不限板”套餐。
- 本期不改动会员充值/普通消费/豆仓模块逻辑。
- 本期不引入新依赖，不修改依赖声明与 lock 文件。

# 3. Current State & Constraints

## Current behavior/state

- 计费规则后端结构固定：
  - `backend/routes/billing.py` 中 `DEFAULT_RULES.weekday/weekend` 仅有 `singleUnlimited/doubleUnlimited/singleLimited`。
- 计费规则页面固定字段：
  - `frontend/src/views/Billing.vue` 直接绑定 `weekdaySingleUnlimited`、`weekdayDoubleUnlimited`、`weekendDoubleUnlimited` 等固定键。
- 套餐选项硬编码：
  - `frontend/src/utils/timerConsume.js` 中 `timerPackagePlanOptionsByType` 写死固定套餐编码。
  - `frontend/src/utils/consumptionCalculator.js` 按 `weekdayType/weekendType` 的固定枚举分支计费。
- 多处页面依赖固定套餐编码或文案：
  - `frontend/src/views/ActiveTimers.vue`
  - `frontend/src/views/Customers.vue`
  - `frontend/src/views/Transactions.vue`

## Environment/platform constraints

- Windows + PowerShell。
- 前端：Vue 3 + Vite。
- 后端：Flask + SQLAlchemy + SQLite。

## Risk constraints

- 不自动执行依赖安装/升级。
- 兼容历史规则数据时，不能因缺字段导致计费页面崩溃或金额回退为 0。
- 动态套餐引入后，需保证旧套餐编码仍可识别，避免历史计时数据失效。

# 4. Requirements

## Functional requirements

### P0

- 后端计费规则模型升级（保持 `billing_rules` 表不变，升级 `rule_data` 结构）：
  - `weekday`、`weekend` 支持 `unlimited_packages` 列表（仅不限板套餐）。
  - `singleLimited` 作为单人限板价格继续保留（不做多人化）。
  - 每个套餐项包含：`id`、`code`、`label`、`people_count`、`price`、`enabled`、`sort_order`。
- 后端 `GET /api/billing-rules` 返回规范化套餐列表：
  - 若检测到旧结构（`singleUnlimited/doubleUnlimited/singleLimited`），自动映射为 `unlimited_packages + singleLimited` 并兼容输出。
- 后端 `PUT /api/billing-rules` 支持更新套餐列表并校验：
  - `code` 唯一、`people_count >= 1`、`price >= 0`、排序值有效。
- 计费规则页面支持套餐列表管理：
  - 新增/编辑/删除/启用禁用/排序（仅不限板套餐列表）。
  - 至少保留 1 个启用套餐（按工作日、周末各自维度）。
- 动态套餐接入计时消费流程：
  - ActiveTimers/Customers/Transactions 的套餐下拉从规则数据生成。
  - 结算金额按选中不限板套餐价格计算，不再依赖固定 `single|double` 分支。
  - 限板场景继续使用单人限板规则，不出现“多人限板”选项。

### P1

- 历史兼容能力：
  - 旧套餐编码（如 `weekdayDoubleUnlimited`）仍能在展示和结算中识别。
  - 旧数据未提供 `unlimited_packages` 时，前端依然可正常展示并可保存回新结构。
- 交易描述与页面展示中使用套餐 `label`（而非硬编码文案）。
- 允许套餐“禁用但保留”（不物理删除）作为历史记录兼容策略。

### P2

- 计费规则页面支持套餐复制（例如“复制工作日双人套餐改成三人”）以降低录入成本。

## Non-functional requirements

- 稳定性：旧规则数据可自动归一化，不抛异常。
- 可维护性：套餐定义统一来源于规则数据，避免多处硬编码。
- 可审计性：保存规则仍写 `billing_rule_update` 日志，包含变更范围摘要。

## Compatibility/migration requirements

- 规则迁移采用“读时归一化 + 写时新结构”：
  - 读取旧 `weekday/weekend` 固定键时自动转换成 `unlimited_packages + singleLimited`。
  - 写回时持久化为 `unlimited_packages + singleLimited` 结构，同时可选保留旧键镜像（过渡期兼容）。
- 历史交易/计时记录若带旧 `packagePlan`，需有映射表兜底，不影响显示和结算。

# 5. Design

## Overall approach

- 以后端 `billing.py` 为规则“单一事实源”，统一输出标准化套餐列表。
- 前端所有套餐选项（Billing/ActiveTimers/Customers/Transactions）改为消费该标准化结构。
- 计费计算器改为“按不限板套餐 code 查价”模式，删除固定 `single/double` 分支依赖；单人限板保留独立价格路径。

## Key decisions

- 不新增数据库表，继续使用 `BillingRule.rule_data` JSON 承载，降低迁移成本。
- 保留旧编码映射层，保证历史数据和现网行为平滑过渡。
- 套餐最小模型固定为“人数 + 价格 + 标签 + 启用状态”，且仅用于不限板场景。

## Alternatives and trade-offs

- 方案 A（推荐）：`rule_data` 内引入动态 `packages` 列表
  - 优点：改动集中、迁移轻量、上线风险较低。
  - 缺点：套餐关系和约束主要靠应用层校验。
- 方案 B：新增独立套餐表（关系化）
  - 优点：数据结构更规范、查询更灵活。
  - 缺点：涉及数据库迁移、模型变更更大，不符合本期“快速扩展套餐”目标。

## Impact scope

- 后端：
  - `backend/routes/billing.py`
- 前端：
  - `frontend/src/views/Billing.vue`
  - `frontend/src/utils/consumptionCalculator.js`
  - `frontend/src/utils/timerConsume.js`
  - `frontend/src/views/ActiveTimers.vue`
  - `frontend/src/views/Customers.vue`
  - `frontend/src/views/Transactions.vue`
  - `frontend/src/components/timers/TimerConsumeDialog.vue`（按需）

# 6. Acceptance Criteria

- 在计费规则页新增“工作日三人不限时不限板（例如 ¥149.9）”并保存成功。
- 刷新页面后新增套餐仍存在，且在 ActiveTimers/Customers/Transactions 的套餐选择中可见。
- 选择新增套餐结算时，基础费用等于套餐价格，交易金额与说明正确。
- 限板选项仍仅保留单人限板，不出现多人限板选项。
- 旧套餐（单人/双人/限板）行为保持不变，历史记录可正常展示。
- 从旧结构规则数据启动时，页面可正常加载并在保存后转为新结构。
- 规则更新后系统日志保留 `billing_rule_update` 记录。

# 7. Validation Strategy

候选验证命令（PowerShell）：

```powershell
# 1) 后端语法检查（预期：无语法错误）
Set-Location backend
..\.venv\Scripts\python.exe -m py_compile routes\billing.py
..\.venv\Scripts\python.exe -m py_compile routes\active_timers.py
```

```powershell
# 2) 前端构建检查（预期：构建成功，无 error）
Set-Location frontend
npm run build
```

```powershell
# 3) 计费规则接口冒烟（用户执行并回传输出）
# 预期：weekday/weekend 返回 packages 列表；PUT 后新增套餐可读回
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:5000/api/billing-rules" -Headers @{ Authorization = "Bearer <TOKEN>" }
Invoke-RestMethod -Method PUT -Uri "http://127.0.0.1:5000/api/billing-rules" -Headers @{ Authorization = "Bearer <TOKEN>" } -ContentType "application/json" -Body "<JSON_PAYLOAD>"
```

```powershell
# 4) 前端联调（用户执行并回传结果）
# 预期：计费页可新增套餐并在计时结算流程可选
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

若本地环境命令受依赖限制，由用户执行并回传输出后继续。

# 8. Risks & Rollback

## Risks

- 动态结构改造遗漏页面，会出现“计费页新增成功但结算页不可选”的不一致。
- 历史字符串解析（交易描述反推套餐）与新套餐标签可能不一致，导致部分编辑场景推断失败。
- 旧规则自动迁移逻辑若不严谨，可能把异常数据写成无效套餐。

## Rollback

- 代码回滚：恢复固定套餐字段分支（`single/double/singleLimited`）。
- 数据降级：保留 `unlimited_packages` 数据但前端仅读取既有固定套餐映射项。
- 功能降级：暂时关闭“新增套餐”入口，仅保留已存在套餐编辑。

# 9. Open Questions

None

# 10. References

- `backend/routes/billing.py`
- `frontend/src/views/Billing.vue`
- `frontend/src/utils/consumptionCalculator.js`
- `frontend/src/utils/timerConsume.js`
- `frontend/src/views/ActiveTimers.vue`
- `frontend/src/views/Customers.vue`
- `frontend/src/views/Transactions.vue`
- `frontend/src/components/timers/TimerConsumeDialog.vue`

---

## /spec Completion Checklist

- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
