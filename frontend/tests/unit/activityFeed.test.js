// The Activity Feed page's pure helpers (src/utils/activityFeed.js): appending
// cursor pages without duplicates, and splitting the list into day sections.

import { appendPage, groupByDay, isDateOnly } from '@/utils/activityFeed'

const ev = (id, timestamp, extra = {}) => ({ id, timestamp, ...extra })

describe('appendPage', () => {
  it('appends a new page after the existing events', () => {
    const merged = appendPage([ev('a', '2026-09-18 10:00:00.000000')], [ev('b', '2026-09-17 10:00:00.000000')])
    expect(merged.map((e) => e.id)).toEqual(['a', 'b'])
  })

  it('drops an event already on screen, so Vue keys never collide', () => {
    const merged = appendPage(
      [ev('a', '2026-09-18 10:00:00.000000'), ev('b', '2026-09-18 09:00:00.000000')],
      [ev('b', '2026-09-18 09:00:00.000000'), ev('c', '2026-09-18 08:00:00.000000')],
    )
    expect(merged.map((e) => e.id)).toEqual(['a', 'b', 'c'])
  })

  it('tolerates an empty or missing page', () => {
    expect(appendPage([ev('a', 'x')], []).map((e) => e.id)).toEqual(['a'])
    expect(appendPage([ev('a', 'x')], undefined).map((e) => e.id)).toEqual(['a'])
  })

  it('does not mutate the existing list', () => {
    const existing = [ev('a', 'x')]
    appendPage(existing, [ev('b', 'y')])
    expect(existing).toHaveLength(1)
  })
})

describe('groupByDay', () => {
  // Local wall-clock time, matching how the helper parses server timestamps.
  const now = new Date(2026, 8, 18, 15, 0, 0) // 18 Sep 2026, 15:00

  it('labels today and yesterday, and dates everything older', () => {
    const sections = groupByDay(
      [
        ev('a', '2026-09-18 09:17:23.000000'),
        ev('b', '2026-09-17 23:59:59.000000'),
        ev('c', '2026-08-14 00:00:00.000000'),
      ],
      now,
    )
    expect(sections.map((s) => [s.label, s.date])).toEqual([
      ['Today', '2026-09-18'],
      ['Yesterday', '2026-09-17'],
      [null, '2026-08-14'],
    ])
  })

  it('keeps several events of one day in a single section, in order', () => {
    const sections = groupByDay(
      [ev('a', '2026-09-14 08:46:09.000000'), ev('b', '2026-09-14 00:01:56.000000')],
      now,
    )
    expect(sections).toHaveLength(1)
    expect(sections[0].events.map((e) => e.id)).toEqual(['a', 'b'])
  })

  it('never reorders — the server owns ordering', () => {
    // Deliberately out of order: the helper adds headings, it does not sort.
    const sections = groupByDay(
      [
        ev('a', '2026-09-10 10:00:00.000000'),
        ev('b', '2026-09-12 10:00:00.000000'),
        ev('c', '2026-09-10 09:00:00.000000'),
      ],
      now,
    )
    expect(sections.map((s) => s.date)).toEqual(['2026-09-10', '2026-09-12', '2026-09-10'])
  })

  it('reads the server timestamp as local wall-clock time, not UTC', () => {
    // A late-evening event must land on its own day in every timezone the
    // test runs in; `new Date("2026-09-17 23:30:00")` is engine-dependent.
    const [section] = groupByDay([ev('a', '2026-09-17 23:30:00.000000')], now)
    expect(section.date).toBe('2026-09-17')
  })

  it('handles a date-only timestamp', () => {
    const [section] = groupByDay([ev('a', '2026-08-14')], now)
    expect(section.date).toBe('2026-08-14')
  })

  it('returns nothing for no events', () => {
    expect(groupByDay([], now)).toEqual([])
  })
})

describe('isDateOnly', () => {
  it('is true for a record backfilled from the legacy CRM', () => {
    expect(isDateOnly(ev('a', '2026-08-14 00:00:00.000000', { data: { legacy: true } }))).toBe(true)
  })

  it('is false for everything else', () => {
    expect(isDateOnly(ev('a', '2026-09-18 09:17:23.000000', { data: {} }))).toBe(false)
    expect(isDateOnly(ev('a', '2026-09-18 09:17:23.000000'))).toBe(false)
  })
})
