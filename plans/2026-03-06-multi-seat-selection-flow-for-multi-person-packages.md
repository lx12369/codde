# /plan：多人套餐多座位选择与快速选座交互升级

- 计划日期：2026-03-06
- 对应规格：`specs/2026-03-06-multi-seat-selection-flow-for-multi-person-packages.md`

## 1. Scope / Out-of-scope
### Scope
- 将计时备注从“单附加座位（`secondTableNo`）”升级为“多附加座位（`extraTableNos`）”并保持兼容。
- 多人套餐按 `people_count = N` 强约束座位数：主座位 1 个 + 附加座位 `N-1` 个。
- 快速选座交互升级为：右键首座位、左键依次选中、最后一座位双击左键确认提交。
- ActiveTimers 的开台、编辑、占座冲突检测、提醒播报统一改为消费完整座位集合。
- TimerConsumeDialog 与相关工具函数支持多人附加座位编辑，不再固定“第二座位”。
- 兼容历史 `secondTableNo` 记录读取与展示。

### Out-of-scope
- 不改数据库表结构，不新增 `active_timers` 字段。
- 不改计费金额规则与套餐价格计算。
- 不改房间布局样式/分区结构。
- 不引入新依赖，不修改依赖声明与 lock 文件。

## 2. 实施前提
- `/do` 必须仅按本计划执行；若实现中需要改方案，先回 `/plan` 更新。
- 本次采用“读时兼容 + 写时新结构”：
  - 新写入 `extraTableNos`；
  - 过渡期保留 `secondTableNo = extraTableNos[0]` 镜像。
- 必须确保历史仅 `secondTableNo` 的数据无回归。

## 3. Implementation Steps (Ordered / Verifiable / Reversible)
### Step 1：统一多座位数据契约与工具函数
- 目标：让座位集合能力先独立可复用。
- 变更位置：
  - `frontend/src/utils/timerConsume.js`
  - `frontend/src/views/ActiveTimers.vue`（解析/序列化辅助）
- 变更要点：
  - 引入 `extraTableNos[]` 读写规范。
  - 新增/调整归一化函数：读取时优先 `extraTableNos`，回退 `secondTableNo`。
  - 写入 notes 时同时输出 `extraTableNos` 与 `secondTableNo`（镜像首附加座位）。
  - 校验规则改为基于完整座位集合（格式、重复、数量）。
- 可验证：
  - 任意 N 人套餐可在内存模型中形成 N 个不重复座位。
  - 老数据仍可解析出至少 2 座位（主座位 + secondTableNo）。
- 可回退：
  - 保留 `secondTableNo` 路径，回退为双座位逻辑时不影响历史记录。

### Step 2：升级快速选座状态机（右键首座、末位双击确认）
- 目标：满足新交互并避免误提交。
- 变更位置：
  - `frontend/src/views/ActiveTimers.vue`
- 变更要点：
  - 将 `pendingDoubleSeatStart` 扩展为“多人选座上下文”（已选列表、目标人数、确认阶段）。
  - 右键首座位进入选择模式并锁定首座位。
  - 左键处理中间座位追加；到最后一座位时进入 `pending_final_confirm`。
  - 仅对最后一座位双击左键触发提交；单击只预选。
  - 增加取消选择入口（Esc/按钮）。
- 可验证：
  - N=3 时：右键+左键+双击左键才能提交。
  - N=4/5 时：必须选够并双击最后一座位才能提交。
- 可回退：
  - 可独立回退为“右键+左键第二座即提交”旧流程，不影响 Step 1 数据兼容。

### Step 3：开台/编辑/占座冲突检测改为完整座位集合
- 目标：任何附加座位都纳入冲突校验。
- 变更位置：
  - `frontend/src/views/ActiveTimers.vue`
  - `frontend/src/components/timers/TimerConsumeDialog.vue`
- 变更要点：
  - `validateAddForm` / `validateEditForm` 基于 `occupiedTableNos` 全量校验。
  - `isTableNoOccupied` 与 `getTimerOccupiedTableNos` 全链路支持 `extraTableNos`。
  - 编辑弹窗按人数动态渲染附加座位输入组。
- 可验证：
  - 任一附加座位冲突时开台/编辑失败并提示具体座位。
  - 计时卡片显示完整座位列表。
- 可回退：
  - 可只回退动态渲染层，保留底层 `occupiedTableNos` 逻辑继续兼容。

### Step 4：全局提醒与布局层解析兼容升级
- 目标：提醒播报与全局占座视图不丢第 3+ 座位。
- 变更位置：
  - `frontend/src/layouts/MainLayout.vue`
- 变更要点：
  - `parseTimerNotes` 支持 `extraTableNos`。
  - `isDoublePackagePlan` 等“多座位判断”统一切到人数/座位集合判断。
  - 提醒播报桌号使用完整座位集合拼接。
- 可验证：
  - 多人计时提醒中可见完整座位集合。
  - 历史 `secondTableNo` 计时提醒仍正常。
- 可回退：
  - 可回退提醒显示策略，仅保留主座位展示，不影响计时数据本体。

### Step 5：联调回归与兼容验证
- 目标：确认 N 人场景与历史数据双稳定。
- 校验重点：
  - N=3/4/5 套餐快速选座流程均可完成。
  - 最后一座位非双击不得提交。
  - 历史记录读取/编辑不报错。
  - 占座冲突与提醒展示一致。
- 可回退：
  - 先回退 Step 4（提醒）→ Step 2（交互）→ Step 3（表单）→ Step 1（数据契约）。

## 4. Validation Commands (PowerShell) + Expected Results
```powershell
# 1) 工具可用性（预期：返回命令路径）
Get-Command python
Get-Command node
Get-Command npm
```

```powershell
# 2) 后端语法检查（预期：无输出/退出码 0）
Set-Location backend
..\.venv\Scripts\python.exe -m py_compile routes\active_timers.py
```

```powershell
# 3) 前端构建检查（预期：构建成功，无 error）
Set-Location frontend
npm run build
```

```powershell
# 4) 前端联调（用户执行并回传结果）
# 预期：N 人套餐（3/4/5 及以上）按人数完整选座；最后一座位需双击左键提交
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

## 5. Manual Validation Checklist
1. 在计费规则中配置并启用 3/4/5 人套餐。
2. 进入房间座位图：右键首座位，左键依次选座，最后一座位双击确认，验证可开台。
3. 对任意 N 人套餐，最后一座位仅单击时不得提交。
4. 制造附加座位冲突，确认被拦截并提示冲突座位。
5. 打开计时编辑，确认可查看/调整完整附加座位并保存。
6. 观察提醒弹窗与语音，确认显示完整座位集合。
7. 抽查历史仅 `secondTableNo` 记录，确认显示与编辑正常。

## 6. Risks & Mitigation
- 风险：双击确认可发现性不足，用户误认为无响应。
  - 应对：在选座状态条增加“最后一步需双击确认”高亮提示。
- 风险：`extraTableNos` 与 `secondTableNo` 双写不一致。
  - 应对：统一单入口序列化函数，禁止分散手写 notes。
- 风险：布局页与业务页解析规则不一致。
  - 应对：抽公共解析函数，MainLayout 与 ActiveTimers 共用。

## 7. Enter /do Gate
- [x] 已关联 spec
- [x] 已定义 scope / out-of-scope
- [x] 步骤有序、可验证、可回退
- [x] 包含 PowerShell 验证命令与预期
- [x] 已落实“适配任意多人（N人）”边界
