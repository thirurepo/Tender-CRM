# Creates Contact's legacy client-contact-import fields (see
# tender_crm/contact_import_schema.py).
#
# Also shipped as fixtures (tender_crm/fixtures/custom_field.json), which is what a
# fresh install uses; this is what puts them on an already-migrated site.

from tender_crm.setup import ensure_contact_import_fields


def execute():
    ensure_contact_import_fields()
