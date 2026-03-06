# /plan：计费规则支持可扩展多人不限板套餐

- 计划日期：2026-03-06
- 对应规格：`specs/2026-03-06-billing-rules-extensible-multi-person-packages.md`

## 1. Scope / Out-of-scope
### Scope
- 将工作日/周末套餐从固定字段升级为“仅不限板可扩展套餐列表”。
- 保留单人限板规则，不扩展多人限板。
- 计费规则页支持不限板套餐新增/编辑/删除/启用禁用/排序。
- ActiveTimers、Customers、Transactions、计费计算逻辑改为读取动态不限板套餐。
- 兼容历史规则与历史套餐编码（如 `weekdayDoubleUnlimited`）。
- 允许套餐“禁用但保留”（不物理删除）。

### Out-of-scope
- 不实现“多人占多席位”的桌位模型扩展。
- 不改充值/豆仓/杂项库存等无关模块。
- 不新增依赖，不修改依赖声明与 lock 文件。

## 2. 实施前提
- `/do` 必须仅按此计划执行；若需改方案需先回 `/plan` 更新。
- 本次改造采用“读时归一化 + 写时新结构”保证平滑迁移。
- 迁移过程中必须保证计时结算金额可追溯、不会因规则缺失降为 0。

## 3. Implementation Steps (Ordered / Verifiable / Reversible)
### Step 1：后端规则结构升级与归一化
- 目标：`billing.py` 输出统一的新规则结构（`unlimited_packages + singleLimited`）。
- 变更位置：
  - `backend/routes/billing.py`
- 变更要点：
  - 为 `weekday/weekend` 增加 `unlimited_packages` 规范化函数（校验 `code/people_count/price/enabled/sort_order`）。
  - 保留并规范化 `singleLimited` 字段。
  - 将旧键（`singleUnlimited/doubleUnlimited/singleLimited`）自动映射到新结构。
  - `PUT /billing-rules` 支持新结构并阻止非法数据（重复 code、people_count<1、price<0）。
- 可验证：
  - `GET /billing-rules` 始终返回标准化 `unlimited_packages`。
  - 旧数据首次读取后可被正常保存。
- 可回退：
  - 保留兼容映射函数，回退前端前可继续输出旧键镜像。

### Step 2：计费规则页改为动态不限板套餐编辑
- 目标：Billing 页面不再依赖固定单/双人字段。
- 变更位置：
  - `frontend/src/views/Billing.vue`
- 变更要点：
  - 用列表渲染工作日/周末 `unlimited_packages`。
  - 提供新增、编辑、删除、启用禁用、排序操作。
  - `singleLimited` 保留为单独输入项（仅单人限板）。
  - 保存 payload 使用新结构，禁用但保留的数据仍提交。
- 可验证：
  - 页面可新增“工作日3人不限板”等套餐并保存。
  - 禁用套餐后刷新仍保留且状态正确。
- 可回退：
  - 保留旧字段映射读取，必要时恢复固定字段 UI。

### Step 3：统一套餐选项来源（计时表单/选择器）
- 目标：所有套餐下拉由规则数据驱动。
- 变更位置：
  - `frontend/src/utils/timerConsume.js`
  - `frontend/src/components/timers/TimerConsumeDialog.vue`
  - `frontend/src/views/ActiveTimers.vue`
  - `frontend/src/views/Customers.vue`
  - `frontend/src/views/Transactions.vue`
- 变更要点：
  - 移除或降级硬编码 `weekdaySingleUnlimited/weekdayDoubleUnlimited/...` 作为静态源。
  - 根据 `weekday.unlimited_packages`、`weekend.unlimited_packages` 构建选择项。
  - 保留并映射历史套餐 code，保证旧记录显示和编辑不报错。
  - 限板分支仅保留单人限板选项，不暴露多人限板。
- 可验证：
  - 新增套餐可在各页面选择器中出现。
  - 历史记录中的旧套餐编码仍能正常显示标签。
- 可回退：
  - 使用旧编码映射表回退到固定套餐选项。

### Step 4：计费计算器改为按动态套餐查价
- 目标：金额计算不再依赖固定 `weekdayType/weekendType` 枚举分支。
- 变更位置：
  - `frontend/src/utils/consumptionCalculator.js`
- 变更要点：
  - 新增“按 package code 查找不限板套餐价格”逻辑。
  - 无匹配时按兼容映射回退（旧 code -> 旧默认价）。
  - 保留限时套餐与单人限板原有计算路径。
  - 结算详情描述使用套餐 `label`。
- 可验证：
  - 选择新增多人不限板套餐后，基础费=套餐价格。
  - 限板与限时金额计算行为不变。
- 可回退：
  - 暂时恢复旧分支，保留新结构读取代码待后续启用。

### Step 5：联调回归与兼容验证
- 目标：确保新增能力可用且旧流程不回归。
- 校验重点：
  - 计费页新增多人不限板套餐 -> 保存 -> 刷新保留。
  - ActiveTimers/Customers/Transactions 可选新套餐并正确结算。
  - 单人限板仍可用且无多人限板入口。
  - 历史旧规则和旧套餐编码正常展示与结算。
- 可回退：
  - 按步骤粒度回退（先回退计算器/下拉，再回退规则页，最后回退后端归一化）。

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
..\.venv\Scripts\python.exe -m py_compile routes\billing.py
..\.venv\Scripts\python.exe -m py_compile routes\active_timers.py
```

```powershell
# 3) 前端构建检查（预期：构建成功，无 error）
Set-Location frontend
npm run build
```

```powershell
# 4) 接口冒烟（用户执行并回传输出）
# 预期：
# - GET 返回 weekday/weekend.unlimited_packages
# - PUT 新增套餐后 GET 可读回
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:5000/api/billing-rules" -Headers @{ Authorization = "Bearer <TOKEN>" }
Invoke-RestMethod -Method PUT -Uri "http://127.0.0.1:5000/api/billing-rules" -Headers @{ Authorization = "Bearer <TOKEN>" } -ContentType "application/json" -Body "<JSON_PAYLOAD>"
Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:5000/api/billing-rules" -Headers @{ Authorization = "Bearer <TOKEN>" }
```

```powershell
# 5) 前端联调（用户执行并回传结果）
# 预期：计费页可新增多人不限板套餐，并在结算流程可选且金额正确
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

## 5. Manual Validation Checklist
1. 在计费规则页新增“工作日3人不限板”与“周末4人不限板”，保存并刷新确认存在。
2. 将某个套餐设为禁用，刷新后确认仍保留但不可选（或标记禁用）。
3. 在 ActiveTimers 新建计时并选择新增套餐结算，确认基础费匹配套餐价格。
4. 在 Customers/Transactions 自动结算入口确认新增套餐可选，金额一致。
5. 确认限板选项仍仅单人限板，无多人限板入口。
6. 导入/使用旧规则数据，确认页面可加载并保存为新结构。

## 6. Risks & Mitigation
- 风险：页面遗漏改造导致规则页与结算页套餐不一致。
  - 应对：统一套餐选项构建函数，多个页面复用。
- 风险：历史 code 无法映射导致显示 “-” 或算价失败。
  - 应对：维护旧 code 映射表和默认兜底标签/价格。
- 风险：套餐列表为空导致不可结算。
  - 应对：后端校验每个时段至少一个启用不限板套餐。

## 7. Enter /do Gate
- [x] 已关联 spec
- [x] 已定义 scope / out-of-scope
- [x] 步骤有序、可验证、可回退
- [x] 包含 PowerShell 验证命令与预期
- [x] 已落实“仅不限板扩展 + 可禁用保留”边界
