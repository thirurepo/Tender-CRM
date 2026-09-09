# Tender CRM

Tender Software India's customization layer over the [Frappe CRM](https://github.com/frappe/crm)
(`crm`) app.

`crm` and `erpnext` stay vanilla upstream on this bench and are updated with
`git pull --rebase upstream <branch>`. Nothing TSI needs from either is edited in
place — it is added from here. This is the same split `tsilearn` has with `lms`,
and for the same reason: the customization ships on its own cadence and an
upstream upgrade never has to be reconciled with local edits.

## What it does

**A pipeline that matches how TSI actually sells.** Vanilla Frappe CRM goes
demo → quote → negotiate, which is not the shape of a tendered sale. A bid is
submitted against a published notice long before anyone negotiates, and then sits
in a technical evaluation the seller cannot influence. Neither state had a stage,
so those deals piled up in *Demo/Making* and every forecast counted bids that were
already out of the seller's hands as though they were still being worked.

Tender CRM adds **Requirement Study**, **Bid/Tender Submitted**, **Technical
Evaluation** and **On Hold** and orders the pipeline around them. It also adds the
lead stages *Tender Notice* and *Demo Scheduled*, six tender-specific lost reasons
(L1 price loss, technical disqualification, retendered, EMD not furnished, …) and
the CRM Territory tree, which the site had no root for at all.

**A CRM Deal that stays connected to ERPNext.** Upstream `crm` creates an ERPNext
Customer when a deal is won and stamps `crm_deal` onto a Quotation. It stops
there: the Sales Order has no link back to the deal, and nothing moves the deal as
those documents are raised. Tender CRM adds both — see
[`tender_crm/crm_overrides/README.md`](tender_crm/crm_overrides/README.md).

## Layout

Note the doubled path — the app package is `tender_crm/`, the Frappe module inside
it is also `tender_crm/` (module name `Tender CRM`).

```
tender_crm/hooks.py                     # single source of truth for all wiring
tender_crm/pipeline.py                  # the TSI pipeline, as data
tender_crm/seed.py                      # idempotent seeding, shared by patches + install
tender_crm/install.py                   # after_install
tender_crm/patches.txt                  # migration patch registry
tender_crm/fixtures/                    # Custom Field JSON
tender_crm/crm_overrides/               # behaviour: CRM <-> ERPNext linkage
tender_crm/patches/                     # patch implementations listed in patches.txt
tender_crm/tender_crm/doctype/          # Tender CRM Settings
```

## Configuration

Everything is driven by the **Tender CRM Settings** single (`/app/tender-crm-settings`):

| Setting | Default | Effect |
| --- | --- | --- |
| Enable CRM ↔ ERPNext Linkage | on | Master switch. Off disables every handler without an uninstall. |
| Advance Deal Status | on | Submitting a quotation moves its deal to *Proposal/Quotation* (forward only). |
| Link Sales Order to Deal | on | Submitting an order stamps it onto the deal, and the deal onto the order. |
| Close Deal as Won | **off** | Submitting an order also closes the deal. Off because most teams close by hand once the advance is in. |

The upstream half of the integration lives in **ERPNext CRM Settings** and is
switched on once by `tender_crm.patches.configure_erpnext_crm_settings`. That patch
never overwrites values an administrator has already set.

## Install

```bash
cd /home/thiru/frappe-bench2 && bench --site erp.tendersoftware.in install-app tender_crm
```

## Development

```bash
cd /home/thiru/frappe-bench2 && bench --site erp.tendersoftware.in migrate
```

Do **not** run `bench export-fixtures` on this bench — it is known to wipe the
sibling app's fixture JSON. Edit `tender_crm/fixtures/custom_field.json` by hand,
and mirror the change in `tender_crm/patches/add_erpnext_link_fields.py` so
already-migrated sites get it too.

After changing Python source, restarting the gunicorn master is not optional —
it runs with `--preload`, so a HUP re-forks the *old* modules. See `CLAUDE.md`.

## License

MIT
