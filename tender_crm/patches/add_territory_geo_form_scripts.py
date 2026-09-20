# Thin wrapper over tender_crm.setup.ensure_territory_geo_form_scripts — see that function for the
# why. Also called from install.py, since a fresh install skips patches.

from tender_crm.setup import ensure_territory_geo_form_scripts


def execute():
    ensure_territory_geo_form_scripts()
