// The quick-jump dialog's pure helpers (src/utils/quickJump.js). The server
// does the searching and ranking; these cover what the dialog does with the
// ranked list — group headers and keyboard selection.

import { matchedHint, moveSelection, withGroupHeaders } from '@/utils/quickJump'

const result = (entity, name, extra = {}) => ({
  entity,
  badge: entity[0].toUpperCase() + entity.slice(1),
  doctype: `DT-${entity}`,
  name,
  title: name,
  ...extra,
})

describe('withGroupHeaders', () => {
  it('puts one header before each run of the same entity', () => {
    const rows = withGroupHeaders([
      result('lead', 'L1'),
      result('lead', 'L2'),
      result('client', 'C1'),
    ])
    expect(rows.map((r) => (r.kind === 'header' ? `#${r.label}` : r.result.name))).toEqual([
      '#Lead',
      'L1',
      'L2',
      '#Client',
      'C1',
    ])
  })

  it('keeps the server ranking even when an entity reappears', () => {
    // The server ranks across types; regrouping into buckets would reorder
    // L2 above C1 and throw that ranking away.
    const rows = withGroupHeaders([
      result('lead', 'L1'),
      result('client', 'C1'),
      result('lead', 'L2'),
    ])
    const names = rows.filter((r) => r.kind === 'result').map((r) => r.result.name)
    expect(names).toEqual(['L1', 'C1', 'L2'])
    expect(rows.filter((r) => r.kind === 'header')).toHaveLength(3)
  })

  it('numbers results contiguously, skipping headers', () => {
    const rows = withGroupHeaders([
      result('lead', 'L1'),
      result('client', 'C1'),
      result('contact', 'P1'),
    ])
    expect(rows.filter((r) => r.kind === 'result').map((r) => r.index)).toEqual([0, 1, 2])
  })

  it('gives every row a unique key', () => {
    const rows = withGroupHeaders([
      result('lead', 'L1'),
      result('client', 'C1'),
      result('lead', 'L2'),
    ])
    const keys = rows.map((r) => r.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('returns nothing for no results', () => {
    expect(withGroupHeaders([])).toEqual([])
    expect(withGroupHeaders(undefined)).toEqual([])
  })
})

describe('moveSelection', () => {
  it('moves down and up', () => {
    expect(moveSelection(0, 1, 3)).toBe(1)
    expect(moveSelection(2, -1, 3)).toBe(1)
  })

  it('wraps at both ends', () => {
    expect(moveSelection(2, 1, 3)).toBe(0)
    expect(moveSelection(0, -1, 3)).toBe(2)
  })

  it('stays at 0 when there is nothing to select', () => {
    expect(moveSelection(0, 1, 0)).toBe(0)
    expect(moveSelection(0, -1, 0)).toBe(0)
  })
})

describe('matchedHint', () => {
  it('names the field a non-title match came from', () => {
    expect(matchedHint({ matched_field: 'mobile_no' })).toBe('mobile')
    expect(matchedHint({ matched_field: 'tsi_contact_email' })).toBe('email')
  })

  it('says nothing for a title match, which the server sends as null', () => {
    expect(matchedHint({ matched_field: null })).toBeNull()
  })

  it('falls back to the raw fieldname rather than hiding the reason', () => {
    expect(matchedHint({ matched_field: 'some_new_field' })).toBe('some_new_field')
  })
})
