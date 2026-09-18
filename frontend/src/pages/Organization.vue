<!--
  Client (CRM Organization) page, laid out like the Lead page: the same
  Activity / Emails / Comments / Data / Calls / Tasks / Notes / Attachments
  tabs, plus the client-only Deals, Contacts and Tickets. Details live in the
  right-hand side panel, as on a lead. The timeline comes from
  tender_crm.api.client_activities, which merges in the history of the lead
  the client was converted from — so nothing logged on a lead is lost when it
  becomes a client.
-->
<template>
  <LayoutHeader v-if="organization.doc">
    <template #left-header>
      <Breadcrumbs :items="breadcrumbs">
        <template #prefix="{ item }">
          <Icon v-if="item.icon" :icon="item.icon" class="mr-2 h-4" />
        </template>
      </Breadcrumbs>
    </template>
    <template #right-header>
      <CustomActions
        v-if="organization._actions?.length"
        :actions="organization._actions"
      />
      <AssignTo
        v-model="assignees.data"
        doctype="CRM Organization"
        :docname="organizationId"
      />
    </template>
  </LayoutHeader>
  <div v-if="organization.doc" class="flex h-full overflow-hidden">
    <Tabs
      v-model="tabIndex"
      as="div"
      :tabs="tabs"
      class="flex flex-1 overflow-hidden flex-col [&_[role='tablist']]:gap-7.5 [&_[role='tablist']]:px-5 [&_[role='tablist']::-webkit-scrollbar]:h-0 [&_[role='tablist']]:min-h-[45px] [&_[role='tabpanel']:not([hidden])]:flex [&_[role='tabpanel']:not([hidden])]:grow"
    >
      <template #tab-item="{ tab, selected }">
        <button
          class="group flex shrink-0 items-center gap-2 border-b border-transparent py-2.5 text-base text-ink-gray-5 duration-300 ease-in-out hover:text-ink-gray-9"
          :class="{ 'text-ink-gray-9': selected }"
        >
          <component :is="tab.icon" v-if="tab.icon" class="h-5" />
          {{ tab.label }}
          <Badge
            v-if="tab.count !== undefined"
            class="group-hover:bg-surface-gray-10"
            :class="[selected ? 'bg-surface-gray-10' : 'bg-gray-600']"
            variant="solid"
            theme="gray"
            size="sm"
          >
            {{ tab.count }}
          </Badge>
        </button>
      </template>
      <template #tab-panel="{ tab }">
        <template v-if="tab.name === 'Deals' || tab.name === 'Contacts'">
          <DealsListView
            v-if="tab.name === 'Deals' && rows.length"
            class="mt-4"
            :rows="rows"
            :columns="columns"
            :options="{ selectable: false, showTooltip: false }"
          />
          <ContactsListView
            v-else-if="tab.name === 'Contacts' && rows.length"
            class="mt-4"
            :rows="rows"
            :columns="columns"
            :options="{ selectable: false, showTooltip: false }"
          />
          <EmptyState v-else :icon="tab.icon" :name="tab.label" />
        </template>
        <LinkedTicketsList
          v-else-if="tab.name === 'Tickets'"
          :filters="{ organization: props.organizationId }"
          :cacheKey="props.organizationId"
        />
        <Activities
          v-else
          ref="activities"
          v-model:reload="reload"
          v-model:tabIndex="tabIndex"
          doctype="CRM Organization"
          :docname="organizationId"
          :tabs="tabs"
          @beforeSave="beforeFieldChange"
        />
      </template>
    </Tabs>
    <Resizer class="flex flex-col justify-between border-l" side="right">
      <div
        class="flex h-[45px] cursor-copy items-center border-b px-5 py-2.5 text-lg-medium text-ink-gray-9"
        @click="copyToClipboard(organizationId)"
      >
        {{ organizationId }}
      </div>
      <FileUploader
        :validateFile="validateIsImageFile"
        @success="changeOrganizationImage"
      >
        <template #default="{ openFileSelector, error }">
          <div class="flex items-center justify-start gap-5 border-b p-5">
            <div class="group relative size-12">
              <Avatar
                size="3xl"
                class="size-12"
                :label="organization.doc.organization_name"
                :image="organization.doc.organization_logo"
              />
              <component
                :is="organization.doc.organization_logo ? Dropdown : 'div'"
                v-bind="
                  organization.doc.organization_logo
                    ? {
                        options: [
                          {
                            icon: 'upload',
                            label: __('Change Image'),
                            onClick: openFileSelector,
                          },
                          {
                            icon: 'trash-2',
                            label: __('Remove Image'),
                            onClick: () => changeOrganizationImage(''),
                          },
                        ],
                      }
                    : { onClick: openFileSelector }
                "
                class="!absolute bottom-0 left-0 right-0"
              >
                <div
                  class="z-1 absolute bottom-0.5 left-0 right-0.5 flex h-9 cursor-pointer items-center justify-center rounded-b-full bg-black bg-opacity-40 pt-3 opacity-0 duration-300 ease-in-out group-hover:opacity-100"
                  style="
                    -webkit-clip-path: inset(12px 0 0 0);
                    clip-path: inset(12px 0 0 0);
                  "
                >
                  <CameraIcon class="size-4 cursor-pointer text-white" />
                </div>
              </component>
            </div>
            <div class="flex flex-col gap-2.5 truncate">
              <Tooltip :text="title">
                <div class="truncate text-3xl-medium text-ink-gray-9">
                  {{ title }}
                </div>
              </Tooltip>
              <div class="flex gap-1.5">
                <Button
                  v-if="callEnabled"
                  :tooltip="__('Make a Call')"
                  :icon="PhoneIcon"
                  @click="
                    () =>
                      contactMobile
                        ? makeCall(contactMobile)
                        : toast.error(
                            __('Please set a mobile number to make calls'),
                          )
                  "
                />
                <Button
                  :tooltip="__('Send an Email')"
                  :icon="Email2Icon"
                  @click="openEmailBox"
                />
                <Button
                  :tooltip="__('Go to Website')"
                  :icon="LinkIcon"
                  @click="openWebsite"
                />
                <Button
                  :tooltip="__('Attach a File')"
                  :icon="AttachmentIcon"
                  @click="showFilesUploader = true"
                />
                <Button
                  v-if="canDelete"
                  :tooltip="__('Delete')"
                  variant="subtle"
                  theme="red"
                  icon="lucide-trash-2"
                  @click="deleteOrganization"
                />
              </div>
              <ErrorMessage :message="__(error)" />
            </div>
          </div>
        </template>
      </FileUploader>
      <div
        v-if="sections.data"
        class="flex flex-1 flex-col justify-between overflow-hidden"
      >
        <SidePanelLayout
          :sections="sections.data"
          doctype="CRM Organization"
          :docname="organization.doc.name"
          @reload="sections.reload"
          @beforeFieldChange="beforeFieldChange"
        />
      </div>
    </Resizer>
  </div>
  <ErrorPage
    v-else-if="errorTitle"
    :errorTitle="errorTitle"
    :errorMessage="errorMessage"
  />
  <FilesUploader
    v-if="organization.doc"
    v-model="showFilesUploader"
    doctype="CRM Organization"
    :docname="organizationId"
    @after="
      () => {
        activities?.all_activities?.reload()
        changeTabTo('attachments')
      }
    "
  />
  <DeleteLinkedDocModal
    v-if="showDeleteLinkedDocModal"
    v-model="showDeleteLinkedDocModal"
    :doctype="'CRM Organization'"
    :docname="props.organizationId"
    name="Organizations"
  />
</template>

<script setup>
import ErrorPage from '@/components/ErrorPage.vue'
import Resizer from '@/components/Resizer.vue'
import SidePanelLayout from '@/components/SidePanelLayout.vue'
import Icon from '@/components/Icon.vue'
import LayoutHeader from '@/components/LayoutHeader.vue'
import DealsListView from '@/components/ListViews/DealsListView.vue'
import ContactsListView from '@/components/ListViews/ContactsListView.vue'
import LinkedTicketsList from '@/components/LinkedTicketsList.vue'
import Activities from '@/components/Activities/Activities.vue'
import AssignTo from '@/components/AssignTo.vue'
import FilesUploader from '@/components/FilesUploader/FilesUploader.vue'
import TicketsIcon from '@/components/Icons/TicketsIcon.vue'
import ActivityIcon from '@/components/Icons/ActivityIcon.vue'
import EmailIcon from '@/components/Icons/EmailIcon.vue'
import Email2Icon from '@/components/Icons/Email2Icon.vue'
import CommentIcon from '@/components/Icons/CommentIcon.vue'
import DetailsIcon from '@/components/Icons/DetailsIcon.vue'
import PhoneIcon from '@/components/Icons/PhoneIcon.vue'
import TaskIcon from '@/components/Icons/TaskIcon.vue'
import NoteIcon from '@/components/Icons/NoteIcon.vue'
import LinkIcon from '@/components/Icons/LinkIcon.vue'
import AttachmentIcon from '@/components/Icons/AttachmentIcon.vue'
import CameraIcon from '@/components/Icons/CameraIcon.vue'
import DealsIcon from '@/components/Icons/DealsIcon.vue'
import ContactsIcon from '@/components/Icons/ContactsIcon.vue'
import DeleteLinkedDocModal from '@/components/DeleteLinkedDocModal.vue'
import CustomActions from '@/components/CustomActions.vue'
import { useDocument } from '@/data/document'
import { getSettings } from '@/stores/settings'
import { globalStore } from '@/stores/global'
import { getMeta } from '@/stores/meta'
import { usersStore } from '@/stores/users'
import { statusesStore } from '@/stores/statuses'
import { getView } from '@/utils/view'
import {
  validateIsImageFile,
  setupCustomizations,
  copyToClipboard,
  openWebsite as openExternalWebsite,
} from '@/utils'
import { callEnabled } from '@/composables/telephony'
import { useActiveTabManager } from '@/composables/useActiveTabManager'
import { timestampCell } from '@/composables/useTimelinePreferences'
import {
  Breadcrumbs,
  Avatar,
  FileUploader,
  Dropdown,
  Tooltip,
  Tabs,
  createListResource,
  usePageMeta,
  createResource,
  toast,
  call,
} from 'frappe-ui'
import { useDoctypeModal } from '@/composables/doctypeModal'
import { useTelemetry } from 'frappe-ui/frappe'
import { computed, ref, watch, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps({
  organizationId: { type: String, required: true },
})

const { brand } = getSettings()
const { $dialog, $socket, makeCall } = globalStore()
const { getUser } = usersStore()
const { getDealStatus } = statusesStore()
const { doctypeMeta } = getMeta('CRM Organization')
const { capture } = useTelemetry()

const route = useRoute()
const router = useRouter()

const errorTitle = ref('')
const errorMessage = ref('')

const showDeleteLinkedDocModal = ref(false)
const showFilesUploader = ref(false)
const reload = ref(false)
const activities = ref(null)

const {
  document: organization,
  assignees,
  permissions,
  scripts,
  error,
  triggerOnRender,
} = useDocument('CRM Organization', props.organizationId)

watch(error, (err) => {
  if (err) {
    errorTitle.value =
      err.exc_type == 'DoesNotExistError'
        ? __('Document not found')
        : __('Error occurred')
    errorMessage.value = __(err.messages?.[0] || __('An error occurred'))
  } else {
    errorTitle.value = ''
    errorMessage.value = ''
  }
})

const canDelete = computed(() => permissions.data?.permissions?.delete || false)

onMounted(async () => {
  if (organization.doc) await triggerOnRender()
})

const breadcrumbs = computed(() => {
  let items = [{ label: __('Organizations'), route: { name: 'Organizations' } }]

  if (route.query.view || route.query.viewType) {
    let view = getView(
      route.query.view,
      route.query.viewType,
      'CRM Organization',
    )
    if (view) {
      items.push({
        label: __(view.label),
        icon: view.icon,
        route: {
          name: 'Organizations',
          params: { viewType: route.query.viewType },
          query: { view: route.query.view },
        },
      })
    }
  }

  items.push({
    label: title.value,
    route: {
      name: 'Organization',
      params: { organizationId: props.organizationId },
      query: route.query,
    },
  })
  return items
})

const title = computed(() => {
  let t = doctypeMeta.value?.title_field || 'name'
  return organization.doc?.[t] || props.organizationId
})

usePageMeta(() => {
  return {
    title: title.value,
    icon: brand.favicon,
  }
})

async function deleteOrganization() {
  showDeleteLinkedDocModal.value = true
}

function changeOrganizationImage(file) {
  organization.setValue.submit({
    organization_logo: file?.file_url || null,
  })
}

function beforeFieldChange(data) {
  if (Object.hasOwn(data ?? {}, 'organization_name')) {
    call('frappe.client.rename_doc', {
      doctype: 'CRM Organization',
      old_name: props.organizationId,
      new_name: data.organization_name,
    }).then(() => {
      router.push({
        name: 'Organization',
        params: { organizationId: data.organization_name },
      })
    })
  } else {
    organization.save.submit()
  }
}

function openWebsite() {
  if (!organization.doc.website) {
    toast.error(__('No Website Found'))
    return
  }

  openExternalWebsite(organization.doc.website)
}

// A client has no phone or email of its own; the legacy client import put its
// primary contact's on the record (tsi_contact_*), and that is who a call or
// email from this page is for.
const contactMobile = computed(
  () =>
    organization.doc?.tsi_contact_mobile || organization.doc?.tsi_contact_phone,
)

async function openEmailBox() {
  // Deals / Contacts / Tickets render no Activities, so the ref is null there:
  // move to Emails by index and let Activities mount before reaching through.
  let current = tabs.value[tabIndex.value]?.name
  if (!['Emails', 'Comments', 'Activity'].includes(current)) {
    tabIndex.value = tabs.value.findIndex((tab) => tab.name === 'Emails')
    await nextTick()
  }
  nextTick(() => {
    if (activities.value?.emailBox) activities.value.emailBox.show = true
  })
}

const sections = createResource({
  url: 'crm.fcrm.doctype.crm_fields_layout.crm_fields_layout.get_sidepanel_sections',
  cache: ['sidePanelSections', 'CRM Organization'],
  params: { doctype: 'CRM Organization' },
  auto: true,
  transform: (data) => getParsedSections(data),
})

function getParsedSections(_sections) {
  return _sections.map((section) => {
    section.columns = section.columns.map((column) => {
      column.fields = column.fields.map((field) => {
        if (field.fieldname === 'address') {
          return {
            ...field,
            create: (value, close) => {
              showAddressModal()
              close()
            },
            edit: (address) => showAddressModal(address),
          }
        } else {
          return field
        }
      })
      return column
    })
    return section
  })
}

// Only the badge. The rows are LinkedTicketsList's own business, and it does
// not fetch them until the tab is opened — the badge has to be right before
// then. This is the payoff for Ticket's denormalised `organization`: one
// indexed equality instead of a walk through the Dynamic Link.
const ticketCount = createResource({
  url: 'frappe.client.get_count',
  params: {
    doctype: 'Ticket',
    filters: { organization: props.organizationId },
  },
  auto: true,
  transform: (value) => value ?? 0,
})

const deals = createListResource({
  type: 'list',
  doctype: 'CRM Deal',
  cache: ['deals', props.organizationId],
  fields: [
    'name',
    'organization',
    'currency',
    'deal_value',
    'status',
    'email',
    'mobile_no',
    'deal_owner',
    'modified',
  ],
  filters: {
    organization: props.organizationId,
  },
  orderBy: 'modified desc',
  pageLength: 20,
  auto: true,
})

const contacts = createListResource({
  type: 'list',
  doctype: 'Contact',
  cache: ['contacts', props.organizationId],
  fields: [
    'name',
    'full_name',
    'image',
    'email_id',
    'mobile_no',
    'company_name',
    'modified',
  ],
  filters: {
    company_name: props.organizationId,
  },
  orderBy: 'modified desc',
  pageLength: 20,
  auto: true,
})

// Same tabs, in the same order, as the Lead page, so a converted lead reads the
// same as a client; then the three views only a client has. `count` is what
// marks a tab as a list with a badge rather than an Activities tab.
const tabs = computed(() => [
  { name: 'Activity', label: __('Activity'), icon: ActivityIcon },
  { name: 'Emails', label: __('Emails'), icon: EmailIcon },
  { name: 'Comments', label: __('Comments'), icon: CommentIcon },
  { name: 'Data', label: __('Data'), icon: DetailsIcon },
  { name: 'Calls', label: __('Calls'), icon: PhoneIcon },
  { name: 'Tasks', label: __('Tasks'), icon: TaskIcon },
  { name: 'Notes', label: __('Notes'), icon: NoteIcon },
  { name: 'Attachments', label: __('Attachments'), icon: AttachmentIcon },
  {
    name: 'Deals',
    label: __('Deals'),
    icon: DealsIcon,
    count: deals.data?.length ?? 0,
  },
  {
    name: 'Contacts',
    label: __('Contacts'),
    icon: ContactsIcon,
    count: contacts.data?.length ?? 0,
  },
  {
    name: 'Tickets',
    label: __('Tickets'),
    icon: TicketsIcon,
    count: ticketCount.data ?? 0,
  },
])

const { tabIndex, changeTabTo } = useActiveTabManager(
  tabs,
  'lastOrganizationTab',
)

const currentTabName = computed(() => tabs.value[tabIndex.value]?.name)

const rows = computed(() => {
  if (currentTabName.value === 'Deals') {
    return (deals.data || []).map(getDealRowObject)
  }
  if (currentTabName.value === 'Contacts') {
    return (contacts.data || []).map(getContactRowObject)
  }
  return []
})

const { getFormattedCurrency } = getMeta('CRM Deal')

const columns = computed(() => {
  return currentTabName.value === 'Deals' ? dealColumns : contactColumns
})

function getDealRowObject(deal) {
  return {
    name: deal.name,
    organization: {
      label: deal.organization,
      logo: organization.doc?.organization_logo,
    },
    deal_value: getFormattedCurrency('deal_value', deal),
    status: {
      label: deal.status,
      color: getDealStatus(deal.status)?.color,
    },
    email: deal.email,
    mobile_no: deal.mobile_no,
    deal_owner: {
      label: deal.deal_owner && getUser(deal.deal_owner).full_name,
      ...(deal.deal_owner && getUser(deal.deal_owner)),
    },
    modified: timestampCell(deal.modified),
  }
}

function getContactRowObject(contact) {
  return {
    name: contact.name,
    full_name: {
      label: contact.full_name,
      image_label: contact.full_name,
      image: contact.image,
    },
    email: contact.email_id,
    mobile_no: contact.mobile_no,
    company_name: {
      label: contact.company_name,
      logo: organization.doc?.organization_logo,
    },
    modified: timestampCell(contact.modified),
  }
}

const dealColumns = [
  {
    label: __('Organization'),
    key: 'organization',
    width: '11rem',
  },
  {
    label: __('Amount'),
    key: 'deal_value',
    align: 'right',
    width: '9rem',
  },
  {
    label: __('Status'),
    key: 'status',
    width: '10rem',
  },
  {
    label: __('Email'),
    key: 'email',
    width: '12rem',
  },
  {
    label: __('Mobile Number'),
    key: 'mobile_no',
    width: '11rem',
  },
  {
    label: __('Deal Owner'),
    key: 'deal_owner',
    width: '10rem',
  },
  {
    label: __('Last Modified'),
    key: 'modified',
    width: '8rem',
  },
]

const contactColumns = [
  {
    label: __('Name'),
    key: 'full_name',
    width: '17rem',
  },
  {
    label: __('Email'),
    key: 'email',
    width: '12rem',
  },
  {
    label: __('Phone'),
    key: 'mobile_no',
    width: '12rem',
  },
  {
    label: __('Organization'),
    key: 'company_name',
    width: '12rem',
  },
  {
    label: __('Last Modified'),
    key: 'modified',
    width: '8rem',
  },
]

const { showModal } = useDoctypeModal()

function showAddressModal(_address) {
  showModal({
    name: _address || null,
    doctype: 'Address',
    callbacks: {
      afterInsert: (d) => {
        capture('address_created')
        organization.doc.address = d.name
        organization.save.submit()
      },
    },
  })
}

// Setup custom actions from Form Scripts
watch(
  () => organization.doc,
  async (_doc) => {
    if (scripts.data?.length) {
      let s = await setupCustomizations(scripts.data, {
        doc: _doc,
        $dialog,
        $socket,
        router,
        toast,
        updateField: organization.setValue.submit,
        createToast: toast.create,
        deleteDoc: deleteOrganization,
        call,
      })
      organization._actions = s.actions || []
    }
  },
  { once: true },
)
</script>
