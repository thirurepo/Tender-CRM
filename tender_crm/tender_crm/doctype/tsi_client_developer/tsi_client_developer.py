# Child table row for CRM Organization-tsi_developers: which developers are
# assigned to a client, shown on the Client detail screen's Developers tab.
# Entered by hand for now — see the "project" field's own description for why
# it is free text rather than a Link.

from frappe.model.document import Document


class TSIClientDeveloper(Document):
    pass
