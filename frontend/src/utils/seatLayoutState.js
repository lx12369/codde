import api from '@/api'
import { ref } from 'vue'
import { createDefaultSeatLayoutConfig, normalizeSeatLayoutConfig } from '@/utils/seatLayout'

const seatLayoutConfig = ref(createDefaultSeatLayoutConfig())
let pendingLoadPromise = null

function unwrapData(response, fallback) {
  if (response && typeof response === 'object' && 'data' in response) {
    return response.data ?? fallback
  }
  return response ?? fallback
}

export function useSeatLayoutConfigState() {
  return {
    seatLayoutConfig,
    loadSeatLayoutConfig,
    applySeatLayoutConfig,
    resetSeatLayoutConfig
  }
}

export async function loadSeatLayoutConfig(force = false) {
  if (!force && pendingLoadPromise) {
    return pendingLoadPromise
  }

  pendingLoadPromise = (async () => {
    try {
      const response = await api.get('/seat-layout-config')
      const payload = unwrapData(response, {})
      seatLayoutConfig.value = normalizeSeatLayoutConfig(payload)
      return seatLayoutConfig.value
    } catch (error) {
      seatLayoutConfig.value = createDefaultSeatLayoutConfig()
      throw error
    } finally {
      pendingLoadPromise = null
    }
  })()

  return pendingLoadPromise
}

export function applySeatLayoutConfig(rawConfig = null) {
  seatLayoutConfig.value = normalizeSeatLayoutConfig(rawConfig)
  return seatLayoutConfig.value
}

export function resetSeatLayoutConfig() {
  seatLayoutConfig.value = createDefaultSeatLayoutConfig()
  return seatLayoutConfig.value
}
