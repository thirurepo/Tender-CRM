# Per-domain landing page: signing in on the CRM domain lands in Tender CRM.
#
# One Frappe site answers to several hostnames (erp.tendersoftware.in for
# ERPNext/HRMS, crm.tendersoftware.in for CRM). Frappe's own "default app"
# setting is site-wide, so it cannot say "CRM domain -> CRM": setting it to
# tender_crm would send every HR/ERP user to /tsi-crm after login, and Frappe
# applies the System Settings default without checking the user may open that
# app, so most of them would land on Not Permitted. Doing it per user would
# not follow the domain either. The hostname is only knowable per request, so
# it is decided here, at login.
#
# How it works: LoginManager.post_login runs the `on_login` hooks first and then
# builds the login response, whose landing route comes from
# frappe.website.utils.get_home_page(). That function returns
# `frappe.local.flags.home_page` ahead of everything else (role home pages, the
# per-user cache, default app), and the flag lives only for this request — so
# setting it here changes this one login and nothing else, with no data written.
#
# Deliberately narrow:
#   * only the configured CRM hostnames; erp.* logins are untouched;
#   * only users who could open the app (same roles crm.api.check_app_permission
#     requires), so a desk-only user on the CRM domain is not sent to a page
#     that refuses them;
#   * it does not beat an explicit ?redirect-to= — login.js prefers that, which is
#     what lets a deep link survive sign-in (tsi-crm itself sends /tsi-crm).
# It does not cover reaching /login while already signed in: www/login.py sends
# that visitor to frappe.apps.get_default_path(), a plain function with no hook.
#
# Like every handler in this package it must never be able to break what it is
# attached to: a failure here must not stop anyone signing in.

import frappe

# Hostnames that mean "the CRM". Overridable per site with `tsi_crm_hosts` in
# site_config.json (a list) so a new domain needs no code change.
DEFAULT_CRM_HOSTS = ("crm.tendersoftware.in",)

# The roles crm.api.check_app_permission accepts for the CRM app.
CRM_ROLES = {"System Manager", "Sales User", "Sales Manager"}

TSI_CRM_ROUTE = "/tsi-crm"


def _crm_hosts():
    configured = frappe.conf.get("tsi_crm_hosts")
    return {host.lower() for host in (configured or DEFAULT_CRM_HOSTS)}


def _request_host():
    request = getattr(frappe.local, "request", None)
    host = getattr(request, "host", "") or ""
    # nginx forwards `Host $host` (no port), but a dev server or a direct hit
    # can carry one.
    return host.split(":")[0].lower()


def on_login(login_manager):
    """`on_login` hook: make Tender CRM the landing page on the CRM domain."""
    try:
        if _request_host() not in _crm_hosts():
            return
        if not CRM_ROLES & set(frappe.get_roles(login_manager.user)):
            return
        frappe.local.flags.home_page = TSI_CRM_ROUTE
    except Exception:
        frappe.log_error(title="tender_crm: could not set CRM-domain landing page")
