# The Deals tab on the Contact page, minus deactivated deals.
#
# crm.api.contact.get_linked_deals is what the Contact page called, and it
# cannot hide a deactivated deal (CRM Deal.tsi_disabled, see setup.py): it
# returns a fixed field list without the flag and has no filter hook. It stays
# vendor-owned and untouched; this endpoint returns the *same rows in the same
# shape* so the frontend swaps the URL and nothing else, and drops deactivated
# deals on the way. The Organization pages need no equivalent — they read
# CRM Deal through a list resource, so a plain `tsi_disabled: 0` filter there
# is enough.

import frappe
from frappe import _


@frappe.whitelist()
def get_linked_deals(contact: str):
    """Deals a contact is attached to, excluding deactivated ones.

    Mirrors crm.api.contact.get_linked_deals, including its permission rule
    (read on the Contact). Filtering happens in the query rather than in the
    frontend so the tab's count — taken from the length of this list — agrees
    with the rows it shows.
    """
    if not frappe.has_permission("Contact", "read", contact):
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    deal_names = frappe.get_all(
        "CRM Contacts",
        filters={"contact": contact, "parenttype": "CRM Deal"},
        fields=["parent"],
        distinct=True,
    )
    if not deal_names:
        return []

    active = set(
        frappe.get_all(
            "CRM Deal",
            filters={"name": ["in", [d.parent for d in deal_names]], "tsi_disabled": 0},
            pluck="name",
        )
    )

    deals = []
    for d in deal_names:
        if d.parent not in active:
            continue
        deal = frappe.get_cached_doc(
            "CRM Deal",
            d.parent,
            fields=[
                "name",
                "organization",
                "currency",
                "deal_value",
                "status",
                "email",
                "mobile_no",
                "deal_owner",
                "modified",
            ],
        )
        deals.append(deal.as_dict())

    return deals
