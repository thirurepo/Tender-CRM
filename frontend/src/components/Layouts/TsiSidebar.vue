<!--
  The Tender CRM design's nav sidebar: brand mark, grouped navigation, a
  quick-jump affordance, and a user chip. Replaces AppSidebar.vue's dynamic
  saved-views nav, which doesn't fit this design's fixed grouped layout.

  Only "Leads" and "Clients" are live routes (this design pass's scope) —
  every other nav item (Activity Feed, Tasks, Tickets, Dashboard, Marketing,
  Reports) renders but does nothing yet, matching the plan's decision to keep
  them present-but-inert rather than hide them.
-->
<template>
  <aside class="tsi-sidebar">
    <div class="tsi-sidebar__brand">
      <span class="tsi-sidebar__brand-name">Tender</span>
      <span class="tsi-sidebar__brand-rule" />
      <span class="tsi-sidebar__brand-sub">CRM · Frappe</span>
    </div>

    <button class="tsi-sidebar__quickjump" type="button" @click="() => {}">
      <span>Quick jump</span>
      <span>/</span>
    </button>

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
import { computed } from 'vue'
import { createResource } from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/users'

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

const navGroups = computed(() => [
  {
    label: 'CRM',
    items: [
      { label: 'Activity Feed', count: '—' },
      { label: 'Leads', count: leadCount.data ?? '…', route: 'Leads' },
      { label: 'Clients', count: clientCount.data ?? '…', route: 'Organizations' },
      { label: 'Tasks', count: '—' },
      { label: 'Tickets', count: '—' },
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
.tsi-sidebar__brand-sub {
  display: block;
  font-size: 11px;
  text-transform: uppercase;
  color: var(--tsi-color-neutral-600);
  margin-top: var(--tsi-space-1);
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
