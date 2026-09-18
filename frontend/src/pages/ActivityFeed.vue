<!--
  The Activity Feed: everything happening across Leads, Clients, Tasks and
  Tickets, newest first, filterable by entity, by who did it, and by date.

  Backed by tender_crm.api.feed.get_feed. Two properties of that endpoint shape
  this page, and both are why it is an infinite scroll and not a paginator:

    * Pages are fetched by opaque cursor (`next_cursor`), never by offset or
      page number. The server permission-filters after it fetches, so there is
      no stable notion of "page 7" to jump to.
    * A page can come back *short* while `has_more` is still true — a user who
      can see few records gets sparse pages. So "load more" is driven by
      `has_more` alone, never by "the last page was smaller than the limit".
-->
<template>
  <LayoutHeader>
    <template #left-header>
      <ViewBreadcrumbs routeName="Activity Feed" />
    </template>
    <template #right-header>
      <Button :label="__('Refresh')" :iconLeft="LucideRefreshCcw" @click="reload" />
    </template>
  </LayoutHeader>

  <div class="feed">
    <div class="feed__filters">
      <div class="feed__chips" role="group" :aria-label="__('Filter by record type')">
        <button
          v-for="chip in ENTITY_CHIPS"
          :key="chip.value"
          type="button"
          class="feed__chip"
          :class="{ 'feed__chip--active': entities.includes(chip.value) }"
          :aria-pressed="entities.includes(chip.value)"
          @click="toggleEntity(chip.value)"
        >
          {{ __(chip.label) }}
        </button>
      </div>

      <div class="feed__controls">
        <label class="feed__control">
          <span>{{ __('By') }}</span>
          <select v-model="user" class="feed__select">
            <option value="">{{ __('Everyone') }}</option>
            <option v-for="u in userOptions" :key="u.name" :value="u.name">
              {{ u.full_name || u.name }}
            </option>
          </select>
        </label>
        <label class="feed__control">
          <span>{{ __('From') }}</span>
          <input v-model="fromDate" type="date" class="feed__select" :max="toDate || undefined" />
        </label>
        <label class="feed__control">
          <span>{{ __('To') }}</span>
          <input v-model="toDate" type="date" class="feed__select" :min="fromDate || undefined" />
        </label>
        <button v-if="hasFilters" type="button" class="feed__clear" @click="clearFilters">
          {{ __('Clear') }}
        </button>
      </div>
    </div>

    <div class="feed__list">
      <section v-for="section in sections" :key="section.key" class="feed__day">
        <h3 class="feed__day-label">
          {{ section.label ? __(section.label) : formatDate(section.date, 'dddd, D MMMM YYYY') }}
        </h3>
        <FeedEvent v-for="event in section.events" :key="event.id" :event="event" />
      </section>

      <div v-if="feed.error" class="feed__status">
        {{ __('Could not load activity.') }}
        <button type="button" class="feed__link" @click="loadMore">{{ __('Retry') }}</button>
      </div>
      <div v-else-if="feed.loading" class="feed__status">{{ __('Loading…') }}</div>
      <div v-else-if="!events.length" class="feed__status">
        {{ hasFilters ? __('No activity matches these filters.') : __('No activity yet.') }}
      </div>
      <div v-else-if="!hasMore" class="feed__status feed__status--end">
        {{ __("That's everything.") }}
      </div>

      <!-- Scrolled into view => fetch the next page. -->
      <div ref="sentinel" class="feed__sentinel" />
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Button, call } from 'frappe-ui'
import LayoutHeader from '@/components/LayoutHeader.vue'
import ViewBreadcrumbs from '@/components/ViewBreadcrumbs.vue'
import FeedEvent from '@/components/ActivityFeed/FeedEvent.vue'
import { usersStore } from '@/stores/users'
import { formatDate } from '@/utils'
import { appendPage, groupByDay } from '@/utils/activityFeed'
import LucideRefreshCcw from '~icons/lucide/refresh-ccw'

// The sidebar's four entities, in the sidebar's words. `value` is the slug
// tender_crm.api.feed.ENTITY_TO_DOCTYPE understands.
const ENTITY_CHIPS = [
  { value: 'lead', label: 'Leads' },
  { value: 'client', label: 'Clients' },
  { value: 'task', label: 'Tasks' },
  { value: 'ticket', label: 'Tickets' },
]

const PAGE_SIZE = 30

const { users } = usersStore()
// CRM users only: they are the people who act on leads and clients. The full
// site user list on this bench includes every HRMS employee.
const userOptions = computed(() => users.data?.crmUsers || [])

// No chip selected means "all four" — an empty filter is a non-filter, not
// "show nothing", so there is no state in which the page is blank by choice.
const entities = ref([])
const user = ref('')
const fromDate = ref('')
const toDate = ref('')

const events = ref([])
const cursor = ref(null)
const hasMore = ref(true)
// Own state rather than a createResource's: its `loading` belongs to whichever
// request is in flight, so a filter change mid-request would see "still
// loading" and skip fetching the new filters' first page entirely.
const feed = reactive({ loading: false, error: null })
// Bumped on every filter change; a response tagged with an older generation is
// discarded. Without it, a slow page for the *previous* filters can land after
// the new ones were applied and splice stale rows into the list.
let generation = 0

const hasFilters = computed(
  () => entities.value.length > 0 || Boolean(user.value || fromDate.value || toDate.value),
)
const sections = computed(() => groupByDay(events.value))

async function loadMore() {
  if (feed.loading || !hasMore.value) return
  const requestedFor = generation
  feed.loading = true
  feed.error = null
  try {
    const page = await call('tender_crm.api.feed.get_feed', {
      before: cursor.value,
      limit: PAGE_SIZE,
      entities: entities.value.length ? entities.value : null,
      user: user.value || null,
      from_date: fromDate.value || null,
      // A bare date means "up to and including that day", and the server
      // compares against full timestamps.
      to_date: toDate.value ? `${toDate.value} 23:59:59.999999` : null,
    })
    if (requestedFor !== generation) return

    events.value = appendPage(events.value, page.events)
    cursor.value = page.next_cursor
    hasMore.value = page.has_more
  } catch (error) {
    if (requestedFor === generation) feed.error = error
    return
  } finally {
    if (requestedFor === generation) feed.loading = false
  }
  // A short page with more behind it (sparse permissions) may not fill the
  // screen, and then the sentinel never *re*-enters view to trigger the next
  // load. Check again rather than leaving the user stranded above the fold.
  queueSentinelCheck()
}

function reload() {
  generation += 1
  events.value = []
  cursor.value = null
  hasMore.value = true
  // The superseded request's `finally` will not touch these (its generation is
  // stale), so the new one must be free to start.
  feed.loading = false
  feed.error = null
  loadMore()
}

function toggleEntity(value) {
  const i = entities.value.indexOf(value)
  entities.value = i === -1 ? [...entities.value, value] : entities.value.filter((v) => v !== value)
}

function clearFilters() {
  entities.value = []
  user.value = ''
  fromDate.value = ''
  toDate.value = ''
}

watch([entities, user, fromDate, toDate], reload)

// Infinite scroll: an IntersectionObserver on an empty div after the last row,
// with a generous rootMargin so the next page is usually in before the user
// reaches the bottom.
const sentinel = ref(null)
let observer = null

function sentinelVisible() {
  const el = sentinel.value
  if (!el) return false
  const rect = el.getBoundingClientRect()
  return rect.top < window.innerHeight + 400
}

function queueSentinelCheck() {
  requestAnimationFrame(() => {
    if (hasMore.value && sentinelVisible()) loadMore()
  })
}

onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadMore()
    },
    { rootMargin: '400px' },
  )
  if (sentinel.value) observer.observe(sentinel.value)
  reload()
})

onBeforeUnmount(() => observer?.disconnect())
</script>

<style scoped>
.feed {
  font-family: var(--tsi-font-body);
  color: var(--tsi-color-text);
  max-width: 960px;
}

.feed__filters {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--tsi-space-2);
  padding: var(--tsi-space-3) var(--tsi-space-4);
  background: var(--tsi-color-neutral-100);
  border-bottom: 1px solid var(--tsi-color-divider);
}

.feed__chips {
  display: flex;
  gap: var(--tsi-space-1);
}
.feed__chip {
  font-size: 12px;
  padding: 3px var(--tsi-space-2);
  border: 1px solid var(--tsi-color-divider);
  border-radius: var(--tsi-radius-lg);
  background: transparent;
  color: var(--tsi-color-neutral-700);
  cursor: pointer;
}
.feed__chip:hover {
  background: var(--tsi-color-bg);
}
.feed__chip--active {
  background: var(--tsi-color-accent-100);
  border-color: var(--tsi-color-accent);
  color: var(--tsi-color-accent-800);
  font-weight: 600;
}

.feed__controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--tsi-space-2);
}
.feed__control {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-1);
  font-size: 12px;
  color: var(--tsi-color-neutral-600);
}
.feed__select {
  font-size: 12px;
  padding: 2px var(--tsi-space-1);
  border: 1px solid var(--tsi-color-divider);
  border-radius: var(--tsi-radius-md);
  background: var(--tsi-color-neutral-100);
  color: var(--tsi-color-text);
  height: 26px;
}
.feed__clear,
.feed__link {
  font-size: 12px;
  color: var(--tsi-color-accent-700);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
}

.feed__day-label {
  padding: var(--tsi-space-2) var(--tsi-space-4) var(--tsi-space-1);
  font-family: var(--tsi-font-heading);
  font-size: 12px;
  font-weight: var(--tsi-font-heading-weight);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--tsi-color-neutral-600);
  background: var(--tsi-color-neutral-100);
}

.feed__status {
  padding: var(--tsi-space-6) var(--tsi-space-4);
  text-align: center;
  font-size: 13px;
  color: var(--tsi-color-neutral-600);
}
.feed__status--end {
  padding: var(--tsi-space-4);
  font-size: 12px;
  color: var(--tsi-color-neutral-500);
}
.feed__sentinel {
  height: 1px;
}
</style>
