<!--
  The tickets raised against one record, for the Tickets tab on the Client,
  Lead and Deal screens.

  Self-contained on purpose: it takes the filter and fetches its own rows, so
  adding the tab to a detail page is three lines there rather than another
  branch in that page's shared `rows` computed. That is what keeps the fork's
  divergence from upstream crm down to the handful of lines that actually have
  to change.

  On the Client screen the filter is the denormalised `organization` field — a
  plain indexed equality, which is the whole reason Ticket carries it rather
  than making every caller walk the Dynamic Link. On Lead and Deal it is the
  polymorphic reference itself, because those two are what the reference names.
-->
<template>
  <div class="flex flex-1 flex-col overflow-hidden">
    <ListView
      v-if="rows.length"
      class="mt-4"
      :columns="columns"
      :rows="rows"
      :options="{
        getRowRoute: (row) => ({
          name: 'Ticket',
          params: { ticketId: row.name },
        }),
        selectable: false,
        showTooltip: false,
      }"
      row-key="name"
    >
      <ListHeader class="mx-3 sm:mx-5">
        <ListHeaderItem
          v-for="column in columns"
          :key="column.key"
          :item="column"
        />
      </ListHeader>
      <ListRows class="mx-3 sm:mx-5" :rows="rows" doctype="Ticket">
        <template #default="{ column, item }">
          <ListRowItem :item="item" class="overflow-hidden">
            <template #prefix>
              <IndicatorIcon
                v-if="['status', 'priority'].includes(column.key)"
                :class="item.color"
              />
            </template>
            <template #default="{ label }">
              <Tooltip v-if="column.key === 'modified'" :text="item.label">
                <div class="truncate text-base">{{ item.timeAgo }}</div>
              </Tooltip>
              <div v-else class="truncate text-base">{{ label }}</div>
            </template>
          </ListRowItem>
        </template>
      </ListRows>
    </ListView>
    <EmptyState v-else :icon="TicketsIcon" :name="__('Tickets')" />
  </div>
</template>

<script setup>
import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import TicketsIcon from '@/components/Icons/TicketsIcon.vue'
import ListRows from '@/components/ListViews/ListRows.vue'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import { ticketStatusesStore } from '@/stores/ticketStatuses'
import { timestampCell } from '@/composables/useTimelinePreferences'
import {
  ListView,
  ListHeader,
  ListHeaderItem,
  ListRowItem,
  Tooltip,
  createListResource,
} from 'frappe-ui'
import { computed } from 'vue'

const props = defineProps({
  // Any filter crm's list API accepts. See the component comment for which one
  // each caller passes.
  filters: { type: Object, required: true },
  // Distinguishes this resource's cache from every other record's.
  cacheKey: { type: [String, Array], required: true },
})

const { getTicketStatus, getTicketPriority } = ticketStatusesStore()

const columns = [
  { label: __('Subject'), key: 'subject', width: '20rem' },
  { label: __('Status'), key: 'status', width: '10rem' },
  { label: __('Priority'), key: 'priority', width: '8rem' },
  { label: __('Last Modified'), key: 'modified', width: '9rem' },
]

const tickets = createListResource({
  type: 'list',
  doctype: 'Ticket',
  cache: ['linked-tickets', props.cacheKey],
  fields: ['name', 'subject', 'status', 'priority', 'modified'],
  filters: props.filters,
  orderBy: 'modified desc',
  pageLength: 20,
  auto: true,
})

const rows = computed(() =>
  (tickets.data || []).map((ticket) => ({
    name: ticket.name,
    subject: ticket.subject,
    status: {
      label: ticket.status,
      color: getTicketStatus(ticket.status)?.color,
    },
    priority: {
      label: ticket.priority,
      color: getTicketPriority(ticket.priority)?.color,
    },
    modified: timestampCell(ticket.modified),
  })),
)

defineExpose({ count: computed(() => tickets.data?.length ?? 0) })
</script>
