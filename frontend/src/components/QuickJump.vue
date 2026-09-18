<!--
  Quick jump: one search box over Leads, Clients, Contacts, Tickets and Deals,
  opened from the sidebar button or the "/" key anywhere outside a text field.

  The results always list, even when there is exactly one — jumping straight to
  a lone hit would navigate away from under someone still typing, and a single
  Enter is a small price for never being surprised. Enter or click opens the
  highlighted record.

  All the searching and ranking is server-side in
  tender_crm.api.search.quick_jump (see that module for why it is one endpoint
  over five doctypes rather than five link searches). This component only
  debounces, renders the ranked list with group headers, and handles the keys.
-->
<template>
  <Dialog v-model:open="open" size="xl">
    <template #body>
      <div class="quickjump" @keydown="onKeydown">
        <div class="quickjump__field">
          <FeatherIcon name="search" class="quickjump__icon" />
          <!-- `autofocus` is how frappe-ui's Dialog is told who owns initial
               focus; without it Reka's focus scope takes the first tabbable. -->
          <input
            v-model="query"
            autofocus
            class="quickjump__input"
            type="text"
            autocomplete="off"
            spellcheck="false"
            :placeholder="__('Search leads, clients, contacts by name, email, phone…')"
          />
          <kbd class="quickjump__kbd">esc</kbd>
        </div>

        <div class="quickjump__results">
          <div v-if="state === 'hint'" class="quickjump__empty">
            {{ __('Type at least two characters') }}
          </div>
          <div v-else-if="state === 'loading'" class="quickjump__empty">
            {{ __('Searching…') }}
          </div>
          <div v-else-if="state === 'error'" class="quickjump__empty">
            {{ __('Search failed. Try again.') }}
          </div>
          <div v-else-if="state === 'empty'" class="quickjump__empty">
            {{ __('No lead, client, contact, ticket or deal matches “{0}”', [query.trim()]) }}
          </div>

          <template v-else>
            <template v-for="row in rows" :key="row.key">
              <div v-if="row.kind === 'header'" class="quickjump__group">
                {{ row.label }}
              </div>
              <button
                v-else
                :ref="(el) => (rowEls[row.index] = el)"
                type="button"
                class="quickjump__row"
                :class="{ 'quickjump__row--active': row.index === selected }"
                @mousemove="selected = row.index"
                @click="go(row.result)"
              >
                <div class="quickjump__row-main">
                  <span class="quickjump__title">{{ row.result.title }}</span>
                  <span v-if="row.result.subtitle" class="quickjump__subtitle">
                    {{ row.result.subtitle }}
                  </span>
                </div>
                <div class="quickjump__row-meta">
                  <span v-if="matchedHint(row.result)" class="quickjump__hint">
                    {{ __('matched on {0}', [__(matchedHint(row.result))]) }}
                  </span>
                  <span v-if="row.result.status" class="quickjump__status">
                    {{ row.result.status }}
                  </span>
                </div>
              </button>
            </template>
            <div v-if="search.data?.truncated" class="quickjump__footer">
              {{ __('Showing the best matches — keep typing to narrow it down') }}
            </div>
          </template>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { watchDebounced } from '@vueuse/core'
import { createResource, Dialog, FeatherIcon } from 'frappe-ui'
import { useKeyboardShortcuts } from '@/composables/useKeyboardShortcuts'
import { matchedHint, moveSelection, withGroupHeaders } from '@/utils/quickJump'

// Matches MIN_QUERY_LENGTH in tender_crm/api/search.py. The server returns an
// empty list below it rather than erroring, so this only saves a round trip.
const MIN_QUERY_LENGTH = 2

const open = defineModel({ type: Boolean, default: false })

const router = useRouter()
const query = ref('')
const selected = ref(0)
const rowEls = ref([])

const search = createResource({
  url: 'tender_crm.api.search.quick_jump',
  auto: false,
})

const results = computed(() => search.data?.results || [])
const rows = computed(() => withGroupHeaders(results.value))

// One place decides what the panel shows, so the template's v-if chain cannot
// disagree with itself about, say, a stale result list under a spinner.
const state = computed(() => {
  if (query.value.trim().length < MIN_QUERY_LENGTH) return 'hint'
  if (search.error) return 'error'
  // Only a spinner when there is nothing to show yet; while refining an
  // existing query the previous results stay up rather than flashing away.
  if (search.loading && !results.value.length) return 'loading'
  // The last response may belong to an older query — the debounce has not
  // fired yet for what is in the box. Treat that as loading, not as "no match".
  if (search.data?.query !== query.value.trim()) return 'loading'
  if (!results.value.length) return 'empty'
  return 'results'
})

// 250 ms, the same order as Controls/Link.vue's link search: long enough not to
// fire on every keystroke of a name, short enough to feel live.
watchDebounced(
  query,
  (value) => {
    const trimmed = value.trim()
    if (trimmed.length < MIN_QUERY_LENGTH) return
    search.submit({ query: trimmed })
  },
  { debounce: 250 },
)

// A fresh result list starts the highlight at its best match.
watch(results, () => {
  selected.value = 0
  rowEls.value = []
})

watch(open, (isOpen) => {
  if (!isOpen) return
  // Reopening starts clean. Keeping the last query would be convenient
  // exactly once and confusing every other time.
  query.value = ''
  search.reset()
})

function onKeydown(e) {
  const count = results.value.length
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault()
    selected.value = moveSelection(selected.value, e.key === 'ArrowDown' ? 1 : -1, count)
    rowEls.value[selected.value]?.scrollIntoView({ block: 'nearest' })
  } else if (e.key === 'Enter' && state.value === 'results') {
    e.preventDefault()
    go(results.value[selected.value])
  }
}

function go(result) {
  if (!result) return
  open.value = false
  // A named route with params — never a hand-built path. A client's docname is
  // its free-text name, and router.push is what encodes a '/' or '&' in it.
  router.push(result.route)
}

// "/" from anywhere that isn't a text field. The composable already skips
// keystrokes inside inputs and while another dialog is open, and prevents the
// default so the "/" does not land in the search box as it gains focus.
useKeyboardShortcuts({
  active: () => !open.value,
  shortcuts: [{ keys: '/', action: () => (open.value = true) }],
})
</script>

<style scoped>
.quickjump {
  font-family: var(--tsi-font-body);
  color: var(--tsi-color-text);
}

.quickjump__field {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-2);
  padding: var(--tsi-space-3);
  border-bottom: 1px solid var(--tsi-color-divider);
}
.quickjump__icon {
  width: 16px;
  height: 16px;
  color: var(--tsi-color-neutral-600);
  flex-shrink: 0;
}
.quickjump__input {
  flex: 1;
  border: none;
  outline: none;
  box-shadow: none;
  background: transparent;
  font-size: 15px;
  padding: 0;
  color: var(--tsi-color-text);
}
.quickjump__input:focus {
  box-shadow: none;
}
.quickjump__kbd {
  font-size: 11px;
  color: var(--tsi-color-neutral-600);
  border: 1px solid var(--tsi-color-divider);
  border-radius: var(--tsi-radius-md);
  padding: 1px var(--tsi-space-1);
}

.quickjump__results {
  max-height: 60vh;
  overflow-y: auto;
  padding: var(--tsi-space-1) 0;
}
.quickjump__empty,
.quickjump__footer {
  padding: var(--tsi-space-4) var(--tsi-space-3);
  font-size: 13px;
  color: var(--tsi-color-neutral-600);
  text-align: center;
}
.quickjump__footer {
  padding: var(--tsi-space-2) var(--tsi-space-3);
  font-size: 12px;
  border-top: 1px solid var(--tsi-color-divider);
}

.quickjump__group {
  padding: var(--tsi-space-2) var(--tsi-space-3) var(--tsi-space-1);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--tsi-color-neutral-500);
}

.quickjump__row {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--tsi-space-3);
  padding: var(--tsi-space-2) var(--tsi-space-3);
  text-align: left;
  cursor: pointer;
  border-left: 2px solid transparent;
}
.quickjump__row--active {
  background: var(--tsi-color-accent-100);
  border-left-color: var(--tsi-color-accent);
}
.quickjump__row-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.quickjump__title {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.quickjump__subtitle {
  font-size: 12px;
  color: var(--tsi-color-neutral-600);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.quickjump__row-meta {
  display: flex;
  align-items: center;
  gap: var(--tsi-space-2);
  flex-shrink: 0;
}
.quickjump__hint {
  font-size: 11px;
  color: var(--tsi-color-neutral-500);
  font-style: italic;
}
.quickjump__status {
  font-size: 11px;
  padding: 1px var(--tsi-space-1);
  border-radius: var(--tsi-radius-md);
  background: var(--tsi-color-neutral-200);
  color: var(--tsi-color-neutral-800);
}
</style>
