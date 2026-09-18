<!--
  One row of the Activity Feed: who did what to which record, and when. The
  whole row links to the record through the named route the server built
  (tender_crm.api.feed._route_for), never a hand-assembled path.

  Every sentence here — "commented", "moved this to Qualified", "assigned this
  to Eric" — arrives already built and translated in `event.summary`. The row
  only lays it out; it does not interpret event types, beyond picking an icon
  and deciding whether a status pill or an excerpt is worth showing.
-->
<template>
  <router-link :to="event.route" class="feed-event">
    <div class="feed-event__avatar">
      <span v-if="!event.actor" class="feed-event__legacy" :title="__('Legacy CRM')">
        <FeatherIcon name="archive" class="size-3.5" />
      </span>
      <UserAvatar v-else :user="event.actor" size="md" />
    </div>

    <div class="feed-event__body">
      <div class="feed-event__line">
        <span class="feed-event__actor">{{ event.actor_name }}</span>
        <span class="feed-event__summary">{{ event.summary }}</span>
        <span class="feed-event__entity" :class="`feed-event__entity--${event.entity}`">
          {{ entityLabel }}
        </span>
        <span class="feed-event__title">{{ event.reference_title }}</span>
      </div>
      <div v-if="event.detail" class="feed-event__detail">{{ event.detail }}</div>
    </div>

    <div class="feed-event__meta">
      <FeatherIcon :name="icon" class="feed-event__icon" />
      <span v-if="isDateOnly(event)" class="feed-event__time" :title="__('Date carried over from the legacy CRM — no time of day was recorded')">
        {{ formatDate(event.timestamp, 'D MMM YYYY') }}
      </span>
      <TimelineTimestamp v-else :date="event.timestamp" class-name="feed-event__time" />
    </div>
  </router-link>
</template>

<script setup>
import { computed } from 'vue'
import { FeatherIcon } from 'frappe-ui'
import TimelineTimestamp from '@/components/Activities/TimelineTimestamp.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import { formatDate } from '@/utils'
import { isDateOnly } from '@/utils/activityFeed'

const props = defineProps({
  event: { type: Object, required: true },
})

// The sidebar's vocabulary, not doctype names: a CRM Organization is a
// "Client" everywhere a user can see it.
const ENTITY_LABELS = {
  lead: 'Lead',
  client: 'Client',
  task: 'Task',
  ticket: 'Ticket',
}

const ICONS = {
  created: 'plus-circle',
  comment: 'message-square',
  status_change: 'arrow-right-circle',
  email: 'mail',
  call: 'phone',
  assignment: 'user-plus',
  field_change: 'edit-3',
}

const entityLabel = computed(() => __(ENTITY_LABELS[props.event.entity] || props.event.entity))
const icon = computed(() => ICONS[props.event.event_type] || 'activity')
</script>

<style scoped>
.feed-event {
  display: flex;
  align-items: flex-start;
  gap: var(--tsi-space-3);
  padding: var(--tsi-space-2) var(--tsi-space-4);
  text-decoration: none;
  color: var(--tsi-color-text);
  font-family: var(--tsi-font-body);
  border-left: 2px solid transparent;
}
.feed-event:hover {
  background: var(--tsi-color-bg);
  border-left-color: var(--tsi-color-accent);
}

.feed-event__avatar {
  flex-shrink: 0;
  padding-top: 1px;
}
.feed-event__legacy {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--tsi-color-neutral-200);
  color: var(--tsi-color-neutral-600);
}

.feed-event__body {
  flex: 1;
  min-width: 0;
}
.feed-event__line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: var(--tsi-space-1);
  font-size: 13px;
  line-height: 1.5;
}
.feed-event__actor {
  font-weight: 600;
}
.feed-event__summary {
  color: var(--tsi-color-neutral-700);
}
.feed-event__title {
  font-weight: 600;
  color: var(--tsi-color-accent-700);
}
.feed-event__entity {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0 var(--tsi-space-1);
  border-radius: var(--tsi-radius-md);
  background: var(--tsi-color-neutral-200);
  color: var(--tsi-color-neutral-700);
}
/* One tint per sidebar entity, drawn from the design's two accent ramps so
   the four stay distinguishable without introducing new colours. */
.feed-event__entity--lead {
  background: var(--tsi-color-accent-100);
  color: var(--tsi-color-accent-800);
}
.feed-event__entity--client {
  background: var(--tsi-color-accent-2-100);
  color: var(--tsi-color-accent-2-800);
}
.feed-event__entity--ticket {
  background: var(--tsi-color-accent-2-200);
  color: var(--tsi-color-accent-2-900);
}

.feed-event__detail {
  margin-top: 2px;
  font-size: 12px;
  color: var(--tsi-color-neutral-600);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.feed-event__meta {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-1);
  flex-shrink: 0;
  padding-top: 2px;
}
.feed-event__icon {
  width: 13px;
  height: 13px;
  color: var(--tsi-color-neutral-500);
}
.feed-event__time,
:deep(.feed-event__time) {
  font-size: 12px;
  color: var(--tsi-color-neutral-500);
  white-space: nowrap;
}
</style>
