# Keeps a CRM Deal and the ERPNext documents raised from it pointing at each other.
#
# Upstream `crm` already handles one direction of this: it can create a Customer
# when a deal reaches a chosen status, and it stamps `crm_deal` onto a Quotation
# so the quote knows which deal it came from. What it does not do is carry that
# link one step further, to the Sales Order, or move the deal along the pipeline
# as those documents are raised. Both are what this module adds.
#
# Read this before changing anything here:
#
#   * Every handler runs on **submit**, not save. A draft quotation is a working
#     document that gets revised, deleted and re-made; treating one as evidence
#     that a deal reached proposal stage produced deals that jumped forward and
#     then sat there after the draft was thrown away.
#
#   * Every handler is **best-effort**. It is writing a convenience link onto a
#     second document, and a failure there must not roll back the sales order the
#     user was actually submitting. Failures are logged and surfaced as a warning,
#     never raised. `_best_effort` is what enforces that.
#
#   * Deal status only ever moves **forward**, compared by the `position` field on
#     CRM Deal Status. A revised quotation on a deal already in Negotiation must
#     not drag it back to Proposal.

import frappe
from frappe import _

from tender_crm.tender_crm.doctype.tender_crm_settings.tender_crm_settings import get_settings


# --------------------------------------------------------------------------- #
# Hook entry points
# --------------------------------------------------------------------------- #


def advance_deal_on_quotation_submit(doc, method=None):
    """Move the deal behind a submitted quotation to the configured status."""
    settings = get_settings()
    if not settings or not settings.advance_deal_on_quotation or not settings.quotation_deal_status:
        return

    deal = doc.get("crm_deal")
    if not deal:
        return

    _best_effort(
        lambda: _move_deal_forward(
            deal,
            settings.quotation_deal_status,
            _("Quotation {0} was submitted.").format(doc.name),
        ),
        f"Tender CRM: could not advance CRM Deal {deal} for Quotation {doc.name}",
    )


def link_deal_on_sales_order_submit(doc, method=None):
    """Stamp a submitted sales order onto its deal, and optionally close the deal.

    The two switches are independent: a team can want the order traceable from the
    deal without wanting the deal auto-closed, which is the common case and the
    reason `close_deal_on_sales_order` defaults off.
    """
    settings = get_settings()
    if not settings:
        return

    deal = _get_deal_for_sales_order(doc)
    if not deal:
        return

    if settings.link_sales_order_to_deal:
        _best_effort(
            lambda: _stamp_sales_order(doc, deal),
            f"Tender CRM: could not link CRM Deal {deal} to Sales Order {doc.name}",
        )

    if settings.close_deal_on_sales_order and settings.won_deal_status:
        _best_effort(
            lambda: _move_deal_forward(
                deal,
                settings.won_deal_status,
                _("Sales Order {0} was submitted.").format(doc.name),
            ),
            f"Tender CRM: could not close CRM Deal {deal} for Sales Order {doc.name}",
        )


def unlink_deal_on_sales_order_cancel(doc, method=None):
    """Clear the deal's pointer to a sales order that has just been cancelled.

    The deal's *status* is deliberately left alone. Cancelling an order is not the
    same as losing the deal — it is usually re-raised the same week — and quietly
    reopening a closed deal would be a bigger surprise than a stale status. The
    comment left on the deal is what tells a human to make that call.
    """
    settings = get_settings()
    if not settings or not settings.link_sales_order_to_deal:
        return

    deal = doc.get("crm_deal") or _get_deal_for_sales_order(doc)
    if not deal:
        return

    _best_effort(
        lambda: _clear_sales_order_stamp(doc, deal),
        f"Tender CRM: could not unlink CRM Deal {deal} from cancelled Sales Order {doc.name}",
    )


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _get_deal_for_sales_order(doc):
    """Find the CRM Deal behind a sales order.

    Prefers our own `crm_deal` field, which a previously-submitted order will
    already carry. Falls back to walking each item's `prevdoc_docname` back to its
    quotation and reading crm's field off that — the only route available on an
    order being submitted for the first time, and the reason the stamp is worth
    having at all.
    """
    if doc.get("crm_deal"):
        return doc.get("crm_deal")

    for item in doc.get("items") or []:
        quotation = item.get("prevdoc_docname")
        if not quotation:
            continue
        deal = frappe.db.get_value("Quotation", quotation, "crm_deal")
        if deal:
            return deal

    return None


def _stamp_sales_order(doc, deal):
    """Write the link onto both documents.

    Direct column writes rather than a save on either side: neither field
    participates in validation, the sales order is mid-submit and must not be
    re-saved from inside its own hook, and the deal has no business firing its full
    on_update chain — including crm's create-customer-in-ERPNext handler — because
    an order was submitted.
    """
    if not frappe.db.exists("CRM Deal", deal):
        return

    if doc.get("crm_deal") != deal:
        # db_set rather than db.set_value: it writes the column *and* updates the
        # in-memory document, so the order the user is looking at reflects the link
        # without a reload. `update_modified=False` keeps this off the audit trail —
        # nobody edited the order, we annotated it.
        doc.db_set("crm_deal", deal, update_modified=False)

    if frappe.db.get_value("CRM Deal", deal, "tsi_erpnext_sales_order") != doc.name:
        frappe.db.set_value("CRM Deal", deal, "tsi_erpnext_sales_order", doc.name)

    if doc.get("company") and not frappe.db.get_value("CRM Deal", deal, "tsi_erpnext_company"):
        frappe.db.set_value("CRM Deal", deal, "tsi_erpnext_company", doc.company)

    _comment(deal, _("Sales Order {0} was submitted against this deal.").format(doc.name))


def _clear_sales_order_stamp(doc, deal):
    """Drop the deal's pointer, but only if it still points at this order."""
    if frappe.db.get_value("CRM Deal", deal, "tsi_erpnext_sales_order") == doc.name:
        frappe.db.set_value("CRM Deal", deal, "tsi_erpnext_sales_order", None)

    _comment(
        deal,
        _(
            "Sales Order {0} was cancelled. The deal status has been left unchanged — "
            "close or reopen it by hand if that is no longer right."
        ).format(doc.name),
    )


def _move_deal_forward(deal, target_status, reason):
    """Set the deal's status to `target_status`, unless it is already past it.

    Goes through `doc.save()` rather than `db.set_value` on purpose: CRM Deal's own
    `validate` is what appends to the status change log, stamps `closed_date` and
    fills the default probability for the new status. Writing the column directly
    would leave a deal that claims to be Won with a 10% probability and no closing
    date, and no record of when it got there.

    `ignore_permissions` is set because this is a system consequence of submitting
    a document, not an edit by the person who clicked submit — a Sales User with no
    write access to CRM Deal must still be able to submit an order.
    """
    if not frappe.db.exists("CRM Deal", deal):
        return

    current_status = frappe.db.get_value("CRM Deal", deal, "status")
    if current_status == target_status:
        return

    if not _is_forward(current_status, target_status):
        return

    doc = frappe.get_doc("CRM Deal", deal)
    doc.status = target_status
    doc.flags.ignore_permissions = True
    doc.save()

    _comment(
        deal,
        _("Status moved from {0} to {1} by Tender CRM. {2}").format(
            current_status or _("(none)"), target_status, reason
        ),
    )


def _is_forward(current_status, target_status):
    """True when `target_status` sits later in the pipeline than `current_status`.

    Ordering is the `position` field on CRM Deal Status, which is the same number
    the CRM kanban board orders its columns by — so "forward" here means exactly
    what it looks like on screen. A status with no position sorts as 0, which makes
    an unpositioned status something we will move *out of* but never *into*, the
    safer of the two failure modes.
    """
    positions = dict(
        frappe.get_all("CRM Deal Status", fields=["name", "position"], as_list=True)
    )
    return (positions.get(target_status) or 0) > (positions.get(current_status) or 0)


def _comment(deal, text):
    """Leave an audit trail on the deal.

    Deals move on their own under this app; a comment is what stops that reading
    as the record changing for no reason.
    """
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "CRM Deal",
            "reference_name": deal,
            "content": text,
        }
    ).insert(ignore_permissions=True)


def _best_effort(fn, error_title):
    """Run `fn`, converting any failure into a log entry and a non-blocking warning.

    These handlers hang off another document's submit. Letting one raise would
    abort that submit and roll back the transaction, which means a broken link
    field would stop the business from taking orders. Logging is the right trade;
    the msgprint is so the failure is not silent to the person standing there.
    """
    try:
        fn()
    except Exception:
        frappe.log_error(frappe.get_traceback(), error_title[:140])
        frappe.msgprint(
            _("The CRM deal linked to this document could not be updated. See the Error Log."),
            title=_("Tender CRM"),
            indicator="orange",
            alert=True,
        )
