# Gives Project Account a default Side Panel layout. Load-bearing, not cosmetic:
# crm's get_sidepanel_sections has no generated fallback, so without a CRM Fields
# Layout row of type "Side Panel" the detail screen's sidebar renders empty. See
# tender_crm/setup.py::ensure_project_account_side_panel_layouts.

from tender_crm.setup import ensure_project_account_side_panel_layouts


def execute():
    ensure_project_account_side_panel_layouts()
