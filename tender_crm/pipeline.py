# The TSI sales pipeline, as data.
#
# One source of truth shared by the seed patches and by after_install, so a fresh
# site and an existing one end up with the same pipeline rather than two
# definitions that drift.
#
# Why these stages: TSI sells into tendered procurement, where the shape of a deal
# is not the generic demo → quote → negotiate. A bid is submitted against a
# published notice long before anyone negotiates, and it then sits in a technical
# evaluation the seller cannot influence. Vanilla Frappe CRM has no stage for
# either, so deals in those two states used to pile up in "Demo/Making" and made
# the pipeline unreadable — every forecast counted bids that were already out of
# the seller's hands as though they were still being worked.
#
# `position` is what orders the kanban columns, and is also what
# crm_overrides/erpnext_link.py compares to decide whether a status change is
# forward. Keep the list in pipeline order; the positions are derived from it.

# (status, type, probability, color)
#
# `type` is one of Open / Ongoing / On Hold / Won / Lost and is what the CRM's own
# reporting groups by — only `Won` and `Lost` take a deal out of the open pipeline.
DEAL_STATUSES = [
    ("Qualification", "Open", 10, "gray"),
    ("Requirement Study", "Ongoing", 20, "cyan"),
    ("Demo/Making", "Ongoing", 30, "orange"),
    ("Bid/Tender Submitted", "Ongoing", 45, "violet"),
    ("Proposal/Quotation", "Ongoing", 55, "blue"),
    ("Technical Evaluation", "Ongoing", 70, "teal"),
    ("Negotiation", "Ongoing", 80, "yellow"),
    ("Ready to Close", "Ongoing", 90, "purple"),
    ("Won", "Won", 100, "green"),
    ("Lost", "Lost", 0, "red"),
    ("On Hold", "On Hold", 0, "amber"),
]

# (status, type, color)
#
# "Tender Notice" is a lead that came off a procurement portal rather than from a
# person — nobody has been contacted yet, so it is not "Contacted", but it is also
# not an inbound "New" enquiry that someone is waiting on a reply to.
#
# Colors for the six statuses on the working board (New through Qualified) are
# pinned to the Tender CRM design system's Kanban column palette — see
# seed.py's LEAD_RECOLOR_APPLIED_FLAG for why changing these here does not, by
# itself, recolor an already-seeded site.
LEAD_STATUSES = [
    ("New", "Open", "gray"),
    ("Tender Notice", "Open", "cyan"),
    ("Contacted", "Ongoing", "pink"),
    ("Demo Scheduled", "Ongoing", "amber"),
    ("Nurture", "Ongoing", "teal"),
    ("Qualified", "Won", "black"),
    ("Converted", "Won", "teal"),
    ("Unqualified", "Lost", "red"),
    ("Junk", "Lost", "purple"),
]

# Added alongside the reasons crm ships. Every one of these is a way a tendered
# deal is lost that the generic list has no room for: losing on price alone is
# "L1" and says nothing about fit, and a retendered notice is not a loss to a
# competitor at all.
LOST_REASONS = [
    "Lost on Price (L1)",
    "Technical Disqualification",
    "Eligibility Criteria Not Met",
    "EMD or Bid Security Not Furnished",
    "Tender Cancelled or Retendered",
    "Incumbent Vendor Retained",
]

# CRM Territory is a nested set, so it needs a root before it will accept
# anything. TSI sells nationally with a small export book; the zones match how the
# sales team is actually split.
TERRITORY_ROOT = "All Territories"
TERRITORIES = [
    "North India",
    "South India",
    "East India",
    "West India",
    "Central India",
    "International",
]


# The support queue, as data.
# ---------------------------
# Same shape and the same reasons as the two pipelines above: one definition
# shared by the seed patches and after_install, list order defines `position`.
#
# (status, category, color)
#
# `category` is Open / Paused / Resolved / Closed and is what every report
# groups by — open work is Open + Paused. Keeping Resolved and Closed apart
# matters to more than reporting: Ticket.stamp_dates() reads the first to set
# `resolution_date` and the second to set `closed_at`, so collapsing them would
# make one of those two timestamps unreachable.
#
# "Awaiting Info" is Paused rather than Open on purpose. A ticket blocked on a
# reply from the person who raised it is not work the support team can do, and
# counting it as open makes the queue look permanently worse than it is —
# the same complaint that put "Technical Evaluation" in DEAL_STATUSES.
TICKET_STATUSES = [
    ("New", "Open", "gray"),
    ("Assigned", "Open", "cyan"),
    ("In Progress", "Open", "orange"),
    ("Awaiting Info", "Paused", "amber"),
    ("Resolved", "Resolved", "green"),
    ("Closed", "Closed", "black"),
]

# (priority, color)
#
# List order is the sort order, lowest position first: a queue sorted by
# priority has to put Urgent at the top, and the names do not sort that way.
TICKET_PRIORITIES = [
    ("Urgent", "red"),
    ("High", "orange"),
    ("Medium", "blue"),
    ("Low", "gray"),
]

# What kind of work the ticket is — the axis "are we spending the week on bugs
# or on training?" is answered by.
TICKET_TYPES = [
    "Bug",
    "Feature Request",
    "Support Query",
    "Data Request",
    "Training",
    "Other",
]

# Which part of what TSI sells the ticket concerns. A starter set only: unlike
# the statuses, nothing in the code reads a category by name, and the support
# lead is expected to edit this list on the site rather than here.
TICKET_CATEGORIES = [
    "Tender Portal",
    "Bid Preparation",
    "Document Management",
    "Integrations",
    "Reports",
    "Account & Billing",
    "Other",
]
