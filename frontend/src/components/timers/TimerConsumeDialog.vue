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
  }
})

const emit = defineEmits(['update:modelValue'])
const customerSelectRef = ref(null)

const packagePlanOptions = computed(() => getTimerPackagePlanOptions(props.modelValue?.timerType))
const tableAreaOptions = TABLE_AREA_OPTIONS
const tableSeatOptions = TABLE_SEAT_OPTIONS
const showSecondSeat = computed(() => isDoublePackagePlan(props.modelValue?.packagePlan))

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
