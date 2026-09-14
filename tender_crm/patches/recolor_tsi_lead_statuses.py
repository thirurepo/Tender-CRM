# Recolors the working lead statuses to the Tender CRM design's Kanban
# palette. One-shot and independent of seed_tsi_lead_statuses' own ordering
# flag — see seed.py's LEAD_RECOLOR_APPLIED_FLAG for why.

from tender_crm.seed import recolor_lead_statuses


def execute():
    recolor_lead_statuses()
