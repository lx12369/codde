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
  today_expense_amount: 0,
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
  today_consumption_amount: 0,
  today_consumption_people: 0
})

const billingDayTypeLabel = computed(() => (billingDayType.value === 'weekend' ? '周末' : '工作日'))
const nextBillingDayTypeLabel = computed(() => (billingDayType.value === 'weekend' ? '工作日' : '周末'))
const billingDayTypeBadgeClass = computed(() => (
  billingDayType.value === 'weekend'
    ? 'bg-amber-100 text-amber-700 border border-amber-200'
    : 'bg-sky-100 text-sky-700 border border-sky-200'
))

const coreKpiCards = computed(() => ([
  {
    id: 'today_consumption_amount',
    title: '今日消费金额',
    value: formatAmount(stats.value.today_consumption_amount),
    hint: '按消费流水统计',
    tag: '消费收入',
    cardClass: 'core-kpi-card--income',
    tagClass: 'core-kpi-card__tag--income',
    barClass: 'core-kpi-card__meter-fill--income',
    valueClass: 'core-kpi-card__value--amount',
    barWidth: calcKpiBarWidth('today_consumption_amount', stats.value.today_consumption_amount)
  },
  {
    id: 'today_consumption_people',
    title: '今日消费人次',
    value: formatPeople(stats.value.today_consumption_people),
    hint: '按消费记录估算人次',
    tag: '客流热度',
    cardClass: 'core-kpi-card--people',
    tagClass: 'core-kpi-card__tag--people',
    barClass: 'core-kpi-card__meter-fill--people',
    valueClass: 'core-kpi-card__value--people',
    barWidth: calcKpiBarWidth('today_consumption_people', stats.value.today_consumption_people)
  }
]))

const overviewCards = computed(() => ([
  {
    id: 'active_timers_count',
    title: '活跃计时项目',
    value: formatCount(stats.value.active_timers_count),
    tag: '在场服务',
    chipClass: 'bg-rose-50 text-rose-700',
    dotClass: 'bg-rose-500',
    orbClass: 'bg-rose-100'
  },
  {
    id: 'today_net_income',
    title: '今日净收益',
    value: formatAmount(stats.value.today_net_income),
    tag: '净收益',
    chipClass: 'bg-emerald-50 text-emerald-700',
    dotClass: 'bg-emerald-500',
    orbClass: 'bg-emerald-100',
    valueClass: 'bead-overview-card__value--compact'
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
    id: 'total_customers',
    title: '客户总数',
    value: formatCount(stats.value.total_customers),
    tag: '会员池',
    chipClass: 'bg-indigo-50 text-indigo-700',
    dotClass: 'bg-indigo-500',
    orbClass: 'bg-indigo-100'
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
    id: 'today_transactions',
    title: '今日充值笔数',
    value: formatCount(stats.value.today_transactions),
    tag: '充值频次',
    chipClass: 'bg-sky-50 text-sky-700',
    dotClass: 'bg-sky-500',
    orbClass: 'bg-sky-100'
  }
]))

const amountInsight = computed(() => {
  const recharge = stats.value.today_amount
  const consumeRevenue = stats.value.today_consumption_amount
  const expenseAmount = stats.value.today_expense_amount
  const beadLoss = stats.value.today_bead_loss_amount
  const total = recharge + consumeRevenue
  const netIncome = consumeRevenue - expenseAmount - beadLoss

  const lossRate = consumeRevenue > 0
    ? Math.round((beadLoss / consumeRevenue) * 100)
    : beadLoss > 0
      ? 100
      : 0

  return {
    rechargePercent: total > 0 ? Math.round((recharge / total) * 100) : 0,
    consumePercent: total > 0 ? Math.round((consumeRevenue / total) * 100) : 0,
    totalFlow: total,
    expenseAmount,
    beadLoss,
    netIncome,
    lossRate: Math.min(100, Math.max(0, lossRate)),
    flowHealth: consumeRevenue <= 0 && expenseAmount <= 0 && beadLoss <= 0
      ? '今日暂无经营流水'
      : netIncome >= 0
        ? '已覆盖支出与损耗'
        : '支出与损耗高于消费收益'
  }
})

const averageInsight = computed(() => {
  const consumeCount = stats.value.today_consumptions
  const consumePeople = stats.value.today_consumption_people
  const consumeAmount = stats.value.today_consumption_amount

  return {
    avgPerOrder: consumeCount > 0 ? consumeAmount / consumeCount : 0,
    avgPerPerson: consumePeople > 0 ? consumeAmount / consumePeople : 0,
    orderPerPerson: consumePeople > 0 ? consumeCount / consumePeople : 0
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
    sunny: '建议关注店内温控与补水提示。',
    cloud: '建议按平峰节奏安排接待与排班。',
    rain: '可提前准备防滑与雨具收纳。',
    storm: '建议加强入店动线引导。',
    snow: '注意门店地面干燥与保暖提醒。',
    mist: '建议加强到店指引信息。',
    default: '按常规运营节奏执行。'
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

function formatSignedAmount(amount) {
  const normalized = toNumber(amount)
  if (normalized === 0) return formatAmount(0)
  const sign = normalized > 0 ? '+' : '-'
  return `${sign}${formatAmount(Math.abs(normalized))}`
}

function formatDecimal(value, digits = 2) {
  const normalized = toNumber(value)
  return normalized.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  })
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
    today_expense_amount: toNumber(payload.today_expense_amount),
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
      today_consumption_amount: toNumber(parsed.today_consumption_amount ?? parsed.today_net_income),
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
  <div class="bead-dashboard space-y-6 p-4 sm:p-6">
    <div class="bead-dashboard__ambient" aria-hidden="true">
      <span class="bead-dashboard__dotfield"></span>
      <span class="bead-dashboard__ribbon bead-dashboard__ribbon--a"></span>
      <span class="bead-dashboard__ribbon bead-dashboard__ribbon--b"></span>
    </div>

    <section class="ops-hero bead-shell relative overflow-hidden rounded-2xl border border-orange-200 p-4 sm:p-6">
      <div class="ops-hero__ambient" aria-hidden="true">
        <span class="ops-hero__grid"></span>
        <span class="ops-hero__mesh"></span>
        <span class="ops-hero__orb ops-hero__orb--a"></span>
        <span class="ops-hero__orb ops-hero__orb--b"></span>
        <span class="ops-hero__ring ops-hero__ring--a"></span>
        <span class="ops-hero__ring ops-hero__ring--b"></span>
        <span class="ops-hero__scan"></span>
      </div>
      <div class="ops-hero__content flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div class="space-y-2">
          <h1 class="ops-hero__title text-2xl font-bold text-slate-900">运营概况</h1>
          <div class="flex items-center gap-2">
            <span class="text-sm text-slate-600">当前计费日类型</span>
            <span :class="['ops-hero__status rounded-full px-2.5 py-1 text-xs font-semibold', billingDayTypeBadgeClass]">
              {{ billingDayTypeLabel }}
            </span>
          </div>
          <p class="text-xs text-slate-600">
            节假日可手动切换为周末计费
            <span v-if="billingDayType !== calendarDayType">
              （今日自然日类型：{{ calendarDayType === 'weekend' ? '周末' : '工作日' }}）
            </span>
          </p>
          <p v-if="lastUpdateTime" class="ops-hero__timestamp text-xs text-slate-600">最后更新：{{ lastUpdateTime }}</p>
        </div>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
          <button
            @click="switchBillingDayType"
            class="ops-hero__btn ops-hero__btn--ghost min-h-11 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors duration-200"
          >
            切换为{{ nextBillingDayTypeLabel }}
          </button>
          <button
            @click="refreshData"
            :disabled="isLoading"
            :class="[
              'ops-hero__btn min-h-11 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200',
              isLoading
                ? 'cursor-not-allowed ops-hero__btn--disabled'
                : 'ops-hero__btn--primary'
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

    <section class="bead-kpi-grid grid grid-cols-1 gap-4 md:grid-cols-2">
      <article
        v-for="card in coreKpiCards"
        :key="card.id"
        :class="[
          'core-kpi-card relative overflow-hidden rounded-2xl border p-5 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-xl',
          card.cardClass
        ]"
      >
        <span class="core-kpi-card__grid"></span>
        <span class="core-kpi-card__glow"></span>
        <span class="core-kpi-card__orb"></span>
        <span class="core-kpi-card__spark core-kpi-card__spark--a"></span>
        <span class="core-kpi-card__spark core-kpi-card__spark--b"></span>
        <p class="core-kpi-card__title text-sm">{{ card.title }}</p>
        <p :class="['core-kpi-card__value mt-3 font-semibold tracking-tight', card.valueClass || 'text-3xl']">{{ card.value }}</p>
        <div class="mt-2 flex items-center gap-2">
          <p class="core-kpi-card__hint text-xs">{{ card.hint }}</p>
          <span :class="['core-kpi-card__tag rounded-full px-2 py-0.5 text-[11px]', card.tagClass]">{{ card.tag }}</span>
        </div>
        <div class="core-kpi-card__meter mt-3 h-1.5 rounded-full">
          <div
            :class="['core-kpi-card__meter-fill h-1.5 rounded-full transition-all duration-700', card.barClass]"
            :style="{ width: card.barWidth }"
          ></div>
        </div>
      </article>
    </section>

    <section class="bead-weather-shell bead-shell rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <div class="bead-weather-shell__head flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 class="bead-section-title text-lg font-semibold text-slate-900">当天天气</h2>
        <div class="flex items-center gap-2">
          <p class="bead-section-meta text-xs text-slate-500">
            数据来源：{{ weather.provider }} · 观测时间：{{ formatDateTime(weather.observed_at) }}
          </p>
          <button
            @click="manualRefreshWeather"
            :disabled="isWeatherRefreshing"
            :class="[
              'bead-weather-shell__refresh rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors duration-200',
              isWeatherRefreshing
                ? 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
                : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
            ]"
          >
            {{ isWeatherRefreshing ? '刷新中...' : '刷新' }}
          </button>
        </div>
      </div>

      <p v-if="weatherError" class="bead-weather-shell__error mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
        {{ weatherError }}
      </p>

      <div v-else class="bead-weather-shell__grid mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
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

    <section class="bead-overview-shell bead-shell rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <div class="bead-section-head mb-4 flex items-center justify-between">
        <h2 class="bead-section-title text-lg font-semibold text-slate-900">运营总览</h2>
        <span class="bead-section-meta text-xs text-slate-500">来自当日与累计统计</span>
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <article
          v-for="card in overviewCards"
          :key="card.id"
          class="bead-overview-card relative overflow-hidden rounded-xl border border-slate-200 p-4"
        >
          <span class="bead-overview-card__edge" aria-hidden="true"></span>
          <span class="bead-overview-card__texture" aria-hidden="true"></span>
          <span class="bead-overview-card__glow"></span>
          <span :class="['bead-overview-card__orb absolute -right-3 -top-3 h-10 w-10 rounded-full', card.orbClass]"></span>
          <span class="bead-overview-card__pearls" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </span>
          <p class="bead-overview-card__title text-xs">{{ card.title }}</p>
          <p :class="['bead-overview-card__value mt-2 text-2xl font-semibold', card.valueClass || '']">{{ card.value }}</p>
          <div :class="['bead-overview-card__tag mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px]', card.chipClass]">
            <span :class="['h-1.5 w-1.5 rounded-full', card.dotClass]"></span>{{ card.tag }}
          </div>
          <div class="bead-overview-card__trail" aria-hidden="true">
            <span class="bead-overview-card__trail-dot"></span>
          </div>
        </article>
      </div>
    </section>

    <section class="bead-insight-shell bead-shell rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <h2 class="bead-section-title bead-insight-shell__title text-lg font-semibold text-slate-900">结构洞察</h2>
      <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <article class="bead-insight-card bead-insight-card--structure relative overflow-hidden rounded-xl border border-slate-200 p-4">
          <span class="bead-insight-card__glow"></span>
          <span class="absolute -right-4 -top-4 h-12 w-12 rounded-full bg-emerald-100/70"></span>
          <p class="bead-insight-card__heading text-sm font-medium text-slate-700">经营结构</p>
          <div class="bead-insight-card__chip mt-2 inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>充值 / 消费收益
          </div>
          <div class="mt-3 space-y-3">
            <div>
              <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
                <span>充值占比</span>
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
                <span>消费收益占比</span>
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
          <p class="bead-insight-card__summary mt-3 text-sm text-slate-600">
            经营流水 <span class="font-semibold text-slate-900">{{ formatAmount(amountInsight.totalFlow) }}</span>，
            今日支出 <span class="font-semibold text-slate-900">{{ formatAmount(amountInsight.expenseAmount) }}</span>，
            豆仓损耗 <span class="font-semibold text-slate-900">{{ formatAmount(amountInsight.beadLoss) }}</span>，
            净收益 <span class="font-semibold text-slate-900">{{ formatSignedAmount(amountInsight.netIncome) }}</span>
            （{{ amountInsight.flowHealth }}，损耗率 {{ amountInsight.lossRate }}%）。
          </p>
        </article>

        <article class="bead-insight-card bead-insight-card--efficiency relative overflow-hidden rounded-xl border border-slate-200 p-4">
          <span class="bead-insight-card__glow"></span>
          <span class="absolute -right-4 -top-4 h-12 w-12 rounded-full bg-orange-100/70"></span>
          <p class="bead-insight-card__heading text-sm font-medium text-slate-700">客单效率洞察</p>
          <div class="bead-insight-card__chip mt-2 inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-[11px] text-orange-700">
            <span class="h-1.5 w-1.5 rounded-full bg-orange-500"></span>消费效率
          </div>
          <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div class="bead-insight-mini rounded-lg border border-slate-100 bg-white p-3 shadow-sm">
              <p class="text-xs text-slate-500">客单价（按笔）</p>
              <p class="mt-2 text-xl font-semibold text-slate-900">{{ formatAmount(averageInsight.avgPerOrder) }}</p>
            </div>
            <div class="bead-insight-mini rounded-lg border border-slate-100 bg-white p-3 shadow-sm">
              <p class="text-xs text-slate-500">人均消费（按人次）</p>
              <p class="mt-2 text-xl font-semibold text-slate-900">{{ formatAmount(averageInsight.avgPerPerson) }}</p>
            </div>
          </div>
          <p class="bead-insight-card__summary mt-3 text-sm text-slate-600">
            今日消费 {{ formatCount(stats.today_consumptions) }} 笔，覆盖 {{ formatCount(stats.today_consumption_people) }} 人，
            人均消费频次 {{ formatDecimal(averageInsight.orderPerPerson) }} 笔。
          </p>
        </article>
      </div>
    </section>

  </div>
</template>

<style scoped>
.bead-dashboard {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  border-radius: 1.25rem;
  background:
    radial-gradient(circle at 12% 8%, rgba(250, 204, 21, 0.2), transparent 38%),
    radial-gradient(circle at 88% 18%, rgba(45, 212, 191, 0.18), transparent 34%),
    radial-gradient(circle at 50% 100%, rgba(251, 113, 133, 0.16), transparent 42%),
    linear-gradient(160deg, #fff9ec 0%, #fff4ef 45%, #effcf8 100%);
}

.bead-dashboard > *:not(.bead-dashboard__ambient) {
  position: relative;
  z-index: 1;
}

.bead-dashboard__ambient {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
  z-index: 0;
}

.bead-dashboard__dotfield {
  position: absolute;
  inset: -22% -10%;
  background-image:
    radial-gradient(circle at 1px 1px, rgba(249, 115, 22, 0.26) 1.2px, transparent 1.7px),
    radial-gradient(circle at 12px 12px, rgba(14, 165, 233, 0.22) 1px, transparent 1.5px);
  background-size: 24px 24px, 28px 28px;
  opacity: 0.34;
  animation: bead-dot-pan 30s linear infinite;
}

.bead-dashboard__ribbon {
  position: absolute;
  width: clamp(360px, 42vw, 680px);
  height: clamp(360px, 42vw, 680px);
  border-radius: 999px;
  filter: blur(28px);
  opacity: 0.48;
  transform-origin: center;
  animation: bead-ribbon-drift 11s ease-in-out infinite alternate;
}

.bead-dashboard__ribbon--a {
  right: -220px;
  top: -220px;
  background: radial-gradient(circle, rgba(251, 146, 60, 0.5) 0%, rgba(251, 146, 60, 0) 72%);
}

.bead-dashboard__ribbon--b {
  left: -240px;
  bottom: -260px;
  background: radial-gradient(circle, rgba(20, 184, 166, 0.46) 0%, rgba(20, 184, 166, 0) 70%);
  animation-delay: 1.2s;
}

.bead-shell {
  position: relative;
  isolation: isolate;
  border-color: rgba(251, 146, 60, 0.26) !important;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.94) 0%, rgba(255, 251, 245, 0.9) 52%, rgba(240, 253, 250, 0.86) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.94),
    0 16px 32px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(5px);
}

.bead-shell::after {
  content: '';
  position: absolute;
  inset: 1px;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(120deg, transparent 5%, rgba(255, 255, 255, 0.6) 48%, transparent 78%);
  opacity: 0.2;
  transform: translateX(-120%);
  animation: bead-shell-sheen 12s ease-in-out infinite;
}

.bead-section-head {
  padding-bottom: 0.68rem;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.48);
}

.bead-section-title {
  letter-spacing: 0.04em;
  color: #1e293b;
}

.bead-section-meta {
  color: #64748b;
}

.bead-kpi-grid .core-kpi-card {
  border-color: rgba(249, 115, 22, 0.3);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 12px 26px rgba(15, 23, 42, 0.12);
}

.bead-kpi-grid .core-kpi-card:hover {
  transform: translateY(-4px);
}

.bead-weather-shell {
  border-color: rgba(14, 165, 233, 0.24) !important;
  background:
    linear-gradient(140deg, rgba(240, 249, 255, 0.95) 0%, rgba(248, 250, 252, 0.95) 46%, rgba(236, 254, 255, 0.94) 100%);
}

.bead-weather-shell__head {
  border-bottom: 1px dashed rgba(148, 163, 184, 0.45);
  padding-bottom: 0.7rem;
}

.bead-weather-shell__refresh {
  border-color: rgba(14, 165, 233, 0.34);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.84);
}

.bead-weather-shell__error {
  border-style: dashed;
}

.bead-weather-shell__grid {
  align-items: stretch;
}

.bead-overview-shell {
  border-color: rgba(249, 115, 22, 0.25) !important;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.96) 0%, rgba(255, 247, 237, 0.92) 40%, rgba(236, 253, 245, 0.9) 100%);
}

.bead-overview-card {
  --overview-accent: #fb923c;
  --overview-accent-soft: rgba(251, 146, 60, 0.3);
  --overview-accent-deep: rgba(251, 146, 60, 0.74);
  position: relative;
  isolation: isolate;
  border-color: rgba(148, 163, 184, 0.32);
  background:
    linear-gradient(148deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 250, 252, 0.9) 58%, rgba(241, 245, 249, 0.86) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 12px 24px rgba(15, 23, 42, 0.08);
  transition: transform 240ms ease, box-shadow 240ms ease, border-color 240ms ease;
}

.bead-overview-card:hover {
  transform: translateY(-5px);
  border-color: var(--overview-accent-soft);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.94),
    0 18px 34px rgba(15, 23, 42, 0.12);
}

.bead-overview-card__edge,
.bead-overview-card__texture,
.bead-overview-card__glow,
.bead-overview-card__orb,
.bead-overview-card__pearls {
  position: absolute;
  pointer-events: none;
}

.bead-overview-card__edge {
  left: 14px;
  right: 14px;
  top: 0;
  height: 2.5px;
  border-radius: 999px;
  z-index: 1;
  background: linear-gradient(90deg, transparent, var(--overview-accent-deep), transparent);
  opacity: 0.95;
}

.bead-overview-card__texture {
  inset: 0;
  z-index: 0;
  opacity: 0.36;
  background-image:
    radial-gradient(circle at 12px 12px, rgba(148, 163, 184, 0.22) 1.1px, transparent 1.6px),
    linear-gradient(120deg, rgba(148, 163, 184, 0.08), rgba(255, 255, 255, 0));
  background-size: 22px 22px, 100% 100%;
}

.bead-overview-card__glow {
  right: -48px;
  top: -56px;
  width: 164px;
  height: 164px;
  z-index: 0;
  border-radius: 999px;
  background: radial-gradient(circle, var(--overview-accent-soft), rgba(255, 255, 255, 0) 72%);
  opacity: 0.58;
  filter: blur(2px);
  animation: bead-overview-glow 6s ease-in-out infinite;
}

.bead-overview-card__pearls {
  right: 16px;
  bottom: 14px;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.bead-overview-card__pearls span {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--overview-accent-deep);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.45);
  opacity: 0.62;
  animation: bead-overview-pearl 3.6s ease-in-out infinite;
}

.bead-overview-card__pearls span:nth-child(2) {
  animation-delay: 0.4s;
}

.bead-overview-card__pearls span:nth-child(3) {
  animation-delay: 0.8s;
}

.bead-overview-card__orb {
  z-index: 1;
  opacity: 0.78;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5), 0 0 0 4px rgba(255, 255, 255, 0.3);
  filter: saturate(1.08);
  animation: bead-overview-orb 5.6s ease-in-out infinite;
}

.bead-overview-card__trail {
  position: relative;
  z-index: 2;
  margin-top: 0.75rem;
  height: 5px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.12), rgba(148, 163, 184, 0.36), rgba(148, 163, 184, 0.12));
  overflow: hidden;
}

.bead-overview-card__trail-dot {
  position: absolute;
  left: -2%;
  top: 50%;
  width: 11px;
  height: 11px;
  border-radius: 999px;
  transform: translateY(-50%);
  background: var(--overview-accent-deep);
  box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.58), 0 0 16px var(--overview-accent-soft);
  animation: bead-overview-trail 3.9s ease-in-out infinite;
}

.bead-overview-card__title,
.bead-overview-card__value,
.bead-overview-card__tag,
.bead-overview-card__trail {
  position: relative;
  z-index: 2;
}

.bead-overview-card__title {
  color: #475569;
  letter-spacing: 0.03em;
}

.bead-overview-card__value {
  color: #0b1324;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.5);
}

.bead-overview-card__value--compact {
  font-size: clamp(1.3rem, 1.8vw, 1.75rem);
  line-height: 1.2;
}

.bead-overview-card__tag {
  border: 1px solid rgba(148, 163, 184, 0.24);
  backdrop-filter: blur(2px);
}

.bead-overview-card:nth-child(1) {
  --overview-accent: #6366f1;
  --overview-accent-soft: rgba(99, 102, 241, 0.3);
  --overview-accent-deep: rgba(79, 70, 229, 0.8);
  border-color: rgba(129, 140, 248, 0.34);
  background: linear-gradient(150deg, #f8faff 0%, #eef2ff 56%, #e0e7ff 100%);
}

.bead-overview-card:nth-child(2) {
  --overview-accent: #0ea5e9;
  --overview-accent-soft: rgba(14, 165, 233, 0.32);
  --overview-accent-deep: rgba(2, 132, 199, 0.82);
  border-color: rgba(56, 189, 248, 0.34);
  background: linear-gradient(150deg, #f4fbff 0%, #e0f2fe 56%, #dbeafe 100%);
}

.bead-overview-card:nth-child(3) {
  --overview-accent: #10b981;
  --overview-accent-soft: rgba(16, 185, 129, 0.3);
  --overview-accent-deep: rgba(5, 150, 105, 0.82);
  border-color: rgba(52, 211, 153, 0.34);
  background: linear-gradient(150deg, #f3fff9 0%, #dcfce7 56%, #ccfbf1 100%);
}

.bead-overview-card:nth-child(4) {
  --overview-accent: #f59e0b;
  --overview-accent-soft: rgba(245, 158, 11, 0.3);
  --overview-accent-deep: rgba(217, 119, 6, 0.82);
  border-color: rgba(251, 191, 36, 0.34);
  background: linear-gradient(150deg, #fffaf0 0%, #fef3c7 56%, #fde68a 100%);
}

.bead-overview-card:nth-child(5) {
  --overview-accent: #64748b;
  --overview-accent-soft: rgba(100, 116, 139, 0.3);
  --overview-accent-deep: rgba(51, 65, 85, 0.8);
  border-color: rgba(148, 163, 184, 0.34);
  background: linear-gradient(150deg, #f8fafc 0%, #e2e8f0 56%, #cbd5e1 100%);
}

.bead-overview-card:nth-child(6) {
  --overview-accent: #f43f5e;
  --overview-accent-soft: rgba(244, 63, 94, 0.28);
  --overview-accent-deep: rgba(225, 29, 72, 0.8);
  border-color: rgba(251, 113, 133, 0.34);
  background: linear-gradient(150deg, #fff5f7 0%, #ffe4e6 56%, #fecdd3 100%);
}

.bead-overview-card:nth-child(2n) .bead-overview-card__glow,
.bead-overview-card:nth-child(2n) .bead-overview-card__trail-dot {
  animation-delay: 0.5s;
}

.bead-overview-card:nth-child(3n) .bead-overview-card__orb {
  animation-delay: 0.8s;
}

.bead-insight-shell {
  border-color: rgba(20, 184, 166, 0.28) !important;
  background:
    linear-gradient(150deg, rgba(255, 255, 255, 0.96) 0%, rgba(240, 253, 250, 0.9) 48%, rgba(255, 247, 237, 0.9) 100%);
}

.bead-insight-shell__title {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.bead-insight-shell__title::before {
  content: '';
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #14b8a6 0%, #f97316 100%);
  box-shadow: 0 0 0 6px rgba(20, 184, 166, 0.14);
}

.bead-insight-card {
  isolation: isolate;
  border-color: rgba(148, 163, 184, 0.34);
  background:
    linear-gradient(150deg, rgba(255, 255, 255, 0.94) 0%, rgba(248, 250, 252, 0.9) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    0 12px 26px rgba(15, 23, 42, 0.08);
}

.bead-insight-card__glow {
  position: absolute;
  inset: -30% -24%;
  z-index: 0;
  pointer-events: none;
  opacity: 0.34;
  filter: blur(16px);
  animation: bead-insight-sweep 8.5s ease-in-out infinite;
}

.bead-insight-card--structure .bead-insight-card__glow {
  background:
    conic-gradient(
      from 90deg at 45% 44%,
      rgba(16, 185, 129, 0.54),
      rgba(56, 189, 248, 0.22),
      rgba(245, 158, 11, 0.26),
      rgba(16, 185, 129, 0.54)
    );
}

.bead-insight-card--efficiency .bead-insight-card__glow {
  background:
    conic-gradient(
      from 160deg at 50% 45%,
      rgba(249, 115, 22, 0.45),
      rgba(236, 72, 153, 0.24),
      rgba(56, 189, 248, 0.24),
      rgba(249, 115, 22, 0.45)
    );
}

.bead-insight-card__heading,
.bead-insight-card__chip,
.bead-insight-card__summary,
.bead-insight-mini {
  position: relative;
  z-index: 1;
}

.bead-insight-card__heading {
  color: #334155;
  letter-spacing: 0.02em;
}

.bead-insight-card__chip {
  border: 1px solid rgba(148, 163, 184, 0.22);
}

.bead-insight-mini {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.8);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.88),
    0 8px 16px rgba(15, 23, 42, 0.06);
}

.bead-insight-card__summary {
  color: #475569;
}

@media (max-width: 1024px) {
  .bead-section-meta {
    display: none;
  }
}

@media (max-width: 640px) {
  .bead-dashboard {
    border-radius: 1rem;
  }

  .bead-dashboard__ribbon {
    width: 132vw;
    height: 132vw;
    filter: blur(22px);
  }

  .bead-dashboard__ribbon--a {
    right: -42vw;
    top: -44vw;
  }

  .bead-dashboard__ribbon--b {
    left: -48vw;
    bottom: -52vw;
  }

  .bead-weather-shell__head {
    gap: 0.7rem;
  }

  .bead-weather-shell__head > div {
    width: 100%;
    justify-content: space-between;
  }

  .bead-section-title {
    letter-spacing: 0.02em;
  }
}

.ops-hero {
  isolation: isolate;
  background:
    radial-gradient(circle at 16% 24%, rgba(250, 204, 21, 0.24), transparent 46%),
    radial-gradient(circle at 84% 18%, rgba(244, 114, 182, 0.2), transparent 44%),
    radial-gradient(circle at 54% 76%, rgba(45, 212, 191, 0.16), transparent 52%),
    linear-gradient(130deg, #fff9ed 0%, #fff5f7 48%, #f0fdfa 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.75),
    0 14px 28px rgba(251, 146, 60, 0.12);
}

.ops-hero__ambient {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.ops-hero__content {
  position: relative;
  z-index: 1;
}

.ops-hero__mesh {
  position: absolute;
  inset: -38% -22%;
  background:
    conic-gradient(
      from 120deg at 50% 50%,
      rgba(251, 191, 36, 0.28),
      rgba(244, 114, 182, 0.12),
      rgba(45, 212, 191, 0.22),
      rgba(251, 191, 36, 0.28)
    );
  filter: blur(20px);
  opacity: 0.7;
  animation: ops-hero-mesh-shift 11s ease-in-out infinite alternate;
}

.ops-hero__grid {
  position: absolute;
  inset: -35% -12%;
  background-image:
    radial-gradient(circle at 10px 10px, rgba(251, 191, 36, 0.24) 2px, transparent 2.3px),
    linear-gradient(rgba(251, 146, 60, 0.09) 1px, transparent 1px),
    linear-gradient(90deg, rgba(45, 212, 191, 0.08) 1px, transparent 1px);
  background-size: 22px 22px, 44px 44px, 44px 44px;
  transform: perspective(640px) rotateX(62deg) translateY(24%);
  transform-origin: center top;
  opacity: 0.48;
  animation: ops-hero-grid-drift 16s linear infinite;
}

.ops-hero__orb {
  position: absolute;
  border-radius: 999px;
  filter: blur(1px);
  opacity: 0.62;
}

.ops-hero__orb--a {
  width: 184px;
  height: 184px;
  right: -40px;
  top: -52px;
  background: radial-gradient(circle, rgba(251, 191, 36, 0.52), rgba(251, 191, 36, 0.03) 72%);
  animation: ops-hero-orb-float 7.4s ease-in-out infinite;
}

.ops-hero__orb--b {
  width: 142px;
  height: 142px;
  left: -38px;
  bottom: -48px;
  background: radial-gradient(circle, rgba(244, 114, 182, 0.42), rgba(244, 114, 182, 0.02) 74%);
  animation: ops-hero-orb-float 9.4s ease-in-out infinite reverse;
}

.ops-hero__ring {
  position: absolute;
  border-radius: 999px;
  border: 2px dotted rgba(251, 146, 60, 0.38);
  opacity: 0.42;
  animation: ops-hero-ring-pulse 8s ease-out infinite;
}

.ops-hero__ring--a {
  width: 240px;
  height: 240px;
  right: -72px;
  top: -92px;
}

.ops-hero__ring--b {
  width: 180px;
  height: 180px;
  left: -58px;
  bottom: -88px;
  animation-delay: 1.9s;
}

.ops-hero__scan {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    102deg,
    transparent 12%,
    rgba(250, 204, 21, 0.18) 40%,
    rgba(255, 255, 255, 0.34) 50%,
    rgba(45, 212, 191, 0.18) 60%,
    transparent 84%
  );
  mix-blend-mode: soft-light;
  transform: translateX(-120%);
  animation: ops-hero-scan 7.4s ease-in-out infinite;
}

.ops-hero__title {
  letter-spacing: 0.01em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.5);
  animation: ops-hero-title-in 560ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

.ops-hero__status {
  position: relative;
  overflow: hidden;
}

.ops-hero__status::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: -40%;
  width: 32%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.52), transparent);
  transform: skewX(-20deg);
  animation: ops-hero-chip-glint 6s ease-in-out infinite;
}

.ops-hero__timestamp {
  animation: ops-hero-fade-in 620ms ease-out;
}

.ops-hero__btn {
  border: 1px solid rgba(251, 146, 60, 0.28);
  backdrop-filter: blur(3px);
}

.ops-hero__btn--ghost {
  background: rgba(255, 255, 255, 0.72);
  color: #9a3412;
}

.ops-hero__btn--ghost:hover {
  background: rgba(255, 255, 255, 0.92);
}

.ops-hero__btn--primary {
  background: linear-gradient(135deg, #fb7185 0%, #f59e0b 100%);
  color: #fffaf0;
  border-color: rgba(251, 146, 60, 0.44);
  box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.2), 0 10px 20px rgba(249, 115, 22, 0.24);
}

.ops-hero__btn--primary:hover {
  filter: brightness(1.08);
}

.ops-hero__btn--disabled {
  background: rgba(226, 232, 240, 0.72);
  color: rgba(100, 116, 139, 0.92);
  border-color: rgba(148, 163, 184, 0.34);
}

.core-kpi-card {
  isolation: isolate;
}

.core-kpi-card__grid,
.core-kpi-card__glow,
.core-kpi-card__orb,
.core-kpi-card__spark {
  position: absolute;
  pointer-events: none;
  z-index: 0;
}

.core-kpi-card__title,
.core-kpi-card__value,
.core-kpi-card__hint,
.core-kpi-card__tag,
.core-kpi-card__meter {
  position: relative;
  z-index: 1;
}

.core-kpi-card__title {
  color: #64748b;
}

.core-kpi-card__value {
  color: #0f172a;
}

.core-kpi-card__value--amount {
  font-size: clamp(2rem, 2.6vw, 2.6rem);
  line-height: 1.08;
}

.core-kpi-card__value--people {
  font-size: clamp(1.9rem, 2.3vw, 2.35rem);
  line-height: 1.1;
}

.core-kpi-card__hint {
  color: #64748b;
}

.core-kpi-card__tag {
  border: 1px solid transparent;
}

.core-kpi-card__meter {
  background: rgba(148, 163, 184, 0.18);
  overflow: hidden;
}

.core-kpi-card__meter-fill {
  min-width: 10%;
  position: relative;
}

.core-kpi-card__meter-fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent, rgba(255, 255, 255, 0.55), transparent);
  transform: translateX(-120%);
  animation: core-kpi-meter-glint 3.2s ease-in-out infinite;
}

.core-kpi-card__grid {
  inset: 0;
  opacity: 0.34;
  background-image:
    radial-gradient(circle at 10px 10px, rgba(148, 163, 184, 0.22) 2px, transparent 2.4px),
    linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 20px 20px, 40px 40px, 40px 40px;
}

.core-kpi-card__glow {
  width: 220px;
  height: 220px;
  right: -86px;
  top: -108px;
  border-radius: 999px;
  filter: blur(1px);
  opacity: 0.62;
}

.core-kpi-card__orb {
  width: 78px;
  height: 78px;
  left: -16px;
  bottom: -22px;
  border-radius: 999px;
  opacity: 0.44;
}

.core-kpi-card__spark {
  width: 6px;
  height: 6px;
  border-radius: 999px;
}

.core-kpi-card__spark--a {
  right: 24px;
  top: 18px;
  animation: core-kpi-spark-drift 3.8s ease-in-out infinite;
}

.core-kpi-card__spark--b {
  right: 52px;
  top: 34px;
  animation: core-kpi-spark-drift 4.8s ease-in-out infinite reverse;
}

.core-kpi-card--income {
  border-color: rgba(52, 211, 153, 0.44);
  background:
    radial-gradient(circle at 86% -10%, rgba(45, 212, 191, 0.22), transparent 48%),
    linear-gradient(145deg, #ecfdf5 0%, #f0fdfa 46%, #f8fafc 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 12px 24px rgba(20, 184, 166, 0.12);
}

.core-kpi-card--income .core-kpi-card__grid {
  animation: core-kpi-grid-pan 12s linear infinite;
}

.core-kpi-card--income .core-kpi-card__glow {
  background: radial-gradient(circle, rgba(45, 212, 191, 0.4), rgba(45, 212, 191, 0.03) 72%);
}

.core-kpi-card--income .core-kpi-card__orb {
  background: radial-gradient(circle, rgba(110, 231, 183, 0.46), rgba(110, 231, 183, 0.04) 70%);
  animation: core-kpi-orb-rise 6.2s ease-in-out infinite;
}

.core-kpi-card--income .core-kpi-card__spark {
  background: rgba(45, 212, 191, 0.82);
  box-shadow: 0 0 10px rgba(45, 212, 191, 0.56);
}

.core-kpi-card__tag--income {
  color: #0f766e;
  background: rgba(204, 251, 241, 0.92);
  border-color: rgba(94, 234, 212, 0.56);
}

.core-kpi-card__meter-fill--income {
  background: linear-gradient(90deg, #10b981 0%, #14b8a6 52%, #06b6d4 100%);
}

.core-kpi-card--people {
  border-color: rgba(244, 114, 182, 0.42);
  background:
    radial-gradient(circle at 90% -8%, rgba(244, 114, 182, 0.24), transparent 46%),
    linear-gradient(145deg, #fff7ed 0%, #fdf2f8 46%, #faf5ff 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 12px 24px rgba(236, 72, 153, 0.12);
}

.core-kpi-card--people .core-kpi-card__grid {
  animation: core-kpi-grid-pan 16s linear infinite reverse;
}

.core-kpi-card--people .core-kpi-card__glow {
  background: radial-gradient(circle, rgba(244, 114, 182, 0.42), rgba(244, 114, 182, 0.04) 70%);
}

.core-kpi-card--people .core-kpi-card__orb {
  background: radial-gradient(circle, rgba(196, 181, 253, 0.5), rgba(196, 181, 253, 0.04) 72%);
  animation: core-kpi-orb-rise 7.2s ease-in-out infinite reverse;
}

.core-kpi-card--people .core-kpi-card__spark {
  background: rgba(236, 72, 153, 0.78);
  box-shadow: 0 0 10px rgba(244, 114, 182, 0.52);
}

.core-kpi-card__tag--people {
  color: #9d174d;
  background: rgba(252, 231, 243, 0.9);
  border-color: rgba(249, 168, 212, 0.62);
}

.core-kpi-card__meter-fill--people {
  background: linear-gradient(90deg, #ec4899 0%, #a855f7 55%, #818cf8 100%);
}

@keyframes bead-dot-pan {
  0% {
    transform: translate3d(-16px, -10px, 0);
  }
  100% {
    transform: translate3d(18px, 14px, 0);
  }
}

@keyframes bead-ribbon-drift {
  0% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  100% {
    transform: translate3d(10px, 14px, 0) scale(1.06);
  }
}

@keyframes bead-shell-sheen {
  0%, 64% {
    transform: translateX(-120%);
    opacity: 0;
  }
  76% {
    opacity: 0.24;
  }
  100% {
    transform: translateX(126%);
    opacity: 0;
  }
}

@keyframes bead-overview-glow {
  0%, 100% {
    transform: scale(0.94) translateY(0);
    opacity: 0.46;
  }
  50% {
    transform: scale(1.08) translateY(6px);
    opacity: 0.72;
  }
}

@keyframes bead-overview-trail {
  0% {
    left: -4%;
  }
  50% {
    left: 52%;
  }
  100% {
    left: 98%;
  }
}

@keyframes bead-overview-pearl {
  0%, 100% {
    transform: translateY(0) scale(0.92);
    opacity: 0.54;
  }
  50% {
    transform: translateY(-2px) scale(1.08);
    opacity: 1;
  }
}

@keyframes bead-overview-orb {
  0%, 100% {
    transform: translateY(0);
    opacity: 0.7;
  }
  50% {
    transform: translateY(4px);
    opacity: 0.95;
  }
}

@keyframes bead-insight-sweep {
  0%, 100% {
    transform: rotate(0deg) scale(1);
  }
  50% {
    transform: rotate(10deg) scale(1.06);
  }
}

@keyframes ops-hero-grid-drift {
  0% {
    transform: perspective(640px) rotateX(62deg) translate3d(-2%, 24%, 0);
  }
  100% {
    transform: perspective(640px) rotateX(62deg) translate3d(3%, 30%, 0);
  }
}

@keyframes ops-hero-mesh-shift {
  0% {
    transform: rotate(0deg) scale(1);
  }
  100% {
    transform: rotate(14deg) scale(1.07);
  }
}

@keyframes ops-hero-orb-float {
  0%, 100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(0, 11px, 0) scale(1.08);
  }
}

@keyframes ops-hero-ring-pulse {
  0% {
    transform: scale(0.76);
    opacity: 0.42;
  }
  100% {
    transform: scale(1.2);
    opacity: 0;
  }
}

@keyframes ops-hero-scan {
  0%, 46% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(118%);
  }
}

@keyframes ops-hero-chip-glint {
  0%, 72% {
    left: -45%;
  }
  100% {
    left: 138%;
  }
}

@keyframes ops-hero-title-in {
  0% {
    transform: translateY(8px);
    opacity: 0;
  }
  100% {
    transform: translateY(0);
    opacity: 1;
  }
}

@keyframes ops-hero-fade-in {
  0% {
    opacity: 0;
    transform: translateY(4px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes core-kpi-grid-pan {
  0% {
    transform: translate3d(0, 0, 0);
  }
  100% {
    transform: translate3d(20px, 20px, 0);
  }
}

@keyframes core-kpi-orb-rise {
  0%, 100% {
    transform: translateY(0);
    opacity: 0.42;
  }
  50% {
    transform: translateY(-10px);
    opacity: 0.72;
  }
}

@keyframes core-kpi-spark-drift {
  0%, 100% {
    transform: translateY(0) scale(1);
    opacity: 0.65;
  }
  50% {
    transform: translateY(-8px) scale(1.18);
    opacity: 1;
  }
}

@keyframes core-kpi-meter-glint {
  0%, 64% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(130%);
  }
}

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
  .bead-dashboard__dotfield,
  .bead-dashboard__ribbon,
  .bead-shell::after,
  .bead-overview-card__glow,
  .bead-overview-card__orb,
  .bead-overview-card__pearls span,
  .bead-overview-card__trail-dot,
  .bead-insight-card__glow,
  .ops-hero__grid,
  .ops-hero__mesh,
  .ops-hero__orb,
  .ops-hero__ring,
  .ops-hero__scan,
  .ops-hero__status::after,
  .ops-hero__title,
  .ops-hero__timestamp,
  .core-kpi-card__grid,
  .core-kpi-card__orb,
  .core-kpi-card__spark,
  .core-kpi-card__meter-fill::after,
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
