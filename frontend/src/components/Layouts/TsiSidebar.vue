<!--
  The Tender CRM design's nav sidebar: brand mark, grouped navigation, a
  quick-jump affordance, a user chip and a collapse toggle. Replaces
  AppSidebar.vue's dynamic saved-views nav, which doesn't fit this design's
  fixed grouped layout.

  "Activity Feed", "Leads", "Clients", "Deals", "Contacts", "Notes", "Call
  Logs", "Tasks" and "Tickets" are live routes, as is Dashboard's "Main". This
  sidebar replaced stock AppSidebar on desktop, so it also has to carry what
  AppSidebar gave every user and the design had dropped: the notifications
  bell (its panel is mounted by DesktopLayout) and the user menu (logout, theme,
  apps switcher) behind the user chip. The remaining Dashboard items,
  Marketing and Reports render but do nothing yet, matching the plan's decision
  to keep them present-but-inert rather than hide them.

  The "Settings" group at the foot of the nav is different in kind: its items
  are not routes but pages of the Settings dialog (Settings.vue), and clicking
  one opens the dialog on that page. It is collapsible because the list is long
  (up to ~19 pages for a manager) and would otherwise push the CRM links off
  a laptop screen.

  Collapsed, the sidebar narrows to an icon rail. The inert placeholders drop
  out of it rather than shrinking to icons that do nothing, and the settings
  group becomes a single gear — a rail is for the things you can actually act
  on, and every icon on it should survive being unlabelled.
-->
<template>
  <aside class="tsi-sidebar" :class="{ 'tsi-sidebar--collapsed': isCollapsed }">
    <div class="tsi-sidebar__brand">
      <div class="tsi-sidebar__brand-row">
        <BrandLogo v-model="brand" class="tsi-sidebar__brand-logo" />
        <span v-if="!isCollapsed" class="tsi-sidebar__brand-name">
          CRM
        </span>
      </div>
      <span v-if="!isCollapsed" class="tsi-sidebar__brand-rule" />
    </div>

    <Tooltip :text="__('Quick jump')" placement="right" :disabled="!isCollapsed">
      <button
        class="tsi-sidebar__quickjump"
        type="button"
        :aria-label="__('Quick jump')"
        @click="quickJumpOpen = true"
      >
        <template v-if="isCollapsed">
          <SearchIcon class="tsi-sidebar__icon" />
        </template>
        <template v-else>
          <span>{{ __('Quick jump') }}</span>
          <span>/</span>
        </template>
      </button>
    </Tooltip>

    <QuickJump v-model="quickJumpOpen" />

    <nav class="tsi-sidebar__nav">
      <!-- Collapsed: one flat rail of the routes, no group headings — there is
           no width to label a group in, and the counts have nowhere to sit. -->
      <template v-if="isCollapsed">
        <Tooltip
          v-for="item in railItems"
          :key="item.label"
          :text="__(item.label)"
          placement="right"
        >
          <router-link
            :to="{ name: item.route }"
            class="tsi-sidebar__item tsi-sidebar__item--rail"
            :aria-label="__(item.label)"
          >
            <component :is="item.icon" class="tsi-sidebar__icon" />
          </router-link>
        </Tooltip>

        <Tooltip :text="__('Notifications')" placement="right">
          <button
            id="notifications-btn"
            type="button"
            class="tsi-sidebar__item tsi-sidebar__item--rail tsi-sidebar__item--button tsi-sidebar__bell"
            :aria-label="__('Notifications')"
            @click="toggleNotificationPanel"
          >
            <NotificationsIcon class="tsi-sidebar__icon" />
            <span v-if="unreadNotificationsCount" class="tsi-sidebar__dot" />
          </button>
        </Tooltip>

        <Tooltip :text="__('Settings')" placement="right">
          <button
            type="button"
            class="tsi-sidebar__item tsi-sidebar__item--rail tsi-sidebar__item--button"
            :class="{ 'tsi-sidebar__item--active': showSettings }"
            :aria-label="__('Settings')"
            @click="openSettings(firstSettingsPage)"
          >
            <SettingsIcon class="tsi-sidebar__icon" />
          </button>
        </Tooltip>
      </template>

      <template v-else>
        <!-- id is load-bearing: Notifications.vue's click-outside handler
             ignores #notifications-btn, without which clicking the bell while
             the panel is open would close it and then immediately reopen it. -->
        <button
          id="notifications-btn"
          type="button"
          class="tsi-sidebar__item tsi-sidebar__item--button"
          @click="toggleNotificationPanel"
        >
          <span class="tsi-sidebar__item-label">
            <NotificationsIcon class="tsi-sidebar__icon" />
            <span>{{ __('Notifications') }}</span>
          </span>
          <span v-if="unreadNotificationsCount" class="tsi-sidebar__count">
            {{ unreadNotificationsCount }}
          </span>
        </button>

        <div
          v-for="group in navGroups"
          :key="group.label"
          class="tsi-sidebar__group"
        >
          <div class="tsi-sidebar__group-label">{{ group.label }}</div>
          <component
            :is="item.route ? 'router-link' : 'span'"
            v-for="item in group.items"
            :key="item.label"
            :to="item.route ? { name: item.route } : undefined"
            class="tsi-sidebar__item"
            :class="{ 'tsi-sidebar__item--inert': !item.route }"
          >
            <span class="tsi-sidebar__item-label">
              <component
                :is="item.icon"
                v-if="item.icon"
                class="tsi-sidebar__icon"
              />
              <span>{{ item.label }}</span>
            </span>
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
            <span class="tsi-sidebar__chevron">
              {{ settingsExpanded ? '−' : '+' }}
            </span>
          </button>
          <template v-if="settingsExpanded">
            <template v-for="section in settingsTabs" :key="section.label">
              <div class="tsi-sidebar__subgroup-label">{{ section.label }}</div>
              <button
                v-for="page in section.items"
                :key="page.label"
                type="button"
                class="tsi-sidebar__item tsi-sidebar__item--button"
                :class="{
                  'tsi-sidebar__item--active': isSettingsPageOpen(page.label),
                }"
                @click="openSettings(page.label)"
              >
                <span>{{ page.label }}</span>
              </button>
            </template>
          </template>
        </div>
      </template>
    </nav>

    <UserDropdown :isCollapsed="isCollapsed" placement="top-start">
      <template #trigger>
        <button
          type="button"
          class="tsi-sidebar__user"
          :aria-label="__('User menu')"
        >
          <span class="tsi-sidebar__user-avatar">{{ initials }}</span>
          <div v-if="!isCollapsed">
            <div class="tsi-sidebar__user-name">{{ user.full_name }}</div>
            <div class="tsi-sidebar__user-sub">
              Sales Unit · {{ salesUnit }}
            </div>
          </div>
        </button>
      </template>
    </UserDropdown>

    <Tooltip
      :text="__('Expand sidebar')"
      placement="right"
      :disabled="!isCollapsed"
    >
      <button
        type="button"
        class="tsi-sidebar__collapse"
        :aria-label="isCollapsed ? __('Expand sidebar') : __('Collapse sidebar')"
        :aria-expanded="!isCollapsed"
        @click="toggleCollapsed"
      >
        <CollapseSidebar
          class="tsi-sidebar__icon"
          :class="{ 'tsi-sidebar__icon--flipped': isCollapsed }"
        />
        <span v-if="!isCollapsed">{{ __('Collapse') }}</span>
      </button>
    </Tooltip>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'
import { createResource, Tooltip } from 'frappe-ui'
import SearchIcon from '~icons/lucide/search'
import ActivityIcon from '@/components/Icons/ActivityIcon.vue'
import LeadsIcon from '@/components/Icons/LeadsIcon.vue'
import OrganizationsIcon from '@/components/Icons/OrganizationsIcon.vue'
import TaskIcon from '@/components/Icons/TaskIcon.vue'
import TicketsIcon from '@/components/Icons/TicketsIcon.vue'
import DealsIcon from '@/components/Icons/DealsIcon.vue'
import ContactsIcon from '@/components/Icons/ContactsIcon.vue'
import NoteIcon from '@/components/Icons/NoteIcon.vue'
import PhoneIcon from '@/components/Icons/PhoneIcon.vue'
import NotificationsIcon from '@/components/Icons/NotificationsIcon.vue'
import DashboardIcon from '@/components/Icons/DashboardIcon.vue'
import EmailIcon from '@/components/Icons/EmailIcon.vue'
import WhatsAppIcon from '@/components/Icons/WhatsAppIcon.vue'
import DocumentIcon from '@/components/Icons/DocumentIcon.vue'
import SettingsIcon from '@/components/Icons/SettingsIcon.vue'
import CollapseSidebar from '@/components/Icons/CollapseSidebar.vue'
import BrandLogo from '@/components/BrandLogo.vue'
import QuickJump from '@/components/QuickJump.vue'
import UserDropdown from '@/components/UserDropdown.vue'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/users'
import { getSettings } from '@/stores/settings'
import {
  unreadNotificationsCount,
  notificationsStore,
} from '@/stores/notifications'
import { showSettings, activeSettingsPage } from '@/composables/settings'
import { useSettingsTabs } from '@/composables/settingsTabs'

// Owned here rather than inside QuickJump because two things open the dialog:
// this button, and the global "/" shortcut QuickJump binds for itself.
const quickJumpOpen = ref(false)

const session = sessionStore()
const { toggle: toggleNotificationPanel } = notificationsStore()
const { getUser } = usersStore()
const user = computed(() => getUser(session.user))

// Same source as the stock sidebar's logo, so a logo uploaded on the Brand
// settings page shows up here too; CRMLogo is the fallback (see BrandLogo.vue).
const { brand } = getSettings()

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

// Both of these are layout preferences, not data, so they live in the
// browser. Storage can throw (private mode, blocked site data); when it does
// the sidebar just opens in its default state every time.
const COLLAPSED_KEY = 'tsi_sidebar_collapsed'
const SETTINGS_EXPANDED_KEY = 'tsi_sidebar_settings_expanded'

function readFlag(key) {
  try {
    return localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function writeFlag(key, value) {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // Not persisting a toggle is harmless; see readFlag().
  }
}

const isCollapsed = ref(readFlag(COLLAPSED_KEY))
const settingsExpanded = ref(readFlag(SETTINGS_EXPANDED_KEY))

function toggleCollapsed() {
  isCollapsed.value = !isCollapsed.value
  writeFlag(COLLAPSED_KEY, isCollapsed.value)
}

function toggleSettings() {
  settingsExpanded.value = !settingsExpanded.value
  writeFlag(SETTINGS_EXPANDED_KEY, settingsExpanded.value)
}

// The same permission-filtered list the dialog renders, so a non-manager sees
// only the pages they can actually open (Profile, Preferences, Templates, ...).
const settingsTabs = useSettingsTabs()

// What the dialog itself opens on when nothing else is chosen — the rail's
// gear has no page of its own to name.
const firstSettingsPage = computed(
  () => settingsTabs.value[0]?.items[0]?.label || '',
)

// Settings.vue watches activeSettingsPage and switches its right pane to the
// matching page, so setting both refs is all "open on this page" takes.
function openSettings(label) {
  activeSettingsPage.value = label
  showSettings.value = true
}

function isSettingsPageOpen(label) {
  return showSettings.value && activeSettingsPage.value === label
}

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

// Deals, Notes and Call Logs get the same "how big is this thing?" chip as the
// rest of the CRM group. Contacts deliberately does not: it is a lookup list
// rather than a queue anyone works through, so a total would be noise.
const dealCount = createResource({
  url: 'frappe.client.get_count',
  params: { doctype: 'CRM Deal' },
  auto: true,
  transform: (value) => value ?? 0,
})
const noteCount = createResource({
  url: 'frappe.client.get_count',
  params: { doctype: 'FCRM Note' },
  auto: true,
  transform: (value) => value ?? 0,
})
const callLogCount = createResource({
  url: 'frappe.client.get_count',
  params: { doctype: 'CRM Call Log' },
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

const navGroups = computed(() => [
  {
    label: 'CRM',
    items: [
      {
        label: 'Activity Feed',
        icon: ActivityIcon,
        count: recentActivityCount.data ?? '…',
        route: 'Activity Feed',
      },
      {
        label: 'Leads',
        icon: LeadsIcon,
        count: leadCount.data ?? '…',
        route: 'Leads',
      },
      {
        label: 'Clients',
        icon: OrganizationsIcon,
        count: clientCount.data ?? '…',
        route: 'Organizations',
      },
      {
        label: 'Deals',
        icon: DealsIcon,
        count: dealCount.data ?? '…',
        route: 'Deals',
      },
      {
        label: 'Contacts',
        icon: ContactsIcon,
        route: 'Contacts',
      },
      {
        label: 'Tasks',
        icon: TaskIcon,
        count: taskCount.data ?? '…',
        route: 'Tasks',
      },
      {
        label: 'Tickets',
        icon: TicketsIcon,
        count: ticketCount.data ?? '…',
        route: 'Tickets',
      },
      {
        label: 'Notes',
        icon: NoteIcon,
        count: noteCount.data ?? '…',
        route: 'Notes',
      },
      {
        label: 'Call Logs',
        icon: PhoneIcon,
        count: callLogCount.data ?? '…',
        route: 'Call Logs',
      },
    ],
  },
  {
    label: 'Dashboard',
    items: [
      { label: 'Main', icon: DashboardIcon, route: 'Dashboard' },
      { label: 'Leads', icon: LeadsIcon },
      { label: 'Clients', icon: OrganizationsIcon },
      { label: 'Hours', icon: DashboardIcon },
    ],
  },
  {
    label: 'Marketing',
    items: [
      { label: 'Email campaign', icon: EmailIcon },
      { label: 'WhatsApp', icon: WhatsAppIcon },
    ],
  },
  {
    label: 'Reports',
    items: [
      { label: 'Weekly', icon: DocumentIcon },
      { label: 'Clients', icon: DocumentIcon },
    ],
  },
])

// Only the routed entries: an icon rail of inert placeholders would be a row
// of icons that look clickable and aren't.
const railItems = computed(() =>
  navGroups.value.flatMap((group) => group.items.filter((item) => item.route)),
)
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
  transition: width 150ms ease-in-out;
}
.tsi-sidebar--collapsed {
  width: 56px;
}

.tsi-sidebar__brand {
  padding: var(--tsi-space-4) var(--tsi-space-3) var(--tsi-space-3);
}
.tsi-sidebar--collapsed .tsi-sidebar__brand {
  padding: var(--tsi-space-3) 0;
}
.tsi-sidebar__brand-row {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-2);
}
.tsi-sidebar--collapsed .tsi-sidebar__brand-row {
  justify-content: center;
}
.tsi-sidebar__brand-logo {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: var(--tsi-radius-sm);
  overflow: hidden;
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
.tsi-sidebar--collapsed .tsi-sidebar__quickjump {
  margin: 0 auto var(--tsi-space-2);
  width: 32px;
  justify-content: center;
}

.tsi-sidebar__nav {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--tsi-space-2);
}
.tsi-sidebar--collapsed .tsi-sidebar__nav {
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
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
.tsi-sidebar__item-label {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-2);
  min-width: 0;
}
.tsi-sidebar__item--rail {
  width: 32px;
  height: 32px;
  padding: 0;
  justify-content: center;
}
.tsi-sidebar__icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
.tsi-sidebar__icon--flipped {
  transform: rotateY(180deg);
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
.tsi-sidebar__item--rail.tsi-sidebar__item--button {
  width: 32px;
}
.tsi-sidebar__bell {
  position: relative;
}
/* Unread marker on the collapsed rail, where the count chip has no room. */
.tsi-sidebar__dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--tsi-color-accent-700);
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
  /* Now a <button> (it opens the user menu), so reset the native chrome. */
  width: 100%;
  background: none;
  border: 0;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--tsi-space-2);
  padding: var(--tsi-space-3);
  border-top: 1px solid var(--tsi-color-divider);
}
.tsi-sidebar--collapsed .tsi-sidebar__user {
  justify-content: center;
  padding: var(--tsi-space-2) 0;
}
.tsi-sidebar__user:hover {
  background: var(--tsi-color-bg);
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

.tsi-sidebar__collapse {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-2);
  width: 100%;
  padding: var(--tsi-space-2) var(--tsi-space-3);
  border: 0;
  border-top: 1px solid var(--tsi-color-divider);
  background: none;
  font-family: inherit;
  font-size: 12px;
  color: var(--tsi-color-neutral-600);
  cursor: pointer;
}
.tsi-sidebar--collapsed .tsi-sidebar__collapse {
  justify-content: center;
  padding: var(--tsi-space-2) 0;
}
.tsi-sidebar__collapse:hover {
  background: var(--tsi-color-bg);
  color: var(--tsi-color-text);
}
</style>
