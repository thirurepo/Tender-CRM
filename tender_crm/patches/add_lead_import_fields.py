# Creates CRM Lead's legacy-import fields (see tender_crm/lead_import_schema.py).
#
# Also shipped as fixtures (tender_crm/fixtures/custom_field.json), which is what a
# fresh install uses; this is what puts them on an already-migrated site.

from tender_crm.setup import ensure_lead_import_fields


def execute():
    ensure_lead_import_fields()
