# Switches on crm's own ERPNext integration (ERPNext CRM Settings), which ships
# off by default. One-shot and non-destructive — see tender_crm/setup.py.

from tender_crm.setup import configure_erpnext_integration


def execute():
    configure_erpnext_integration()
