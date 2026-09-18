// Pure helpers for the quick-jump dialog (components/QuickJump.vue), kept out
// of the component so they can be unit-tested without mounting anything.

/**
 * Turn the server's flat, ranked result list into render rows with a group
 * header inserted wherever the entity changes.
 *
 * Headers are inserted on *change*, not by bucketing: the server
 * (tender_crm.api.search.quick_jump) ranks across types, so the list can
 * legitimately run Lead, Client, Lead. Regrouping into one bucket per type
 * would throw that ranking away, and it is the one thing only the server can
 * compute. A repeated header is the honest cost of keeping it.
 *
 * `index` on each result row is its position among *results only* — what the
 * arrow keys move through, since headers are not selectable.
 */
export function withGroupHeaders(results) {
  const rows = []
  let lastEntity = null
  let index = 0
  for (const result of results || []) {
    if (result.entity !== lastEntity) {
      rows.push({
        kind: 'header',
        key: `header-${rows.length}`,
        label: result.badge,
      })
      lastEntity = result.entity
    }
    rows.push({
      kind: 'result',
      key: `${result.doctype}:${result.name}`,
      index: index++,
      result,
    })
  }
  return rows
}

/**
 * Move a keyboard selection through `count` items, wrapping at both ends —
 * the usual command-palette behaviour, so ArrowUp from the first result lands
 * on the last rather than doing nothing.
 */
export function moveSelection(current, delta, count) {
  if (!count) return 0
  return (((current + delta) % count) + count) % count
}

// Human labels for the server's `matched_field`, for the "matched on …" hint
// shown when the hit is not in the title. Fields not listed fall back to the
// raw fieldname, which is still better than no explanation at all.
const MATCHED_FIELD_LABELS = {
  email: 'email',
  email_id: 'email',
  tsi_contact_email: 'email',
  mobile_no: 'mobile',
  tsi_contact_mobile: 'mobile',
  phone: 'phone',
  tsi_contact_phone: 'phone',
  organization: 'company',
  company_name: 'company',
  website: 'website',
  tsi_skype: 'Skype',
  tsi_legacy_id: 'legacy ID',
  first_name: 'first name',
  last_name: 'last name',
  tsi_contact_first_name: 'contact name',
  tsi_contact_last_name: 'contact name',
  raised_by: 'raised by',
  name: 'ID',
}

/**
 * The "matched on …" hint for a result, or null when there is nothing to
 * explain. The server already sends a null matched_field for a title match,
 * since only it knows which field is each doctype's title.
 */
export function matchedHint(result) {
  const field = result?.matched_field
  if (!field) return null
  return MATCHED_FIELD_LABELS[field] || field
}
