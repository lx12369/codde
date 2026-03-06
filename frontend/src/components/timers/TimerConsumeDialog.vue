<script setup>
import { computed, ref, watch } from 'vue'
import {
  timerTypeOptions,
  getTimerPackagePlanOptions,
  getDefaultTimerPackagePlan,
  TABLE_AREA_OPTIONS,
  TABLE_SEAT_OPTIONS,
  buildTableNo,
  getRequiredExtraSeatCount,
  getTimerConsumeSeatPayload
} from '@/utils/timerConsume'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true
  },
  errors: {
    type: Object,
    default: () => ({})
  },
  customerOptions: {
    type: Array,
    default: () => []
  },
  enabledMiscItems: {
    type: Array,
    default: () => []
  },
  billingRules: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['update:modelValue'])
const customerSelectRef = ref(null)

const packagePlanOptions = computed(() => getTimerPackagePlanOptions(props.modelValue?.timerType, props.billingRules))
const tableAreaOptions = TABLE_AREA_OPTIONS
const tableSeatOptions = TABLE_SEAT_OPTIONS
const requiredExtraSeatCount = computed(() => getRequiredExtraSeatCount(props.modelValue?.packagePlan, props.billingRules))
const showExtraSeats = computed(() => requiredExtraSeatCount.value > 0)
const extraSeatSelections = computed(() => getTimerConsumeSeatPayload(props.modelValue, props.billingRules).extraTableSelections)
const hasMiscItems = computed(() => props.enabledMiscItems.length > 0)

function patchForm(patch = {}) {
  emit('update:modelValue', {
    ...props.modelValue,
    ...patch
  })
}

function patchTableNo(nextArea, nextSeat) {
  const tableArea = String(nextArea || '').trim().toUpperCase()
  const tableSeat = String(nextSeat || '').trim()
  patchForm({
    tableArea,
    tableSeat,
    tableNo: buildTableNo(tableArea, tableSeat)
  })
}

function getFirstExtraSeatLegacyPatch(nextSelections = null) {
  const seatPayload = getTimerConsumeSeatPayload(
    {
      ...props.modelValue,
      extraTableSelections: nextSelections ?? props.modelValue?.extraTableSelections
    },
    props.billingRules
  )
  const first = seatPayload.extraTableSelections[0] || {}
  return {
    extraTableSelections: seatPayload.extraTableSelections,
    extraTableNos: seatPayload.extraTableNos,
    secondTableArea: first.tableArea || props.modelValue?.tableArea || TABLE_AREA_OPTIONS[0],
    secondTableSeat: first.tableSeat || '',
    secondTableNo: seatPayload.secondTableNo
  }
}

function areExtraSeatSelectionsEqual(left = [], right = []) {
  if (!Array.isArray(left) || !Array.isArray(right)) return false
  if (left.length !== right.length) return false
  return left.every((item, index) => {
    const target = right[index] || {}
    return String(item?.tableArea || '') === String(target.tableArea || '')
      && String(item?.tableSeat || '') === String(target.tableSeat || '')
      && String(item?.tableNo || '') === String(target.tableNo || '')
  })
}

function patchExtraSelections(nextSelections) {
  patchForm(getFirstExtraSeatLegacyPatch(nextSelections))
}

function updateExtraSeatArea(index, value) {
  const list = extraSeatSelections.value.map((item) => ({ ...item }))
  if (!list[index]) return
  const area = String(value || '').trim().toUpperCase()
  list[index] = {
    ...list[index],
    tableArea: area,
    tableNo: buildTableNo(area, list[index].tableSeat)
  }
  patchExtraSelections(list)
}

function updateExtraSeatSeat(index, value) {
  const list = extraSeatSelections.value.map((item) => ({ ...item }))
  if (!list[index]) return
  const seat = String(value || '').trim()
  list[index] = {
    ...list[index],
    tableSeat: seat,
    tableNo: buildTableNo(list[index].tableArea, seat)
  }
  patchExtraSelections(list)
}

function getExtraSeatError(index) {
  return props.errors?.[`extraTableNos.${index}`]
    || (index === 0 ? props.errors?.secondTableNo : '')
    || ''
}

function updateNumberField(field, value) {
  const parsed = Number(value)
  patchForm({
    [field]: Number.isFinite(parsed) && parsed >= 0 ? parsed : 0
  })
}

function createMiscSelectionMap(seed = {}) {
  const source = seed && typeof seed === 'object' ? seed : {}
  const nextMap = {}
  props.enabledMiscItems.forEach((item) => {
    const current = Number(source[item.id])
    const available = getMiscAvailableQuantity(item)
    const normalized = Number.isFinite(current) && current >= 0 ? Math.floor(current) : 0
    nextMap[item.id] = Math.min(available, normalized)
  })
  return nextMap
}

function getMiscAvailableQuantity(item) {
  return Math.max(0, Math.floor(Number(item?.current_stock) || 0))
}

function formatMiscStock(item) {
  return `${getMiscAvailableQuantity(item)}${item?.unit_label || '个'}`
}

function updateMiscSelection(itemId, value) {
  if (!itemId) return
  const currentMap = createMiscSelectionMap(props.modelValue?.miscSelections)
  const item = props.enabledMiscItems.find((entry) => String(entry?.id) === String(itemId))
  const available = getMiscAvailableQuantity(item)
  const parsed = Number(value)
  const normalized = Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : 0
  currentMap[itemId] = Math.min(available, normalized)
  patchForm({
    miscSelections: currentMap
  })
}

function resetMiscSelections() {
  patchForm({
    miscSelections: createMiscSelectionMap({})
  })
}

watch(
  () => props.modelValue?.timerType,
  (nextType) => {
    if (!nextType) {
      patchForm({
        timerType: 'limited',
        packagePlan: getDefaultTimerPackagePlan('limited', props.billingRules)
      })
      return
    }

    const options = getTimerPackagePlanOptions(nextType, props.billingRules)
    const currentPlan = props.modelValue?.packagePlan
    const isCurrentPlanValid = options.some((item) => item.value === currentPlan)

    if (!isCurrentPlanValid) {
      patchForm({
        packagePlan: getDefaultTimerPackagePlan(nextType, props.billingRules)
      })
    }
  },
  { immediate: true }
)

watch(
  () => props.modelValue?.packagePlan,
  () => {
    const expected = getFirstExtraSeatLegacyPatch()
    const currentSelections = Array.isArray(props.modelValue?.extraTableSelections)
      ? props.modelValue.extraTableSelections
      : []
    const currentTableNos = Array.isArray(props.modelValue?.extraTableNos)
      ? props.modelValue.extraTableNos
      : []
    const hasSelectionDiff = !areExtraSeatSelectionsEqual(currentSelections, expected.extraTableSelections)
    const hasTableNoDiff = JSON.stringify(currentTableNos) !== JSON.stringify(expected.extraTableNos)
    const hasLegacyDiff = String(props.modelValue?.secondTableNo || '') !== expected.secondTableNo
      || String(props.modelValue?.secondTableArea || '') !== expected.secondTableArea
      || String(props.modelValue?.secondTableSeat || '') !== expected.secondTableSeat
    if (hasSelectionDiff || hasTableNoDiff || hasLegacyDiff) {
      patchForm(expected)
    }
  }
)

watch(
  () => props.billingRules,
  () => {
    const timerType = props.modelValue?.timerType || 'limited'
    const options = getTimerPackagePlanOptions(timerType, props.billingRules)
    const currentPlan = props.modelValue?.packagePlan
    if (!options.some((item) => item.value === currentPlan)) {
      patchForm({
        packagePlan: getDefaultTimerPackagePlan(timerType, props.billingRules)
      })
    }
    const expected = getFirstExtraSeatLegacyPatch()
    const currentSelections = Array.isArray(props.modelValue?.extraTableSelections)
      ? props.modelValue.extraTableSelections
      : []
    if (!areExtraSeatSelectionsEqual(currentSelections, expected.extraTableSelections)) {
      patchForm(expected)
    }
  },
  { deep: true }
)

watch(
  () => props.modelValue?.tableArea,
  () => {
    const expected = getFirstExtraSeatLegacyPatch()
    const currentSelections = Array.isArray(props.modelValue?.extraTableSelections)
      ? props.modelValue.extraTableSelections
      : []
    if (!areExtraSeatSelectionsEqual(currentSelections, expected.extraTableSelections)) {
      patchForm(expected)
    }
  }
)

function focusFirstField() {
  customerSelectRef.value?.focus()
}

defineExpose({
  focusFirstField
})
</script>

<template>
  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">选择客户</label>
      <select
        ref="customerSelectRef"
        :value="modelValue.customerId"
        :class="[
          'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
          errors.customerId ? 'border-red-500' : 'border-gray-300'
        ]"
        @change="patchForm({ customerId: $event.target.value })"
      >
        <option disabled value="">请选择客户</option>
        <option v-for="customer in customerOptions" :key="customer.id" :value="customer.id">
          {{ customer.name }} ({{ customer.phone }})
        </option>
      </select>
      <p v-if="errors.customerId" class="text-red-500 text-xs mt-1">
        {{ errors.customerId }}
      </p>
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">计时类型</label>
      <select
        :value="modelValue.timerType"
        :class="[
          'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
          errors.timerType ? 'border-red-500' : 'border-gray-300'
        ]"
        @change="patchForm({ timerType: $event.target.value })"
      >
        <option v-for="item in timerTypeOptions" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
      <p v-if="errors.timerType" class="text-red-500 text-xs mt-1">
        {{ errors.timerType }}
      </p>
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">套餐方案</label>
      <select
        :value="modelValue.packagePlan"
        :class="[
          'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
          errors.packagePlan ? 'border-red-500' : 'border-gray-300'
        ]"
        @change="patchForm({ packagePlan: $event.target.value })"
      >
        <option v-for="item in packagePlanOptions" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
      <p v-if="errors.packagePlan" class="text-red-500 text-xs mt-1">
        {{ errors.packagePlan }}
      </p>
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">第1座位</label>
      <div class="grid grid-cols-2 gap-3">
        <select
          :value="modelValue.tableArea"
          :class="[
            'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            errors.tableNo ? 'border-red-500' : 'border-gray-300'
          ]"
          @change="patchTableNo($event.target.value, modelValue.tableSeat)"
        >
          <option v-for="area in tableAreaOptions" :key="area" :value="area">
            {{ area }}桌
          </option>
        </select>
        <select
          :value="modelValue.tableSeat"
          :class="[
            'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            errors.tableNo ? 'border-red-500' : 'border-gray-300'
          ]"
          @change="patchTableNo(modelValue.tableArea, $event.target.value)"
        >
          <option v-for="seat in tableSeatOptions" :key="seat" :value="seat">
            {{ seat }}号
          </option>
        </select>
      </div>
      <p v-if="errors.tableNo" class="text-red-500 text-xs mt-1">
        {{ errors.tableNo }}
      </p>
    </div>

    <div v-if="showExtraSeats" class="space-y-3">
      <div class="text-xs text-slate-600">
        当前套餐需选择 {{ requiredExtraSeatCount }} 个附加座位（总座位 {{ requiredExtraSeatCount + 1 }} 个）
      </div>
      <div v-for="(seat, index) in extraSeatSelections" :key="`extra-seat-${index}`">
        <label class="block text-sm font-medium text-gray-700 mb-1">第{{ index + 2 }}座位</label>
        <div class="grid grid-cols-2 gap-3">
          <select
            :value="seat.tableArea || modelValue.tableArea"
            :class="[
              'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              getExtraSeatError(index) ? 'border-red-500' : 'border-gray-300'
            ]"
            @change="updateExtraSeatArea(index, $event.target.value)"
          >
            <option v-for="area in tableAreaOptions" :key="`extra-area-${index}-${area}`" :value="area">
              {{ area }}桌
            </option>
          </select>
          <select
            :value="seat.tableSeat"
            :class="[
              'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
              getExtraSeatError(index) ? 'border-red-500' : 'border-gray-300'
            ]"
            @change="updateExtraSeatSeat(index, $event.target.value)"
          >
            <option value="">请选择号位</option>
            <option v-for="seatNo in tableSeatOptions" :key="`extra-seat-${index}-${seatNo}`" :value="seatNo">
              {{ seatNo }}号
            </option>
          </select>
        </div>
        <p v-if="getExtraSeatError(index)" class="text-red-500 text-xs mt-1">
          {{ getExtraSeatError(index) }}
        </p>
      </div>
      <p v-if="errors.extraTableNos" class="text-red-500 text-xs mt-1">
        {{ errors.extraTableNos }}
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">大图数量</label>
        <input
          :value="modelValue.largeImages"
          type="number"
          min="0"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          @input="updateNumberField('largeImages', $event.target.value)"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">超量小图</label>
        <input
          :value="modelValue.extraSmallImages"
          type="number"
          min="0"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          @input="updateNumberField('extraSmallImages', $event.target.value)"
        />
      </div>
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">超量大图</label>
        <input
          :value="modelValue.extraLargeImages"
          type="number"
          min="0"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          @input="updateNumberField('extraLargeImages', $event.target.value)"
        />
      </div>
    </div>

    <div v-if="hasMiscItems" class="space-y-3">
      <div class="flex items-center justify-between">
        <h4 class="text-sm font-medium text-gray-700">杂项计费（仅整数）</h4>
        <button
          type="button"
          class="text-xs text-blue-600 hover:text-blue-700"
          @click="resetMiscSelections"
        >
          一键清零
        </button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div v-for="item in enabledMiscItems" :key="item.id">
          <label class="block text-sm font-medium text-gray-700 mb-1">
            {{ item.name }}（¥{{ Number(item.unit_price || 0).toFixed(2) }}/{{ item.unit_label || '个' }}）
          </label>
          <p class="text-xs text-slate-500 mb-1">可用库存：{{ formatMiscStock(item) }}</p>
          <input
            :value="modelValue.miscSelections?.[item.id] ?? 0"
            type="number"
            min="0"
            :max="getMiscAvailableQuantity(item)"
            step="1"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            @input="updateMiscSelection(item.id, $event.target.value)"
          />
        </div>
      </div>
      <p v-if="errors.misc" class="text-red-500 text-xs mt-1">
        {{ errors.misc }}
      </p>
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">备注</label>
      <textarea
        :value="modelValue.notes"
        rows="2"
        class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
        placeholder="开始计时前的备注"
        @input="patchForm({ notes: $event.target.value })"
      ></textarea>
    </div>

    <div class="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
      计时开始后，请前往“正在计时”页面完成结算。
    </div>
  </div>
</template>
