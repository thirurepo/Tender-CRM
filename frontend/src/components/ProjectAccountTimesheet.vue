<!--
  The Timesheet tab of a Project Account: hours per developer for a period.

  Kept out of Activities.vue on purpose. That component is the vendor timeline
  and treats any tab name it does not know as the Activity feed; this tab has
  nothing to do with a timeline, so ProjectAccount.vue swaps this component in
  for it instead. Data comes from
  tender_crm.api.project_account_timesheet.get_project_account_timesheet.

  Period presets fill From/To; editing either date by hand switches the period
  to "Custom" so the dropdown never claims a range the dates no longer match.
  Weeks run Monday to Sunday.
-->
<template>
  <div class="flex flex-1 flex-col gap-5 overflow-auto px-3 py-5 sm:px-10">
    <div class="flex flex-wrap items-end gap-3">
      <div class="w-44">
        <div class="mb-1 text-xs text-ink-gray-5">{{ __('Period') }}</div>
        <FormControl
          type="select"
          :modelValue="period"
          :options="periodOptions"
          @update:modelValue="setPeriod"
        />
      </div>
      <div class="w-40">
        <div class="mb-1 text-xs text-ink-gray-5">{{ __('From') }}</div>
        <DatePicker
          :value="fromDate"
          :clearable="false"
          :format="'MMM D, YYYY'"
          @update:modelValue="(v) => setDate('from', v)"
        />
      </div>
      <div class="w-40">
        <div class="mb-1 text-xs text-ink-gray-5">{{ __('To') }}</div>
        <DatePicker
          :value="toDate"
          :clearable="false"
          :format="'MMM D, YYYY'"
          @update:modelValue="(v) => setDate('to', v)"
        />
      </div>
    </div>

    <div
      v-if="timesheet.error"
      class="rounded border border-outline-red-2 px-4 py-3 text-sm text-ink-red-4"
    >
      {{ timesheet.error.messages?.[0] || __('Could not load the timesheet') }}
    </div>

    <template v-else-if="data">
      <div class="flex flex-wrap items-baseline gap-x-8 gap-y-2 border-b pb-4">
        <div>
          <div class="text-xs text-ink-gray-5">{{ __('Account') }}</div>
          <div class="text-base font-medium text-ink-gray-9">
            {{ data.account || '—' }}
          </div>
        </div>
        <div>
          <div class="text-xs text-ink-gray-5">{{ __('Project') }}</div>
          <div class="text-base font-medium text-ink-gray-9">
            {{ data.project || '—' }}
          </div>
        </div>
        <div>
          <div class="text-xs text-ink-gray-5">{{ __('Total hours') }}</div>
          <div class="text-base font-medium text-ink-gray-9">
            {{ formatHours(data.total_hours) }}
          </div>
        </div>
      </div>

      <div
        v-if="data.no_account"
        class="py-10 text-center text-sm text-ink-gray-5"
      >
        {{ __('Set an Account on this project account to see its hours.') }}
      </div>
      <div
        v-else-if="!data.developers.length"
        class="py-10 text-center text-sm text-ink-gray-5"
      >
        {{ __('No hours were logged for this period.') }}
      </div>
      <table v-else class="w-full max-w-2xl text-base">
        <thead>
          <tr class="border-b text-left text-sm text-ink-gray-5">
            <th class="py-2 pr-4 font-normal">{{ __('Developer') }}</th>
            <th class="py-2 text-right font-normal">{{ __('Total hours') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="dev in data.developers"
            :key="dev.employee"
            class="border-b text-ink-gray-8"
          >
            <td class="py-2 pr-4">{{ dev.employee_name }}</td>
            <td class="py-2 text-right tabular-nums">
              {{ formatHours(dev.hours) }}
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="font-medium text-ink-gray-9">
            <td class="py-2 pr-4">{{ __('Total') }}</td>
            <td class="py-2 text-right tabular-nums">
              {{ formatHours(data.total_hours) }}
            </td>
          </tr>
        </tfoot>
      </table>
    </template>

    <div v-else class="py-10 text-center text-sm text-ink-gray-5">
      {{ __('Loading…') }}
    </div>
  </div>
</template>

<script setup>
import { createResource, dayjs, DatePicker, FormControl } from 'frappe-ui'
import { computed, ref, watch } from 'vue'

const props = defineProps({
  projectAccountId: { type: String, required: true },
})

const DATE_FORMAT = 'YYYY-MM-DD'

// Monday of the week containing `d` (dayjs's own week starts on Sunday).
const weekStart = (d) => d.subtract((d.day() + 6) % 7, 'day')

// Each preset returns [from, to] as dayjs values, evaluated when picked so
// "current week" is always relative to today, not to when the page loaded.
const PERIODS = {
  'Current week': () => {
    const start = weekStart(dayjs())
    return [start, start.add(6, 'day')]
  },
  'Last week': () => {
    const start = weekStart(dayjs()).subtract(7, 'day')
    return [start, start.add(6, 'day')]
  },
  'Current month': () => [dayjs().startOf('month'), dayjs().endOf('month')],
  'Last month': () => {
    const m = dayjs().subtract(1, 'month')
    return [m.startOf('month'), m.endOf('month')]
  },
  'Last 3 months': () => [dayjs().subtract(3, 'month'), dayjs()],
  'Last 1 year': () => [dayjs().subtract(1, 'year'), dayjs()],
}

const periodOptions = [
  ...Object.keys(PERIODS).map((p) => ({ label: __(p), value: p })),
  { label: __('Custom'), value: 'Custom' },
]

const rangeOf = (name) => PERIODS[name]().map((d) => d.format(DATE_FORMAT))

const period = ref('Current week')
const [initialFrom, initialTo] = rangeOf(period.value)
const fromDate = ref(initialFrom)
const toDate = ref(initialTo)

function setPeriod(name) {
  period.value = name
  if (name === 'Custom') return
  ;[fromDate.value, toDate.value] = rangeOf(name)
}

function setDate(which, value) {
  if (!value) return
  const date = dayjs(value).format(DATE_FORMAT)
  if (which === 'from') fromDate.value = date
  else toDate.value = date
  period.value = 'Custom'
}

const timesheet = createResource({
  url: 'tender_crm.api.project_account_timesheet.get_project_account_timesheet',
})

const data = computed(() => timesheet.data)

// A reversed range is rejected by the server; skip the round trip and leave
// the last good result showing until the user fixes the dates.
watch(
  [fromDate, toDate, () => props.projectAccountId],
  () => {
    if (fromDate.value > toDate.value) return
    timesheet.submit({
      name: props.projectAccountId,
      from_date: fromDate.value,
      to_date: toDate.value,
    })
  },
  { immediate: true },
)

const formatHours = (h) =>
  (h || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
</script>
