# One-off import of the legacy TSI CRM's lead-comment replies
# (CRM_Leads_Comments_Reply_Import.csv, 59 rows) into core `Comment`, as
# sibling Comment records to their parent (linked via tsi_reply_to_comment).
# Sibling of import_lead_comments.py — same conventions throughout; read
# import_leads.py's header first if this is the first import script you're
# looking at.
#
# Deliberately NOT a patch — see import_leads.py's header for why. Run it by
# hand, AFTER import_lead_comments.py has already run live (its
# tsi_legacy_comment_id stamps are what this script looks parents up by):
#
#   bench --site erp.tendersoftware.in execute \
#       tender_crm.Import_crm_data.import_lead_comment_replies.run \
#       --kwargs "{'dry_run': True}"
#
# Record Type: same three-way split as the comments CSV — `Reply` (26 rows,
# real content), `Reply View` (28 rows) and `Reply Like` (5 rows), the latter
# two skipped entirely per the same decision as import_lead_comments.py.
#
# A reply becomes its own Comment document (not appended text on the parent):
# same reference_doctype/reference_name as its parent (CRM Lead), so it shows
# in that lead's comment list, with tsi_reply_to_comment pointing at the
# parent Comment. The CRM UI does not render nested threads, so this does not
# produce visible nesting — it preserves the relationship as data, which was
# the explicit call over losing the reply's own author/date by folding it
# into the parent's content instead.
#
# Idempotency: own composite key,
# "<lead id>:<comment id>:reply:<reply id>", stored in the same
# tsi_legacy_comment_id field a plain comment uses (a reply is still a
# Comment row; the ":reply:<reply id>" suffix is what keeps it distinct from
# its parent's own key).
#
# `Reply Date` is corrected onto `creation` after insert, same reasoning and
# mechanism as import_lead_comments.py's `Comment Date` handling.

import csv
from pathlib import Path

import frappe

DATA_DIR = Path(__file__).resolve().parent / "14092026"
REPLIES_CSV = DATA_DIR / "CRM_Leads_Comments_Reply_Import.csv"

BATCH_SIZE = 100

REPORT_KEYS = (
    "blank_reply",
    "unresolved_parent_comment",
    "unresolved_user",
    "failed_rows",
)


def run(dry_run=True):
    """Import CRM_Leads_Comments_Reply_Import.csv's Reply rows into core Comment.

    Prints a summary; returns it too. Requires import_lead_comments.py to
    have already run live — every reply's parent is looked up by the
    tsi_legacy_comment_id that script stamps.
    """
    rows = _read_rows()
    user_map = _build_user_map()

    report = {
        "total": len(rows),
        "already_imported": 0,
        "would_create": 0,
        "created": 0,
        "skipped_record_type": 0,
        **{key: [] for key in REPORT_KEYS},
    }

    created = 0
    for line_no, row in enumerate(rows, start=2):  # header is line 1
        if (row.get("Record Type") or "").strip() != "Reply":
            report["skipped_record_type"] += 1
            continue

        content = (row.get("Reply") or "").strip()
        if not content:
            report["blank_reply"].append({"row": line_no, "value": "(blank)"})
            continue

        lead_id = (row.get("Lead ID") or "").strip()
        comment_id = (row.get("Comment ID") or "").strip()
        reply_id = (row.get("Reply ID") or "").strip()
        parent_legacy_id = f"{lead_id}:{comment_id}"
        reply_legacy_id = f"{lead_id}:{comment_id}:reply:{reply_id}"

        if frappe.db.exists("Comment", {"tsi_legacy_comment_id": reply_legacy_id}):
            report["already_imported"] += 1
            continue

        parent = frappe.db.get_value(
            "Comment", {"tsi_legacy_comment_id": parent_legacy_id}, ["name", "reference_name"], as_dict=True
        )
        if not parent:
            report["unresolved_parent_comment"].append(
                {"row": line_no, "value": f"comment {parent_legacy_id!r} not imported"}
            )
            continue

        user_email = (row.get("Reply User") or "").strip()
        comment_by = user_map.get(user_email.lower())
        if user_email and not comment_by:
            report["unresolved_user"].append({"row": line_no, "value": user_email})

        report["would_create"] += 1
        if dry_run:
            continue

        savepoint_name = f"tsi_reply_import_row_{line_no}"
        frappe.db.savepoint(savepoint_name)
        try:
            doc = frappe.get_doc(
                {
                    "doctype": "Comment",
                    "comment_type": "Comment",
                    "reference_doctype": "CRM Lead",
                    "reference_name": parent.reference_name,
                    "content": content,
                    "comment_email": user_email or None,
                    "comment_by": comment_by,
                    "tsi_legacy_comment_id": reply_legacy_id,
                    "tsi_reply_to_comment": parent.name,
                }
            )
            doc.insert(ignore_permissions=True)
            reply_date = (row.get("Reply Date") or "").strip()
            if reply_date:
                frappe.db.set_value(
                    "Comment", doc.name, "creation", reply_date, update_modified=False
                )
        except Exception as e:
            frappe.db.rollback(save_point=savepoint_name)
            frappe.log_error(frappe.get_traceback(), f"Tender CRM: reply import row {line_no}"[:140])
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
# IO
# --------------------------------------------------------------------------- #


def _read_rows():
    if not REPLIES_CSV.exists():
        frappe.throw(
            f"Tender CRM: {REPLIES_CSV} not found. This CSV is not committed to "
            "git — copy it onto this bench before running the import."
        )
    with open(REPLIES_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _build_user_map():
    """{lowercased email: User name}, built once rather than re-queried per row."""
    users = frappe.get_all("User", fields=["name", "email"])
    return {u.email.lower(): u.name for u in users if u.email}


def _print_report(report, dry_run):
    mode = "DRY RUN — nothing written" if dry_run else "LIVE RUN"
    print(f"\n=== Legacy lead-comment-reply import — {mode} ===")
    print(f"rows read:            {report['total']}")
    print(f"skipped (not Reply):  {report['skipped_record_type']}")
    print(f"already imported:     {report['already_imported']}")
    if dry_run:
        print(f"would create:         {report['would_create']}")
    else:
        print(f"created:              {report['created']}")

    for key in REPORT_KEYS:
        items = report[key]
        if not items:
            continue
        print(f"{key}: {len(items)}")
        for item in items[:20]:
            print(f"    row {item['row']}: {item.get('value', item.get('error'))}")
        if len(items) > 20:
            print(f"    ... and {len(items) - 20} more")
    print()
