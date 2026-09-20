# The timeline behind a Project Account's Activity, Comments, Tasks, Notes and
# Attachments tabs.
#
# crm.api.activities.get_activities is what the Lead and Deal pages call, and it
# cannot serve this doctype: it resolves the name to a CRM Deal or CRM Lead and
# throws DoesNotExistError otherwise. It stays vendor-owned and untouched. This
# endpoint returns the *same five-tuple shape* — (activities, calls, notes,
# tasks, attachments) — so the shared Activities component renders it without a
# second code path, and it reuses crm's own row builders so every row looks
# identical to a Lead's. Same approach, and same reasoning, as
# client_activities.py.
#
# WHAT IS IN IT
#
#   * comments, and attachment upload/removal log rows, from Frappe's docinfo;
#   * field changes, from Version — Project Account has track_changes on, so
#     unlike a Client, status and field edits do show up here;
#   * notes (FCRM Note) and tasks (CRM Task) whose reference_docname is this
#     account, plus attached Files.
#
# Calls are always empty and Emails never appear: a project account has no phone
# number or mailbox of its own, and the page shows neither tab.
#
# PERMISSION: read on the Project Account is required, checked up front.

import json

import frappe
from frappe import _
from frappe.desk.form.load import get_docinfo

from crm.api.activities import (
	get_attachments,
	get_linked_notes,
	get_linked_tasks,
	handle_multiple_versions,
	parse_attachment_log,
)

DOCTYPE = "Project Account"


@frappe.whitelist()
def get_project_account_activities(name: str):
	"""Everything that has happened to a project account, newest first.

	Returned in the exact shape of crm.api.activities.get_activities so the
	shared Activities component can swap endpoints by doctype and nothing else.
	"""
	if not frappe.has_permission(DOCTYPE, "read", name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	get_docinfo("", DOCTYPE, name)
	docinfo = frappe.response["docinfo"]

	creation, owner = frappe.db.get_value(DOCTYPE, name, ["creation", "owner"])
	activities = [
		{
			"activity_type": "creation",
			"creation": creation,
			"owner": owner,
			"data": _("created this project account"),
			"is_lead": False,
		}
	]

	activities.extend(_field_changes(docinfo.versions))

	for comment in docinfo.comments:
		activities.append(
			{
				"name": comment.name,
				"activity_type": "comment",
				"creation": comment.creation,
				"owner": comment.owner,
				"content": comment.content,
				"attachments": get_attachments("Comment", comment.name),
				"is_lead": False,
			}
		)

	for attachment_log in docinfo.attachment_logs:
		activities.append(
			{
				"name": attachment_log.name,
				"activity_type": "attachment_log",
				"creation": attachment_log.creation,
				"owner": attachment_log.owner,
				"data": parse_attachment_log(attachment_log.content, attachment_log.comment_type),
				"is_lead": False,
			}
		)

	activities.sort(key=lambda x: x["creation"], reverse=True)
	activities = handle_multiple_versions(activities)

	return (
		activities,
		[],
		get_linked_notes(name),
		get_linked_tasks(name),
		get_attachments(DOCTYPE, name),
	)


def _field_changes(versions):
	"""Version rows as crm's added / removed / changed timeline entries.

	Follows the first-change-per-version rule crm's get_lead_activities uses, so
	the rows look and group the same way. Fields the doctype does not declare
	(and edits from nothing to nothing) are skipped.
	"""
	fields = {
		field.fieldname: field.label for field in frappe.get_meta(DOCTYPE).fields
	}
	rows = []

	for version in versions:
		changed = json.loads(version.data).get("changed")
		if not changed:
			continue

		fieldname, old_value, new_value = changed[0][:3]
		if fieldname not in fields or (not old_value and not new_value):
			continue

		data = {
			"field": fieldname,
			"field_label": fields[fieldname] or fieldname,
			"old_value": old_value,
			"value": new_value,
		}
		activity_type = "changed"
		if not old_value:
			activity_type = "added"
			del data["old_value"]
		elif not new_value:
			activity_type = "removed"
			data["value"] = old_value
			del data["old_value"]

		rows.append(
			{
				"activity_type": activity_type,
				"creation": version.creation,
				"owner": version.owner,
				"data": data,
				"is_lead": False,
				"options": None,
			}
		)

	return rows
