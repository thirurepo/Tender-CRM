// Ticket Status / Ticket Priority, cached the way crm caches its own status
// masters.
//
// A separate store rather than three more branches inside stores/statuses.js:
// that file is byte-identical to upstream crm and its `statusOptions` is
// hardcoded to the strings 'lead' and 'deal'. Keeping the support queue's
// masters here is what stops this fork from diverging on a file it would then
// have to re-merge on every `git pull --rebase upstream`.

import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import { parseColor } from '@/utils'
import { defineStore } from 'pinia'
import { createListResource } from 'frappe-ui'
import { reactive, h } from 'vue'

export const ticketStatusesStore = defineStore('tsi-ticket-statuses', () => {
  let ticketStatusesByName = reactive({})
  let ticketPrioritiesByName = reactive({})

  // Ordered by position, not by name: position is the whole reason both
  // doctypes carry the field. Disabled rows are excluded so a status retired
  // by the support lead stops being offered, while tickets that still carry
  // it keep a valid link.
  const ticketStatuses = createListResource({
    doctype: 'Ticket Status',
    fields: ['name', 'color', 'position', 'category'],
    filters: { disabled: 0 },
    orderBy: 'position asc',
    pageLength: 99,
    cache: 'ticket-statuses',
    initialData: [],
    auto: true,
    transform(statuses) {
      for (let status of statuses) {
        status.color = parseColor(status.color)
        ticketStatusesByName[status.name] = status
      }
      return statuses
    },
  })

  const ticketPriorities = createListResource({
    doctype: 'Ticket Priority',
    fields: ['name', 'color', 'position'],
    filters: { disabled: 0 },
    orderBy: 'position asc',
    pageLength: 99,
    cache: 'ticket-priorities',
    initialData: [],
    auto: true,
    transform(priorities) {
      for (let priority of priorities) {
        priority.color = parseColor(priority.color)
        ticketPrioritiesByName[priority.name] = priority
      }
      return priorities
    },
  })

  // Both getters tolerate an unknown name — a ticket can legitimately carry a
  // status that has since been disabled, and a list row must still render.
  function getTicketStatus(name) {
    return ticketStatusesByName[name]
  }

  function getTicketPriority(name) {
    return ticketPrioritiesByName[name]
  }

  function ticketStatusOptions(onSelect = null) {
    return (ticketStatuses.data || []).map((status) => ({
      label: __(status.name),
      value: status.name,
      icon: () => h(IndicatorIcon, { class: status.color }),
      onClick: () => onSelect?.(status.name),
    }))
  }

  return {
    ticketStatuses,
    ticketPriorities,
    getTicketStatus,
    getTicketPriority,
    ticketStatusOptions,
  }
})
