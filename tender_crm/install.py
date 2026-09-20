# Install-time setup.
#
# This must leave a freshly installed site in its *final* state, not a partial one.
# `bench install-app` marks every patch in patches.txt as already applied without
# running it — Frappe assumes a fresh install gets there directly and that patches
# exist for sites that already have data. So anything only a patch does is anything
# a new site never gets.
#
# Both paths therefore call the same functions: see tender_crm/setup.py.

import frappe

from tender_crm.seed import seed_all, seed_territory_countries
from tender_crm.setup import (
    configure_erpnext_integration,
    configure_ticket_email_intake,
    ensure_client_form_scripts,
    ensure_client_import_fields,
    ensure_client_lead_fields,
    ensure_comment_import_fields,
    ensure_contact_import_fields,
    ensure_disabled_flag_fields,
    ensure_form_scripts,
    ensure_lead_import_fields,
    ensure_link_fields,
    ensure_organization_geo_side_panel,
    ensure_side_panel_layouts,
    ensure_support_agent_role,
    ensure_territory_geo_fields,
    ensure_territory_geo_form_scripts,
    ensure_ticket_side_panel_layouts,
    seed_settings,
    seed_ticket_settings,
)


def after_install():
    """Bring a newly installed site to the same state a migrated one reaches.

    Ordered the same way patches.txt is, and for the same reasons: the pipeline has
    to exist before a setting can point at one of its statuses, and the link fields
    have to exist before the integration is switched on and starts writing to them.
    seed_all() creates TSI Sales Unit rows before ensure_client_lead_fields() adds
    the Link fields that point at them, though field creation does not actually
    depend on any row existing — it is just the more sensible read order.

    The ticketing steps run last, after seed_all() has created the ticket
    masters they configure defaults against.

    Deliberately does NOT seed the legacy CRM's master data (users, territories,
    lead/client sources/statuses, states) — that is one-time historical data, not
    application schema, and lives entirely in the one-off import processes. See
    tender_crm/Import_crm_data/import_leads.py and import_clients.py.
    """
    seed_all()
    ensure_link_fields()
    ensure_client_lead_fields()
    ensure_side_panel_layouts()
    configure_erpnext_integration()
    seed_settings()
    ensure_lead_import_fields()
    ensure_disabled_flag_fields()
    ensure_form_scripts()
    ensure_client_import_fields()
    ensure_client_form_scripts()
    ensure_contact_import_fields()
    ensure_comment_import_fields()
    ensure_territory_geo_fields()
    ensure_territory_geo_form_scripts()
    ensure_organization_geo_side_panel()
    seed_territory_countries()

    # Ticketing. seed_all() above has already created the ticket masters, so the
    # settings defaults below have something to point at, and the role has to
    # exist before anyone can be given it. Email intake goes last because it
    # reads the mailbox out of the settings the step before it writes.
    ensure_support_agent_role()
    ensure_ticket_side_panel_layouts()
    seed_ticket_settings()
    configure_ticket_email_intake()

    frappe.db.commit()
