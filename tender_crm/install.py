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

from tender_crm.seed import seed_all
from tender_crm.setup import (
    configure_erpnext_integration,
    ensure_client_lead_fields,
    ensure_link_fields,
    ensure_side_panel_layouts,
    seed_settings,
)


def after_install():
    """Bring a newly installed site to the same state a migrated one reaches.

    Ordered the same way patches.txt is, and for the same reasons: the pipeline has
    to exist before a setting can point at one of its statuses, and the link fields
    have to exist before the integration is switched on and starts writing to them.
    seed_all() creates TSI Sales Unit rows before ensure_client_lead_fields() adds
    the Link fields that point at them, though field creation does not actually
    depend on any row existing — it is just the more sensible read order.
    """
    seed_all()
    ensure_link_fields()
    ensure_client_lead_fields()
    ensure_side_panel_layouts()
    configure_erpnext_integration()
    seed_settings()
    frappe.db.commit()
