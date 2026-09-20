# Adds the `tsi_disabled` (Deactivated) flag to CRM Deal, so a deal can be taken
# out of the Deals list without being deleted.
#
# Also shipped as a fixture (tender_crm/fixtures/custom_field.json), which is what a
# fresh install uses; this is what puts it on an already-migrated site.

from tender_crm.setup import ensure_deal_deactivation_field


def execute():
    ensure_deal_deactivation_field()
