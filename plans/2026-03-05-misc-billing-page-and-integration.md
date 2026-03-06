# /plan：运营管理新增杂项计费页面并接入计费系统

- 计划日期：2026-03-05
- 对应规格：[specs/2026-03-05-misc-billing-page-and-integration.md](/C:/Users/PC/Desktop/codde/specs/2026-03-05-misc-billing-page-and-integration.md)

## 1. Scope / Out-of-scope
### Scope
- 在“运营管理”分组新增“杂项计费”页面入口（`/misc-billing`）。
- 基于现有 `/api/billing-rules` 扩展 `misc` 规则（登录用户可写）。
- 杂项规则支持新增、编辑、启停、删除、排序保存。
- 计费引擎支持杂项费用（数量仅整数），并将杂项费用并入消费总额。
- 在 `ActiveTimers.vue`、`Customers.vue`、`Transactions.vue` 三个消费入口接入杂项选择与预览。
- 消费提交金额与描述包含杂项明细。

### Out-of-scope
- 不新增数据库表与迁移脚本。
- 不改变充值、余额、交易撤销主流程。
- 不新增依赖或修改依赖/锁文件。
- 不新增交易主类型（仍按 `consumption` 入账）。

## 2. Implementation Steps (Ordered / Verifiable / Reversible)
### Step 1：后端扩展 billing-rules 的 misc 规则块
- 目标：`backend/routes/billing.py` 支持 `misc` 读写与归一化。
- 变更要点：
  - 新增 `DEFAULT_RULES['misc']`（建议结构：`{ items: [] }`）。
  - 新增 `normalize_misc_rule_data`，对规则字段做清洗（名称、单价、单位、启停、排序）。
  - `GET /billing-rules` 返回 `misc`，旧数据自动补齐。
  - `PUT /billing-rules` 支持仅提交 `misc` 局部更新，兼容现有规则更新流程。
- 可验证：
  - 请求 `GET /api/billing-rules` 返回 `misc.items`。
  - 提交 `PUT /api/billing-rules` 仅含 `misc` 后再次 GET 可读回。
- 可回滚：
  - 移除 `misc` 归一化与更新逻辑，恢复原五类规则。

### Step 2：前端增加杂项计费页面入口与 API 封装
- 目标：在导航与路由中接入页面，并补充 `billingApi` 调用方法。
- 变更要点：
  - `frontend/src/layouts/MainLayout.vue` 新增“杂项计费”菜单（`operation` 分组）。
  - `frontend/src/router/index.js` 新增 `/misc-billing` 路由。
  - `frontend/src/api/index.js` 增加杂项规则读取/保存封装（复用 `/billing-rules`）。
- 可验证：
  - 登录后侧边栏出现“杂项计费”，点击可进入页面。
- 可回滚：
  - 删除新增菜单、路由和 API 封装，导航恢复原样。

### Step 3：实现杂项计费页面（规则管理）
- 目标：新增 `frontend/src/views/MiscBilling.vue` 并完成规则 CRUD 交互。
- 变更要点：
  - 页面提供：规则列表、添加、编辑、启停、删除、排序（上下移动或排序值）。
  - 字段校验：名称非空、单价 >= 0、单位非空。
  - 保存时提交 `misc.items`，并显示成功/失败反馈。
- 可验证：
  - 新增“钥匙串（¥5/个）”并刷新后仍存在。
  - 修改/停用/删除后状态与接口返回一致。
- 可回滚：
  - 移除 `MiscBilling.vue` 和其路由入口。

### Step 4：扩展计费引擎支持杂项费用（整数数量）
- 目标：在 `frontend/src/utils/consumptionCalculator.js` 增加 `miscFee` 计算。
- 变更要点：
  - `normalizeBillingRules` 增加 `misc` 默认结构。
  - `calculateConsumptionAmount` 新增 `miscSelections` 输入处理。
  - 数量按整数校验（小数/非法视为无效并由上层拦截）。
  - 返回结构新增 `miscFee` 与杂项明细，`total` 包含 `miscFee`。
  - `buildConsumptionDescription` 合并输出杂项摘要文本。
- 可验证：
  - 规则“钥匙串 ¥5/个”，数量 2 时 `miscFee = 10`，总额增加 10。
- 可回滚：
  - 回退 `consumptionCalculator.js` 相关新增字段与计算分支。

### Step 5：接入三个消费入口（正在计时/客户管理/交易记录）
- 目标：三处消费表单一致支持杂项数量输入与预览展示。
- 变更要点：
  - `frontend/src/views/ActiveTimers.vue`：
    - 加载启用杂项规则并渲染数量输入（整数）。
    - 结算预览展示 `miscFee`，提交描述带杂项明细。
  - `frontend/src/views/Customers.vue` 与 `frontend/src/views/Transactions.vue`：
    - 自动消费表单新增杂项输入区域（整数）。
    - 预览与提交金额统一接入 `miscFee`。
  - 非法数量（小数、负数、非数字）在前端阻断并提示。
- 可验证：
  - 三个入口都能录入杂项数量并看到金额变化。
  - 提交后交易金额正确，描述包含“钥匙串xN”。
- 可回滚：
  - 移除三个页面的杂项输入与 `miscSelections` 传参，恢复改造前行为。

### Step 6：回归校验与收口
- 目标：确认未引入计费回归，文案与权限满足规格。
- 校验点：
  - 不使用杂项时，计费结果与改造前一致。
  - 登录用户可写杂项规则。
  - 杂项数量仅允许整数。
- 可回滚：
  - 按步骤粒度回滚最近变更（优先回滚页面接入，再回滚引擎与后端）。

## 3. Validation Commands (PowerShell) + Expected Results
```powershell
# 1) 工具检查
Get-Command node
Get-Command npm
Get-Command python
# 预期：返回可执行路径

# 2) 后端语法检查
python -m py_compile backend\routes\billing.py
# 预期：无输出，退出码 0

# 3) 前端关键文件语法检查
node --check frontend\src\utils\consumptionCalculator.js
node --check frontend\src\api\index.js
node --check frontend\src\router\index.js
# 预期：无语法报错

# 4) 前端构建校验
cd frontend; npm run build
# 预期：Vite build 成功，无 error
```

## 4. Manual Validation Checklist
1. 进入“杂项计费”页面，新增规则 `钥匙串`，单价 `5`，单位 `个`，启用。
2. 分别在“正在计时”“客户管理自动消费”“交易记录自动消费”输入 `钥匙串=2`，确认杂项费用为 `¥10` 且总额同步增加。
3. 将杂项数量输入为 `1.5` 或非数字，系统应拦截提交并给出提示。
4. 提交一笔消费后在交易记录确认：金额包含杂项费用，描述含杂项明细。
5. 停用该规则后，新的消费表单不再显示该杂项输入项。
6. 不填写任何杂项执行消费，确认金额与旧逻辑一致。

## 5. User-run Commands (Only if environment is missing dependencies)
```powershell
cd frontend; npm install
cd backend; ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
- 说明：仅在本地缺依赖导致无法执行验证时由用户手动运行并回贴输出。
