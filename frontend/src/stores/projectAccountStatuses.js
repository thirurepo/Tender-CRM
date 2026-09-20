// Project Account Status, cached the way crm caches its own status masters.
//
// A separate store rather than more branches in stores/statuses.js, for the same
// reason stores/ticketStatuses.js is: that file is byte-identical to upstream crm
// and its `statusOptions` is hardcoded to 'lead' and 'deal'. Keeping this here is
// what stops the fork diverging on a file it would re-merge on every
// `git pull --rebase upstream`.

import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import { parseColor } from '@/utils'
import { defineStore } from 'pinia'
import { createListResource } from 'frappe-ui'
import { reactive, h } from 'vue'

export const projectAccountStatusesStore = defineStore(
  'tsi-project-account-statuses',
  () => {
    let projectAccountStatusesByName = reactive({})

    // Ordered by position, not name. Disabled rows are excluded so a status
    // retired by a sales manager stops being offered, while accounts that still
    // carry it keep a valid link.
    const projectAccountStatuses = createListResource({
      doctype: 'Project Account Status',
      fields: ['name', 'color', 'position', 'category'],
      filters: { disabled: 0 },
      orderBy: 'position asc',
      pageLength: 99,
      cache: 'project-account-statuses',
      initialData: [],
      auto: true,
      transform(statuses) {
        for (let status of statuses) {
          status.color = parseColor(status.color)
          projectAccountStatusesByName[status.name] = status
        }
        return statuses
      },
    })

    // Tolerates an unknown name: an account can legitimately carry a status that
    // has since been disabled, and a list row must still render.
    function getProjectAccountStatus(name) {
      return projectAccountStatusesByName[name]
    }

    function projectAccountStatusOptions(onSelect = null) {
      return (projectAccountStatuses.data || []).map((status) => ({
        label: __(status.name),
        value: status.name,
        icon: () => h(IndicatorIcon, { class: status.color }),
        onClick: () => onSelect?.(status.name),
      }))
    }

    return {
      projectAccountStatuses,
      getProjectAccountStatus,
      projectAccountStatusOptions,
    }
  },
)
