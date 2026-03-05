function normalizeServerDateTime(value) {
  if (typeof value !== 'string') return value

  const text = value.trim()
  if (!text) return text

  const hasTimezone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(text)
  const isDateTime = /^\d{4}-\d{2}-\d{2}T/.test(text)

  if (isDateTime && !hasTimezone) {
    // Backend stores UTC as naive datetime; append Z so browser parses it as UTC.
    return `${text}Z`
  }

  return text
}

export function toServerDate(value) {
  if (!value) return null
  const date = new Date(normalizeServerDateTime(value))
  if (Number.isNaN(date.getTime())) return null
  return date
}

export function formatServerDateTime(value, localeOptions = {}) {
  const date = toServerDate(value)
  if (!date) return '-'

  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    ...localeOptions
  })
}
