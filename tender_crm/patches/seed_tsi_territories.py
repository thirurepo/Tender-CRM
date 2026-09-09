# Creates the CRM Territory tree. The site has none at all until something makes
# the root, and CRM Territory is a nested set that will not accept a child without
# one.

from tender_crm.seed import seed_territories


def execute():
    seed_territories()
