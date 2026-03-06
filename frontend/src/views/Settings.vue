<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import api from '@/api'

const dataStatus = reactive({
  storageLocation: '',
  dataSize: '0 KB',
  userCount: 0,
  revokedTokenCount: 0,
  customerCount: 0,
  balanceCount: 0,
  transactionCount: 0,
  activityCount: 0,
  billingRuleCount: 0,
  activeTimerCount: 0,
  beadMaterialCount: 0,
  beadBalanceCount: 0,
  beadLedgerCount: 0,
  beadStocktakeCount: 0,
  logCount: 0
})

const statusLoading = ref(false)
const backupLoading = ref(false)
const restoreLoading = ref(false)
const clearLoading = ref(false)
const showClearConfirm = ref(false)
const fileInput = ref(null)
const lastSyncedAt = ref('')
const clearConfirmButtonRef = ref(null)

const feedback = reactive({
  tone: 'info',
  message: ''
})

let feedbackTimer = null

const feedbackStyle = computed(() => {
  if (feedback.tone === 'success') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  }
  if (feedback.tone === 'error') {
    return 'border-rose-200 bg-rose-50 text-rose-800'
  }
  return 'border-blue-200 bg-blue-50 text-blue-800'
})

const isAnyActionRunning = computed(() => (
  statusLoading.value || backupLoading.value || restoreLoading.value || clearLoading.value
))

const safeCount = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const formatFileSize = (bytes) => {
  const size = Number(bytes)
  if (!Number.isFinite(size) || size <= 0) return '0 KB'

  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(2)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const formatNumber = (num) => safeCount(num).toLocaleString()

const overviewCards = computed(() => ([
  {
    key: 'storageLocation',
    label: '存储位置',
    value: dataStatus.storageLocation || '本地数据库（路径未知）',
    helper: '当前数据库文件路径',
    tone: 'slate'
  },
  {
    key: 'dataSize',
    label: '数据大小',
    value: dataStatus.dataSize,
    helper: '用于评估备份体量',
    tone: 'amber'
  },
  {
    key: 'userCount',
    label: '人员账号',
    value: formatNumber(dataStatus.userCount),
    helper: '管理员与员工账号',
    tone: 'sky'
  },
  {
    key: 'revokedTokenCount',
    label: '失效令牌',
    value: formatNumber(dataStatus.revokedTokenCount),
    helper: '登录黑名单记录',
    tone: 'amber'
  },
  {
    key: 'customerCount',
    label: '客户总数',
    value: formatNumber(dataStatus.customerCount),
    helper: '客户档案记录',
    tone: 'indigo'
  },
  {
    key: 'balanceCount',
    label: '余额账户',
    value: formatNumber(dataStatus.balanceCount),
    helper: '客户余额数据',
    tone: 'emerald'
  },
  {
    key: 'transactionCount',
    label: '交易记录',
    value: formatNumber(dataStatus.transactionCount),
    helper: '充值与消费流水',
    tone: 'teal'
  },
  {
    key: 'activityCount',
    label: '活动档案',
    value: formatNumber(dataStatus.activityCount),
    helper: '活动配置记录',
    tone: 'violet'
  },
  {
    key: 'billingRuleCount',
    label: '计费规则',
    value: formatNumber(dataStatus.billingRuleCount),
    helper: '价格与计费策略',
    tone: 'rose'
  },
  {
    key: 'activeTimerCount',
    label: '活跃计时',
    value: formatNumber(dataStatus.activeTimerCount),
    helper: '进行中的计时项目',
    tone: 'sky'
  },
  {
    key: 'beadMaterialCount',
    label: '豆料档案',
    value: formatNumber(dataStatus.beadMaterialCount),
    helper: '材料基础信息',
    tone: 'emerald'
  },
  {
    key: 'beadBalanceCount',
    label: '豆仓库存记录',
    value: formatNumber(dataStatus.beadBalanceCount),
    helper: '库存余额快照',
    tone: 'teal'
  },
  {
    key: 'beadLedgerCount',
    label: '豆仓流水',
    value: formatNumber(dataStatus.beadLedgerCount),
    helper: '入库、出库、损耗',
    tone: 'violet'
  },
  {
    key: 'beadStocktakeCount',
    label: '豆仓盘点记录',
    value: formatNumber(dataStatus.beadStocktakeCount),
    helper: '盘点校准历史',
    tone: 'rose'
  },
  {
    key: 'logCount',
    label: '系统日志',
    value: formatNumber(dataStatus.logCount),
    helper: '全模块操作日志',
    tone: 'slate'
  }
]))

const overviewGroupConfig = [
  {
    key: 'operations',
    title: '经营核心',
    description: '围绕人员、客户、交易与计费的主业务数据。',
    cardKeys: ['userCount', 'customerCount', 'balanceCount', 'transactionCount', 'activityCount', 'billingRuleCount', 'activeTimerCount']
  },
  {
    key: 'inventory',
    title: '豆仓体系',
    description: '豆料档案、库存余额与流水盘点的仓储链路。',
    cardKeys: ['beadMaterialCount', 'beadBalanceCount', 'beadLedgerCount', 'beadStocktakeCount']
  },
  {
    key: 'infra',
    title: '系统基建',
    description: '存储容量、日志审计与会话黑名单状态。',
    cardKeys: ['storageLocation', 'dataSize', 'logCount', 'revokedTokenCount']
  }
]

const overviewCardMap = computed(() => (
  overviewCards.value.reduce((acc, card) => {
    acc[card.key] = card
    return acc
  }, {})
))

const overviewGroups = computed(() => (
  overviewGroupConfig.map((group) => ({
    ...group,
    cards: group.cardKeys
      .map((cardKey) => overviewCardMap.value[cardKey])
      .filter(Boolean)
  }))
))

const formatDateTime = (date) => {
  if (!(date instanceof Date)) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(date)
}

const clearFeedbackTimer = () => {
  if (!feedbackTimer) return
  window.clearTimeout(feedbackTimer)
  feedbackTimer = null
}

const showFeedback = (tone, message) => {
  feedback.tone = tone
  feedback.message = message
  clearFeedbackTimer()
  feedbackTimer = window.setTimeout(() => {
    feedback.message = ''
    feedbackTimer = null
  }, 4500)
}

const resetDataStatus = () => {
  dataStatus.storageLocation = '本地数据库（路径未知）'
  dataStatus.dataSize = '0 KB'
  dataStatus.userCount = 0
  dataStatus.revokedTokenCount = 0
  dataStatus.customerCount = 0
  dataStatus.balanceCount = 0
  dataStatus.transactionCount = 0
  dataStatus.activityCount = 0
  dataStatus.billingRuleCount = 0
  dataStatus.activeTimerCount = 0
  dataStatus.beadMaterialCount = 0
  dataStatus.beadBalanceCount = 0
  dataStatus.beadLedgerCount = 0
  dataStatus.beadStocktakeCount = 0
  dataStatus.logCount = 0
}

const fetchDataStatus = async ({ withFeedback = false } = {}) => {
  statusLoading.value = true
  try {
    const storageResponse = await api.get('/data/storage-info')
    const storageInfo = storageResponse?.data || storageResponse || {}
    const dataCounts = storageInfo.dataCounts || {}

    dataStatus.storageLocation = storageInfo.storageLocation || storageInfo.databaseUri || '本地数据库（路径未知）'
    dataStatus.dataSize = formatFileSize(storageInfo.dataSizeBytes)
    dataStatus.userCount = safeCount(dataCounts.users)
    dataStatus.revokedTokenCount = safeCount(dataCounts.revoked_tokens)
    dataStatus.customerCount = safeCount(dataCounts.customers)
    dataStatus.balanceCount = safeCount(dataCounts.balances)
    dataStatus.transactionCount = safeCount(dataCounts.transactions)
    dataStatus.activityCount = safeCount(dataCounts.activities)
    dataStatus.billingRuleCount = safeCount(dataCounts.billing_rules)
    dataStatus.activeTimerCount = safeCount(dataCounts.active_timers)
    dataStatus.beadMaterialCount = safeCount(dataCounts.bead_materials)
    dataStatus.beadBalanceCount = safeCount(dataCounts.bead_inventory_balances)
    dataStatus.beadLedgerCount = safeCount(dataCounts.bead_inventory_ledgers)
    dataStatus.beadStocktakeCount = safeCount(dataCounts.bead_stocktakes)
    dataStatus.logCount = safeCount(dataCounts.logs)
    lastSyncedAt.value = formatDateTime(new Date())

    if (withFeedback) {
      showFeedback('success', '数据状态已刷新。')
    }
  } catch (error) {
    console.error('Failed to fetch data status:', error)
    resetDataStatus()
    if (withFeedback) {
      showFeedback('error', '刷新失败，请检查网络连接后重试。')
    }
  } finally {
    statusLoading.value = false
  }
}

const backupData = async () => {
  backupLoading.value = true
  try {
    const response = await api.get('/data/backup')
    const payload = response?.data || response || {}
    const content = JSON.stringify(payload, null, 2)
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '')
    const filename = `backup_${timestamp}.json`

    link.href = url
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    showFeedback('success', `备份完成，已下载 ${filename}`)
    await fetchDataStatus()
  } catch (error) {
    console.error('Failed to backup data:', error)
    showFeedback('error', '备份失败，请稍后重试。')
  } finally {
    backupLoading.value = false
  }
}

const triggerRestore = () => {
  fileInput.value?.click()
}

const restoreData = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return

  if (!file.name.toLowerCase().endsWith('.json')) {
    showFeedback('error', '仅支持 .json 备份文件。')
    if (fileInput.value) {
      fileInput.value.value = ''
    }
    return
  }

  restoreLoading.value = true
  try {
    const fileContent = await file.text()
    let jsonData = null

    try {
      jsonData = JSON.parse(fileContent)
    } catch (parseError) {
      showFeedback('error', '文件格式错误：无法解析为有效 JSON。')
      return
    }

    await api.post('/data/restore', jsonData)
    showFeedback('success', `恢复完成：${file.name}`)
    await fetchDataStatus()
  } catch (error) {
    console.error('Failed to restore data:', error)
    const apiMessage = error?.response?.data?.message
    showFeedback('error', apiMessage || '恢复失败，请检查备份文件内容后重试。')
  } finally {
    restoreLoading.value = false
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

const openClearConfirm = async () => {
  showClearConfirm.value = true
  await nextTick()
  clearConfirmButtonRef.value?.focus()
}

const closeClearConfirm = () => {
  if (clearLoading.value) return
  showClearConfirm.value = false
}

const clearAllData = async () => {
  clearLoading.value = true
  try {
    await api.delete('/data/clear')
    showClearConfirm.value = false
    showFeedback('success', '系统数据已清空。')
    await fetchDataStatus()
  } catch (error) {
    console.error('Failed to clear data:', error)
    const apiMessage = error?.response?.data?.message
    showFeedback('error', apiMessage || '清空失败，请稍后重试。')
  } finally {
    clearLoading.value = false
  }
}

onMounted(() => {
  fetchDataStatus()
})

onUnmounted(() => {
  clearFeedbackTimer()
})
</script>

<template>
  <div class="settings-page space-y-6">
    <section class="page-hero rounded-3xl p-6 sm:p-8">
      <div class="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-2">
          <p class="page-hero__eyebrow">Data Control Center</p>
          <h1 class="page-hero__title">数据管理</h1>
          <p class="page-hero__meta">最近更新：{{ lastSyncedAt || '尚未刷新' }}</p>
        </div>

        <button
          type="button"
          :disabled="isAnyActionRunning"
          @click="fetchDataStatus({ withFeedback: true })"
          class="page-hero__action"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span>{{ statusLoading ? '刷新中...' : '刷新状态' }}</span>
        </button>
      </div>
    </section>

    <Transition name="notice">
      <div
        v-if="feedback.message"
        role="status"
        aria-live="polite"
        :class="['rounded-2xl border px-4 py-3 sm:px-5 sm:py-4 text-sm sm:text-[0.95rem] shadow-sm settings-feedback', feedbackStyle]"
      >
        {{ feedback.message }}
      </div>
    </Transition>

    <section class="settings-shell">
      <section class="panel-surface settings-map rounded-3xl border p-5 sm:p-6 lg:p-8">
        <div class="settings-map__head">
          <div>
            <p class="settings-map__eyebrow">Data Topology</p>
            <h2 class="settings-map__title">全域数据版图</h2>
          </div>
          <p class="settings-map__desc">
            按业务域拆分查看系统数据状态，所有卡片均来自实时刷新结果。
          </p>
        </div>

        <div class="settings-groups">
          <article
            v-for="group in overviewGroups"
            :key="group.key"
            class="group-panel"
          >
            <div class="group-panel__head">
              <h3 class="group-panel__title">{{ group.title }}</h3>
              <p class="group-panel__desc">{{ group.description }}</p>
            </div>

            <div class="group-panel__grid">
              <article
                v-for="(card, index) in group.cards"
                :key="`${group.key}-${card.key}`"
                :class="['status-card', `status-card--${card.tone}`]"
                :style="{ animationDelay: `${index * 0.06}s` }"
              >
                <p class="status-card__label">{{ card.label }}</p>
                <p :class="['status-card__value', card.key === 'storageLocation' ? 'break-all' : '']">
                  {{ card.value }}
                </p>
                <p class="status-card__helper">{{ card.helper }}</p>
              </article>
            </div>
          </article>
        </div>
      </section>

      <aside class="panel-surface settings-command rounded-3xl border p-5 sm:p-6 lg:p-7">
        <header class="settings-command__head">
          <p class="settings-command__eyebrow">Action Deck</p>
          <h2 class="settings-command__title">维护操作台</h2>
        </header>

        <article class="action-card action-card--backup">
          <div class="action-card__head">
            <h3 class="action-card__title">数据备份</h3>
            <span class="action-card__tag">推荐先执行</span>
          </div>
          <p class="action-card__desc">导出当前系统快照，生成本地 JSON 备份文件。</p>
          <button
            type="button"
            :disabled="isAnyActionRunning"
            @click="backupData"
            class="action-btn action-btn--backup"
          >
            {{ backupLoading ? '备份中...' : '立即备份到文件' }}
          </button>
        </article>

        <article class="action-card action-card--restore">
          <div class="action-card__head">
            <h3 class="action-card__title">数据恢复</h3>
            <span class="action-card__tag">需谨慎</span>
          </div>
          <p class="action-card__desc">上传 `.json` 备份文件，将系统恢复到指定快照。</p>
          <input
            ref="fileInput"
            type="file"
            accept=".json"
            class="hidden"
            @change="restoreData"
          >
          <button
            type="button"
            :disabled="isAnyActionRunning"
            @click="triggerRestore"
            class="action-btn action-btn--restore"
          >
            {{ restoreLoading ? '恢复中...' : '上传 JSON 并恢复' }}
          </button>
        </article>

        <article class="tips-card rounded-2xl border p-4 text-sm">
          <h4 class="font-semibold">安全流程建议</h4>
          <p class="mt-2">1. 刷新状态，确认数据规模和更新时间。</p>
          <p class="mt-1">2. 先执行备份，再进行恢复或清空。</p>
          <p class="mt-1">3. 高风险操作后再次刷新并复核统计。</p>
        </article>

        <section class="danger-zone rounded-2xl border p-5 sm:p-6">
          <h3 class="text-lg font-bold text-rose-950">危险操作区</h3>
          <p class="mt-2 text-sm text-rose-900/85 leading-relaxed">
            清空后将删除客户、交易、活动、豆仓与日志等数据。此操作不可撤销，请确认已完成备份。
          </p>
          <button
            type="button"
            :disabled="isAnyActionRunning"
            @click="openClearConfirm"
            class="danger-zone__btn mt-5 inline-flex w-full items-center justify-center rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {{ clearLoading ? '清空中...' : '清空所有数据' }}
          </button>
        </section>
      </aside>
    </section>

    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="showClearConfirm"
          class="clear-modal-overlay fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-[1px]"
          @click.self="closeClearConfirm"
        >
          <div
            class="clear-modal w-full max-w-lg rounded-2xl bg-white shadow-2xl ring-1 ring-black/5"
            role="dialog"
            aria-modal="true"
            aria-labelledby="clear-data-title"
          >
            <div class="border-b border-slate-100 px-6 py-5">
              <h3 id="clear-data-title" class="text-lg font-bold text-slate-900">确认清空所有数据？</h3>
              <p class="mt-2 text-sm text-slate-600 leading-relaxed">
                该操作会永久删除业务与豆仓数据，且无法撤销。建议先执行“数据备份”，再继续。
              </p>
            </div>

            <div class="flex flex-col gap-3 px-6 py-5 sm:flex-row sm:justify-end">
              <button
                type="button"
                :disabled="clearLoading"
                @click="closeClearConfirm"
                class="clear-modal__cancel inline-flex items-center justify-center rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                取消
              </button>
              <button
                ref="clearConfirmButtonRef"
                type="button"
                :disabled="clearLoading"
                @click="clearAllData"
                class="clear-modal__confirm inline-flex items-center justify-center rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {{ clearLoading ? '正在清空...' : '确认清空' }}
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.settings-page {
  --ink: #12233f;
  --muted: #5d6f8a;
  --panel-border: rgba(18, 35, 63, 0.14);
  --panel-bg: rgba(255, 255, 255, 0.84);
  position: relative;
  isolation: isolate;
  font-family: 'Avenir Next', 'Trebuchet MS', 'PingFang SC', 'Microsoft YaHei UI', sans-serif;
  color: var(--ink);
}

.settings-page::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(circle at 6% 8%, rgba(14, 116, 144, 0.18), transparent 35%),
    radial-gradient(circle at 93% 6%, rgba(245, 158, 11, 0.14), transparent 33%),
    radial-gradient(circle at 72% 90%, rgba(59, 130, 246, 0.12), transparent 28%),
    linear-gradient(160deg, #edf3ff 0%, #f6faff 42%, #f4fbf5 100%);
}

.settings-page::after {
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background-image:
    linear-gradient(to right, rgba(15, 23, 42, 0.022) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(15, 23, 42, 0.022) 1px, transparent 1px);
  background-size: 28px 28px;
  opacity: 0.6;
}

.settings-feedback {
  border-width: 1px;
  backdrop-filter: blur(8px);
  box-shadow: 0 18px 26px -18px rgba(37, 99, 235, 0.38);
}

.settings-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
}

.panel-surface {
  position: relative;
  overflow: hidden;
  border-color: var(--panel-border);
  background: var(--panel-bg);
  box-shadow:
    0 24px 36px -30px rgba(15, 23, 42, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(8px);
}

.panel-surface::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.58), rgba(255, 255, 255, 0));
}

.settings-map,
.settings-command,
.group-panel,
.status-card,
.action-card,
.danger-zone {
  position: relative;
  z-index: 1;
}

.settings-map__head {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin-bottom: 1rem;
}

.settings-map__eyebrow {
  font-size: 0.74rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #1d4ed8;
  font-weight: 700;
}

.settings-map__title {
  font-size: 1.35rem;
  line-height: 1.2;
  font-weight: 800;
  color: #0f172a;
}

.settings-map__desc {
  color: var(--muted);
  font-size: 0.92rem;
  line-height: 1.6;
}

.settings-groups {
  display: grid;
  gap: 0.9rem;
}

.group-panel {
  border: 1px solid rgba(191, 219, 254, 0.6);
  border-radius: 1rem;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(241, 245, 249, 0.7));
  padding: 0.95rem;
}

.group-panel__head {
  margin-bottom: 0.75rem;
}

.group-panel__title {
  font-size: 1rem;
  font-weight: 800;
  color: #0f172a;
}

.group-panel__desc {
  margin-top: 0.25rem;
  color: #5f708b;
  font-size: 0.84rem;
  line-height: 1.5;
}

.group-panel__grid {
  display: grid;
  gap: 0.75rem;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
}

.status-card {
  --card-accent: #64748b;
  --card-blob: rgba(100, 116, 139, 0.2);
  border: 1px solid rgba(203, 213, 225, 0.75);
  border-radius: 0.95rem;
  background: #ffffff;
  padding: 0.9rem 0.88rem 0.84rem;
  min-height: 120px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 12px 20px -18px rgba(15, 23, 42, 0.35);
  transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
  animation: card-in 360ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.status-card::before {
  content: '';
  position: absolute;
  left: 0.95rem;
  right: 0.95rem;
  top: 0;
  height: 3px;
  border-radius: 9999px;
  background: linear-gradient(90deg, var(--card-accent), rgba(255, 255, 255, 0));
}

.status-card::after {
  content: '';
  position: absolute;
  right: -18px;
  top: -18px;
  width: 72px;
  height: 72px;
  border-radius: 9999px;
  background: var(--card-blob);
  opacity: 0.55;
}

.status-card:hover {
  transform: translateY(-1px);
  border-color: #bfdbfe;
  box-shadow: 0 16px 26px -20px rgba(37, 99, 235, 0.44);
}

.status-card__label {
  color: #3c4f71;
  font-size: 0.82rem;
  letter-spacing: 0.02em;
}

.status-card__value {
  margin-top: 0.45rem;
  color: #0f172a;
  font-size: 1.02rem;
  font-weight: 700;
  line-height: 1.42;
}

.status-card__helper {
  margin-top: 0.38rem;
  font-size: 0.78rem;
  color: #5f708b;
}

.status-card--slate {
  --card-accent: #475569;
  --card-blob: rgba(148, 163, 184, 0.3);
}

.status-card--amber {
  --card-accent: #d97706;
  --card-blob: rgba(245, 158, 11, 0.28);
  border-color: #fde68a;
  background: linear-gradient(180deg, #ffffff 0%, #fffbeb 100%);
}

.status-card--sky {
  --card-accent: #0284c7;
  --card-blob: rgba(14, 165, 233, 0.22);
  border-color: #bae6fd;
  background: linear-gradient(180deg, #ffffff 0%, #f0f9ff 100%);
}

.status-card--indigo {
  --card-accent: #4f46e5;
  --card-blob: rgba(99, 102, 241, 0.2);
  border-color: #c7d2fe;
  background: linear-gradient(180deg, #ffffff 0%, #eef2ff 100%);
}

.status-card--emerald {
  --card-accent: #059669;
  --card-blob: rgba(16, 185, 129, 0.22);
  border-color: #bbf7d0;
  background: linear-gradient(180deg, #ffffff 0%, #f0fdf4 100%);
}

.status-card--teal {
  --card-accent: #0f766e;
  --card-blob: rgba(45, 212, 191, 0.24);
  border-color: #99f6e4;
  background: linear-gradient(180deg, #ffffff 0%, #f0fdfa 100%);
}

.status-card--violet {
  --card-accent: #7c3aed;
  --card-blob: rgba(167, 139, 250, 0.24);
  border-color: #ddd6fe;
  background: linear-gradient(180deg, #ffffff 0%, #f5f3ff 100%);
}

.status-card--rose {
  --card-accent: #e11d48;
  --card-blob: rgba(251, 113, 133, 0.23);
  border-color: #fecdd3;
  background: linear-gradient(180deg, #ffffff 0%, #fff1f2 100%);
}

.settings-command {
  display: grid;
  gap: 0.85rem;
  align-content: start;
}

.settings-command__head {
  margin-bottom: 0.15rem;
}

.settings-command__eyebrow {
  font-size: 0.73rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #0f766e;
  font-weight: 700;
}

.settings-command__title {
  margin-top: 0.24rem;
  font-size: 1.22rem;
  font-weight: 800;
  color: #0f172a;
}

.action-card {
  border-radius: 0.95rem;
  padding: 1.1rem 1.02rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  border: 1px solid;
  position: relative;
  overflow: hidden;
  box-shadow: 0 12px 20px -16px rgba(30, 64, 175, 0.34);
  transition: transform 220ms ease, box-shadow 220ms ease;
}

.action-card::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.42), rgba(255, 255, 255, 0));
}

.action-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 18px 26px -18px rgba(30, 64, 175, 0.4);
}

.action-card > * {
  position: relative;
  z-index: 1;
}

.action-card--backup {
  background: linear-gradient(155deg, #e9fbf3 0%, #ffffff 86%);
  border-color: #9fe5bb;
}

.action-card--restore {
  background: linear-gradient(155deg, #edf5ff 0%, #ffffff 86%);
  border-color: #bad9ff;
}

.action-card__title {
  color: #0f172a;
  font-size: 1.08rem;
  font-weight: 800;
}

.action-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.action-card__tag {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: rgba(255, 255, 255, 0.72);
  padding: 0.2rem 0.55rem;
  font-size: 0.72rem;
  font-weight: 700;
  color: #334155;
}

.action-card__desc {
  margin-top: 0.25rem;
  color: #475569;
  font-size: 0.92rem;
  line-height: 1.55;
}

.tips-card {
  border-color: #c7d2fe;
  background: linear-gradient(180deg, rgba(238, 242, 255, 0.9), rgba(255, 255, 255, 0.82));
  color: #3730a3;
  box-shadow:
    inset 0 0 0 1px rgba(99, 102, 241, 0.08),
    0 10px 16px -14px rgba(79, 70, 229, 0.38);
}

.action-btn {
  margin-top: auto;
  border-radius: 0.82rem;
  padding: 0.68rem 0.92rem;
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 700;
  box-shadow: 0 14px 18px -14px rgba(15, 23, 42, 0.58);
  transition: transform 180ms ease, filter 180ms ease, opacity 180ms ease, box-shadow 180ms ease;
}

.action-btn:hover:enabled {
  transform: translateY(-1px);
  filter: brightness(1.03);
  box-shadow: 0 18px 20px -14px rgba(15, 23, 42, 0.56);
}

.action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.action-btn--backup {
  background: linear-gradient(135deg, #177c44, #14833f);
}

.action-btn--restore {
  background: linear-gradient(135deg, #1d4ed8, #2563eb);
}

.danger-zone {
  position: relative;
  overflow: hidden;
  border-color: #fda4af;
  background: linear-gradient(180deg, #fff1f2 0%, #ffffff 100%);
  box-shadow:
    inset 0 0 0 1px rgba(251, 113, 133, 0.16),
    0 12px 20px -16px rgba(244, 63, 94, 0.33);
}

.danger-zone::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    -35deg,
    rgba(244, 63, 94, 0.06),
    rgba(244, 63, 94, 0.06) 6px,
    transparent 6px,
    transparent 16px
  );
}

.danger-zone > * {
  position: relative;
  z-index: 1;
}

.danger-zone__btn {
  box-shadow: 0 12px 20px -14px rgba(225, 29, 72, 0.6);
}

.danger-zone__btn:hover:enabled {
  box-shadow: 0 15px 22px -14px rgba(225, 29, 72, 0.56);
}

.clear-modal-overlay {
  backdrop-filter: blur(2px);
  background:
    radial-gradient(circle at 50% 10%, rgba(244, 63, 94, 0.14), transparent 40%),
    rgba(15, 23, 42, 0.62);
}

.clear-modal {
  border: 1px solid #fecdd3;
  background: linear-gradient(180deg, #ffffff 0%, #fff5f6 100%);
  box-shadow: 0 30px 44px -28px rgba(15, 23, 42, 0.72);
}

.clear-modal__cancel {
  border-color: #cbd5e1;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
}

.clear-modal__cancel:hover:enabled {
  border-color: #94a3b8;
  background: #f8fafc;
}

.clear-modal__confirm {
  box-shadow: 0 12px 18px -14px rgba(225, 29, 72, 0.62);
}

.clear-modal__confirm:hover:enabled {
  box-shadow: 0 16px 20px -14px rgba(225, 29, 72, 0.58);
}

.notice-enter-active,
.notice-leave-active {
  transition: all 180ms ease;
}

.notice-enter-from,
.notice-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 220ms ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(7px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (min-width: 1280px) {
  .settings-shell {
    grid-template-columns: minmax(0, 1.52fr) minmax(0, 0.92fr);
    align-items: start;
  }

  .settings-command {
    position: sticky;
    top: 1.05rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .status-card {
    animation: none;
  }

  .status-card,
  .action-card,
  .action-btn,
  .danger-zone__btn {
    transition: none;
  }
}

@media (max-width: 420px) {
  .status-card {
    min-height: 106px;
  }
}
</style>

