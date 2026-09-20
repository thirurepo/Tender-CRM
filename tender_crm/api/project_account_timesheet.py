# The hours behind a Project Account's Timesheet tab.
#
# The hours live in tsiconnect's Flexi Timesheet (one row per employee per day)
# and its child table Flexi Hours, which records against a Customer (`company`)
# and a free-text `project`. Project Account was modelled to match: its
# `account` is that Customer and its `project` is that text, so a project
# account's hours are simply the Flexi Hours rows carrying both values. This
# endpoint sums them per developer for a date window.
#
# It reads tsiconnect's tables by name and imports nothing from it, so tender_crm
# keeps no code dependency on tsiconnect (see CLAUDE.md, "Related apps").
#
# PERMISSION: read on the Project Account is the boundary, checked up front.
# Sales roles have no read on Flexi Timesheet, so the aggregate is read directly
# after that check. Only a developer's name and their summed hours leave this
# function — nothing else from the timesheet — which is why bypassing Flexi's own
# permissions here is safe.

import frappe
from frappe import _
from frappe.utils import flt, getdate

DOCTYPE = "Project Account"

# Flexi Hours.activity values that count as hours worked. Break and Private are
# left out (Break is ~0.6 hrs all-time). One place to change if that is revisited.
COUNTED_ACTIVITIES = ("Active", "Idle", "Manual")


@frappe.whitelist()
def get_project_account_timesheet(name: str, from_date: str, to_date: str):
	"""Hours per developer on one project account between two dates, inclusive.

	Returns `{account, project, from_date, to_date, total_hours, developers}`,
	developers being `[{employee, employee_name, hours}]`, most hours first. An
	account with no Account set has nothing to match Flexi Hours against, so it
	returns no developers and `no_account: True` for the UI to explain.
	"""
	frappe.has_permission(DOCTYPE, "read", name, throw=True)

	if not (from_date and to_date):
		frappe.throw(_("From and To dates are required"))
	from_date, to_date = getdate(from_date), getdate(to_date)
	if from_date > to_date:
		frappe.throw(_("From date cannot be after To date"))

	account, project = frappe.db.get_value(DOCTYPE, name, ["account", "project"])
	result = {
		"account": account,
		"project": project,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"total_hours": 0.0,
		"developers": [],
	}
	if not account:
		result["no_account"] = True
		return result

	rows = frappe.db.sql(
		"""
		SELECT
			ts.employee,
			COALESCE(NULLIF(MAX(ts.employee_name), ''), ts.employee) AS employee_name,
			SUM(fh.hours) AS hours
		FROM `tabFlexi Timesheet` ts
		INNER JOIN `tabFlexi Hours` fh
			ON fh.parent = ts.name AND fh.parenttype = 'Flexi Timesheet'
		WHERE fh.company = %(account)s
			AND fh.project = %(project)s
			AND fh.activity IN %(activities)s
			AND ts.date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY ts.employee_doctype, ts.employee
		HAVING SUM(fh.hours) > 0
		ORDER BY hours DESC, employee_name
		""",
		{
			"account": account,
			"project": project,
			"activities": COUNTED_ACTIVITIES,
			"from_date": from_date,
			"to_date": to_date,
		},
		as_dict=True,
	)

	developers = [
		{"employee": r.employee, "employee_name": r.employee_name, "hours": flt(r.hours, 2)}
		for r in rows
	]
	result["developers"] = developers
	result["total_hours"] = flt(sum(r.hours for r in rows), 2)
	return result
