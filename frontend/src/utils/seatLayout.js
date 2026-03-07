export const TABLE_AREA_OPTIONS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'.split('')
export const TABLE_SEAT_OPTIONS = Array.from({ length: 100 }, (_, index) => String(index + 1))
export const TABLE_NO_PATTERN = /^([A-HJ-NP-Za-hj-np-z])桌([1-9]|[1-9][0-9]|100)号$/
export const SEAT_LAYOUT_VERSION = 1
export const FIXED_SEAT_LAYOUT_SECTIONS = [
  {
    key: 'living',
    title: '客厅',
    subtitle: '大厅区域',
    tables: [
      { area: 'F', seatCount: 4, seatColumns: 2, shape: 'square' },
      { area: 'C', seatCount: 6, seatColumns: 3, shape: 'wide' },
      { area: 'E', seatCount: 4, seatColumns: 2, shape: 'square' },
      { area: 'B', seatCount: 6, seatColumns: 3, shape: 'wide' },
      { area: 'D', seatCount: 4, seatColumns: 2, shape: 'square' },
      { area: 'A', seatCount: 6, seatColumns: 3, shape: 'wide' }
    ]
  },
  {
    key: 'small',
    title: '小房间',
    subtitle: '私密小间',
    tables: [
      { area: 'G', seatCount: 4, seatColumns: 2, shape: 'wide' },
      { area: 'H', seatCount: 4, seatColumns: 1, shape: 'tall' },
      { area: 'J', seatCount: 2, seatColumns: 2, shape: 'wide' }
    ]
  },
  {
    key: 'garden',
    title: '花园',
    subtitle: '露台区域',
    tables: [
      { area: 'K', seatCount: 6, seatColumns: 3, shape: 'square' },
      { area: 'L', seatCount: 4, seatColumns: 2, shape: 'square' }
    ]
  },
  {
    key: 'upstairs',
    title: '楼上',
    subtitle: '楼上区域',
    tables: [
      { area: 'M', seatCount: 3, seatColumns: 3, shape: 'wide' }
    ]
  }
]

function normalizeTableArea(value = '', fallback = TABLE_AREA_OPTIONS[0]) {
  const normalized = String(value || '').trim().toUpperCase()
  if (TABLE_AREA_OPTIONS.includes(normalized)) return normalized
  if (fallback === '') return ''
  return TABLE_AREA_OPTIONS.includes(fallback) ? fallback : TABLE_AREA_OPTIONS[0]
}

function normalizeTableSeat(value = '', fallback = '') {
  const normalized = String(value || '').trim()
  if (TABLE_SEAT_OPTIONS.includes(normalized)) return normalized
  const normalizedFallback = String(fallback || '').trim()
  if (TABLE_SEAT_OPTIONS.includes(normalizedFallback)) {
    return normalizedFallback
  }
  return ''
}

export function buildTableNo(area = '', seat = '') {
  const normalizedArea = normalizeTableArea(area, '')
  const normalizedSeat = normalizeTableSeat(seat, '')
  if (!normalizedArea || !normalizedSeat) return ''
  return `${normalizedArea}桌${normalizedSeat}号`
}

export function normalizeTableNo(value = '') {
  const raw = String(value || '').trim()
  const matched = raw.match(TABLE_NO_PATTERN)
  if (!matched) return raw
  return buildTableNo(matched[1], matched[2])
}

export function isValidTableNo(value = '') {
  return TABLE_NO_PATTERN.test(normalizeTableNo(value))
}

export function parseTableNoParts(
  tableNo = '',
  fallbackArea = TABLE_AREA_OPTIONS[0],
  fallbackSeat = TABLE_SEAT_OPTIONS[0]
) {
  const normalizedFallbackArea = normalizeTableArea(fallbackArea, TABLE_AREA_OPTIONS[0])
  const normalizedFallbackSeat = normalizeTableSeat(fallbackSeat, '')
  const matched = normalizeTableNo(tableNo).match(TABLE_NO_PATTERN)
  if (!matched) {
    return {
      tableArea: normalizedFallbackArea,
      tableSeat: normalizedFallbackSeat
    }
  }
  return {
    tableArea: normalizeTableArea(matched[1], normalizedFallbackArea),
    tableSeat: normalizeTableSeat(matched[2], normalizedFallbackSeat)
  }
}

export function buildSeatSlotKey(sectionKey = '', tableKey = '', seatIndex = '') {
  return `${String(sectionKey || '').trim()}:${normalizeTableArea(tableKey, '')}:${String(seatIndex || '').trim()}`
}

const FIXED_SEAT_SLOTS = FIXED_SEAT_LAYOUT_SECTIONS.flatMap((section) => (
  section.tables.flatMap((table) => (
    Array.from({ length: table.seatCount }, (_, index) => {
      const seatIndex = String(index + 1)
      const slotKey = buildSeatSlotKey(section.key, table.area, seatIndex)
      return {
        slotKey,
        sectionKey: section.key,
        tableKey: table.area,
        seatIndex,
        defaultTableArea: table.area,
        defaultTableSeat: seatIndex,
        defaultTableNo: buildTableNo(table.area, seatIndex)
      }
    })
  ))
))

const FIXED_SEAT_SLOT_MAP = FIXED_SEAT_SLOTS.reduce((acc, slot) => {
  acc[slot.slotKey] = slot
  return acc
}, {})

export function createDefaultSeatLayoutConfig() {
  return {
    version: SEAT_LAYOUT_VERSION,
    slots: FIXED_SEAT_SLOTS.reduce((acc, slot) => {
      acc[slot.slotKey] = {
        tableArea: slot.defaultTableArea,
        tableSeat: slot.defaultTableSeat
      }
      return acc
    }, {})
  }
}

export function normalizeSeatLayoutConfig(rawConfig = null) {
  const defaultConfig = createDefaultSeatLayoutConfig()
  if (!rawConfig || typeof rawConfig !== 'object' || typeof rawConfig.slots !== 'object') {
    return defaultConfig
  }

  const usedTableNos = new Set()
  const slots = {}

  for (const slot of FIXED_SEAT_SLOTS) {
    const rawSlot = rawConfig.slots?.[slot.slotKey]
    const tableArea = normalizeTableArea(rawSlot?.tableArea, slot.defaultTableArea)
    const tableSeat = normalizeTableSeat(rawSlot?.tableSeat, slot.defaultTableSeat)
    const tableNo = buildTableNo(tableArea, tableSeat)
    if (!tableNo || usedTableNos.has(tableNo)) {
      return defaultConfig
    }
    usedTableNos.add(tableNo)
    slots[slot.slotKey] = {
      tableArea,
      tableSeat
    }
  }

  return {
    version: SEAT_LAYOUT_VERSION,
    slots
  }
}

export function validateSeatLayoutDraft(rawConfig = null) {
  const errors = {}
  const slots = rawConfig && typeof rawConfig === 'object' && typeof rawConfig.slots === 'object'
    ? rawConfig.slots
    : {}
  const occupied = new Map()

  FIXED_SEAT_SLOTS.forEach((slot) => {
    const rawSlot = slots[slot.slotKey] || {}
    const tableArea = String(rawSlot.tableArea || '').trim().toUpperCase()
    const tableSeat = String(rawSlot.tableSeat || '').trim()

    if (!TABLE_AREA_OPTIONS.includes(tableArea) || !TABLE_SEAT_OPTIONS.includes(tableSeat)) {
      errors[slot.slotKey] = '编号格式不正确'
      return
    }

    const tableNo = buildTableNo(tableArea, tableSeat)
    if (!tableNo) {
      errors[slot.slotKey] = '编号格式不正确'
      return
    }

    if (occupied.has(tableNo)) {
      errors[slot.slotKey] = `编号重复：${tableArea}${tableSeat}`
      const previousSlotKey = occupied.get(tableNo)
      if (!errors[previousSlotKey]) {
        errors[previousSlotKey] = `编号重复：${tableArea}${tableSeat}`
      }
      return
    }

    occupied.set(tableNo, slot.slotKey)
  })

  return errors
}

export function getSeatOptionList(rawConfig = null) {
  const config = normalizeSeatLayoutConfig(rawConfig)
  return FIXED_SEAT_SLOTS.map((slot) => {
    const assignment = config.slots[slot.slotKey]
    const tableArea = normalizeTableArea(assignment?.tableArea, slot.defaultTableArea)
    const tableSeat = normalizeTableSeat(assignment?.tableSeat, slot.defaultTableSeat)
    const tableNo = buildTableNo(tableArea, tableSeat)
    return {
      slotKey: slot.slotKey,
      sectionKey: slot.sectionKey,
      physicalTableKey: slot.tableKey,
      physicalSeatIndex: slot.seatIndex,
      tableArea,
      tableSeat,
      tableNo,
      shortLabel: `${tableArea}${tableSeat}`,
      label: `${tableArea}桌${tableSeat}号`
    }
  })
}

export function getSeatOptionByTableNo(tableNo = '', rawConfig = null) {
  const normalized = normalizeTableNo(tableNo)
  return getSeatOptionList(rawConfig).find((item) => item.tableNo === normalized) || null
}

export function isConfiguredTableNo(tableNo = '', rawConfig = null) {
  return Boolean(getSeatOptionByTableNo(tableNo, rawConfig))
}

export function getSeatLayoutTablesBySection(sectionKey = '', rawConfig = null) {
  const section = FIXED_SEAT_LAYOUT_SECTIONS.find((item) => item.key === sectionKey)
  if (!section) return []

  const config = normalizeSeatLayoutConfig(rawConfig)

  return section.tables.map((table) => ({
    ...table,
    seats: Array.from({ length: table.seatCount }, (_, index) => {
      const seatIndex = String(index + 1)
      const slotKey = buildSeatSlotKey(section.key, table.area, seatIndex)
      const assignment = config.slots[slotKey] || {}
      const tableArea = normalizeTableArea(assignment.tableArea, table.area)
      const tableSeat = normalizeTableSeat(assignment.tableSeat, seatIndex)
      return {
        slotKey,
        seatNo: seatIndex,
        tableArea,
        tableSeat,
        tableNo: buildTableNo(tableArea, tableSeat),
        displayCode: `${tableArea}${tableSeat}`,
        displayLabel: `${tableArea}桌${tableSeat}号`
      }
    })
  }))
}

export function cloneSeatLayoutConfig(rawConfig = null) {
  return normalizeSeatLayoutConfig(JSON.parse(JSON.stringify(normalizeSeatLayoutConfig(rawConfig))))
}
