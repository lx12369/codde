<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { employeeApi } from '@/api'
import { useAuthStore } from '@/stores'

const authStore = useAuthStore()
const isAdmin = computed(() => String(authStore.user?.role || '').toLowerCase() === 'admin')

const employees = ref([])
const loading = ref(false)
const submitting = ref(false)
const resetting = ref(false)
const deleting = ref(false)

const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const pageSizeOptions = [10, 20, 50]

const requestError = ref('')
const feedback = reactive({
  visible: false,
  tone: 'info',
  message: ''
})

let feedbackTimer = null

const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showResetDialog = ref(false)
const showDeleteDialog = ref(false)
const pendingActionUser = ref(null)

const createForm = reactive({
  username: '',
  password: '',
  role: 'staff'
})

const editForm = reactive({
  id: null,
  username: '',
  role: 'staff'
})

const resetForm = reactive({
  id: null,
  username: '',
  newPassword: '',
  confirmPassword: ''
})

const roleOptions = [
  { value: 'staff', label: '员工' },
  { value: 'admin', label: '管理员' }
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const pageSummary = computed(() => {
  if (total.value <= 0) return '暂无数据'
  const start = (currentPage.value - 1) * pageSize.value + 1
  const end = Math.min(total.value, currentPage.value * pageSize.value)
  return `第 ${start}-${end} 条，共 ${total.value} 条`
})

const feedbackStyle = computed(() => {
  if (feedback.tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (feedback.tone === 'error') return 'border-rose-200 bg-rose-50 text-rose-800'
  return 'border-blue-200 bg-blue-50 text-blue-800'
})

const unwrapData = (payload, fallback = null) => {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data ?? fallback
  }
  return payload ?? fallback
}

const getErrorMessage = (error, fallback = '操作失败，请稍后重试') => (
  error?.response?.data?.message || error?.message || fallback
)

const formatDateTime = (value) => {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '-'
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

const toRoleLabel = (role) => (String(role || '').toLowerCase() === 'admin' ? '管理员' : '员工')

const roleBadgeClass = (role) => (
  String(role || '').toLowerCase() === 'admin'
    ? 'border-blue-200 bg-blue-50 text-blue-700'
    : 'border-slate-200 bg-slate-50 text-slate-700'
)

function clearFeedbackTimer() {
  if (!feedbackTimer) return
  window.clearTimeout(feedbackTimer)
  feedbackTimer = null
}

function showFeedback(tone, message, duration = 3200) {
  feedback.tone = tone
  feedback.message = message
  feedback.visible = true
  clearFeedbackTimer()
  feedbackTimer = window.setTimeout(() => {
    feedback.visible = false
    feedbackTimer = null
  }, duration)
}

function closeFeedback() {
  feedback.visible = false
  clearFeedbackTimer()
}

function ensureAdminAction() {
  if (isAdmin.value) return true
  showFeedback('error', '当前账号仅可查看员工列表，无法执行该操作')
  return false
}

function resetCreateForm() {
  createForm.username = ''
  createForm.password = ''
  createForm.role = 'staff'
}

function resetEditForm() {
  editForm.id = null
  editForm.username = ''
  editForm.role = 'staff'
}

function resetPasswordForm() {
  resetForm.id = null
  resetForm.username = ''
  resetForm.newPassword = ''
  resetForm.confirmPassword = ''
}

function closeCreateDialog() {
  if (submitting.value) return
  showCreateDialog.value = false
  resetCreateForm()
}

function closeEditDialog() {
  if (submitting.value) return
  showEditDialog.value = false
  resetEditForm()
}

function closeResetDialog() {
  if (resetting.value) return
  showResetDialog.value = false
  resetPasswordForm()
}

function closeDeleteDialog() {
  if (deleting.value) return
  showDeleteDialog.value = false
  pendingActionUser.value = null
}

function openCreateDialog() {
  if (!ensureAdminAction()) return
  resetCreateForm()
  showCreateDialog.value = true
}

function openEditDialog(user) {
  if (!ensureAdminAction()) return
  editForm.id = user.id
  editForm.username = user.username || ''
  editForm.role = String(user.role || 'staff').toLowerCase()
  showEditDialog.value = true
}

function openResetDialog(user) {
  if (!ensureAdminAction()) return
  resetForm.id = user.id
  resetForm.username = user.username || ''
  resetForm.newPassword = ''
  resetForm.confirmPassword = ''
  showResetDialog.value = true
}

function openDeleteDialog(user) {
  if (!ensureAdminAction()) return
  pendingActionUser.value = user
  showDeleteDialog.value = true
}

async function fetchEmployees() {
  loading.value = true
  requestError.value = ''

  try {
    const response = await employeeApi.getEmployees({
      page: currentPage.value,
      page_size: pageSize.value,
      search: String(searchKeyword.value || '').trim()
    })
    const payload = unwrapData(response, {})
    const items = Array.isArray(payload?.items) ? payload.items : []
    const pagination = payload?.pagination || {}

    employees.value = items.map((item) => ({
      id: item.id,
      username: item.username || '',
      role: item.role || 'staff',
      createdAt: item.created_at
    }))
    total.value = Number(pagination.total ?? items.length) || 0
  } catch (error) {
    employees.value = []
    total.value = 0
    requestError.value = getErrorMessage(error, '加载员工列表失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

async function submitCreate() {
  if (!ensureAdminAction()) return

  const username = String(createForm.username || '').trim()
  const password = String(createForm.password || '')
  const role = String(createForm.role || '').toLowerCase()

  if (!username) {
    showFeedback('error', '请输入用户名')
    return
  }
  if (!password || password.length < 6) {
    showFeedback('error', '密码至少需要 6 个字符')
    return
  }
  if (!['admin', 'staff'].includes(role)) {
    showFeedback('error', '角色仅支持管理员或员工')
    return
  }

  submitting.value = true
  try {
    await employeeApi.createEmployee({
      username,
      password,
      role
    })
    closeCreateDialog()
    currentPage.value = 1
    await fetchEmployees()
    showFeedback('success', '员工账号创建成功')
  } catch (error) {
    showFeedback('error', getErrorMessage(error, '创建员工失败'))
  } finally {
    submitting.value = false
  }
}

async function submitEdit() {
  if (!ensureAdminAction()) return

  const username = String(editForm.username || '').trim()
  const role = String(editForm.role || '').toLowerCase()

  if (!username) {
    showFeedback('error', '用户名不能为空')
    return
  }
  if (!['admin', 'staff'].includes(role)) {
    showFeedback('error', '角色仅支持管理员或员工')
    return
  }

  submitting.value = true
  try {
    await employeeApi.updateEmployee(editForm.id, {
      username,
      role
    })
    closeEditDialog()
    await fetchEmployees()
    showFeedback('success', '员工信息已更新')
  } catch (error) {
    showFeedback('error', getErrorMessage(error, '更新员工失败'))
  } finally {
    submitting.value = false
  }
}

async function submitResetPassword() {
  if (!ensureAdminAction()) return

  const newPassword = String(resetForm.newPassword || '')
  const confirmPassword = String(resetForm.confirmPassword || '')

  if (!newPassword || newPassword.length < 6) {
    showFeedback('error', '新密码至少需要 6 个字符')
    return
  }
  if (newPassword !== confirmPassword) {
    showFeedback('error', '两次输入的新密码不一致')
    return
  }

  resetting.value = true
  try {
    await employeeApi.resetEmployeePassword(resetForm.id, {
      new_password: newPassword
    })
    closeResetDialog()
    showFeedback('success', '密码重置成功')
  } catch (error) {
    showFeedback('error', getErrorMessage(error, '密码重置失败'))
  } finally {
    resetting.value = false
  }
}

async function confirmDelete() {
  if (!ensureAdminAction()) return
  if (!pendingActionUser.value) return

  deleting.value = true
  try {
    await employeeApi.deleteEmployee(pendingActionUser.value.id)
    closeDeleteDialog()
    if (employees.value.length <= 1 && currentPage.value > 1) {
      currentPage.value -= 1
    }
    await fetchEmployees()
    showFeedback('success', '员工账号已删除')
  } catch (error) {
    showFeedback('error', getErrorMessage(error, '删除员工失败'))
  } finally {
    deleting.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchEmployees()
}

function resetSearch() {
  if (!searchKeyword.value) return
  searchKeyword.value = ''
  currentPage.value = 1
  fetchEmployees()
}

function refreshList() {
  fetchEmployees()
}

function goToPrevPage() {
  if (currentPage.value <= 1 || loading.value) return
  currentPage.value -= 1
  fetchEmployees()
}

function goToNextPage() {
  if (currentPage.value >= totalPages.value || loading.value) return
  currentPage.value += 1
  fetchEmployees()
}

function onPageSizeChange() {
  currentPage.value = 1
  fetchEmployees()
}

onMounted(() => {
  fetchEmployees()
})

onBeforeUnmount(() => {
  clearFeedbackTimer()
})
</script>

<template>
  <div class="employees-page space-y-6">
    <section class="page-hero rounded-3xl p-6 sm:p-8">
      <div class="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div class="space-y-2">
          <p class="page-hero__eyebrow">People Workspace</p>
          <h1 class="page-hero__title">员工管理</h1>
          <p class="page-hero__meta">
            当前账号：{{ authStore.user?.username || '-' }}（{{ isAdmin ? '管理员' : '员工' }}）
          </p>
        </div>
        <button
          class="page-hero__action"
          :disabled="!isAdmin"
          @click="openCreateDialog"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.1" d="M12 4v16m8-8H4" />
          </svg>
          新增员工
        </button>
      </div>
    </section>

    <section
      v-if="!isAdmin"
      class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
    >
      当前账号为员工，只允许查看员工列表，不能新增、编辑、重置密码或删除账号。
    </section>

    <Transition name="notice">
      <section
        v-if="feedback.visible"
        :class="[
          'rounded-2xl border px-4 py-3 text-sm shadow-sm',
          feedbackStyle
        ]"
      >
        <div class="flex items-start justify-between gap-3">
          <p>{{ feedback.message }}</p>
          <button
            class="rounded-md px-2 py-0.5 text-xs font-semibold transition hover:bg-black/5"
            @click="closeFeedback"
          >
            关闭
          </button>
        </div>
      </section>
    </Transition>

    <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
      <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto_auto] lg:items-end">
        <div>
          <label for="employee-search" class="mb-1.5 block text-sm font-medium text-slate-700">关键词</label>
          <input
            id="employee-search"
            v-model="searchKeyword"
            type="text"
            placeholder="按用户名搜索"
            class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
            @keyup.enter="handleSearch"
          >
        </div>
        <div>
          <label for="employee-page-size" class="mb-1.5 block text-sm font-medium text-slate-700">每页数量</label>
          <select
            id="employee-page-size"
            v-model.number="pageSize"
            class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
            @change="onPageSizeChange"
          >
            <option v-for="size in pageSizeOptions" :key="size" :value="size">
              {{ size }}
            </option>
          </select>
        </div>
        <button
          class="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          @click="resetSearch"
        >
          清空筛选
        </button>
        <button
          class="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="loading"
          @click="handleSearch"
        >
          查询
        </button>
      </div>
    </section>

    <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <header class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 sm:px-5">
        <div>
          <h2 class="text-base font-semibold text-slate-900">员工列表</h2>
          <p class="text-xs text-slate-500">{{ pageSummary }}</p>
        </div>
        <button
          class="inline-flex min-h-[36px] items-center rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="loading"
          @click="refreshList"
        >
          刷新
        </button>
      </header>

      <div v-if="loading" class="px-5 py-10 text-center text-sm text-slate-500">
        正在加载员工列表...
      </div>

      <div v-else-if="requestError" class="px-5 py-10 text-center">
        <p class="text-sm text-rose-700">{{ requestError }}</p>
        <button
          class="mt-4 inline-flex min-h-[40px] items-center rounded-xl border border-rose-300 px-4 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50"
          @click="fetchEmployees"
        >
          重新加载
        </button>
      </div>

      <div v-else-if="employees.length === 0" class="px-5 py-10 text-center text-sm text-slate-500">
        暂无员工数据
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-slate-200">
          <thead class="bg-slate-50">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">ID</th>
              <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">用户名</th>
              <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">角色</th>
              <th class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">创建时间</th>
              <th class="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="employee in employees" :key="employee.id" class="hover:bg-slate-50/70">
              <td class="px-4 py-3 text-sm text-slate-700">{{ employee.id }}</td>
              <td class="px-4 py-3 text-sm font-medium text-slate-900">{{ employee.username }}</td>
              <td class="px-4 py-3 text-sm">
                <span
                  :class="[
                    'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold',
                    roleBadgeClass(employee.role)
                  ]"
                >
                  {{ toRoleLabel(employee.role) }}
                </span>
              </td>
              <td class="px-4 py-3 text-sm text-slate-600">{{ formatDateTime(employee.createdAt) }}</td>
              <td class="px-4 py-3">
                <div class="flex flex-wrap justify-end gap-2">
                  <button
                    class="inline-flex min-h-[34px] items-center rounded-lg px-3 text-xs font-medium text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="!isAdmin"
                    @click="openEditDialog(employee)"
                  >
                    编辑
                  </button>
                  <button
                    class="inline-flex min-h-[34px] items-center rounded-lg px-3 text-xs font-medium text-amber-700 transition hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="!isAdmin"
                    @click="openResetDialog(employee)"
                  >
                    重置密码
                  </button>
                  <button
                    class="inline-flex min-h-[34px] items-center rounded-lg px-3 text-xs font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="!isAdmin"
                    @click="openDeleteDialog(employee)"
                  >
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="flex items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 sm:px-5">
        <p class="text-xs text-slate-500">第 {{ currentPage }} / {{ totalPages }} 页</p>
        <div class="flex items-center gap-2">
          <button
            class="inline-flex min-h-[34px] items-center rounded-lg border border-slate-300 px-3 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="currentPage <= 1 || loading"
            @click="goToPrevPage"
          >
            上一页
          </button>
          <button
            class="inline-flex min-h-[34px] items-center rounded-lg border border-slate-300 px-3 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="currentPage >= totalPages || loading"
            @click="goToNextPage"
          >
            下一页
          </button>
        </div>
      </footer>
    </section>

    <Teleport to="body">
      <div v-if="showCreateDialog" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-900/55 backdrop-blur-sm" @click="closeCreateDialog"></div>
        <div class="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div class="border-b border-slate-100 px-5 py-4">
            <h3 class="text-lg font-semibold text-slate-900">新增员工</h3>
          </div>
          <form class="space-y-4 px-5 py-5" @submit.prevent="submitCreate">
            <div>
              <label for="create-username" class="mb-1.5 block text-sm font-medium text-slate-700">用户名</label>
              <input
                id="create-username"
                v-model.trim="createForm.username"
                type="text"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
            </div>
            <div>
              <label for="create-password" class="mb-1.5 block text-sm font-medium text-slate-700">初始密码</label>
              <input
                id="create-password"
                v-model="createForm.password"
                type="password"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
            </div>
            <div>
              <label for="create-role" class="mb-1.5 block text-sm font-medium text-slate-700">角色</label>
              <select
                id="create-role"
                v-model="createForm.role"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
                <option v-for="role in roleOptions" :key="role.value" :value="role.value">
                  {{ role.label }}
                </option>
              </select>
            </div>
            <div class="flex justify-end gap-3 pt-1">
              <button
                type="button"
                class="inline-flex min-h-[40px] items-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                @click="closeCreateDialog"
              >
                取消
              </button>
              <button
                type="submit"
                class="inline-flex min-h-[40px] items-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="submitting"
              >
                {{ submitting ? '保存中...' : '创建' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showEditDialog" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-900/55 backdrop-blur-sm" @click="closeEditDialog"></div>
        <div class="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div class="border-b border-slate-100 px-5 py-4">
            <h3 class="text-lg font-semibold text-slate-900">编辑员工</h3>
          </div>
          <form class="space-y-4 px-5 py-5" @submit.prevent="submitEdit">
            <div>
              <label for="edit-username" class="mb-1.5 block text-sm font-medium text-slate-700">用户名</label>
              <input
                id="edit-username"
                v-model.trim="editForm.username"
                type="text"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
            </div>
            <div>
              <label for="edit-role" class="mb-1.5 block text-sm font-medium text-slate-700">角色</label>
              <select
                id="edit-role"
                v-model="editForm.role"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
                <option v-for="role in roleOptions" :key="role.value" :value="role.value">
                  {{ role.label }}
                </option>
              </select>
            </div>
            <div class="flex justify-end gap-3 pt-1">
              <button
                type="button"
                class="inline-flex min-h-[40px] items-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                @click="closeEditDialog"
              >
                取消
              </button>
              <button
                type="submit"
                class="inline-flex min-h-[40px] items-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="submitting"
              >
                {{ submitting ? '保存中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showResetDialog" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-900/55 backdrop-blur-sm" @click="closeResetDialog"></div>
        <div class="relative w-full max-w-md rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <div class="border-b border-slate-100 px-5 py-4">
            <h3 class="text-lg font-semibold text-slate-900">重置密码</h3>
            <p class="mt-1 text-xs text-slate-500">账号：{{ resetForm.username }}</p>
          </div>
          <form class="space-y-4 px-5 py-5" @submit.prevent="submitResetPassword">
            <div>
              <label for="reset-password" class="mb-1.5 block text-sm font-medium text-slate-700">新密码</label>
              <input
                id="reset-password"
                v-model="resetForm.newPassword"
                type="password"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
            </div>
            <div>
              <label for="reset-confirm-password" class="mb-1.5 block text-sm font-medium text-slate-700">确认新密码</label>
              <input
                id="reset-confirm-password"
                v-model="resetForm.confirmPassword"
                type="password"
                class="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-[#1d4ed8] focus:ring-offset-1"
              >
            </div>
            <div class="flex justify-end gap-3 pt-1">
              <button
                type="button"
                class="inline-flex min-h-[40px] items-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                @click="closeResetDialog"
              >
                取消
              </button>
              <button
                type="submit"
                class="inline-flex min-h-[40px] items-center rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="resetting"
              >
                {{ resetting ? '提交中...' : '确认重置' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="showDeleteDialog" class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-slate-900/55 backdrop-blur-sm" @click="closeDeleteDialog"></div>
        <div class="relative w-full max-w-md rounded-2xl border border-rose-200 bg-white shadow-2xl">
          <div class="border-b border-rose-100 bg-rose-50/70 px-5 py-4">
            <h3 class="text-lg font-semibold text-rose-800">确认删除员工</h3>
            <p class="mt-1 text-sm text-rose-700">
              删除后账号将无法登录，请确认是否删除「{{ pendingActionUser?.username }}」。
            </p>
          </div>
          <div class="flex justify-end gap-3 px-5 py-4">
            <button
              type="button"
              class="inline-flex min-h-[40px] items-center rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              @click="closeDeleteDialog"
            >
              取消
            </button>
            <button
              type="button"
              class="inline-flex min-h-[40px] items-center rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="deleting"
              @click="confirmDelete"
            >
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.employees-page {
  animation: employees-fade-in 260ms ease-out;
}

@keyframes employees-fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
