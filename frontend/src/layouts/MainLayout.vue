<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'
import { timerApi, authApi } from '@/api'
import { useBackdropClose } from '@/utils/modalBackdrop'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { onBackdropMouseDown, onBackdropMouseUp } = useBackdropClose()

const isCollapsed = ref(false)
const activeTimersCount = ref(0)
const showUserMenu = ref(false)
const userMenuRef = ref(null)
const currentGlobalFont = ref('default')
const showChangePasswordModal = ref(false)
const showWarningLeadModal = ref(false)
const passwordLoading = ref(false)
const passwordSuccess = ref('')
const passwordError = ref('')
const warningLeadDraftMinute = ref(10)
const warningLeadError = ref('')
const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const passwordErrors = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})
const GLOBAL_FONT_STORAGE_KEY = 'global_font_preference_v1'
const WARNING_STORAGE_KEY = 'active_timer_warning_v1'
const WARNING_LEAD_STORAGE_KEY = 'timer_warning_lead_seconds_v1'
const LEGACY_WARNING_LEAD_STORAGE_KEY = 'timer_warning_lead_minutes_v1'
const DEFAULT_WARNING_LEAD_SECONDS = 600
const TABLE_NO_PATTERN = /^([A-HJ-NP-Za-hj-np-z])桌([1-9]|1[0-9]|20)号$/
const PACKAGE_TOTAL_MINUTES = {
  limited1h: 60,
  limited2h: 120
}

const globalWarningQueue = ref([])
const activeGlobalWarning = ref(null)
const globalTimers = ref([])
const warnedTimerIds = ref(loadWarnedTimerIds())
const reminderLeadSeconds = ref(loadWarningLeadSeconds())
const pendingWarningTimerIds = new Set()
let timerWarningPoller = null
let timerWarningTicker = null
let timerWarningRefreshing = false
const showWarningDebugPanel = ref(false)
const isAdmin = computed(() => String(authStore.user?.role || '').toLowerCase() === 'admin')
const currentUserLabel = computed(() => {
  const username = String(authStore.user?.username || '').trim()
  const roleLabel = isAdmin.value ? '管理员' : '员工'
  return username ? `${username}（${roleLabel}）` : roleLabel
})

function normalizeTableNo(rawValue) {
  const raw = String(rawValue || '').trim()
  const matched = TABLE_NO_PATTERN.exec(raw)
  if (!matched) return raw
  return `${matched[1].toUpperCase()}桌${matched[2]}号`
}

function toSeatCode(rawTableNo) {
  const normalized = normalizeTableNo(rawTableNo)
  const matched = TABLE_NO_PATTERN.exec(normalized)
  if (!matched) return ''
  return `${matched[1].toLowerCase()}${matched[2]}`
}

function getTimerExtraTableNos(timer) {
  const list = []
  const seen = new Set()
  const pushSeat = (rawSeatNo) => {
    const normalized = normalizeTableNo(rawSeatNo)
    if (!TABLE_NO_PATTERN.test(normalized)) return
    if (seen.has(normalized)) return
    seen.add(normalized)
    list.push(normalized)
  }

  if (Array.isArray(timer?.extraTableNos)) {
    timer.extraTableNos.forEach((item) => pushSeat(item))
  }
  pushSeat(timer?.secondTableNo)
  return list
}

function getTimerOccupiedTableNos(timer) {
  const seats = []
  const first = normalizeTableNo(timer?.tableNo)
  if (TABLE_NO_PATTERN.test(first)) {
    seats.push(first)
  }
  const seen = new Set(seats)
  getTimerExtraTableNos(timer).forEach((seatNo) => {
    if (seen.has(seatNo)) return
    seen.add(seatNo)
    seats.push(seatNo)
  })
  return seats
}

function loadWarnedTimerIds() {
  if (typeof window === 'undefined') return new Set()
  try {
    const raw = window.localStorage.getItem(WARNING_STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.map((item) => String(item || '').trim()).filter(Boolean))
  } catch {
    return new Set()
  }
}

function normalizeWarningLeadSeconds(value) {
  const parsed = Number.parseInt(String(value ?? ''), 10)
  if (!Number.isFinite(parsed)) return DEFAULT_WARNING_LEAD_SECONDS
  return Math.max(1, Math.min(7200, parsed))
}

function splitLeadSeconds(value) {
  const seconds = normalizeWarningLeadSeconds(value)
  return {
    minute: Math.floor(seconds / 60),
    second: seconds % 60
  }
}

function formatLeadText(value) {
  const seconds = normalizeWarningLeadSeconds(value)
  const minute = Math.max(1, Math.floor(seconds / 60))
  return `${minute}分钟`
}

function loadWarningLeadSeconds() {
  if (typeof window === 'undefined') return DEFAULT_WARNING_LEAD_SECONDS
  try {
    const raw = window.localStorage.getItem(WARNING_LEAD_STORAGE_KEY)
    if (raw !== null) return normalizeWarningLeadSeconds(raw)

    const legacy = window.localStorage.getItem(LEGACY_WARNING_LEAD_STORAGE_KEY)
    if (legacy !== null) return normalizeWarningLeadSeconds(Number(legacy) * 60)
    return DEFAULT_WARNING_LEAD_SECONDS
  } catch {
    return DEFAULT_WARNING_LEAD_SECONDS
  }
}

function persistWarningLeadSeconds() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(WARNING_LEAD_STORAGE_KEY, String(reminderLeadSeconds.value))
    window.localStorage.removeItem(LEGACY_WARNING_LEAD_STORAGE_KEY)
  } catch (error) {
    console.error('保存提醒提前秒数失败:', error)
  }
}

function openWarningLeadSetting() {
  closeUserMenu()
  const draft = splitLeadSeconds(reminderLeadSeconds.value)
  warningLeadDraftMinute.value = Math.max(1, draft.minute)
  warningLeadError.value = ''
  showWarningLeadModal.value = true
}

function closeWarningLeadModal() {
  showWarningLeadModal.value = false
  warningLeadError.value = ''
}

function setWarningLeadPreset(value) {
  const minute = Number.parseInt(String(value ?? ''), 10)
  warningLeadDraftMinute.value = Number.isFinite(minute) ? Math.max(1, Math.min(120, minute)) : 10
  warningLeadError.value = ''
}

function adjustWarningLead(delta) {
  const base = Number(warningLeadDraftMinute.value) || 10
  setWarningLeadPreset(base + delta)
}

function applyWarningLeadSetting() {
  const minute = Number.parseInt(String(warningLeadDraftMinute.value ?? ''), 10)

  if (!Number.isFinite(minute) || minute < 1 || minute > 120) {
    warningLeadError.value = '分钟请输入 1 到 120。'
    return
  }

  const totalSeconds = minute * 60
  if (totalSeconds < 1 || totalSeconds > 7200) {
    warningLeadError.value = '提醒提前时间需在 1 到 120 分钟内。'
    return
  }

  reminderLeadSeconds.value = totalSeconds
  persistWarningLeadSeconds()
  resetActiveTimerWarningState()
  evaluateGlobalWarnings(globalTimers.value, Date.now())
  closeWarningLeadModal()
}

function persistWarnedTimerIds() {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(WARNING_STORAGE_KEY, JSON.stringify(Array.from(warnedTimerIds.value)))
  } catch (error) {
    console.error('保存全局计时提醒状态失败:', error)
  }
}

function parseTimerNotes(rawNotes) {
  const createDefault = () => ({
    packagePlan: '',
    extraTableNos: [],
    secondTableNo: '',
    timing: {
      elapsedSeconds: 0,
      resumedAt: ''
    }
  })
  const normalizeExtraSeatList = (rawExtraTableNos, legacySecondTableNo = '') => {
    const source = Array.isArray(rawExtraTableNos) ? rawExtraTableNos : []
    const list = []
    const seen = new Set()
    const pushSeat = (rawSeatNo) => {
      const seatNo = normalizeTableNo(rawSeatNo)
      if (!TABLE_NO_PATTERN.test(seatNo)) return
      if (seen.has(seatNo)) return
      seen.add(seatNo)
      list.push(seatNo)
    }
    source.forEach((item) => pushSeat(item))
    if (list.length === 0 && legacySecondTableNo) {
      pushSeat(legacySecondTableNo)
    }
    return list
  }

  if (!rawNotes) {
    return createDefault()
  }

  try {
    const parsed = JSON.parse(rawNotes)
    if (!parsed || typeof parsed !== 'object') throw new Error('invalid notes')
    const extraTableNos = normalizeExtraSeatList(parsed.extraTableNos, parsed.secondTableNo)
    return {
      packagePlan: String(parsed.packagePlan || '').trim(),
      extraTableNos,
      secondTableNo: extraTableNos[0] || '',
      timing: {
        elapsedSeconds: Math.max(0, Math.floor(Number(parsed.timing?.elapsedSeconds) || 0)),
        resumedAt: String(parsed.timing?.resumedAt || '')
      }
    }
  } catch {
    return createDefault()
  }
}

function inferPackagePlan(timerType, parsedPlan) {
  const normalizedPlan = String(parsedPlan || '').trim()
  if (normalizedPlan) return normalizedPlan
  const normalizedType = String(timerType || '').trim()
  if (normalizedType === 'limited') return 'limited1h'
  return ''
}

function unwrapData(payload, fallback = null) {
  if (payload && typeof payload === 'object' && Object.prototype.hasOwnProperty.call(payload, 'data')) {
    return payload.data
  }
  return payload ?? fallback
}

function resolveTimerList(payload) {
  const unwrapped = unwrapData(payload, [])
  return Array.isArray(unwrapped) ? unwrapped : []
}

function toServerDateTimestamp(dateTime) {
  if (!dateTime) return Number.NaN
  if (typeof dateTime !== 'string') return new Date(dateTime).getTime()
  const hasTimezone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(dateTime)
  const normalized = hasTimezone ? dateTime : `${dateTime}Z`
  return new Date(normalized).getTime()
}

function getElapsedSeconds(timer, timestamp = Date.now()) {
  const startMs = toServerDateTimestamp(timer.startTime)
  if (!Number.isFinite(startMs)) return 0

  const baseElapsedSeconds = Math.max(0, Math.floor(Number(timer.timing?.elapsedSeconds) || 0))
  const resumedAtMs = toServerDateTimestamp(timer.timing?.resumedAt)

  if (timer.status === 'paused') {
    if (Number.isFinite(resumedAtMs)) {
      const pausedElapsed = Math.max(0, Math.floor((resumedAtMs - startMs) / 1000))
      return Math.max(baseElapsedSeconds, pausedElapsed)
    }
    return baseElapsedSeconds
  }

  if (Number.isFinite(resumedAtMs)) {
    const sinceResume = Math.max(0, Math.floor((timestamp - resumedAtMs) / 1000))
    return Math.max(0, baseElapsedSeconds + sinceResume)
  }

  return Math.max(0, Math.floor((timestamp - startMs) / 1000))
}

function getElapsedMinutes(timer, timestamp = Date.now()) {
  return Math.floor(getElapsedSeconds(timer, timestamp) / 60)
}

function formatRemainingText(minutes) {
  const safeMinutes = Math.max(0, Math.floor(Number(minutes) || 0))
  return `${safeMinutes}分钟`
}

function formatRemainingSpeech(minutes) {
  const safeMinutes = Math.max(0, Math.floor(Number(minutes) || 0))
  return `${safeMinutes}分钟`
}

function resolvePreferredFemaleVoice() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices()
  if (!Array.isArray(voices) || voices.length === 0) return null
  const zhVoices = voices.filter((voice) => String(voice?.lang || '').toLowerCase().startsWith('zh'))
  if (zhVoices.length === 0) return voices[0] || null
  const matched = zhVoices.find((voice) => {
    const name = String(voice?.name || '').toLowerCase()
    return name.includes('xiaoxiao') || name.includes('xiaoyi') || name.includes('female') || String(voice?.name || '').includes('女')
  })
  return matched || zhVoices[0] || voices[0] || null
}

function playLeadTone() {
  if (typeof window === 'undefined') return
  try {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext
    if (!AudioContextCtor) return

    const ctx = new AudioContextCtor()
    const playBeep = (startAt, frequency = 880) => {
      const oscillator = ctx.createOscillator()
      const gainNode = ctx.createGain()
      oscillator.type = 'sine'
      oscillator.frequency.value = frequency
      gainNode.gain.setValueAtTime(0.0001, startAt)
      gainNode.gain.exponentialRampToValueAtTime(0.2, startAt + 0.02)
      gainNode.gain.exponentialRampToValueAtTime(0.0001, startAt + 0.22)
      oscillator.connect(gainNode)
      gainNode.connect(ctx.destination)
      oscillator.start(startAt)
      oscillator.stop(startAt + 0.22)
    }
    playBeep(ctx.currentTime, 880)
    playBeep(ctx.currentTime + 0.32, 1046.5)
    window.setTimeout(() => {
      ctx.close().catch(() => {})
    }, 700)
  } catch (error) {
    console.error('提示音播放失败:', error)
  }
}

function speakWarningText(text) {
  if (typeof window === 'undefined') return
  const synth = window.speechSynthesis
  if (!synth || typeof window.SpeechSynthesisUtterance !== 'function') return
  try {
    synth.cancel()
    const utterance = new window.SpeechSynthesisUtterance(String(text || ''))
    utterance.lang = 'zh-CN'
    utterance.rate = 0.94
    utterance.pitch = 1.12
    utterance.volume = 1
    const voice = resolvePreferredFemaleVoice()
    if (voice) {
      utterance.voice = voice
      utterance.lang = voice.lang || 'zh-CN'
    }
    playLeadTone()
    window.setTimeout(() => {
      synth.speak(utterance)
    }, 620)
  } catch (error) {
    console.error('全局语音播报失败:', error)
  }
}

function requestNotificationPermission() {
  if (typeof window === 'undefined' || typeof window.Notification === 'undefined') return
  if (window.Notification.permission !== 'default') return
  window.Notification.requestPermission().catch((error) => {
    console.error('请求通知权限失败:', error)
  })
}

function notifyWarning(warning) {
  if (typeof window === 'undefined' || typeof window.Notification === 'undefined') return
  if (window.Notification.permission !== 'granted') return
  try {
    const notification = new window.Notification('计时剩余提醒', {
      body: `${warning.tableNo || '-'} 剩余 ${warning.remainingText}`,
      tag: `timer-warning-${warning.timerId}`,
      renotify: true
    })
    notification.onclick = () => {
      window.focus()
      router.push('/active-timers')
      notification.close()
    }
  } catch (error) {
    console.error('发送系统通知失败:', error)
  }
}

function markTimerWarningDone(timerId) {
  const normalized = String(timerId || '').trim()
  if (!normalized) return
  warnedTimerIds.value.add(normalized)
  pendingWarningTimerIds.delete(normalized)
  persistWarnedTimerIds()
}

function resetActiveTimerWarningState() {
  const activeIds = new Set(
    globalTimers.value
      .filter((timer) => timer.status === 'active')
      .map((timer) => String(timer.id || '').trim())
      .filter(Boolean)
  )

  if (activeIds.size > 0) {
    warnedTimerIds.value = new Set(
      Array.from(warnedTimerIds.value).filter((id) => !activeIds.has(id))
    )
  }

  pendingWarningTimerIds.clear()
  globalWarningQueue.value = []
  activeGlobalWarning.value = null
  persistWarnedTimerIds()
}

function showNextGlobalWarning() {
  if (activeGlobalWarning.value || globalWarningQueue.value.length === 0) return
  const nextWarning = globalWarningQueue.value.shift()
  if (!nextWarning) return

  speakWarningText(nextWarning.speechText)
  notifyWarning(nextWarning)

  activeGlobalWarning.value = nextWarning
}

function dismissGlobalWarning() {
  if (!activeGlobalWarning.value) return
  markTimerWarningDone(activeGlobalWarning.value.timerId)
  activeGlobalWarning.value = null
  showNextGlobalWarning()
}

function buildWarningFromTimer(timer, timestamp = Date.now()) {
  const totalMinutes = PACKAGE_TOTAL_MINUTES[timer.packagePlan]
  if (!Number.isFinite(totalMinutes)) return null

  const leadMinutes = Math.max(1, Math.floor(reminderLeadSeconds.value / 60))
  const triggerMinutes = Math.max(0, totalMinutes - leadMinutes)

  const elapsedMinutes = getElapsedMinutes(timer, timestamp)
  if (elapsedMinutes < triggerMinutes) return null

  const filteredSeats = getTimerOccupiedTableNos(timer)
    .map((seatNo) => toSeatCode(seatNo))
    .filter(Boolean)
  const speechDesk = filteredSeats.length > 0 ? filteredSeats.join('、') : (timer.customerName || `客户${timer.customerId || ''}`)
  const tableNoDisplay = filteredSeats.length > 0 ? filteredSeats.join('、').toUpperCase() : normalizeTableNo(timer.tableNo)
  const remainingMinutes = Math.max(0, totalMinutes - elapsedMinutes)
  const remainingText = formatRemainingText(remainingMinutes)
  const remainingSpeech = formatRemainingSpeech(remainingMinutes)

  return {
    timerId: timer.id,
    tableNo: tableNoDisplay || '-',
    customerName: timer.customerName || '',
    packagePlan: timer.packagePlan,
    remainingMinutes,
    remainingText,
    speechText: `${speechDesk}剩余${remainingSpeech}`,
    triggeredAt: timestamp
  }
}

function queueGlobalTimerWarning(timer, timestamp = Date.now()) {
  const timerId = String(timer?.id || '').trim()
  if (!timerId) return
  if (warnedTimerIds.value.has(timerId) || pendingWarningTimerIds.has(timerId)) return
  const warning = buildWarningFromTimer(timer, timestamp)
  if (!warning) return
  pendingWarningTimerIds.add(timerId)
  globalWarningQueue.value.push(warning)
  showNextGlobalWarning()
}

function evaluateGlobalWarnings(timerList, timestamp = Date.now()) {
  timerList.forEach((timer) => {
    if (timer.status !== 'active') return
    queueGlobalTimerWarning(timer, timestamp)
  })
}

function normalizeTimer(timer = {}) {
  const notes = parseTimerNotes(timer.notes)
  const timerType = String(timer.timer_type || timer.timerType || 'limited').trim()
  return {
    id: String(timer.id || '').trim(),
    status: String(timer.status || 'active'),
    timerType,
    customerId: String(timer.customer_id || timer.customerId || '').trim(),
    customerName: String(timer.customer?.name || '').trim(),
    tableNo: normalizeTableNo(timer.table_no || timer.tableNo || ''),
    extraTableNos: Array.isArray(notes.extraTableNos) ? notes.extraTableNos : [],
    secondTableNo: normalizeTableNo(notes.secondTableNo),
    packagePlan: inferPackagePlan(timerType, notes.packagePlan),
    startTime: timer.start_time || timer.startTime || null,
    timing: notes.timing
  }
}

async function refreshGlobalTimerWarnings() {
  if (timerWarningRefreshing) return
  timerWarningRefreshing = true
  try {
    const response = await timerApi.getActiveTimers()
    const list = resolveTimerList(response)
    activeTimersCount.value = list.length
    globalTimers.value = list.map(normalizeTimer)
    evaluateGlobalWarnings(globalTimers.value)
  } catch (error) {
    console.error('Failed to refresh global timer warnings:', error)
    activeTimersCount.value = 0
    globalTimers.value = []
  } finally {
    timerWarningRefreshing = false
  }
}

function startTimerWarningPoller() {
  stopTimerWarningPoller()
  refreshGlobalTimerWarnings()
  timerWarningPoller = window.setInterval(() => {
    refreshGlobalTimerWarnings()
  }, 5000)
  timerWarningTicker = window.setInterval(() => {
    evaluateGlobalWarnings(globalTimers.value, Date.now())
  }, 1000)
}

function stopTimerWarningPoller() {
  if (!timerWarningPoller) return
  window.clearInterval(timerWarningPoller)
  timerWarningPoller = null
  if (timerWarningTicker) {
    window.clearInterval(timerWarningTicker)
    timerWarningTicker = null
  }
}

function getTimerTriggerDebug(timer, timestamp = Date.now()) {
  const totalMinutes = PACKAGE_TOTAL_MINUTES[timer.packagePlan]
  if (!Number.isFinite(totalMinutes)) {
    return {
      totalMinutes: 0,
      triggerMinutes: 0,
      elapsedMinutes: getElapsedMinutes(timer, timestamp),
      remainingMinutes: 0,
      canTrigger: false
    }
  }

  const leadMinutes = Math.max(1, Math.floor(reminderLeadSeconds.value / 60))
  const triggerMinutes = Math.max(0, totalMinutes - leadMinutes)
  const elapsedMinutes = getElapsedMinutes(timer, timestamp)
  const remainingMinutes = Math.max(0, totalMinutes - elapsedMinutes)
  return {
    totalMinutes,
    triggerMinutes,
    elapsedMinutes,
    remainingMinutes,
    canTrigger: elapsedMinutes >= triggerMinutes
  }
}

const warningDebugRows = computed(() => {
  const now = Date.now()
  return globalTimers.value
    .filter((timer) => timer.status === 'active')
    .map((timer) => {
      const debug = getTimerTriggerDebug(timer, now)
      const id = String(timer.id || '')
      return {
        id,
        tableNo: timer.tableNo || '-',
        packagePlan: timer.packagePlan || '(空)',
        elapsedText: formatRemainingText(debug.elapsedMinutes),
        remainingText: formatRemainingText(debug.remainingMinutes),
        triggerText: formatRemainingText(debug.triggerMinutes),
        canTrigger: debug.canTrigger ? '是' : '否',
        warned: warnedTimerIds.value.has(id) ? '是' : '否',
        pending: pendingWarningTimerIds.has(id) ? '是' : '否'
      }
    })
})

const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value
}

const closeUserMenu = () => {
  showUserMenu.value = false
}

const handleDocumentClick = (event) => {
  if (!showUserMenu.value) return
  const root = userMenuRef.value
  if (!root) return
  if (!root.contains(event.target)) {
    closeUserMenu()
  }
}

const fetchActiveTimersCount = async () => {
  try {
    const response = await timerApi.getActiveTimers()
    const list = resolveTimerList(response)
    activeTimersCount.value = list.length
  } catch (error) {
    console.error('Failed to fetch active timers count:', error)
    activeTimersCount.value = 0
  }
}

onMounted(() => {
  window.__STUDIO_GLOBAL_TIMER_WARNING_CENTER__ = true
  const savedFont = localStorage.getItem(GLOBAL_FONT_STORAGE_KEY)
  currentGlobalFont.value = savedFont === 'heiti' ? 'heiti' : 'default'
  document.documentElement.setAttribute('data-global-font', currentGlobalFont.value)
  setTimeout(() => {
    fetchActiveTimersCount()
    startTimerWarningPoller()
  }, 100)
  document.addEventListener('click', handleDocumentClick)
  window.addEventListener('pointerdown', requestNotificationPermission, { once: true, capture: true })
  window.addEventListener('keydown', requestNotificationPermission, { once: true, capture: true })
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  window.__STUDIO_GLOBAL_TIMER_WARNING_CENTER__ = false
  document.removeEventListener('click', handleDocumentClick)
  stopTimerWarningPoller()
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

function handleVisibilityChange() {
  if (typeof document === 'undefined') return
  if (!document.hidden) {
    evaluateGlobalWarnings(globalTimers.value, Date.now())
    showNextGlobalWarning()
  }
}

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

const toggleGlobalFont = () => {
  currentGlobalFont.value = currentGlobalFont.value === 'default' ? 'heiti' : 'default'
  document.documentElement.setAttribute('data-global-font', currentGlobalFont.value)
  localStorage.setItem(GLOBAL_FONT_STORAGE_KEY, currentGlobalFont.value)
}

const menuItems = computed(() => {
  const items = [
    {
      title: '运营概况',
      icon: 'dashboard',
      path: '/dashboard',
      group: 'main'
    },
    {
      title: '正在计时',
      icon: 'timer',
      path: '/active-timers',
      badge: activeTimersCount.value,
      group: 'main'
    },
    {
      title: '客户管理',
      icon: 'users',
      path: '/customers',
      group: 'member'
    },
    {
      title: '员工管理',
      icon: 'user',
      path: '/employees',
      group: 'member'
    },
    {
      title: '交易记录',
      icon: 'receipt',
      path: '/transactions',
      group: 'operation'
    },
    {
      title: '活动管理',
      icon: 'calendar',
      path: '/activities',
      group: 'operation'
    },
    {
      title: '计费规则',
      icon: 'currency',
      path: '/billing-rules',
      group: 'operation'
    },
    {
      title: '杂项计费',
      icon: 'tag',
      path: '/misc-billing',
      group: 'operation'
    },
    {
      title: '豆仓管理',
      icon: 'warehouse',
      path: '/bead-inventory',
      group: 'operation'
    },
  ]

  if (isAdmin.value) {
    items.push({
      title: '系统日志',
      icon: 'receipt',
      path: '/system-logs',
      group: 'system'
    })
    items.push({
      title: '数据管理',
      icon: 'settings',
      path: '/settings',
      group: 'system'
    })
  }

  return items
})

const groupedMenuItems = computed(() => {
  const groups = {
    main: { title: '主要功能', items: [] },
    member: { title: '人员管理', items: [] },
    operation: { title: '运营管理', items: [] },
    system: { title: '系统', items: [] }
  }
  
  menuItems.value.forEach(item => {
    if (groups[item.group]) {
      groups[item.group].items.push(item)
    }
  })
  
  return groups
})

const isActive = (path) => {
  return route.path === path
}

const navigateTo = (path) => {
  router.push(path)
}

const handleLogout = async () => {
  closeUserMenu()
  try {
    await authApi.logout()
  } catch (error) {
    console.warn('Logout API failed:', error)
  }
  authStore.logout()
  router.push('/login')
}

const resetPasswordForm = () => {
  passwordForm.currentPassword = ''
  passwordForm.newPassword = ''
  passwordForm.confirmPassword = ''
  passwordErrors.currentPassword = ''
  passwordErrors.newPassword = ''
  passwordErrors.confirmPassword = ''
  passwordSuccess.value = ''
  passwordError.value = ''
}

const openChangePasswordModal = () => {
  closeUserMenu()
  resetPasswordForm()
  showChangePasswordModal.value = true
}

const closeChangePasswordModal = () => {
  showChangePasswordModal.value = false
  resetPasswordForm()
}

const validatePasswordForm = () => {
  let isValid = true
  passwordErrors.currentPassword = ''
  passwordErrors.newPassword = ''
  passwordErrors.confirmPassword = ''
  passwordSuccess.value = ''
  passwordError.value = ''

  if (!passwordForm.currentPassword) {
    passwordErrors.currentPassword = '请输入当前密码'
    isValid = false
  }

  if (!passwordForm.newPassword) {
    passwordErrors.newPassword = '请输入新密码'
    isValid = false
  } else if (passwordForm.newPassword.length < 6) {
    passwordErrors.newPassword = '密码至少需要6个字符'
    isValid = false
  }

  if (!passwordForm.confirmPassword) {
    passwordErrors.confirmPassword = '请确认新密码'
    isValid = false
  } else if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    passwordErrors.confirmPassword = '两次输入的密码不一致'
    isValid = false
  }

  return isValid
}

const submitPasswordChange = async () => {
  if (!validatePasswordForm()) return

  passwordLoading.value = true
  try {
    await authApi.changePassword({
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword
    })
    passwordSuccess.value = '密码修改成功'
    passwordForm.currentPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch (error) {
    console.error('Failed to change password:', error)
    passwordError.value = error.response?.data?.message || '密码修改失败'
  } finally {
    passwordLoading.value = false
  }
}

const getIcon = (iconName) => {
  const icons = {
    dashboard: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>`,
    timer: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>`,
    users: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>`,
    user: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a2 2 0 012-2h12a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V5z" />
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.5 10a2.5 2.5 0 115 0 2.5 2.5 0 01-5 0z" />
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16a4 4 0 018 0M15.5 8H18M15.5 11H18" />
    </svg>`,
    receipt: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2zM10 8.5a.5.5 0 11-1 0 .5.5 0 011 0zm5 5a.5.5 0 11-1 0 .5.5 0 011 0z" />
    </svg>`,
    calendar: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>`,
    currency: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>`,
    tag: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M3 11l7.586 7.586a2 2 0 002.828 0L21 11.999a2 2 0 000-2.828L13.414 1.586A2 2 0 0012 1H5a2 2 0 00-2 2v8z" />
    </svg>`,
    warehouse: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10l9-7 9 7M5 10v9a1 1 0 001 1h12a1 1 0 001-1v-9M9 21V12h6v9" />
    </svg>`,
    settings: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>`
  }
  return icons[iconName] || ''
}
</script>

<template>
  <div class="min-h-screen bg-gray-100">
    <nav class="fixed top-0 left-0 right-0 h-16 bg-white shadow-sm z-40 flex items-center justify-between px-4">
      <div class="flex items-center space-x-4">
        <button
          @click="toggleSidebar"
          class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 class="text-xl font-semibold text-gray-800">织雾拼豆管理系统</h1>
      </div>
      
      <div class="flex items-center space-x-4">
        <button
          @click="toggleGlobalFont"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          :title="`当前字体：${currentGlobalFont === 'heiti' ? '黑体' : '默认'}`"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m-4 4h10" />
          </svg>
          <span>字体：{{ currentGlobalFont === 'heiti' ? '黑体' : '默认' }}</span>
        </button>
        <button
          @click="openWarningLeadSetting"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          :title="`当前提醒提前：${formatLeadText(reminderLeadSeconds)}`"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l2.5 2.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>提醒：{{ formatLeadText(reminderLeadSeconds) }}</span>
        </button>
        <button
          @click="showWarningDebugPanel = !showWarningDebugPanel"
          class="inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4V7M4 5h16M4 19h16" />
          </svg>
          <span>{{ showWarningDebugPanel ? '关闭调试' : '提醒调试' }}</span>
        </button>

        <div ref="userMenuRef" class="relative">
          <button
            @click.stop="toggleUserMenu"
            class="flex items-center space-x-2 p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <div class="h-8 w-8 bg-blue-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm font-medium">A</span>
            </div>
            <span class="text-gray-700">{{ currentUserLabel }}</span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              :class="['h-4 w-4 text-gray-500 transition-transform', showUserMenu ? 'rotate-180' : 'rotate-0']"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          
          <div v-if="showUserMenu" class="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg py-1 z-50">
            <button
              @click="openChangePasswordModal"
              class="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 transition-colors flex items-center space-x-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 11c1.657 0 3-1.343 3-3V7a3 3 0 10-6 0v1c0 1.657 1.343 3 3 3zm6 9H6a2 2 0 01-2-2v-5a2 2 0 012-2h12a2 2 0 012 2v5a2 2 0 01-2 2z" />
              </svg>
              <span>修改密码</span>
            </button>
            <button
              @click="handleLogout"
              class="w-full text-left px-4 py-2 text-gray-700 hover:bg-gray-100 transition-colors flex items-center space-x-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span>退出登录</span>
            </button>
          </div>
        </div>
      </div>
    </nav>

    <aside
      :class="[
        'fixed top-16 left-0 h-[calc(100vh-4rem)] bg-white shadow-lg transition-all duration-300 z-30 overflow-y-auto',
        isCollapsed ? 'w-16' : 'w-64'
      ]"
    >
      <div class="py-4">
        <template v-for="(group, key) in groupedMenuItems" :key="key">
          <div v-if="group.items.length > 0">
            <div
              class="transition-all duration-300 ease-in-out overflow-hidden whitespace-nowrap"
              :class="[
                isCollapsed ? 'h-0 opacity-0 my-2 border-t border-gray-200' : 'h-8 px-4 py-2 opacity-100'
              ]"
            >
              <span v-if="!isCollapsed" class="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                {{ group.title }}
              </span>
            </div>
            
            <nav class="space-y-1 px-2">
              <button
                v-for="item in group.items"
                :key="item.path"
                @click="navigateTo(item.path)"
                :class="[
                  'w-full flex items-center rounded-lg transition-all duration-300 relative overflow-hidden',
                  isCollapsed ? 'px-0 py-3 justify-center' : 'px-4 py-3',
                  isActive(item.path)
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                ]"
                :title="isCollapsed ? item.title : ''"
              >
                <span
                  v-html="getIcon(item.icon)"
                  :class="[
                    'flex-shrink-0 transition-colors duration-300',
                    isActive(item.path) ? 'text-blue-600' : 'text-gray-500'
                  ]"
                ></span>
                
                <span
                  class="whitespace-nowrap overflow-hidden transition-all duration-300 ease-in-out"
                  :class="[
                    isCollapsed ? 'w-0 opacity-0 ml-0' : 'w-32 opacity-100 ml-3'
                  ]"
                >
                  {{ item.title }}
                </span>
                
                <span
                  v-if="item.badge && !isCollapsed"
                  class="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full"
                >
                  {{ item.badge }}
                </span>
                
                <span
                  v-if="item.badge && isCollapsed"
                  class="absolute -top-1 -right-1 bg-red-500 text-white text-xs font-bold w-5 h-5 flex items-center justify-center rounded-full"
                >
                  {{ item.badge }}
                </span>
              </button>
            </nav>
          </div>
        </template>
      </div>
    </aside>

    <main
      :class="[
        'pt-16 min-h-screen transition-all duration-300',
        isCollapsed ? 'pl-16' : 'pl-64'
      ]"
    >
      <div class="p-6">
        <router-view />
      </div>
    </main>

    <Teleport to="body">
      <div
        v-if="showWarningLeadModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('warning-lead', $event)"
        @mouseup="onBackdropMouseUp('warning-lead', $event) && closeWarningLeadModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">设置提醒提前时间</h3>
            <button @click="closeWarningLeadModal" class="text-gray-400 hover:text-gray-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-6 space-y-4">
            <p class="text-sm text-gray-600">按分钟设置，范围 1 到 120 分钟。当前：{{ formatLeadText(reminderLeadSeconds) }}。</p>
            <div class="flex items-center gap-2">
              <button
                type="button"
                @click="adjustWarningLead(-1)"
                class="h-10 w-10 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                -
              </button>
              <input
                v-model.number="warningLeadDraftMinute"
                type="number"
                min="1"
                max="120"
                step="1"
                placeholder="分钟"
                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
              <button
                type="button"
                @click="adjustWarningLead(1)"
                class="h-10 w-10 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                +
              </button>
            </div>
            <div class="flex flex-wrap gap-2">
              <button type="button" @click="setWarningLeadPreset(1)" class="px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50">1分钟</button>
              <button type="button" @click="setWarningLeadPreset(5)" class="px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50">5分钟</button>
              <button type="button" @click="setWarningLeadPreset(10)" class="px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50">10分钟</button>
              <button type="button" @click="setWarningLeadPreset(15)" class="px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50">15分钟</button>
              <button type="button" @click="setWarningLeadPreset(20)" class="px-3 py-1.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50">20分钟</button>
            </div>
            <p v-if="warningLeadError" class="text-sm text-red-600">{{ warningLeadError }}</p>
            <div class="pt-1 flex justify-end gap-3">
              <button
                type="button"
                @click="closeWarningLeadModal"
                class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                type="button"
                @click="applyWarningLeadSetting"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="activeGlobalWarning"
        class="fixed inset-0 bg-black bg-opacity-40 z-[70] flex items-center justify-center p-4"
      >
        <div class="bg-white rounded-xl shadow-2xl w-full max-w-md border border-orange-200">
          <div class="px-5 py-4 border-b border-orange-100 bg-orange-50">
            <h3 class="text-lg font-semibold text-orange-800">计时剩余提醒</h3>
          </div>
          <div class="px-5 py-4 space-y-2 text-sm text-gray-700">
            <p><span class="text-gray-500">桌号：</span> {{ activeGlobalWarning.tableNo || '-' }}</p>
            <p><span class="text-gray-500">客户：</span> {{ activeGlobalWarning.customerName || '-' }}</p>
            <p class="text-base font-semibold text-orange-700">剩余 {{ activeGlobalWarning.remainingText }}</p>
          </div>
          <div class="px-5 py-4 border-t border-gray-100 flex justify-end">
            <button
              @click="dismissGlobalWarning"
              class="px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
            >
              我知道了
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showChangePasswordModal"
        class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
        @mousedown="onBackdropMouseDown('change-password', $event)"
        @mouseup="onBackdropMouseUp('change-password', $event) && closeChangePasswordModal()"
      >
        <div class="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
          <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800">修改密码</h3>
            <button @click="closeChangePasswordModal" class="text-gray-400 hover:text-gray-600 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <form @submit.prevent="submitPasswordChange" class="p-6 space-y-4">
            <div v-if="passwordSuccess" class="p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
              {{ passwordSuccess }}
            </div>
            <div v-if="passwordError" class="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {{ passwordError }}
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">当前密码</label>
              <input
                v-model="passwordForm.currentPassword"
                type="password"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  passwordErrors.currentPassword ? 'border-red-500' : 'border-gray-300'
                ]"
                placeholder="请输入当前密码"
              >
              <p v-if="passwordErrors.currentPassword" class="text-red-500 text-xs mt-1">{{ passwordErrors.currentPassword }}</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">新密码</label>
              <input
                v-model="passwordForm.newPassword"
                type="password"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  passwordErrors.newPassword ? 'border-red-500' : 'border-gray-300'
                ]"
                placeholder="请输入新密码"
              >
              <p v-if="passwordErrors.newPassword" class="text-red-500 text-xs mt-1">{{ passwordErrors.newPassword }}</p>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">确认新密码</label>
              <input
                v-model="passwordForm.confirmPassword"
                type="password"
                :class="[
                  'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                  passwordErrors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                ]"
                placeholder="请确认新密码"
              >
              <p v-if="passwordErrors.confirmPassword" class="text-red-500 text-xs mt-1">{{ passwordErrors.confirmPassword }}</p>
            </div>

            <div class="pt-2 flex justify-end gap-3">
              <button
                type="button"
                @click="closeChangePasswordModal"
                class="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
              <button
                type="submit"
                :disabled="passwordLoading"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="passwordLoading">处理中...</span>
                <span v-else>确认修改</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showWarningDebugPanel"
        class="fixed bottom-4 right-4 z-[80] w-[420px] max-w-[92vw] rounded-xl border border-slate-300 bg-white shadow-2xl"
      >
        <div class="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <p class="text-sm font-semibold text-slate-800">提醒调试面板</p>
          <div class="flex items-center gap-3">
            <button class="text-xs text-blue-600 hover:text-blue-700" @click="refreshGlobalTimerWarnings">刷新</button>
            <button class="text-xs text-slate-500 hover:text-slate-700" @click="showWarningDebugPanel = false">关闭</button>
          </div>
        </div>
        <div class="space-y-2 px-4 py-3 text-xs text-slate-700">
          <p>提前时间：{{ formatLeadText(reminderLeadSeconds) }}</p>
          <p>活跃计时：{{ warningDebugRows.length }}</p>
          <p>队列长度：{{ globalWarningQueue.length }}，当前弹窗：{{ activeGlobalWarning ? '有' : '无' }}</p>
        </div>
        <div class="max-h-72 overflow-auto border-t border-slate-200 px-4 py-3 text-xs">
          <div v-if="warningDebugRows.length === 0" class="text-slate-500">当前没有活跃计时。</div>
          <div v-for="row in warningDebugRows" :key="row.id" class="mb-3 rounded-lg border border-slate-200 p-2 text-slate-700">
            <p>ID: {{ row.id }}</p>
            <p>桌号: {{ row.tableNo }} | 套餐: {{ row.packagePlan }}</p>
            <p>已计时: {{ row.elapsedText }} | 剩余: {{ row.remainingText }}</p>
            <p>触发阈值(已计时): {{ row.triggerText }} | 可触发: {{ row.canTrigger }}</p>
            <p>warned: {{ row.warned }} | pending: {{ row.pending }}</p>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
aside::-webkit-scrollbar {
  width: 6px;
}

aside::-webkit-scrollbar-track {
  background: transparent;
}

aside::-webkit-scrollbar-thumb {
  background-color: #cbd5e1;
  border-radius: 3px;
}

aside::-webkit-scrollbar-thumb:hover {
  background-color: #94a3b8;
}
</style>


