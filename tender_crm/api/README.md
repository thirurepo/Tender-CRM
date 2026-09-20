# api

Tender CRM's whitelisted **read** endpoints — screens the tsi-crm frontend has
that the vendor `crm` app has no equivalent of.

The line between this package and `crm_overrides/` is the point of it existing.
`crm_overrides/` holds everything that *changes* how Frappe CRM or ERPNext
behaves, and is wired from `hooks.py`. Nothing here changes anything: these
endpoints only read, and a whitelisted method needs no hook — the decorator
registers it at import time. That is why `hooks.py` has a "Read APIs" block
saying so rather than any entries.

## What is here

| File | Endpoint | Called from |
| --- | --- | --- |
| `search.py` | `quick_jump(query, limit)` — one ranked search over Leads, Clients, Contacts, Tickets and Deals, by name *and* contact detail (email, mobile, phone, Skype, legacy ID). | `frontend/src/components/QuickJump.vue` — the sidebar's "Quick jump" and the `/` key. |
| `client_activities.py` | `get_client_activities(name)` — a client's Activity/Emails/Comments/Calls/Tasks/Notes/Attachments, merged with the lead it was converted from (`tsi_converted_from_lead`) and any deals raised against it. Same five-tuple shape as `crm.api.activities.get_activities`. | `frontend/src/components/Activities/Activities.vue`, when `doctype` is `CRM Organization`. |
| `project_account_activities.py` | `get_project_account_activities(name)` — a project account's Activity/Comments/Tasks/Notes/Attachments, including field changes from Version. Same five-tuple shape as `crm.api.activities.get_activities`. | `frontend/src/components/Activities/Activities.vue`, when `doctype` is `Project Account`. |
| `project_account_timesheet.py` | `get_project_account_timesheet(name, from_date, to_date)` — hours per developer on a project account, from tsiconnect's Flexi Timesheet / Flexi Hours matched on `account` = `company` and `project`. Counts Active, Idle and Manual activity; Break and Private are excluded. Reads Flexi Timesheet directly after checking read on the Project Account (Sales roles cannot read it), and returns only developer names and hours. | `frontend/src/components/ProjectAccountTimesheet.vue` — the Timesheet tab on a Project Account. |
| `feed.py` | `get_feed(before, limit, entities, user, from_date, to_date)` — cross-record activity, newest first, cursor-paginated. `get_recent_count(hours)` — the sidebar chip. | `frontend/src/pages/ActivityFeed.vue`, `TsiSidebar.vue`. |
| `linked_deals.py` | `get_linked_deals(contact)` — crm's `get_linked_deals` (same rows, same permission rule) minus deactivated deals (`CRM Deal.tsi_disabled`). | `frontend/src/pages/Contact.vue`, `MobileContact.vue` — the Deals tab. |
| `territory_geo.py` | `get_territory_geo(territory)` — the countries a CRM Territory covers, each with currency and timezones. `get_country_geo(country)` — one country's currency and timezones. | The "TSI Client Territory Geo" CRM Form Script on CRM Organization (`territory_geo_schema.py`). |

`crm_overrides/todo.py` (`get_todos`) is a sibling that predates this package.
It is additive-only too, and would belong here if written today; it stays put
because moving it would change a working frontend URL for no functional gain.

## Two rules both endpoints follow

**1. Permission comes from `frappe.get_list`, never `get_all` or raw SQL, on
the records a user will see.** `get_list` is what applies crm's `org_hierarchy`
permission query condition on CRM Lead and CRM Deal — a Sales User sees their
own and their subtree's leads, not the company's — plus User Permissions.
`get_all` skips both silently. Verified on the live site: walking the entire
feed as each of Administrator (718 visible leads), eric (526) and matt (5)
references exactly the leads that user can open, and none they cannot.

**2. Routes go back as vue-router *named routes*, never URL strings** —
`{"name": "Organization", "params": {"organizationId": ...}}`. A CRM
Organization's docname is its free-text name, and `router.push` encodes a `/`
or `&` in it where a hand-built path would not.

## search.py

One endpoint looping five doctypes rather than five link searches, because the
ranking is cross-type: an exact Client-name match has to outrank a substring hit
on a Lead's phone number, and only code that sees every candidate can decide
that.

It is **not** built on `frappe.desk.search.search_link`. That searches `name` +
`title_field` + the doctype's `search_fields`, and none of these doctypes
declares `search_fields` — so it cannot find a lead by phone number, which is
the whole feature. `Controls/Link.vue` keeps using `search_link` for link
fields, which is what it is for.

Ceiling: `LIKE '%x%'` cannot use an index, so every query is a table scan. Right
at ~700–1,200 rows per doctype (tens of milliseconds); wrong somewhere north of
~50k, when the move is a MariaDB `FULLTEXT` index.

## feed.py

### The permission boundary

`Comment`, `Communication`, `ToDo` (as read here) and child-table rows have no
per-reference permission of their own — anyone with read on Comment can read
every comment on the site. **The parent record is the only boundary**, so every
event is filtered by one `get_list` per doctype against its parent before it is
returned. That same query resolves the title. Never fall back to per-row
`has_permission`: on CRM Lead that is a query with a hierarchy subquery per
document.

### Why a cursor, not pages

The permission pass removes rows *after* the database applied its LIMIT, so
"page 7" has no stable meaning. The cursor is an opaque `(timestamp, id)` pair —
the `id` because imports put many rows on the same timestamp. A page can come
back short with `has_more` still true (a user who can see little gets sparse
pages); the endpoint refetches up to four times to fill it, and the frontend
must drive "load more" from `has_more` alone.

### Event sources

| Source | In? | Why |
| --- | --- | --- |
| Record creation (all four) | yes | Only source covering CRM Organization and CRM Task at all — neither has `track_changes`. |
| `Comment` (`comment_type = "Comment"`) | yes | The only real content today: 2,849 legacy comments back to 2017. |
| `CRM Status Change Log` | yes | Status moves on CRM Lead and Ticket, typed and attributed, regardless of `track_changes`. |
| `Communication` | yes | Zero CRM rows today; on for when ticket mail arrives. |
| `CRM Call Log` | yes | Zero rows today; one cheap query. |
| `ToDo` | yes | Assignments. Filtered by parent record, like the rest. |
| `Version` | **off** | See below. |
| `CRM Notification` | no | The bell's per-user mention list, not a feed. |

### The legacy import, and why the feed is not 1,440 rows of it

Every lead and all but one client were created by the legacy import inside one
minute on 2026-09-14. Read naively, the feed's first ~1,440 rows are that one
script run. Three different traces, handled three ways:

- **Records** — their `creation` is the import's, but the importers carried the
  true date in `tsi_added_date`. The feed places a record at that date and
  credits it to "Legacy CRM", not to whoever ran the import. A record whose
  added date matches its creation day was created normally and keeps its real
  timestamp and owner.
- **Comments** — the comment importer backdated `creation` itself and kept the
  real author in `comment_email`. The feed reads `comment_email`, which is also
  Frappe's own convention for a comment's author. Its `Assigned`/`Shared`/`Info`
  rows (1,416 of them) are excluded by the `comment_type` filter.
- **ToDos** — all 174 were written in eight seconds with no legacy date to
  recover. Dropped when written on the import day against an imported record;
  the assignment itself is still on the lead.

None of this hardcodes the import date — each rule reads it off the data, and
each can only match on the day a given record was imported.

### Turning on `Version` (field changes)

Off because `tabVersion` is ~790k rows, 98% HRMS, and zero CRM. Its indexes do
not serve the feed's query, so it would scan backwards through HRMS rows. To
enable, first ship — each as an idempotent function in `setup.py` called from
**both** `install.py` and a thin `patches/` wrapper, per CLAUDE.md:

1. `frappe.db.add_index("Version", ["ref_doctype", "creation"])`
2. Property Setters enabling `track_changes` on CRM Organization and CRM Task,
   without which they never produce a Version row — which is also why client
   status changes are not in the feed today.

Then run `EXPLAIN` on the window query before flipping `ENABLE_VERSION_SOURCE`.
