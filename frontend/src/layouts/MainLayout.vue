<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores'
import { timerApi } from '@/api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isCollapsed = ref(false)
const activeTimersCount = ref(0)
const showUserMenu = ref(false)
const userMenuRef = ref(null)

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
    activeTimersCount.value = response.length || 0
  } catch (error) {
    console.error('Failed to fetch active timers count:', error)
    activeTimersCount.value = 0
  }
}

onMounted(() => {
  setTimeout(() => {
    fetchActiveTimersCount()
  }, 100)
  document.addEventListener('click', handleDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleDocumentClick)
})

const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

const menuItems = computed(() => [
  {
    title: '仪表盘',
    icon: 'dashboard',
    path: '/dashboard',
    group: 'main'
  },
  {
    title: '正在拼',
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
    title: '交易记录',
    icon: 'receipt',
    path: '/transactions',
    group: 'member'
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
    title: '系统设置',
    icon: 'settings',
    path: '/settings',
    group: 'system'
  }
])

const groupedMenuItems = computed(() => {
  const groups = {
    main: { title: '主要功能', items: [] },
    member: { title: '会员管理', items: [] },
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

const handleLogout = () => {
  closeUserMenu()
  authStore.logout()
  router.push('/login')
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
    receipt: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2zM10 8.5a.5.5 0 11-1 0 .5.5 0 011 0zm5 5a.5.5 0 11-1 0 .5.5 0 011 0z" />
    </svg>`,
    calendar: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>`,
    currency: `<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
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
    <nav class="fixed top-0 left-0 right-0 h-16 bg-white shadow-sm z-50 flex items-center justify-between px-4">
      <div class="flex items-center space-x-4">
        <button
          @click="toggleSidebar"
          class="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 class="text-xl font-semibold text-gray-800">织雾拼豆会员管理系统</h1>
      </div>
      
      <div class="flex items-center space-x-4">
        <button class="relative p-2 rounded-lg hover:bg-gray-100 transition-colors">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
          <span class="absolute top-1 right-1 h-2 w-2 bg-red-500 rounded-full"></span>
        </button>
        
        <div ref="userMenuRef" class="relative">
          <button
            @click.stop="toggleUserMenu"
            class="flex items-center space-x-2 p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <div class="h-8 w-8 bg-blue-500 rounded-full flex items-center justify-center">
              <span class="text-white text-sm font-medium">A</span>
            </div>
            <span class="text-gray-700">管理员</span>
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
        'fixed top-16 left-0 h-[calc(100vh-4rem)] bg-white shadow-lg transition-all duration-300 z-40 overflow-y-auto',
        isCollapsed ? 'w-16' : 'w-64'
      ]"
    >
      <div class="py-4">
        <template v-for="(group, key) in groupedMenuItems" :key="key">
          <div v-if="group.items.length > 0">
            <div
              v-if="!isCollapsed"
              class="px-4 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider"
            >
              {{ group.title }}
            </div>
            <div v-else class="border-t border-gray-200 my-2"></div>
            
            <nav class="space-y-1 px-2">
              <button
                v-for="item in group.items"
                :key="item.path"
                @click="navigateTo(item.path)"
                :class="[
                  'w-full flex items-center rounded-lg transition-colors relative',
                  isCollapsed ? 'justify-center px-3 py-3' : 'px-4 py-3',
                  isActive(item.path)
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                ]"
                :title="isCollapsed ? item.title : ''"
              >
                <span
                  v-html="getIcon(item.icon)"
                  :class="[
                    'flex-shrink-0',
                    isActive(item.path) ? 'text-blue-600' : 'text-gray-500'
                  ]"
                ></span>
                
                <span
                  v-if="!isCollapsed"
                  class="ml-3 flex-1 text-left text-sm font-medium"
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
