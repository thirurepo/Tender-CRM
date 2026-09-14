# Installs the CRM Lead form script that filters tsi_state / status / source
# (see tender_crm/lead_import_schema.py).
#
# Also shipped as a fixture (tender_crm/hooks.py's `fixtures` list), which is
# what a fresh install uses; this is what puts it on an already-migrated site.

from tender_crm.setup import ensure_form_scripts


def execute():
    ensure_form_scripts()
