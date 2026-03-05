# /plan：织雾拼豆管理系统人员模块扩展（员工管理 + 权限收敛）

## 1. 关联规格
- Spec：[`specs/2026-03-05-personnel-module-employee-management.md`](../specs/2026-03-05-personnel-module-employee-management.md)

## 2. 范围与非范围
### Scope
- 统一系统品牌文案为“织雾拼豆管理系统”（至少覆盖主布局与登录页）。
- 将侧边栏“会员管理”分组更名为“人员管理”，并纳入“客户管理”“员工管理”菜单。
- 新增员工管理能力：
  - 前端 `Employees` 页面（列表/搜索/分页/新增/编辑/删除/重置密码）。
  - 后端 `employees` 路由（`/api/employees`）与管理员写权限控制。
- 落地“员工不可访问数据管理页面”：
  - 非管理员不显示“数据管理”菜单。
  - 非管理员直达 `/settings` 时拦截跳转。
  - 非管理员访问 `/api/data/*` 返回 403。

### Out of Scope
- 不改客户管理业务模型与接口契约。
- 不重构全局 RBAC 或登录/JWT 基础流程。
- 不新增依赖，不改 `package.json`、lock 文件、`requirements.txt`。

## 3. 执行前提
- 本计划用于 `/do` 阶段实施，当前 `/plan` 只产出文档。
- 严格按本计划顺序执行；若需求变更，先回到 `/plan` 更新。
- 若本地依赖缺失，先由用户执行安装并粘贴输出后继续。

## 4. 分步实施（有序、可验证、可回退）
### Step 1：导航与品牌文案改造（前端）
- 操作：
  - `MainLayout.vue`：`member` 分组标题改为“人员管理”，加入“员工管理”菜单项。
  - `Login.vue` 与主布局顶部文案改为“织雾拼豆管理系统”。
  - `router/index.js` 新增 `/employees` 路由占位并接入页面组件。
- 验证：
  - 登录后可见“人员管理”分组，含“客户管理”“员工管理”。
  - 品牌文案一致且无“会员管理系统”残留。
- 回退：
  - 回滚上述文件中的文案与菜单配置，不影响后端数据。

### Step 2：员工管理后端接口（Flask）
- 操作：
  - 新增 `backend/routes/employees.py`。
  - 在 `backend/app.py` 注册 `employees` 蓝图。
  - 实现接口：
    - `GET /api/employees`（分页/搜索）
    - `POST /api/employees`（创建）
    - `PUT /api/employees/<id>`（更新用户名/角色）
    - `PUT /api/employees/<id>/reset-password`（重置密码）
    - `DELETE /api/employees/<id>`（删除）
  - 统一返回格式；禁止返回 `password_hash`。
  - 写操作校验管理员身份，并加保护规则（不可删当前账号、不可删 `admin`）。
- 验证：
  - 管理员可完成 CRUD + 重置密码。
  - 非管理员写操作返回 403。
- 回退：
  - 移除蓝图注册与新增路由文件，恢复到原接口集。

### Step 3：员工管理前端页面与 API 对接
- 操作：
  - `frontend/src/api/index.js` 增加 `employeeApi`。
  - 新增 `frontend/src/views/Employees.vue`，复用现有页面视觉框架（hero、反馈条、卡片/表格）。
  - 实现员工列表、搜索、分页、创建/编辑/删除/重置密码弹窗交互。
- 验证：
  - 页面能正确读写 `/api/employees` 并刷新列表。
  - 异常提示清晰，成功后反馈可见。
- 回退：
  - 移除页面与 API 调用接入，保留导航基本结构。

### Step 4：数据管理页面访问限制（员工禁入）
- 操作：
  - 前端菜单层：非管理员不展示“数据管理”。
  - 前端路由层：非管理员命中 `/settings` 时跳转到 `/dashboard` 并提示无权限。
  - 后端接口层：`backend/routes/data.py` 对非管理员返回 403（防止绕过前端）。
- 验证：
  - 非管理员账号无法通过菜单或 URL 进入数据管理页面。
  - 非管理员调用 `/api/data/*` 被拒绝，管理员不受影响。
- 回退：
  - 分层回退（先路由拦截、后菜单隐藏、最后接口限制），可快速恢复可用性。

### Step 5：联调、构建与回归
- 操作：
  - 执行语法检查与前端构建。
  - 执行手工回归：登录、客户管理、员工管理、数据管理权限边界。
- 验证：
  - 满足 Spec AC1-AC13。
- 回退：
  - 按步骤回退最近改动，优先回退权限策略引发的问题点。

## 5. 验证命令（PowerShell）与预期结果
### 5.1 工具可用性
```powershell
Get-Command node
Get-Command npm
Get-Command python
```
预期结果：返回命令路径。

### 5.2 后端语法检查
```powershell
python -m py_compile backend\routes\employees.py
python -m py_compile backend\routes\data.py
python -m py_compile backend\app.py
```
预期结果：无输出且退出码为 0。

### 5.3 前端语法与构建
```powershell
node --check frontend\src\api\index.js
node --check frontend\src\router\index.js
Set-Location frontend
npm run build
```
预期结果：语法检查通过，Vite 构建成功。

### 5.4 联调命令
```powershell
Set-Location backend
..\.venv\Scripts\python.exe app.py

Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```
预期结果：可登录并完成 AC1-AC13 手工验收。

### 5.5 依赖缺失时（用户执行并粘贴输出）
```powershell
Set-Location frontend
npm install

Set-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
预期结果：依赖安装完成后可继续执行 5.2-5.4。

## 6. 验收清单（映射 Spec AC）
- AC1/AC11：侧边栏更名“人员管理”，当前包含客户管理与员工管理，结构可扩展。
- AC2：`/employees` 页面可访问且菜单高亮正确。
- AC3：员工列表分页与搜索有效。
- AC4/AC5：管理员可新增、编辑、重置密码。
- AC6：不可删当前登录账号，不可删默认 `admin`。
- AC7：非管理员对员工写操作返回 403。
- AC8：客户管理及既有核心页面无回归。
- AC9：构建与语法检查通过。
- AC10：品牌文案统一为“织雾拼豆管理系统”。
- AC12/AC13：非管理员无法访问 `/settings` 且调用 `/api/data/*` 返回 403。

## 7. 风险与应对
- 风险：前端隐藏菜单但后端未限权，存在绕过风险。
  - 应对：前端路由 + 后端接口双重限制。
- 风险：账号保护规则遗漏导致可登录账号被误删。
  - 应对：删除前双校验（当前用户、默认管理员）并写日志。
- 风险：文案替换不完整导致系统命名不一致。
  - 应对：实施后全局检索关键字“会员管理系统/会员管理”复核。

## 8. 进入 /do 门槛
- 已包含：
  - 关联 spec
  - scope / out-of-scope
  - 有序、可验证、可回退步骤
  - PowerShell 验证命令与预期结果
- 你确认后进入 `/do`。
