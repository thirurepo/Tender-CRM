# Creates the support queue's masters: statuses, priorities, types and the
# starter categories. The status and priority orderings are one-shots guarded by
# their own global flags, so re-running a migrate never undoes a re-order done
# on the kanban board. See tender_crm/seed.py.

from tender_crm.seed import (
    seed_ticket_categories,
    seed_ticket_priorities,
    seed_ticket_statuses,
    seed_ticket_types,
)


def execute():
    seed_ticket_statuses()
    seed_ticket_priorities()
    seed_ticket_types()
    seed_ticket_categories()
