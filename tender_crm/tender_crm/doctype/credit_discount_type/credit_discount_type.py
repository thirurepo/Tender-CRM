# Why hours were credited or discounted on a Project Account (an outage, a
# goodwill gesture, a billing correction, ...). A master rather than a Select
# because the reasons are not known up front and are expected to be added on the
# site as they come up; nothing in the code reads a type by name, and none are
# seeded.

from frappe.model.document import Document


class CreditDiscountType(Document):
    pass
