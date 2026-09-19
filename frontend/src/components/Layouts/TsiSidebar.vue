<!--
  The Tender CRM design's nav sidebar: brand mark, grouped navigation, a
  quick-jump affordance, and a user chip. Replaces AppSidebar.vue's dynamic
  saved-views nav, which doesn't fit this design's fixed grouped layout.

  "Activity Feed", "Leads", "Clients", "Tickets" and "Tasks" are live routes.
  The rest (Dashboard, Marketing, Reports) renders but does nothing yet,
  matching the plan's decision to keep them present-but-inert rather than hide
  them.

  The "Settings" group at the foot of the nav is different in kind: its items
  are not routes but pages of the Settings dialog (Settings.vue), and clicking
  one opens the dialog on that page. It is collapsible because the list is long
  (up to ~19 pages for a manager) and would otherwise push the CRM links off
  a laptop screen.
-->
<template>
  <aside class="tsi-sidebar">
    <div class="tsi-sidebar__brand">
      <span class="tsi-sidebar__brand-name">CRM - Tender</span>
      <span class="tsi-sidebar__brand-rule" />
    </div>

    <button
      class="tsi-sidebar__quickjump"
      type="button"
      @click="quickJumpOpen = true"
    >
      <span>{{ __('Quick jump') }}</span>
      <span>/</span>
    </button>

    <QuickJump v-model="quickJumpOpen" />

    <nav class="tsi-sidebar__nav">
      <div v-for="group in navGroups" :key="group.label" class="tsi-sidebar__group">
        <div class="tsi-sidebar__group-label">{{ group.label }}</div>
        <component
          :is="item.route ? 'router-link' : 'span'"
          v-for="item in group.items"
          :key="item.label"
          :to="item.route ? { name: item.route } : undefined"
          class="tsi-sidebar__item"
          :class="{ 'tsi-sidebar__item--inert': !item.route }"
        >
          <span>{{ item.label }}</span>
          <span v-if="item.count !== undefined" class="tsi-sidebar__count">
            {{ item.count }}
          </span>
        </component>
      </div>

      <div class="tsi-sidebar__group">
        <button
          type="button"
          class="tsi-sidebar__group-label tsi-sidebar__group-toggle"
          :aria-expanded="settingsExpanded"
          @click="toggleSettings"
        >
          <span>{{ __('Settings') }}</span>
          <span class="tsi-sidebar__chevron">{{ settingsExpanded ? '−' : '+' }}</span>
        </button>
        <template v-if="settingsExpanded">
          <template v-for="section in settingsTabs" :key="section.label">
            <div class="tsi-sidebar__subgroup-label">{{ section.label }}</div>
            <button
              v-for="page in section.items"
              :key="page.label"
              type="button"
              class="tsi-sidebar__item tsi-sidebar__item--button"
              :class="{ 'tsi-sidebar__item--active': isSettingsPageOpen(page.label) }"
              @click="openSettings(page.label)"
            >
              <span>{{ page.label }}</span>
            </button>
          </template>
        </template>
      </div>
    </nav>

    <div class="tsi-sidebar__user">
      <span class="tsi-sidebar__user-avatar">{{ initials }}</span>
      <div>
        <div class="tsi-sidebar__user-name">{{ user.full_name }}</div>
        <div class="tsi-sidebar__user-sub">Sales Unit · {{ salesUnit }}</div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'
import { createResource } from 'frappe-ui'
import QuickJump from '@/components/QuickJump.vue'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/users'
import { showSettings, activeSettingsPage } from '@/composables/settings'
import { useSettingsTabs } from '@/composables/settingsTabs'

// Owned here rather than inside QuickJump because two things open the dialog:
// this button, and the global "/" shortcut QuickJump binds for itself.
const quickJumpOpen = ref(false)

const session = sessionStore()
const { getUser } = usersStore()
const user = computed(() => getUser(session.user))

const initials = computed(() =>
  (user.value.full_name || '')
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase(),
)

// "Sales Unit" is a new concept (tsi_sales_unit) this design introduces on
// the Lead/Organization doctypes — there is no per-user sales unit yet, so
// the chip reads generically until that's decided.
const salesUnit = computed(() => 'All')

const leadCount = createResource({
  url: 'frappe.client.get_count',
  params: { doctype: 'CRM Lead' },
  auto: true,
  transform: (value) => value ?? 0,
})
const clientCount = createResource({
  url: 'frappe.client.get_count',
  params: { doctype: 'CRM Organization' },
  auto: true,
  transform: (value) => value ?? 0,
})
// Every ticket, not just the open ones: this chip is a "how big is this
// thing?" count like the two above it, and a filtered count here would be the
// only number on the sidebar that means something different from its label.
const ticketCount = createResource({
  url: 'frappe.client.get_count',
  params: { doctype: 'Ticket' },
  auto: true,
  transform: (value) => value ?? 0,
})
// CRM Task only, matching the sidebar's "how big is this thing?" convention
// above — the Tasks page's own To Dos toggle (see pages/Tasks.vue) has no
// single sidebar-sized count since ToDo's visibility is per-user, not global.
const taskCount = createResource({
  url: 'frappe.client.get_count',
  params: { doctype: 'CRM Task' },
  auto: true,
  transform: (value) => value ?? 0,
})

// Unlike the four counts above — which answer "how big is this thing?" — this
// one answers "is anything happening?", so it is a 24-hour window rather than a
// total. A lifetime activity count would be a number nobody can act on.
const recentActivityCount = createResource({
  url: 'tender_crm.api.feed.get_recent_count',
  params: { hours: 24 },
  auto: true,
  transform: (value) => value ?? 0,
})

// The same permission-filtered list the dialog renders, so a non-manager sees
// only the pages they can actually open (Profile, Preferences, Templates, ...).
const settingsTabs = useSettingsTabs()

// Collapsed by default; remembered per browser because it is a layout
// preference, not data. Storage can throw (private mode, blocked site data),
// in which case the group simply starts collapsed every time.
const SETTINGS_EXPANDED_KEY = 'tsi_sidebar_settings_expanded'
const settingsExpanded = ref(readSettingsExpanded())

function readSettingsExpanded() {
  try {
    return localStorage.getItem(SETTINGS_EXPANDED_KEY) === '1'
  } catch {
    return false
  }
}

function toggleSettings() {
  settingsExpanded.value = !settingsExpanded.value
  try {
    localStorage.setItem(SETTINGS_EXPANDED_KEY, settingsExpanded.value ? '1' : '0')
  } catch {
    // Not persisting the toggle is harmless; see readSettingsExpanded().
  }
}

// Settings.vue watches activeSettingsPage and switches its right pane to the
// matching page, so setting both refs is all "open on this page" takes.
function openSettings(label) {
  activeSettingsPage.value = label
  showSettings.value = true
}

function isSettingsPageOpen(label) {
  return showSettings.value && activeSettingsPage.value === label
}

const navGroups = computed(() => [
  {
    label: 'CRM',
    items: [
      {
        label: 'Activity Feed',
        count: recentActivityCount.data ?? '…',
        route: 'Activity Feed',
      },
      { label: 'Leads', count: leadCount.data ?? '…', route: 'Leads' },
      { label: 'Clients', count: clientCount.data ?? '…', route: 'Organizations' },
      { label: 'Tasks', count: taskCount.data ?? '…', route: 'Tasks' },
      { label: 'Tickets', count: ticketCount.data ?? '…', route: 'Tickets' },
    ],
  },
  {
    label: 'Dashboard',
    items: [
      { label: 'Main' },
      { label: 'Leads' },
      { label: 'Clients' },
      { label: 'Hours' },
    ],
  },
  {
    label: 'Marketing',
    items: [{ label: 'Email campaign' }, { label: 'WhatsApp' }],
  },
  {
    label: 'Reports',
    items: [{ label: 'Weekly' }, { label: 'Clients' }],
  },
])
</script>

<style scoped>
.tsi-sidebar {
  width: 214px;
  flex-shrink: 0;
  height: 100vh;
  overflow-y: auto;
  background: var(--tsi-color-surface);
  border-right: 1px solid var(--tsi-color-divider);
  display: flex;
  flex-direction: column;
  font-family: var(--tsi-font-body);
  color: var(--tsi-color-text);
}

.tsi-sidebar__brand {
  padding: var(--tsi-space-4) var(--tsi-space-3) var(--tsi-space-3);
}
.tsi-sidebar__brand-name {
  display: block;
  font-family: var(--tsi-font-heading);
  font-size: 19px;
  font-weight: var(--tsi-font-heading-weight);
  text-transform: uppercase;
  letter-spacing: 0.14em;
}
.tsi-sidebar__brand-rule {
  display: block;
  margin: var(--tsi-space-1) 0;
  border-top: 3px solid var(--tsi-color-text);
  border-bottom: 1px solid var(--tsi-color-text);
  padding-top: 1px;
}
.tsi-sidebar__quickjump {
  margin: 0 var(--tsi-space-3) var(--tsi-space-3);
  padding: var(--tsi-space-1) var(--tsi-space-2);
  border: 1px solid var(--tsi-color-divider);
  border-radius: var(--tsi-radius-md);
  background: var(--tsi-color-bg);
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--tsi-color-neutral-700);
  cursor: pointer;
}

.tsi-sidebar__nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--tsi-space-2);
}
.tsi-sidebar__group {
  margin-bottom: var(--tsi-space-4);
}
.tsi-sidebar__group-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--tsi-color-neutral-500);
  padding: 0 var(--tsi-space-2);
  margin-bottom: var(--tsi-space-1);
}
.tsi-sidebar__item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--tsi-space-1) var(--tsi-space-2);
  border-radius: var(--tsi-radius-sm);
  font-size: 13px;
  color: var(--tsi-color-text);
  text-decoration: none;
  cursor: pointer;
}
.tsi-sidebar__item:hover {
  background: var(--tsi-color-bg);
}
.tsi-sidebar__item.router-link-active {
  background: var(--tsi-color-accent-100);
  color: var(--tsi-color-accent-700);
  font-weight: 600;
}
.tsi-sidebar__item--inert {
  color: var(--tsi-color-neutral-500);
  cursor: default;
}
.tsi-sidebar__item--inert:hover {
  background: none;
}
.tsi-sidebar__group-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  background: none;
  border: 0;
  cursor: pointer;
  font-family: inherit;
}
.tsi-sidebar__group-toggle:hover {
  color: var(--tsi-color-text);
}
.tsi-sidebar__chevron {
  font-size: 13px;
  line-height: 1;
}
.tsi-sidebar__subgroup-label {
  font-size: 11px;
  color: var(--tsi-color-neutral-500);
  padding: var(--tsi-space-2) var(--tsi-space-2) 2px;
}
/* <button> resets so the settings entries line up with the router-links. */
.tsi-sidebar__item--button {
  width: 100%;
  background: none;
  border: 0;
  font-family: inherit;
  text-align: left;
}
.tsi-sidebar__item--active {
  background: var(--tsi-color-accent-100);
  color: var(--tsi-color-accent-700);
  font-weight: 600;
}
.tsi-sidebar__count {
  font-size: 12px;
  color: var(--tsi-color-neutral-500);
}

.tsi-sidebar__user {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-2);
  padding: var(--tsi-space-3);
  border-top: 1px solid var(--tsi-color-divider);
}
.tsi-sidebar__user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--tsi-color-accent-200);
  color: var(--tsi-color-accent-800);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.tsi-sidebar__user-name {
  font-size: 13px;
  font-weight: 600;
}
.tsi-sidebar__user-sub {
  font-size: 11px;
  color: var(--tsi-color-neutral-600);
}
</style>
