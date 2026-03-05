# /plan：入库记账接入交易记录 & 交易记录归入运营管理

- 计划日期：2026-03-05
- 对应规格：`specs/2026-03-05-bead-money-in-transactions-and-operation-group.md`

## 1. Scope / Out-of-scope
### Scope
- 豆仓“入库（买豆）”成功时，按市场价自动换算金额并写入交易记录（真实交易）。
- 交易记录页面可展示并筛选这类“买豆支出”记录。
- 损耗/常规出库/盘点调整不写入交易记录，仅保留库存流水。
- 侧边栏“交易记录”菜单移动到“运营管理”分组。

### Out-of-scope
- 不改会员充值/消费核心业务流程。
- 不新增财务总账、利润报表、导出能力。
- 不修改依赖声明与锁文件。

## 2. Implementation Steps (Ordered / Verifiable / Reversible)
### Step 1：后端入库联动记账（核心）
- 目标：在 `backend/routes/bead_inventory.py` 的入库事务中增加交易写入。
- 变更要点：
  - 读取豆料 `market_price_per_500g`。
  - 计算入库金额：`amount = grams * (market_price_per_500g / 500)`，按现有金额精度规则保留。
  - 写入交易表（建议类型：`bead_purchase`，描述含豆料与库存流水单号）。
  - 与入库保持同事务提交（失败回滚），避免“入库成功但交易缺失”。
- 可验证：完成一次入库后，数据库/接口中可查到对应交易。
- 可回滚：移除入库联动写交易逻辑，恢复仅库存流水。

### Step 2：后端交易查询兼容新类型
- 目标：`backend/routes/transactions.py` 支持 `bead_purchase` 查询与返回展示。
- 变更要点：
  - 交易列表筛选 `type` 能包含新类型。
  - 返回字段兼容现有前端结构（时间、金额、描述、操作员、状态等）。
- 可验证：`/transactions` 携带 `type=bead_purchase` 可返回数据。
- 可回滚：撤销对新类型筛选与映射的扩展。

### Step 3：前端交易记录页接入新类型
- 目标：`frontend/src/views/Transactions.vue` 展示“买豆支出”记录。
- 变更要点：
  - 交易类型筛选增加“买豆支出”（value 与后端一致）。
  - 表格/卡片类型标签、颜色、文案适配新类型。
  - 详情弹窗可读到豆料与库存单号信息（来自描述或扩展字段）。
- 可验证：筛选“买豆支出”后仅看到入库交易。
- 可回滚：删除新类型 UI 映射，恢复原两类交易视图。

### Step 4：菜单分组迁移到运营管理
- 目标：`frontend/src/layouts/MainLayout.vue` 中“交易记录”项归到 `operation`。
- 变更要点：
  - 将 `transactions` 菜单项的 `group` 从 `member` 调整为 `operation`。
  - 保持路由路径 `/transactions` 不变。
- 可验证：侧边栏“交易记录”在“运营管理”分组显示。
- 可回滚：改回原分组。

### Step 5：回归与边界校验
- 目标：确保新逻辑不破坏旧交易流程。
- 校验点：
  - 入库：生成交易。
  - 损耗/常规出库/盘点：不生成交易。
  - 会员充值/消费/取消交易：行为不变。
- 可回滚：若发现回归，按步骤粒度回滚最近变更。

## 3. Validation Commands (PowerShell) + Expected Results
```powershell
# 1) 后端语法检查
python -m py_compile backend\routes\bead_inventory.py
python -m py_compile backend\routes\transactions.py
python -m py_compile backend\models\models.py
# 预期：无输出/退出码 0

# 2) 前端构建
cd frontend; npm run build
# 预期：build 成功，无 error
```

## 4. Manual Validation Checklist
1. 登录系统，进入豆仓管理，选择任意豆料执行一笔入库（有克数）。
2. 进入交易记录，筛选“买豆支出”，应出现对应记录，金额符合公式。
3. 执行一笔损耗，返回交易记录确认无新增；在豆仓库存流水中能看到该损耗。
4. 执行一笔会员充值/消费并取消一笔交易，确认功能正常。
5. 检查侧边栏：交易记录位于“运营管理”。

## 5. Execution Notes
- 若实现中发现交易类型枚举/数据库约束导致无法直接写入 `bead_purchase`，需先回到 `/plan` 更新方案（例如采用既有类型 + 标记字段）。
- 不执行依赖安装/恢复命令；如环境缺失由用户手动执行并反馈输出。
