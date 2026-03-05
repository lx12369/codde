<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import api from '@/api'

const dataStatus = reactive({
  storageLocation: '',
  dataSize: '0 KB',
  customerCount: 0,
  transactionCount: 0,
  beadMaterialCount: 0,
  beadBalanceCount: 0,
  beadLedgerCount: 0,
  beadStocktakeCount: 0
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

const statusBadgeText = computed(() => {
  if (statusLoading.value) return '同步中'
  if (lastSyncedAt.value) return '已同步'
  return '待同步'
})

const statusBadgeStyle = computed(() => (
  statusLoading.value
    ? 'border-amber-200 bg-amber-50 text-amber-700'
    : 'border-emerald-200 bg-emerald-50 text-emerald-700'
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
    key: 'customerCount',
    label: '客户总数',
    value: formatNumber(dataStatus.customerCount),
    helper: '活跃客户档案',
    tone: 'sky'
  },
  {
    key: 'transactionCount',
    label: '交易记录',
    value: formatNumber(dataStatus.transactionCount),
    helper: '充值与消费流水',
    tone: 'indigo'
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
  }
]))

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
  dataStatus.customerCount = 0
  dataStatus.transactionCount = 0
  dataStatus.beadMaterialCount = 0
  dataStatus.beadBalanceCount = 0
  dataStatus.beadLedgerCount = 0
  dataStatus.beadStocktakeCount = 0
}

const fetchDataStatus = async ({ withFeedback = false } = {}) => {
  statusLoading.value = true
  try {
    const storageResponse = await api.get('/data/storage-info')
    const storageInfo = storageResponse?.data || storageResponse || {}
    const dataCounts = storageInfo.dataCounts || {}

    dataStatus.storageLocation = storageInfo.storageLocation || storageInfo.databaseUri || '本地数据库（路径未知）'
    dataStatus.dataSize = formatFileSize(storageInfo.dataSizeBytes)
    dataStatus.customerCount = safeCount(dataCounts.customers)
    dataStatus.transactionCount = safeCount(dataCounts.transactions)
    dataStatus.beadMaterialCount = safeCount(dataCounts.bead_materials)
    dataStatus.beadBalanceCount = safeCount(dataCounts.bead_inventory_balances)
    dataStatus.beadLedgerCount = safeCount(dataCounts.bead_inventory_ledgers)
    dataStatus.beadStocktakeCount = safeCount(dataCounts.bead_stocktakes)
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
    <section class="settings-hero rounded-3xl p-6 sm:p-8">
      <div class="settings-hero__veil" aria-hidden="true"></div>
      <div class="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div class="max-w-3xl space-y-4">
          <p class="page-hero__eyebrow">Data Control Center</p>
          <h1 class="page-hero__title">数据管理</h1>
          <p class="settings-hero__subtitle">
            统一维护系统备份、恢复与清理流程。所有高风险动作建议先执行备份并确认当前状态。
          </p>
          <div class="settings-hero__meta flex flex-wrap items-center gap-2">
            <span
              :class="[
                'inline-flex items-center rounded-full border px-3 py-1 text-xs sm:text-sm font-semibold',
                statusBadgeStyle
              ]"
            >
              {{ statusBadgeText }}
            </span>
            <span class="inline-flex items-center rounded-full border border-slate-200 bg-white/75 px-3 py-1 text-xs sm:text-sm font-medium text-slate-700">
              最近同步：{{ lastSyncedAt || '尚未刷新' }}
            </span>
          </div>
        </div>

        <button
          type="button"
          :disabled="isAnyActionRunning"
          @click="fetchDataStatus({ withFeedback: true })"
          class="page-hero__action settings-hero__action"
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

    <section class="panel-surface rounded-3xl border border-slate-200/80 p-5 sm:p-6 lg:p-8 space-y-8 shadow-sm">
      <div class="settings-bento grid grid-cols-1 gap-5 xl:grid-cols-[1.45fr_minmax(0,1fr)]">
        <section class="overview-panel rounded-2xl border border-sky-100 bg-gradient-to-b from-white via-white to-sky-50/80 p-5 sm:p-6">
          <div>
            <h2 class="text-lg sm:text-xl font-bold text-slate-900">状态总览</h2>
            <p class="mt-1 text-sm text-slate-500">
              数据快照用于评估系统体量与恢复风险，建议操作前先刷新状态。
            </p>
          </div>

          <div class="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
            <article
              v-for="(card, index) in overviewCards"
              :key="card.key"
              :class="['status-card', `status-card--${card.tone}`]"
              :style="{ animationDelay: `${index * 0.05}s` }"
            >
              <p class="status-card__label">{{ card.label }}</p>
              <p :class="['status-card__value', card.key === 'storageLocation' ? 'break-all' : '']">
                {{ card.value }}
              </p>
              <p class="status-card__helper">{{ card.helper }}</p>
            </article>
          </div>
        </section>

        <section class="operation-panel grid grid-cols-1 gap-5">
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

          <article class="tips-card rounded-2xl border border-indigo-100 bg-indigo-50/70 p-4 text-sm text-indigo-900">
            <h4 class="font-semibold">操作建议</h4>
            <p class="mt-2 leading-relaxed text-indigo-800/90">
              推荐顺序：刷新状态 → 备份数据 → 执行恢复或清理。若状态异常，请先检查网络与权限。
            </p>
          </article>
        </section>
      </div>

      <section class="danger-zone rounded-2xl border border-rose-200 bg-gradient-to-b from-rose-50 to-white p-5 sm:p-6">
        <div class="space-y-2">
          <h3 class="text-lg font-bold text-rose-900">危险操作区</h3>
          <p class="text-sm text-rose-700/90 leading-relaxed">
            清空后将删除客户、交易、活动、豆仓与日志等数据。此操作不可撤销，请确认已完成备份。
          </p>
        </div>
        <button
          type="button"
          :disabled="isAnyActionRunning"
          @click="openClearConfirm"
          class="mt-5 inline-flex w-full items-center justify-center rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
        >
          {{ clearLoading ? '清空中...' : '清空所有数据' }}
        </button>
      </section>
    </section>

    <Teleport to="body">
      <Transition name="modal-fade">
        <div
          v-if="showClearConfirm"
          class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-[1px]"
          @click.self="closeClearConfirm"
        >
          <div
            class="w-full max-w-lg rounded-2xl bg-white shadow-2xl ring-1 ring-black/5"
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
                class="inline-flex items-center justify-center rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                取消
              </button>
              <button
                ref="clearConfirmButtonRef"
                type="button"
                :disabled="clearLoading"
                @click="clearAllData"
                class="inline-flex items-center justify-center rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white transition-all hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 disabled:cursor-not-allowed disabled:opacity-60"
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
  font-family: 'Fira Sans', 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
}

.settings-hero {
  position: relative;
  overflow: hidden;
  border: 1px solid #dbe7f5;
  background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 48%, #f9fbff 100%);
}

.settings-hero__veil {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 10% 10%, rgba(59, 130, 246, 0.14), transparent 36%),
    radial-gradient(circle at 92% 82%, rgba(245, 158, 11, 0.12), transparent 33%);
}

.settings-hero__subtitle {
  max-width: 70ch;
  color: #334155;
  font-size: 0.95rem;
  line-height: 1.65;
}

.settings-hero__action {
  min-height: 44px;
}

.settings-feedback {
  backdrop-filter: blur(2px);
}

.panel-surface {
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.overview-panel {
  box-shadow: inset 0 0 0 1px rgba(186, 230, 253, 0.36);
}

.status-card {
  border: 1px solid #dbe7f5;
  border-radius: 1rem;
  background: #ffffff;
  padding: 1rem;
  min-height: 138px;
  box-shadow: 0 10px 20px -18px rgba(6, 37, 82, 0.65);
  transition: transform 220ms ease, box-shadow 220ms ease, border-color 220ms ease;
  animation: card-in 360ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.status-card:hover {
  transform: translateY(-2px);
  border-color: #b7d7f5;
  box-shadow: 0 16px 30px -20px rgba(15, 76, 129, 0.55);
}

.status-card__label {
  color: #475569;
  font-size: 0.82rem;
  letter-spacing: 0.02em;
}

.status-card__value {
  margin-top: 0.45rem;
  color: #0f172a;
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.4;
}

.status-card__helper {
  margin-top: 0.4rem;
  font-size: 0.78rem;
  color: #64748b;
}

.status-card--amber {
  border-color: #fde68a;
  background: linear-gradient(180deg, #ffffff 0%, #fffbeb 100%);
}

.status-card--sky {
  border-color: #bae6fd;
  background: linear-gradient(180deg, #ffffff 0%, #f0f9ff 100%);
}

.status-card--indigo {
  border-color: #c7d2fe;
  background: linear-gradient(180deg, #ffffff 0%, #eef2ff 100%);
}

.status-card--emerald {
  border-color: #bbf7d0;
  background: linear-gradient(180deg, #ffffff 0%, #f0fdf4 100%);
}

.status-card--teal {
  border-color: #99f6e4;
  background: linear-gradient(180deg, #ffffff 0%, #f0fdfa 100%);
}

.status-card--violet {
  border-color: #ddd6fe;
  background: linear-gradient(180deg, #ffffff 0%, #f5f3ff 100%);
}

.status-card--rose {
  border-color: #fecdd3;
  background: linear-gradient(180deg, #ffffff 0%, #fff1f2 100%);
}

.action-card {
  border-radius: 1rem;
  padding: 1.4rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  border: 1px solid;
  box-shadow: 0 8px 20px -16px rgba(15, 23, 42, 0.55);
}

.action-card--backup {
  background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 88%);
  border-color: #b7e4c7;
}

.action-card--restore {
  background: linear-gradient(180deg, #eff6ff 0%, #ffffff 88%);
  border-color: #bfdbfe;
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
  background: rgba(255, 255, 255, 0.62);
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
  box-shadow: inset 0 0 0 1px rgba(99, 102, 241, 0.06);
}

.action-btn {
  margin-top: auto;
  border-radius: 0.8rem;
  padding: 0.65rem 0.9rem;
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 700;
  transition: transform 180ms ease, filter 180ms ease, opacity 180ms ease;
}

.action-btn:hover:enabled {
  transform: translateY(-1px);
  filter: brightness(1.03);
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
  box-shadow: inset 0 0 0 1px rgba(251, 113, 133, 0.14);
}

.danger-zone::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: repeating-linear-gradient(
    -35deg,
    rgba(244, 63, 94, 0.05),
    rgba(244, 63, 94, 0.05) 6px,
    transparent 6px,
    transparent 16px
  );
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

@media (max-width: 420px) {
  .status-card {
    min-height: 110px;
  }

  .settings-hero__subtitle {
    font-size: 0.9rem;
  }
}
</style>


