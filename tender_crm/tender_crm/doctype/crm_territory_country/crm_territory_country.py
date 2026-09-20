# Child table row for CRM Territory-tsi_countries: one country a territory
# covers, with the currency Organizations in that territory default to.
# Lives in tender_crm (not crm) because crm's CRM Territory carries no
# geography; the Table field is a Custom Field — see setup.ensure_territory_geo_fields.

from frappe.model.document import Document


class CRMTerritoryCountry(Document):
    pass
