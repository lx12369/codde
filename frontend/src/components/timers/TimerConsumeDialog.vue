<script setup>
import { computed, ref, watch } from 'vue'
import {
  timerTypeOptions,
  getTimerPackagePlanOptions,
  getDefaultTimerPackagePlan,
  TABLE_AREA_OPTIONS,
  TABLE_SEAT_OPTIONS,
  buildTableNo,
  isDoublePackagePlan
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
  }
})

const emit = defineEmits(['update:modelValue'])
const customerSelectRef = ref(null)

const packagePlanOptions = computed(() => getTimerPackagePlanOptions(props.modelValue?.timerType))
const tableAreaOptions = TABLE_AREA_OPTIONS
const tableSeatOptions = TABLE_SEAT_OPTIONS
const showSecondSeat = computed(() => isDoublePackagePlan(props.modelValue?.packagePlan))
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
        packagePlan: getDefaultTimerPackagePlan('limited')
      })
      return
    }

    const options = getTimerPackagePlanOptions(nextType)
    const currentPlan = props.modelValue?.packagePlan
    const isCurrentPlanValid = options.some((item) => item.value === currentPlan)

    if (!isCurrentPlanValid) {
      patchForm({
        packagePlan: getDefaultTimerPackagePlan(nextType)
      })
    }
  },
  { immediate: true }
)

watch(
  () => props.modelValue?.packagePlan,
  (nextPlan) => {
    if (isDoublePackagePlan(nextPlan)) return
    patchForm({
      secondTableSeat: '',
      secondTableNo: ''
    })
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
      <label class="block text-sm font-medium text-gray-700 mb-1">桌号</label>
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

    <div v-if="showSecondSeat">
      <label class="block text-sm font-medium text-gray-700 mb-1">第二座位（双人套餐）</label>
      <div class="grid grid-cols-2 gap-3">
        <select
          :value="modelValue.secondTableArea || modelValue.tableArea"
          :class="[
            'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            errors.secondTableNo ? 'border-red-500' : 'border-gray-300'
          ]"
          @change="patchForm({
            secondTableArea: String($event.target.value || '').trim().toUpperCase(),
            secondTableNo: buildTableNo(String($event.target.value || '').trim().toUpperCase(), modelValue.secondTableSeat)
          })"
        >
          <option v-for="area in tableAreaOptions" :key="`second-${area}`" :value="area">
            {{ area }}桌
          </option>
        </select>
        <select
          :value="modelValue.secondTableSeat"
          :class="[
            'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            errors.secondTableNo ? 'border-red-500' : 'border-gray-300'
          ]"
          @change="patchForm({
            secondTableArea: modelValue.secondTableArea || modelValue.tableArea,
            secondTableSeat: $event.target.value,
            secondTableNo: buildTableNo(modelValue.secondTableArea || modelValue.tableArea, $event.target.value)
          })"
        >
          <option value="">请选择号位</option>
          <option v-for="seat in tableSeatOptions" :key="`second-seat-${seat}`" :value="seat">
            {{ seat }}号
          </option>
        </select>
      </div>
      <p v-if="errors.secondTableNo" class="text-red-500 text-xs mt-1">
        {{ errors.secondTableNo }}
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
