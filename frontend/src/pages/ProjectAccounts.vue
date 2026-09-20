<!--
  The Project Accounts list.

  Modelled on Tickets.vue, without the kanban board (the Status column and
  group-by cover it for now). Data comes from crm/api/doc.py's `get_data`, which
  takes an arbitrary doctype string and asks that doctype's controller for its
  defaults — so list, filter, sort, saved views and group-by work with no backend
  of their own. See
  tender_crm/tender_crm/doctype/project_account/project_account.py.
-->
<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs v-model="viewControls" routeName="Project Accounts" />
    </template>
    <template #right-header>
      <CustomActions
        v-if="projectAccountsListView?.customListActions"
        :actions="projectAccountsListView.customListActions"
      />
      <Button
        variant="solid"
        :label="__('Create')"
        iconLeft="plus"
        @click="createProjectAccount()"
      />
    </template>
  </LayoutHeader>
  <ViewControls
    ref="viewControls"
    v-model="projectAccounts"
    v-model:loadMore="loadMore"
    v-model:resizeColumn="triggerResize"
    v-model:updatedPageCount="updatedPageCount"
    doctype="Project Account"
    :options="{
      allowedViews: ['list', 'group_by'],
    }"
  />
  <ProjectAccountsListView
    v-if="projectAccounts.data && rows.length"
    ref="projectAccountsListView"
    v-model="projectAccounts.data.page_length_count"
    v-model:list="projectAccounts"
    :rows="rows"
    :columns="columns"
    :options="{
      showTooltip: false,
      resizeColumn: true,
      rowCount: projectAccounts.data.row_count,
      totalCount: projectAccounts.data.total_count,
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
    v-else-if="projectAccounts.data && !rows.length"
    name="Project Accounts"
    :icon="ProjectAccountsIcon"
  />
</template>

<script setup>
import ViewBreadcrumbs from '@/components/ViewBreadcrumbs.vue'
import CustomActions from '@/components/CustomActions.vue'
import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import ProjectAccountsIcon from '@/components/Icons/ProjectAccountsIcon.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import ProjectAccountsListView from '@/components/ListViews/ProjectAccountsListView.vue'
import EmptyState from '@/components/ListViews/EmptyState.vue'
import ViewControls from '@/components/ViewControls.vue'
import { useDoctypeModal } from '@/composables/doctypeModal'
import { projectAccountStatusesStore } from '@/stores/projectAccountStatuses'
import { formatDate } from '@/utils'
import { timestampCell } from '@/composables/useTimelinePreferences'
import { ref, computed, h } from 'vue'

const { getProjectAccountStatus } = projectAccountStatusesStore()
const { showModal } = useDoctypeModal()

const projectAccountsListView = ref(null)

// projectAccounts data is loaded in the ViewControls component
const projectAccounts = ref({})
const loadMore = ref(1)
const triggerResize = ref(1)
const updatedPageCount = ref(20)
const viewControls = ref(null)

const rows = computed(() => {
  if (!projectAccounts.value?.data?.data) return []
  if (projectAccounts.value.data.view_type === 'group_by') {
    if (!projectAccounts.value?.data.group_by_field?.fieldname) return []
    return getGroupedByRows(
      projectAccounts.value?.data.data,
      projectAccounts.value?.data.group_by_field,
      projectAccounts.value.data.columns,
    )
  }
  return parseRows(
    projectAccounts.value?.data.data,
    projectAccounts.value.data.columns,
  )
})

const columns = computed(() => {
  let _columns = projectAccounts.value?.data?.columns || []

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
          class: getProjectAccountStatus(option)?.color,
        })
    }
    groupedRows.push(groupDetail)
  })

  return groupedRows || listRows
}

function parseRows(rows, columns = []) {
  return rows.map((projectAccount) => {
    let _rows = {}
    projectAccounts.value?.data.rows.forEach((row) => {
      _rows[row] = projectAccount[row]

      let fieldType = columns?.find((col) => col.key == row)?.type

      if (
        fieldType &&
        ['Date', 'Datetime'].includes(fieldType) &&
        !['modified', 'creation'].includes(row)
      ) {
        _rows[row] = formatDate(
          projectAccount[row],
          '',
          true,
          fieldType == 'Datetime',
        )
      }

      if (row == 'status') {
        _rows[row] = {
          label: projectAccount.status,
          color: getProjectAccountStatus(projectAccount.status)?.color,
        }
      } else if (['modified', 'creation'].includes(row)) {
        _rows[row] = timestampCell(projectAccount[row])
      }
    })
    return _rows
  })
}

// Create goes through the shared DoctypeModal rather than a bespoke modal: crm
// generates a Quick Entry layout for any doctype that has no saved one, so there
// is nothing a Project Account-specific modal would add yet.
function createProjectAccount(defaults = {}) {
  showModal({ doctype: 'Project Account', title: 'Project Account', defaults })
}
</script>
