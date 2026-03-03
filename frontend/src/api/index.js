import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token')
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
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      sessionStorage.removeItem('token')
      sessionStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login: (data) => api.post('/auth/login', data),
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
  getCharts: (params) => api.get('/dashboard/charts', { params }),
  getRecentActivities: (params) => api.get('/dashboard/recent-activities', { params })
}

export const dataApi = {
  backupData: () => api.get('/data/backup'),
  restoreData: (data) => api.post('/data/restore', data),
  clearData: () => api.delete('/data/clear')
}

export default api
