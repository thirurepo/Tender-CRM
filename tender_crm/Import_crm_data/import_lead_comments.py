# One-off import of the legacy TSI CRM's lead comments
# (CRM_Leads_Comments_Import.csv, 3,630 rows) into core `Comment`, against
# already-imported CRM Lead records. Sibling of import_leads.py /
# import_clients.py / import_client_contacts.py — same conventions
# throughout; read import_leads.py's header first if this is the first
# import script you're looking at.
#
# Deliberately NOT a patch — see import_leads.py's header for why. Run it by
# hand:
#
#   bench --site erp.tendersoftware.in execute \
#       tender_crm.Import_crm_data.import_lead_comments.run \
#       --kwargs "{'dry_run': True}"
#
# Must run BEFORE import_lead_comment_replies.py, which looks up each reply's
# parent comment by the tsi_legacy_comment_id this script stamps.
#
# Record Type: this CSV mixes three kinds of rows sharing one shape —
# `Comment` (the actual note, 2,860 rows), `Comment View` (756 rows, an audit
# row recording who viewed a comment and when) and `Comment Like` (14 rows,
# same idea for likes). Frappe's core Comment doctype has no view/like
# tracking to receive that into, and per explicit decision this data is
# skipped entirely — only `Record Type == "Comment"` rows are imported.
#
# Idempotency: `tsi_legacy_comment_id = "<lead id>:<comment id>"` (Comment ID
# resets per Lead in the source data — 2,865 unique of 3,630 rows — so it is
# only unique combined with Lead ID). See comment_import_schema.py.
#
# Lead resolution: CRM_Lead_Import.csv had no numeric ID of its own (see
# import_leads.py), so there is nothing to match "Lead ID" against directly —
# this script instead resolves via Lead Name, tie-broken by Organization Name
# when the name alone is ambiguous. Confirmed against the live site: of 2,860
# Comment rows, 2,832 resolve to exactly one CRM Lead by name, 26 are
# ambiguous by name alone but resolve uniquely once tie-broken by
# organization, and 2 have no match at all (reported as `unresolved_lead`,
# not guessed at).
#
# `Comment Date` is a date, not a full timestamp, and needs to land on the
# record's own timeline position for the CRM UI's chronological comment list
# to stay accurate — `doc.insert()` always stamps `creation` as now()
# regardless of any flag, so it is corrected with `frappe.db.set_value(...,
# "creation", ...)` immediately after insert, mirroring how tsi_added_date-
# style historical dates are handled for leads/clients (there, a plain field;
# here, a native Frappe column instead).
#
# `Is Permanent Note` is deliberately not carried anywhere — Comment does
# have a tsi_note_type Select (Private/Dev team/Permanent/Audio note, from
# setup.py's CLIENT_LEAD_FIELDS) built for the Tender CRM design's own
# Comments tab, but that is a different, forward-looking concept for new
# comments created through that UI, not a faithful home for this CSV's binary
# legacy flag; left unset rather than force a mapping onto it.

import csv
from pathlib import Path

import frappe

DATA_DIR = Path(__file__).resolve().parent / "14092026"
COMMENTS_CSV = DATA_DIR / "CRM_Leads_Comments_Import.csv"

BATCH_SIZE = 100

REPORT_KEYS = (
    "skipped_record_type",
    "blank_comment",
    "unresolved_lead",
    "unresolved_user",
    "failed_rows",
)


def run(dry_run=True):
    """Import CRM_Leads_Comments_Import.csv's Comment rows into core Comment.

    Prints a summary; returns it too.
    """
    rows = _read_rows()
    lead_map = _build_lead_map()
    user_map = _build_user_map()

    report = {
        "total": len(rows),
        "already_imported": 0,
        "would_create": 0,
        "created": 0,
        "skipped_record_type": 0,
        **{key: [] for key in REPORT_KEYS if key != "skipped_record_type"},
    }

    created = 0
    for line_no, row in enumerate(rows, start=2):  # header is line 1
        if (row.get("Record Type") or "").strip() != "Comment":
            report["skipped_record_type"] += 1
            continue

        content = (row.get("Comments") or "").strip()
        if not content:
            report["blank_comment"].append({"row": line_no, "value": "(blank)"})
            continue

        lead_id = (row.get("Lead ID") or "").strip()
        comment_id = (row.get("Comment ID") or "").strip()
        legacy_id = f"{lead_id}:{comment_id}"

        if frappe.db.exists("Comment", {"tsi_legacy_comment_id": legacy_id}):
            report["already_imported"] += 1
            continue

        lead_name, warning = _resolve_lead(row, lead_map)
        if warning:
            report["unresolved_lead"].append({"row": line_no, "value": warning})
            continue

        user_email = (row.get("Comment User Email") or "").strip()
        comment_by = user_map.get(user_email.lower())
        if user_email and not comment_by:
            report["unresolved_user"].append({"row": line_no, "value": user_email})

        report["would_create"] += 1
        if dry_run:
            continue

        savepoint_name = f"tsi_comment_import_row_{line_no}"
        frappe.db.savepoint(savepoint_name)
        try:
            doc = frappe.get_doc(
                {
                    "doctype": "Comment",
                    "comment_type": "Comment",
                    "reference_doctype": "CRM Lead",
                    "reference_name": lead_name,
                    "content": content,
                    "comment_email": user_email or None,
                    "comment_by": comment_by,
                    "tsi_legacy_comment_id": legacy_id,
                }
            )
            doc.insert(ignore_permissions=True)
            comment_date = (row.get("Comment Date") or "").strip()
            if comment_date:
                frappe.db.set_value(
                    "Comment", doc.name, "creation", comment_date, update_modified=False
                )
        except Exception as e:
            frappe.db.rollback(save_point=savepoint_name)
            frappe.log_error(frappe.get_traceback(), f"Tender CRM: comment import row {line_no}"[:140])
            report["failed_rows"].append({"row": line_no, "error": str(e)})
            continue
        else:
            frappe.db.release_savepoint(savepoint_name)

        report["created"] += 1
        created += 1
        if created % BATCH_SIZE == 0:
            frappe.db.commit()

    if not dry_run:
        frappe.db.commit()

    _print_report(report, dry_run)
    return report


# --------------------------------------------------------------------------- #
# Row mapping
# --------------------------------------------------------------------------- #


def _resolve_lead(row, lead_map):
    """(lead_name, warning) — warning is None on a clean single match."""
    name = (row.get("Lead Name") or "").strip().lower()
    org = (row.get("Organization Name") or "").strip().lower()

    matches = lead_map.get(name, [])
    if len(matches) == 1:
        return matches[0]["name"], None
    if not matches:
        return None, f"{row.get('Lead Name')!r}: no CRM Lead with that name"

    by_org = [m for m in matches if (m["organization"] or "").strip().lower() == org]
    if len(by_org) == 1:
        return by_org[0]["name"], None
    if not by_org:
        return None, (
            f"{row.get('Lead Name')!r} matched {len(matches)} leads by name, "
            f"none with organization {row.get('Organization Name')!r}"
        )
    return None, (
        f"{row.get('Lead Name')!r} + {row.get('Organization Name')!r} still "
        f"matched {len(by_org)} leads"
    )


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #


def _read_rows():
    if not COMMENTS_CSV.exists():
        frappe.throw(
            f"Tender CRM: {COMMENTS_CSV} not found. This CSV is not committed to "
            "git — copy it onto this bench before running the import."
        )
    with open(COMMENTS_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _build_lead_map():
    """{lead_name.lower(): [{"name":..., "organization":...}, ...]}, so an
    ambiguous match (more than one imported lead sharing a name) is
    detectable, and tie-breakable by organization, without a query per row.
    """
    leads = frappe.get_all("CRM Lead", fields=["name", "lead_name", "organization"])
    mapping = {}
    for lead in leads:
        if not lead.lead_name:
            continue
        mapping.setdefault(lead.lead_name.strip().lower(), []).append(
            {"name": lead.name, "organization": lead.organization}
        )
    return mapping


def _build_user_map():
    """{lowercased email: User name}, built once rather than re-queried per row."""
    users = frappe.get_all("User", fields=["name", "email"])
    return {u.email.lower(): u.name for u in users if u.email}


def _print_report(report, dry_run):
    mode = "DRY RUN — nothing written" if dry_run else "LIVE RUN"
    print(f"\n=== Legacy lead-comment import — {mode} ===")
    print(f"rows read:            {report['total']}")
    print(f"skipped (not Comment): {report['skipped_record_type']}")
    print(f"already imported:     {report['already_imported']}")
    if dry_run:
        print(f"would create:         {report['would_create']}")
    else:
        print(f"created:              {report['created']}")

    for key in REPORT_KEYS:
        if key == "skipped_record_type":
            continue
        items = report[key]
        if not items:
            continue
        print(f"{key}: {len(items)}")
        for item in items[:20]:
            print(f"    row {item['row']}: {item.get('value', item.get('error'))}")
        if len(items) > 20:
            print(f"    ... and {len(items) - 20} more")
    print()
