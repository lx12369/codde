<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import {
  getEffectiveBillingDayType,
  getCalendarDayType,
  setManualBillingDayType,
  toggleBillingDayType
} from '@/utils/dayType'

const isLoading = ref(false)
const isWeatherRefreshing = ref(false)
const statsError = ref('')
const weatherError = ref('')
const lastUpdateTime = ref('')

const billingDayType = ref(getEffectiveBillingDayType())
const calendarDayType = ref(getCalendarDayType())

const stats = ref({
  total_customers: 0,
  today_transactions: 0,
  today_amount: 0,
  today_consumptions: 0,
  today_consumption_people: 0,
  today_consumption_amount: 0,
  total_transactions: 0,
  active_timers_count: 0
})

const weather = ref({
  city: '宁波市鄞州区下应街道',
  weather: '--',
  temperature: null,
  feels_like: null,
  temp_min: null,
  temp_max: null,
  humidity: null,
  wind_direction: '--',
  wind_speed: null,
  observed_at: '',
  provider: 'Amap Weather'
})

const WEATHER_CACHE_KEY = 'dashboard_weather_cache_v1'
const WEATHER_CACHE_DATE_KEY = 'dashboard_weather_cache_date_v1'
const KPI_HISTORY_MAX_KEY = 'dashboard_kpi_history_max_v1'

const kpiHistoryMax = ref({
  today_consumption_amount: 0,
  today_consumption_people: 0
})

const billingDayTypeLabel = computed(() => (billingDayType.value === 'weekend' ? '周末' : '工作日'))
const nextBillingDayTypeLabel = computed(() => (billingDayType.value === 'weekend' ? '工作日' : '周末'))
const billingDayTypeBadgeClass = computed(() => (
  billingDayType.value === 'weekend'
    ? 'bg-orange-100 text-orange-700'
    : 'bg-blue-100 text-blue-700'
))

const coreKpiCards = computed(() => ([
  {
    id: 'today_consumption_amount',
    title: '今日消费金额',
    value: formatAmount(stats.value.today_consumption_amount),
    hint: '核心运营指标',
    tag: '收入核心',
    dotClass: 'bg-emerald-500',
    orbClass: 'bg-emerald-100',
    barClass: 'from-emerald-500 to-cyan-500',
    barWidth: calcKpiBarWidth('today_consumption_amount', stats.value.today_consumption_amount)
  },
  {
    id: 'today_consumption_people',
    title: '今日消费人数',
    value: formatPeople(stats.value.today_consumption_people),
    hint: '按消费记录估算人次',
    tag: '客流热度',
    dotClass: 'bg-violet-500',
    orbClass: 'bg-violet-100',
    barClass: 'from-violet-500 to-fuchsia-500',
    barWidth: calcKpiBarWidth('today_consumption_people', stats.value.today_consumption_people)
  }
]))

const overviewCards = computed(() => ([
  {
    id: 'total_customers',
    title: '客户总数',
    value: formatCount(stats.value.total_customers),
    tag: '会员池',
    chipClass: 'bg-indigo-50 text-indigo-700',
    dotClass: 'bg-indigo-500',
    orbClass: 'bg-indigo-100'
  },
  {
    id: 'today_transactions',
    title: '今日充值笔数',
    value: formatCount(stats.value.today_transactions),
    tag: '充值频次',
    chipClass: 'bg-sky-50 text-sky-700',
    dotClass: 'bg-sky-500',
    orbClass: 'bg-sky-100'
  },
  {
    id: 'today_amount',
    title: '今日充值金额',
    value: formatAmount(stats.value.today_amount),
    tag: '现金流入',
    chipClass: 'bg-emerald-50 text-emerald-700',
    dotClass: 'bg-emerald-500',
    orbClass: 'bg-emerald-100'
  },
  {
    id: 'today_consumptions',
    title: '今日消费笔数',
    value: formatCount(stats.value.today_consumptions),
    tag: '消耗单量',
    chipClass: 'bg-amber-50 text-amber-700',
    dotClass: 'bg-amber-500',
    orbClass: 'bg-amber-100'
  },
  {
    id: 'total_transactions',
    title: '累计交易笔数',
    value: formatCount(stats.value.total_transactions),
    tag: '经营沉淀',
    chipClass: 'bg-slate-100 text-slate-700',
    dotClass: 'bg-slate-500',
    orbClass: 'bg-slate-200'
  },
  {
    id: 'active_timers_count',
    title: '活跃计时项目',
    value: formatCount(stats.value.active_timers_count),
    tag: '在场服务',
    chipClass: 'bg-rose-50 text-rose-700',
    dotClass: 'bg-rose-500',
    orbClass: 'bg-rose-100'
  }
]))

const amountInsight = computed(() => {
  const recharge = stats.value.today_amount
  const consume = stats.value.today_consumption_amount
  const total = recharge + consume

  if (total <= 0) {
    return {
      rechargePercent: 0,
      consumePercent: 0,
      netAmount: 0
    }
  }

  return {
    rechargePercent: Math.round((recharge / total) * 100),
    consumePercent: Math.round((consume / total) * 100),
    netAmount: recharge + consume
  }
})

const averageInsight = computed(() => {
  const consumeCount = stats.value.today_consumptions
  const consumePeople = stats.value.today_consumption_people
  const consumeAmount = stats.value.today_consumption_amount

  return {
    avgPerOrder: consumeCount > 0 ? consumeAmount / consumeCount : 0,
    avgPerPerson: consumePeople > 0 ? consumeAmount / consumePeople : 0
  }
})

const humidityPercent = computed(() => {
  const parsed = Number(weather.value.humidity)
  if (!Number.isFinite(parsed)) return 0
  return Math.min(100, Math.max(0, Math.round(parsed)))
})

const windSpeedPercent = computed(() => {
  const parsed = Number(weather.value.wind_speed)
  if (!Number.isFinite(parsed)) return 0
  return Math.min(100, Math.max(0, Math.round((parsed / 60) * 100)))
})

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatAmount(amount) {
  const normalized = toNumber(amount)
  return `¥${normalized.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`
}

function formatCount(count) {
  return toNumber(count).toLocaleString('zh-CN')
}

function formatPeople(count) {
  return `${formatCount(count)} 人`
}

function formatTemperature(value) {
  if (value === null || value === undefined || value === '') return '--'
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '--'
  return `${parsed.toFixed(1)}°C`
}

function formatHumidity(value) {
  if (value === null || value === undefined || value === '') return '--'
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return '--'
  return `${Math.round(parsed)}%`
}

function formatWind(direction, speed) {
  const normalizedDirection = String(direction || '--')
  const parsedSpeed = Number(speed)
  if (!Number.isFinite(parsedSpeed)) return normalizedDirection
  return `${normalizedDirection} ${Math.round(parsedSpeed)} km/h`
}

function formatDateTime(value) {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '--'
  return parsed.toLocaleString('zh-CN')
}

function resolveStatsPayload(response) {
  if (!response || typeof response !== 'object') return {}
  if (response.data && typeof response.data === 'object') return response.data
  return response
}

function resolveWeatherPayload(response) {
  if (!response || typeof response !== 'object') return {}
  if (response.data && typeof response.data === 'object') return response.data
  return response
}

function applyStatsPayload(payload) {
  stats.value = {
    total_customers: toNumber(payload.total_customers),
    today_transactions: toNumber(payload.today_transactions),
    today_amount: toNumber(payload.today_amount),
    today_consumptions: toNumber(payload.today_consumptions),
    today_consumption_people: toNumber(payload.today_consumption_people),
    today_consumption_amount: toNumber(payload.today_consumption_amount),
    total_transactions: toNumber(payload.total_transactions),
    active_timers_count: toNumber(payload.active_timers_count)
  }
}

function applyWeatherPayload(payload) {
  weather.value = {
    city: payload.city || '宁波市鄞州区下应街道',
    weather: payload.weather || '--',
    temperature: payload.temperature ?? null,
    feels_like: payload.feels_like ?? null,
    temp_min: payload.temp_min ?? null,
    temp_max: payload.temp_max ?? null,
    humidity: payload.humidity ?? null,
    wind_direction: payload.wind_direction || '--',
    wind_speed: payload.wind_speed ?? null,
    observed_at: payload.observed_at || '',
    provider: payload.provider || 'Amap Weather'
  }
}

function getTodayDateKey() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function readCachedWeather() {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem(WEATHER_CACHE_KEY)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

function writeCachedWeather(payload) {
  if (typeof window === 'undefined') return
  localStorage.setItem(WEATHER_CACHE_KEY, JSON.stringify(payload || {}))
  localStorage.setItem(WEATHER_CACHE_DATE_KEY, getTodayDateKey())
}

function readKpiHistoryMax() {
  if (typeof window === 'undefined') return
  const raw = localStorage.getItem(KPI_HISTORY_MAX_KEY)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return
    kpiHistoryMax.value = {
      today_consumption_amount: toNumber(parsed.today_consumption_amount),
      today_consumption_people: toNumber(parsed.today_consumption_people)
    }
  } catch {
    kpiHistoryMax.value = {
      today_consumption_amount: 0,
      today_consumption_people: 0
    }
  }
}

function writeKpiHistoryMax() {
  if (typeof window === 'undefined') return
  localStorage.setItem(KPI_HISTORY_MAX_KEY, JSON.stringify(kpiHistoryMax.value))
}

function syncKpiHistoryMax() {
  const nextAmountMax = Math.max(
    toNumber(kpiHistoryMax.value.today_consumption_amount),
    toNumber(stats.value.today_consumption_amount)
  )
  const nextPeopleMax = Math.max(
    toNumber(kpiHistoryMax.value.today_consumption_people),
    toNumber(stats.value.today_consumption_people)
  )

  kpiHistoryMax.value = {
    today_consumption_amount: nextAmountMax,
    today_consumption_people: nextPeopleMax
  }
  writeKpiHistoryMax()
}

function calcKpiBarWidth(key, currentValue) {
  const current = toNumber(currentValue)
  const max = toNumber(kpiHistoryMax.value[key])
  if (max <= 0 || current <= 0) return '0%'
  const percent = Math.round((current / max) * 100)
  const bounded = Math.max(8, Math.min(100, percent))
  return `${bounded}%`
}

function shouldRefreshWeatherToday() {
  if (typeof window === 'undefined') return true
  const lastDate = localStorage.getItem(WEATHER_CACHE_DATE_KEY) || ''
  return lastDate !== getTodayDateKey()
}

function syncBillingDayType() {
  calendarDayType.value = getCalendarDayType()
  billingDayType.value = getEffectiveBillingDayType()
}

function switchBillingDayType() {
  const nextType = toggleBillingDayType(billingDayType.value)
  setManualBillingDayType(nextType)
  syncBillingDayType()
}

function updateTime() {
  lastUpdateTime.value = new Date().toLocaleString('zh-CN')
}

async function fetchStats() {
  const response = await api.get('/dashboard/stats')
  return resolveStatsPayload(response)
}

async function fetchWeatherToday() {
  const response = await api.get('/dashboard/weather/today')
  return resolveWeatherPayload(response)
}

async function refreshWeather(force = false) {
  weatherError.value = ''

  const shouldFetch = force || shouldRefreshWeatherToday()
  if (!shouldFetch) {
    const cached = readCachedWeather()
    if (cached) {
      applyWeatherPayload(cached)
      return
    }
  }

  try {
    const weatherPayload = await fetchWeatherToday()
    applyWeatherPayload(weatherPayload)
    writeCachedWeather(weatherPayload)
  } catch (error) {
    console.error('Failed to fetch weather data:', error)
    if (!force) {
      const cached = readCachedWeather()
      if (cached) {
        applyWeatherPayload(cached)
        weatherError.value = '天气服务异常，已展示上次天气数据'
        return
      }
    }
    applyWeatherPayload({})
    weatherError.value = '天气数据暂不可用，请稍后重试'
  }
}

async function manualRefreshWeather() {
  isWeatherRefreshing.value = true
  await refreshWeather(true)
  isWeatherRefreshing.value = false
}

async function refreshData() {
  readKpiHistoryMax()
  syncBillingDayType()
  isLoading.value = true
  statsError.value = ''

  const statsResult = await Promise.allSettled([fetchStats()])

  if (statsResult[0].status === 'fulfilled') {
    applyStatsPayload(statsResult[0].value)
    syncKpiHistoryMax()
  } else {
    console.error('Failed to fetch dashboard stats:', statsResult[0].reason)
    applyStatsPayload({})
    statsError.value = '核心统计数据加载失败，已展示默认值'
  }

  await refreshWeather(false)

  updateTime()
  isLoading.value = false
}

onMounted(() => refreshData())
</script>

<template>
  <div class="space-y-6 p-4 sm:p-6">
    <section class="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-50 via-white to-slate-50 p-4 sm:p-6">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div class="space-y-2">
          <h1 class="text-2xl font-bold text-slate-900">运营概况</h1>
          <div class="flex items-center gap-2">
            <span class="text-sm text-slate-500">当前计费日类型</span>
            <span :class="['rounded-full px-2.5 py-1 text-xs font-semibold', billingDayTypeBadgeClass]">
              {{ billingDayTypeLabel }}
            </span>
          </div>
          <p class="text-xs text-slate-500">
            节假日可手动切换为周末计费
            <span v-if="billingDayType !== calendarDayType">
              （今日自然日类型：{{ calendarDayType === 'weekend' ? '周末' : '工作日' }}）
            </span>
          </p>
          <p v-if="lastUpdateTime" class="text-xs text-slate-500">最后更新：{{ lastUpdateTime }}</p>
        </div>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            @click="switchBillingDayType"
            class="min-h-11 rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors duration-200 hover:bg-slate-100"
          >
            切换为{{ nextBillingDayTypeLabel }}
          </button>
          <button
            @click="refreshData"
            :disabled="isLoading"
            :class="[
              'min-h-11 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200',
              isLoading
                ? 'cursor-not-allowed bg-slate-300 text-slate-500'
                : 'bg-[#1e40af] text-white hover:bg-[#1e3a8a]'
            ]"
          >
            {{ isLoading ? '刷新中...' : '刷新数据' }}
          </button>
        </div>
      </div>

      <p v-if="statsError" class="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {{ statsError }}
      </p>
    </section>

    <section class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <article
        v-for="card in coreKpiCards"
        :key="card.id"
        class="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-shadow duration-200 hover:shadow-md"
      >
        <span :class="['absolute -right-5 -top-5 h-16 w-16 rounded-full', card.orbClass]"></span>
        <span :class="['absolute right-3 top-3 h-2 w-2 rounded-full', card.dotClass]"></span>
        <p class="text-sm text-slate-500">{{ card.title }}</p>
        <p class="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{{ card.value }}</p>
        <div class="mt-2 flex items-center gap-2">
          <p class="text-xs text-slate-500">{{ card.hint }}</p>
          <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">{{ card.tag }}</span>
        </div>
        <div class="mt-3 h-1.5 rounded-full bg-slate-100">
          <div
            :class="['h-1.5 rounded-full bg-gradient-to-r transition-all duration-500', card.barClass]"
            :style="{ width: card.barWidth }"
          ></div>
        </div>
      </article>
    </section>

    <section class="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 class="text-lg font-semibold text-slate-900">当天天气</h2>
        <div class="flex items-center gap-2">
          <p class="text-xs text-slate-500">
            数据来源：{{ weather.provider }} · 观测时间：{{ formatDateTime(weather.observed_at) }}
          </p>
          <button
            @click="manualRefreshWeather"
            :disabled="isWeatherRefreshing"
            :class="[
              'rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors duration-200',
              isWeatherRefreshing
                ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
                : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
            ]"
          >
            {{ isWeatherRefreshing ? '刷新中...' : '刷新' }}
          </button>
        </div>
      </div>

      <p v-if="weatherError" class="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
        {{ weatherError }}
      </p>

      <div v-else class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <article class="relative overflow-hidden rounded-xl border border-sky-200 bg-gradient-to-br from-sky-50 to-cyan-50 p-4 shadow-sm">
          <span class="absolute -right-3 -top-3 h-10 w-10 rounded-full bg-sky-200/60"></span>
          <span class="absolute bottom-2 right-3 text-2xl text-sky-200/80">◌</span>
          <p class="inline-flex items-center gap-1 rounded-full bg-white/70 px-2 py-0.5 text-xs text-slate-600">
            <span class="h-1.5 w-1.5 rounded-full bg-sky-500"></span>天气
          </p>
          <p class="mt-2 text-xl font-semibold text-slate-900">{{ weather.weather }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ weather.city }}</p>
          <div class="mt-2 flex items-center gap-2 text-[11px] text-sky-700">
            <span class="rounded-full bg-white/80 px-2 py-0.5">实时</span>
            <span class="rounded-full bg-white/80 px-2 py-0.5">本地</span>
          </div>
        </article>
        <article class="relative overflow-hidden rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50 p-4 shadow-sm">
          <span class="absolute -right-3 -top-3 h-10 w-10 rounded-full bg-blue-200/60"></span>
          <span class="absolute bottom-2 right-3 text-2xl text-blue-200/80">◌</span>
          <p class="inline-flex items-center gap-1 rounded-full bg-white/70 px-2 py-0.5 text-xs text-slate-600">
            <span class="h-1.5 w-1.5 rounded-full bg-blue-500"></span>当前 / 体感
          </p>
          <p class="mt-2 text-xl font-semibold text-slate-900">
            {{ formatTemperature(weather.temperature) }} / {{ formatTemperature(weather.feels_like) }}
          </p>
          <p class="mt-1 text-xs text-slate-500">单位：摄氏度</p>
          <div class="mt-2">
            <div class="h-1.5 rounded-full bg-white/70">
              <div class="h-1.5 w-2/3 rounded-full bg-gradient-to-r from-sky-400 via-blue-500 to-indigo-500"></div>
            </div>
            <p class="mt-1 text-[11px] text-blue-700">体感与当前温度趋势参考</p>
          </div>
        </article>
        <article class="relative overflow-hidden rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 p-4 shadow-sm">
          <span class="absolute -right-3 -top-3 h-10 w-10 rounded-full bg-amber-200/60"></span>
          <span class="absolute bottom-2 right-3 text-2xl text-amber-200/80">◌</span>
          <p class="inline-flex items-center gap-1 rounded-full bg-white/70 px-2 py-0.5 text-xs text-slate-600">
            <span class="h-1.5 w-1.5 rounded-full bg-amber-500"></span>今日高低温
          </p>
          <p class="mt-2 text-xl font-semibold text-slate-900">
            {{ formatTemperature(weather.temp_max) }} / {{ formatTemperature(weather.temp_min) }}
          </p>
          <p class="mt-1 text-xs text-slate-500">最高 / 最低</p>
          <div class="mt-2 flex items-center gap-2 text-[11px] text-amber-700">
            <span class="rounded-full bg-white/80 px-2 py-0.5">↑ 日间峰值</span>
            <span class="rounded-full bg-white/80 px-2 py-0.5">↓ 夜间低谷</span>
          </div>
        </article>
        <article class="relative overflow-hidden rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-teal-50 p-4 shadow-sm">
          <span class="absolute -right-3 -top-3 h-10 w-10 rounded-full bg-emerald-200/60"></span>
          <span class="absolute bottom-2 right-3 text-2xl text-emerald-200/80">◌</span>
          <p class="inline-flex items-center gap-1 rounded-full bg-white/70 px-2 py-0.5 text-xs text-slate-600">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>湿度 / 风况
          </p>
          <p class="mt-2 text-xl font-semibold text-slate-900">{{ formatHumidity(weather.humidity) }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ formatWind(weather.wind_direction, weather.wind_speed) }}</p>
          <div class="mt-2 space-y-1">
            <div>
              <div class="flex items-center justify-between text-[11px] text-emerald-700">
                <span>湿度</span>
                <span>{{ humidityPercent }}%</span>
              </div>
              <div class="mt-0.5 h-1.5 rounded-full bg-white/80">
                <div class="h-1.5 rounded-full bg-emerald-500 transition-all duration-300" :style="{ width: `${humidityPercent}%` }"></div>
              </div>
            </div>
            <div>
              <div class="flex items-center justify-between text-[11px] text-teal-700">
                <span>风速强度</span>
                <span>{{ windSpeedPercent }}%</span>
              </div>
              <div class="mt-0.5 h-1.5 rounded-full bg-white/80">
                <div class="h-1.5 rounded-full bg-teal-500 transition-all duration-300" :style="{ width: `${windSpeedPercent}%` }"></div>
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-semibold text-slate-900">运营总览</h2>
        <span class="text-xs text-slate-500">来自当日与累计统计</span>
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="card in overviewCards"
          :key="card.id"
          class="relative overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4"
        >
          <span :class="['absolute -right-3 -top-3 h-10 w-10 rounded-full', card.orbClass]"></span>
          <p class="text-xs text-slate-500">{{ card.title }}</p>
          <p class="mt-2 text-2xl font-semibold text-slate-900">{{ card.value }}</p>
          <div :class="['mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]', card.chipClass]">
            <span :class="['h-1.5 w-1.5 rounded-full', card.dotClass]"></span>{{ card.tag }}
          </div>
        </article>
      </div>
    </section>

    <section class="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <h2 class="text-lg font-semibold text-slate-900">结构洞察</h2>
      <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <article class="relative overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4">
          <span class="absolute -right-4 -top-4 h-12 w-12 rounded-full bg-emerald-100/70"></span>
          <p class="text-sm font-medium text-slate-700">今日金额结构</p>
          <div class="mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>结构占比
          </div>
          <div class="mt-3 space-y-3">
            <div>
              <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
                <span>充值金额占比</span>
                <span>{{ amountInsight.rechargePercent }}%</span>
              </div>
              <div class="h-2 rounded-full bg-slate-200">
                <div
                  class="h-2 rounded-full bg-emerald-500 transition-all duration-300"
                  :style="{ width: `${amountInsight.rechargePercent}%` }"
                ></div>
              </div>
            </div>
            <div>
              <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
                <span>消费金额占比</span>
                <span>{{ amountInsight.consumePercent }}%</span>
              </div>
              <div class="h-2 rounded-full bg-slate-200">
                <div
                  class="h-2 rounded-full bg-orange-500 transition-all duration-300"
                  :style="{ width: `${amountInsight.consumePercent}%` }"
                ></div>
              </div>
            </div>
          </div>
          <p class="mt-3 text-sm text-slate-600">
            今日总收入：<span class="font-semibold text-slate-900">{{ formatAmount(amountInsight.netAmount) }}</span>
          </p>
        </article>

        <article class="relative overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4">
          <span class="absolute -right-4 -top-4 h-12 w-12 rounded-full bg-orange-100/70"></span>
          <p class="text-sm font-medium text-slate-700">消费效率指标</p>
          <div class="mt-2 inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-[11px] text-orange-700">
            <span class="h-1.5 w-1.5 rounded-full bg-orange-500"></span>效率观察
          </div>
          <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div class="rounded-lg border border-slate-100 bg-white p-3 shadow-sm">
              <p class="text-xs text-slate-500">单笔消费均额</p>
              <p class="mt-2 text-xl font-semibold text-slate-900">{{ formatAmount(averageInsight.avgPerOrder) }}</p>
            </div>
            <div class="rounded-lg border border-slate-100 bg-white p-3 shadow-sm">
              <p class="text-xs text-slate-500">按人次均额</p>
              <p class="mt-2 text-xl font-semibold text-slate-900">{{ formatAmount(averageInsight.avgPerPerson) }}</p>
            </div>
          </div>
          <p class="mt-3 text-sm text-slate-600">
            今日消费笔数 {{ formatCount(stats.today_consumptions) }}，估算消费人次 {{ formatCount(stats.today_consumption_people) }}。
          </p>
        </article>
      </div>
    </section>

  </div>
</template>
