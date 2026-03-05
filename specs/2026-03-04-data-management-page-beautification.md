# 数据管理页面美化（/settings）可执行规格

### 1. Summary
- 在不改动后端接口与依赖的前提下，重构并美化 `frontend/src/views/Settings.vue` 的信息架构与视觉表现，提升可读性、操作安全感与移动端可用性。
- 该页面承载“备份/恢复/清空”高风险数据操作，当前视觉与反馈机制不足会直接影响管理员误操作风险与系统信任感。

### 2. Goals / Non-goals
- Goals
  - 将页面结构明确分为“状态总览 / 操作区 / 危险区”，让用户在 3 秒内理解页面用途。
  - 修复页面所有用户可见乱码文案，保证文案为可读中文（UTF-8 正常显示）。
  - 为备份、恢复、清空三类操作提供一致的状态反馈（空闲/进行中/成功/失败）。
  - 优化移动端与桌面端布局（至少覆盖 375px 与 >=1280px）。
  - 保持现有 API 调用契约不变：`/data/storage-info`、`/data/backup`、`/data/restore`、`/data/clear`。
  - 降低误触风险：危险操作在视觉与交互上与普通操作严格区分。
- Non-goals
  - 不修改后端接口行为、权限模型、日志模型或数据库结构。
  - 不引入新的 UI 框架或第三方依赖。
  - 不改动与 `/settings` 无关的业务页面（如客户、交易、活动页）。
  - 不实现多语言（i18n）体系，仅修复当前中文可读性。

### 3. Current State & Constraints
- 当前状态
  - 页面入口：`/settings`，路由定义于 `frontend/src/router/index.js`，导航文案“数据管理”在 `frontend/src/layouts/MainLayout.vue`。
  - 页面实现集中在 `frontend/src/views/Settings.vue`（脚本与模板耦合在单文件组件）。
  - 当前已具备基本卡片布局和三项数据操作，但多处中文文案出现乱码（例如标题与按钮提示），影响可用性与可信度。
  - 数据来源依赖后端：`backend/routes/data.py`（`/storage-info`、`/backup`、`/restore`、`/clear`）。
- 约束条件
  - 环境约束：Windows + PowerShell 工作流。
  - 工程约束：前端技术栈为 Vue 3 + Vite + Tailwind，优先复用现有样式体系。
  - 风险约束：禁止自动安装/恢复依赖；未经用户明确批准，不修改依赖声明或 lock 文件。
  - 变更范围约束：本需求聚焦“页面美化与交互清晰化”，不改变既有数据语义。

### 4. Requirements
- Functional requirements
  - P0
    - 页面信息架构调整为：顶部页面说明区 + 数据状态区 + 操作卡片区 + 危险操作区。
    - 所有用户可见文本为可读中文，消除乱码。
    - 统一操作反馈：每个操作都有加载态禁用、成功提示、失败提示，且提示语语义明确。
    - 恢复操作保留 `.json` 校验，错误提示可读且可定位问题（格式错误/请求失败）。
    - 清空操作必须保留二次确认，且视觉上保持“高风险”语义（红色主题、警示文案、明确后果）。
  - P1
    - 增加“最近一次状态刷新时间”或等效状态标识，帮助判断页面数据新鲜度。
    - 卡片密度与留白优化，避免移动端拥挤与按钮误触。
    - 弹窗交互优化（聚焦顺序、关闭行为、按钮主次关系）。
  - P2
    - 增加轻量过渡动画（如卡片进入/按钮状态切换），不影响可读性与性能。
- Non-functional requirements
  - 可访问性：键盘可达、焦点可见、文本与背景对比度满足基础可读标准。
  - 性能：首屏不新增高成本请求；保持当前并发拉取策略（最多同级 3 个请求）。
  - 可维护性：将样式语义化（统一色板与状态类），避免重复类名堆叠。
  - 一致性：与现有后台布局（`MainLayout`）视觉语言保持一致，不引入突兀设计。
- Compatibility / migration requirements
  - 前端接口调用参数与返回处理保持向后兼容，不要求数据迁移。
  - 保持现有下载文件命名约定 `backup_YYYYMMDDTHHMMSS.json`（现行为 ISO 截断变体）。

### 5. Design
- Overall approach
  - 采用“状态优先、操作分层、风险隔离”的页面结构：
    - 第一层：数据状态（存储位置、数据体积、客户数、交易数）
    - 第二层：常规操作（备份、恢复）
    - 第三层：危险操作（清空数据）
  - 统一交互状态模型（加载/成功/失败）并驱动按钮、提示条与弹窗文案，减少 `alert` 的突兀中断。
- Key decisions
  - 决策 1：保持单页路由与既有 API，不改后端，仅优化前端展示与交互反馈。
  - 决策 2：优先使用 Tailwind 现有能力，不新增依赖，降低实现与回归风险。
  - 决策 3：危险区独立视觉块，避免与“备份/恢复”操作混淆。
- Alternatives and trade-offs
  - 方案 A（推荐）：在 `Settings.vue` 内完成结构重排与状态统一。
    - 优点：改动集中、上线快、对现有项目侵入低。
    - 缺点：单文件体积继续增大，后续复用性一般。
  - 方案 B：拆分为多个子组件（如 `DataStatusCards`、`DataActions`、`DangerZone`）。
    - 优点：组件职责清晰、后续维护性更好。
    - 缺点：本次需求规模下改动面更广，联调与回归成本更高。
- Impact scope
  - 主要影响：`frontend/src/views/Settings.vue`
  - 可能小范围联动：`frontend/src/layouts/MainLayout.vue`（仅当导航文案或图标需微调时）
  - 参考接口：`backend/routes/data.py`

### 6. Acceptance Criteria
- AC1：进入 `/settings` 后，页面主标题、副标题、按钮、弹窗、提示文案均为可读中文，无乱码字符。
- AC2：页面加载时展示“加载中”状态；加载完成后展示存储位置、数据大小、客户数、交易数四项信息。
- AC3：点击“备份数据”可触发 JSON 下载，按钮在请求期间禁用并显示进行中状态。
- AC4：上传非 `.json` 文件时，页面给出明确错误提示且不发起恢复请求。
- AC5：上传合法备份后恢复成功，页面自动刷新状态数据并给出成功反馈。
- AC6：清空数据操作存在明确二次确认流程；确认后执行删除并刷新状态数据。
- AC7：在 375px 宽度下无横向滚动，关键按钮可见且可点击；在 >=1280px 下卡片布局清晰且不拥挤。
- AC8：执行备份/恢复/清空全流程时，浏览器控制台无新增未处理异常（网络失败场景除外，需有可见错误反馈）。

### 7. Validation Strategy
- 候选验证命令（PowerShell）
  - 环境检查
    ```powershell
    Get-Command node
    Get-Command npm
    ```
    预期：返回可执行路径，说明可运行前端构建命令。
  - 生产构建验证
    ```powershell
    cd frontend; npm run build
    ```
    预期：Vite 构建成功，无编译错误。
  - 本地联调（手工验收）
    ```powershell
    cd frontend; npm run dev -- --host 127.0.0.1 --port 3000
    ```
    预期：页面可访问并按验收标准完成手工检查。
- 需用户执行并粘贴输出的命令
  - 若缺失依赖（例如 `node_modules` 不存在）导致构建/运行失败，以下命令属于依赖安装，需用户明确执行并回贴日志：
    ```powershell
    cd frontend; npm install
    ```

### 8. Risks & Rollback
- Risks
  - 文案与状态重构时可能出现遗漏，导致某些边缘错误分支仍使用旧 `alert` 或乱码文案。
  - 过度视觉改动可能与现有后台整体风格不一致。
  - 危险操作交互若设计不当，可能增加操作路径复杂度，影响效率。
- Rollback
  - 以单文件变更为主时可直接回滚 `frontend/src/views/Settings.vue` 到前一版本。
  - 若涉及布局联动，按提交粒度回滚对应文件并重新执行构建验证。

### 9. Open Questions
- 是否需要为“清空数据”增加更强防误触机制（例如输入“清空”后才允许确认）？
- 是否保留当前“蓝色品牌头图”风格，还是改为更中性的数据控制台风格？
- 是否允许在页面中展示完整数据库路径（`storageLocation`）给所有管理员角色？

### 10. References
- `frontend/src/views/Settings.vue`
- `frontend/src/layouts/MainLayout.vue`
- `frontend/src/router/index.js`
- `frontend/src/api/index.js`
- `backend/routes/data.py`
