import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { guest: true }
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/dashboard'
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/Dashboard.vue')
        },
        {
          path: 'customers',
          name: 'customers',
          component: () => import('@/views/Customers.vue')
        },
        {
          path: 'employees',
          name: 'employees',
          component: () => import('@/views/Employees.vue')
        },
        {
          path: 'transactions',
          name: 'transactions',
          component: () => import('@/views/Transactions.vue')
        },
        {
          path: 'activities',
          name: 'activities',
          component: () => import('@/views/Activities.vue')
        },
        {
          path: 'billing-rules',
          name: 'billing-rules',
          component: () => import('@/views/Billing.vue')
        },
        {
          path: 'bead-inventory',
          name: 'bead-inventory',
          component: () => import('@/views/BeadInventory.vue')
        },
        {
          path: 'active-timers',
          name: 'active-timers',
          component: () => import('@/views/ActiveTimers.vue')
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/Settings.vue'),
          meta: { requiresAdmin: true }
        },
        {
          path: 'system-logs',
          name: 'system-logs',
          component: () => import('@/views/SystemLogs.vue'),
          meta: { requiresAdmin: true }
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/dashboard'
    }
  ]
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const isAdmin = String(authStore.user?.role || '').toLowerCase() === 'admin'

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'login' })
  } else if (to.meta.guest && authStore.isAuthenticated) {
    next({ name: 'dashboard' })
  } else if (to.meta.requiresAdmin && !isAdmin) {
    if (typeof window !== 'undefined') {
      window.alert('当前账号无权访问该页面')
    }
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router
