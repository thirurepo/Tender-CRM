# Puts TSI's deal stages on the site.
#
# Adds the four stages vanilla Frappe CRM has no room for (Requirement Study,
# Bid/Tender Submitted, Technical Evaluation, On Hold) and, once, re-orders the
# whole pipeline so they sit in the right places between crm's own stages.

from tender_crm.seed import seed_deal_statuses


def execute():
    """See tender_crm/seed.py for why creation and re-ordering are guarded differently."""
    seed_deal_statuses()
