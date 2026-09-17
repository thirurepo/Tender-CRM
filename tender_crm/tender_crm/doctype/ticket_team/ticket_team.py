# A group of agents a ticket can be routed to, and the core Assignment Rule
# that picks which of them actually gets it.
#
# Read-only for Support Agent on purpose: who is on which team is a support
# lead's decision, not an agent's. No teams are seeded — TSI's support
# structure is not something this app can guess.

from frappe.model.document import Document


class TicketTeam(Document):
    pass
