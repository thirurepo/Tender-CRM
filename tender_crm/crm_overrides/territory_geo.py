# Territory -> Country -> Currency / Timezone rules for CRM Organization.
#
# A CRM Territory can cover several countries (child table
# CRM Territory-tsi_countries, rows of CRM Territory Country). An Organization
# in that territory picks one of them (tsi_country); its currency then follows
# the country and its timezone is one of the country's zones.
#
# The SPA does the interactive part (tender_crm/territory_geo_schema.py form
# script). Everything here is the server-side backstop, so imports, API writes
# and desk edits end up with the same defaults the form would have produced.
#
# Data source: Frappe's Country doctype has no currency, so currency comes from
# frappe/geo/country_info.json. Timezones prefer Country.time_zones (a site can
# edit it) and fall back to the same json.

import frappe
from frappe import _
from frappe.geo.country_info import get_country_info


def country_geo(country):
    """Return {"currency": str|None, "timezones": [str]} for a Country name.

    Timezones are de-duplicated in order — the json lists America/Denver twice
    for the US, which would show as a repeated dropdown entry. The first zone is
    what the default-timezone rule picks, so order is preserved deliberately.
    """
    if not country:
        return {"currency": None, "timezones": []}

    info = get_country_info(country)
    site_zones = frappe.db.get_value("Country", country, "time_zones") or ""
    zones = [z.strip() for z in site_zones.split("\n") if z.strip()] or list(
        info.get("timezones") or []
    )
    # Only a Currency that exists on this site can be linked; a country whose
    # currency is not enabled/created must not fail the Organization save.
    currency = info.get("currency")
    if currency and not frappe.db.exists("Currency", currency):
        currency = None

    return {"currency": currency, "timezones": list(dict.fromkeys(zones))}


def territory_countries(territory):
    """Countries a territory covers, as [{country, currency, timezones}].

    Empty list means the territory is unrestricted (no rows configured).
    """
    if not territory or not frappe.get_meta("CRM Territory").has_field("tsi_countries"):
        return []

    rows = frappe.get_all(
        "CRM Territory Country",
        filters={"parent": territory, "parenttype": "CRM Territory"},
        fields=["country", "currency"],
        order_by="idx",
    )
    result = []
    for row in rows:
        geo = country_geo(row.country)
        result.append(
            {
                "country": row.country,
                "currency": row.currency or geo["currency"],
                "timezones": geo["timezones"],
            }
        )
    return result


def validate_territory(doc, method=None):
    """Reject a country listed twice; fill blank row currencies from the country."""
    seen = set()
    for row in doc.get("tsi_countries") or []:
        if row.country in seen:
            frappe.throw(
                _("Row #{0}: {1} is already listed for this territory.").format(
                    row.idx, row.country
                )
            )
        seen.add(row.country)
        if not row.currency:
            row.currency = country_geo(row.country)["currency"]


def apply_organization_defaults(doc, method=None):
    """Default currency and timezone from the Organization's country.

    Fills blanks only — currency stays user-editable, and an explicit timezone is
    never overwritten. A timezone that is not one of the country's zones is a
    real data error, so that one is raised; the defaulting itself is best-effort
    and never blocks the save.
    """
    if not doc.get("tsi_country"):
        return

    geo = country_geo(doc.tsi_country)

    try:
        if not doc.get("currency"):
            doc.currency = _territory_currency(doc) or geo["currency"]
        if not doc.get("tsi_timezone") and geo["timezones"]:
            doc.tsi_timezone = geo["timezones"][0]
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Tender CRM: could not default geography on CRM Organization {doc.name}"[:140],
        )

    if doc.get("tsi_timezone") and geo["timezones"] and doc.tsi_timezone not in geo["timezones"]:
        frappe.throw(
            _("Timezone {0} is not a timezone of {1}.").format(doc.tsi_timezone, doc.tsi_country)
        )


def _territory_currency(doc):
    """Currency the Organization's territory assigns to its country, if any."""
    for row in territory_countries(doc.get("territory")):
        if row["country"] == doc.tsi_country:
            return row["currency"]
    return None
