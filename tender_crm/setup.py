# Everything that has to be true about a site for this app to work, expressed as
# idempotent steps.
#
# Read this before adding setup work anywhere else. There are two paths onto a
# site and they are not interchangeable:
#
#   * `bench install-app` runs `after_install` and syncs fixtures — and marks every
#     patch in patches.txt as already applied *without running it*. Frappe assumes
#     a fresh install reaches the final state directly, and that patches are
#     migrations that only existing sites need.
#
#   * `bench migrate` runs the patches, and never calls `after_install`.
#
# So setup work that lives only in a patch silently does not happen on a new site
# — which is exactly the bug this module was extracted to fix. Every step below is
# called from both `install.py` (for the first path) and a thin wrapper in
# `patches/` (for the second), and every step is safe to run any number of times.

import frappe

# `module` is set on every custom field on purpose. A Custom Field inserted without
# one is owned by no app, so it would never be picked up by a fixture export and
# would drift away from fixtures/custom_field.json over time.
MODULE = "Tender CRM"

SETTINGS = "Tender CRM Settings"
ERPNEXT_SETTINGS = "ERPNext CRM Settings"

LINK_FIELDS = [
    {
        "dt": "CRM Deal",
        "fieldname": "tsi_erpnext_sales_order",
        "label": "Sales Order in ERPNext",
        "fieldtype": "Data",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "closed_date",
        "description": "Set by Tender CRM when a sales order is submitted against this deal.",
    },
    {
        "dt": "CRM Deal",
        "fieldname": "tsi_erpnext_company",
        "label": "Company",
        "fieldtype": "Link",
        "options": "Company",
        "insert_after": "tsi_erpnext_sales_order",
        "description": "ERPNext company this deal is sold under.",
    },
    {
        # The gap this app exists to close on the ERPNext side. crm stamps
        # `crm_deal` onto a Quotation but not onto the Sales Order made from it,
        # so an order's only route back to the deal is to walk every item's
        # prevdoc_docname to its quotation and read the field off that.
        "dt": "Sales Order",
        "fieldname": "crm_deal",
        "label": "Frappe CRM Deal",
        "fieldtype": "Data",
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "customer_name",
        "description": "Set by Tender CRM when this order is submitted.",
    },
]


def ensure_link_fields():
    """Create the fields tying a CRM Deal to the ERPNext documents raised from it.

    Guarded per field rather than per run: the Sales Order field depends on erpnext
    being installed, and a CRM-only site must still get the two CRM Deal fields
    rather than having the whole step skip.
    """
    for spec in LINK_FIELDS:
        doctype = spec["dt"]

        if not frappe.db.exists("DocType", doctype):
            # erpnext is not on this bench, or crm was uninstalled. Nothing to
            # attach the field to — the linkage no-ops in that case anyway.
            continue

        if frappe.db.exists("Custom Field", f"{doctype}-{spec['fieldname']}"):
            continue

        frappe.get_doc({"doctype": "Custom Field", "module": MODULE, **spec}).insert(
            ignore_permissions=True
        )


def seed_settings():
    """Write Tender CRM Settings' defaults the first time it exists.

    Frappe does not materialise a Single's row until something saves it, so a
    freshly created settings doctype reads back as all-NULL. Here that would mean
    the `enabled` and `link_sales_order_to_deal` checkboxes reading as 0 despite
    being declared with `"default": "1"` — the linkage installed and inert, the
    most confusing of the possible starting states.

    Idempotent by construction: a Single with no `tabSingles` rows has never been
    saved, so a re-run on a configured site does nothing and cannot stamp over an
    administrator's changes.

    The obvious form of that test — `get_single_value(..., "enabled") is None` —
    does not work. It casts the missing value through the field's type on the way
    out, so an unsaved Check reads back as `0`, not `None`, and the guard would
    fire on the very first run and skip the seeding it exists to do.
    """
    already_saved = frappe.db.sql(
        "select 1 from tabSingles where doctype = %s limit 1", SETTINGS
    )
    if already_saved:
        return

    settings = frappe.get_single(SETTINGS)
    settings.enabled = 1
    settings.advance_deal_on_quotation = 1
    settings.link_sales_order_to_deal = 1

    # Off by default: most teams close the deal by hand once the advance is in, and
    # a deal that closes itself the moment an order is raised is a surprise.
    settings.close_deal_on_sales_order = 0

    if frappe.db.exists("CRM Deal Status", "Proposal/Quotation"):
        settings.quotation_deal_status = "Proposal/Quotation"
    if frappe.db.exists("CRM Deal Status", "Won"):
        settings.won_deal_status = "Won"

    settings.erpnext_company = _default_company()
    settings.save(ignore_permissions=True)


def configure_erpnext_integration():
    """Switch on crm's own ERPNext integration, once.

    The customer-creation half of CRM ↔ ERPNext already exists upstream, in
    `ERPNext CRM Settings`; it is just off by default and has to be filled in by
    hand. Turning it on is what makes crm create an ERPNext Customer when a deal is
    won, add the Create Quotation / View Customer buttons to the deal form, and
    allow `Quotation.quotation_to = CRM Deal`. Tender CRM's own handlers pick up
    from there, at the Sales Order.

    Deliberately one-shot and non-destructive. `enabled` being already set is taken
    as "an administrator has been here", and every value is then left alone. The one
    way this step could fight a human is by overwriting a company or trigger status
    they chose, so it does not.
    """
    if "erpnext" not in frappe.get_installed_apps():
        # CRM-only site. crm's integration would refuse to validate, and Tender
        # CRM's own linkage no-ops without erpnext.
        return

    settings = frappe.get_single(ERPNEXT_SETTINGS)
    if settings.enabled:
        return

    company = _default_company()
    if not company:
        # A site that has not finished ERPNext setup. Leave the integration off
        # rather than enabling it against nothing; this step re-runs on the next
        # migrate, by which time setup is usually done.
        return

    settings.enabled = 1
    settings.erpnext_company = company
    settings.is_erpnext_in_different_site = 0

    # Create the ERPNext Customer at the moment the deal is won. This is the status
    # crm's handler compares against, and it must be an exact match for a CRM Deal
    # Status name.
    if frappe.db.exists("CRM Deal Status", "Won"):
        settings.create_customer_on_status_change = 1
        settings.deal_status = "Won"

    # `validate` on this single is what actually does the work — it creates the
    # custom fields on both sides, adds the CRM Deal form script and grants Item
    # access to the sales roles. Saving is not incidental here.
    settings.save(ignore_permissions=True)


def _default_company():
    """The company to sell under.

    Global Defaults is where ERPNext records the company chosen during setup, so it
    is the right answer when there is one. Falling back to the only company on the
    site covers a bench where that default was never set; more than one company and
    no default is genuinely ambiguous, so it is left for a human.
    """
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if company:
        return company

    companies = frappe.get_all("Company", pluck="name", limit=2)
    return companies[0] if len(companies) == 1 else None
