<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import api from '@/api'

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
  weekdaySingleUnlimited: 53.9,
  weekdayDoubleUnlimited: 103.9,
  weekdaySingleLimitedBoard: 35.9,
  weekendSingleUnlimited: 63.9,
  weekendDoubleUnlimited: 123.9,
  weekendSingleLimitedBoard: 42.8,
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

function assignFormNumber(key, value) {
  if (value === undefined || value === null || value === '') return
  billingRules[key] = Math.max(0, toNumber(value, billingRules[key]))
}

function isGroupedRulesPayload(data) {
  return Boolean(data && typeof data === 'object' && (data.limited || data.weekday || data.weekend || data.materials || data.overtime))
}

const overtimeRuleSummary = computed(() => {
  const freeMinutes = Math.max(0, Math.floor(toNumber(overtimeConfig.overtimeFreeMinutes, 10)))
  const fee10to30 = Math.max(0, toNumber(overtimeConfig.overtime10to30Fee, 10))
  const fee30Plus = Math.max(0, toNumber(overtimeConfig.overtime30Fee, toNumber(billingRules.singlePersonOneHour, 18.9)))

  return `0-${freeMinutes}分钟免费，${freeMinutes}-30分钟加收${fee10to30}，30分钟以上每小时加收${fee30Plus}`
})

function trySyncOvertimeConfigFromLegacyText(text) {
  if (text === undefined || text === null) return
  const normalizedText = String(text)

  const freeMatch = normalizedText.match(/0\s*-\s*(\d+(?:\.\d+)?)\s*分钟/)
  const fee10to30Match = normalizedText.match(/(?:10\s*-\s*30\s*分钟|30\s*分钟内)[^\d]*(\d+(?:\.\d+)?)/)
  const fee30PlusMatch = normalizedText.match(/30\s*分钟(?:以上|后)[^\d]*(\d+(?:\.\d+)?)/)

  if (freeMatch?.[1] !== undefined) {
    overtimeConfig.overtimeFreeMinutes = Math.max(0, Math.floor(toNumber(freeMatch[1], overtimeConfig.overtimeFreeMinutes)))
  }
  if (fee10to30Match?.[1] !== undefined) {
    overtimeConfig.overtime10to30Fee = Math.max(0, toNumber(fee10to30Match[1], overtimeConfig.overtime10to30Fee))
  }
  if (fee30PlusMatch?.[1] !== undefined) {
    overtimeConfig.overtime30Fee = Math.max(0, toNumber(fee30PlusMatch[1], overtimeConfig.overtime30Fee))
  }
}

function applyGroupedRules(data = {}) {
  const limited = data.limited || {}
  const weekday = data.weekday || {}
  const weekend = data.weekend || {}
  const materials = data.materials || {}
  const overtime = data.overtime || {}

  assignFormNumber('singlePersonOneHour', limited.price1h)
  assignFormNumber('singlePersonTwoHours', limited.price2h)

  overtimeConfig.overtimeFreeMinutes = Math.max(0, Math.floor(toNumber(limited.overtimeFreeMinutes, overtimeConfig.overtimeFreeMinutes)))
  overtimeConfig.overtime10to30Fee = Math.max(0, toNumber(limited.overtime10to30Fee, overtimeConfig.overtime10to30Fee))
  overtimeConfig.overtime30Fee = Math.max(0, toNumber(limited.overtime30Fee, overtimeConfig.overtime30Fee))

  assignFormNumber('weekdaySingleUnlimited', weekday.singleUnlimited)
  assignFormNumber('weekdayDoubleUnlimited', weekday.doubleUnlimited)
  assignFormNumber('weekdaySingleLimitedBoard', weekday.singleLimited)

  assignFormNumber('weekendSingleUnlimited', weekend.singleUnlimited)
  assignFormNumber('weekendDoubleUnlimited', weekend.doubleUnlimited)
  assignFormNumber('weekendSingleLimitedBoard', weekend.singleLimited)

  assignFormNumber('largeImageExtra', materials.largeImageFee)
  assignFormNumber('excessSmallImage', materials.extraSmallImageFee)
  assignFormNumber('excessLargeImage', materials.extraLargeImageFee)
  assignFormNumber('overtimeRatePerMinute', overtime.ratePerMinute)
}

function applyLegacyFlatRules(data = {}) {
  const mappingKeys = [
    'singlePersonOneHour',
    'singlePersonTwoHours',
    'weekdaySingleUnlimited',
    'weekdayDoubleUnlimited',
    'weekdaySingleLimitedBoard',
    'weekendSingleUnlimited',
    'weekendDoubleUnlimited',
    'weekendSingleLimitedBoard',
    'largeImageExtra',
    'excessSmallImage',
    'excessLargeImage',
    'overtimeRatePerMinute'
  ]

  mappingKeys.forEach((key) => assignFormNumber(key, data[key]))

  if (data.overtimeFreeMinutes !== undefined) {
    overtimeConfig.overtimeFreeMinutes = Math.max(0, Math.floor(toNumber(data.overtimeFreeMinutes, overtimeConfig.overtimeFreeMinutes)))
  }
  if (data.overtime10to30Fee !== undefined) {
    overtimeConfig.overtime10to30Fee = Math.max(0, toNumber(data.overtime10to30Fee, overtimeConfig.overtime10to30Fee))
  }
  if (data.overtime30Fee !== undefined) {
    overtimeConfig.overtime30Fee = Math.max(0, toNumber(data.overtime30Fee, overtimeConfig.overtime30Fee))
  }
  if (data.overtimeBillingRule !== undefined && data.overtimeBillingRule !== null) {
    trySyncOvertimeConfigFromLegacyText(data.overtimeBillingRule)
  }
}

async function fetchBillingRules() {
  loading.value = true
  try {
    const response = await api.get('/billing-rules')
    const data = response?.data || response || {}

    if (isGroupedRulesPayload(data)) {
      applyGroupedRules(data)
    } else {
      applyLegacyFlatRules(data)
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
    const payload = {
      limited: {
        price1h: toNumber(billingRules.singlePersonOneHour),
        price2h: toNumber(billingRules.singlePersonTwoHours),
        overtimeFreeMinutes: Math.max(0, Math.floor(toNumber(overtimeConfig.overtimeFreeMinutes, 10))),
        overtime10to30Fee: Math.max(0, toNumber(overtimeConfig.overtime10to30Fee, 10)),
        overtime30Fee: Math.max(0, toNumber(overtimeConfig.overtime30Fee, toNumber(billingRules.singlePersonOneHour, 0)))
      },
      weekday: {
        singleUnlimited: toNumber(billingRules.weekdaySingleUnlimited),
        doubleUnlimited: toNumber(billingRules.weekdayDoubleUnlimited),
        singleLimited: toNumber(billingRules.weekdaySingleLimitedBoard)
      },
      weekend: {
        singleUnlimited: toNumber(billingRules.weekendSingleUnlimited),
        doubleUnlimited: toNumber(billingRules.weekendDoubleUnlimited),
        singleLimited: toNumber(billingRules.weekendSingleLimitedBoard)
      },
      materials: {
        largeImageFee: toNumber(billingRules.largeImageExtra),
        extraSmallImageFee: toNumber(billingRules.excessSmallImage),
        extraLargeImageFee: toNumber(billingRules.excessLargeImage)
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
          @click="saveBillingRules"
          :disabled="saving"
          class="page-hero__action"
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

      <div class="management-surface p-6 space-y-4">
        <h2 class="text-lg font-semibold text-slate-800">工作日方案</h2>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">单人不限时不限板</label>
          <input v-model.number="billingRules.weekdaySingleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">双人不限时不限板</label>
          <input v-model.number="billingRules.weekdayDoubleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">单人不限时限板</label>
          <input v-model.number="billingRules.weekdaySingleLimitedBoard" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
      </div>

      <div class="management-surface p-6 space-y-4">
        <h2 class="text-lg font-semibold text-slate-800">周末方案</h2>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">单人不限时不限板</label>
          <input v-model.number="billingRules.weekendSingleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">双人不限时不限板</label>
          <input v-model.number="billingRules.weekendDoubleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">单人不限时限板</label>
          <input v-model.number="billingRules.weekendSingleLimitedBoard" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500" />
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


