<!--
  A single support ticket.

  Modelled on Deal.vue and deliberately thinner: a header with the status
  control, the conversation on the left (crm's Activities component, unchanged —
  the email thread is just Communications with reference_doctype = "Ticket", the
  same shape it takes on a Lead or a Deal), and the side panel on the right,
  driven by the seeded "Side Panel" CRM Fields Layout for Ticket. That layout is
  load-bearing: crm's get_sidepanel_sections has no generated fallback, so
  without it this sidebar renders empty. See
  tender_crm/setup.py::ensure_ticket_side_panel_layouts.

  Internal-only, by design. Tickets are never sent to or seen by a client, so
  there is no "reply to customer" affordance here — the support mailbox is how
  work arrives, not a two-way channel. The composer defaults to the people
  working the ticket.
-->
<template>
  <LayoutHeader>
    <template #left-header>
      <Breadcrumbs :items="breadcrumbs" />
    </template>
    <template v-if="!errorTitle" #right-header>
      <CustomActions
        v-if="document._actions?.length"
        :actions="document._actions"
      />
      <AssignTo v-model="assignees.data" doctype="Ticket" :docname="ticketId" />
      <Dropdown v-if="doc.name" :options="statuses" placement="right">
        <template #default="{ open }">
          <Button
            v-if="doc.status"
            :label="__(doc.status)"
            :iconRight="open ? 'chevron-up' : 'chevron-down'"
          >
            <template #prefix>
              <IndicatorIcon :class="getTicketStatus(doc.status)?.color" />
            </template>
          </Button>
        </template>
      </Dropdown>
    </template>
  </LayoutHeader>
  <div v-if="doc.name" class="flex h-full overflow-hidden">
    <Tabs
      v-model="tabIndex"
      as="div"
      :tabs="tabs"
      class="flex flex-1 overflow-hidden flex-col [&_[role='tab']]:px-0 [&_[role='tab']]:shrink-0 [&_[role='tablist']]:px-5 [&_[role='tablist']::-webkit-scrollbar]:h-0 [&_[role='tablist']]:min-h-[45px] [&_[role='tablist']]:gap-7.5 [&_[role='tabpanel']:not([hidden])]:flex [&_[role='tabpanel']:not([hidden])]:grow"
    >
      <template #tab-panel>
        <Activities
          ref="activities"
          v-model:reload="reload"
          v-model:tabIndex="tabIndex"
          doctype="Ticket"
          :docname="ticketId"
          :tabs="tabs"
        />
      </template>
    </Tabs>
    <Resizer side="right" class="flex flex-col justify-between border-l">
      <div
        class="flex h-[45px] cursor-copy items-center border-b px-5 py-2.5 text-lg-medium text-ink-gray-9"
        @click="copyToClipboard(ticketId)"
      >
        {{ __(ticketId) }}
      </div>
      <div class="border-b px-5 py-4">
        <div class="text-base font-medium text-ink-gray-9">
          {{ doc.subject }}
        </div>
        <div v-if="doc.raised_by" class="mt-1 text-sm text-ink-gray-5">
          {{ doc.raised_by }}
        </div>
      </div>
      <div
        v-if="sections.data"
        class="flex flex-1 flex-col justify-between overflow-hidden"
      >
        <SidePanelLayout
          :sections="sections.data"
          doctype="Ticket"
          :docname="ticketId"
          @reload="sections.reload"
        />
      </div>
    </Resizer>
  </div>
  <ErrorPage
    v-else-if="errorTitle"
    :errorTitle="errorTitle"
    :errorMessage="errorMessage"
  />
</template>

<script setup>
import ActivityIcon from '@/components/Icons/ActivityIcon.vue'
import EmailIcon from '@/components/Icons/EmailIcon.vue'
import CommentIcon from '@/components/Icons/CommentIcon.vue'
import DetailsIcon from '@/components/Icons/DetailsIcon.vue'
import TaskIcon from '@/components/Icons/TaskIcon.vue'
import NoteIcon from '@/components/Icons/NoteIcon.vue'
import AttachmentIcon from '@/components/Icons/AttachmentIcon.vue'
import IndicatorIcon from '@/components/Icons/IndicatorIcon.vue'
import CustomActions from '@/components/CustomActions.vue'
import AssignTo from '@/components/AssignTo.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import Resizer from '@/components/Resizer.vue'
import ErrorPage from '@/components/ErrorPage.vue'
import Activities from '@/components/Activities/Activities.vue'
import SidePanelLayout from '@/components/SidePanelLayout.vue'
import { useDocument } from '@/data/document'
import { ticketStatusesStore } from '@/stores/ticketStatuses'
import { viewsStore } from '@/stores/views'
import { getSettings } from '@/stores/settings'
import { copyToClipboard } from '@/utils'
import { useActiveTabManager } from '@/composables/useActiveTabManager'
import { useUnsavedChangesWarning } from '@/composables/useUnsavedChangesWarning'
import { Breadcrumbs, Tabs, Dropdown, createResource, usePageMeta } from 'frappe-ui'
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'

const props = defineProps({
  ticketId: { type: String, required: true },
})

const route = useRoute()
const { brand } = getSettings()
const { getView } = viewsStore()
const { getTicketStatus, ticketStatusOptions } = ticketStatusesStore()

const errorTitle = ref('')
const errorMessage = ref('')
const reload = ref(false)
const activities = ref(null)

const { triggerOnChange, assignees, document, error } = useDocument(
  'Ticket',
  props.ticketId,
)

const doc = computed(() => document.doc || {})

useUnsavedChangesWarning(() => document.isDirty)

watch(error, (err) => {
  if (err) {
    errorTitle.value = __(
      err.exc_type == 'DoesNotExistError'
        ? __('Document Not Found')
        : __('Error Occurred'),
    )
    errorMessage.value = __(err.messages?.[0] || __('An Error Occurred'))
  } else {
    errorTitle.value = ''
    errorMessage.value = ''
  }
})

// Its own dropdown rather than statusesStore's statusOptions, which is
// hardcoded to the strings 'lead' and 'deal' upstream. See
// stores/ticketStatuses.js for why that file is left alone.
const statuses = computed(() =>
  ticketStatusOptions((value) => triggerOnChange('status', value)),
)

const title = computed(() => doc.value.subject || props.ticketId)

usePageMeta(() => ({ title: title.value, icon: brand.favicon }))

const breadcrumbs = computed(() => {
  let items = [{ label: __('Tickets'), route: { name: 'Tickets' } }]

  if (route.query.view || route.query.viewType) {
    let view = getView(route.query.view, route.query.viewType, 'Ticket')
    if (view) {
      items.push({
        label: __(view.label),
        icon: view.icon,
        route: {
          name: 'Tickets',
          params: { viewType: route.query.viewType },
          query: { view: route.query.view },
        },
      })
    }
  }

  items.push({
    label: title.value,
    route: {
      name: 'Ticket',
      params: { ticketId: props.ticketId },
      query: route.query,
    },
  })
  return items
})

// No Calls or WhatsApp tab: neither is part of an internal-only support queue
// in this phase, and an empty tab is worse than an absent one.
const tabs = computed(() => [
  { name: 'Activity', label: __('Activity'), icon: ActivityIcon },
  { name: 'Emails', label: __('Emails'), icon: EmailIcon },
  { name: 'Comments', label: __('Comments'), icon: CommentIcon },
  { name: 'Data', label: __('Data'), icon: DetailsIcon },
  { name: 'Tasks', label: __('Tasks'), icon: TaskIcon },
  { name: 'Notes', label: __('Notes'), icon: NoteIcon },
  { name: 'Attachments', label: __('Attachments'), icon: AttachmentIcon },
])

const { tabIndex } = useActiveTabManager(tabs, 'lastTicketTab')

const sections = createResource({
  url: 'crm.fcrm.doctype.crm_fields_layout.crm_fields_layout.get_sidepanel_sections',
  params: { doctype: 'Ticket' },
  auto: true,
})
</script>
