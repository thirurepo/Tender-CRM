# Gives crm.tendersoftware.in its own home page without touching the site's
# single global Website Settings.home_page, which erp.tendersoftware.in and
# lms.tendersoftware.in also rely on.
#
# This can't be a get_website_user_home_page hook (the documented extension
# point for a dynamic home page). frappe.website.utils.get_home_page() caches
# its result in frappe.cache.hget("home_page", frappe.session.user, ...) keyed
# on user alone, with no domain in the key, and checks that cache *before*
# calling any hook. Every domain alias on this site shares one Redis cache for
# the same site, so whichever domain computed "Guest"'s home page first wins
# it for all of them until the key expires or is cleared - a
# get_website_user_home_page hook here would only take effect intermittently.
#
# frappe.local.flags.home_page is the one thing get_home_page() checks ahead
# of that cache lookup, and it is a per-request flag frappe resets on every
# request, so setting it from before_request - before path resolution reads
# it - is what actually makes this domain-specific and immune to another
# domain's cached value.

import frappe

CRM_DOMAIN = "crm.tendersoftware.in"


def set_home_page_for_domain():
    request = frappe.local.request
    if request and request.host == CRM_DOMAIN:
        frappe.local.flags.home_page = "tsi-crm"
