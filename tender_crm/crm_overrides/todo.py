# Surfaces core Frappe `ToDo` records (created behind the scenes by the
# Assign-To feature tsi-crm already ships) on the tsi-crm Tasks tab, next to
# `CRM Task`. `crm.api.activities.get_activities` — the vendor-owned endpoint
# that powers that tab today — only ever queries CRM Task, and is deliberately
# left untouched here rather than overridden: ToDo's response shape has
# nothing to do with `crm`'s activity feed, and wrapping a vendor whitelisted
# method just to bolt on an unrelated doctype would couple this app to
# `crm`'s internal response format across upgrades for no benefit. This is a
# plain additive read endpoint instead; the frontend fetches it alongside
# `get_activities` and merges the two lists itself.
#
# Status changes on a ToDo (Closed/Cancelled) go straight through the generic
# `frappe.client.set_value` from the frontend, the same way CRM Task's own
# status dropdown already works — no backend code needed for that half.

import frappe


@frappe.whitelist()
def get_todos(reference_doctype, reference_name):
	"""Return the ToDo records pointed at a CRM Lead/Deal/Organization record.

	Permission is enforced by ToDo's own `get_permission_query_conditions`/
	`has_permission` (frappe/core/doctype/todo/todo.py): a non-System-Manager
	only ever sees ToDos they are `allocated_to` or `assigned_by` on. That is
	expected here too — a Sales User's Tasks tab shows their own assignments,
	not a teammate's.
	"""
	return frappe.get_list(
		"ToDo",
		filters={
			"reference_type": reference_doctype,
			"reference_name": reference_name,
		},
		fields=[
			"name",
			"description",
			"allocated_to",
			"date",
			"priority",
			"status",
			"reference_type",
			"reference_name",
			"creation",
		],
		order_by="creation desc",
	)
