<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs v-model="viewControls" routeName="Organizations" />
    </template>
    <template #right-header>
      <CustomActions
        v-if="organizationsListView?.customListActions"
        :actions="organizationsListView.customListActions"
      />
      <Button
        variant="solid"
        :label="__('Create')"
        iconLeft="plus"
        @click="showOrganizationModal = true"
      />
    </template>
  </LayoutHeader>
  <ViewControls
    ref="viewControls"
    v-model="organizations"
    v-model:loadMore="loadMore"
    v-model:resizeColumn="triggerResize"
    v-model:updatedPageCount="updatedPageCount"
    doctype="CRM Organization"
    :options="{
      allowedViews: ['list', 'group_by', 'kanban'],
      kanban: {
        columnField: 'tsi_client_status',
        titleField: 'organization_name',
        fields: kanbanFields,
      },
    }"
  />
  <KanbanView
    v-if="route.params.viewType == 'kanban'"
    v-model="organizations"
    :options="{
      getRoute: (row) => ({
        name: 'Organization',
        params: { organizationId: row.name },
        query: { view: route.query.view, viewType: route.params.viewType },
      }),
      onNewClick: (column) => onNewClick(column),
    }"
    @update="(data) => viewControls.updateKanbanSettings(data)"
    @loadMore="(columnName) => viewControls.loadMoreKanban(columnName)"
  >
    <template #title="{ titleField, itemName }">
      <div class="flex items-center gap-2">
        <div
          v-if="
            titleField === 'organization_name' &&
            getRow(itemName, titleField).label
          "
        >
          <Avatar
            class="flex items-center"
            :image="getRow(itemName, titleField).logo"
            :label="getRow(itemName, titleField).label"
            size="sm"
          />
        </div>
        <div
          v-else-if="
            titleField === 'tsi_account_owner' &&
            getRow(itemName, titleField).full_name
          "
        >
          <Avatar
            class="flex items-center"
            :image="getRow(itemName, titleField).user_image"
            :label="getRow(itemName, titleField).full_name"
            size="sm"
          />
        </div>
        <div
          v-if="['modified', 'creation'].includes(titleField)"
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
        <div v-if="fieldName === 'tsi_account_owner'">
          <Avatar
            v-if="getRow(itemName, fieldName).full_name"
            class="flex items-center"
            :image="getRow(itemName, fieldName).user_image"
            :label="getRow(itemName, fieldName).full_name"
            size="xs"
          />
        </div>
        <div
          v-if="['modified', 'creation'].includes(fieldName)"
          class="truncate text-base"
        >
          <Tooltip :text="getRow(itemName, fieldName).label">
            <div>{{ getRow(itemName, fieldName).timeAgo }}</div>
          </Tooltip>
        </div>
        <div v-else class="truncate text-base">
          {{ getRow(itemName, fieldName).label }}
        </div>
      </div>
    </template>
  </KanbanView>
  <OrganizationsListView
    v-else-if="organizations.data && rows.length"
    ref="organizationsListView"
    v-model="organizations.data.page_length_count"
    v-model:list="organizations"
    :rows="rows"
    :columns="columns"
    :options="{
      showTooltip: false,
      resizeColumn: true,
      rowCount: organizations.data.row_count,
      totalCount: organizations.data.total_count,
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
    v-else-if="organizations.data && !rows.length"
    name="Organizations"
    :icon="OrganizationsIcon"
  />
  <OrganizationModal
    v-if="showOrganizationModal"
    v-model="showOrganizationModal"
    :data="defaults"
  />
</template>
<script setup>
import ViewBreadcrumbs from '@/components/ViewBreadcrumbs.vue'
import CustomActions from '@/components/CustomActions.vue'
import OrganizationsIcon from '@/components/Icons/OrganizationsIcon.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import OrganizationModal from '@/components/Modals/OrganizationModal.vue'
import OrganizationsListView from '@/components/ListViews/OrganizationsListView.vue'
import KanbanView from '@/components/Kanban/KanbanView.vue'
import ViewControls from '@/components/ViewControls.vue'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import { getMeta } from '@/stores/meta'
import { usersStore } from '@/stores/users'
import { formatDate, website } from '@/utils'
import { timestampCell } from '@/composables/useTimelinePreferences'
import { Avatar, Tooltip } from 'frappe-ui'
import { useRoute } from 'vue-router'
import { ref, computed, reactive } from 'vue'

const { getFormattedPercent, getFormattedFloat, getFormattedCurrency } =
  getMeta('CRM Organization')

const { getUser } = usersStore()
const route = useRoute()

const organizationsListView = ref(null)
const showOrganizationModal = ref(false)

// Pre-fills the create modal when "+" is clicked on a kanban column, so the new
// client lands in that column.
const defaults = reactive({})

// What a kanban card shows below the client name. The name and the status
// column are already on the card, so these are the fields worth scanning for.
const kanbanFields = JSON.stringify([
  'tsi_country',
  'tsi_account_owner',
  'tsi_ranking',
  'modified',
])

// organizations data is loaded in the ViewControls component
const organizations = ref({})
const loadMore = ref(1)
const triggerResize = ref(1)
const updatedPageCount = ref(20)
const viewControls = ref(null)

function getRow(name, field) {
  const value = rows.value?.find((row) => row.name == name)?.[field]
  if (value && typeof value === 'object' && !Array.isArray(value)) return value
  return { label: value }
}

const rows = computed(() => {
  const data = organizations.value?.data
  if (!data?.data) return []
  if (data.view_type === 'group_by') {
    if (!data.group_by_field?.fieldname) return []
    return getGroupedByRows(data.data, data.group_by_field, data.columns)
  } else if (data.view_type === 'kanban') {
    return getKanbanRows(data.data, data.fields)
  }
  return parseRows(data.data, data.columns)
})

function getGroupedByRows(listRows, groupByField, columns) {
  return groupByField.options?.map((option) => {
    const filteredRows = option
      ? listRows.filter((row) => row[groupByField.fieldname] == option)
      : listRows.filter((row) => !row[groupByField.fieldname])
    return {
      label: groupByField.label,
      group: option || __(' '),
      collapsed: false,
      rows: parseRows(filteredRows, columns),
    }
  })
}

function getKanbanRows(data, columns) {
  const _rows = []
  data.forEach((column) => {
    column.data?.forEach((row) => _rows.push(row))
  })
  return parseRows(_rows, columns)
}

function parseRows(rows, columns = []) {
  // Kanban describes its fields as {fieldname, fieldtype}; list as {key, type}.
  const isKanban = organizations.value.data.view_type === 'kanban'
  const key = isKanban ? 'fieldname' : 'key'
  const type = isKanban ? 'fieldtype' : 'type'

  return rows.map((organization) => {
    let _rows = {}
    organizations.value?.data.rows.forEach((row) => {
      _rows[row] = organization[row]

      let fieldType = columns?.find((col) => (col[key] || col.value) == row)?.[
        type
      ]

      if (
        fieldType &&
        ['Date', 'Datetime'].includes(fieldType) &&
        !['modified', 'creation'].includes(row)
      ) {
        _rows[row] = formatDate(
          organization[row],
          '',
          true,
          fieldType == 'Datetime',
        )
      }

      if (fieldType && fieldType == 'Currency') {
        _rows[row] = getFormattedCurrency(row, organization)
      }

      if (fieldType && fieldType == 'Float') {
        _rows[row] = getFormattedFloat(row, organization)
      }

      if (fieldType && fieldType == 'Percent') {
        _rows[row] = getFormattedPercent(row, organization)
      }

      if (row === 'organization_name') {
        _rows[row] = {
          label: organization.organization_name,
          logo: organization.organization_logo,
        }
      } else if (row === 'website') {
        _rows[row] = website(organization.website)
      } else if (row === 'tsi_account_owner') {
        _rows[row] = {
          label:
            organization.tsi_account_owner &&
            getUser(organization.tsi_account_owner).full_name,
          ...(organization.tsi_account_owner &&
            getUser(organization.tsi_account_owner)),
        }
      } else if (['modified', 'creation'].includes(row)) {
        _rows[row] = timestampCell(organization[row])
      }
    })
    return _rows
  })
}

function onNewClick(column) {
  const column_field = organizations.value.params.column_field

  if (column_field) {
    defaults[column_field] = column.column.name
  }

  showOrganizationModal.value = true
}

const columns = computed(() => {
  let _columns = organizations.value?.data?.columns || []

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
</script>
