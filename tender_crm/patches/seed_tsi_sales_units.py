# Creates TSI's sales units (the team-territory axis the Tender CRM design's
# Leads/Clients screens filter and group by).

from tender_crm.seed import seed_sales_units


def execute():
    seed_sales_units()
