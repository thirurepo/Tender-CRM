# One-off import of the legacy TSI CRM's client contacts
# (CRM_Client_Contacts_Import.csv, 961 rows) into the standard Frappe
# `Contact` doctype. Sibling of import_leads.py / import_clients.py — same
# conventions throughout; read import_leads.py's header first if this is the
# first import script you're looking at.
#
# Deliberately NOT a patch — see import_leads.py's header for why (one-time
# historical data, needs a human to read the dry-run report first). Run it by
# hand:
#
#   bench --site erp.tendersoftware.in execute \
#       tender_crm.Import_crm_data.import_client_contacts.run \
#       --kwargs "{'dry_run': True}"
#
# This CSV lives in a dated subfolder (14092026/), unlike CRM_Lead_Import.csv
# / CRM_Client_Import.csv, which sit directly in Import_crm_data/ — DATA_DIR
# below is adjusted accordingly. It is also utf-8-sig, not cp1252 like the
# first two legacy exports (confirmed: cp1252 decoding fails on this file;
# utf-8-sig round-trips cleanly and strips the BOM Excel adds).
#
# Idempotency: every row's Contact Email is distinct within this CSV (0
# duplicates), so `(email_id, tsi_organization)` is used as the natural key —
# email alone is not quite enough, since nothing rules out the same person's
# address appearing again for a different org in a future re-export. 12 rows
# have a blank Contact Email; those cannot be deduplicated this way and are
# reported as `unresolved_email`, not silently created (or silently skipped
# on a re-run).
#
# Prerequisite: Contact's legacy-import fields (tsi_organization and friends —
# see contact_import_schema.py) must already exist on this site — via
# `bench migrate` or a fresh install, see setup.py.ensure_contact_import_fields.
# Prerequisite data: CRM_Client_Import.csv must already be imported
# (import_clients.py) — every row's Company is expected to resolve to an
# existing CRM Organization (confirmed: 961/961 do, live).
#
# Field mapping notes:
#   - Position -> designation, Is Primary -> is_primary_contact: both native
#     Contact fields, used directly rather than re-derived as custom ones.
#   - Company -> company_name (native, plain text — matches Contact's own
#     field) AND tsi_organization (Link, resolved against CRM Organization).
#   - Primary Email is a *separate* legacy column from Contact Email — differs
#     on 281/961 rows. It looks like a legacy account/login grouping key
#     shared across a company's contacts, not this person's own address, so
#     it is kept as a raw reference (tsi_legacy_primary_email) rather than
#     used for this contact's actual email.
#   - Contact's real email/mobile/phone are set through its own child tables
#     (email_ids/phone_nos), not flat fields — Contact.validate() derives the
#     flat email_id/mobile_no/phone from whichever child row is marked
#     primary, so those are set there directly instead.
#   - mobile/phone reuse import_leads.py's phone-format handling: pre-checked
#     with Frappe's own validator, blanked + left as a comment on the record
#     rather than failing the whole row when the legacy value doesn't parse.

import csv
from datetime import datetime
from pathlib import Path

import frappe
from frappe.utils import validate_phone_number

DATA_DIR = Path(__file__).resolve().parent / "14092026"
CONTACT_CSV = DATA_DIR / "CRM_Client_Contacts_Import.csv"

BATCH_SIZE = 100

BOOLEAN_FIELDS = {
    "Reporting": "tsi_reporting_contact",
    "Billing": "tsi_billing_contact",
    "Holiday Email Only": "tsi_holiday_email_only",
    "Is RMR": "tsi_is_rmr",
    "LinkedIn Sent": "tsi_linkedin_sent",
    "Status": "tsi_status",
    "Approve Status": "tsi_approve_status",
}

REPORT_KEYS = (
    "unresolved_email",
    "unresolved_organization",
    "unresolved_owner",
    "unresolved_phone",
    "sanitized_name",
    "bad_dates",
    "failed_rows",
)


def run(dry_run=True):
    """Import CRM_Client_Contacts_Import.csv into Contact.

    Prints a summary; returns it too.
    """
    rows = _read_rows()
    owner_map = _build_owner_map()

    report = {
        "total": len(rows),
        "already_imported": 0,
        "would_create": 0,
        "created": 0,
        **{key: [] for key in REPORT_KEYS},
    }

    created = 0
    for line_no, row in enumerate(rows, start=2):  # header is line 1
        email = (row.get("Contact Email") or "").strip().lower()
        company = (row.get("Company") or "").strip()

        if not email:
            report["unresolved_email"].append({"row": line_no, "value": "(blank)"})
            continue

        if not frappe.db.exists("CRM Organization", company):
            report["unresolved_organization"].append({"row": line_no, "value": company})
            organization = None
        else:
            organization = company

        if organization and frappe.db.exists(
            "Contact", {"email_id": email, "tsi_organization": organization}
        ):
            report["already_imported"] += 1
            continue

        doc_fields, warnings = _map_row(row, company, organization, owner_map)
        for key, value in warnings:
            report[key].append({"row": line_no, "value": value})

        report["would_create"] += 1
        if dry_run:
            continue

        savepoint_name = f"tsi_contact_import_row_{line_no}"
        frappe.db.savepoint(savepoint_name)
        try:
            doc = frappe.get_doc({"doctype": "Contact", **doc_fields})
            doc.insert(ignore_permissions=True)
        except Exception as e:
            frappe.db.rollback(save_point=savepoint_name)
            frappe.log_error(frappe.get_traceback(), f"Tender CRM: contact import row {line_no}"[:140])
            report["failed_rows"].append({"row": line_no, "error": str(e)})
            continue
        else:
            frappe.db.release_savepoint(savepoint_name)

        phone_notes = [v for k, v in warnings if k == "unresolved_phone"]
        if phone_notes:
            _leave_comment(doc.name, "phone number", phone_notes)

        name_notes = [v for k, v in warnings if k == "sanitized_name"]
        if name_notes:
            _leave_comment(doc.name, "name (stripped a pasted email/header fragment)", name_notes)

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


def _map_row(row, company, organization, owner_map):
    """Return (doc_fields, warnings) for one CSV row.

    Nothing here can make the whole row unimportable — a blank/unresolved
    Company is reported and left blank, same stance as import_clients.py
    takes on its own ambiguities.
    """
    warnings = []

    raw_first_name = (row.get("First Name") or "").strip()
    raw_last_name = (row.get("Last Name") or "").strip()
    first_name, first_bad = _strip_angle_brackets(raw_first_name)
    last_name, last_bad = _strip_angle_brackets(raw_last_name)
    if first_bad:
        warnings.append(("sanitized_name", f"First Name={raw_first_name!r}"))
    if last_bad:
        warnings.append(("sanitized_name", f"Last Name={raw_last_name!r}"))

    first_name = first_name or last_name or "(unknown)"

    doc_fields = {
        "first_name": first_name,
        "last_name": last_name or None,
        "designation": (row.get("Position") or "").strip() or None,
        "is_primary_contact": 1 if (row.get("Is Primary") or "").strip() == "1" else 0,
        "company_name": company or None,
        "tsi_organization": organization,
        "tsi_legacy_primary_email": (row.get("Primary Email") or "").strip() or None,
        "email_ids": [],
        "phone_nos": [],
    }

    email = (row.get("Contact Email") or "").strip()
    if email:
        doc_fields["email_ids"].append({"email_id": email, "is_primary": 1})

    for csv_col, is_primary_key in (("Mobile No.", "is_primary_mobile_no"), ("Phone", "is_primary_phone")):
        value = (row.get(csv_col) or "").strip()
        if not value:
            continue
        if validate_phone_number(value):
            doc_fields["phone_nos"].append({"phone": value, is_primary_key: 1})
        else:
            warnings.append(("unresolved_phone", f"{csv_col}={value!r}"))

    for csv_col, fieldname in BOOLEAN_FIELDS.items():
        doc_fields[fieldname] = 1 if (row.get(csv_col) or "").strip() == "1" else 0

    rmr_added_by = (row.get("RMR Added By Email") or "").strip()
    if rmr_added_by:
        owner = owner_map.get(rmr_added_by.lower())
        if owner:
            doc_fields["tsi_rmr_added_by"] = owner
        else:
            warnings.append(("unresolved_owner", f"RMR Added By={rmr_added_by!r}"))

    created_by = (row.get("Created By Email") or "").strip()
    if created_by:
        owner = owner_map.get(created_by.lower())
        if owner:
            doc_fields["tsi_legacy_created_by"] = owner
        else:
            warnings.append(("unresolved_owner", f"Created By={created_by!r}"))

    added_date, bad = _parse_date(row.get("Created Date"))
    if bad:
        warnings.append(("bad_dates", f"Created Date={row.get('Created Date')!r}"))
    doc_fields["tsi_added_date"] = added_date

    return doc_fields, warnings


def _strip_angle_brackets(value):
    """(cleaned, was_bad) — drops a pasted "<email>" (or truncated "<...")
    fragment some rows have stuck onto First/Last Name (e.g. "Sharma
    <sanjeev@parrotanalytics.com>", "Rolfe <"). Contact's own autoname
    rejects '<'/'>' outright, which failed 2 of 961 rows on the first live
    run of this script; the '<'-onward text is never part of the actual
    name, so it is dropped rather than the whole row being lost.
    """
    if "<" not in value and ">" not in value:
        return value, False
    cleaned = value.split("<", 1)[0].replace(">", "").strip()
    return cleaned, True


def _parse_date(raw):
    """(date, is_bad) for a yyyy-mm-dd string. Blank is valid — not bad, just absent.

    Unlike CRM_Lead_Import.csv / CRM_Client_Import.csv's dd-mm-yyyy dates,
    this CSV's own Created Date / Modified Date columns are already
    yyyy-mm-dd (confirmed against the sample data).
    """
    raw = (raw or "").strip()
    if not raw:
        return None, False
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date(), False
    except ValueError:
        return None, True


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #


def _read_rows():
    if not CONTACT_CSV.exists():
        frappe.throw(
            f"Tender CRM: {CONTACT_CSV} not found. This CSV is not committed to "
            "git — copy it onto this bench before running the import."
        )
    with open(CONTACT_CSV, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _build_owner_map():
    """{lowercased email: User name}, built once rather than re-queried per row."""
    users = frappe.get_all("User", fields=["name", "email"])
    return {u.email.lower(): u.name for u in users if u.email}


def _leave_comment(reference_name, what, notes):
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Contact",
            "reference_name": reference_name,
            "content": f"Legacy CRM import: could not store as a valid {what}, left blank — "
            + "; ".join(notes),
        }
    ).insert(ignore_permissions=True)


def _print_report(report, dry_run):
    mode = "DRY RUN — nothing written" if dry_run else "LIVE RUN"
    print(f"\n=== Legacy client-contact import — {mode} ===")
    print(f"rows read:          {report['total']}")
    print(f"already imported:   {report['already_imported']}")
    if dry_run:
        print(f"would create:       {report['would_create']}")
    else:
        print(f"created:            {report['created']}")

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
