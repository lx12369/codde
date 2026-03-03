<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '@/api'

const loading = ref(false)
const saving = ref(false)
const showSuccess = ref(false)

const billingRules = reactive({
  singlePersonOneHour: 0,
  singlePersonTwoHours: 0,
  overtimeBillingRule: '',
  weekdaySingleUnlimited: 0,
  weekdayDoubleUnlimited: 0,
  weekdaySingleLimitedBoard: 0,
  weekendSingleUnlimited: 0,
  weekendDoubleUnlimited: 0,
  weekendSingleLimitedBoard: 0,
  largeImageExtra: 0,
  excessSmallImage: 0,
  excessLargeImage: 0
})

const overtimeConfig = reactive({
  overtimeFreeMinutes: 10,
  overtime10to30Fee: 10,
  overtime30Fee: 18.9
})

function toNumber(value, fallback = 0) {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

function assignFormNumber(key, value) {
  if (value === undefined || value === null || value === '') return
  billingRules[key] = toNumber(value, billingRules[key])
}

function isGroupedRulesPayload(data) {
  return Boolean(data && typeof data === 'object' && (data.limited || data.weekday || data.weekend || data.materials))
}

function updateOvertimeRuleText() {
  billingRules.overtimeBillingRule = `0-${overtimeConfig.overtimeFreeMinutes}分钟免费，${overtimeConfig.overtimeFreeMinutes}-30分钟加收${overtimeConfig.overtime10to30Fee}，30分钟以上每小时加收${overtimeConfig.overtime30Fee}`
}

function trySyncOvertimeConfigFromText() {
  const text = String(billingRules.overtimeBillingRule || '')
  const matches = text.match(/\d+(?:\.\d+)?/g)
  if (!matches || matches.length < 3) return

  const freeMinutes = Math.floor(toNumber(matches[0], overtimeConfig.overtimeFreeMinutes))
  const fee10to30 = toNumber(matches[1], overtimeConfig.overtime10to30Fee)
  const fee30Plus = toNumber(matches[2], overtimeConfig.overtime30Fee)

  overtimeConfig.overtimeFreeMinutes = Math.max(0, freeMinutes)
  overtimeConfig.overtime10to30Fee = Math.max(0, fee10to30)
  overtimeConfig.overtime30Fee = Math.max(0, fee30Plus)
}

function applyGroupedRules(data = {}) {
  const limited = data.limited || {}
  const weekday = data.weekday || {}
  const weekend = data.weekend || {}
  const materials = data.materials || {}

  assignFormNumber('singlePersonOneHour', limited.price1h)
  assignFormNumber('singlePersonTwoHours', limited.price2h)

  overtimeConfig.overtimeFreeMinutes = Math.max(0, Math.floor(toNumber(limited.overtimeFreeMinutes, overtimeConfig.overtimeFreeMinutes)))
  overtimeConfig.overtime10to30Fee = Math.max(0, toNumber(limited.overtime10to30Fee, overtimeConfig.overtime10to30Fee))
  overtimeConfig.overtime30Fee = Math.max(0, toNumber(limited.overtime30Fee, overtimeConfig.overtime30Fee))
  updateOvertimeRuleText()

  assignFormNumber('weekdaySingleUnlimited', weekday.singleUnlimited)
  assignFormNumber('weekdayDoubleUnlimited', weekday.doubleUnlimited)
  assignFormNumber('weekdaySingleLimitedBoard', weekday.singleLimited)

  assignFormNumber('weekendSingleUnlimited', weekend.singleUnlimited)
  assignFormNumber('weekendDoubleUnlimited', weekend.doubleUnlimited)
  assignFormNumber('weekendSingleLimitedBoard', weekend.singleLimited)

  assignFormNumber('largeImageExtra', materials.largeImageFee)
  assignFormNumber('excessSmallImage', materials.extraSmallImageFee)
  assignFormNumber('excessLargeImage', materials.extraLargeImageFee)
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
    'excessLargeImage'
  ]

  mappingKeys.forEach((key) => assignFormNumber(key, data[key]))

  if (data.overtimeBillingRule !== undefined && data.overtimeBillingRule !== null) {
    billingRules.overtimeBillingRule = String(data.overtimeBillingRule)
    trySyncOvertimeConfigFromText()
  }
}

const fetchBillingRules = async () => {
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
  } finally {
    loading.value = false
  }
}

const saveBillingRules = async () => {
  saving.value = true
  try {
    trySyncOvertimeConfigFromText()

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
      }
    }

    await api.put('/billing-rules', payload)
    await fetchBillingRules()

    showSuccess.value = true
    setTimeout(() => {
      showSuccess.value = false
    }, 3000)
  } catch (error) {
    console.error('保存计费规则失败:', error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchBillingRules()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">计费规则</h1>
        <p class="text-gray-500 mt-1">配置套餐与素材收费规则</p>
      </div>
      <button
        @click="saveBillingRules"
        :disabled="saving"
        class="inline-flex items-center px-4 py-2 bg-[#1e40af] text-white rounded-lg hover:bg-[#1e3a8a] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg v-if="saving" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        保存规则
      </button>
    </div>

    <div v-if="showSuccess" class="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center">
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-500 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" />
      </svg>
      <span class="text-green-700">保存成功</span>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <svg class="animate-spin h-8 w-8 text-[#1e40af]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
      </svg>
    </div>

    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <h2 class="text-lg font-semibold text-gray-800">限时套餐</h2>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">1小时价格</label>
          <input v-model.number="billingRules.singlePersonOneHour" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">2小时价格</label>
          <input v-model.number="billingRules.singlePersonTwoHours" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">超时规则说明</label>
          <textarea v-model="billingRules.overtimeBillingRule" rows="3" class="w-full px-3 py-2 border border-gray-300 rounded-lg"></textarea>
        </div>
      </div>

      <div class="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <h2 class="text-lg font-semibold text-gray-800">工作日方案</h2>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">单人不限时不限板</label>
          <input v-model.number="billingRules.weekdaySingleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">双人不限时不限板</label>
          <input v-model.number="billingRules.weekdayDoubleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">单人不限时限板</label>
          <input v-model.number="billingRules.weekdaySingleLimitedBoard" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
      </div>

      <div class="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <h2 class="text-lg font-semibold text-gray-800">周末方案</h2>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">单人不限时不限板</label>
          <input v-model.number="billingRules.weekendSingleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">双人不限时不限板</label>
          <input v-model.number="billingRules.weekendDoubleUnlimited" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">单人不限时限板</label>
          <input v-model.number="billingRules.weekendSingleLimitedBoard" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
      </div>

      <div class="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <h2 class="text-lg font-semibold text-gray-800">素材费用</h2>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">大图加收</label>
          <input v-model.number="billingRules.largeImageExtra" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">超量小图加收</label>
          <input v-model.number="billingRules.excessSmallImage" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">超量大图加收</label>
          <input v-model.number="billingRules.excessLargeImage" type="number" min="0" step="0.01" class="w-full px-3 py-2 border border-gray-300 rounded-lg" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>

