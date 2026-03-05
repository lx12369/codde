# 织雾拼豆管理系统人员模块扩展（新增员工管理）可执行规格

### 1. Summary
- 新增员工管理页面，并将侧边栏原“会员管理”模块更名为“人员管理”，把“客户管理”和“员工管理”统一归入该模块，同时统一系统品牌文案为“织雾拼豆管理系统”。
- 当前系统仅能管理客户，缺少员工账号可视化管理入口，导致账号维护依赖数据库或临时脚本，效率和安全性都不足。

### 2. Goals / Non-goals
- Goals
  - 侧边栏分组文案由“会员管理”改为“人员管理”，且分组下至少包含“客户管理”“员工管理”两个菜单。
  - 系统品牌文案统一为“织雾拼豆管理系统”（替换现存“织雾拼豆会员管理系统”文案）。
  - 人员管理分组保持可扩展，当前仅包含“客户管理”“员工管理”两类，后续可继续新增。
  - 员工账号（非管理员）不可访问数据管理页面（`/settings`）。
  - 新增 `/employees` 页面，支持员工列表查看、搜索、分页。
  - 基于现有 `users` 表提供员工账号管理能力（新增、编辑、删除、重置密码）。
  - 员工管理接口与页面仅允许管理员执行写操作，避免普通账号误操作。
  - 保持现有客户管理、交易、计费、计时等业务流程不回归。
- Non-goals
  - 不改登录流程、JWT 机制与鉴权基础设施。
  - 不重构全系统 RBAC（本次仅覆盖员工管理相关权限控制）。
  - 不调整客户数据模型、客户 API 与客户页面交互逻辑。
  - 不新增第三方依赖或修改依赖锁文件。

### 3. Current State & Constraints
- 当前状态
  - 前端侧边栏分组定义在 `frontend/src/layouts/MainLayout.vue`，`member` 分组标题为“会员管理”，当前仅有“客户管理”菜单。
  - 顶部导航与登录页品牌文案当前为“织雾拼豆会员管理系统”。
  - 路由定义在 `frontend/src/router/index.js`，目前不存在 `employees` 路由。
  - 数据管理页面路由为 `/settings`（`frontend/src/views/Settings.vue`），当前仅基于登录态控制，未在规格中明确员工禁入要求。
  - 后端 `backend/app.py` 仅注册了 `auth/customers/transactions/...` 等蓝图，未注册员工管理蓝图。
  - 账号数据来自 `backend/models/models.py` 的 `User` 模型（`id/username/password_hash/role/created_at/updated_at`），目前仅在 `auth` 路由中使用。
- 环境/平台约束
  - Windows + PowerShell。
  - 前端 Vue 3 + Vite，后端 Flask + SQLAlchemy + SQLite。
- 风险约束
  - 禁止自动执行依赖安装/恢复；未获用户批准不得修改依赖声明或锁文件。
  - `/spec` 阶段仅允许修改 `specs/`。

### 4. Requirements
- Functional requirements
  - P0
    - 将侧边栏分组标题“会员管理”改为“人员管理”。
    - 系统品牌文案统一改为“织雾拼豆管理系统”（至少覆盖主布局顶部与登录页标题/页脚）。
    - 在侧边栏同分组新增“员工管理”菜单项，路由为 `/employees`。
    - 非管理员账号不可访问数据管理页面 `/settings`：
      - 侧边栏不展示“数据管理”菜单项给非管理员。
      - 非管理员直接输入 `/settings` 时被重定向到可访问页面（建议 `/dashboard`）并给出提示。
    - 新增员工管理页面，提供：列表、关键词搜索（用户名）、分页、创建员工、编辑员工、删除员工。
    - 新增后端员工管理 API（建议 `/api/employees`）：
      - `GET /api/employees`：分页查询员工
      - `POST /api/employees`：创建员工
      - `PUT /api/employees/<id>`：更新员工基础信息（用户名、角色）
      - `PUT /api/employees/<id>/reset-password`：重置密码
      - `DELETE /api/employees/<id>`：删除员工
    - 写操作必须校验管理员身份；非管理员返回 403。
    - 密码写入必须复用现有哈希能力（与登录校验兼容）。
  - P1
    - 人员管理分组的菜单组织为可扩展结构，不将逻辑硬编码为“仅两类”。
    - 删除员工时禁止删除当前登录账号。
    - 禁止删除默认管理员 `admin`（或至少提供显式保护规则）。
    - 数据管理相关后端接口（`/api/data/*`）对非管理员返回 403，避免绕过前端路由限制。
    - 关键操作写入系统日志（创建/更新/重置密码/删除）。
  - P2
    - 员工管理页视觉与现有已美化页面保持一致（`page-hero`、反馈条、卡片化布局）。
- Non-functional requirements
  - 安全性：接口不得返回 `password_hash`；重置密码必须有最小长度校验（>=6）。
  - 兼容性：沿用统一响应结构 `success_response/error_response/paginated_response`。
  - 可维护性：前后端命名与目录结构遵循现有约定（`routes/*.py`、`views/*.vue`、`api/index.js`）。
  - 性能：员工列表分页查询保持与客户列表同量级响应，不引入额外 N+1 查询。
- Compatibility / migration requirements
  - 优先复用现有 `users` 表，不引入新表迁移。
  - 现有管理员账号（`admin`）继续可登录且可使用新员工管理页面。

### 5. Design
- Overall approach
  - 前端：
    - `MainLayout.vue` 调整分组文案并新增“员工管理”菜单项。
    - `router/index.js` 新增 `employees` 子路由。
    - 新增 `views/Employees.vue`，复用系统统一页面框架与反馈机制。
    - `api/index.js` 新增 `employeeApi` 封装。
  - 后端：
    - 新增 `routes/employees.py` 蓝图，复用 `token_required` 和统一响应工具。
    - 在 `app.py` 注册员工蓝图。
    - 基于 `User` 模型实现分页、增删改、重置密码；通过 `role` 做管理员写权限校验。
- Key decisions
  - 决策 1：复用 `users` 表承载员工数据，避免新增表和迁移风险。
  - 决策 2：员工管理接口采用与客户管理一致的 REST 风格与分页返回结构。
  - 决策 3：把“模块重命名 + 新页面接入”作为一个原子交付，保证导航语义与功能同步。
  - 决策 4：统一系统品牌文案为“织雾拼豆管理系统”，避免“会员/人员”命名混用。
- Alternatives and trade-offs
  - 方案 A（推荐）：复用 `users` 表 + 新增 `employees` 路由/页面。
    - 优点：实现成本低、数据一致、回滚简单。
    - 缺点：员工字段受限于当前 `users` 模型（无手机号/状态等扩展字段）。
  - 方案 B：新增独立 `employees` 表并与 `users` 解耦。
    - 优点：可扩展字段更多，领域边界更清晰。
    - 缺点：需要迁移与同步策略，复杂度和风险显著上升。
- Impact scope
  - 前端：`frontend/src/layouts/MainLayout.vue`、`frontend/src/views/Login.vue`、`frontend/src/router/index.js`、`frontend/src/api/index.js`、`frontend/src/views/Employees.vue`。
  - 后端：`backend/app.py`、`backend/routes/employees.py`（新增）。
  - 复用模型：`backend/models/models.py`（`User`）。

### 6. Acceptance Criteria
- AC1：侧边栏原“会员管理”分组改名为“人员管理”，并显示“客户管理”“员工管理”。
- AC2：访问 `/employees` 可正常加载员工管理页，页面标题与菜单高亮正确。
- AC3：员工列表支持分页和关键词搜索，返回结构符合现有分页协议。
- AC4：管理员可成功创建员工；创建后可立即在列表中看到新员工。
- AC5：管理员可编辑员工用户名/角色、重置密码，且新凭据可用于登录（手工验证）。
- AC6：删除员工遵循保护规则（不可删当前登录账号，不可删默认管理员）。
- AC7：非管理员访问员工写接口时被拒绝（403）。
- AC8：客户管理页面和原有业务页面可正常访问，无明显回归。
- AC9：前端构建通过，后端新增路由文件语法检查通过。
- AC10：系统品牌文案显示为“织雾拼豆管理系统”（主布局与登录页一致）。
- AC11：人员管理分组当前呈现“客户管理”“员工管理”两类，且后续新增第三类不需要重构分组模型。
- AC12：非管理员登录后看不到“数据管理”菜单，直接访问 `/settings` 会被拦截并跳转到允许页面。
- AC13：非管理员调用 `/api/data/*` 接口返回 403，管理员调用保持可用。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 工具存在性检查
    ```powershell
    Get-Command node
    Get-Command npm
    Get-Command python
    ```
    预期：返回可执行路径，说明本地可运行构建/语法检查命令。
  - 后端语法检查
    ```powershell
    python -m py_compile backend\routes\employees.py
    python -m py_compile backend\app.py
    ```
    预期：无输出且退出码为 0。
  - 前端语法与构建检查
    ```powershell
    node --check frontend\src\api\index.js
    cd frontend; npm run build
    ```
    预期：无语法报错，Vite 构建成功。
  - 联调与手工验收
    ```powershell
    cd backend; ..\.venv\Scripts\python.exe app.py
    cd frontend; npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：可登录系统，按 AC1-AC8、AC10-AC13 完成手工验证。
- 需用户执行并粘贴输出的命令
  - 若执行校验时提示依赖缺失，以下命令需用户确认后执行：
    ```powershell
    cd frontend; npm install
    cd backend; ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
    ```

### 8. Risks & Rollback
- Risks
  - 管理员权限判定实现不严谨，可能导致普通账号越权管理员工。
  - 删除/更新员工保护规则不完整，可能误删可登录账号造成锁定风险。
  - 模块重命名涉及导航分组，若遗漏映射可能导致菜单展示异常。
- Rollback
  - 前端回滚：恢复 `MainLayout.vue` 分组文案与菜单项，移除 `Employees.vue` 路由入口。
  - 后端回滚：取消 `employees` 蓝图注册并移除新增路由文件。
  - 数据回滚：若误操作账号，使用数据库备份或手工恢复 `users` 记录（用户名、角色、密码哈希）。

### 9. Open Questions
- 员工角色是否固定为 `admin/staff` 两类？（本规格默认先沿用现有 `role` 字段自由文本，但写入时可限制为白名单）

### 10. References
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/views/Login.vue`
- `frontend/src/router/index.js`
- `frontend/src/api/index.js`
- `backend/app.py`
- `backend/models/models.py`
- `backend/routes/auth.py`
- `backend/routes/customers.py`

## /spec Completion Checklist (self-check)
- [x] Only `specs/` changes
- [x] Goals/Non-goals are clear and non-conflicting
- [x] At least one alternative with trade-offs
- [x] Acceptance criteria are verifiable
- [x] Validation strategy lists candidates and marks user-run commands
- [x] Risks and rollback are clearly defined
