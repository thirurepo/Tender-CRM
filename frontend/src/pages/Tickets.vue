<!--
  The support queue.

  Modelled on Deals.vue / Leads.vue, and deliberately thinner than either. All
  three get their data from crm/api/doc.py's `get_data`, which takes an
  arbitrary doctype string and asks that doctype's controller for its defaults —
  so list, filter, sort, saved views, group-by and kanban all work here with no
  backend of their own. See tender_crm/tender_crm/doctype/ticket/ticket.py.

  Tickets are internal. Nothing on this screen is visible to a client; a ticket
  merely points at one.
-->
<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs v-model="viewControls" routeName="Tickets" />
    </template>
    <template #right-header>
      <CustomActions
        v-if="ticketsListView?.customListActions"
        :actions="ticketsListView.customListActions"
      />
      <Button
        variant="solid"
        :label="__('Create')"
        iconLeft="plus"
        @click="createTicket()"
      />
    </template>
  </LayoutHeader>
  <ViewControls
    ref="viewControls"
    v-model="tickets"
    v-model:loadMore="loadMore"
    v-model:resizeColumn="triggerResize"
    v-model:updatedPageCount="updatedPageCount"
    doctype="Ticket"
    :options="{
      allowedViews: ['list', 'group_by', 'kanban'],
    }"
  />
  <KanbanView
    v-if="route.params.viewType == 'kanban'"
    v-model="tickets"
    :options="{
      getRoute: (row) => ({
        name: 'Ticket',
        params: { ticketId: row.name },
        query: { view: route.query.view, viewType: route.params.viewType },
      }),
      onNewClick: (column) => onNewClick(column),
    }"
    @update="(data) => viewControls.updateKanbanSettings(data)"
    @loadMore="(columnName) => viewControls.loadMoreKanban(columnName)"
  >
    <template #title="{ titleField, itemName }">
      <div class="flex items-center gap-2">
        <div v-if="titleField === 'status'">
          <IndicatorIcon :class="getRow(itemName, titleField).color" />
        </div>
        <div v-else-if="titleField === 'priority'">
          <IndicatorIcon :class="getRow(itemName, titleField).color" />
        </div>
        <div
          v-else-if="
            titleField === 'organization' && getRow(itemName, titleField).label
          "
        >
          <Avatar
            class="flex items-center"
            :label="getRow(itemName, titleField).label"
            size="sm"
          />
        </div>
        <div
          v-if="['modified', 'creation', 'opening_date'].includes(titleField)"
          class="truncate text-base"
        >
          <Tooltip :text="getRow(itemName, titleField).label">
            <div>{{ getRow(itemName, titleField).timeAgo }}</div>
          </Tooltip>
        </div>
        <div
          v-else-if="getRow(itemName, titleField).label"
          class="truncate text-base"
        >
          {{ getRow(itemName, titleField).label }}
        </div>
        <div v-else class="text-ink-gray-4">{{ __('No Title') }}</div>
      </div>
    </template>
    <template #fields="{ fieldName, itemName }">
      <div
        v-if="getRow(itemName, fieldName).label"
        class="truncate flex items-center gap-2"
      >
        <div v-if="['status', 'priority'].includes(fieldName)">
          <IndicatorIcon :class="getRow(itemName, fieldName).color" />
        </div>
        <div v-else-if="fieldName === 'organization'">
          <Avatar
            class="flex items-center"
            :label="getRow(itemName, fieldName).label"
            size="xs"
          />
        </div>
        <div
          v-if="['modified', 'creation', 'opening_date'].includes(fieldName)"
          class="truncate text-base"
        >
          <Tooltip :text="getRow(itemName, fieldName).label">
            <div>{{ getRow(itemName, fieldName).timeAgo }}</div>
          </Tooltip>
        </div>
        <div
          v-else-if="fieldName === '_assign'"
          class="flex items-center truncate"
        >
          <MultipleAvatar
            :avatars="getRow(itemName, fieldName).label"
            size="xs"
          />
        </div>
        <div v-else class="truncate text-base">
          {{ getRow(itemName, fieldName).label }}
        </div>
      </div>
    </template>
  </KanbanView>
  <TicketsListView
    v-else-if="tickets.data && rows.length"
    ref="ticketsListView"
    v-model="tickets.data.page_length_count"
    v-model:list="tickets"
    :rows="rows"
    :columns="columns"
    :options="{
      showTooltip: false,
      resizeColumn: true,
      rowCount: tickets.data.row_count,
      totalCount: tickets.data.total_count,
    }"
    @loadMore="() => loadMore++"
    @columnWidthUpdated="() => triggerResize++"
    @updatePageCount="(count) => (updatedPageCount = count)"
    @applyFilter="(data) => viewControls.applyFilter(data)"
    @applyLikeFilter="(data) => viewControls.applyLikeFilter(data)"
    @likeDoc="(data) => viewControls.likeDoc(data)"
    @selectionsChanged="
      (selections) => viewControls.updateSelections(selections)
    "
  />
  <EmptyState
    v-else-if="tickets.data && !rows.length"
    name="Tickets"
    :icon="TicketsIcon"
  />
</template>

<script setup>
import ViewBreadcrumbs from '@/components/ViewBreadcrumbs.vue'
import MultipleAvatar from '@/components/MultipleAvatar.vue'
import CustomActions from '@/components/CustomActions.vue'
import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import TicketsIcon from '@/components/Icons/TicketsIcon.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import TicketsListView from '@/components/ListViews/TicketsListView.vue'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import KanbanView from '@/components/Kanban/KanbanView.vue'
import ViewControls from '@/components/ViewControls.vue'
import { useDoctypeModal } from '@/composables/doctypeModal'
import { usersStore } from '@/stores/users'
import { ticketStatusesStore } from '@/stores/ticketStatuses'
import { formatDate } from '@/utils'
import { timestampCell } from '@/composables/useTimelinePreferences'
import { Avatar, Tooltip } from 'frappe-ui'
import { useRoute } from 'vue-router'
import { ref, computed, h } from 'vue'

const { getUser } = usersStore()
const { getTicketStatus, getTicketPriority } = ticketStatusesStore()
const { showModal } = useDoctypeModal()

const route = useRoute()

const ticketsListView = ref(null)

// tickets data is loaded in the ViewControls component
const tickets = ref({})
const loadMore = ref(1)
const triggerResize = ref(1)
const updatedPageCount = ref(20)
const viewControls = ref(null)

function getRow(name, field) {
  function getValue(value) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return value
    }
    return { label: value }
  }
  return getValue(rows.value?.find((row) => row.name == name)[field])
}

const rows = computed(() => {
  if (!tickets.value?.data?.data) return []
  if (tickets.value.data.view_type === 'group_by') {
    if (!tickets.value?.data.group_by_field?.fieldname) return []
    return getGroupedByRows(
      tickets.value?.data.data,
      tickets.value?.data.group_by_field,
      tickets.value.data.columns,
    )
  } else if (tickets.value.data.view_type === 'kanban') {
    return getKanbanRows(tickets.value.data.data, tickets.value.data.fields)
  } else {
    return parseRows(tickets.value?.data.data, tickets.value.data.columns)
  }
})

const columns = computed(() => {
  let _columns = tickets.value?.data?.columns || []

  // Set align right for last column
  if (_columns.length) {
    _columns = _columns.map((col, index) => {
      if (index === _columns.length - 1) {
        return { ...col, align: 'right' }
      }
      return col
    })
  }

  return _columns
})

function getGroupedByRows(listRows, groupByField, columns) {
  let groupedRows = []

  groupByField.options?.forEach((option) => {
    let filteredRows

    if (!option) {
      filteredRows = listRows.filter((row) => !row[groupByField.fieldname])
    } else {
      filteredRows = listRows.filter(
        (row) => row[groupByField.fieldname] == option,
      )
    }

    let groupDetail = {
      label: groupByField.label,
      group: option || __(' '),
      collapsed: false,
      rows: parseRows(filteredRows, columns),
    }
    if (groupByField.fieldname == 'status') {
      groupDetail.icon = () =>
        h(IndicatorIcon, {
          class: getTicketStatus(option)?.color,
        })
    }
    groupedRows.push(groupDetail)
  })

  return groupedRows || listRows
}

function getKanbanRows(data, columns) {
  let _rows = []
  data.forEach((column) => {
    column.data?.forEach((row) => {
      _rows.push(row)
    })
  })
  return parseRows(_rows, columns)
}

function parseRows(rows, columns = []) {
  let view_type = tickets.value.data.view_type
  let key = view_type === 'kanban' ? 'fieldname' : 'key'
  let type = view_type === 'kanban' ? 'fieldtype' : 'type'

  return rows.map((ticket) => {
    let _rows = {}
    tickets.value?.data.rows.forEach((row) => {
      _rows[row] = ticket[row]

      let fieldType = columns?.find((col) => (col[key] || col.value) == row)?.[
        type
      ]

      if (
        fieldType &&
        ['Date', 'Datetime'].includes(fieldType) &&
        !['modified', 'creation', 'opening_date'].includes(row)
      ) {
        _rows[row] = formatDate(ticket[row], '', true, fieldType == 'Datetime')
      }

      if (row == 'status') {
        _rows[row] = {
          label: ticket.status,
          color: getTicketStatus(ticket.status)?.color,
        }
      } else if (row == 'priority') {
        _rows[row] = {
          label: ticket.priority,
          color: getTicketPriority(ticket.priority)?.color,
        }
      } else if (row == 'assigned_agent') {
        _rows[row] = {
          label: ticket.assigned_agent && getUser(ticket.assigned_agent).full_name,
          ...(ticket.assigned_agent && getUser(ticket.assigned_agent)),
        }
      } else if (row == '_assign') {
        let assignees = JSON.parse(ticket._assign || '[]')
        _rows[row] = assignees.map((user) => ({
          name: user,
          image: getUser(user).user_image,
          label: getUser(user).full_name,
        }))
      } else if (['modified', 'creation', 'opening_date'].includes(row)) {
        _rows[row] = timestampCell(ticket[row])
      }
    })
    return _rows
  })
}

// Create goes through the shared DoctypeModal rather than a bespoke
// TicketModal: crm generates a Quick Entry layout for any doctype that has no
// saved one, so there is nothing for a ticket-specific modal to add yet.
function createTicket(defaults = {}) {
  showModal({ doctype: 'Ticket', title: 'Ticket', defaults })
}

function onNewClick(column) {
  let column_field = tickets.value.params.column_field
  createTicket(column_field ? { [column_field]: column.column.name } : {})
}
</script>
