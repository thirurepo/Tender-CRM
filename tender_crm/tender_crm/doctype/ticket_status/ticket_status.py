# The support queue's stages, as records rather than a Select option list.
#
# A record per status is what lets the kanban board be re-ordered and
# re-coloured by a support lead without a code change, exactly as CRM Deal
# Status does for the sales pipeline. `category` is the part that matters to
# anything downstream: reports ask "is this ticket still open?" by reading the
# category, never by comparing the status name.

from frappe.model.document import Document


class TicketStatus(Document):
    pass
