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
    label: `${dayLabel(dayType)}${Math.max(1, peopleCount)}人不限时不限板`,
    people_count: Math.max(1, peopleCount),
    price: 0,
    enabled: true,
    sort_order: Math.max(1, index)
  }
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
        label: String(item?.label || '').trim() || `${dayLabel(dayType)}${peopleCount}人不限时不限板`,
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

function addUnlimitedPackage(dayType) {
  const list = dayPackageRules[dayType].unlimitedPackages
  const maxPeople = list.reduce((maxValue, item) => Math.max(maxValue, Math.max(1, toInteger(item?.people_count, 1))), 1)
  const nextPeople = maxPeople + 1
  list.push(createEmptyPackage(dayType, list.length + 1, nextPeople))
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

    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="management-surface p-6 space-y-4">
        <h2 class="text-lg font-semibold text-slate-800">限时套餐</h2>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">1小时价格</label>
          <input v-model.number="billingRules.singlePersonOneHour" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">2小时价格</label>
          <input v-model.number="billingRules.singlePersonTwoHours" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">超时免费分钟</label>
          <input v-model.number="overtimeConfig.overtimeFreeMinutes" type="number" min="0" step="1" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">超时10-30分钟加收</label>
          <input v-model.number="overtimeConfig.overtime10to30Fee" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">超时30分钟后每小时加收</label>
          <input v-model.number="overtimeConfig.overtime30Fee" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">超时规则说明</label>
          <p class="px-3 py-2 bg-sky-50 border border-sky-100 rounded-xl text-sm text-slate-700">
            {{ overtimeRuleSummary }}
          </p>
        </div>
      </div>

      <div
        v-for="dayType in ['weekday', 'weekend']"
        :key="dayType"
        class="management-surface p-6 space-y-4"
      >
        <div class="flex items-center justify-between">
          <h2 class="text-lg font-semibold text-slate-800">{{ dayLabel(dayType) }}不限板套餐</h2>
          <button
            type="button"
            class="px-3 py-1.5 rounded-lg text-xs bg-blue-50 text-blue-700 hover:bg-blue-100"
            @click="addUnlimitedPackage(dayType)"
          >
            新增套餐
          </button>
        </div>

        <div class="space-y-3">
          <div
            v-for="(item, index) in dayPackageRules[dayType].unlimitedPackages"
            :key="item.id"
            class="rounded-xl border border-slate-200 p-3 bg-slate-50 space-y-3"
          >
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">套餐名称</label>
                <input
                  v-model="item.label"
                  type="text"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="例如：工作日3人不限时不限板"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">编码（唯一）</label>
                <input
                  v-model="item.code"
                  type="text"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="例如：weekdayUnlimited3P"
                />
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">人数</label>
                <input
                  v-model.number="item.people_count"
                  type="number"
                  min="1"
                  step="1"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-slate-600 mb-1">价格</label>
                <input
                  v-model.number="item.price"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <label class="inline-flex items-center gap-2 pt-6 text-sm text-slate-700">
                <input
                  v-model="item.enabled"
                  type="checkbox"
                  class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  @change="handlePackageEnabledChange(dayType, item)"
                />
                启用套餐
              </label>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <button
                type="button"
                class="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-40"
                :disabled="index === 0"
                @click="moveUnlimitedPackage(dayType, index, -1)"
              >
                上移
              </button>
              <button
                type="button"
                class="px-2.5 py-1.5 rounded-lg border border-slate-300 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-40"
                :disabled="index === dayPackageRules[dayType].unlimitedPackages.length - 1"
                @click="moveUnlimitedPackage(dayType, index, 1)"
              >
                下移
              </button>
              <button
                type="button"
                class="px-2.5 py-1.5 rounded-lg border border-rose-200 text-xs text-rose-600 hover:bg-rose-50"
                @click="removeUnlimitedPackage(dayType, item.id)"
              >
                删除
              </button>
              <span class="text-xs text-slate-500">排序：{{ index + 1 }}</span>
            </div>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">{{ dayLabel(dayType) }}单人不限时限板</label>
          <input
            v-model.number="dayPackageRules[dayType].singleLimited"
            type="number"
            min="0"
            step="0.01"
            class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div class="management-surface p-6 space-y-4">
        <h2 class="text-lg font-semibold text-slate-800">素材费用</h2>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">大图加收</label>
          <input v-model.number="billingRules.largeImageExtra" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">超量小图加收</label>
          <input v-model.number="billingRules.excessSmallImage" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">超量大图加收</label>
          <input v-model.number="billingRules.excessLargeImage" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
      </div>

      <div class="management-surface p-6 space-y-4 lg:col-span-2">
        <h2 class="text-lg font-semibold text-slate-800">加班费用</h2>
        <div class="max-w-sm">
          <label class="block text-sm font-medium text-slate-700 mb-1">每分钟费用</label>
          <input v-model.number="billingRules.overtimeRatePerMinute" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
