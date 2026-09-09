# Creates the fields that tie a CRM Deal to the ERPNext documents raised from it.
#
# Also shipped as fixtures (tender_crm/fixtures/custom_field.json), which is what a
# fresh install uses; this is what puts them on an already-migrated site.

from tender_crm.setup import ensure_link_fields


def execute():
    ensure_link_fields()
