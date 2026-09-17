# How urgent a ticket is, as records so the set can be tuned per site.
#
# `position` exists because the one thing a support queue is always sorted by
# is urgency, and the names do not sort that way on their own.

from frappe.model.document import Document


class TicketPriority(Document):
    pass
