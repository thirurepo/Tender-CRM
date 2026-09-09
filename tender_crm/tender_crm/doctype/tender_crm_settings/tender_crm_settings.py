# Controller for the single that governs TSI's CRM ↔ ERPNext linkage.
#
# Everything in tender_crm/crm_overrides/erpnext_link.py reads its switches from
# here, so this is the one place an administrator has to look to answer "why did
# my deal move on its own?".

import frappe
from frappe import _
from frappe.model.document import Document


class TenderCRMSettings(Document):
    def validate(self):
        self.validate_status_directions()

    def validate_status_directions(self):
        """Refuse a configuration that would move deals the wrong way.

        The quotation step is meant to advance a deal into the middle of the
        pipeline and the sales order step to close it. Pointing them at statuses
        that invert that (a "won" status on quotation, an open one on the order)
        is almost always a mis-click, and it is much cheaper to catch here than
        to explain a fortnight of wrongly-closed deals later.
        """
        if self.advance_deal_on_quotation and self.quotation_deal_status:
            status_type = frappe.db.get_value(
                "CRM Deal Status", self.quotation_deal_status, "type"
            )
            if status_type in ("Won", "Lost"):
                frappe.throw(
                    _(
                        "{0} is a {1} status. Submitting a quotation should move a deal "
                        "along the pipeline, not close it — pick an Open or Ongoing status."
                    ).format(frappe.bold(self.quotation_deal_status), status_type)
                )

        if self.close_deal_on_sales_order and self.won_deal_status:
            status_type = frappe.db.get_value("CRM Deal Status", self.won_deal_status, "type")
            if status_type != "Won":
                frappe.throw(
                    _(
                        "{0} is a {1} status. Closing a deal against a submitted sales order "
                        "requires a status of type Won."
                    ).format(frappe.bold(self.won_deal_status), status_type or _("missing"))
                )


def get_settings():
    """Return the settings single, or None when the linkage is switched off.

    Every caller in crm_overrides/ starts here, so "disabled" is expressed once
    rather than repeated as a guard at each hook. Cached: these hooks fire inside
    submit, and re-reading a single per document event is wasted work.
    """
    settings = frappe.get_cached_doc("Tender CRM Settings")
    if not settings.enabled:
        return None
    return settings
