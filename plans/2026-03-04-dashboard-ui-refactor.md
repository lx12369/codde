# /plan：仪表盘界面重构执行计划

## 1. 关联规格
- Spec 文档：`specs/2026-03-04-dashboard-ui-refactor.md`

## 2. 范围与非范围
### Scope
- 仅实施前端仪表盘重构，目标文件为 `frontend/src/views/Dashboard.vue`。
- 必须保留：
  - 计费日类型显示与切换（工作日/周末）。
  - 今日消费金额（`today_consumption_amount`）。
  - 今日消费人数（`today_consumption_people`）。
- 允许删除或替换其余仪表盘模块（趋势图、最近活动、其他统计项等）。

### Out of Scope
- 不改后端统计逻辑与接口契约（`backend/routes/dashboard.py`）。
- 不改路由与鉴权流程（`frontend/src/router/index.js`、登录态逻辑）。
- 不新增依赖，不修改依赖声明/锁文件。

## 3. 执行前提
- 在 `/do` 阶段执行，不在本阶段改源码。
- 默认本地已有可用前端依赖；若无依赖，由用户手动安装并粘贴输出。

## 4. 分步实施（有序、可验证、可回退）
### Step 1：收敛并确认保留逻辑
- 操作：
  - 在 `Dashboard.vue` 中标记必须保留的状态与方法：
    - `billingDayType` / `calendarDayType`
    - `switchBillingDayType()` / `syncBillingDayType()`
    - `refreshData()` + 拉取 `/dashboard/stats` 的流程
    - 金额格式化函数与核心指标映射
- 完成判定：
  - 能明确列出“保留”和“删除候选”清单。
- 回退方式：
  - 仅分析不改动，无需回退。

### Step 2：重构 Dashboard 结构为“核心优先”
- 操作：
  - 重写 `Dashboard.vue` 模板结构：
    - 顶部：标题 + 当前计费日类型 + 切换按钮 + 刷新按钮。
    - 中部：仅保留 2 张核心指标卡（今日消费金额、今日消费人数）。
    - 底部：可选扩展区（可留空或简要占位）。
  - 删除非核心 UI 区块（趋势图、最近活动表、非必要统计卡等）。
- 完成判定：
  - 页面视觉上仅保留并突出核心能力；无保留无关模块。
- 回退方式：
  - 回退 `frontend/src/views/Dashboard.vue` 到改造前版本。

### Step 3：清理脚本与状态，确保字段映射正确
- 操作：
  - 删除与已移除模块相关的无用状态/函数/import（如图表实例、recentActivities 等）。
  - 保持对 `/api/dashboard/stats` 的请求，并仅映射：
    - `today_consumption_amount`
    - `today_consumption_people`
  - 补充/保留失败降级显示（例如 `0.00`、`0`、错误提示或加载态）。
- 完成判定：
  - 脚本无无效引用；核心字段映射可直接追踪到接口返回。
- 回退方式：
  - 回退 `Dashboard.vue` 到 Step 2 完成时版本，逐项恢复删除的状态定义。

### Step 4：响应式与交互稳定性检查
- 操作：
  - 调整卡片与顶部操作区布局，确保移动端（360px）与桌面均可读。
  - 验证按钮可点击性与禁用态（刷新中）。
- 完成判定：
  - 核心信息在 360px 下无明显横向溢出，交互无阻塞。
- 回退方式：
  - 仅回退样式与布局相关改动，保留业务逻辑。

### Step 5：构建与手工验收
- 操作：
  - 执行构建验证与本地联调。
  - 按 AC1-AC6 逐项验收并记录结论。
- 完成判定：
  - 构建通过，核心功能验收通过，无运行时报错。
- 回退方式：
  - 若构建失败且短时无法修复，回退到 Step 1 前的 `Dashboard.vue` 版本并重新拆分改动。

## 5. 验证命令（PowerShell）与预期结果
### 5.1 工具可用性检查
```powershell
Get-Command node
Get-Command npm
```
预期结果：返回可执行路径与命令信息，说明前端工具可用。

### 5.2 前端构建检查
```powershell
Set-Location frontend
npm run build
```
预期结果：构建成功，终端无编译错误，生成/更新 `frontend/dist` 构建产物。

### 5.3 前后端联调（手工验收）
```powershell
Set-Location backend
..\.venv\Scripts\python.exe app.py
```
预期结果：后端服务启动成功，可响应 `/api/dashboard/stats`。

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 3000
```
预期结果：前端开发服务启动成功，可访问 `/dashboard` 并完成点击验收。

### 5.4 依赖缺失时（用户执行）
```powershell
Set-Location frontend
npm install
```
预期结果：依赖安装成功后，可继续执行 `npm run build` 与 `npm run dev`。

## 6. 验收清单（对应 Spec AC）
- AC1：可见当前计费日类型与切换按钮。
- AC2：切换后标签立即变化，刷新后保持与 `localStorage` 一致。
- AC3：可见今日消费金额、今日消费人数且格式正确。
- AC4：两项指标由 `/api/dashboard/stats` 字段驱动。
- AC5：删除/替换其他模块后页面仍可运行且无报错。
- AC6：360px 与桌面宽度下核心内容可读，无明显横向溢出。

## 7. 风险与应对
- 风险：删模块后残留引用导致编译失败。
  - 应对：先删模板再清理脚本，最后统一跑构建。
- 风险：字段映射错误导致核心指标显示异常。
  - 应对：在代码中保留清晰映射点并做手工接口联调。
- 风险：移动端布局异常。
  - 应对：优先使用简单栅格与换行策略，避免固定宽度。

## 8. 进入 /do 的门槛
- 本计划已覆盖：
  - 关联 spec
  - 范围/非范围
  - 有序步骤（可验证、可回退）
  - 验证命令与预期结果
- 需用户确认后再进入 `/do`。
