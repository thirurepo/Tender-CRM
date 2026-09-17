# What kind of work a ticket is — the axis support reports on to answer "are we
# spending our week on bugs or on training?".
#
# Deliberately separate from Ticket Category: type is the nature of the work,
# category is the part of the product it concerns.

from frappe.model.document import Document


class TicketType(Document):
    pass
