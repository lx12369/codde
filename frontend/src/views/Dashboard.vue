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
  today_bead_loss_amount: 0,
  today_net_income: 0,
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
  today_net_income: 0,
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
    id: 'today_net_income',
    title: '今日总收益',
    value: formatAmount(stats.value.today_net_income),
    hint: `豆仓损耗 ${formatAmount(stats.value.today_bead_loss_amount)}`,
    tag: '净收益',
    dotClass: 'bg-emerald-500',
    orbClass: 'bg-emerald-100',
    barClass: 'from-emerald-500 to-cyan-500',
    barWidth: calcKpiBarWidth('today_net_income', stats.value.today_net_income)
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
    id: 'today_consumption_amount',
    title: '今日消费金额',
    value: formatAmount(stats.value.today_consumption_amount),
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

function includesAnyKeyword(text, keywords) {
  return keywords.some(keyword => text.includes(keyword))
}

const weatherScene = computed(() => {
  const text = String(weather.value.weather || '').trim().toLowerCase()
  if (!text || text === '--') return 'default'

  if (includesAnyKeyword(text, ['雷阵雨', '雷雨', '暴雨', 'storm', 'thunder'])) return 'storm'
  if (includesAnyKeyword(text, ['雨', 'rain', 'drizzle', 'shower'])) return 'rain'
  if (includesAnyKeyword(text, ['雪', 'snow', 'sleet'])) return 'snow'
  if (includesAnyKeyword(text, ['雾', '霾', 'fog', 'haze', 'mist'])) return 'mist'
  if (includesAnyKeyword(text, ['阴', '多云', 'cloud', 'overcast'])) return 'cloud'
  if (includesAnyKeyword(text, ['晴', 'sunny', 'clear'])) return 'sunny'

  return 'default'
})

const weatherCardToneClass = computed(() => `weather-card--${weatherScene.value}`)
const hasCloudLayer = computed(() => ['cloud', 'mist', 'rain', 'storm', 'snow'].includes(weatherScene.value))
const isRainScene = computed(() => ['rain', 'storm'].includes(weatherScene.value))

const weatherSceneTag = computed(() => {
  const labels = {
    sunny: '晴朗模式',
    cloud: '多云模式',
    rain: '降雨模式',
    storm: '雷雨模式',
    snow: '降雪模式',
    mist: '雾霾模式',
    default: '常规模式'
  }
  return labels[weatherScene.value] || labels.default
})

const weatherSceneHint = computed(() => {
  const hints = {
    sunny: '光照良好，建议关注店内温控与补水提示。',
    cloud: '云量较多，客流节奏可能更平稳。',
    rain: '雨天已开启降雨动画，可提前准备防滑与雨具收纳。',
    storm: '雷雨天气波动较大，建议加强入店动线引导。',
    snow: '低温天气注意门店地面干燥与保暖提醒。',
    mist: '能见度偏低，建议加强到店指引信息。',
    default: '天气状态稳定，按常规运营节奏执行。'
  }
  return hints[weatherScene.value] || hints.default
})

const rainDrops = Object.freeze(
  Array.from({ length: 22 }, (_, index) => ({
    id: index,
    left: (index * 37) % 100,
    delay: Number((((index * 17) % 24) * 0.08).toFixed(2)),
    duration: Number((1.1 + ((index * 13) % 8) * 0.18).toFixed(2)),
    opacity: Number((0.35 + ((index * 11) % 4) * 0.13).toFixed(2))
  }))
)

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
    today_bead_loss_amount: toNumber(payload.today_bead_loss_amount),
    today_net_income: toNumber(payload.today_net_income),
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
      today_net_income: toNumber(parsed.today_net_income ?? parsed.today_consumption_amount),
      today_consumption_people: toNumber(parsed.today_consumption_people)
    }
  } catch {
    kpiHistoryMax.value = {
      today_net_income: 0,
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
    toNumber(kpiHistoryMax.value.today_net_income),
    toNumber(stats.value.today_net_income)
  )
  const nextPeopleMax = Math.max(
    toNumber(kpiHistoryMax.value.today_consumption_people),
    toNumber(stats.value.today_consumption_people)
  )

  kpiHistoryMax.value = {
    today_net_income: nextAmountMax,
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
        <article :class="['weather-card weather-card--hero relative overflow-hidden rounded-xl border p-4 shadow-sm', weatherCardToneClass]">
          <div class="weather-card__atmosphere" aria-hidden="true">
            <span class="weather-card__glow"></span>
            <div v-if="hasCloudLayer" class="weather-card__clouds">
              <span class="weather-card__cloud weather-card__cloud--a"></span>
              <span class="weather-card__cloud weather-card__cloud--b"></span>
            </div>
            <span v-if="weatherScene === 'sunny'" class="weather-card__sun"></span>
            <div v-if="isRainScene" class="weather-card__rain">
              <span
                v-for="drop in rainDrops"
                :key="drop.id"
                class="weather-card__rain-drop"
                :style="{
                  left: `${drop.left}%`,
                  '--rain-delay': `${drop.delay}s`,
                  '--rain-duration': `${drop.duration}s`,
                  '--rain-opacity': String(drop.opacity)
                }"
              ></span>
            </div>
          </div>
          <p class="weather-card__badge inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs">
            <span class="h-1.5 w-1.5 rounded-full bg-current"></span>天气
          </p>
          <p class="weather-card__headline mt-2 text-xl font-semibold">{{ weather.weather }}</p>
          <p class="weather-card__meta mt-1 text-xs">{{ weather.city }}</p>
          <div class="mt-2 flex items-center gap-2 text-[11px]">
            <span class="weather-card__pill rounded-full px-2 py-0.5">实时</span>
            <span class="weather-card__pill rounded-full px-2 py-0.5">{{ weatherSceneTag }}</span>
          </div>
          <p class="weather-card__hint mt-2 text-[11px] leading-5">{{ weatherSceneHint }}</p>
        </article>
        <article :class="['weather-card weather-card--metric relative overflow-hidden rounded-xl border p-4 shadow-sm', weatherCardToneClass]">
          <div class="weather-card__atmosphere weather-card__atmosphere--soft" aria-hidden="true">
            <span class="weather-card__glow weather-card__glow--soft"></span>
            <div class="weather-card__thermo">
              <span class="weather-card__thermo-track"></span>
              <span class="weather-card__thermo-mercury"></span>
              <span class="weather-card__thermo-bulb"></span>
              <span class="weather-card__thermo-dot weather-card__thermo-dot--a"></span>
              <span class="weather-card__thermo-dot weather-card__thermo-dot--b"></span>
            </div>
          </div>
          <p class="weather-card__badge inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs">
            <span class="h-1.5 w-1.5 rounded-full bg-current"></span>当前 / 体感
          </p>
          <p class="weather-card__headline mt-2 text-xl font-semibold">
            {{ formatTemperature(weather.temperature) }} / {{ formatTemperature(weather.feels_like) }}
          </p>
          <p class="weather-card__meta mt-1 text-xs">单位：摄氏度</p>
          <p class="weather-card__hint mt-3 text-[11px]">体感与当前温度趋势参考</p>
        </article>
        <article :class="['weather-card weather-card--metric relative overflow-hidden rounded-xl border p-4 shadow-sm', weatherCardToneClass]">
          <div class="weather-card__atmosphere weather-card__atmosphere--soft" aria-hidden="true">
            <span class="weather-card__glow weather-card__glow--soft"></span>
            <div class="weather-card__range-scan">
              <span class="weather-card__range-axis"></span>
              <span class="weather-card__range-orb weather-card__range-orb--high"></span>
              <span class="weather-card__range-orb weather-card__range-orb--low"></span>
            </div>
          </div>
          <p class="weather-card__badge inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs">
            <span class="h-1.5 w-1.5 rounded-full bg-current"></span>今日高低温
          </p>
          <p class="weather-card__headline mt-2 text-xl font-semibold">
            {{ formatTemperature(weather.temp_max) }} / {{ formatTemperature(weather.temp_min) }}
          </p>
          <p class="weather-card__meta mt-1 text-xs">最高 / 最低</p>
        </article>
        <article :class="['weather-card weather-card--metric relative overflow-hidden rounded-xl border p-4 shadow-sm', weatherCardToneClass]">
          <div class="weather-card__atmosphere weather-card__atmosphere--soft" aria-hidden="true">
            <span class="weather-card__glow weather-card__glow--soft"></span>
            <div class="weather-card__climate-flow">
              <span class="weather-card__humidity-ripple weather-card__humidity-ripple--a"></span>
              <span class="weather-card__humidity-ripple weather-card__humidity-ripple--b"></span>
              <span class="weather-card__wind-line weather-card__wind-line--1"></span>
              <span class="weather-card__wind-line weather-card__wind-line--2"></span>
              <span class="weather-card__wind-line weather-card__wind-line--3"></span>
            </div>
          </div>
          <p class="weather-card__badge inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs">
            <span class="h-1.5 w-1.5 rounded-full bg-current"></span>湿度 / 风况
          </p>
          <p class="weather-card__headline mt-2 text-xl font-semibold">{{ formatHumidity(weather.humidity) }}</p>
          <p class="weather-card__meta mt-1 text-xs">{{ formatWind(weather.wind_direction, weather.wind_speed) }}</p>
          <div class="mt-2 space-y-1">
            <div>
              <div class="weather-card__hint flex items-center justify-between text-[11px]">
                <span>湿度</span>
                <span>{{ humidityPercent }}%</span>
              </div>
              <div class="weather-card__meter-track mt-0.5 h-1.5 rounded-full">
                <div class="weather-card__meter-fill h-1.5 rounded-full transition-all duration-500" :style="{ width: `${humidityPercent}%` }"></div>
              </div>
            </div>
            <div>
              <div class="weather-card__hint flex items-center justify-between text-[11px]">
                <span>风速强度</span>
                <span>{{ windSpeedPercent }}%</span>
              </div>
              <div class="weather-card__meter-track mt-0.5 h-1.5 rounded-full">
                <div class="weather-card__meter-fill h-1.5 rounded-full transition-all duration-500" :style="{ width: `${windSpeedPercent}%` }"></div>
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

<style scoped>
.weather-card--hero {
  isolation: isolate;
  min-height: 176px;
}

.weather-card--metric {
  isolation: isolate;
  min-height: 176px;
}

.weather-card__atmosphere {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.weather-card__glow {
  position: absolute;
  width: 180px;
  height: 180px;
  right: -40px;
  top: -56px;
  border-radius: 999px;
  filter: blur(2px);
  opacity: 0.62;
}

.weather-card__atmosphere--soft {
  opacity: 0.72;
}

.weather-card__glow--soft {
  width: 154px;
  height: 154px;
  right: -28px;
  top: -44px;
  opacity: 0.52;
}

.weather-card__badge,
.weather-card__headline,
.weather-card__meta,
.weather-card__hint,
.weather-card__pill {
  position: relative;
  z-index: 1;
}

.weather-card__clouds {
  position: absolute;
  inset: 0;
}

.weather-card__cloud {
  position: absolute;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.26), rgba(255, 255, 255, 0.1));
  filter: blur(0.2px);
  animation: weather-cloud-drift 9s ease-in-out infinite alternate;
}

.weather-card__cloud::before,
.weather-card__cloud::after {
  content: '';
  position: absolute;
  border-radius: 999px;
  background: inherit;
}

.weather-card__cloud--a {
  width: 88px;
  height: 26px;
  left: 10%;
  top: 24%;
}

.weather-card__cloud--a::before {
  width: 24px;
  height: 24px;
  left: 12px;
  top: -12px;
}

.weather-card__cloud--a::after {
  width: 28px;
  height: 28px;
  right: 14px;
  top: -14px;
}

.weather-card__cloud--b {
  width: 118px;
  height: 34px;
  right: -8px;
  top: 56%;
  animation-delay: 0.8s;
}

.weather-card__cloud--b::before {
  width: 30px;
  height: 30px;
  left: 18px;
  top: -15px;
}

.weather-card__cloud--b::after {
  width: 36px;
  height: 36px;
  right: 20px;
  top: -18px;
}

.weather-card__sun {
  position: absolute;
  right: 14%;
  top: 18%;
  width: 44px;
  height: 44px;
  border-radius: 999px;
  background: radial-gradient(circle at 35% 35%, #fff8ce 0%, #ffd166 45%, #f59e0b 100%);
  box-shadow: 0 0 0 8px rgba(253, 224, 71, 0.18), 0 0 36px rgba(245, 158, 11, 0.35);
  animation: weather-sun-pulse 4.4s ease-in-out infinite;
}

.weather-card__rain {
  position: absolute;
  inset: 0;
}

.weather-card__rain--soft .weather-card__rain-drop {
  height: 30px;
  width: 1.4px;
}

.weather-card__rain-drop {
  position: absolute;
  top: -48px;
  width: 1.7px;
  height: 42px;
  border-radius: 999px;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0), rgba(186, 230, 253, 0.95));
  opacity: var(--rain-opacity);
  transform: rotate(14deg);
  animation-name: weather-rain-fall;
  animation-duration: var(--rain-duration);
  animation-delay: var(--rain-delay);
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

.weather-card__thermo {
  position: absolute;
  right: 14px;
  bottom: 8px;
  width: 56px;
  height: 112px;
  opacity: 0.44;
}

.weather-card__thermo-track {
  position: absolute;
  left: 50%;
  top: 8px;
  width: 13px;
  height: 76px;
  border: 2px solid rgba(255, 255, 255, 0.55);
  border-bottom: none;
  border-radius: 12px 12px 0 0;
  transform: translateX(-50%);
}

.weather-card__thermo-mercury {
  position: absolute;
  left: 50%;
  bottom: 18px;
  width: 7px;
  height: 62px;
  border-radius: 999px;
  background: rgba(14, 165, 233, 0.95);
  transform: translateX(-50%);
  transform-origin: center bottom;
  animation: weather-thermo-fill 3.2s ease-in-out infinite;
}

.weather-card__thermo-bulb {
  position: absolute;
  left: 50%;
  bottom: 0;
  width: 24px;
  height: 24px;
  border-radius: 999px;
  border: 2px solid rgba(255, 255, 255, 0.58);
  transform: translateX(-50%);
  background: rgba(14, 165, 233, 0.85);
  box-shadow: 0 0 0 4px rgba(255, 255, 255, 0.12);
}

.weather-card__thermo-dot {
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.68);
}

.weather-card__thermo-dot--a {
  left: 6px;
  top: 22px;
  animation: weather-thermo-drift 2.8s ease-in-out infinite;
}

.weather-card__thermo-dot--b {
  right: 5px;
  top: 44px;
  animation: weather-thermo-drift 3.4s ease-in-out infinite reverse;
}

.weather-card__range-scan {
  position: absolute;
  inset: 0;
}

.weather-card__range-axis {
  position: absolute;
  left: 12%;
  right: 10%;
  top: 58%;
  height: 1.5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.5);
}

.weather-card__range-orb {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 999px;
  box-shadow: 0 0 14px rgba(255, 255, 255, 0.36);
}

.weather-card__range-orb--high {
  background: rgba(250, 204, 21, 0.92);
  animation: weather-range-high 4.8s ease-in-out infinite;
}

.weather-card__range-orb--low {
  background: rgba(56, 189, 248, 0.9);
  animation: weather-range-low 4.8s ease-in-out infinite;
}

.weather-card__climate-flow {
  position: absolute;
  inset: 0;
}

.weather-card__humidity-ripple {
  position: absolute;
  right: 9%;
  bottom: 16%;
  border-radius: 999px;
  border: 1.4px solid rgba(255, 255, 255, 0.45);
  animation: weather-humidity-pulse 3.8s ease-out infinite;
}

.weather-card__humidity-ripple--a {
  width: 24px;
  height: 24px;
}

.weather-card__humidity-ripple--b {
  width: 44px;
  height: 44px;
  animation-delay: 1.3s;
}

.weather-card__wind-line {
  position: absolute;
  left: -45%;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(224, 242, 254, 0.92), rgba(255, 255, 255, 0));
  animation: weather-wind-slide 3.1s linear infinite;
}

.weather-card__wind-line--1 {
  top: 36%;
  width: 56%;
}

.weather-card__wind-line--2 {
  top: 48%;
  width: 46%;
  animation-delay: 0.8s;
}

.weather-card__wind-line--3 {
  top: 60%;
  width: 62%;
  animation-delay: 1.6s;
}

.weather-card__pill {
  color: inherit;
  border: 1px solid currentColor;
  background: rgba(255, 255, 255, 0.14);
}

.weather-card__hint {
  max-width: 32ch;
}

.weather-card--metric .weather-card__hint {
  max-width: none;
}

.weather-card__meter-track {
  background: rgba(255, 255, 255, 0.46);
}

.weather-card__meter-fill {
  background: linear-gradient(90deg, rgba(14, 165, 233, 0.85), rgba(59, 130, 246, 0.95));
}

.weather-card--sunny {
  border-color: #fcd34d;
  background: linear-gradient(145deg, #fff7d6 0%, #ffe8a6 48%, #fde68a 100%);
  color: #713f12;
}

.weather-card--sunny .weather-card__glow {
  background: radial-gradient(circle, rgba(255, 247, 170, 0.88) 0%, rgba(255, 237, 186, 0.24) 70%, rgba(255, 237, 186, 0) 100%);
}

.weather-card--sunny .weather-card__badge {
  background: rgba(255, 255, 255, 0.42);
  color: #92400e;
}

.weather-card--sunny .weather-card__meta,
.weather-card--sunny .weather-card__hint {
  color: rgba(120, 53, 15, 0.82);
}

.weather-card--sunny .weather-card__meter-track {
  background: rgba(255, 255, 255, 0.42);
}

.weather-card--sunny .weather-card__meter-fill {
  background: linear-gradient(90deg, #f59e0b 0%, #f97316 100%);
}

.weather-card--cloud {
  border-color: #cbd5e1;
  background: linear-gradient(145deg, #f8fafc 0%, #e2e8f0 55%, #dbeafe 100%);
  color: #334155;
}

.weather-card--cloud .weather-card__glow,
.weather-card--mist .weather-card__glow {
  background: radial-gradient(circle, rgba(241, 245, 249, 0.82) 0%, rgba(226, 232, 240, 0.18) 70%, rgba(226, 232, 240, 0) 100%);
}

.weather-card--cloud .weather-card__badge,
.weather-card--mist .weather-card__badge {
  background: rgba(248, 250, 252, 0.78);
  color: #475569;
}

.weather-card--cloud .weather-card__meta,
.weather-card--mist .weather-card__meta,
.weather-card--cloud .weather-card__hint,
.weather-card--mist .weather-card__hint {
  color: rgba(51, 65, 85, 0.76);
}

.weather-card--cloud .weather-card__meter-track,
.weather-card--mist .weather-card__meter-track {
  background: rgba(248, 250, 252, 0.72);
}

.weather-card--cloud .weather-card__meter-fill,
.weather-card--mist .weather-card__meter-fill {
  background: linear-gradient(90deg, #64748b 0%, #3b82f6 100%);
}

.weather-card--rain,
.weather-card--storm {
  border-color: #60a5fa;
  background: linear-gradient(145deg, #0b2545 0%, #15406f 46%, #1e3a8a 100%);
  color: #e2e8f0;
}

.weather-card--rain .weather-card__glow,
.weather-card--storm .weather-card__glow {
  background: radial-gradient(circle, rgba(125, 211, 252, 0.36) 0%, rgba(125, 211, 252, 0.08) 68%, rgba(125, 211, 252, 0) 100%);
}

.weather-card--rain .weather-card__badge,
.weather-card--storm .weather-card__badge {
  background: rgba(15, 23, 42, 0.34);
  color: #e0f2fe;
}

.weather-card--rain .weather-card__meta,
.weather-card--storm .weather-card__meta {
  color: rgba(224, 242, 254, 0.82);
}

.weather-card--rain .weather-card__hint,
.weather-card--storm .weather-card__hint {
  color: rgba(186, 230, 253, 0.9);
}

.weather-card--rain .weather-card__meter-track,
.weather-card--storm .weather-card__meter-track {
  background: rgba(186, 230, 253, 0.2);
}

.weather-card--rain .weather-card__meter-fill,
.weather-card--storm .weather-card__meter-fill {
  background: linear-gradient(90deg, #38bdf8 0%, #60a5fa 56%, #818cf8 100%);
}

.weather-card--storm .weather-card__rain-drop {
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0), rgba(191, 219, 254, 0.95));
  animation-duration: calc(var(--rain-duration) * 0.76);
}

.weather-card--snow {
  border-color: #93c5fd;
  background: linear-gradient(145deg, #f8fafc 0%, #e0f2fe 48%, #dbeafe 100%);
  color: #334155;
}

.weather-card--snow .weather-card__glow {
  background: radial-gradient(circle, rgba(224, 242, 254, 0.9) 0%, rgba(191, 219, 254, 0.16) 72%, rgba(191, 219, 254, 0) 100%);
}

.weather-card--snow .weather-card__badge {
  background: rgba(255, 255, 255, 0.74);
  color: #1d4ed8;
}

.weather-card--snow .weather-card__meta,
.weather-card--snow .weather-card__hint {
  color: rgba(51, 65, 85, 0.8);
}

.weather-card--snow .weather-card__meter-track {
  background: rgba(255, 255, 255, 0.74);
}

.weather-card--snow .weather-card__meter-fill {
  background: linear-gradient(90deg, #60a5fa 0%, #22d3ee 100%);
}

.weather-card--mist {
  border-color: #cbd5e1;
  background: linear-gradient(145deg, #f8fafc 0%, #e2e8f0 48%, #cbd5e1 100%);
  color: #334155;
}

.weather-card--default {
  border-color: #bae6fd;
  background: linear-gradient(145deg, #f0f9ff 0%, #e0f2fe 50%, #dbeafe 100%);
  color: #0f172a;
}

.weather-card--default .weather-card__glow {
  background: radial-gradient(circle, rgba(186, 230, 253, 0.7) 0%, rgba(186, 230, 253, 0.18) 72%, rgba(186, 230, 253, 0) 100%);
}

.weather-card--default .weather-card__badge {
  background: rgba(255, 255, 255, 0.74);
  color: #0c4a6e;
}

.weather-card--default .weather-card__meta,
.weather-card--default .weather-card__hint {
  color: rgba(15, 23, 42, 0.72);
}

.weather-card--default .weather-card__meter-track {
  background: rgba(255, 255, 255, 0.78);
}

.weather-card--default .weather-card__meter-fill {
  background: linear-gradient(90deg, #0ea5e9 0%, #2563eb 100%);
}

@keyframes weather-rain-fall {
  0% {
    transform: translate3d(0, -44px, 0) rotate(14deg);
  }
  100% {
    transform: translate3d(22px, 226px, 0) rotate(14deg);
  }
}

@keyframes weather-thermo-fill {
  0%, 100% {
    transform: translateX(-50%) scaleY(0.56);
  }
  50% {
    transform: translateX(-50%) scaleY(1);
  }
}

@keyframes weather-thermo-drift {
  0%, 100% {
    transform: translateY(0);
    opacity: 0.42;
  }
  50% {
    transform: translateY(-8px);
    opacity: 0.8;
  }
}

@keyframes weather-range-high {
  0% {
    left: 14%;
    top: 62%;
  }
  50% {
    left: 64%;
    top: 30%;
  }
  100% {
    left: 84%;
    top: 62%;
  }
}

@keyframes weather-range-low {
  0% {
    left: 82%;
    top: 66%;
  }
  50% {
    left: 34%;
    top: 74%;
  }
  100% {
    left: 12%;
    top: 66%;
  }
}

@keyframes weather-humidity-pulse {
  0% {
    transform: scale(0.6);
    opacity: 0.78;
  }
  100% {
    transform: scale(1.4);
    opacity: 0;
  }
}

@keyframes weather-wind-slide {
  0% {
    transform: translateX(0);
    opacity: 0;
  }
  20% {
    opacity: 0.9;
  }
  80% {
    opacity: 0.9;
  }
  100% {
    transform: translateX(230%);
    opacity: 0;
  }
}

@keyframes weather-cloud-drift {
  0% {
    transform: translateX(-6px);
  }
  100% {
    transform: translateX(9px);
  }
}

@keyframes weather-sun-pulse {
  0%, 100% {
    transform: scale(0.98);
  }
  50% {
    transform: scale(1.06);
  }
}

@media (prefers-reduced-motion: reduce) {
  .weather-card__cloud,
  .weather-card__sun,
  .weather-card__rain-drop,
  .weather-card__thermo-mercury,
  .weather-card__thermo-dot,
  .weather-card__range-orb,
  .weather-card__humidity-ripple,
  .weather-card__wind-line {
    animation: none !important;
  }
}
</style>
