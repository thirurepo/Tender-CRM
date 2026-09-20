# A client's project account: which project TSI is doing for which client, under
# which account, of what type, for how many hours, and when it started and
# closed.
#
# Shaped to look like a CRM Deal to everything above it, because crm's list
# machinery (crm/api/doc.py's get_data and friends) takes an arbitrary doctype
# string and then asks the controller for `default_list_data` /
# `default_kanban_settings` / `get_non_filterable_fields`. Providing those three
# staticmethods is the whole price of admission for the list, filter, sort and
# group-by views — the same arrangement Ticket uses (see ticket/ticket.py).
#
# Comments, tasks, notes and attachments need nothing here: they attach to any
# document by (reference_doctype, reference_docname) or attached_to_doctype. The
# one thing crm cannot do for us is assemble them into a timeline, because
# crm.api.activities.get_activities only resolves Deals and Leads — that is
# tender_crm/api/project_account_activities.py.

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class ProjectAccount(Document):
    def validate(self):
        self.apply_default_status()
        self.check_dates()
        self.stamp_closed_date()

    def apply_default_status(self):
        """Give a new account the first live status rather than leaving it blank.

        Only fills an empty field, so an account someone deliberately left
        without a status is not overwritten on its next save. Picks by category
        and position, never by name, so a site that renames "Active" keeps
        working.
        """
        if self.status:
            return

        open_statuses = frappe.get_all(
            "Project Account Status",
            filters={"category": "Open", "disabled": 0},
            order_by="position asc",
            pluck="name",
            limit=1,
        )
        if open_statuses:
            self.status = open_statuses[0]

    def check_dates(self):
        if (
            self.start_date
            and self.closed_date
            and getdate(self.closed_date) < getdate(self.start_date)
        ):
            frappe.throw(
                _("Closed date cannot be before the Start date"),
                title=_("Invalid dates"),
            )

    def stamp_closed_date(self):
        """Move the Closed date with the status category.

        Keyed off the category so renaming or adding statuses does not silently
        stop the stamping. Only fires when the status actually changed, so a
        hand-entered Closed date on an ordinary edit is left alone. Reopening
        clears it: an account that is live again has not closed, and a stale
        date would make "closed this month" counts wrong — but never on insert,
        so back-filling an account with a Closed date and an open status is not
        undone.
        """
        if not self.has_value_changed("status"):
            return

        category = (
            frappe.db.get_value("Project Account Status", self.status, "category")
            if self.status
            else None
        )

        if category == "Closed":
            if not self.closed_date:
                self.closed_date = today()
        elif not self.is_new():
            self.closed_date = None

    @staticmethod
    def get_non_filterable_fields():
        """Nothing here is unfilterable; crm just requires the method."""
        return []

    @staticmethod
    def default_list_data():
        columns = [
            {"label": "ID", "type": "Data", "key": "name", "width": "8rem"},
            {
                "label": "Organization",
                "type": "Link",
                "options": "CRM Organization",
                "key": "organization",
                "width": "14rem",
            },
            {"label": "Project", "type": "Data", "key": "project", "width": "14rem"},
            {
                "label": "Account",
                "type": "Link",
                "options": "Customer",
                "key": "account",
                "width": "12rem",
            },
            {
                "label": "Type",
                "type": "Link",
                "options": "Project Account Type",
                "key": "account_type",
                "width": "10rem",
            },
            {
                "label": "Status",
                "type": "Link",
                "options": "Project Account Status",
                "key": "status",
                "width": "9rem",
            },
            {"label": "Hours", "type": "Float", "key": "hours", "width": "7rem"},
            {"label": "Start", "type": "Date", "key": "start_date", "width": "8rem"},
            {"label": "Closed", "type": "Date", "key": "closed_date", "width": "8rem"},
            {
                "label": "Last Modified",
                "type": "Datetime",
                "key": "modified",
                "width": "8rem",
            },
        ]
        rows = [
            "name",
            "organization",
            "project",
            "account",
            "account_type",
            "status",
            "hours",
            "start_date",
            "closed_date",
            "modified",
        ]
        return {"columns": columns, "rows": rows}

    @staticmethod
    def default_kanban_settings():
        return {
            "column_field": "status",
            "title_field": "project",
            "kanban_fields": '["organization", "account_type", "hours", "modified"]',
        }
