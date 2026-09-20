# What kind of engagement a Project Account is (fixed hours, retainer, ...).
# A master rather than a Select so the list can be edited on the site; nothing in
# the code reads a type by name.

from frappe.model.document import Document


class ProjectAccountType(Document):
    pass
