# ARCHITECTURE

## 1. 项目概览

这是一个本地化的会员管理系统，核心能力包括：

- 用户登录与密码管理
- 客户管理（含软删除）
- 充值/消费/交易记录
- 活动与赠送规则管理
- 计费规则管理（限时、工作日、周末、素材费用）
- 计时消费（开始计时、编辑素材参数、结算、取消）
- 数据备份/恢复/清空
- 仪表盘统计与趋势图

技术上采用：

- 前端：`Vue 3 + Vite + Pinia + Vue Router + Axios + Tailwind + Chart.js`
- 后端：`Flask + SQLAlchemy + SQLite + JWT + bcrypt`
- 部署：开发模式（前后端分离） + 桌面打包模式（PyInstaller 单文件 EXE）

## 2. 顶层目录结构

```text
codde/
├─ backend/                    # Flask 后端
│  ├─ app.py                   # 应用工厂、路由注册、错误处理
│  ├─ desktop_main.py          # 桌面模式入口（挂载 SPA、设置本地 DB）
│  ├─ config.py                # 环境配置（Dev/Prod/Test）
│  ├─ models/
│  │  ├─ models.py             # ORM 模型
│  │  ├─ init_db.py            # 初始化与默认管理员创建
│  │  └─ __init__.py
│  ├─ routes/                  # 业务蓝图
│  │  ├─ auth.py
│  │  ├─ customers.py
│  │  ├─ transactions.py
│  │  ├─ activities.py
│  │  ├─ billing.py
│  │  ├─ active_timers.py
│  │  ├─ dashboard.py
│  │  ├─ data.py
│  │  └─ __init__.py
│  ├─ utils/                   # 鉴权/装饰器/响应格式
│  │  ├─ auth.py
│  │  ├─ decorators.py
│  │  ├─ response.py
│  │  └─ __init__.py
│  ├─ requirements.txt
│  ├─ build_exe.ps1            # 打包脚本（先构建前端，再打包后端）
│  └─ StudioSystem.spec        # PyInstaller 配置
├─ frontend/                   # Vue 前端
│  ├─ src/
│  │  ├─ api/index.js          # Axios 实例 + API 封装
│  │  ├─ router/index.js       # 路由与登录守卫
│  │  ├─ stores/index.js       # Pinia（app/auth）
│  │  ├─ layouts/MainLayout.vue
│  │  ├─ views/                # 页面模块（Dashboard/Customers/Transactions/...）
│  │  ├─ utils/consumptionCalculator.js  # 消费/套餐结算核心计算
│  │  ├─ App.vue
│  │  └─ main.js
│  ├─ vite.config.js           # 开发代理 /api -> 5000
│  ├─ tailwind.config.js
│  ├─ postcss.config.js
│  └─ package.json
├─ release/                    # 打包产物目录
└─ backup-*.json               # 备份样例数据
```

## 3. 运行架构（逻辑视图）

```text
Browser / Desktop WebView
        │
        ▼
Vue SPA (views + router + stores)
        │ Axios (/api)
        ▼
Flask (Blueprint Routes)
        │
        ▼
SQLAlchemy ORM
        │
        ▼
SQLite (app.db)
```

### 3.1 两种运行方式

1. 开发模式  
`frontend` 运行在 `:3000`，通过 Vite 代理把 `/api` 转发到 `backend :5000`。

2. 桌面打包模式  
`backend/desktop_main.py` 启动 Flask，并托管前端 `dist`，同时把数据库固定到：
`%USERPROFILE%/AppData/Local/StudioSystem/app.db`。

## 4. 后端架构

### 4.1 应用工厂与初始化

- `backend/app.py#create_app`
  - 读取配置（`config.py`）
  - 配置 CORS（开放 `/api/*`）
  - 初始化数据库
  - 注册全部蓝图
  - 注册统一错误处理
  - 执行 `init_db(app)`（建表 + 补字段 + 默认管理员）

- `backend/models/init_db.py`
  - `db.create_all()`
  - 自动补齐 `customers` 历史字段（`wechat/birthday/is_deleted/deleted_at`）
  - 创建默认管理员：`admin / admin123`

### 4.2 数据模型

- `User`：后台账号
- `Customer`：客户（支持软删除）
- `Balance`：客户余额
- `Transaction`：交易流水（充值/消费）
- `Activity`：充值活动（满额赠送）
- `BillingRule`：计费规则 JSON
- `ActiveTimer`：进行中的计时消费
- `Log`：操作日志（仪表盘最近活动）

### 4.3 路由分层

- `auth`：`/api/auth/login`, `/api/auth/password`
- `customers`：客户 CRUD + 余额查询
- `transactions`：交易查询、充值、消费、取消交易
- `activities`：活动 CRUD
- `billing`：计费规则读取/更新（分组 JSON）
- `active_timers`：计时记录管理与结算
- `dashboard`：统计、趋势图、最近活动
- `data`：备份、恢复、清空

所有业务接口通过 `@token_required` 做 JWT 鉴权（登录接口除外）。

### 4.4 公共能力

- `utils/auth.py`：JWT 生成/解析、密码哈希与验证
- `utils/decorators.py`：从 `Authorization: Bearer <token>` 提取身份
- `utils/response.py`：统一响应格式（成功/失败/分页）

## 5. 前端架构

### 5.1 启动与状态管理

- `src/main.js`：挂载 `Pinia + Router`
- `src/router/index.js`：
  - `/login` 游客路由
  - 主布局 `MainLayout` + 子页面
  - 全局前置守卫：未登录跳转登录页
- `src/stores/index.js`：
  - `useAuthStore` 管理 token/user 与登出
  - token 持久化到 `localStorage/sessionStorage`

### 5.2 API 访问层

- `src/api/index.js`
  - Axios 基础地址：`/api`
  - 请求拦截：自动注入 Bearer Token
  - 响应拦截：`401` 自动清理登录状态并跳转 `/login`
  - 暴露分域 API：`authApi/customerApi/transactionApi/...`

### 5.3 页面模块（按业务）

- `Dashboard.vue`：统计卡片 + 图表 + 最近活动
- `Customers.vue`：客户列表、详情、批量删除、充值/消费入口
- `Transactions.vue`：交易筛选、新增充值、手动/自动/计时消费、取消交易
- `Activities.vue`：活动管理
- `Billing.vue`：计费规则编辑
- `ActiveTimers.vue`：计时创建、动态时长、结算预览、结算提交
- `Settings.vue`：改密、数据备份/恢复/清空
- `Login.vue`：登录页

### 5.4 结算核心算法

`src/utils/consumptionCalculator.js` 负责统一计费计算：

- 限时套餐（1h/2h）+ 分段超时规则
- 工作日/周末套餐
- 素材附加费（大图/超量小图/超量大图）
- 美团抽成（默认 7%）
- 自动最优策略（超时后比较限时与不限时）

这是前端业务规则的核心复用模块，`Customers/Transactions/ActiveTimers` 都依赖它。

## 6. 关键业务流程

### 6.1 登录流程

`Login.vue` -> `POST /api/auth/login` -> 返回 `token + user` -> 写入 Store/Storage -> 跳转 `Dashboard`。

### 6.2 充值流程

前端提交充值 -> `transactions.py#create_recharge`  
-> 校验活动与赠送金额 -> 新增 `Transaction(type=recharge)`  
-> 更新 `Balance` -> 写 `Log`。

### 6.3 消费流程（非计时）

手动/自动结算计算金额 -> `POST /api/transactions/consumption`  
-> 校验余额 -> 新增 `Transaction(type=consumption)`  
-> 扣减 `Balance` -> 写 `Log`。

### 6.4 计时消费流程

开始计时：`POST /api/active-timers`（可在 `notes` 中存套餐/素材元数据）  
结算：前端实时计算预览 -> `POST /api/active-timers/<id>/settle`  
-> 生成消费交易、扣余额、计时单置 `completed`、写日志。

### 6.5 数据维护流程

- 备份：`GET /api/data/backup` 导出 JSON
- 恢复：`POST /api/data/restore` 合并回写各表
- 清空：`DELETE /api/data/clear` 删除业务数据

## 7. 数据与部署约定

### 7.1 数据库位置

- 开发：`sqlite:///app.db`（通常在 `backend/instance/app.db`）
- 桌面：`%USERPROFILE%/AppData/Local/StudioSystem/app.db`

### 7.2 ID 生成规则（代码约定）

- 客户：`C001...`
- 活动：`A001...`
- 交易：`T001...`（或时间戳回退）
- 计时：`TM<time_ns>`

### 7.3 打包流程

`backend/build_exe.ps1`：

1. 先执行前端 `npm run build`
2. 安装 `pyinstaller`
3. 按 `StudioSystem.spec` 打包 `desktop_main.py`
4. 把 `frontend/dist` 作为 `web_dist` 一并打入 EXE

## 8. 维护建议

- 保持接口字段命名兼容（当前前端已兼容 `snake_case/camelCase` 混用）
- 若新增业务规则，优先补充 `consumptionCalculator.js` 并在多个消费入口复用
- `data/restore` 属于高权限操作，后续可增加结构校验和版本号
- 若要支持多人角色权限，可在 `User.role` 基础上增加 RBAC 中间层

