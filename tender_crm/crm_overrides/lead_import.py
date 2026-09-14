# Keeps CRM Lead's tsi_converted_date / tsi_last_status_change accurate for
# leads worked normally, after the legacy CRM import lands.
#
# The import script (tender_crm/Import_crm_data/import_leads.py)
# sets both fields directly from the legacy CSV's historical dates, on
# doc.flags.tsi_importing = True. These handlers must never overwrite that —
# a lead imported with a 2019 status change should not read as "changed
# today" the moment the import script inserts it — hence the flag check
# guarding both handlers below.
#
# Best-effort, same reasoning as erpnext_link.py: these run inside CRM Lead's
# own on_update, but a lead edit is a normal user action, not a system
# consequence of submitting a different document, so a raised exception here
# should not silently vanish either — it is logged and surfaced, never left to
# abort the save outright, since a broken date stamp is not worth losing an
# otherwise-valid edit over.

import frappe
from frappe import _


def stamp_status_change(doc, method=None):
    """Record today's date the moment Status actually changes."""
    if doc.flags.get("tsi_importing"):
        return
    if not doc.has_value_changed("status"):
        return

    _best_effort(
        lambda: doc.db_set(
            "tsi_last_status_change", frappe.utils.today(), update_modified=False
        ),
        f"Tender CRM: could not stamp tsi_last_status_change on CRM Lead {doc.name}",
    )


def stamp_converted_date(doc, method=None):
    """Record the date a lead is first marked Converted.

    `not doc.tsi_converted_date` makes this a one-time stamp — a lead cannot be
    un-converted and re-converted to pick up a later date, matching how the
    legacy CRM only ever recorded the original conversion.
    """
    if doc.flags.get("tsi_importing"):
        return
    if not (doc.has_value_changed("converted") and doc.converted and not doc.tsi_converted_date):
        return

    _best_effort(
        lambda: doc.db_set(
            "tsi_converted_date", frappe.utils.today(), update_modified=False
        ),
        f"Tender CRM: could not stamp tsi_converted_date on CRM Lead {doc.name}",
    )


def _best_effort(fn, error_title):
    """Run `fn`, converting any failure into a log entry and a non-blocking warning.

    Mirrors crm_overrides/erpnext_link.py's helper of the same name. Kept as a
    separate copy rather than a shared import: each override file documents
    its own failure-handling choice, and the two call sites have different
    reasons for it (there: must not abort someone else's submit; here: a
    broken date stamp should not cost a user their otherwise-valid lead edit).
    """
    try:
        fn()
    except Exception:
        frappe.log_error(frappe.get_traceback(), error_title[:140])
        frappe.msgprint(
            _("This lead's tracking dates could not be updated. See the Error Log."),
            title=_("Tender CRM"),
            indicator="orange",
            alert=True,
        )
