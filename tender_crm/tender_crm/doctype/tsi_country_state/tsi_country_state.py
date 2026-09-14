# A state/province master, scoped to a Country, so CRM Lead's tsi_state Link
# field has something to filter against (see lead_import_schema.py's CRM Form
# Script). Seeded from the legacy CRM's TSI State.csv — see legacy_masters.py.

from frappe.model.document import Document


class TSICountryState(Document):
    pass
