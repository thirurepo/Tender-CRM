# Every change Tender CRM makes to the Frappe CRM (`crm`) app is wired here.
#
# This file is the map of what this app does to the stack. The behaviour itself
# lives in tender_crm/crm_overrides/ — read that package's README.md before
# changing anything here, particularly the Quotation/Sales Order handlers, which
# deliberately do their work on submit rather than on save.
#
# The rule this app exists to enforce: `crm` and `erpnext` stay vanilla upstream
# and are updated with `git pull --rebase upstream <branch>`. Nothing TSI needs
# from either of them is edited in place; it is added from here.

app_name = "tender_crm"
app_title = "Tender CRM"
app_publisher = "Tender Software India"
app_description = "TSI's customization layer over the Frappe CRM (crm) app"
app_email = "thiru@tendersoftware.com"
app_license = "mit"

# `crm` is not optional: every hook below targets a crm doctype or extends the
# pipeline crm owns. Declaring it means bench refuses a nonsensical install
# rather than producing a site whose migrate fails on the first seed patch.
#
# `erpnext` is deliberately *not* declared. The linkage degrades to a no-op when
# it is absent (see crm_overrides/erpnext_link.py), so a CRM-only site can still
# run this app for the pipeline and territory customization alone.
required_apps = ["frappe/crm"]

# Serves the Tender CRM design's forked frontend (../frontend/) at /tsi-crm.
# crm's own /crm route (apps/crm/crm/hooks.py) is left untouched; it is retired
# by the website_redirects entry below rather than by editing crm.
website_route_rules = [
    # Frappe's default www-page resolution matches a bare path straight to a
    # same-named file (this is how crm's own bare /crm works, with no rule at
    # all — /crm literally matches crm/www/crm.py). That only works when the
    # URL and the file share a name; ours deliberately don't (tsi-crm vs
    # tsi_crm.py, for a nicer URL), so the bare path needs its own rule too,
    # not just the sub-path one below.
    {"from_route": "/tsi-crm", "to_route": "tsi_crm"},
    {"from_route": "/tsi-crm/<path:app_path>", "to_route": "tsi_crm"},
]

# Two CRM UIs at two URLs is confusing, so stock /crm hands everything to the
# TSI design: /crm/<anything> becomes /tsi-crm/<anything>. This is a pure prefix
# swap — the forked frontend keeps every stock route name and path (leads, deals,
# contacts, organizations, notes, tasks, call-logs, dashboard, data-import ...),
# so bookmarks, desk "Open in Portal" links and post-login redirects that crm
# itself emits all land on the equivalent page.
#
# website_redirects is consulted by frappe's path resolver before route rules and
# before same-named www files, so it wins over crm's own /crm/<path:app_path>
# rule and its bare www/crm.py match without touching apps/crm. The resolver
# hands the regex the path with no leading or trailing slash, and `crm(/.*)?`
# requires "/" or end-of-path right after "crm" — that is what keeps
# /crm-form/<route> (crm's public lead-capture embed, a different feature) out.
#
# 302, not 301: browsers cache a 301 indefinitely, which would make this
# awkward to back out. Results are cached in Redis, so `bench clear-cache`
# after changing this.
website_redirects = [
    {
        "source": r"/crm(/.*)?",
        "target": r"/tsi-crm\1",
        "redirect_http_status": 302,
        "forward_query_parameters": True,
    },
]

# Apps screen (/apps) entry for the TSI UI. Frappe resolves a user's landing
# route from the entry whose `name` equals their default_app, so registering it
# is what lets tender_crm be chosen as a default app at all. The stock `crm` tile
# cannot be removed from here (hooks are read per app); it now redirects to
# /tsi-crm anyway. Same permission gate as crm's own tile and www/tsi_crm.py.
add_to_apps_screen = [
    {
        "name": "tender_crm",
        "logo": "/assets/crm/images/logo.svg",
        "title": "Tender CRM",
        "route": "/tsi-crm",
        "has_permission": "crm.api.check_app_permission",
    },
]


# Fixtures
# --------
# The ERPNext-linkage fields, plus the fields the Tender CRM design's
# Leads/Clients screens (tender_crm/frontend/) read and write on CRM Lead,
# CRM Organization, and core Comment.
#
# `Sales Order-crm_deal` closes a real gap upstream: crm stamps `crm_deal` onto a
# Quotation but never onto the Sales Order made from it, so today the only way to
# get from an order back to the deal is to walk every item's `prevdoc_docname` to
# its quotation and read the field off that. See crm_overrides/erpnext_link.py.
#
# These fields are also created by tender_crm.patches.add_erpnext_link_fields /
# tender_crm.patches.add_client_lead_fields (see tender_crm/setup.py), which is
# what guarantees they exist on an already-migrated site; the fixtures are what
# carry them to a new one.
#
# The CRM Lead-tsi_* fields and the two "disabled" flags carry the legacy CRM
# lead import's schema (see lead_import_schema.py); the CRM Organization-tsi_*
# fields carry the legacy client import's (see client_import_schema.py). The
# two CRM Form Scripts carry the frontend filtering both imports need (state
# scoped to country; for leads, status/source scoped to not-disabled). Same
# two-path split as the ERPNext link fields: also created by
# tender_crm.setup.ensure_lead_import_fields / ensure_client_import_fields /
# ensure_disabled_flag_fields / ensure_form_scripts / ensure_client_form_scripts
# for an already-migrated site.
#
# CRM Territory-tsi_countries (the countries a territory covers), CRM
# Organization-tsi_timezone and the "TSI Client Territory Geo" form script carry
# the territory -> country -> currency/timezone rules (see territory_geo_schema.py);
# also created by tender_crm.setup.ensure_territory_geo_fields /
# ensure_territory_geo_form_scripts for an already-migrated site.
#
# The Contact-tsi_* fields carry the legacy client-contact import's schema
# (see contact_import_schema.py); the Comment-tsi_legacy_comment_id/
# tsi_reply_to_comment pair carries the legacy comment/reply import's (see
# comment_import_schema.py). Same two-path split again: also created by
# tender_crm.setup.ensure_contact_import_fields / ensure_comment_import_fields.
#
# Edit fixtures/custom_field.json by hand. Do not run `bench export-fixtures` on
# this bench — it is known to wipe the sibling app's fixture JSON.
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["name", "in", [
            "CRM Deal-tsi_erpnext_company",
            "CRM Deal-tsi_erpnext_sales_order",
            "CRM Deal-tsi_disabled",
            "Sales Order-crm_deal",
            "CRM Lead-tsi_skype",
            "CRM Lead-tsi_country",
            "CRM Lead-tsi_state",
            "CRM Lead-tsi_legacy_id",
            "CRM Lead-tsi_added_date",
            "CRM Lead-tsi_converted_date",
            "CRM Lead-tsi_last_status_change",
            "CRM Lead-tsi_contacted_today",
            "CRM Lead-tsi_linkedin_sent",
            "CRM Lead-tsi_chronic_nonresponder",
            "CRM Lead-tsi_weak_lead",
            "CRM Lead-tsi_difficult_personality",
            "CRM Lead-tsi_time_waster",
            "CRM Lead-tsi_client_nature",
            "CRM Lead-tsi_notice_no",
            "CRM Lead-tsi_bid_due",
            "CRM Lead-tsi_sales_unit",
            "CRM Lead Status-disabled",
            "CRM Lead Source-disabled",
            "CRM Organization-tsi_contact_first_name",
            "CRM Organization-tsi_contact_last_name",
            "CRM Organization-tsi_contact_email",
            "CRM Organization-tsi_contact_mobile",
            "CRM Organization-tsi_contact_phone",
            "CRM Organization-tsi_contact_skype",
            "CRM Organization-tsi_country",
            "CRM Organization-tsi_state",
            "CRM Organization-tsi_client_status",
            "CRM Organization-tsi_account_owner",
            "CRM Organization-tsi_added_date",
            "CRM Organization-tsi_converted_from_lead",
            "CRM Organization-tsi_legacy_lead_name",
            "CRM Organization-tsi_legacy_lead_company",
            "CRM Organization-tsi_linkedin_sent",
            "CRM Organization-tsi_30_day_report",
            "CRM Organization-tsi_60_day_report",
            "CRM Organization-tsi_90_day_report",
            "CRM Organization-tsi_chronic_nonresponder",
            "CRM Organization-tsi_weak_lead",
            "CRM Organization-tsi_difficult_personality",
            "CRM Organization-tsi_time_waster",
            "CRM Organization-tsi_low_value_client",
            "CRM Organization-tsi_cost_code",
            "CRM Organization-tsi_tax_code_name",
            "CRM Organization-tsi_sales_term_name",
            "CRM Organization-tsi_exact_accounting_name",
            "CRM Organization-tsi_invoice_projects_separately",
            "CRM Organization-tsi_accept_credit_card",
            "CRM Organization-tsi_client_nature",
            "CRM Organization-tsi_ranking",
            "CRM Organization-tsi_sales_unit",
            "CRM Organization-tsi_referred_by",
            "CRM Organization-tsi_client_since",
            "CRM Organization-tsi_developers",
            "CRM Organization-tsi_timezone",
            "CRM Territory-tsi_countries",
            "Comment-tsi_note_type",
            "Contact-tsi_organization",
            "Contact-tsi_legacy_primary_email",
            "Contact-tsi_reporting_contact",
            "Contact-tsi_billing_contact",
            "Contact-tsi_holiday_email_only",
            "Contact-tsi_is_rmr",
            "Contact-tsi_rmr_added_by",
            "Contact-tsi_linkedin_sent",
            "Contact-tsi_status",
            "Contact-tsi_approve_status",
            "Contact-tsi_legacy_created_by",
            "Contact-tsi_added_date",
            "Comment-tsi_legacy_comment_id",
            "Comment-tsi_reply_to_comment",
        ]]]
    },
    {
        "doctype": "CRM Form Script",
        "filters": [["name", "in", [
            "TSI Lead Country, State and Master Filters",
            "TSI Client Country/State Filter",
            "TSI Client Territory Geo",
        ]]]
    },
]


# Login
# -----
# Signing in on the CRM domain (crm.tendersoftware.in) lands in /tsi-crm, while
# the same site's ERP domain keeps its own default. Site-wide `default_app`
# cannot express that; see crm_overrides/default_app.py for why and how.
on_login = "tender_crm.crm_overrides.default_app.on_login"


# Document Events
# ---------------
# The Quotation/Sales Order handlers no-op unless Tender CRM Settings is enabled
# and the relevant switch on it is on, so an administrator can turn the ERPNext
# linkage off without an uninstall. Each one is individually guarded — the Sales
# Order handlers do not assume the Quotation one ran.
#
# The CRM Lead handlers are unconditional — they exist to keep two fields
# accurate, not to implement a switchable integration.
doc_events = {
    "Quotation": {
        # Submitting a quotation is the moment a deal is genuinely at proposal
        # stage. Moves the deal forward to that status — forward only, so a deal
        # already in Negotiation is not dragged backwards by a revised quote.
        "on_submit": "tender_crm.crm_overrides.erpnext_link.advance_deal_on_quotation_submit",
    },
    "Sales Order": {
        # Stamps the order onto the deal it came from, and optionally closes the
        # deal as Won. Both are on_submit: a draft order is not a sale.
        "on_submit": "tender_crm.crm_overrides.erpnext_link.link_deal_on_sales_order_submit",
        # A cancelled order is no longer evidence of a won deal. Clears the stamp
        # so the deal does not keep pointing at a cancelled document.
        "on_cancel": "tender_crm.crm_overrides.erpnext_link.unlink_deal_on_sales_order_cancel",
    },
    "CRM Lead": {
        # Historical leads from the legacy CRM import set these two fields
        # directly from the CSV (tsi_importing flag suppresses both handlers —
        # see crm_overrides/lead_import.py). This is what keeps them accurate
        # for every lead edited normally from here on.
        "on_update": [
            "tender_crm.crm_overrides.lead_import.stamp_status_change",
            "tender_crm.crm_overrides.lead_import.stamp_converted_date",
        ],
    },
    # Territory -> Country -> Currency / Timezone (crm_overrides/territory_geo.py).
    # Server-side backstop for what the SPA form script does interactively, so
    # imports and API writes get the same defaults. Only the duplicate-country and
    # wrong-timezone checks can raise, and both concern the document being saved.
    "CRM Territory": {
        "validate": "tender_crm.crm_overrides.territory_geo.validate_territory",
    },
    "CRM Organization": {
        "validate": "tender_crm.crm_overrides.territory_geo.apply_organization_defaults",
    },
    "CRM Deal": {
        # "Convert to client" goes through crm's convert_to_deal, which never
        # records the source lead on the organization. This does, so the Client
        # page's timeline keeps the lead's history. See crm_overrides/client_link.py.
        "after_insert": "tender_crm.crm_overrides.client_link.stamp_source_lead",
    },
}


# Ticketing
# ---------
# Deliberately absent from this file, and that absence is the point.
#
# The support queue is built out of doctypes this app owns (Ticket and its
# masters, in tender_crm/tender_crm/doctype/), not out of changes to somebody
# else's, so there is nothing to wire:
#
#   * No `website_route_rules` — the /tsi-crm/<path> rule above already carries
#     /tsi-crm/tickets and every ticket deep link.
#   * No `fixtures` — every ticket field lives on a doctype we own, so not one
#     of them is a Custom Field.
#   * No `doc_events` — Ticket's own behaviour belongs in its controller. A
#     cross-app event handler is what you reach for when the doctype is not
#     yours; here it is.
#   * No inbound email handler — intake is a DocType flag (`email_append_to`,
#     `subject_field`, `sender_field` on ticket.json) that frappe's own IMAP
#     receiver acts on. See setup.configure_ticket_email_intake.


# Project Accounts
# ----------------
# Absent from this file for the same reason as Ticketing: Project Account and its
# two masters are doctypes this app owns, so there is nothing to wire — no route
# rule, no fixture, no doc_event. Its timeline endpoint
# (api/project_account_activities.py) is registered by its decorator.


# Read APIs
# ---------
# Also deliberately absent. tender_crm/api/ holds the app's whitelisted read
# endpoints — quick jump (api/search.py), the activity feed (api/feed.py) and
# the Client page's timeline (api/client_activities.py).
# A whitelisted method is registered by its decorator at import time, not by a
# hook, and these change nothing about crm or erpnext: they only read.
#
# The feed's field-change source is off until a tabVersion index ships; that
# goes in setup.py and a patch, not here. See api/README.md.


# Installation
# ------------
# Seeds the pipeline on a fresh install. The same work is done idempotently by
# the patches, which is what covers an existing site; this is only so that a
# newly installed site does not have to wait for the next migrate.
after_install = "tender_crm.install.after_install"
