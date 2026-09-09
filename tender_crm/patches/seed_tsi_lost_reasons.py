# Adds the ways a tendered deal is lost. Additive — crm's generic reasons stay.

from tender_crm.seed import seed_lost_reasons


def execute():
    seed_lost_reasons()
