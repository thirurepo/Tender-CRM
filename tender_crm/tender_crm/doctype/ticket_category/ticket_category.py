# Which part of what TSI sells a ticket is about.
#
# The starter set seeded by tender_crm.seed is a guess at TSI's product surface
# and is expected to be edited by the support lead; nothing in the code reads a
# category by name.

from frappe.model.document import Document


class TicketCategory(Document):
    pass
