# Creates the Custom Fields the Tender CRM design's Leads/Clients screens read
# and write (CRM Lead nature/notice/bid-due/sales-unit, CRM Organization
# client-status/nature/ranking/sales-unit/cost-code/referred-by/client-since/
# developers, and Comment's note-type).
#
# Also shipped as fixtures (tender_crm/fixtures/custom_field.json), which is what
# a fresh install uses; this is what puts them on an already-migrated site. Must
# run after TSI Sales Unit exists (seed_tsi_sales_units) since two of these
# fields link to it.

from tender_crm.setup import ensure_client_lead_fields


def execute():
    ensure_client_lead_fields()
