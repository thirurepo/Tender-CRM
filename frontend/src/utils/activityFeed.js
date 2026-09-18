// Pure helpers for the Activity Feed page (pages/ActivityFeed.vue), kept out
// of the component so they can be unit-tested without mounting anything.

/**
 * Append a freshly loaded page to the events already on screen, dropping any
 * event already present.
 *
 * The server's (timestamp, id) cursor should make overlap impossible, so this
 * is a guard rather than a mechanism: if a page ever does repeat a row — a
 * clock-skewed insert landing exactly on the cursor boundary, say — the cost of
 * letting it through is a duplicated row *and* a Vue key collision, which
 * breaks rendering of the whole list, not just the one row.
 */
export function appendPage(existing, incoming) {
  const seen = new Set(existing.map((event) => event.id))
  const fresh = (incoming || []).filter((event) => !seen.has(event.id))
  return existing.concat(fresh)
}

/**
 * Split an already newest-first event list into day sections for rendering.
 *
 * Sections are built on *change* of day while walking the list, so the output
 * order is exactly the input order — the server owns ordering, this only adds
 * headings. `now` is injectable so "Today"/"Yesterday" can be tested.
 */
export function groupByDay(events, now = new Date()) {
  const today = dayKey(now)
  const yesterday = dayKey(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1))

  const sections = []
  for (const event of events || []) {
    const key = dayKey(parseTimestamp(event.timestamp))
    let section = sections[sections.length - 1]
    if (!section || section.key !== key) {
      section = {
        key,
        label: key === today ? 'Today' : key === yesterday ? 'Yesterday' : null,
        date: key,
        events: [],
      }
      sections.push(section)
    }
    section.events.push(event)
  }
  return sections
}

/**
 * True for a timestamp the server placed at midnight because it only knows the
 * *day* — a record backfilled from the legacy CRM's added date (see
 * _creation_event in tender_crm/api/feed.py). Rendering "5 hours ago" or
 * "00:00" for those would claim a precision the data does not have, so the page
 * shows the date alone.
 */
export function isDateOnly(event) {
  return Boolean(event?.data?.legacy)
}

// The server sends "YYYY-MM-DD HH:MM:SS.ffffff" in the site's timezone. Parsing
// it by hand, rather than with `new Date(string)`, keeps it in local wall-clock
// time instead of letting the browser guess — a space-separated timestamp is
// not ISO 8601, and engines disagree about whether it means UTC.
function parseTimestamp(timestamp) {
  const [date, time = '00:00:00'] = String(timestamp).split(' ')
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute, second] = time.split(':').map((part) => parseInt(part, 10))
  return new Date(year, month - 1, day, hour || 0, minute || 0, second || 0)
}

function dayKey(date) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
