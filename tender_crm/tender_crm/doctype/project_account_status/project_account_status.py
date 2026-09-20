# The stages a Project Account moves through, as records rather than a Select
# option list, so a sales manager can add or re-order them without a code change.
# `category` is the part that matters downstream: Project Account reads it (never
# the status name) to decide when to stamp its Closed date.

from frappe.model.document import Document


class ProjectAccountStatus(Document):
    pass
