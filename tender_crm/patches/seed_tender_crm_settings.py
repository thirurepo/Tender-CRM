# Writes Tender CRM Settings' defaults the first time the doctype exists, so the
# linkage is not installed-but-inert. See tender_crm/setup.py.

from tender_crm.setup import seed_settings


def execute():
    seed_settings()
