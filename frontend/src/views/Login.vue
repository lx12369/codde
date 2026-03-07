<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'
import api from '@/api'
import { saveAuthSession } from '@/utils/authStorage'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  account: '',
  password: '',
  rememberMe: false
})

const errors = ref({
  account: '',
  password: ''
})

const isLoading = ref(false)
const errorMessage = ref('')
const showErrorModal = ref(false)
const currentYear = new Date().getFullYear()
const isInteractiveEnabled = ref(true)
const followActive = ref(false)
const pointerTarget = ref({ x: 0, y: 0 })
const pointerCurrent = ref({ x: 0, y: 0 })
const shellTilt = ref({
  rotateX: 0,
  rotateY: 0
})
let pointerAnimationId = null

const pageStyle = computed(() => ({
  '--fx': `${pointerCurrent.value.x}px`,
  '--fy': `${pointerCurrent.value.y}px`
}))

const shellStyle = computed(() => ({
  transform: `perspective(1200px) rotateX(${shellTilt.value.rotateX}deg) rotateY(${shellTilt.value.rotateY}deg)`
}))

function handlePointerMove(event) {
  if (!isInteractiveEnabled.value) return
  pointerTarget.value.x = event.clientX
  pointerTarget.value.y = event.clientY
  followActive.value = true

  const halfWidth = window.innerWidth / 2
  const halfHeight = window.innerHeight / 2
  const normalizedX = (event.clientX - halfWidth) / halfWidth
  const normalizedY = (event.clientY - halfHeight) / halfHeight
  shellTilt.value.rotateY = Number((normalizedX * 1.8).toFixed(2))
  shellTilt.value.rotateX = Number((-normalizedY * 1.4).toFixed(2))
}

function handlePointerLeave() {
  followActive.value = false
  if (typeof window !== 'undefined') {
    pointerTarget.value.x = window.innerWidth / 2
    pointerTarget.value.y = window.innerHeight / 2
  }
  shellTilt.value.rotateX = 0
  shellTilt.value.rotateY = 0
}

function detectInteractionCapability() {
  if (typeof window === 'undefined') return
  const isCoarsePointer = window.matchMedia('(pointer: coarse)').matches
  isInteractiveEnabled.value = !isCoarsePointer
  const centerX = window.innerWidth / 2
  const centerY = window.innerHeight / 2
  if (!followActive.value) {
    pointerTarget.value.x = centerX
    pointerTarget.value.y = centerY
  }
  if (pointerCurrent.value.x === 0 && pointerCurrent.value.y === 0) {
    pointerCurrent.value.x = centerX
    pointerCurrent.value.y = centerY
  }
}

function animatePointerFollow() {
  const easing = followActive.value ? 0.2 : 0.09
  pointerCurrent.value.x += (pointerTarget.value.x - pointerCurrent.value.x) * easing
  pointerCurrent.value.y += (pointerTarget.value.y - pointerCurrent.value.y) * easing
  pointerAnimationId = window.requestAnimationFrame(animatePointerFollow)
}

onMounted(() => {
  detectInteractionCapability()
  pointerAnimationId = window.requestAnimationFrame(animatePointerFollow)
  window.addEventListener('resize', detectInteractionCapability)
})

onBeforeUnmount(() => {
  if (pointerAnimationId) {
    window.cancelAnimationFrame(pointerAnimationId)
    pointerAnimationId = null
  }
  window.removeEventListener('resize', detectInteractionCapability)
})

function validateForm() {
  let isValid = true
  errors.value = { account: '', password: '' }

  if (!form.value.account.trim()) {
    errors.value.account = '请输入账号'
    isValid = false
  }

  if (!form.value.password) {
    errors.value.password = '请输入密码'
    isValid = false
  }

  return isValid
}

async function handleLogin() {
  errorMessage.value = ''
  showErrorModal.value = false

  if (!validateForm()) {
    return
  }

  isLoading.value = true

  try {
    const response = await api.post('/auth/login', {
      account: form.value.account,
      password: form.value.password,
      rememberMe: form.value.rememberMe
    })

    const data = response.data || response
    const token = data.token
    const user = data.user

    if (!token) {
      throw new Error('登录失败：服务端未返回令牌')
    }

    authStore.setToken(token)
    authStore.setUser(user)
    saveAuthSession(token, user, form.value.rememberMe)
    router.push({ name: 'dashboard' })
  } catch (error) {
    console.error('Login failed:', error)
    errorMessage.value = error.response?.data?.message || error.message || '登录失败，请检查账号和密码'
    showErrorModal.value = true
  } finally {
    isLoading.value = false
  }
}

function closeErrorModal() {
  showErrorModal.value = false
}
</script>

<template>
  <div
    class="bead-login-page"
    :style="pageStyle"
    @pointermove="handlePointerMove"
    @pointerleave="handlePointerLeave"
  >
    <div class="bg-soft-gradient"></div>
    <div class="bg-prism-flow"></div>
    <div
      v-if="isInteractiveEnabled"
      :class="['bg-follow-core', followActive ? 'bg-follow-core--active' : '']"
      aria-hidden="true"
    ></div>
    <div
      v-if="isInteractiveEnabled"
      :class="['bg-follow-ring', followActive ? 'bg-follow-ring--active' : '']"
      aria-hidden="true"
    ></div>
    <div class="bg-holo-grid"></div>
    <div class="bg-scanlight"></div>
    <div class="bg-pegboard"></div>
    <div class="bg-floating-beads" aria-hidden="true">
      <span class="bead bead-a"></span>
      <span class="bead bead-b"></span>
      <span class="bead bead-c"></span>
      <span class="bead bead-d"></span>
      <span class="bead bead-e"></span>
      <span class="bead bead-f"></span>
    </div>

    <div class="bead-shell" :style="isInteractiveEnabled ? shellStyle : undefined">
      <aside class="brand-panel">
        <p class="brand-chip">FogBead Console</p>
        <h1>织雾拼豆管理系统</h1>
        <div class="pixel-row" aria-hidden="true">
          <span class="pixel-icon heart"></span>
          <span class="pixel-icon flower"></span>
          <span class="pixel-icon star"></span>
        </div>
      </aside>

      <section class="form-panel">
        <div class="form-header">
          <h2>欢迎回来</h2>
          <p>请输入账号和密码进入拼豆管理后台</p>
        </div>

        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-field">
            <label for="account">账号</label>
            <input
              id="account"
              v-model="form.account"
              type="text"
              autocomplete="username"
              :class="['field-input', errors.account ? 'field-input--error' : '']"
              placeholder="请输入账号"
            />
            <p v-if="errors.account" class="field-error">
              {{ errors.account }}
            </p>
          </div>

          <div class="form-field">
            <label for="password">密码</label>
            <input
              id="password"
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              :class="['field-input', errors.password ? 'field-input--error' : '']"
              placeholder="请输入密码"
            />
            <p v-if="errors.password" class="field-error">
              {{ errors.password }}
            </p>
          </div>

          <label class="remember-row" for="remember-me">
            <input
              id="remember-me"
              v-model="form.rememberMe"
              type="checkbox"
            />
            <span>记住我（7天内免重复登录）</span>
          </label>

          <button
            type="submit"
            :disabled="isLoading"
            class="login-submit"
          >
            <span v-if="isLoading" class="submit-loading">
              <svg class="spinner" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              登录中...
            </span>
            <span v-else>登录</span>
          </button>
        </form>

        <p class="copyright">
          &copy; {{ currentYear }} 织雾拼豆管理系统
        </p>
      </section>
    </div>

    <Teleport to="body">
      <div
        v-if="showErrorModal"
        class="fixed inset-0 z-[120] flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
      >
        <div class="absolute inset-0 bg-slate-900/55 backdrop-blur-sm" @click="closeErrorModal"></div>
        <div class="relative w-full max-w-sm overflow-hidden rounded-2xl border border-rose-200 bg-white shadow-2xl">
          <div class="border-b border-rose-100 bg-rose-50 px-5 py-4">
            <h3 class="text-base font-semibold text-rose-800">登录失败</h3>
          </div>
          <div class="px-5 py-4 text-sm text-slate-700">
            {{ errorMessage || '账号或密码错误，请检查后重试。' }}
          </div>
          <div class="flex justify-end border-t border-slate-100 px-5 py-4">
            <button
              type="button"
              class="error-confirm inline-flex min-h-[38px] items-center rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-700"
              @click="closeErrorModal"
            >
              我知道了
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.bead-login-page {
  --bg-a: #f2f9ff;
  --bg-b: #f6fbf8;
  --bg-c: #fff8f3;
  --teal: #0f766e;
  --cyan: #0284c7;
  --amber: #f59e0b;
  --coral: #ea580c;
  --ink: #1f2937;
  --muted: #5f6f86;
  --panel: rgba(255, 255, 255, 0.9);
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  padding: 1.3rem;
  display: grid;
  place-items: center;
  isolation: isolate;
  background:
    radial-gradient(130% 110% at 8% 6%, rgba(14, 116, 144, 0.16), transparent 46%),
    radial-gradient(95% 85% at 86% 15%, rgba(245, 158, 11, 0.14), transparent 56%),
    linear-gradient(145deg, var(--bg-a) 0%, var(--bg-b) 46%, var(--bg-c) 100%);
}

.bead-login-page::before,
.bead-login-page::after {
  content: '';
  position: absolute;
  inset: -18%;
  pointer-events: none;
  z-index: 0;
}

.bead-login-page::before {
  background: conic-gradient(
    from 120deg at var(--fx) var(--fy),
    rgba(2, 132, 199, 0) 0deg,
    rgba(2, 132, 199, 0.24) 72deg,
    rgba(15, 118, 110, 0.16) 146deg,
    rgba(234, 88, 12, 0.18) 228deg,
    rgba(2, 132, 199, 0) 360deg
  );
  mix-blend-mode: screen;
  opacity: 0.62;
  filter: blur(28px) saturate(118%);
  animation: prism-rotate 20s linear infinite;
}

.bead-login-page::after {
  background:
    radial-gradient(circle at 18% 78%, rgba(255, 255, 255, 0.52), transparent 38%),
    radial-gradient(circle at 84% 28%, rgba(255, 255, 255, 0.46), transparent 35%);
  opacity: 0.6;
  filter: blur(40px);
}

.bg-soft-gradient,
.bg-prism-flow,
.bg-follow-core,
.bg-follow-ring,
.bg-holo-grid,
.bg-scanlight,
.bg-pegboard,
.bg-floating-beads {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.bg-soft-gradient {
  background:
    radial-gradient(circle at 10% 20%, rgba(234, 88, 12, 0.2), transparent 40%),
    radial-gradient(circle at 84% 18%, rgba(2, 132, 199, 0.23), transparent 36%),
    radial-gradient(circle at 72% 84%, rgba(15, 118, 110, 0.19), transparent 34%);
  mix-blend-mode: multiply;
  animation: cloud-drift 20s ease-in-out infinite alternate;
}

.bg-prism-flow {
  inset: -24%;
  background:
    conic-gradient(
      from 90deg at 16% 34%,
      rgba(2, 132, 199, 0.34),
      rgba(56, 189, 248, 0.05),
      rgba(15, 118, 110, 0.26),
      rgba(250, 204, 21, 0.1),
      rgba(234, 88, 12, 0.26),
      rgba(2, 132, 199, 0.34)
    ),
    conic-gradient(
      from 30deg at 86% 64%,
      rgba(250, 204, 21, 0.26),
      rgba(56, 189, 248, 0.08),
      rgba(15, 118, 110, 0.2),
      rgba(2, 132, 199, 0.22),
      rgba(234, 88, 12, 0.2),
      rgba(250, 204, 21, 0.26)
    );
  opacity: 0.56;
  mix-blend-mode: screen;
  filter: blur(18px) saturate(122%);
  animation: prism-flow 22s ease-in-out infinite alternate;
}

.bg-follow-core {
  background:
    radial-gradient(
      260px circle at var(--fx) var(--fy),
      rgba(56, 189, 248, 0.38) 0%,
      rgba(56, 189, 248, 0.2) 32%,
      rgba(15, 118, 110, 0.08) 56%,
      rgba(255, 255, 255, 0) 74%
    );
  opacity: 0;
  z-index: 1;
  mix-blend-mode: screen;
  filter: blur(2px) saturate(118%);
  transition: opacity 200ms ease;
}

.bg-follow-core--active {
  opacity: 0.96;
}

.bg-follow-ring {
  background:
    radial-gradient(circle at var(--fx) var(--fy), rgba(255, 255, 255, 0) 52px, rgba(125, 211, 252, 0.32) 58px, rgba(255, 255, 255, 0) 82px),
    radial-gradient(circle at var(--fx) var(--fy), rgba(255, 255, 255, 0.42) 0 14px, rgba(255, 255, 255, 0) 34px);
  opacity: 0;
  z-index: 1;
  mix-blend-mode: screen;
  transition: opacity 220ms ease;
  animation: follow-ring-pulse 2.6s ease-in-out infinite;
}

.bg-follow-ring--active {
  opacity: 0.78;
}

.bg-holo-grid {
  inset: -28% -12% -6%;
  background:
    repeating-linear-gradient(90deg, rgba(15, 23, 42, 0.07) 0 1px, transparent 1px 54px),
    repeating-linear-gradient(0deg, rgba(15, 23, 42, 0.06) 0 1px, transparent 1px 54px);
  transform: perspective(1000px) rotateX(68deg) translateY(34%);
  transform-origin: center bottom;
  -webkit-mask-image: linear-gradient(to top, rgba(0, 0, 0, 0.82), transparent 72%);
  mask-image: linear-gradient(to top, rgba(0, 0, 0, 0.82), transparent 72%);
  opacity: 0.36;
  animation: grid-drift 24s linear infinite;
}

.bg-scanlight {
  inset: -8% -40%;
  background: linear-gradient(
    114deg,
    transparent 0%,
    rgba(255, 255, 255, 0.03) 36%,
    rgba(255, 255, 255, 0.44) 50%,
    rgba(255, 255, 255, 0.03) 64%,
    transparent 100%
  );
  transform: translateX(-100%) skewX(-16deg);
  opacity: 0.52;
  animation: scan-sweep 9s ease-in-out infinite;
}

.bg-pegboard {
  opacity: 0.34;
  background-image: radial-gradient(circle, rgba(98, 122, 160, 0.2) 1px, transparent 1.7px);
  background-size: 20px 20px;
  mix-blend-mode: soft-light;
}

.bg-floating-beads {
  z-index: 1;
}

.bead {
  position: absolute;
  border-radius: 999px;
  border: 3px solid rgba(255, 255, 255, 0.85);
  box-shadow: inset 0 -5px 0 rgba(0, 0, 0, 0.06), 0 8px 24px -14px rgba(70, 91, 130, 0.45);
  mix-blend-mode: multiply;
}

.bead::after {
  content: '';
  position: absolute;
  inset: 35%;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.42);
}

.bead-a {
  width: 68px;
  height: 68px;
  left: 8%;
  top: 11%;
  background: #fb923c;
  animation: float-a 9s ease-in-out infinite;
}

.bead-b {
  width: 52px;
  height: 52px;
  right: 12%;
  top: 16%;
  background: #38bdf8;
  animation: float-b 10s ease-in-out infinite;
}

.bead-c {
  width: 58px;
  height: 58px;
  left: 16%;
  bottom: 13%;
  background: #34d399;
  animation: float-c 8.5s ease-in-out infinite;
}

.bead-d {
  width: 74px;
  height: 74px;
  right: 9%;
  bottom: 10%;
  background: #5eead4;
  animation: float-d 11s ease-in-out infinite;
}

.bead-e {
  width: 44px;
  height: 44px;
  left: 44%;
  top: 8%;
  background: #fbbf24;
  animation: float-e 7.5s ease-in-out infinite;
}

.bead-f {
  width: 46px;
  height: 46px;
  right: 42%;
  bottom: 8%;
  background: var(--coral);
  animation: float-f 9.6s ease-in-out infinite;
}

.bead-shell {
  width: min(1020px, 100%);
  border-radius: 28px;
  display: grid;
  grid-template-columns: 1fr;
  overflow: hidden;
  background: var(--panel);
  border: 1px solid rgba(255, 255, 255, 0.92);
  box-shadow: 0 36px 70px -42px rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(12px);
  position: relative;
  z-index: 1;
  transform-style: preserve-3d;
  transition: transform 150ms ease, box-shadow 220ms ease;
}

.bead-shell::before {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 20px;
  border: 1px dashed rgba(88, 122, 151, 0.36);
  pointer-events: none;
}

.brand-panel {
  padding: 2.1rem 1.6rem;
  background:
    linear-gradient(145deg, rgba(14, 116, 144, 0.96), rgba(15, 118, 110, 0.92)),
    linear-gradient(90deg, rgba(255, 255, 255, 0.2), transparent);
  color: #ffffff;
  position: relative;
  display: flex;
  flex-direction: column;
}

.brand-panel::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  width: 44%;
  height: 100%;
  background-image: radial-gradient(circle, rgba(255, 255, 255, 0.25) 1px, transparent 1.8px);
  background-size: 15px 15px;
  opacity: 0.45;
}

.brand-chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0.35rem 0.76rem;
  font-size: 0.74rem;
  letter-spacing: 0.04em;
  font-weight: 700;
  width: fit-content;
  background: rgba(255, 255, 255, 0.22);
  border: 1px solid rgba(255, 255, 255, 0.5);
}

.brand-panel h1 {
  margin: 0.95rem 0 0;
  font-size: clamp(1.52rem, 2.8vw, 2rem);
  line-height: 1.25;
  font-family: 'STKaiti', 'KaiTi', 'Noto Serif SC', serif;
  text-wrap: balance;
  max-width: 15ch;
}

.pixel-row {
  margin-top: 0.95rem;
  display: flex;
  gap: 0.6rem;
}

.pixel-icon {
  width: 22px;
  height: 22px;
  image-rendering: pixelated;
  filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.14));
}

.pixel-icon.heart {
  background:
    linear-gradient(90deg, transparent 20%, #fb7185 20% 80%, transparent 80%),
    linear-gradient(90deg, #fb7185 10%, transparent 10% 30%, #fb7185 30% 70%, transparent 70% 90%, #fb7185 90%),
    linear-gradient(90deg, transparent 0 20%, #fb7185 20% 80%, transparent 80%),
    linear-gradient(90deg, transparent 0 30%, #fb7185 30% 70%, transparent 70%),
    linear-gradient(90deg, transparent 0 40%, #fb7185 40% 60%, transparent 60%);
  background-size: 100% 20%;
  background-repeat: no-repeat;
  background-position: 0 0, 0 20%, 0 40%, 0 60%, 0 80%;
}

.pixel-icon.flower {
  background:
    radial-gradient(circle, #fcd34d 28%, transparent 30%),
    radial-gradient(circle at 50% 14%, #fb923c 26%, transparent 28%),
    radial-gradient(circle at 86% 50%, #38bdf8 26%, transparent 28%),
    radial-gradient(circle at 50% 86%, #34d399 26%, transparent 28%),
    radial-gradient(circle at 14% 50%, #a5f3fc 26%, transparent 28%);
}

.pixel-icon.star {
  background:
    linear-gradient(90deg, transparent 40%, #fbbf24 40% 60%, transparent 60%),
    linear-gradient(transparent 40%, #fbbf24 40% 60%, transparent 60%),
    linear-gradient(45deg, transparent 44%, #fbbf24 44% 56%, transparent 56%),
    linear-gradient(-45deg, transparent 44%, #fbbf24 44% 56%, transparent 56%);
}

.form-panel {
  padding: 2.1rem 1.6rem 1.5rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(248, 252, 255, 0.9)),
    linear-gradient(125deg, rgba(2, 132, 199, 0.07), rgba(245, 158, 11, 0.08));
  color: var(--ink);
  position: relative;
}

.form-header h2 {
  margin: 0;
  font-size: 1.42rem;
  font-family: 'YouYuan', 'Noto Sans SC', 'Microsoft YaHei UI', sans-serif;
}

.form-header p {
  margin-top: 0.5rem;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.6;
}

.login-form {
  margin-top: 1.15rem;
}

.form-field + .form-field {
  margin-top: 0.9rem;
}

.form-field label {
  display: block;
  margin-bottom: 0.44rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: #4c5a74;
}

.field-input {
  width: 100%;
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid #d2deef;
  background: rgba(255, 255, 255, 0.95);
  padding: 0.72rem 0.9rem;
  font-size: 0.94rem;
  color: #334155;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease, background-color 160ms ease;
}

.field-input::placeholder {
  color: #95a4bc;
}

.field-input:hover {
  border-color: #a6c9e8;
}

.field-input:focus {
  outline: none;
  border-color: var(--cyan);
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.2);
  transform: translateY(-1px);
}

.field-input--error {
  border-color: #fb7185;
  background: #fff5f6;
}

.field-error {
  margin-top: 0.34rem;
  font-size: 0.76rem;
  color: #be123c;
}

.remember-row {
  margin-top: 0.92rem;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  gap: 0.46rem;
  font-size: 0.82rem;
  color: #53627e;
  cursor: pointer;
  user-select: none;
}

.remember-row input[type='checkbox'] {
  width: 1.02rem;
  height: 1.02rem;
  accent-color: var(--cyan);
}

.login-submit {
  width: 100%;
  margin-top: 1rem;
  border: 0;
  min-height: 46px;
  border-radius: 12px;
  padding: 0.78rem 0.95rem;
  color: #ffffff;
  font-size: 0.94rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  cursor: pointer;
  background: linear-gradient(120deg, var(--teal) 0%, var(--cyan) 42%, var(--amber) 100%);
  box-shadow: 0 14px 26px -16px rgba(2, 132, 199, 0.8);
  transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
}

.login-submit:hover:enabled {
  transform: translateY(-1px);
  filter: brightness(1.03);
  box-shadow: 0 18px 30px -18px rgba(2, 132, 199, 0.82);
}

.login-submit:active:enabled {
  transform: translateY(0);
}

.login-submit:disabled {
  opacity: 0.76;
  cursor: not-allowed;
  filter: saturate(0.6);
}

.login-submit:focus-visible,
.field-input:focus-visible,
.error-confirm:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.24);
}

.submit-loading {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
}

.spinner {
  width: 1rem;
  height: 1rem;
  animation: spin 0.9s linear infinite;
}

.copyright {
  margin-top: 1.12rem;
  text-align: center;
  font-size: 0.76rem;
  color: #70819a;
}

.error-confirm {
  min-height: 40px;
  min-width: 92px;
}

@media (min-width: 900px) {
  .bead-shell {
    grid-template-columns: 1.05fr 1fr;
  }

  .brand-panel,
  .form-panel {
    padding: 2.45rem 2.3rem;
  }
}

@media (max-width: 720px) {
  .bead-login-page {
    padding: 1rem;
  }

  .bead-shell {
    border-radius: 22px;
  }

  .brand-panel,
  .form-panel {
    padding: 1.5rem 1.2rem;
  }

  .brand-panel h1 {
    font-size: 1.55rem;
  }

  .brand-desc {
    max-width: 100%;
  }
}

@media (pointer: coarse) {
  .bg-follow-core,
  .bg-follow-ring,
  .bg-scanlight {
    display: none;
  }

  .bead-shell {
    transform: none !important;
  }
}

@keyframes cloud-drift {
  0% {
    transform: translate3d(-2%, -1%, 0) scale(1);
  }
  100% {
    transform: translate3d(2%, 2%, 0) scale(1.05);
  }
}

@keyframes prism-rotate {
  from {
    transform: rotate(0deg) scale(1);
  }
  to {
    transform: rotate(360deg) scale(1.08);
  }
}

@keyframes prism-flow {
  0% {
    transform: translate3d(-3%, -2%, 0) rotate(0deg);
  }
  50% {
    transform: translate3d(2%, 3%, 0) rotate(10deg);
  }
  100% {
    transform: translate3d(3%, -1%, 0) rotate(-8deg);
  }
}

@keyframes grid-drift {
  0% {
    transform: perspective(1000px) rotateX(68deg) translate3d(0, 34%, 0);
  }
  100% {
    transform: perspective(1000px) rotateX(68deg) translate3d(0, 39%, 0);
  }
}

@keyframes scan-sweep {
  0%,
  100% {
    transform: translateX(-100%) skewX(-16deg);
  }
  50% {
    transform: translateX(100%) skewX(-16deg);
  }
}

@keyframes follow-ring-pulse {
  0%,
  100% {
    filter: blur(0px) saturate(100%);
  }
  50% {
    filter: blur(1px) saturate(120%);
  }
}

@keyframes float-a {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(12px); }
}

@keyframes float-b {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-14px); }
}

@keyframes float-c {
  0%, 100% { transform: translate3d(0, 0, 0); }
  50% { transform: translate3d(12px, -8px, 0); }
}

@keyframes float-d {
  0%, 100% { transform: translate3d(0, 0, 0); }
  50% { transform: translate3d(-10px, 8px, 0); }
}

@keyframes float-e {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(9px); }
}

@keyframes float-f {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .bead-login-page::before,
  .bead-login-page::after,
  .bg-soft-gradient,
  .bg-prism-flow,
  .bg-follow-core,
  .bg-follow-ring,
  .bg-holo-grid,
  .bg-scanlight,
  .bead,
  .spinner,
  .bead-shell,
  .field-input,
  .login-submit,
  .error-confirm {
    animation: none !important;
    transition: none !important;
  }
}

</style>
