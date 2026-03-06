# 1. Summary

修复多人套餐（`people_count = N, N>2`）无法完整选座的问题，并将多人选座交互统一为“右键首座位 -> 左键依次选中中间座位 -> 最后一个座位双击左键确认”，确保多人套餐可完整落地到计时开始、占座判定与提醒链路。

该改动可消除当前多人套餐（>2人）在实操中的阻断，避免新增套餐规则后前台无法按人数正确开台。

# 2. Goals / Non-goals

## Goals

- 支持按套餐人数（`people_count`）选择多座位，不再仅支持“主座位 + 第二座位”。
- 支持多人套餐通用场景：按 `N` 人套餐可完成 `N` 个座位选择并成功开始计时（含 3/4/5 人及以上）。
- 快速选座流程改为：
  - 右键选第一个座位进入多人选座模式；
  - 左键按顺序选择后续座位；
  - 到最后一个座位时必须“双击左键”才确认提交。
- 开台、编辑、占座冲突检测、全局提醒统一基于“完整座位集合”运行。
- 兼容历史计时记录（仅有 `secondTableNo`）的显示、提醒与编辑。

## Non-goals

- 本期不改动数据库表结构（不新增列/表）。
- 本期不改动计费金额计算规则（只处理选座与占座链路）。
- 本期不改造“桌区布局配置”与房间 UI 结构。
- 本期不引入新依赖，不修改依赖声明与 lock 文件。

# 3. Current State & Constraints

## Current behavior/state

- 计时备注结构当前仅支持一个附加座位：`secondTableNo`。
  - 相关路径：
    - `frontend/src/views/ActiveTimers.vue`
    - `frontend/src/components/timers/TimerConsumeDialog.vue`
    - `frontend/src/utils/timerConsume.js`
    - `frontend/src/layouts/MainLayout.vue`
- 快速选座状态机仅支持两座位闭环：右键首座后，左键第二座即直接进入提交流程。
  - 相关路径：`frontend/src/views/ActiveTimers.vue`
- 占座与语音提醒逻辑按“主座位 + secondTableNo”处理，不支持第 3+（即 `N>2`）座位。
  - 相关路径：
    - `frontend/src/views/ActiveTimers.vue`
    - `frontend/src/layouts/MainLayout.vue`
- 后端 `active_timers` 仅对主座位字段 `table_no`做服务端唯一性校验；附加座位完全依赖前端备注解析。
  - 相关路径：`backend/routes/active_timers.py`

## Environment/platform constraints

- Windows + PowerShell。
- 前端：Vue 3 + Vite。
- 后端：Flask + SQLAlchemy + SQLite。

## Risk constraints

- 不能破坏历史备注格式读取（`secondTableNo` 仍需可识别）。
- 不能引入“多人套餐已开始但占座未完整记录”的不一致状态。
- 需保证交互升级后仍可快速开台，避免误触导致操作失败率上升。

# 4. Requirements

## Functional requirements

### P0

- 定义统一“附加座位数组”数据契约（建议字段：`extraTableNos`），用于表达主座位之外的所有座位。
- 兼容写入策略：
  - 新记录写入 `extraTableNos`；
  - 兼容镜像 `secondTableNo = extraTableNos[0] || ''`（过渡期）。
- 兼容读取策略：
  - 优先读取 `extraTableNos`；
  - 若不存在则回退读取 `secondTableNo`。
- 多人座位数量约束：
  - 设套餐人数为 `N`，则必须有 `N` 个不重复座位（主座位 1 个 + 附加座位 `N-1` 个）。
- 快速选座交互（房间座位图）升级：
  - 右键首座位：进入多人选座模式并记录首座位；
  - 左键：依次选择后续座位；
  - 最后一个座位：必须双击左键确认提交；单击仅预选不提交。
- 开台与编辑校验升级：
  - 校验全部座位格式、重复、占用冲突；
  - 错误提示明确指出冲突座位。
- 占座与提醒升级：
  - `getTimerOccupiedTableNos` 等逻辑基于完整座位集合；
  - 全局提醒/播报展示所有占用座位。

### P1

- `TimerConsumeDialog` 与 ActiveTimers 编辑弹窗支持按人数动态渲染“附加座位选择器”（不限于第二座位）。
- 交易记录与计时展示文案在多座位场景下展示完整座位列表（例如 `A桌1号 / A桌2号 / A桌3号`）。
- 历史数据编辑后保存为新结构（含 `extraTableNos`），但旧数据读取不报错。

### P2

- 快速选座模式增加显式状态提示（已选数量 / 目标数量 / 最后一步需双击）。
- 支持取消当前多人选座（Esc 或显式“取消选择”按钮）。

## Non-functional requirements

- 可靠性：同一时刻不得出现同座位被多个活跃计时占用。
- 可维护性：座位集合解析/归一化集中在工具函数，避免页面分散硬编码。
- 易用性：双击确认只用于“最后一座位”，并提供明确提示，降低误操作。

## Compatibility/migration requirements

- 保持历史备注兼容：仅 `secondTableNo` 的记录必须可正常读取与展示。
- 新增字段迁移采用“读时兼容 + 写时新结构”。
- 过渡期保留 `secondTableNo` 镜像，降低旧逻辑残留风险。

# 5. Design

## Overall approach

- 在前端建立统一座位集合模型：
  - `primaryTableNo`（主座位）
  - `extraTableNos[]`（附加座位）
  - `occupiedTableNos = [primaryTableNo, ...extraTableNos]`
- 快速选座以状态机实现：
  - `idle -> selecting -> pending_final_confirm -> confirmed`。
- 计时备注 JSON 扩展 `extraTableNos`，并继续维护 `secondTableNo` 兼容字段。

## Key decisions

- 不改 DB 结构，仍使用 `notes` 存储扩展字段，降低迁移成本。
- 将“最后一步双击确认”限定在快速选座流程，不影响普通表单选择。
- 占座、校验、提醒统一改为消费 `occupiedTableNos`，避免遗漏任意多座位（`N>2`）。

## Alternatives and trade-offs

- 方案 A（推荐）：`notes` 扩展 `extraTableNos`（兼容 `secondTableNo`）
  - 优点：改动集中于前端和备注解析，发布风险可控。
  - 缺点：附加座位冲突校验仍主要靠前端聚合状态。
- 方案 B：后端新增专用字段/表存储多座位
  - 优点：服务端约束更强。
  - 缺点：涉及模型/数据迁移，超出本期“快速修复 + 交互升级”目标。

## Impact scope

- 前端：
  - `frontend/src/views/ActiveTimers.vue`
  - `frontend/src/components/timers/TimerConsumeDialog.vue`
  - `frontend/src/utils/timerConsume.js`
  - `frontend/src/layouts/MainLayout.vue`
- 后端（按需最小改动）：
  - `backend/routes/active_timers.py`（若需补强服务端备注字段校验）

# 6. Acceptance Criteria

- 已新增并启用多人套餐（例如 3/4/5 人）时，可完成对应数量座位选择并成功开始计时。
- 快速选座流程满足：
  - 右键选择首座位；
  - 左键可依次选择中间座位；
  - 最后一个座位必须双击左键才提交。
- 若套餐人数为 `N`，仅选择到 `N-1` 个座位不得提交；必须在第 `N` 个座位执行双击左键才提交。
- 所有已选座位必须参与占用冲突校验；任一座位冲突都阻止提交并给出错误提示。
- 计时列表、编辑弹窗、提醒播报都能正确识别并展示 `N` 座位（`N>2`）。
- 历史仅含 `secondTableNo` 的记录可正常显示和编辑，不报错。

# 7. Validation Strategy

候选验证命令（PowerShell）：

```powershell
# 1) 后端语法检查（预期：无语法错误）
Set-Location backend
..\.venv\Scripts\python.exe -m py_compile routes\active_timers.py
```

```powershell
# 2) 前端构建检查（预期：构建成功，无 error）
Set-Location frontend
npm run build
```

```powershell
# 3) 前端联调（用户执行并回传结果）
# 预期：多人套餐（3/4/5人及以上）可按人数完整选座；最后一步需双击左键才能提交
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

手工验证要点：
1. 新增 3 人、4 人、5 人套餐后，分别在房间图按流程选足座位，确认都可开台。
2. 对任意 `N` 人套餐，最后座位仅单击时不得提交，双击才提交。
3. 编辑计时记录时可维护 `N` 座位且冲突校验生效。
4. 提醒弹窗与语音显示完整座位集合（不丢失中间座位）。

# 8. Risks & Rollback

## Risks

- 双击确认交互不明显，可能导致用户误判“点击无效”。
- 历史备注解析与新字段并存期间，若优先级处理不当会出现座位丢失。
- 多处占座逻辑若改造不全，可能出现“列表显示三座位但冲突检测仍按两座位”。

## Rollback

- 交互回退：恢复“右键首座位 + 左键第二座位即提交”的旧流程。
- 数据回退：继续仅读取 `secondTableNo`，忽略 `extraTableNos`。
- 范围回退：先保留多座位数据结构，仅暂停快速选座状态机升级。

# 9. Open Questions

None

# 10. References

- `frontend/src/views/ActiveTimers.vue`
- `frontend/src/components/timers/TimerConsumeDialog.vue`
- `frontend/src/utils/timerConsume.js`
- `frontend/src/layouts/MainLayout.vue`
- `backend/routes/active_timers.py`

---

## /spec Completion Checklist

- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
