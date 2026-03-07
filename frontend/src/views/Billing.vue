<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import api from '@/api'
import { normalizeBillingRules } from '@/utils/consumptionCalculator'

const loading = ref(false)
const saving = ref(false)
const feedback = reactive({
  tone: 'info',
  message: ''
})
let feedbackTimer = null

const billingRules = reactive({
  singlePersonOneHour: 18.9,
  singlePersonTwoHours: 35.8,
  largeImageExtra: 5,
  excessSmallImage: 3,
  excessLargeImage: 5,
  overtimeRatePerMinute: 0.5
})

const overtimeConfig = reactive({
  overtimeFreeMinutes: 10,
  overtime10to30Fee: 10,
  overtime30Fee: 18.9
})

const dayPackageRules = reactive({
  weekday: {
    singleLimited: 35.9,
    unlimitedPackages: []
  },
  weekend: {
    singleLimited: 42.8,
    unlimitedPackages: []
  }
})

const packageEditorState = reactive({})
const panelEditorState = reactive({
  timed: false,
  materials: false,
  overtime: false
})

function clearFeedbackTimer() {
  if (!feedbackTimer) return
  window.clearTimeout(feedbackTimer)
  feedbackTimer = null
}

function showFeedback(tone, message) {
  feedback.tone = tone
  feedback.message = message
  clearFeedbackTimer()
  feedbackTimer = window.setTimeout(() => {
    feedback.message = ''
    feedbackTimer = null
  }, 3600)
}

function getFeedbackClass(tone) {
  if (tone === 'success') return 'management-feedback--success'
  if (tone === 'error') return 'management-feedback--error'
  return 'management-feedback--info'
}

function toNumber(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function toInteger(value, fallback = 0) {
  return Math.max(0, Math.floor(toNumber(value, fallback)))
}

function dayLabel(dayType) {
  return dayType === 'weekend' ? '周末' : '工作日'
}

function formatChineseCount(value) {
  const safeValue = Math.max(1, toInteger(value, 1))
  const map = {
    1: '一',
    2: '二',
    3: '三',
    4: '四',
    5: '五',
    6: '六',
    7: '七',
    8: '八',
    9: '九',
    10: '十'
  }
  return map[safeValue] || String(safeValue)
}

function createLocalPackageId(dayType = 'weekday') {
  return `${dayType}_pkg_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`
}

function normalizePackageCode(code = '', fallbackCode = '') {
  const normalized = String(code || '').trim()
  if (/^[A-Za-z0-9_-]{2,64}$/.test(normalized)) return normalized
  return String(fallbackCode || '').trim()
}

function buildDefaultPackageCode(dayType = 'weekday', peopleCount = 1, index = 1) {
  const safePeopleCount = Math.max(1, toInteger(peopleCount, 1))
  if (safePeopleCount === 1) return dayType === 'weekend' ? 'weekendSingleUnlimited' : 'weekdaySingleUnlimited'
  if (safePeopleCount === 2) return dayType === 'weekend' ? 'weekendDoubleUnlimited' : 'weekdayDoubleUnlimited'
  return `${dayType}Unlimited${safePeopleCount}P${Math.max(1, toInteger(index, 1))}`
}

function ensureUniquePackageCode(dayType, baseCode) {
  const existingCodes = new Set(
    dayPackageRules[dayType].unlimitedPackages
      .map((item) => String(item.code || '').trim())
      .filter(Boolean)
  )
  if (!existingCodes.has(baseCode)) return baseCode

  let suffix = 2
  let candidate = `${baseCode}_${suffix}`
  while (existingCodes.has(candidate)) {
    suffix += 1
    candidate = `${baseCode}_${suffix}`
  }
  return candidate
}

function createEmptyPackage(dayType = 'weekday', index = 1, peopleCount = 1) {
  const defaultCode = buildDefaultPackageCode(dayType, peopleCount, index)
  const uniqueCode = ensureUniquePackageCode(dayType, defaultCode)
  return {
    id: createLocalPackageId(dayType),
    code: uniqueCode,
    label: `${dayLabel(dayType)}${formatChineseCount(peopleCount)}人不限时不限板`,
    people_count: Math.max(1, peopleCount),
    price: 0,
    enabled: true,
    sort_order: Math.max(1, index)
  }
}

function getPackageEditorKey(dayType, packageId) {
  return `${dayType}:${String(packageId || '')}`
}

function isPackageEditorOpen(dayType, packageId) {
  return packageEditorState[getPackageEditorKey(dayType, packageId)] === true
}

function setPackageEditorOpen(dayType, packageId, open) {
  packageEditorState[getPackageEditorKey(dayType, packageId)] = open === true
}

function togglePackageEditor(dayType, packageId) {
  const nextOpen = !isPackageEditorOpen(dayType, packageId)
  setPackageEditorOpen(dayType, packageId, nextOpen)
}

function syncDayPackages(dayType, sourceRule = {}) {
  const sourcePackages = Array.isArray(sourceRule?.unlimited_packages)
    ? sourceRule.unlimited_packages
    : []

  const normalizedPackages = sourcePackages
    .map((item, index) => {
      const peopleCount = Math.max(1, toInteger(item?.people_count ?? item?.peopleCount, 1))
      const fallbackCode = buildDefaultPackageCode(dayType, peopleCount, index + 1)
      return {
        id: String(item?.id || createLocalPackageId(dayType)).trim() || createLocalPackageId(dayType),
        code: normalizePackageCode(item?.code, fallbackCode) || fallbackCode,
        label: String(item?.label || '').trim() || `${dayLabel(dayType)}${formatChineseCount(peopleCount)}人不限时不限板`,
        people_count: peopleCount,
        price: Math.max(0, toNumber(item?.price, 0)),
        enabled: item?.enabled !== false,
        sort_order: Math.max(1, toInteger(item?.sort_order ?? item?.sortOrder, index + 1))
      }
    })
    .sort((left, right) => {
      if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order
      if (left.people_count !== right.people_count) return left.people_count - right.people_count
      return String(left.code || '').localeCompare(String(right.code || ''), 'en-US')
    })
    .map((item, index) => ({
      ...item,
      sort_order: index + 1
    }))

  dayPackageRules[dayType].unlimitedPackages = normalizedPackages.length > 0
    ? normalizedPackages
    : [createEmptyPackage(dayType, 1, 1)]
}

function applyGroupedRules(data = {}) {
  const normalized = normalizeBillingRules(data)
  const limited = normalized.limited || {}
  const materials = normalized.materials || {}
  const overtime = normalized.overtime || {}

  billingRules.singlePersonOneHour = Math.max(0, toNumber(limited.price1h, billingRules.singlePersonOneHour))
  billingRules.singlePersonTwoHours = Math.max(0, toNumber(limited.price2h, billingRules.singlePersonTwoHours))
  overtimeConfig.overtimeFreeMinutes = Math.max(0, toInteger(limited.overtimeFreeMinutes, overtimeConfig.overtimeFreeMinutes))
  overtimeConfig.overtime10to30Fee = Math.max(0, toNumber(limited.overtime10to30Fee, overtimeConfig.overtime10to30Fee))
  overtimeConfig.overtime30Fee = Math.max(0, toNumber(limited.overtime30Fee, overtimeConfig.overtime30Fee))

  dayPackageRules.weekday.singleLimited = Math.max(0, toNumber(normalized.weekday?.singleLimited, dayPackageRules.weekday.singleLimited))
  dayPackageRules.weekend.singleLimited = Math.max(0, toNumber(normalized.weekend?.singleLimited, dayPackageRules.weekend.singleLimited))
  syncDayPackages('weekday', normalized.weekday || {})
  syncDayPackages('weekend', normalized.weekend || {})

  billingRules.largeImageExtra = Math.max(0, toNumber(materials.largeImageFee, billingRules.largeImageExtra))
  billingRules.excessSmallImage = Math.max(0, toNumber(materials.extraSmallImageFee, billingRules.excessSmallImage))
  billingRules.excessLargeImage = Math.max(0, toNumber(materials.extraLargeImageFee, billingRules.excessLargeImage))
  billingRules.overtimeRatePerMinute = Math.max(0, toNumber(overtime.ratePerMinute, billingRules.overtimeRatePerMinute))
}

function isGroupedRulesPayload(data) {
  return Boolean(data && typeof data === 'object' && (data.limited || data.weekday || data.weekend || data.materials || data.overtime))
}

const overtimeRuleSummary = computed(() => {
  const freeMinutes = Math.max(0, toInteger(overtimeConfig.overtimeFreeMinutes, 10))
  const fee10to30 = Math.max(0, toNumber(overtimeConfig.overtime10to30Fee, 10))
  const fee30Plus = Math.max(0, toNumber(overtimeConfig.overtime30Fee, billingRules.singlePersonOneHour))
  return `0-${freeMinutes}分钟免费，${freeMinutes}-30分钟加收${fee10to30}，30分钟以上每小时加收${fee30Plus}`
})

function formatCurrency(value) {
  const amount = Math.max(0, toNumber(value, 0))
  return `￥${amount.toFixed(2)}`
}

const daySectionMeta = Object.freeze({
  weekday: {
    badge: '工作日',
    title: '工作日不限板套餐',
    description: '',
    tone: 'weekday'
  },
  weekend: {
    badge: '周末',
    title: '周末不限板套餐',
    description: '',
    tone: 'weekend'
  }
})

const timedHighlights = computed(() => ([
  {
    label: '1小时',
    value: formatCurrency(billingRules.singlePersonOneHour),
    note: '单人限时基础价'
  },
  {
    label: '2小时',
    value: formatCurrency(billingRules.singlePersonTwoHours),
    note: '延长停留的标准价'
  },
  {
    label: '免费时长',
    value: `${Math.max(0, toInteger(overtimeConfig.overtimeFreeMinutes, 0))} 分钟`,
    note: '超时前缓冲区'
  },
  {
    label: '10-30分钟',
    value: formatCurrency(overtimeConfig.overtime10to30Fee),
    note: '首段超时加收'
  },
  {
    label: '30分钟以上',
    value: formatCurrency(overtimeConfig.overtime30Fee),
    note: '按小时续费基准'
  }
]))

const materialHighlights = computed(() => ([
  {
    label: '大图加收',
    value: formatCurrency(billingRules.largeImageExtra)
  },
  {
    label: '超量小图',
    value: formatCurrency(billingRules.excessSmallImage)
  },
  {
    label: '超量大图',
    value: formatCurrency(billingRules.excessLargeImage)
  }
]))

function addUnlimitedPackage(dayType) {
  const list = dayPackageRules[dayType].unlimitedPackages
  const maxPeople = list.reduce((maxValue, item) => Math.max(maxValue, Math.max(1, toInteger(item?.people_count, 1))), 1)
  const nextPeople = maxPeople + 1
  const nextPackage = createEmptyPackage(dayType, list.length + 1, nextPeople)
  list.push(nextPackage)
  setPackageEditorOpen(dayType, nextPackage.id, true)
  resequenceDayPackages(dayType)
}

function resequenceDayPackages(dayType) {
  dayPackageRules[dayType].unlimitedPackages = dayPackageRules[dayType].unlimitedPackages
    .map((item, index) => ({
      ...item,
      sort_order: index + 1
    }))
}

function moveUnlimitedPackage(dayType, index, offset) {
  const list = dayPackageRules[dayType].unlimitedPackages
  const targetIndex = index + offset
  if (targetIndex < 0 || targetIndex >= list.length) return
  const current = list[index]
  list.splice(index, 1)
  list.splice(targetIndex, 0, current)
  resequenceDayPackages(dayType)
}

function removeUnlimitedPackage(dayType, packageId) {
  const list = dayPackageRules[dayType].unlimitedPackages
  if (list.length <= 1) {
    showFeedback('error', `${dayLabel(dayType)}至少保留一个不限板套餐`)
    return
  }

  const nextList = list.filter((item) => String(item.id || '') !== String(packageId || ''))
  const enabledCount = nextList.filter((item) => item.enabled !== false).length
  if (enabledCount === 0) {
    showFeedback('error', `${dayLabel(dayType)}至少保留一个启用的不限板套餐`)
    return
  }

  dayPackageRules[dayType].unlimitedPackages = nextList
  delete packageEditorState[getPackageEditorKey(dayType, packageId)]
  resequenceDayPackages(dayType)
}

function handlePackageEnabledChange(dayType, packageItem) {
  const list = dayPackageRules[dayType].unlimitedPackages
  const enabledCount = list.filter((item) => item.enabled !== false).length
  if (enabledCount > 0) return
  packageItem.enabled = true
  showFeedback('error', `${dayLabel(dayType)}至少保留一个启用的不限板套餐`)
}

function normalizePayloadDayPackages(dayType) {
  const dayRule = dayPackageRules[dayType]
  const list = Array.isArray(dayRule.unlimitedPackages) ? dayRule.unlimitedPackages : []
  if (list.length === 0) {
    throw new Error(`${dayLabel(dayType)}至少保留一个不限板套餐`)
  }

  const seenCodes = new Set()
  const normalizedPackages = list.map((item, index) => {
    const code = normalizePackageCode(item?.code)
    if (!code) {
      throw new Error(`${dayLabel(dayType)}套餐编码不能为空，且只能包含字母/数字/_/-`)
    }
    if (seenCodes.has(code)) {
      throw new Error(`${dayLabel(dayType)}套餐编码重复：${code}`)
    }
    seenCodes.add(code)

    const peopleCount = Math.max(1, toInteger(item?.people_count, 1))
    const price = Math.max(0, toNumber(item?.price, 0))
    const label = String(item?.label || '').trim() || `${dayLabel(dayType)}${peopleCount}人不限时不限板`
    const packageId = String(item?.id || createLocalPackageId(dayType)).trim() || createLocalPackageId(dayType)

    return {
      id: packageId,
      code,
      label,
      people_count: peopleCount,
      price,
      enabled: item?.enabled !== false,
      sort_order: index + 1
    }
  })

  if (!normalizedPackages.some((item) => item.enabled)) {
    throw new Error(`${dayLabel(dayType)}至少保留一个启用的不限板套餐`)
  }

  const singleLimited = Math.max(0, toNumber(dayRule.singleLimited, 0))
  return {
    singleLimited,
    unlimited_packages: normalizedPackages
  }
}

async function fetchBillingRules() {
  loading.value = true
  try {
    const response = await api.get('/billing-rules')
    const payload = response?.data || response || {}
    if (isGroupedRulesPayload(payload)) {
      applyGroupedRules(payload)
    } else {
      applyGroupedRules(payload?.data || {})
    }
  } catch (error) {
    console.error('获取计费规则失败:', error)
    showFeedback('error', '计费规则加载失败，请稍后重试。')
  } finally {
    loading.value = false
  }
}

async function saveBillingRules() {
  saving.value = true
  try {
    const weekdayPayload = normalizePayloadDayPackages('weekday')
    const weekendPayload = normalizePayloadDayPackages('weekend')

    const payload = {
      limited: {
        price1h: Math.max(0, toNumber(billingRules.singlePersonOneHour)),
        price2h: Math.max(0, toNumber(billingRules.singlePersonTwoHours)),
        overtimeFreeMinutes: Math.max(0, toInteger(overtimeConfig.overtimeFreeMinutes, 10)),
        overtime10to30Fee: Math.max(0, toNumber(overtimeConfig.overtime10to30Fee, 10)),
        overtime30Fee: Math.max(0, toNumber(overtimeConfig.overtime30Fee, billingRules.singlePersonOneHour))
      },
      weekday: weekdayPayload,
      weekend: weekendPayload,
      materials: {
        largeImageFee: Math.max(0, toNumber(billingRules.largeImageExtra)),
        extraSmallImageFee: Math.max(0, toNumber(billingRules.excessSmallImage)),
        extraLargeImageFee: Math.max(0, toNumber(billingRules.excessLargeImage))
      },
      overtime: {
        ratePerMinute: Math.max(0, toNumber(billingRules.overtimeRatePerMinute, 0.5))
      }
    }

    await api.put('/billing-rules', payload)
    await fetchBillingRules()
    showFeedback('success', '计费规则已保存。')
  } catch (error) {
    console.error('保存计费规则失败:', error)
    showFeedback('error', error?.response?.data?.message || error?.message || '保存计费规则失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchBillingRules()
})

onUnmounted(() => {
  clearFeedbackTimer()
})
</script>

<template>
  <div class="space-y-6">
    <section class="page-hero rounded-3xl p-6 sm:p-8">
      <div class="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div class="max-w-2xl space-y-2">
          <p class="page-hero__eyebrow">Pricing Workspace</p>
          <h1 class="page-hero__title">计费规则</h1>
        </div>

        <button
          :disabled="saving"
          class="page-hero__action"
          @click="saveBillingRules"
        >
          <svg v-if="saving" class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
          </svg>
          <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <span>{{ saving ? '保存中...' : '保存规则' }}</span>
        </button>
      </div>
    </section>

    <Transition name="notice">
      <div
        v-if="feedback.message"
        role="status"
        aria-live="polite"
        :class="['management-feedback flex items-center gap-2', getFeedbackClass(feedback.tone)]"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" />
        </svg>
        <span>{{ feedback.message }}</span>
      </div>
    </Transition>

    <div v-if="loading" class="management-surface flex items-center justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-[#1e40af]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
      </svg>
    </div>

    <div v-else class="billing-workspace space-y-4 xl:space-y-5">
      <section class="billing-main-grid">
        <article class="billing-panel billing-panel--primary">
          <div class="billing-panel__header">
            <div>
              <p class="billing-panel__eyebrow">Timed Packages</p>
              <h2 class="billing-panel__title">限时套餐与超时规则</h2>
            </div>
            <div class="billing-panel__pill">当前生效</div>
          </div>

          <div class="billing-panel__summary-grid">
            <article
              v-for="item in timedHighlights"
              :key="item.label"
              class="billing-summary-tile"
            >
              <span class="billing-summary-tile__label">{{ item.label }}</span>
              <strong class="billing-summary-tile__value">{{ item.value }}</strong>
              <small class="billing-summary-tile__note">{{ item.note }}</small>
            </article>
          </div>

          <div class="billing-highlight mt-5">
            <p class="billing-highlight__label">规则摘要</p>
            <p class="billing-highlight__value">{{ overtimeRuleSummary }}</p>
          </div>

          <div class="billing-panel__actions">
            <button
              type="button"
              class="billing-action-button billing-action-button--accent"
              @click="panelEditorState.timed = !panelEditorState.timed"
            >
              {{ panelEditorState.timed ? '收起编辑' : '编辑规则' }}
            </button>
          </div>

          <Transition name="billing-editor">
            <div v-if="panelEditorState.timed" class="billing-panel__editor-grid">
              <div class="billing-field">
                <label class="billing-field__label">1小时价格</label>
                <input v-model.number="billingRules.singlePersonOneHour" type="number" min="0" step="0.01" class="billing-input" />
              </div>
              <div class="billing-field">
                <label class="billing-field__label">2小时价格</label>
                <input v-model.number="billingRules.singlePersonTwoHours" type="number" min="0" step="0.01" class="billing-input" />
              </div>
              <div class="billing-field">
                <label class="billing-field__label">超时免费分钟</label>
                <input v-model.number="overtimeConfig.overtimeFreeMinutes" type="number" min="0" step="1" class="billing-input" />
              </div>
              <div class="billing-field">
                <label class="billing-field__label">超时10-30分钟加收</label>
                <input v-model.number="overtimeConfig.overtime10to30Fee" type="number" min="0" step="0.01" class="billing-input" />
              </div>
              <div class="billing-field md:col-span-2">
                <label class="billing-field__label">超时30分钟后每小时加收</label>
                <input v-model.number="overtimeConfig.overtime30Fee" type="number" min="0" step="0.01" class="billing-input" />
              </div>
            </div>
          </Transition>
        </article>

        <div class="billing-side-stack">
          <article class="billing-panel billing-panel--materials">
            <div class="billing-panel__header">
              <div>
                <p class="billing-panel__eyebrow">Material Fees</p>
                <h2 class="billing-panel__title">素材费用</h2>
              </div>
              <div class="billing-panel__pill">附加项</div>
            </div>

            <div class="billing-panel__summary-grid billing-panel__summary-grid--compact">
              <article
                v-for="item in materialHighlights"
                :key="item.label"
                class="billing-summary-tile billing-summary-tile--compact"
              >
                <span class="billing-summary-tile__label">{{ item.label }}</span>
                <strong class="billing-summary-tile__value">{{ item.value }}</strong>
              </article>
            </div>

            <div class="billing-panel__actions">
              <button
                type="button"
                class="billing-action-button billing-action-button--accent"
                @click="panelEditorState.materials = !panelEditorState.materials"
              >
                {{ panelEditorState.materials ? '收起编辑' : '编辑费用' }}
              </button>
            </div>

            <Transition name="billing-editor">
              <div v-if="panelEditorState.materials" class="billing-panel__editor-grid">
                <div class="billing-field">
                  <label class="billing-field__label">大图加收</label>
                  <input v-model.number="billingRules.largeImageExtra" type="number" min="0" step="0.01" class="billing-input" />
                </div>
                <div class="billing-field">
                  <label class="billing-field__label">超量小图加收</label>
                  <input v-model.number="billingRules.excessSmallImage" type="number" min="0" step="0.01" class="billing-input" />
                </div>
                <div class="billing-field md:col-span-2">
                  <label class="billing-field__label">超量大图加收</label>
                  <input v-model.number="billingRules.excessLargeImage" type="number" min="0" step="0.01" class="billing-input" />
                </div>
              </div>
            </Transition>
          </article>

          <article class="billing-panel billing-panel--overtime">
            <div class="billing-panel__header">
              <div>
                <p class="billing-panel__eyebrow">Overtime</p>
                <h2 class="billing-panel__title">加班费用</h2>
              </div>
              <div class="billing-panel__pill">分钟计费</div>
            </div>

            <div class="billing-summary-line">
              <span class="billing-summary-line__label">当前单价</span>
              <strong class="billing-summary-line__value">{{ formatCurrency(billingRules.overtimeRatePerMinute) }}</strong>
              <span class="billing-summary-line__note">按分钟计费，用于加班补差</span>
            </div>

            <div class="billing-panel__actions">
              <button
                type="button"
                class="billing-action-button billing-action-button--accent"
                @click="panelEditorState.overtime = !panelEditorState.overtime"
              >
                {{ panelEditorState.overtime ? '收起编辑' : '编辑单价' }}
              </button>
            </div>

            <Transition name="billing-editor">
              <div v-if="panelEditorState.overtime" class="billing-panel__editor-grid">
                <div class="billing-field max-w-sm">
                  <label class="billing-field__label">每分钟费用</label>
                  <input v-model.number="billingRules.overtimeRatePerMinute" type="number" min="0" step="0.01" class="billing-input" />
                </div>
              </div>
            </Transition>
          </article>
        </div>
      </section>

      <section class="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:gap-5">
        <article
          v-for="dayType in ['weekday', 'weekend']"
          :key="dayType"
          :class="['billing-day-panel', `billing-day-panel--${daySectionMeta[dayType].tone}`]"
        >
          <div class="billing-day-panel__hero">
            <div>
              <span class="billing-day-panel__badge">{{ daySectionMeta[dayType].badge }}</span>
              <h2 class="billing-day-panel__title">{{ daySectionMeta[dayType].title }}</h2>
              <p class="billing-day-panel__desc">{{ daySectionMeta[dayType].description }}</p>
            </div>
            <button
              type="button"
              class="billing-add-button"
              @click="addUnlimitedPackage(dayType)"
            >
              新增套餐
            </button>
          </div>

          <div class="billing-inline-stat">
            <div>
              <span class="billing-inline-stat__label">启用套餐</span>
              <strong class="billing-inline-stat__value">{{ dayPackageRules[dayType].unlimitedPackages.filter(item => item.enabled !== false).length }}</strong>
            </div>
            <div>
              <span class="billing-inline-stat__label">总套餐数</span>
              <strong class="billing-inline-stat__value">{{ dayPackageRules[dayType].unlimitedPackages.length }}</strong>
            </div>
            <div>
              <span class="billing-inline-stat__label">单人限板价</span>
              <strong class="billing-inline-stat__value">{{ formatCurrency(dayPackageRules[dayType].singleLimited) }}</strong>
            </div>
          </div>

          <div class="space-y-4">
            <article
              v-for="(item, index) in dayPackageRules[dayType].unlimitedPackages"
              :key="item.id"
              class="billing-package-card"
            >
              <div class="billing-package-card__top">
                <div>
                  <p class="billing-package-card__order">套餐 {{ index + 1 }}</p>
                  <h3 class="billing-package-card__name">{{ item.label || `${dayLabel(dayType)}${Math.max(1, toInteger(item.people_count, 1))}人不限时不限板` }}</h3>
                  <div class="billing-package-card__badges">
                    <span class="billing-package-card__badge">
                      <strong>{{ Math.max(1, toInteger(item.people_count, 1)) }}</strong>
                      <em>人数</em>
                    </span>
                    <span class="billing-package-card__badge billing-package-card__badge--price">
                      <strong>{{ formatCurrency(item.price) }}</strong>
                      <em>套餐价</em>
                    </span>
                    <span :class="['billing-package-card__badge', item.enabled ? 'billing-package-card__badge--enabled' : 'billing-package-card__badge--disabled']">
                      <strong>{{ item.enabled ? '启用中' : '已停用' }}</strong>
                      <em>状态</em>
                    </span>
                  </div>
                </div>
                <label class="billing-toggle">
                  <input
                    v-model="item.enabled"
                    type="checkbox"
                    class="billing-toggle__input"
                    @change="handlePackageEnabledChange(dayType, item)"
                  />
                  <span class="billing-toggle__track"></span>
                  <span class="billing-toggle__text">{{ item.enabled ? '已启用' : '已停用' }}</span>
                </label>
              </div>

              <div class="billing-package-card__actions">
                <button
                  type="button"
                  class="billing-action-button billing-action-button--accent"
                  @click="togglePackageEditor(dayType, item.id)"
                >
                  {{ isPackageEditorOpen(dayType, item.id) ? '收起编辑' : '编辑套餐' }}
                </button>
                <button
                  type="button"
                  class="billing-action-button"
                  :disabled="index === 0"
                  @click="moveUnlimitedPackage(dayType, index, -1)"
                >
                  上移
                </button>
                <button
                  type="button"
                  class="billing-action-button"
                  :disabled="index === dayPackageRules[dayType].unlimitedPackages.length - 1"
                  @click="moveUnlimitedPackage(dayType, index, 1)"
                >
                  下移
                </button>
                <button
                  type="button"
                  class="billing-action-button billing-action-button--danger"
                  @click="removeUnlimitedPackage(dayType, item.id)"
                >
                  删除
                </button>
                <span class="billing-package-card__sort">排序 {{ index + 1 }}</span>
              </div>

              <Transition name="billing-editor">
                <div v-if="isPackageEditorOpen(dayType, item.id)" class="billing-package-card__editor">
                  <div class="billing-field md:col-span-2">
                    <label class="billing-field__label">套餐名称</label>
                    <input
                      v-model="item.label"
                      type="text"
                      class="billing-input"
                      placeholder="例如：工作日3人不限时不限板"
                    />
                  </div>
                  <div class="billing-field">
                    <label class="billing-field__label">人数</label>
                    <input
                      v-model.number="item.people_count"
                      type="number"
                      min="1"
                      step="1"
                      class="billing-input"
                    />
                  </div>
                  <div class="billing-field">
                    <label class="billing-field__label">价格</label>
                    <input
                      v-model.number="item.price"
                      type="number"
                      min="0"
                      step="0.01"
                      class="billing-input"
                    />
                  </div>
                  <div class="billing-package-card__insight">
                    <span class="billing-package-card__insight-label">当前价格</span>
                    <strong>{{ formatCurrency(item.price) }}</strong>
                    <small>{{ item.enabled ? '已参与结算' : '暂不参与结算' }}</small>
                  </div>
                </div>
              </Transition>
            </article>
          </div>

          <div class="billing-highlight billing-highlight--subtle">
            <label class="billing-field__label">{{ dayLabel(dayType) }}单人不限时限板</label>
            <input
              v-model.number="dayPackageRules[dayType].singleLimited"
              type="number"
              min="0"
              step="0.01"
              class="billing-input mt-2"
            />
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<style scoped>
.billing-workspace {
  position: relative;
}

.billing-main-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
}

.billing-side-stack {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
}

.billing-panel,
.billing-day-panel {
  position: relative;
  overflow: hidden;
  border-radius: 1.75rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 252, 0.85));
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(14px);
}

.billing-panel {
  padding: 1.15rem;
}

.billing-panel--primary {
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.14), transparent 28%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(239, 246, 255, 0.86));
  min-height: 100%;
}

.billing-panel--materials {
  padding: 1.05rem 1.15rem;
  background:
    radial-gradient(circle at top right, rgba(16, 185, 129, 0.16), transparent 34%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(236, 253, 245, 0.88));
}

.billing-panel--overtime {
  padding: 1.05rem 1.15rem;
  background:
    radial-gradient(circle at top right, rgba(139, 92, 246, 0.14), transparent 34%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(245, 243, 255, 0.88));
}

.billing-panel__header,
.billing-day-panel__hero,
.billing-package-card__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.billing-panel__eyebrow {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.billing-panel__title,
.billing-day-panel__title {
  margin-top: 0.35rem;
  font-size: 1.18rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #0f172a;
}

.billing-panel__pill,
.billing-day-panel__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2rem;
  padding: 0.35rem 0.8rem;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 700;
  color: #0f172a;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.22);
}

.billing-day-panel {
  padding: 1.1rem;
}

.billing-day-panel--weekday {
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.14), transparent 28%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(240, 249, 255, 0.88));
}

.billing-day-panel--weekend {
  background:
    radial-gradient(circle at top left, rgba(245, 158, 11, 0.18), transparent 28%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.95), rgba(255, 251, 235, 0.88));
}

.billing-day-panel__desc {
  margin-top: 0.3rem;
  max-width: 34rem;
  font-size: 0.84rem;
  line-height: 1.45;
  color: #475569;
}

.billing-field {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.billing-field__label {
  font-size: 0.9rem;
  font-weight: 700;
  color: #334155;
}

.billing-input {
  width: 100%;
  min-height: 2.65rem;
  border-radius: 1rem;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.78);
  padding: 0.68rem 0.85rem;
  font-size: 0.9rem;
  color: #0f172a;
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease, background-color 180ms ease;
}

.billing-input:hover {
  border-color: rgba(59, 130, 246, 0.32);
  background: rgba(255, 255, 255, 0.92);
}

.billing-input:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.55);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.12);
  background: rgba(255, 255, 255, 0.98);
}

.billing-input--mono {
  font-family: 'Consolas', 'SFMono-Regular', monospace;
}

.billing-highlight {
  border-radius: 1.25rem;
  border: 1px solid rgba(125, 211, 252, 0.32);
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.92), rgba(224, 242, 254, 0.78));
  padding: 0.82rem 0.95rem;
}

.billing-highlight--subtle {
  border-color: rgba(148, 163, 184, 0.2);
  background: linear-gradient(135deg, rgba(255,255,255,0.82), rgba(248, 250, 252, 0.72));
}

.billing-highlight__label {
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #0369a1;
}

.billing-highlight__value {
  margin-top: 0.28rem;
  font-size: 0.9rem;
  line-height: 1.55;
  color: #0f172a;
}

.billing-panel__summary-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 0.65rem;
  margin-top: 0.8rem;
}

.billing-panel__summary-grid--compact {
  grid-template-columns: repeat(1, minmax(0, 1fr));
}

.billing-summary-tile {
  border-radius: 1.15rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.74);
  padding: 0.72rem 0.82rem;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}

.billing-summary-tile--compact {
  padding: 0.68rem 0.8rem;
}

.billing-summary-tile__label {
  display: block;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #64748b;
}

.billing-summary-tile__value {
  display: block;
  margin-top: 0.28rem;
  font-size: 1.08rem;
  font-weight: 800;
  color: #0f172a;
}

.billing-summary-tile__note {
  display: block;
  margin-top: 0.18rem;
  font-size: 0.74rem;
  line-height: 1.35;
  color: #64748b;
}

.billing-summary-line {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.75rem;
  padding: 0.8rem 0.9rem;
  border-radius: 1.2rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.74);
}

.billing-summary-line__label {
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #64748b;
}

.billing-summary-line__value {
  font-size: 1.18rem;
  font-weight: 800;
  color: #0f172a;
}

.billing-summary-line__note {
  font-size: 0.84rem;
  color: #64748b;
}

.billing-panel__actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.billing-panel__editor-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 0.8rem;
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.28);
}

.billing-add-button,
.billing-action-button {
  min-height: 2.35rem;
  border-radius: 0.95rem;
  border: 1px solid rgba(148, 163, 184, 0.24);
  padding: 0.55rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: #0f172a;
  background: rgba(255, 255, 255, 0.74);
  transition: transform 180ms ease, box-shadow 180ms ease, background-color 180ms ease, border-color 180ms ease;
  cursor: pointer;
}

.billing-add-button:hover,
.billing-action-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.08);
  border-color: rgba(59, 130, 246, 0.24);
  background: rgba(255, 255, 255, 0.9);
}

.billing-add-button:focus-visible,
.billing-action-button:focus-visible,
.billing-toggle__input:focus-visible + .billing-toggle__track {
  outline: none;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.16);
}

.billing-action-button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
  transform: none;
  box-shadow: none;
}

.billing-action-button--danger {
  color: #be123c;
  border-color: rgba(244, 63, 94, 0.22);
}

.billing-action-button--accent {
  color: #0f3d91;
  border-color: rgba(59, 130, 246, 0.28);
  background: linear-gradient(135deg, rgba(219, 234, 254, 0.9), rgba(239, 246, 255, 0.88));
}

.billing-inline-stat {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.6rem;
  margin: 0.75rem 0;
}

.billing-inline-stat > div {
  border-radius: 1.1rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.64);
  padding: 0.72rem 0.82rem;
}

.billing-inline-stat__label {
  display: block;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}

.billing-inline-stat__value {
  display: block;
  margin-top: 0.24rem;
  font-size: 1rem;
  font-weight: 800;
  color: #0f172a;
}

.billing-package-card {
  border-radius: 1.35rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(248,250,252,0.8));
  padding: 0.82rem;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}

.billing-package-card__order {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}

.billing-package-card__name {
  margin-top: 0.2rem;
  font-size: 0.94rem;
  font-weight: 800;
  color: #0f172a;
}

.billing-package-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.55rem;
}

.billing-package-card__badge {
  display: inline-flex;
  flex-direction: column;
  gap: 0.12rem;
  min-width: 5.2rem;
  padding: 0.5rem 0.65rem;
  border-radius: 1rem;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(255, 255, 255, 0.8);
}

.billing-package-card__badge strong {
  font-size: 0.96rem;
  font-weight: 800;
  color: #0f172a;
}

.billing-package-card__badge em {
  font-style: normal;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}

.billing-package-card__badge--price {
  background: linear-gradient(135deg, rgba(240, 249, 255, 0.92), rgba(224, 242, 254, 0.88));
}

.billing-package-card__badge--enabled {
  background: linear-gradient(135deg, rgba(236, 253, 245, 0.94), rgba(209, 250, 229, 0.88));
}

.billing-package-card__badge--disabled {
  background: linear-gradient(135deg, rgba(248, 250, 252, 0.94), rgba(226, 232, 240, 0.88));
}

.billing-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  cursor: pointer;
}

.billing-toggle__input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.billing-toggle__track {
  position: relative;
  width: 3rem;
  height: 1.7rem;
  border-radius: 9999px;
  background: rgba(148, 163, 184, 0.4);
  transition: background-color 180ms ease;
}

.billing-toggle__track::after {
  content: '';
  position: absolute;
  top: 0.18rem;
  left: 0.2rem;
  width: 1.34rem;
  height: 1.34rem;
  border-radius: 9999px;
  background: #fff;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.18);
  transition: transform 180ms ease;
}

.billing-toggle__input:checked + .billing-toggle__track {
  background: linear-gradient(90deg, #0ea5e9, #22c55e);
}

.billing-toggle__input:checked + .billing-toggle__track::after {
  transform: translateX(1.28rem);
}

.billing-toggle__text {
  font-size: 0.85rem;
  font-weight: 700;
  color: #334155;
}

.billing-package-card__editor {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 0.95rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px dashed rgba(148, 163, 184, 0.28);
}

.billing-package-card__insight {
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-radius: 1rem;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.78);
  padding: 0.8rem 0.95rem;
  color: #475569;
}

.billing-package-card__insight-label {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
}

.billing-package-card__insight strong {
  margin-top: 0.35rem;
  font-size: 1.2rem;
  font-weight: 800;
  color: #0f172a;
}

.billing-package-card__insight small {
  margin-top: 0.28rem;
  font-size: 0.8rem;
  color: #64748b;
}

.billing-package-card__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  margin-top: 0.7rem;
}

.billing-package-card__sort {
  margin-left: auto;
  font-size: 0.82rem;
  font-weight: 700;
  color: #64748b;
}

.billing-editor-enter-active,
.billing-editor-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.billing-editor-enter-from,
.billing-editor-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (min-width: 768px) {
  .billing-panel__summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .billing-panel__summary-grid--compact {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .billing-panel__editor-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .billing-package-card__editor {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 1280px) {
  .billing-main-grid {
    grid-template-columns: minmax(0, 1.25fr) minmax(17rem, 0.82fr);
  }

  .billing-side-stack {
    align-content: start;
  }

  .billing-panel__summary-grid {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
}

@media (max-width: 767px) {
  .billing-panel,
  .billing-panel--materials,
  .billing-panel--overtime,
  .billing-day-panel {
    padding: 1.15rem;
    border-radius: 1.4rem;
  }

  .billing-panel__header,
  .billing-day-panel__hero,
  .billing-package-card__top {
    flex-direction: column;
  }

  .billing-inline-stat {
    grid-template-columns: 1fr;
  }

  .billing-package-card__badges {
    width: 100%;
  }

  .billing-package-card__badge {
    flex: 1 1 calc(50% - 0.55rem);
  }

  .billing-package-card__sort {
    margin-left: 0;
  }

  .billing-panel__actions {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .billing-input,
  .billing-add-button,
  .billing-action-button,
  .billing-toggle__track,
  .billing-toggle__track::after {
    transition: none;
  }
}
</style>
