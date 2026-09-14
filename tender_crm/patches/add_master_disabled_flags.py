# Adds the `disabled` flag to CRM Lead Status and CRM Lead Source, so the
# legacy CRM import can retire values in favour of the legacy CRM's own list.
#
# Also shipped as fixtures (tender_crm/fixtures/custom_field.json), which is what a
# fresh install uses; this is what puts them on an already-migrated site.

from tender_crm.setup import ensure_disabled_flag_fields


def execute():
    ensure_disabled_flag_fields()
