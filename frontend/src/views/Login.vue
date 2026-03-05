<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'
import api from '@/api'
import { saveAuthSession } from '@/utils/authStorage'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  username: '',
  password: '',
  rememberMe: false
})

const errors = ref({
  username: '',
  password: ''
})

const isLoading = ref(false)
const errorMessage = ref('')
const showErrorModal = ref(false)
const currentYear = new Date().getFullYear()
const isInteractiveEnabled = ref(true)
const cursor = ref({
  x: 0,
  y: 0,
  active: false
})
const shellTilt = ref({
  rotateX: 0,
  rotateY: 0
})

const pageStyle = computed(() => ({
  '--mx': `${cursor.value.x}px`,
  '--my': `${cursor.value.y}px`
}))

const shellStyle = computed(() => ({
  transform: `perspective(1200px) rotateX(${shellTilt.value.rotateX}deg) rotateY(${shellTilt.value.rotateY}deg)`
}))

function handlePointerMove(event) {
  if (!isInteractiveEnabled.value) return
  cursor.value.x = event.clientX
  cursor.value.y = event.clientY
  cursor.value.active = true

  const halfWidth = window.innerWidth / 2
  const halfHeight = window.innerHeight / 2
  const normalizedX = (event.clientX - halfWidth) / halfWidth
  const normalizedY = (event.clientY - halfHeight) / halfHeight
  shellTilt.value.rotateY = Number((normalizedX * 1.8).toFixed(2))
  shellTilt.value.rotateX = Number((-normalizedY * 1.4).toFixed(2))
}

function handlePointerLeave() {
  cursor.value.active = false
  shellTilt.value.rotateX = 0
  shellTilt.value.rotateY = 0
}

function detectInteractionCapability() {
  if (typeof window === 'undefined') return
  const isCoarsePointer = window.matchMedia('(pointer: coarse)').matches
  isInteractiveEnabled.value = !isCoarsePointer
  cursor.value.x = window.innerWidth / 2
  cursor.value.y = window.innerHeight / 2
}

onMounted(() => {
  detectInteractionCapability()
  window.addEventListener('resize', detectInteractionCapability)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', detectInteractionCapability)
})

function validateForm() {
  let isValid = true
  errors.value = { username: '', password: '' }

  if (!form.value.username.trim()) {
    errors.value.username = '请输入用户名'
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
      username: form.value.username,
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
    errorMessage.value = error.response?.data?.message || error.message || '登录失败，请检查用户名和密码'
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
    <div
      v-if="isInteractiveEnabled"
      :class="['bg-cursor-aura', cursor.active ? 'bg-cursor-aura--active' : '']"
      aria-hidden="true"
    ></div>
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
        <p class="brand-chip">Pin Beads Studio</p>
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
        </div>

        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-field">
            <label for="username">用户名</label>
            <input
              id="username"
              v-model="form.username"
              type="text"
              autocomplete="username"
              :class="['field-input', errors.username ? 'field-input--error' : '']"
              placeholder="请输入用户名"
            />
            <p v-if="errors.username" class="field-error">
              {{ errors.username }}
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
              class="inline-flex min-h-[38px] items-center rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-700"
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
  --bg-a: #ffefe4;
  --bg-b: #eaf6ff;
  --bg-c: #f4ecff;
  --mint: #44c6a8;
  --sky: #56a9ff;
  --pink: #ff8db0;
  --coral: #ff8a5b;
  --ink: #3e4a63;
  --muted: #6a778f;
  --panel: rgba(255, 255, 255, 0.9);
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  padding: 1.25rem;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, #fff7f1 0%, #eef8ff 52%, #f4edff 100%);
}

.bg-soft-gradient,
.bg-cursor-aura,
.bg-pegboard,
.bg-floating-beads {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bg-soft-gradient {
  background:
    radial-gradient(circle at 10% 20%, rgba(255, 141, 176, 0.28), transparent 38%),
    radial-gradient(circle at 84% 18%, rgba(86, 169, 255, 0.24), transparent 36%),
    radial-gradient(circle at 72% 84%, rgba(68, 198, 168, 0.2), transparent 34%);
  animation: cloud-drift 16s ease-in-out infinite alternate;
}

.bg-cursor-aura {
  opacity: 0;
  transition: opacity 200ms ease;
  background:
    radial-gradient(
      150px circle at var(--mx) var(--my),
      rgba(86, 169, 255, 0.26) 0%,
      rgba(255, 141, 176, 0.18) 34%,
      rgba(255, 255, 255, 0) 56%
    );
  z-index: 0;
}

.bg-cursor-aura--active {
  opacity: 1;
}

.bg-pegboard {
  opacity: 0.45;
  background-image: radial-gradient(circle, rgba(98, 122, 160, 0.2) 1px, transparent 1.8px);
  background-size: 20px 20px;
}

.bg-floating-beads {
  z-index: 0;
}

.bead {
  position: absolute;
  border-radius: 999px;
  border: 3px solid rgba(255, 255, 255, 0.85);
  box-shadow: inset 0 -5px 0 rgba(0, 0, 0, 0.06), 0 8px 24px -14px rgba(70, 91, 130, 0.45);
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
  background: var(--pink);
  animation: float-a 9s ease-in-out infinite;
}

.bead-b {
  width: 52px;
  height: 52px;
  right: 12%;
  top: 16%;
  background: var(--sky);
  animation: float-b 10s ease-in-out infinite;
}

.bead-c {
  width: 58px;
  height: 58px;
  left: 16%;
  bottom: 13%;
  background: var(--mint);
  animation: float-c 8.5s ease-in-out infinite;
}

.bead-d {
  width: 74px;
  height: 74px;
  right: 9%;
  bottom: 10%;
  background: #b09dff;
  animation: float-d 11s ease-in-out infinite;
}

.bead-e {
  width: 44px;
  height: 44px;
  left: 44%;
  top: 8%;
  background: #ffd166;
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
  width: min(980px, 100%);
  border-radius: 26px;
  display: grid;
  grid-template-columns: 1fr;
  overflow: hidden;
  background: var(--panel);
  border: 1px solid rgba(255, 255, 255, 0.86);
  box-shadow: 0 30px 70px -42px rgba(50, 72, 110, 0.45);
  backdrop-filter: blur(10px);
  position: relative;
  z-index: 1;
  transform-style: preserve-3d;
  transition: transform 140ms ease, box-shadow 180ms ease;
}

.bead-shell::before {
  content: '';
  position: absolute;
  inset: 10px;
  border-radius: 18px;
  border: 1px dashed rgba(108, 132, 170, 0.4);
  pointer-events: none;
}

.brand-panel {
  padding: 2rem 1.5rem;
  background:
    linear-gradient(140deg, rgba(86, 169, 255, 0.94), rgba(68, 198, 168, 0.88)),
    linear-gradient(90deg, rgba(255, 255, 255, 0.2), transparent);
  color: #ffffff;
  position: relative;
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
  padding: 0.34rem 0.72rem;
  font-size: 0.74rem;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.24);
  border: 1px solid rgba(255, 255, 255, 0.45);
}

.brand-panel h1 {
  margin: 0.9rem 0 0;
  font-size: clamp(1.52rem, 2.8vw, 2rem);
  line-height: 1.22;
  font-family: 'STKaiti', 'KaiTi', 'Noto Serif SC', serif;
  text-wrap: balance;
}

.brand-desc {
  margin-top: 1rem;
  line-height: 1.7;
  font-size: 0.93rem;
  color: rgba(255, 255, 255, 0.96);
  max-width: 34ch;
}

.pixel-row {
  margin-top: 1rem;
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
    linear-gradient(90deg, transparent 20%, #ff6d9f 20% 80%, transparent 80%),
    linear-gradient(90deg, #ff6d9f 10%, transparent 10% 30%, #ff6d9f 30% 70%, transparent 70% 90%, #ff6d9f 90%),
    linear-gradient(90deg, transparent 0 20%, #ff6d9f 20% 80%, transparent 80%),
    linear-gradient(90deg, transparent 0 30%, #ff6d9f 30% 70%, transparent 70%),
    linear-gradient(90deg, transparent 0 40%, #ff6d9f 40% 60%, transparent 60%);
  background-size: 100% 20%;
  background-repeat: no-repeat;
  background-position: 0 0, 0 20%, 0 40%, 0 60%, 0 80%;
}

.pixel-icon.flower {
  background:
    radial-gradient(circle, #ffe08a 28%, transparent 30%),
    radial-gradient(circle at 50% 14%, #ff8db0 26%, transparent 28%),
    radial-gradient(circle at 86% 50%, #8cc8ff 26%, transparent 28%),
    radial-gradient(circle at 50% 86%, #8de3c6 26%, transparent 28%),
    radial-gradient(circle at 14% 50%, #b9a4ff 26%, transparent 28%);
}

.pixel-icon.star {
  background:
    linear-gradient(90deg, transparent 40%, #ffd166 40% 60%, transparent 60%),
    linear-gradient(transparent 40%, #ffd166 40% 60%, transparent 60%),
    linear-gradient(45deg, transparent 44%, #ffd166 44% 56%, transparent 56%),
    linear-gradient(-45deg, transparent 44%, #ffd166 44% 56%, transparent 56%);
}

.form-panel {
  padding: 2rem 1.5rem 1.4rem;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(248, 252, 255, 0.9)),
    linear-gradient(125deg, rgba(255, 141, 176, 0.08), rgba(86, 169, 255, 0.08));
  color: var(--ink);
  position: relative;
}

.form-header h2 {
  margin: 0;
  font-size: 1.45rem;
  font-family: 'YouYuan', 'Noto Sans SC', 'Microsoft YaHei UI', sans-serif;
}

.form-header p {
  margin-top: 0.42rem;
  color: var(--muted);
  font-size: 0.9rem;
}

.login-form {
  margin-top: 1.2rem;
}

.login-alert {
  border: 1px solid #ffb5c8;
  background: linear-gradient(180deg, #fff4f8 0%, #fffafb 100%);
  color: #b73864;
  border-radius: 12px;
  padding: 0.72rem 0.85rem;
  font-size: 0.86rem;
  margin-bottom: 1rem;
}

.form-field + .form-field {
  margin-top: 0.95rem;
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
  border-radius: 12px;
  border: 1px solid #d8e2f0;
  background: rgba(255, 255, 255, 0.95);
  padding: 0.73rem 0.9rem;
  font-size: 0.94rem;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.field-input:hover {
  border-color: #bacde8;
}

.field-input:focus {
  outline: none;
  border-color: #56a9ff;
  box-shadow: 0 0 0 3px rgba(86, 169, 255, 0.2);
  transform: translateY(-1px);
}

.field-input--error {
  border-color: #ffa2bf;
  background: #fff8fb;
}

.field-error {
  margin-top: 0.34rem;
  font-size: 0.76rem;
  color: #d03e70;
}

.remember-row {
  margin-top: 0.9rem;
  display: inline-flex;
  align-items: center;
  gap: 0.44rem;
  font-size: 0.82rem;
  color: #53627e;
  cursor: pointer;
}

.remember-row input[type='checkbox'] {
  width: 1rem;
  height: 1rem;
  accent-color: #56a9ff;
}

.login-submit {
  width: 100%;
  margin-top: 1rem;
  border: 0;
  border-radius: 12px;
  padding: 0.76rem 0.95rem;
  color: #ffffff;
  font-size: 0.94rem;
  font-weight: 700;
  cursor: pointer;
  background: linear-gradient(120deg, #ff8db0 0%, #ff9f75 38%, #56a9ff 100%);
  box-shadow: 0 14px 26px -16px rgba(86, 169, 255, 0.8);
  transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
}

.login-submit:hover:enabled {
  transform: translateY(-1px);
  filter: brightness(1.03);
  box-shadow: 0 18px 30px -18px rgba(86, 169, 255, 0.82);
}

.login-submit:active:enabled {
  transform: translateY(0);
}

.login-submit:disabled {
  opacity: 0.76;
  cursor: not-allowed;
  filter: saturate(0.6);
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
  margin-top: 1.05rem;
  text-align: center;
  font-size: 0.76rem;
  color: #77839c;
}

@media (min-width: 900px) {
  .bead-shell {
    grid-template-columns: 1.05fr 1fr;
  }

  .brand-panel,
  .form-panel {
    padding: 2.35rem 2.2rem;
  }
}

@media (pointer: coarse) {
  .bg-cursor-aura {
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

</style>
