# Records which lead a client (CRM Organization) was converted from, for leads
# converted in the UI with "Convert to client".
#
# That button calls crm's own convert_to_deal, which creates (or reuses) the
# organization and a CRM Deal pointing at both the lead and the organization —
# but never writes anything onto the organization itself. The legacy client
# import already fills CRM Organization.tsi_converted_from_lead for the clients
# it brought over; this fills it for every conversion from here on, so the
# Client page's timeline (api/client_activities.py) can pull in the lead's
# comments, emails, calls, notes, tasks and files no matter what later happens
# to the deal.
#
# First conversion wins: an organization that already names a source lead —
# an existing client picked in the convert dialog for a second lead — keeps it.
# Later leads still reach that client's timeline through their deals.

import frappe
from frappe import _


def stamp_source_lead(doc, method=None):
    """On a new CRM Deal made from a lead, stamp that lead onto its organization."""
    if not (doc.lead and doc.organization):
        return

    _best_effort(
        lambda: _stamp(doc.organization, doc.lead),
        f"Tender CRM: could not stamp tsi_converted_from_lead on CRM Organization {doc.organization}",
    )


def _stamp(organization, lead):
    if frappe.db.get_value("CRM Organization", organization, "tsi_converted_from_lead"):
        return
    # db.set_value, not save: the conversion is still mid-transaction inside
    # crm's convert_to_deal, and the organization has no validation that this
    # field takes part in.
    frappe.db.set_value(
        "CRM Organization", organization, "tsi_converted_from_lead", lead, update_modified=False
    )


def _best_effort(fn, error_title):
    """Run `fn`, converting any failure into a log entry and a non-blocking warning.

    Mirrors crm_overrides/erpnext_link.py's helper of the same name. A missing
    back-link is not worth aborting a lead conversion over.
    """
    try:
        fn()
    except Exception:
        frappe.log_error(frappe.get_traceback(), error_title[:140])
        frappe.msgprint(
            _("The client could not be linked back to its lead. See the Error Log."),
            title=_("Tender CRM"),
            indicator="orange",
            alert=True,
        )
