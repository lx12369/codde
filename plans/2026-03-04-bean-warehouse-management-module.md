# /plan：豆仓管理大模块执行计划

## 1. 关联规格
- Spec：`specs/2026-03-04-bean-warehouse-management-module.md`

## 2. 范围与非范围
### Scope
- 新增“豆仓管理”路由、菜单与页面（`/bead-inventory`）。
- 新增后端豆仓 API：豆料主数据、库存余额、入库、出库（含损耗）、盘点、流水查询。
- 计量单位固定为克；补货和损耗支持“克/袋/瓶”输入并自动换算为克。
- 盘点流程采用单人确认。
- 新增库存预警（低于安全库存）与预计可用天数（基于近 7 天平均出库）。
- 保留现有模块行为不变（运营概况、客户、交易、计时等）。

### Out of Scope
- 不接入采购平台、硬件设备（扫码枪/标签打印等）。
- 不做多门店调拨。
- 不做复杂角色权限分级。
- 不改依赖声明与 lock 文件。

## 3. 执行前提
- 本阶段仅输出计划文档，不做源码实现。
- `/do` 必须严格按此计划执行；若需求变更需先回 `/plan` 更新。
- 库存数据写入需事务化，确保“余额+流水”一致。

## 4. 分步实施（有序、可验证、可回退）
### Step 1：数据模型与表结构落地
- 操作：
  - 在 `backend/models/models.py` 增加模型：`BeadMaterial`、`BeadInventoryBalance`、`BeadInventoryLedger`、`BeadStocktake`。
  - 字段覆盖：单位固定 `gram`、每袋克重 `grams_per_bag`、每瓶克重 `grams_per_bottle`、安全库存、状态等。
  - 在 `backend/models/__init__.py` 导出新增模型。
  - 更新初始化建表逻辑，确保旧库可新增表。
- 验证：
  - 新模型语法通过，应用启动后可创建新表。
- 回退：
  - 回退模型与导出改动，恢复原有数据结构。

### Step 2：库存服务层与换算规则
- 操作：
  - 新增豆仓服务模块（建议 `backend/utils/bead_inventory_service.py`）。
  - 封装数量换算函数：`克/袋/瓶 -> 克`，严格依赖 `grams_per_bag` 或 `grams_per_bottle`。
  - 封装库存事务函数：入库、出库（损耗）、盘点调整，统一写余额+流水+日志。
  - 出库防负库存校验。
- 验证：
  - 输入同一豆料不同单位，换算后克数一致且可复核。
  - 出库超可用库存时返回明确错误。
- 回退：
  - 回退服务层文件，不影响既有业务路由。

### Step 3：后端 API 路由接入
- 操作：
  - 新增 `backend/routes/bead_inventory.py`，提供接口：
    - `GET/POST /api/bead-inventory/materials`
    - `PUT/DELETE /api/bead-inventory/materials/<id>`
    - `GET /api/bead-inventory/balances`
    - `POST /api/bead-inventory/inbound`
    - `POST /api/bead-inventory/outbound`
    - `POST /api/bead-inventory/stocktake`
    - `GET /api/bead-inventory/ledger`
    - `GET /api/bead-inventory/alerts`
  - 所有接口接入 `@token_required`。
  - 在 `backend/routes/__init__.py` 与 `backend/app.py` 注册蓝图。
- 验证：
  - 鉴权通过时 CRUD 与单据接口可用；未登录返回 401。
- 回退：
  - 回退蓝图注册与路由文件。

### Step 4：前端 API 与页面实现
- 操作：
  - 在 `frontend/src/api/index.js` 新增 `beadInventoryApi`。
  - 新增 `frontend/src/views/BeadInventory.vue`：
    - 豆料列表/筛选；
    - 入库弹窗（克/袋/瓶）；
    - 损耗出库弹窗（克/袋/瓶）；
    - 盘点弹窗（单人确认）；
    - 流水列表与筛选；
    - 预警区块（低库存、预计可用天数）。
  - 在 `frontend/src/router/index.js` 和 `frontend/src/layouts/MainLayout.vue` 增加“豆仓管理”入口。
- 验证：
  - 页面可完整走通“建档 -> 入库 -> 损耗 -> 盘点 -> 流水追溯”。
- 回退：
  - 移除新增路由/菜单/页面，恢复原导航结构。

### Step 5：联调与回归
- 操作：
  - 进行前后端联调，核对单位换算、库存余额、流水一致性。
  - 验证预警规则与预计可用天数计算。
  - 回归检查现有模块（运营概况、客户、交易、计时、系统日志）。
- 验证：
  - 既有模块无功能回归；豆仓流程稳定。
- 回退：
  - 若联调阻塞，可先下线“预计可用天数”，保留核心库存台账流程。

## 5. 验证命令（PowerShell）与预期结果
### 5.1 工具可用性
```powershell
Get-Command python
Get-Command node
Get-Command npm
```
预期：均返回命令路径。

### 5.2 后端语法检查
```powershell
python -m py_compile backend\models\models.py
python -m py_compile backend\routes\bead_inventory.py
python -m py_compile backend\utils\bead_inventory_service.py
python -m py_compile backend\app.py
```
预期：无语法错误。

### 5.3 前端构建检查
```powershell
Set-Location frontend
npm run build
```
预期：构建成功，无 `BeadInventory.vue`、路由或布局编译错误。

### 5.4 后端接口冒烟（用户执行并回传输出）
```powershell
# 需先启动后端并准备 token
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/bead-inventory/materials -Headers @{ Authorization = "Bearer <TOKEN>" }
```
预期：返回豆料列表（或空列表）结构正确。

### 5.5 前端联调（用户执行并回传结果）
```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```
预期：可进入“豆仓管理”，完成入库/损耗/盘点操作并观察库存流水。

### 5.6 若依赖缺失（用户执行并回传输出）
```powershell
Set-Location frontend
npm install
```
```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
预期：安装成功后可继续验证。

## 6. 验收清单（映射 Spec）
- AC1：侧边栏出现“豆仓管理”并可进入页面。
- AC2：豆料主数据支持单位固定为克，且可配置每袋/每瓶克重。
- AC3：补货与损耗按袋/瓶输入后自动换算为克，库存与流水一致。
- AC4：出库超库存时被拒绝并提示。
- AC5：盘点采用单人确认并生成盘点调整流水。
- AC6：低于安全库存可见预警，预计可用天数可计算展示。
- AC7：流水可按豆料/时间/类型检索并含操作人、时间、关联单据号。
- AC8：现有模块无回归。

## 7. 风险与应对
- 风险：袋/瓶换算参数缺失导致入账错误。
  - 应对：提交前强校验 `grams_per_bag` / `grams_per_bottle`。
- 风险：库存写入并发冲突导致余额错误。
  - 应对：统一服务层事务更新与数据库锁策略。
- 风险：流水量增加造成查询变慢。
  - 应对：分页查询与必要索引（豆料、时间、类型）。
- 风险：用户误操作频繁盘点。
  - 应对：盘点确认弹窗与日志可追溯。

## 8. 进入 /do 门槛
- 已包含：
  - 关联 spec
  - scope / out-of-scope
  - 有序、可验证、可回退步骤
  - PowerShell 验证命令与预期结果
- 计划批准后进入 `/do`。
