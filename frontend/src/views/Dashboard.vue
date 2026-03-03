<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Chart, registerables } from 'chart.js'
import api from '@/api'

Chart.register(...registerables)

const statsCards = ref([
  { id: 'total_customers', title: '客户总数', value: 0, icon: 'users', bgColor: 'bg-blue-500' },
  { id: 'today_transactions', title: '今日充值', value: 0, icon: 'credit-card', bgColor: 'bg-green-500' },
  { id: 'today_amount', title: '今日充值金额', value: 0, icon: 'dollar-sign', bgColor: 'bg-emerald-500', isAmount: true },
  { id: 'today_consumptions', title: '今日消费', value: 0, icon: 'shopping-cart', bgColor: 'bg-orange-500' },
  { id: 'today_consumption_amount', title: '今日消费金额', value: 0, icon: 'wallet', bgColor: 'bg-red-500', isAmount: true },
  { id: 'total_transactions', title: '交易总数', value: 0, icon: 'activity', bgColor: 'bg-purple-500' }
])

const timeRange = ref('7')
const rechargeChart = ref(null)
const consumeChart = ref(null)
let rechargeChartInstance = null
let consumeChartInstance = null

const recentActivities = ref([])
const isLoading = ref(false)
const lastUpdateTime = ref('')

const iconComponents = {
  users: `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>`,
  'credit-card': `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>`,
  'dollar-sign': `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
  'shopping-cart': `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" /></svg>`,
  wallet: `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>`,
  activity: `<svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>`
}

function getIcon(iconName) {
  return iconComponents[iconName] || iconComponents.users
}

function formatNumber(num) {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  return num.toLocaleString()
}

function formatAmount(amount) {
  return '¥' + Number(amount).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function updateTime() {
  const now = new Date()
  lastUpdateTime.value = now.toLocaleString('zh-CN')
}

async function fetchStats() {
  try {
    const response = await api.get('/dashboard/stats')
    const data = response.data || response
    
    statsCards.value = statsCards.value.map(card => ({
      ...card,
      value: data[card.id] ?? 0
    }))
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  }
}

async function fetchChartData() {
  try {
    const response = await api.get('/dashboard/charts', {
      params: { days: timeRange.value }
    })
    const data = response.data || response
    return data
  } catch (error) {
    console.error('Failed to fetch chart data:', error)
    return generateMockChartData()
  }
}

function generateMockChartData() {
  const days = parseInt(timeRange.value)
  const labels = []
  const rechargeData = []
  const consumeData = []
  
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date()
    date.setDate(date.getDate() - i)
    labels.push(`${date.getMonth() + 1}/${date.getDate()}`)
    rechargeData.push(Math.floor(Math.random() * 5000) + 1000)
    consumeData.push(Math.floor(Math.random() * 3000) + 500)
  }
  
  return {
    dates: labels,
    recharge_amounts: rechargeData,
    consumption_amounts: consumeData
  }
}

function createChart(canvas, labels, data, label, color) {
  const ctx = canvas.getContext('2d')
  
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label,
        data,
        borderColor: color,
        backgroundColor: color + '20',
        fill: true,
        tension: 0.4,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: color,
        pointBorderColor: '#fff',
        pointBorderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          titleColor: '#fff',
          bodyColor: '#fff',
          padding: 12,
          cornerRadius: 8,
          displayColors: false
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#6b7280' }
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(0, 0, 0, 0.05)' },
          ticks: {
            color: '#6b7280',
            callback: (value) => '¥' + value
          }
        }
      },
      interaction: { intersect: false, mode: 'index' }
    }
  })
}

async function initCharts() {
  const chartData = await fetchChartData()
  
  if (rechargeChartInstance) rechargeChartInstance.destroy()
  if (consumeChartInstance) consumeChartInstance.destroy()
  
  const labels = chartData.dates || []
  const rechargeData = chartData.recharge_amounts || []
  const consumeData = chartData.consumption_amounts || []
  
  if (rechargeChart.value) {
    rechargeChartInstance = createChart(rechargeChart.value, labels, rechargeData, '充值', '#10b981')
  }
  
  if (consumeChart.value) {
    consumeChartInstance = createChart(consumeChart.value, labels, consumeData, '消费', '#f97316')
  }
}

async function fetchRecentActivities() {
  try {
    const response = await api.get('/dashboard/recent-activities')
    const payload = response?.data ?? response ?? []
    const list = Array.isArray(payload) ? payload : (Array.isArray(payload?.data) ? payload.data : [])
    recentActivities.value = list.map(normalizeActivityItem)
  } catch (error) {
    console.error('Failed to fetch activities:', error)
    recentActivities.value = []
  }
}

function getTypeBadgeClass(type) {
  const classes = {
    recharge: 'bg-green-100 text-green-800',
    consumption: 'bg-orange-100 text-orange-800',
    login: 'bg-blue-100 text-blue-800',
    password_change: 'bg-red-100 text-red-800'
  }
  return classes[type] || 'bg-gray-100 text-gray-800'
}

function getTypeLabel(type) {
  const map = {
    recharge: '充值',
    consumption: '消费',
    login: '登录',
    password_change: '修改密码'
  }
  return map[type] || '其他'
}

function toMoneyText(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '0.00'
  return amount.toFixed(2)
}

function formatActivityTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

function normalizeActivityDescription(type, rawDescription) {
  const description = String(rawDescription || '').trim()
  if (!description) return '-'

  const rechargeMatch = description.match(/^Customer\s+(.+?)\s+\(([^)]+)\)\s+recharge\s+([0-9]+(?:\.[0-9]+)?)\s+bonus\s+([0-9]+(?:\.[0-9]+)?)$/i)
  if (rechargeMatch) {
    const [, name, customerId, amount, bonus] = rechargeMatch
    return `客户 ${name}（${customerId}）充值 ¥${toMoneyText(amount)}，赠送 ¥${toMoneyText(bonus)}`
  }

  const timedConsumeMatch = description.match(/^Customer\s+(.+?)\s+\(([^)]+)\)\s+timed\s+consumption\s+([0-9]+(?:\.[0-9]+)?):\s*(.*)$/i)
  if (timedConsumeMatch) {
    const [, name, customerId, amount, detail] = timedConsumeMatch
    const detailText = String(detail || '').trim() || '无'
    return `客户 ${name}（${customerId}）计时消费 ¥${toMoneyText(amount)}：${detailText}`
  }

  const consumeMatch = description.match(/^Customer\s+(.+?)\s+\(([^)]+)\)\s+consume\s+([0-9]+(?:\.[0-9]+)?):\s*(.*)$/i)
  if (consumeMatch) {
    const [, name, customerId, amount, detail] = consumeMatch
    const detailText = String(detail || '').trim() || '无'
    return `客户 ${name}（${customerId}）消费 ¥${toMoneyText(amount)}：${detailText}`
  }

  const loginMatch = description.match(/^User\s+(.+?)\s+(?:login(?:ed)?|logged\s+in)(?:\s+success(?:fully)?)?$/i)
  if (loginMatch) {
    return `用户 ${loginMatch[1]} 登录成功`
  }

  const passwordMatch = description.match(/^User\s+(.+?)\s+(?:change|changed)\s+password$/i)
  if (passwordMatch) {
    return `用户 ${passwordMatch[1]} 修改了密码`
  }

  if (/[\u4e00-\u9fa5]/.test(description)) {
    return description
  }

  if (type === 'recharge') return '完成充值操作'
  if (type === 'consumption') return '完成消费操作'
  if (type === 'login') return '用户登录'
  if (type === 'password_change') return '修改密码'

  // If we don't recognize a pattern, keep original text.
  return description
}

function normalizeActivityItem(item = {}) {
  const type = String(item.type || '').trim()
  return {
    ...item,
    type,
    typeLabel: getTypeLabel(type),
    displayDescription: normalizeActivityDescription(type, item.description),
    displayTime: formatActivityTime(item.timestamp)
  }
}

async function refreshData() {
  isLoading.value = true
  try {
    await Promise.all([fetchStats(), initCharts(), fetchRecentActivities()])
    updateTime()
  } finally {
    isLoading.value = false
  }
}

watch(timeRange, () => initCharts())

onMounted(() => refreshData())

onUnmounted(() => {
  if (rechargeChartInstance) rechargeChartInstance.destroy()
  if (consumeChartInstance) consumeChartInstance.destroy()
})
</script>

<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">仪表盘</h1>
        <p v-if="lastUpdateTime" class="text-sm text-gray-500 mt-1">最后更新: {{ lastUpdateTime }}</p>
      </div>
      <button
        @click="refreshData"
        :disabled="isLoading"
        :class="[
          'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-200',
          isLoading ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'bg-[#1e40af] text-white hover:bg-[#1e3a8a] hover:shadow-lg'
        ]"
      >
        <svg :class="['h-5 w-5', isLoading && 'animate-spin']" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        刷新
      </button>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 mb-6">
      <div v-for="card in statsCards" :key="card.id" class="bg-white rounded-xl shadow-sm hover:shadow-md transition-shadow duration-200 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-gray-500 mb-1">{{ card.title }}</p>
            <p class="text-2xl font-bold text-gray-900">
              {{ card.isAmount ? formatAmount(card.value) : formatNumber(card.value) }}
            </p>
          </div>
          <div :class="[card.bgColor, 'p-3 rounded-lg text-white']" v-html="getIcon(card.icon)"></div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
      <div class="bg-white rounded-xl shadow-sm p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-gray-900">充值趋势</h2>
          <div class="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button v-for="days in ['7', '30', '90']" :key="days" @click="timeRange = days"
              :class="['px-3 py-1 text-sm font-medium rounded-md transition-all duration-200', timeRange === days ? 'bg-white text-[#1e40af] shadow-sm' : 'text-gray-600 hover:text-gray-900']">
              {{ days }}d
            </button>
          </div>
        </div>
        <div class="h-64"><canvas ref="rechargeChart"></canvas></div>
      </div>

      <div class="bg-white rounded-xl shadow-sm p-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-gray-900">消费趋势</h2>
          <div class="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button v-for="days in ['7', '30', '90']" :key="days" @click="timeRange = days"
              :class="['px-3 py-1 text-sm font-medium rounded-md transition-all duration-200', timeRange === days ? 'bg-white text-[#1e40af] shadow-sm' : 'text-gray-600 hover:text-gray-900']">
              {{ days }}d
            </button>
          </div>
        </div>
        <div class="h-64"><canvas ref="consumeChart"></canvas></div>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-900">最近活动</h2>
        <span class="text-sm text-gray-500">最近10条记录</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-200">
              <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">时间</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">类型</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">描述</th>
              <th class="text-left py-3 px-4 text-sm font-medium text-gray-500">操作员</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="activity in recentActivities" :key="activity.id" class="border-b border-gray-100 hover:bg-gray-50 transition-colors">
              <td class="py-3 px-4 text-sm text-gray-600">{{ activity.displayTime }}</td>
              <td class="py-3 px-4">
                <span :class="['px-2 py-1 text-xs font-medium rounded-full', getTypeBadgeClass(activity.type)]">
                  {{ activity.typeLabel }}
                </span>
              </td>
              <td class="py-3 px-4 text-sm text-gray-600">{{ activity.displayDescription }}</td>
              <td class="py-3 px-4 text-sm text-gray-600">{{ activity.operator || '-' }}</td>
            </tr>
            <tr v-if="recentActivities.length === 0">
              <td colspan="4" class="py-8 text-center text-gray-500">暂无最近活动</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

