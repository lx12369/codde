const STORAGE_MODE_KEY = 'auth_storage_mode'
const TOKEN_KEY = 'token'
const USER_KEY = 'user'

const MODE_LOCAL = 'local'
const MODE_SESSION = 'session'
const VALID_MODES = [MODE_LOCAL, MODE_SESSION]

function canUseStorage() {
  return typeof window !== 'undefined'
}

function readStorageMode() {
  if (!canUseStorage()) return ''

  const sessionMode = sessionStorage.getItem(STORAGE_MODE_KEY)
  if (VALID_MODES.includes(sessionMode)) return sessionMode

  const localMode = localStorage.getItem(STORAGE_MODE_KEY)
  if (VALID_MODES.includes(localMode)) return localMode

  return ''
}

function readTokenByMode(mode) {
  if (!canUseStorage()) return ''
  if (mode === MODE_LOCAL) return localStorage.getItem(TOKEN_KEY) || ''
  if (mode === MODE_SESSION) return sessionStorage.getItem(TOKEN_KEY) || ''
  return ''
}

function readUserByMode(mode) {
  if (!canUseStorage()) return null

  const raw = mode === MODE_LOCAL
    ? localStorage.getItem(USER_KEY)
    : sessionStorage.getItem(USER_KEY)

  if (!raw) return null

  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function clearAuthStorage() {
  if (!canUseStorage()) return

  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(STORAGE_MODE_KEY)

  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
  sessionStorage.removeItem(STORAGE_MODE_KEY)
}

export function saveAuthSession(token, user, rememberMe = false) {
  if (!canUseStorage()) return

  clearAuthStorage()

  const mode = rememberMe ? MODE_LOCAL : MODE_SESSION
  const targetStorage = rememberMe ? localStorage : sessionStorage

  targetStorage.setItem(TOKEN_KEY, token)
  targetStorage.setItem(USER_KEY, JSON.stringify(user))
  targetStorage.setItem(STORAGE_MODE_KEY, mode)
}

export function getAuthToken() {
  if (!canUseStorage()) return ''

  const mode = readStorageMode()
  if (mode) {
    return readTokenByMode(mode)
  }

  // Backward compatibility: prefer session token first to avoid stale remembered token shadowing.
  const sessionToken = sessionStorage.getItem(TOKEN_KEY)
  if (sessionToken) return sessionToken

  return localStorage.getItem(TOKEN_KEY) || ''
}

export function getAuthUser() {
  if (!canUseStorage()) return null

  const mode = readStorageMode()
  if (mode) {
    return readUserByMode(mode)
  }

  // Backward compatibility with old mixed storage states.
  const sessionRaw = sessionStorage.getItem(USER_KEY)
  if (sessionRaw) {
    try {
      return JSON.parse(sessionRaw)
    } catch {
      // fall through
    }
  }

  const localRaw = localStorage.getItem(USER_KEY)
  if (!localRaw) return null

  try {
    return JSON.parse(localRaw)
  } catch {
    return null
  }
}

export function readAuthSession() {
  return {
    token: getAuthToken(),
    user: getAuthUser()
  }
}

