# Adds the two lead stages TSI's tender-sourced pipeline needs: a lead that came
# off a procurement portal and has not been contacted, and one with a demo booked.

from tender_crm.seed import seed_lead_statuses


def execute():
    seed_lead_statuses()
