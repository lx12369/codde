export function normalizeRole(role) {
  return String(role || '').trim().toLowerCase()
}

export function isSuperAdminRole(role) {
  return normalizeRole(role) === 'super_admin'
}

export function isAdminRole(role) {
  const normalized = normalizeRole(role)
  return normalized === 'admin' || normalized === 'super_admin'
}

export function getRoleLabel(role) {
  const normalized = normalizeRole(role)
  if (normalized === 'super_admin') return '超级管理员'
  if (normalized === 'admin') return '管理员'
  return '员工'
}
