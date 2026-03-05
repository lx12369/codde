import axios from 'axios'
import { clearAuthStorage, getAuthToken } from '@/utils/authStorage'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  (config) => {
    const token = getAuthToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error.response?.status
    const requestUrl = String(error.config?.url || '')
    const isLoginRequest = requestUrl.includes('/auth/login')

    if (status === 401 && !isLoginRequest) {
      clearAuthStorage()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: (data) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  changePassword: (data) => api.put('/auth/password', data)
}

export const customerApi = {
  getCustomers: (params) => api.get('/customers', { params }),
  getCustomer: (id) => api.get(`/customers/${id}`),
  createCustomer: (data) => api.post('/customers', data),
  updateCustomer: (id, data) => api.put(`/customers/${id}`, data),
  deleteCustomer: (id) => api.delete(`/customers/${id}`),
  getCustomerBalance: (id) => api.get(`/customers/${id}/balance`)
}

export const employeeApi = {
  getEmployees: (params) => api.get('/employees', { params }),
  createEmployee: (data) => api.post('/employees', data),
  updateEmployee: (id, data) => api.put(`/employees/${id}`, data),
  resetEmployeePassword: (id, data) => api.put(`/employees/${id}/reset-password`, data),
  deleteEmployee: (id) => api.delete(`/employees/${id}`)
}

export const transactionApi = {
  getTransactions: (params) => api.get('/transactions', { params }),
  getTransaction: (id) => api.get(`/transactions/${id}`),
  createRecharge: (data) => api.post('/transactions/recharge', data),
  createConsumption: (data) => api.post('/transactions/consumption', data)
}

export const activityApi = {
  getActivities: (params) => api.get('/activities', { params }),
  createActivity: (data) => api.post('/activities', data),
  updateActivity: (id, data) => api.put(`/activities/${id}`, data),
  deleteActivity: (id) => api.delete(`/activities/${id}`)
}

export const billingApi = {
  getBillingRules: () => api.get('/billing-rules'),
  updateBillingRules: (data) => api.put('/billing-rules', data)
}

export const timerApi = {
  getActiveTimers: () => api.get('/active-timers'),
  createTimer: (data) => api.post('/active-timers', data),
  updateTimer: (id, data) => api.put(`/active-timers/${id}`, data),
  deleteTimer: (id) => api.delete(`/active-timers/${id}`)
}

export const dashboardApi = {
  getStats: () => api.get('/dashboard/stats'),
  getWeatherToday: () => api.get('/dashboard/weather/today'),
  getCharts: (params) => api.get('/dashboard/charts', { params }),
  getRecentActivities: (params) => api.get('/dashboard/recent-activities', { params })
}

export const beadInventoryApi = {
  getMaterials: (params) => api.get('/bead-inventory/materials', { params }),
  importMardPalette: () => api.post('/bead-inventory/materials/import-mard'),
  batchUpdateConversionStandard: (data) => api.post('/bead-inventory/materials/batch-conversion-standard', data),
  batchUpdateMarketPrice: (data) => api.post('/bead-inventory/materials/batch-market-price', data),
  batchUpdateSafeStockByCommonColor: (data) => api.post('/bead-inventory/materials/batch-safe-stock-by-common-color', data),
  createMaterial: (data) => api.post('/bead-inventory/materials', data),
  updateMaterial: (id, data) => api.put(`/bead-inventory/materials/${id}`, data),
  deleteMaterial: (id) => api.delete(`/bead-inventory/materials/${id}`),
  getBalances: (params) => api.get('/bead-inventory/balances', { params }),
  createInbound: (data) => api.post('/bead-inventory/inbound', data),
  createOutbound: (data) => api.post('/bead-inventory/outbound', data),
  createStocktake: (data) => api.post('/bead-inventory/stocktake', data),
  getLedger: (params) => api.get('/bead-inventory/ledger', { params }),
  getAlerts: () => api.get('/bead-inventory/alerts')
}

export const dataApi = {
  backupData: () => api.get('/data/backup'),
  restoreData: (data) => api.post('/data/restore', data),
  clearData: () => api.delete('/data/clear')
}

export default api
