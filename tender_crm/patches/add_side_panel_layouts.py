# Gives CRM Lead / CRM Organization a default Side Panel layout, so the Tender
# CRM design's "Details"/"Client fields" sidebar sections have something to
# show. Must run after add_client_lead_fields, since both layouts reference
# tsi_* fields. See tender_crm/setup.py::ensure_side_panel_layouts.

from tender_crm.setup import ensure_side_panel_layouts


def execute():
    ensure_side_panel_layouts()
