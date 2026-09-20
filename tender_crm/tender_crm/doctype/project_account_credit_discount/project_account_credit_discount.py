# Child table row for Project Account-credit_discounts: one occasion on which
# hours were credited or discounted to the client's account, why (Credit Discount
# Type), how many, when, and a free-text comment. Behaviour lives on the parent,
# which totals the rows.

from frappe.model.document import Document


class ProjectAccountCreditDiscount(Document):
    pass
