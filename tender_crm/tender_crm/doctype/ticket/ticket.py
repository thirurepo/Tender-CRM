# The support ticket.
#
# Shaped to look like a CRM Deal to everything above it, because crm's list
# machinery (crm/api/doc.py's get_data, get_filterable_fields and friends) takes
# an arbitrary doctype string with no whitelist and then asks the controller for
# `default_list_data` / `default_kanban_settings` / `get_non_filterable_fields`.
# Providing those three staticmethods is the whole price of admission for list,
# filter, sort, group-by and kanban views on the Tickets screen — see
# crm/fcrm/doctype/crm_deal/crm_deal.py for the model.
#
# Tickets are internal-only. They link to a Lead/Client/Deal/User, and email
# from a support mailbox opens and threads onto them, but nothing here sends
# anything to a client.

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from crm.fcrm.doctype.crm_status_change_log.crm_status_change_log import (
    add_status_change_log,
)

# Categories on Ticket Status that mean the work has stopped. Everything that
# needs to know "is this ticket still open?" asks the category, never the status
# name, so a site that renames or adds statuses does not break reporting.
FINISHED_CATEGORIES = ("Resolved", "Closed")

# How a reference document yields the client the ticket is about. An
# Organization is its own client; a Deal and a Lead each carry one; a User is a
# colleague and has none.
ORGANIZATION_SOURCES = {
    "CRM Organization": None,  # the reference *is* the organization
    "CRM Deal": "organization",
    "CRM Lead": "organization",
}


class Ticket(Document):
    def validate(self):
        self.apply_defaults()
        self.resolve_organization()
        self.stamp_dates()

    def before_insert(self):
        if not self.opening_date:
            self.opening_date = now_datetime()

    def apply_defaults(self):
        """Fill in what an inbound email cannot say for itself.

        A ticket created from mail arrives with nothing but a subject and a
        sender — frappe's receiver inserts it with `ignore_mandatory` — so the
        queue's own defaults have to come from somewhere. They come from Tender
        CRM Settings, which is the one place an administrator looks.

        Every default is only applied to an empty field, so a ticket someone
        deliberately left unrouted stays unrouted on the next save. Nothing
        here throws: a configured default pointing at a record that has since
        been deleted or disabled falls through to the next option rather than
        failing an insert and losing the mail behind it.
        """
        settings = frappe.get_cached_doc("Tender CRM Settings")

        if not self.status:
            self.status = self._default_status(settings)

        if not self.priority and self._is_usable(
            "Ticket Priority", settings.default_ticket_priority
        ):
            self.priority = settings.default_ticket_priority

        if not self.team and self._is_usable(
            "Ticket Team", settings.default_ticket_team
        ):
            self.team = settings.default_ticket_team

    def _default_status(self, settings):
        """The configured default, or failing that the first Open status."""
        if self._is_usable("Ticket Status", settings.default_ticket_status):
            return settings.default_ticket_status

        open_statuses = frappe.get_all(
            "Ticket Status",
            filters={"category": "Open", "disabled": 0},
            order_by="position asc",
            pluck="name",
            limit=1,
        )
        return open_statuses[0] if open_statuses else None

    @staticmethod
    def _is_usable(doctype, name):
        """True when `name` still exists on `doctype` and is not disabled."""
        if not name:
            return False
        return bool(frappe.db.exists(doctype, {"name": name, "disabled": 0}))

    def resolve_organization(self):
        """Denormalise the client out of the polymorphic reference.

        `reference_doctype`/`reference_name` is the honest model — a ticket can
        concern a Lead, a Client, a Deal or a colleague — but a Dynamic Link is
        miserable to filter and report on. This one derived field turns "every
        ticket for this client" into an indexed equality filter, which is what
        the Client screen's Tickets tab and every per-client report use.

        Recomputed on every save rather than only when the reference changes,
        so that a deal later attached to an organization repairs its tickets
        on their next edit.
        """
        if not self.reference_doctype or not self.reference_name:
            self.organization = None
            return

        if self.reference_doctype not in ORGANIZATION_SOURCES:
            # A User, or a doctype someone widened the link filter to admit.
            self.organization = None
            return

        source_field = ORGANIZATION_SOURCES[self.reference_doctype]
        if source_field is None:
            self.organization = self.reference_name
            return

        self.organization = (
            frappe.db.get_value(
                self.reference_doctype, self.reference_name, source_field
            )
            or None
        )

    def stamp_dates(self):
        """Move the lifecycle timestamps with the status category.

        Both are derived from the category rather than from a status name so
        that renaming "Resolved" or adding a status between the existing ones
        does not silently stop the stamping.

        Reopening clears them: a ticket that is open again has not been
        resolved, and leaving a stale resolution date behind would make
        "resolved this week" counts wrong.
        """
        if not self.has_value_changed("status"):
            return

        category = self.status_category()
        now = now_datetime()

        if category in FINISHED_CATEGORIES:
            if not self.resolution_date:
                self.resolution_date = now
        else:
            self.resolution_date = None

        if category == "Closed":
            if not self.closed_at:
                self.closed_at = now
        else:
            self.closed_at = None

        self.append_status_change_log()

    def status_category(self):
        if not self.status:
            return None
        return frappe.db.get_value("Ticket Status", self.status, "category")

    def append_status_change_log(self):
        """Record the transition in crm's own CRM Status Change Log table.

        Called from validate(), not on_update(), because crm's helper works by
        `doc.append(...)` — the rows only reach the database if the document is
        saved afterwards, which by on_update it already has been. crm_deal.py
        calls it from validate() for the same reason.

        The helper hardcodes `CRM Deal Status` when it looks up the type to
        record, so on a Ticket it writes the two `*_type` cells empty. Rather
        than fork the helper (there should be exactly one implementation of
        this log), the two cells it just wrote are corrected here from the
        Ticket Status category.
        """
        previous = self.get_doc_before_save()
        previous_category = None
        if previous and previous.status:
            previous_category = frappe.db.get_value(
                "Ticket Status", previous.status, "category"
            )

        add_status_change_log(self)

        if not self.status_change_log:
            return

        # add_status_change_log always leaves the open-ended row for the status
        # just entered as the last one, and — on an update — closed off the row
        # before it.
        self.status_change_log[-1].from_type = self.status_category() or ""
        if len(self.status_change_log) > 1:
            closed_row = self.status_change_log[-2]
            closed_row.to_type = self.status_category() or ""
            if not closed_row.from_type:
                closed_row.from_type = previous_category or ""

    @staticmethod
    def get_non_filterable_fields():
        """Fields that make no sense as a queue filter."""
        return ["status_change_log"]

    @staticmethod
    def default_list_data():
        columns = [
            {
                "label": "Subject",
                "type": "Data",
                "key": "subject",
                "width": "18rem",
            },
            {
                "label": "Status",
                "type": "Link",
                "options": "Ticket Status",
                "key": "status",
                "width": "9rem",
            },
            {
                "label": "Priority",
                "type": "Link",
                "options": "Ticket Priority",
                "key": "priority",
                "width": "8rem",
            },
            {
                "label": "Client",
                "type": "Link",
                "options": "CRM Organization",
                "key": "organization",
                "width": "11rem",
            },
            {
                "label": "Team",
                "type": "Link",
                "options": "Ticket Team",
                "key": "team",
                "width": "9rem",
            },
            {
                "label": "Assigned To",
                "type": "Text",
                "key": "_assign",
                "width": "10rem",
            },
            {
                "label": "Last Modified",
                "type": "Datetime",
                "key": "modified",
                "width": "8rem",
            },
        ]
        rows = [
            "name",
            "subject",
            "status",
            "priority",
            "ticket_type",
            "category",
            "organization",
            "team",
            "assigned_agent",
            "raised_by",
            "reference_doctype",
            "reference_name",
            "opening_date",
            "modified",
            "_assign",
        ]
        return {"columns": columns, "rows": rows}

    @staticmethod
    def default_kanban_settings():
        return {
            "column_field": "status",
            "title_field": "subject",
            "kanban_fields": '["priority", "organization", "team", "_assign", "modified"]',
        }
