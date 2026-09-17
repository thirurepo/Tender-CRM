# Points the support mailbox named in Tender CRM Settings at Ticket, so mail
# arriving on it opens a ticket and replies thread onto the same one. No-ops
# when no mailbox has been nominated, and never creates an Email Account or
# writes credentials. See tender_crm/setup.py::configure_ticket_email_intake.

from tender_crm.setup import configure_ticket_email_intake


def execute():
    configure_ticket_email_intake()
