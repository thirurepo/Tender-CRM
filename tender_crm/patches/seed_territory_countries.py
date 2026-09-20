# Thin wrapper over tender_crm.seed.seed_territory_countries (one-shot, own flag).
# Also called from install.py, since a fresh install skips patches.

from tender_crm.seed import seed_territory_countries


def execute():
    seed_territory_countries()
