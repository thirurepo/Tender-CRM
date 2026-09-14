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
# Purely additive: crm's own /crm route (apps/crm/crm/hooks.py) is untouched
# and keeps working exactly as before.
website_route_rules = [
    {"from_route": "/tsi-crm/<path:app_path>", "to_route": "tsi_crm"},
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
# Edit fixtures/custom_field.json by hand. Do not run `bench export-fixtures` on
# this bench — it is known to wipe the sibling app's fixture JSON.
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["name", "in", [
            "CRM Deal-tsi_erpnext_company",
            "CRM Deal-tsi_erpnext_sales_order",
            "Sales Order-crm_deal",
            "CRM Lead-tsi_client_nature",
            "CRM Lead-tsi_notice_no",
            "CRM Lead-tsi_bid_due",
            "CRM Lead-tsi_sales_unit",
            "CRM Organization-tsi_client_nature",
            "CRM Organization-tsi_ranking",
            "CRM Organization-tsi_sales_unit",
            "CRM Organization-tsi_referred_by",
            "CRM Organization-tsi_client_since",
            "CRM Organization-tsi_developers",
            "Comment-tsi_note_type",
        ]]]
    },
]


# Document Events
# ---------------
# All three handlers no-op unless Tender CRM Settings is enabled and the relevant
# switch on it is on, so an administrator can turn the linkage off without an
# uninstall. Each one is individually guarded — the Sales Order handlers do not
# assume the Quotation one ran.
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
}


# Installation
# ------------
# Seeds the pipeline on a fresh install. The same work is done idempotently by
# the patches, which is what covers an existing site; this is only so that a
# newly installed site does not have to wait for the next migrate.
after_install = "tender_crm.install.after_install"
