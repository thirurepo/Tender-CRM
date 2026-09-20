# Tests for crm_overrides/territory_geo.py. Every case rolls back: this bench's
# site is production, so nothing here may persist (see CLAUDE.md, "Testing
# changes safely").

import frappe
from frappe.tests import IntegrationTestCase

from tender_crm.crm_overrides.territory_geo import (
    apply_organization_defaults,
    country_geo,
    territory_countries,
    validate_territory,
)


class TestTerritoryGeo(IntegrationTestCase):
    def tearDown(self):
        frappe.db.rollback()

    def test_country_geo_dedupes_and_keeps_order(self):
        zones = country_geo("United States")["timezones"]
        self.assertEqual(len(zones), len(set(zones)))
        self.assertEqual(zones[0], "America/Adak")

    def test_single_timezone_country(self):
        self.assertEqual(country_geo("India")["timezones"], ["Asia/Kolkata"])
        self.assertEqual(country_geo("India")["currency"], "INR")

    def test_unknown_country_is_empty(self):
        self.assertEqual(country_geo(None), {"currency": None, "timezones": []})

    @staticmethod
    def _territory(*countries):
        # Stub doc: independent of whether the tsi_countries Custom Field has been
        # migrated onto the site the test happens to run on.
        return frappe._dict(
            tsi_countries=[
                frappe._dict(idx=i + 1, country=c, currency=None) for i, c in enumerate(countries)
            ]
        )

    def test_territory_rejects_duplicate_country(self):
        with self.assertRaises(frappe.ValidationError):
            validate_territory(self._territory("India", "India"))

    def test_territory_fills_row_currency(self):
        doc = self._territory("India")
        validate_territory(doc)
        self.assertEqual(doc.tsi_countries[0].currency, "INR")

    def test_organization_defaults_and_wrong_timezone(self):
        org = frappe._dict(name="x", tsi_country="Australia", currency=None, tsi_timezone=None, territory=None)
        apply_organization_defaults(org)
        self.assertEqual(org.tsi_timezone, "Australia/Adelaide")
        self.assertEqual(org.currency, "AUD")

        org.tsi_timezone = "Asia/Kolkata"
        with self.assertRaises(frappe.ValidationError):
            apply_organization_defaults(org)

    def test_explicit_currency_and_timezone_are_kept(self):
        org = frappe._dict(
            name="x", tsi_country="Australia", currency="USD", tsi_timezone="Australia/Perth", territory=None
        )
        apply_organization_defaults(org)
        self.assertEqual((org.currency, org.tsi_timezone), ("USD", "Australia/Perth"))

    def test_territory_countries_empty_without_territory(self):
        self.assertEqual(territory_countries(None), [])
