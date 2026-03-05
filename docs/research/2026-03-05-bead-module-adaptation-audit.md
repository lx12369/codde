# 豆仓模块跨模块适配审计（2026-03-05）

## 审计范围
- 前端：菜单路由、运营概况、交易记录、系统日志、数据管理、豆仓页面
- 后端：蓝图注册、豆仓路由、交易取消回滚、日志映射、数据备份恢复、打包配置
- 打包：`build_exe.ps1`、根目录与后端目录的 `StudioSystem.spec`

## 已确认适配
- 豆仓路由已注册：`/api/bead-inventory/*`
- 前端菜单与路由已接入豆仓页面
- 数据管理（存储信息/备份/恢复/清空）已包含豆仓 4 张表：
  - `bead_materials`
  - `bead_inventory_balances`
  - `bead_inventory_ledgers`
  - `bead_stocktakes`
- 交易记录已支持 `bead_purchase` 类型展示与取消（含库存回滚逻辑）
- 内置色板文件存在且数量正确：`backend/data/mard_palette_v1.json` 共 `221` 条

## 可能未完全适配（建议优先处理）

### P0：部分打包入口未携带豆仓内置色板数据
- 现状：
  - `backend/build_exe.ps1` 已包含 `--add-data ".\\data;data"`（正确）
  - 但两个 spec 文件都只包含 `web_dist`，未包含 `backend/data`
    - `StudioSystem.spec`
    - `backend/StudioSystem.spec`
- 风险：
  - 若通过 spec 直接打包（而不是 `build_exe.ps1`），新电脑上可能缺少 `mard_palette_v1.json`，导致豆仓“内置 221 色/导入色卡”能力异常或失效。

### P1：日志类型映射缺失，系统日志筛选/标签不完整
- 现状：
  - 豆仓新增日志类型在写入处存在：
    - `bead_safe_stock_batch_update_by_common_color`
    - `transaction_cancel_bead_purchase`
  - 但 `backend/utils/audit_log.py` 的 `LOG_TYPE_META` 未定义上述两项。
- 风险：
  - 系统日志中这些记录会落入“其他”，无法按模块/操作精确筛选，影响追溯与审计。

### P2：系统日志前端徽章样式未覆盖豆仓动作
- 现状：
  - `frontend/src/views/SystemLogs.vue` 的 `getModuleBadgeClass`、`getActionBadgeClass` 未覆盖 `bead_inventory` 及豆仓相关 action（如 `inbound/outbound/loss/stocktake/material_*` 等）。
- 风险：
  - 功能可用，但视觉上退回默认样式，日志可读性较弱。

### P2：运营概况未纳入买豆支出维度
- 现状：
  - `backend/routes/dashboard.py` 统计仅计算 `recharge` 与 `consumption`，未单列或抵扣 `bead_purchase`。
  - 前端 `Dashboard.vue` 的“金额洞察”基于上述数据，未体现买豆支出。
- 风险：
  - 运营概况金额可能偏乐观（尤其频繁进豆时），与实际经营现金流存在偏差。

## 建议的最小修复清单
1. 给两个 `StudioSystem.spec` 增加 `backend/data` 打包项（与 `build_exe.ps1` 保持一致）。
2. 在 `backend/utils/audit_log.py` 的 `LOG_TYPE_META` 增加：
   - `bead_safe_stock_batch_update_by_common_color`
   - `transaction_cancel_bead_purchase`
3. 在 `frontend/src/views/SystemLogs.vue` 补充 `bead_inventory` 模块和豆仓 action 的徽章样式映射。
4. 评估是否在运营概况新增“买豆支出/净额”指标或图表维度，避免金额口径偏差。

## 建议回归验证（Windows 打包后）
1. 在全新 Windows 机器启动后，确认豆仓默认 221 色可见（无需手动导入）。
2. 执行“一键更新安全库存”，检查系统日志是否可按“豆仓 + 对应操作”筛选。
3. 新增买豆入库并在交易记录取消，检查：
   - 交易被撤销
   - 豆仓库存回滚
   - 系统日志操作类型正确显示
4. 对照运营概况与交易明细核对金额口径是否符合你预期（是否应包含买豆支出）。
