# Fills Tender CRM Settings' ticket defaults. Must run after
# seed_ticket_masters, which creates the statuses and priorities these defaults
# point at. See tender_crm/setup.py::seed_ticket_settings.

from tender_crm.setup import seed_ticket_settings


def execute():
    seed_ticket_settings()
