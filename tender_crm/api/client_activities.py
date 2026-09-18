# The timeline behind the Client (CRM Organization) page's Activity, Emails,
# Comments, Calls, Tasks, Notes and Attachments tabs — the same tabs a Lead
# page has, so a lead converted into a client keeps its whole history.
#
# crm.api.activities.get_activities is what the Lead and Deal pages call, and
# it cannot serve a client: it resolves the name to a CRM Deal or CRM Lead and
# throws DoesNotExistError otherwise. It stays vendor-owned and untouched (the
# same call crm_overrides/todo.py and api/feed.py made). This endpoint returns
# the *same five-tuple shape* — (activities, calls, notes, tasks, attachments)
# — so the frontend's Activities component renders it without a second code
# path, and it reuses crm's own row builders so every row looks identical.
#
# WHAT A CLIENT'S TIMELINE IS MADE OF
#
#   1. The client itself — comments, emails, attachments, calls, notes and
#      tasks logged against the CRM Organization from here on.
#   2. The lead it was converted from — `tsi_converted_from_lead`. The legacy
#      client import set it for 221 clients, carrying 704 historical lead
#      comments; crm_overrides/client_link.py sets it for every lead converted
#      in the UI from now on. Without this, converting a lead would strand its
#      history on a record the sales team no longer opens.
#   3. Deals raised against the client — through crm's own get_deal_activities,
#      which already folds in the deal's source lead. A lead reached through a
#      deal is not read a second time under (2).
#
# PERMISSION: read on the client is required. The source lead and each deal
# are then checked individually and skipped (not failed) when the user cannot
# read them — the same rule crm applies to a deal's source lead. A Sales User
# who owns the client but not the original lead sees the client's own history
# and nothing they could not open directly.

import frappe
from frappe import _
from frappe.desk.form.load import get_docinfo

from crm.api.activities import (
	get_attachments,
	get_deal_activities,
	get_lead_activities,
	get_linked_calls,
	get_linked_notes,
	get_linked_tasks,
	handle_multiple_versions,
	parse_attachment_log,
)

DOCTYPE = "CRM Organization"


@frappe.whitelist()
def get_client_activities(name: str):
	"""Everything that has happened to a client, its source lead and its deals.

	Returned in the exact shape of crm.api.activities.get_activities so the
	shared Activities component can swap endpoints by doctype and nothing else.
	"""
	if not frappe.has_permission(DOCTYPE, "read", name):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	activities, calls, notes, tasks, attachments = [], [], [], [], []

	def absorb(result):
		a, c, n, t, f = result
		activities.extend(a)
		calls.extend(c)
		notes.extend(n)
		tasks.extend(t)
		attachments.extend(f)

	covered_leads = set()

	# Deals first: get_deal_activities already includes each deal's source
	# lead, so recording those leads here stops (2) below repeating them.
	for deal, lead in frappe.get_all(
		"CRM Deal", filters={"organization": name}, fields=["name", "lead"], as_list=True
	):
		if not frappe.has_permission("CRM Deal", "read", deal):
			continue
		absorb(get_deal_activities(deal))
		if lead and frappe.has_permission("CRM Lead", "read", lead):
			covered_leads.add(lead)

	source_lead = frappe.db.get_value(DOCTYPE, name, "tsi_converted_from_lead")
	if (
		source_lead
		and source_lead not in covered_leads
		and frappe.db.exists("CRM Lead", source_lead)
		and frappe.has_permission("CRM Lead", "read", source_lead)
	):
		absorb(get_lead_activities(source_lead))

	# The client's own record goes last: get_docinfo writes into
	# frappe.response["docinfo"], and each helper above overwrote it.
	absorb(_own_activities(name, has_source=bool(source_lead)))

	activities.sort(key=lambda x: x["creation"], reverse=True)
	activities = handle_multiple_versions(activities)

	return activities, calls, notes, tasks, attachments


def _own_activities(name: str, has_source: bool):
	"""The client record's own timeline, built the way crm builds a lead's.

	No field-change rows: CRM Organization does not have track_changes on, so it
	has no Version history to read (see api/README.md, "Turning on Version").
	Status and field edits on a client therefore do not appear in its timeline
	until that ships — comments, emails, calls, notes, tasks and files all do.
	"""
	get_docinfo("", DOCTYPE, name)
	docinfo = frappe.response["docinfo"]

	creation, owner = frappe.db.get_value(DOCTYPE, name, ["creation", "owner"])
	activities = [
		{
			"activity_type": "creation",
			"creation": creation,
			"owner": owner,
			"data": _("converted the lead to this client") if has_source else _("created this client"),
			"is_lead": False,
		}
	]

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

	for communication in docinfo.communications + docinfo.automated_messages:
		activities.append(
			{
				"activity_type": "communication",
				"communication_type": communication.communication_type,
				"communication_date": communication.communication_date or communication.creation,
				"creation": communication.creation,
				"data": {
					"subject": communication.subject,
					"content": communication.content,
					"sender_full_name": communication.sender_full_name,
					"sender": communication.sender,
					"recipients": communication.recipients,
					"cc": communication.cc,
					"bcc": communication.bcc,
					"attachments": get_attachments("Communication", communication.name),
					"read_by_recipient": communication.read_by_recipient,
					"delivery_status": communication.delivery_status,
				},
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

	linked = get_linked_calls(name)
	calls = linked.get("calls", [])
	notes = get_linked_notes(name) + linked.get("notes", [])
	tasks = get_linked_tasks(name) + linked.get("tasks", [])
	attachments = get_attachments(DOCTYPE, name)

	return activities, calls, notes, tasks, attachments
