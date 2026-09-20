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

from tender_crm.client_import_schema import CLIENT_FORM_SCRIPTS, CRM_ORGANIZATION_FIELDS
from tender_crm.comment_import_schema import COMMENT_IMPORT_FIELDS
from tender_crm.contact_import_schema import CRM_CONTACT_FIELDS
from tender_crm.lead_import_schema import (
    CRM_LEAD_FIELDS,
    DISABLED_FLAG_FIELDS,
    FORM_SCRIPTS as LEAD_FORM_SCRIPTS,
)
from tender_crm.territory_geo_schema import (
    ORGANIZATION_GEO_SIDE_PANEL_FIELDS,
    TERRITORY_GEO_FIELDS,
    TERRITORY_GEO_FORM_SCRIPTS,
)

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


# CRM Deal has no way to retire a deal upstream: the only exits are the terminal
# statuses (Won / Lost, which still count in the reports) or deletion, which
# takes the deal's whole history with it. This flag is the third option — take a
# deal out of the working pipeline without losing anything. The Deals list and
# kanban filter it out (frontend/src/pages/Deals.vue); the Deal page carries the
# Deactivate / Reactivate button.
DEAL_DEACTIVATION_FIELD = {
    "dt": "CRM Deal",
    "fieldname": "tsi_disabled",
    "label": "Deactivated",
    "fieldtype": "Check",
    "default": "0",
    "no_copy": 1,
    "insert_after": "status",
    "description": "Hides this deal from the Deals list and kanban without deleting it.",
}


def ensure_deal_deactivation_field():
    """Add the `tsi_disabled` flag to CRM Deal (see DEAL_DEACTIVATION_FIELD)."""
    spec = DEAL_DEACTIVATION_FIELD
    if not frappe.db.exists("DocType", spec["dt"]):
        return
    if frappe.db.exists("Custom Field", f"{spec['dt']}-{spec['fieldname']}"):
        return
    frappe.get_doc({"doctype": "Custom Field", "module": MODULE, **spec}).insert(
        ignore_permissions=True
    )


def ensure_lead_import_fields():
    """Create CRM Lead's legacy-import fields (see lead_import_schema.py).

    Guarded per field, matching ensure_link_fields — a run interrupted partway
    through, or a field an administrator already added by hand, must not stop
    the rest of the fields from being created.
    """
    if not frappe.db.exists("DocType", "CRM Lead"):
        return

    for spec in CRM_LEAD_FIELDS:
        if frappe.db.exists("Custom Field", f"CRM Lead-{spec['fieldname']}"):
            continue
        frappe.get_doc(
            {"doctype": "Custom Field", "dt": "CRM Lead", "module": MODULE, **spec}
        ).insert(ignore_permissions=True)


def ensure_disabled_flag_fields():
    """Add a `disabled` flag to CRM Lead Status and CRM Lead Source.

    Neither carries one upstream. It exists so the legacy CRM import can retire
    crm's stock statuses/sources — and TSI's own pipeline statuses, seeded by
    seed.py — in favour of the legacy set, without deleting a value any
    existing lead might still reference. The flag alone hides nothing in the
    CRM frontend: ensure_form_scripts() below is what makes it filter pickers.
    """
    for spec in DISABLED_FLAG_FIELDS:
        doctype = spec["dt"]
        if not frappe.db.exists("DocType", doctype):
            continue
        if frappe.db.exists("Custom Field", f"{doctype}-{spec['fieldname']}"):
            continue
        frappe.get_doc({"doctype": "Custom Field", "module": MODULE, **spec}).insert(
            ignore_permissions=True
        )


# CRM Organization's client-status field is *not* defined here. The Tender
# CRM design's own annotation describes it as "a legacy Client... carrying a
# tsi_client_status Select with the fourteen TSI values" — the same real
# concept the legacy-CRM import (client_import_schema.py) independently
# implements as tsi_client_status, a Link to Tender Client Status seeded from
# the actual historical data in CRM_Client_Import.csv. That is the
# authoritative source; a second, mockup-derived Select under the same
# fieldname would collide with it. See tender_crm.setup.ensure_client_import_fields.

# Shared between CRM Lead and CRM Organization's "Nature" fields. Only one
# sample value appears anywhere in the design ("Government" for a lead,
# "Retainer" for a client) — this list is a starting point, not a confirmed
# business list; adjust before relying on it.
CLIENT_NATURES = ["Retainer", "Project", "One-off", "Referral"]

NOTE_TYPES = ["Private note", "Dev team note", "Permanent note", "Audio note"]

# New Custom Fields the Tender CRM design's Leads/Clients screens need on top
# of crm's stock CRM Lead / CRM Organization fields. Mirrors LINK_FIELDS'
# shape and the same "created once, never dt-checked away" idempotency.
CLIENT_LEAD_FIELDS = [
    {
        "dt": "CRM Lead",
        "fieldname": "tsi_client_nature",
        "label": "Nature",
        "fieldtype": "Select",
        "options": "\n".join(CLIENT_NATURES),
        "insert_after": "territory",
    },
    {
        # Design sidebar label is literally "Notice no.", not "Tender notice
        # no." — kept verbatim so the UI can use the field's own label.
        "dt": "CRM Lead",
        "fieldname": "tsi_notice_no",
        "label": "Notice No.",
        "fieldtype": "Data",
        "insert_after": "tsi_client_nature",
        "description": "Tender notice this lead came from, where the source is a procurement portal.",
    },
    {
        "dt": "CRM Lead",
        "fieldname": "tsi_bid_due",
        "label": "Bid Due",
        "fieldtype": "Date",
        "insert_after": "tsi_notice_no",
    },
    {
        "dt": "CRM Lead",
        "fieldname": "tsi_sales_unit",
        "label": "Sales Unit",
        "fieldtype": "Link",
        "options": "TSI Sales Unit",
        "insert_after": "lead_owner",
    },
    {
        "dt": "CRM Organization",
        "fieldname": "tsi_client_nature",
        "label": "Nature",
        "fieldtype": "Select",
        "options": "\n".join(CLIENT_NATURES),
        "insert_after": "organization_name",
    },
    {
        "dt": "CRM Organization",
        "fieldname": "tsi_ranking",
        "label": "Ranking",
        "fieldtype": "Select",
        "options": "A\nB\nC\nD",
        "insert_after": "tsi_client_nature",
    },
    {
        "dt": "CRM Organization",
        "fieldname": "tsi_sales_unit",
        "label": "Sales Unit",
        "fieldtype": "Link",
        "options": "TSI Sales Unit",
        "insert_after": "territory",
    },
    {
        # tsi_cost_code is deliberately NOT declared here: the legacy-CRM
        # import (client_import_schema.py) already defines an identical
        # field under the same name (Data, "Cost Code") — declaring it twice
        # would just be a second, redundant Custom Field spec for the same
        # fieldname. See ensure_client_import_fields.
        "dt": "CRM Organization",
        "fieldname": "tsi_referred_by",
        "label": "Referred By",
        "fieldtype": "Data",
        "insert_after": "tsi_ranking",
    },
    {
        "dt": "CRM Organization",
        "fieldname": "tsi_client_since",
        "label": "Client Since",
        "fieldtype": "Date",
        "insert_after": "tsi_referred_by",
    },
    {
        "dt": "CRM Organization",
        "fieldname": "tsi_developers",
        "label": "Developers",
        "fieldtype": "Table",
        "options": "TSI Client Developer",
        "insert_after": "tsi_client_since",
    },
    {
        # Backs the Comments tab's note-type chips (Private/Dev team/Permanent/
        # Audio note) on both the Lead and Client detail screens. Deliberately a
        # field on core `Comment` rather than a new doctype: it keeps every
        # existing comment-timeline feature (edit, delete, reference lookup)
        # working unchanged, and a blank value reads as an ordinary comment
        # everywhere else in the desk/crm UI that Comment is used.
        "dt": "Comment",
        "fieldname": "tsi_note_type",
        "label": "Note Type",
        "fieldtype": "Select",
        "options": "\n" + "\n".join(NOTE_TYPES),
        "insert_after": "content",
    },
]


def ensure_client_lead_fields():
    """Create the Custom Fields the Leads/Clients screens read and write.

    Same per-field guard as ensure_link_fields(): a doctype missing (crm
    uninstalled, or — for Comment — a Frappe version without it, which does
    not happen in practice but costs nothing to check) skips just that field
    rather than the whole step.
    """
    for spec in CLIENT_LEAD_FIELDS:
        doctype = spec["dt"]

        if not frappe.db.exists("DocType", doctype):
            continue

        if frappe.db.exists("Custom Field", f"{doctype}-{spec['fieldname']}"):
            continue
        frappe.get_doc({"doctype": "Custom Field", "module": MODULE, **spec}).insert(
            ignore_permissions=True
        )


def ensure_client_import_fields():
    """Create CRM Organization's legacy-import fields (see client_import_schema.py).

    Guarded per field, matching ensure_lead_import_fields, for the same reason.
    """
    if not frappe.db.exists("DocType", "CRM Organization"):
        return

    for spec in CRM_ORGANIZATION_FIELDS:
        if frappe.db.exists("Custom Field", f"CRM Organization-{spec['fieldname']}"):
            continue
        frappe.get_doc(
            {"doctype": "Custom Field", "dt": "CRM Organization", "module": MODULE, **spec}
        ).insert(ignore_permissions=True)


def ensure_contact_import_fields():
    """Create Contact's legacy client-contact-import fields (see
    contact_import_schema.py).

    Guarded per field, matching ensure_lead_import_fields, for the same
    reason. Contact is a core Frappe doctype (not crm's), but it always
    exists on any bench this app runs on, so the DocType guard is really just
    consistency with the other ensure_*_import_fields functions.
    """
    if not frappe.db.exists("DocType", "Contact"):
        return

    for spec in CRM_CONTACT_FIELDS:
        if frappe.db.exists("Custom Field", f"Contact-{spec['fieldname']}"):
            continue
        frappe.get_doc(
            {"doctype": "Custom Field", "dt": "Contact", "module": MODULE, **spec}
        ).insert(ignore_permissions=True)


def ensure_comment_import_fields():
    """Create Comment's legacy comment/reply-import fields (see
    comment_import_schema.py).

    Guarded per field, matching ensure_lead_import_fields. Must run after
    ensure_client_lead_fields() (which creates Comment-tsi_note_type,
    tsi_legacy_comment_id's insert_after anchor) — both are called from
    install.py/patches.txt in that order.
    """
    if not frappe.db.exists("DocType", "Comment"):
        return

    for spec in COMMENT_IMPORT_FIELDS:
        if frappe.db.exists("Custom Field", f"Comment-{spec['fieldname']}"):
            continue
        frappe.get_doc(
            {"doctype": "Custom Field", "dt": "Comment", "module": MODULE, **spec}
        ).insert(ignore_permissions=True)


def ensure_form_scripts():
    """Install the CRM Lead form script that filters tsi_state / status / source."""
    _install_form_scripts(LEAD_FORM_SCRIPTS)


def ensure_client_form_scripts():
    """Install the CRM Organization form script that filters tsi_state by tsi_country."""
    _install_form_scripts(CLIENT_FORM_SCRIPTS)


def ensure_territory_geo_fields():
    """Create CRM Territory's Countries table and CRM Organization's Timezone.

    Guarded per field, matching ensure_client_import_fields. The child doctype
    (CRM Territory Country) ships with the app and is synced by migrate before
    patches run; on install it is synced before after_install, so the Table
    field always finds it.
    """
    for spec in TERRITORY_GEO_FIELDS:
        doctype = spec["dt"]

        if not frappe.db.exists("DocType", doctype):
            continue

        if frappe.db.exists("Custom Field", f"{doctype}-{spec['fieldname']}"):
            continue
        frappe.get_doc({"doctype": "Custom Field", "module": MODULE, **spec}).insert(
            ignore_permissions=True
        )


def ensure_territory_geo_form_scripts():
    """Install the CRM Organization form script that drives country/currency/timezone."""
    _install_form_scripts(TERRITORY_GEO_FORM_SCRIPTS)


ORG_GEO_SIDE_PANEL_APPLIED_FLAG = "tender_crm_org_geo_side_panel_applied"


def ensure_organization_geo_side_panel():
    """Add territory/country/currency/timezone to an existing Organization Side Panel.

    _install_side_panel_layouts is create-only, so a site whose layout already
    exists would never show the new fields. This appends only the ones missing
    from the layout — never reorders or removes anything — and runs once behind
    its own flag: an administrator who later removes a field from the layout on
    purpose must not have it put back on the next migrate.
    """
    import json

    if frappe.db.get_global(ORG_GEO_SIDE_PANEL_APPLIED_FLAG):
        return

    name = frappe.db.get_value(
        "CRM Fields Layout", {"dt": "CRM Organization", "type": "Side Panel"}
    )
    if not name:
        # No layout yet: ensure_side_panel_layouts() will create one that already
        # includes these fields, so there is nothing to amend.
        return

    layout = json.loads(frappe.db.get_value("CRM Fields Layout", name, "layout") or "[]")
    present = {
        field
        for section in layout
        for column in section.get("columns", [])
        for field in column.get("fields", [])
    }
    missing = [f for f in ORGANIZATION_GEO_SIDE_PANEL_FIELDS if f not in present]

    if missing and layout and layout[0].get("columns"):
        layout[0]["columns"][0].setdefault("fields", []).extend(missing)
        frappe.db.set_value("CRM Fields Layout", name, "layout", json.dumps(layout))

    frappe.db.set_global(ORG_GEO_SIDE_PANEL_APPLIED_FLAG, "1")


def _install_form_scripts(specs):
    """Shared installer behind ensure_form_scripts / ensure_client_form_scripts.

    Creates each script once and then leaves it alone, the same one-shot-then-
    hands-off stance seed_settings takes on user-editable configuration — a
    re-run must not silently overwrite a script an administrator has since
    tuned by hand in desk.
    """
    for spec in specs:
        if frappe.db.exists("CRM Form Script", spec["name"]):
            continue
        frappe.get_doc({"doctype": "CRM Form Script", **spec}).insert(
            ignore_permissions=True
        )



SIDE_PANEL_LAYOUTS = [
    {
        "dt": "CRM Lead",
        "type": "Side Panel",
        # Mirrors the Tender CRM design's Lead detail "Details" section, in the
        # exact field order the design specifies.
        "fields": [
            "source",
            "tsi_client_nature",
            "territory",
            "lead_owner",
            "tsi_notice_no",
            "tsi_bid_due",
        ],
    },
    {
        "dt": "CRM Organization",
        "type": "Side Panel",
        # Mirrors the design's Client detail "Client fields" section.
        "fields": [
            "tsi_client_nature",
            "tsi_sales_unit",
            "tsi_cost_code",
            "tsi_referred_by",
            "tsi_client_since",
            *ORGANIZATION_GEO_SIDE_PANEL_FIELDS,
        ],
    },
]


# Kept out of SIDE_PANEL_LAYOUTS so the ticket step can be its own patch, and
# so nothing here runs on a site that predates the ticketing doctypes.
TICKET_SIDE_PANEL_LAYOUTS = [
    {
        "dt": "Ticket",
        "type": "Side Panel",
        # What an agent needs while reading the conversation: who it is for,
        # how urgent, who owns it, and what it concerns.
        "fields": [
            "status",
            "priority",
            "ticket_type",
            "category",
            "team",
            "assigned_agent",
            "organization",
            "tsi_sales_unit",
            "raised_by",
            "opening_date",
        ],
    },
]


def ensure_side_panel_layouts():
    """Give CRM Lead / CRM Organization a default Side Panel layout."""
    _install_side_panel_layouts(SIDE_PANEL_LAYOUTS)


def ensure_ticket_side_panel_layouts():
    """Give Ticket a default Side Panel layout.

    Load-bearing, not cosmetic — see _install_side_panel_layouts. Its own
    entry point rather than another entry in SIDE_PANEL_LAYOUTS so that it can
    be registered as its own patch and so a site without the ticketing
    doctypes is not dragged through it.
    """
    _install_side_panel_layouts(TICKET_SIDE_PANEL_LAYOUTS)


def _install_side_panel_layouts(specs):
    """Shared installer behind the two ensure_*_side_panel_layouts functions.

    Unlike Quick Entry or Data Fields, crm's `get_sidepanel_sections` has no
    generated fallback — a doctype with no "Side Panel" CRM Fields Layout
    record shows an empty sidebar, full stop. crm ships no default for any of
    these doctypes, so without this the design's sidebar sections would simply
    never appear.

    Create-only, like the lost reasons and territory leaves: this is exactly
    the layout a Sales Manager can already hand-edit from Settings, so once a
    record exists here (whether seeded by this function or hand-built by a
    user) it is never touched again — no flag, just an existence check.
    """
    import json

    for spec in specs:
        doctype = spec["dt"]

        if not frappe.db.exists("DocType", doctype):
            continue

        if frappe.db.exists("CRM Fields Layout", {"dt": doctype, "type": "Side Panel"}):
            continue

        layout = [
            {
                "label": "Details",
                "name": "tsi_details_section",
                "opened": True,
                "columns": [{"name": "tsi_details_column", "fields": spec["fields"]}],
            }
        ]
        frappe.get_doc(
            {
                "doctype": "CRM Fields Layout",
                "dt": doctype,
                "type": "Side Panel",
                "layout": json.dumps(layout),
            }
        ).insert(ignore_permissions=True)


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


# The role the ticketing doctypes grant their permissions to. Frappe skips link
# validation when it imports a doctype JSON (modules/import_file.py sets
# ignore_links), so the doctypes sync happily against a role that does not exist
# yet — the permission rows simply apply to nobody until it does.
SUPPORT_AGENT_ROLE = "Support Agent"


def ensure_support_agent_role():
    """Create the Support Agent role the ticketing doctypes are permissioned to.

    Has to be its own step rather than a fixture: `bench migrate` syncs
    doctypes before it runs patches, and `bench install-app` never runs patches
    at all, so the only way both paths end up with the role is an idempotent
    function called from install.py and from a patch.

    `desk_access` is on because an agent works the queue in the Tender CRM SPA,
    which authenticates as a desk user.
    """
    if frappe.db.exists("Role", SUPPORT_AGENT_ROLE):
        return

    frappe.get_doc(
        {
            "doctype": "Role",
            "role_name": SUPPORT_AGENT_ROLE,
            "desk_access": 1,
        }
    ).insert(ignore_permissions=True)


def seed_ticket_settings():
    """Fill Tender CRM Settings' ticket defaults, once, without stamping on anyone.

    Cannot ride on seed_settings(): that one bails out entirely the moment the
    single has ever been saved, which on any site that already has this app
    installed is always. So this writes per field, and only into a field that is
    still empty — a re-run on a configured site changes nothing, and an
    administrator who cleared a field on purpose only gets it back if the seed
    would have chosen the same value anyway.

    `default_ticket_team` and `support_email_account` are deliberately left
    unset. TSI's support structure and its mailbox are site facts this app
    cannot guess, and a wrong guess at the mailbox would start threading real
    mail onto the wrong doctype.
    """
    settings = frappe.get_single(SETTINGS)
    changed = False

    if not settings.default_ticket_status:
        # The lowest-positioned Open status, rather than the literal "New":
        # seed.py owns the status names and this should follow it, not repeat it.
        new_status = frappe.get_all(
            "Ticket Status",
            filters={"category": "Open", "disabled": 0},
            order_by="position asc",
            pluck="name",
            limit=1,
        )
        if new_status:
            settings.default_ticket_status = new_status[0]
            changed = True

    if not settings.default_ticket_priority and frappe.db.exists(
        "Ticket Priority", "Medium"
    ):
        # Medium by name, because "the middle one" is not something position
        # can express — a site with two priorities has no middle.
        settings.default_ticket_priority = "Medium"
        changed = True

    if changed:
        settings.save(ignore_permissions=True)


def configure_ticket_email_intake():
    """Point the configured support mailbox at Ticket.

    Email intake is a DocType flag, not code: Ticket carries `email_append_to`,
    `subject_field` and `sender_field`, and frappe's IMAP receiver then creates
    a ticket for any mail arriving on an Email Account whose `append_to` names
    it (frappe/email/receive.py) and threads replies onto the existing ticket
    by subject and sender. All this function does is set `append_to` on the
    account an administrator has already nominated in Tender CRM Settings.

    It deliberately never creates the Email Account and never writes
    credentials — those are secrets, and per this app's rules they come from an
    administrator or site config, never from code. Creating the mailbox is a
    documented manual step.

    Re-runs are safe and non-destructive: an account already pointed somewhere
    else is left alone, because redirecting a live mailbox away from whatever
    it is currently filing into would silently strand incoming mail.
    """
    account = frappe.db.get_single_value(SETTINGS, "support_email_account")
    if not account or not frappe.db.exists("Email Account", account):
        return

    current = frappe.db.get_value("Email Account", account, "append_to")
    if current == "Ticket":
        return
    if current:
        frappe.log_error(
            title="Tender CRM: support mailbox already routed",
            message=(
                f"Email Account {account} is configured in {SETTINGS} as the support "
                f"mailbox, but its append_to is already {current!r}. Leaving it alone "
                "rather than redirecting a live mailbox; change it by hand if Ticket "
                "is what you want."
            ),
        )
        return

    frappe.db.set_value("Email Account", account, "append_to", "Ticket")
