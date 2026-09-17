# Gives crm.tendersoftware.in its own home page without touching the site's
# single global Website Settings.home_page, which erp.tendersoftware.in and
# lms.tendersoftware.in also rely on.
#
# Frappe resolves "/" per-user, not per-domain (frappe.website.utils.
# get_home_page_via_hooks calls this hook with frappe.session.user and takes
# whatever truthy path it returns; a falsy return falls through to the normal
# role_home_page / home_page-hook / Website Settings chain). Gating on the
# request Host header here is what makes it per-domain instead: every other
# domain alias on this site returns None and keeps its existing home page.

import frappe

CRM_DOMAIN = "crm.tendersoftware.in"


def get_home_page(user):
    request = frappe.local.request
    if request and request.host == CRM_DOMAIN:
        return "tsi-crm"
    return None
