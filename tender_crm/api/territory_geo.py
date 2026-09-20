# Read endpoints behind the CRM Organization "TSI Client Territory Geo" form
# script (tender_crm/territory_geo_schema.py). Read-only: the rules that change
# data are in crm_overrides/territory_geo.py.

import frappe

from tender_crm.crm_overrides.territory_geo import country_geo, territory_countries


@frappe.whitelist()
def get_territory_geo(territory=None):
    """Countries a territory covers: [{country, currency, timezones}].

    An empty list means the territory has none configured and Country is left
    unrestricted.
    """
    frappe.has_permission("CRM Territory", "read", throw=True)
    return territory_countries(territory)


@frappe.whitelist()
def get_country_geo(country=None):
    """{"currency", "timezones"} for one Country."""
    frappe.has_permission("Country", "read", throw=True)
    return country_geo(country)
