# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Tender CRM App Development

Three rules apply every time, no exceptions:

1. **Structured, commented changes** — header comment on new files, docstrings
   that explain *why* (not just what), follow the existing folder conventions, no
   orphaned commented-out code.
2. **No direct DB deletion without confirmation** — any DELETE/TRUNCATE/DROP or
   bulk UPDATE against real data (SQL, bench console, or `frappe.delete_doc`)
   requires a preview of affected rows and explicit user go-ahead first. Reads
   never need confirmation.
3. **Never edit core app files** — nothing under `apps/frappe/`, `apps/crm/`,
   `apps/erpnext/`. All customization goes through Custom Field/Property Setter,
   patches, or `hooks.py` overrides inside `apps/tender_crm/`.

Bench: `/home/thiru/frappe-bench2/` · Site: `erp.tendersoftware.in` ·
Custom app: `tender_crm`

## What this app is

`tender_crm` ("Tender CRM") is Tender Software India's customization layer over
the Frappe CRM (`crm`) app. It does two things: it replaces crm's generic sales
pipeline with one shaped like a tendered sale, and it finishes the CRM ↔ ERPNext
link that crm only half-implements.

It is the CRM sibling of `tsilearn` (which owns everything TSI changes about
`lms`) and `tsiconnect` (Frappe/ERPNext/HRMS). Keep the split: CRM customization
belongs here, not in tsiconnect.

## Layout

Note the doubled path — the app package is `tender_crm/`, the Frappe module inside
it is also `tender_crm/` (module name `Tender CRM`).

```
tender_crm/hooks.py                     # single source of truth for all wiring
tender_crm/pipeline.py                  # the TSI pipeline, as data
tender_crm/seed.py                      # idempotent pipeline seeding
tender_crm/setup.py                     # idempotent site setup (fields, settings, integration)
tender_crm/install.py                   # after_install
tender_crm/patches.txt                  # migration patch registry
tender_crm/fixtures/custom_field.json   # Custom Field JSON, hand-maintained
tender_crm/crm_overrides/               # behaviour — read its README.md first
tender_crm/patches/                     # thin wrappers over seed.py / setup.py
tender_crm/tender_crm/doctype/          # Tender CRM Settings
```

## Conventions

- **All wiring goes in `tender_crm/hooks.py`.** If you add a handler, register it
  there — the file is the map of what this app changes about the stack.

- **Setup work goes in `setup.py` or `seed.py`, never only in a patch.** There are
  two paths onto a site and they are not interchangeable:

  - `bench install-app` runs `after_install`, syncs fixtures, and marks every
    patch in `patches.txt` as already applied **without running it**.
  - `bench migrate` runs the patches and never calls `after_install`.

  So a step that lives only in a patch silently does not happen on a new site.
  Every step is written once as an idempotent function and called from both
  `install.py` and a thin wrapper in `patches/`. This has already been a bug here
  once — the ERPNext integration and the settings single were configured only by
  patches, and a fresh install left both untouched.

- **One-shot migrations get their own flag.** Re-ordering statuses that already
  exist is not safe to repeat: it would undo whatever the sales manager did on the
  kanban board. Those steps are guarded by a global default
  (`frappe.db.get_global` / `set_global`). Give each independent one-shot its
  **own** flag — deal and lead ordering shared one at first, and because the deal
  seed runs first and set the flag before the lead seed read it, lead statuses
  were created but never ordered.

- **Creating a missing record is always safe** and runs on every migrate. Only
  *modifying* an existing one needs the flag.

- **Schema changes to core doctypes** are Custom Fields, declared in
  `fixtures/custom_field.json` **and** created by `setup.ensure_link_fields()`.
  Both, always: the fixture carries the field to a new site, the function puts it
  on an existing one. Set `module` on every Custom Field or it is owned by no app.

- **Do not run `bench export-fixtures` on this bench** — it is known to wipe the
  sibling app's fixture JSON. Edit the JSON by hand.

- **Document-event handlers must not be able to abort the document they hang off.**
  They run inside another doctype's submit; raising would roll back a sales order
  the business was trying to take. Route everything through
  `crm_overrides.erpnext_link._best_effort`.

- **`erpnext` is deliberately not a `required_app`.** The linkage no-ops without
  it so a CRM-only site can still use the pipeline. Guard any new erpnext import.

- **Secrets:** never hardcode API keys. Read from `frappe.conf.get(...)` /
  site_config or env.

## Commands

Run from the bench root, not the app directory.

```bash
cd /home/thiru/frappe-bench2 && bench --site erp.tendersoftware.in migrate
```

```bash
cd /home/thiru/frappe-bench2 && bench --site erp.tendersoftware.in console
```

```bash
cd /home/thiru/frappe-bench2 && bench --site erp.tendersoftware.in execute tender_crm.setup.configure_erpnext_integration
```

```bash
cd /home/thiru/frappe-bench2 && bench --site erp.tendersoftware.in clear-cache
```

### Reloading code after a change (important)

Gunicorn runs under supervisor with `--preload`, so the app is imported in the
**master** process and workers are forked from that image. `kill -HUP <master>`
only re-forks from the *old* modules — your change will not be live. After
changing Python source you must restart the master (`kill -TERM <master-pid>`;
supervisor restarts it in ~3s) plus the processes that hold their own imports:
`bench_helper frappe schedule` and both `bench_helper frappe worker` processes.
Then `bench --site erp.tendersoftware.in clear-cache`.

Diagnostic tell for a stale process: an `ImportError`/`AttributeError` for a
symbol that demonstrably exists in the source, with traceback line numbers that
don't match the file. `bench console` and `bench execute` are fresh processes and
will pass while the web tier still fails — passing there does **not** prove the
running site is fixed.

## Testing changes safely

`erp.tendersoftware.in` is production. Exercise document flows inside a
transaction and roll it back rather than creating test records:

```python
try:
    ...  # create deal, quotation, sales order; assert
finally:
    frappe.db.rollback()
```

Then confirm in a *separate* console session that nothing persisted.

## Related apps

- **crm** is vanilla upstream. Update it with `git pull --rebase upstream main`;
  never edit it in place to change behaviour. Everything TSI needs is added from
  here.
- **erpnext** is vanilla upstream and shared with tsiconnect. The only thing this
  app adds to it is the `Sales Order-crm_deal` custom field.
- **tsiconnect** owns Frappe/ERPNext/HRMS customization. **tsilearn** owns `lms`.
  Neither should gain a `crm` reference — put it here.

## Known upstream behaviour, not a bug

- **Probability does not update on status change if it is already set.** crm's
  `CRM Deal.update_default_probability` only fills the status default when
  probability is falsy, so a deal moved from Negotiation (80%) to Won keeps 80%.
  That is crm treating probability as user-owned once touched. Do not "fix" it
  here without a decision to diverge from upstream.
