# Creates Comment's legacy comment/reply-import fields (see
# tender_crm/comment_import_schema.py).
#
# Also shipped as fixtures (tender_crm/fixtures/custom_field.json), which is what a
# fresh install uses; this is what puts them on an already-migrated site.
#
# Must run after add_client_lead_fields (which creates Comment-tsi_note_type,
# the insert_after anchor for tsi_legacy_comment_id) — see patches.txt order.

from tender_crm.setup import ensure_comment_import_fields


def execute():
    ensure_comment_import_fields()
