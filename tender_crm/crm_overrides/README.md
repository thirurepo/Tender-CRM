# crm_overrides

Everything Tender CRM changes about the behaviour of Frappe CRM and ERPNext.
`tender_crm/hooks.py` is the map of *what* is wired; this is the *why*.

## What is here

| File | What it does |
| --- | --- |
| `erpnext_link.py` | Keeps a CRM Deal and the ERPNext Quotation / Sales Order raised from it pointing at each other, and moves the deal along the pipeline as those documents are submitted. |
| `lead_import.py` | Keeps `tsi_converted_date` / `tsi_last_status_change` on CRM Lead accurate for leads worked normally, after the legacy CRM import (see `tender_crm/Import_crm_data/import_leads.py`) sets both directly from historical CSV data. |
| `todo.py` | A whitelisted `get_todos` endpoint the tsi-crm Tasks tab calls alongside `crm.api.activities.get_activities`, so core `ToDo` records (created by tsi-crm's existing Assign-To feature) show up next to `CRM Task`. Additive only — does not override the vendor endpoint. |

## The gap this closes

Upstream `crm` already does half of CRM ↔ ERPNext, through its own
`ERPNext CRM Settings` single: it can create an ERPNext **Customer** when a deal
reaches a chosen status, and it stamps `crm_deal` onto a **Quotation** so the
quote knows which deal it came from.

It stops there. In particular:

- **The Sales Order has no link back to the deal.** crm derives it on demand by
  walking each order item's `prevdoc_docname` to its quotation and reading
  `crm_deal` off that. That works for one lookup inside a hook and is useless for
  a report, a list view filter, or a person looking at an order.
- **Nothing moves the deal.** A quotation can be raised and an order submitted
  while the deal sits in whatever stage someone last dragged it to, so the
  pipeline stops reflecting reality exactly when it matters most.

`erpnext_link.py` adds both, driven by switches on `Tender CRM Settings`.

## Three rules the handlers follow

**1. Submit, not save.** Every handler hangs off `on_submit`. A draft quotation
is a working document — revised, deleted, re-made — and treating one as evidence
that a deal reached proposal stage produced deals that jumped forward and then
sat there after the draft was thrown away.

**2. Forward only.** Deal status is only ever moved *later* in the pipeline,
compared by the `position` field on `CRM Deal Status` — the same number the
kanban board orders its columns by, so "forward" means what it looks like on
screen. A revised quotation against a deal already in Negotiation must not drag
it back to Proposal.

**3. Best effort, never fatal.** These handlers run inside another document's
submit. If one raised, it would abort that submit and roll back the transaction —
a broken convenience link would stop the business from taking orders. `_best_effort`
converts any failure into an Error Log entry plus a non-blocking alert. That trade
is deliberate; if you add a handler here, route it through `_best_effort` too.

## Things that will bite you

- **Status changes go through `doc.save()`, not `db.set_value`.** CRM Deal's own
  `validate` is what appends to the status change log, stamps `closed_date` and
  fills the default probability for the new status. Writing the column directly
  leaves a deal that claims to be Won with a 10% probability, no closing date, and
  no record of when it got there.

- **The link stamps go through `db.set_value`, not `doc.save()`.** The opposite
  reasoning: neither field participates in validation, the sales order is mid-submit
  and must not be re-saved from inside its own hook, and saving the deal would fire
  crm's `create_customer_in_erpnext` for no reason.

- **`ignore_permissions` on the deal save is load-bearing.** A Sales User with no
  write access to CRM Deal must still be able to submit a sales order. This is a
  system consequence of a submit, not an edit by the person who clicked it — which
  is also why every one of these changes leaves a comment on the deal.

- **Cancelling a sales order does not reopen the deal.** The stamp is cleared and a
  comment is left; the status is not touched. An order is usually re-raised the
  same week, and quietly reopening a closed deal is a bigger surprise than a stale
  status. The comment is what prompts a human to make the call.

- **`erpnext` is not a required app.** Everything here degrades to a no-op without
  it, so a CRM-only site can still run this app for the pipeline and territories
  alone. Keep it that way — guard any new erpnext import.
