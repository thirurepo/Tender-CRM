# A reusable snippet an agent drops into a ticket reply.
#
# Nothing is seeded: a canned response is written in the support team's own
# voice, and a shipped placeholder would only ever be sent by accident.

from frappe.model.document import Document


class CannedResponse(Document):
    pass
