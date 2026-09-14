# Serves the Tender CRM design's frontend (../frontend/, a fork of crm's Vue
# app) at /tsi-crm — additive to, and independent of, crm's own /crm route.
# See tender_crm/hooks.py's website_route_rules.
#
# Deliberately thin: crm.www.crm.get_boot() already builds every boot global
# the forked frontend's JS expects (csrf_token, sysdefaults, translated
# messages, ...), and crm is a required_app here, so importing it is a
# legitimate cross-app call, not an edit to apps/crm. Only default_route
# differs, so this page is not just an alias for /crm.

import frappe
from frappe import _

no_cache = 1


def get_context():
    from crm.api import check_app_permission

    if not check_app_permission():
        frappe.throw(_("You do not have permission to access Tender CRM"), frappe.PermissionError)

    frappe.db.commit()
    context = frappe._dict()
    context.boot = get_boot()
    return context


def get_boot():
    from crm.www.crm import get_boot as get_crm_boot

    boot = get_crm_boot()
    boot["default_route"] = "/tsi-crm"
    return boot
