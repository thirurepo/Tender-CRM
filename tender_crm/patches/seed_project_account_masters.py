# Creates the Project Account masters: statuses and starter types. The status
# ordering is a one-shot guarded by its own global flag, so re-running a migrate
# never undoes a re-order. See tender_crm/seed.py.

from tender_crm.seed import seed_project_account_statuses, seed_project_account_types


def execute():
    seed_project_account_statuses()
    seed_project_account_types()
