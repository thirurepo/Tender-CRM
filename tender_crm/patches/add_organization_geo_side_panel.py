# Thin wrapper over tender_crm.setup.ensure_organization_geo_side_panel — see that function for the
# why. Also called from install.py, since a fresh install skips patches.

from tender_crm.setup import ensure_organization_geo_side_panel


def execute():
    ensure_organization_geo_side_panel()
