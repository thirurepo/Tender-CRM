# The global activity feed — "everything happening" across the four sidebar
# entities: CRM Lead, CRM Organization, CRM Task and Ticket.
#
# crm.api.activities.get_activities is the obvious thing to reach for and it
# cannot do this job: it takes a single record name, resolves it to a CRM Deal
# or a CRM Lead and throws otherwise, and it leans on frappe.desk.form.load's
# get_docinfo, which is per-document by construction. It is also vendor-owned
# and stays untouched — the same call crm_overrides/todo.py made about it.
#
# PERMISSION, the load-bearing property of this module:
#
#   None of Comment, Communication, Version or a child-table query has a
#   per-reference permission of its own. Anyone with `read` on Comment can read
#   every comment on the site. The *parent record* is the only permission
#   boundary that exists for these rows, so every event is filtered by a
#   frappe.get_list against its parent doctype before it leaves this module
#   (see _resolve_and_filter). That pass resolves the display title in the same
#   query, because the round trip is already paid for.
#
#   The corollary is that frappe.get_all is correct inside the event-source
#   adapters and nowhere else: filtering *there* would be theatre, since the row
#   carries no permission of its own, and the real check happens downstream.
#
# EVENT SOURCES were chosen from what this site actually has, measured, not from
# what the schema permits:
#
#   * record creation on all four doctypes — the only source that covers CRM
#     Organization and CRM Task at all, since neither has track_changes on. It
#     is also the only source that permission-filters *inside* its own query
#     (the row is the record), which is why it never under-fills a page.
#   * Comment where comment_type = 'Comment' — the only source with real content
#     today: 2,849 legacy lead comments with creation dates back to 2017. The
#     comment_type filter is load-bearing, see COMMENT_TYPES below.
#   * CRM Status Change Log — status transitions on CRM Lead and Ticket, written
#     by the controllers regardless of track_changes, with a typed from/to and a
#     log_owner. Preferred over Version for status for exactly that reason.
#   * Communication — emails. Zero rows reference a CRM doctype today, but
#     ticket.json already carries email_append_to, so this turns itself on the
#     day support mail starts landing.
#   * CRM Call Log — calls. Zero rows today; telephony is not configured.
#   * ToDo — assignments. See the ToDo visibility note below.
#
# Version is deliberately off (ENABLE_VERSION_SOURCE) and CRM Notification is
# out entirely — it is the notification bell's per-user mention list, not a
# feed. README.md in this package has the reasoning for each.

import base64
import json

import frappe
from frappe import _
from frappe.utils import (
	add_to_date,
	cint,
	get_datetime,
	get_datetime_str,
	getdate,
	now_datetime,
	strip_html_tags,
)

DEFAULT_LIMIT = 20
MAX_LIMIT = 50

# Candidate rows pulled per source per attempt. Wider than `limit` because the
# permission pass removes rows after the fetch, not during it.
WINDOW_MULTIPLIER = 3

# How many times we widen the window when permission filtering under-fills a
# page. Bounded so that a user whose visible slice is sparse gets a short page
# with has_more=true, rather than a request that walks the whole table looking
# for twenty rows it is never going to find.
MAX_REFETCH = 4

# Comment content is Text Editor HTML and can be arbitrarily long. The feed
# shows a taste; the record shows the rest.
DETAIL_LENGTH = 200

# Only real human comments. The legacy CRM import also wrote 674 'Assigned' +
# 674 'Shared' + 68 'Info' comment rows inside a four-minute window on
# 2026-09-14, and without this filter the first 1,416 entries of the feed are
# one script run. Assignment is carried by the ToDo source instead, where it has
# a real actor and a real target.
COMMENT_TYPES = ["Comment"]

# The doctypes whose controllers call crm's add_status_change_log, and so are
# the only ones with a CRM Status Change Log child table to read. CRM
# Organization and CRM Task have no status history at all — their status, where
# they have one, is only ever the current value on the record.
STATUS_LOGGED_DOCTYPES = ("CRM Lead", "Ticket")

# tabVersion is ~790k rows on this bench, 98% of them Flexi Timesheet and
# Attendance belonging to the HRMS that shares this database, and exactly zero
# of them reference a CRM doctype — it is simultaneously the most expensive
# source and the emptiest. Its indexes are (ref_doctype, docname) and
# (creation), with no composite: the window query's selective predicate and its
# ORDER BY ... LIMIT would be served by different indexes, so the optimizer is
# free to walk backwards through hundreds of thousands of HRMS rows to find
# ours, getting slower the deeper the cursor goes.
#
# Turning this on needs, first: an index on Version (ref_doctype, creation), and
# Property Setters enabling track_changes on CRM Organization and CRM Task
# (without which those two never produce a Version row at all). Both belong in
# setup.py *and* a patch wrapper, per the both-paths rule in CLAUDE.md. Run
# EXPLAIN on the window query before trusting the index to have fixed it.
ENABLE_VERSION_SOURCE = False

# A note on ToDo visibility, because it differs from crm_overrides/todo.py on
# purpose. ToDo's own get_permission_query_conditions restricts a
# non-System-Manager to ToDos they are allocated_to or assigned_by on, and
# todo.py's endpoint (via get_list) honours that. The feed reads ToDo with
# get_all instead and, like every other source here, lets the *parent record*
# decide: an assignment shows to anyone who can read the lead it is on. That is
# not a leak — the same assignment is already on the lead itself, in its
# assigned-to avatars — and it keeps the feed consistent: two people who can
# see the same leads see the same events.


# The four sidebar entities.
#
# `title_field` is explicit, not read from frappe.get_meta().title_field: CRM
# Organization has none (the docname is the name) and CRM Task has none
# declared, though it does have a `title` column. Asking get_list for a field
# that does not exist throws.
#
# CRM Task has no per-task route in frontend/src/router.js — only the Tasks
# list — so a task event routes to the record it references when it has one,
# and to the list when it does not. `route` is None here to say so.
#
# `added_date_field` is the legacy-import backfill. Every lead and all but one
# client on this site were created by the legacy CRM import inside a single
# minute on 2026-09-14, so their `creation` is the import's timestamp, not the
# record's — and ordering by it puts ~1,440 "Thirupathy added this client" rows
# at the top of the feed, burying the real history beneath one script run. The
# importers carried the true date across in tsi_added_date instead (the comment
# importer, by contrast, backdated Comment.creation directly — see
# Import_crm_data/import_lead_comments.py). Reading it here puts creation events
# on the same historical timeline as those comments. See _creation_events.
ENTITIES = {
	"CRM Lead": {
		"entity": "lead",
		"title_field": "lead_name",
		"status_field": "status",
		"added_date_field": "tsi_added_date",
		"route": {"name": "Lead", "param": "leadId"},
		"created_label": lambda: _("created this lead"),
	},
	"CRM Organization": {
		"entity": "client",
		"title_field": "name",
		"status_field": "tsi_client_status",
		"added_date_field": "tsi_added_date",
		"route": {"name": "Organization", "param": "organizationId"},
		"created_label": lambda: _("added this client"),
	},
	"CRM Task": {
		"entity": "task",
		"title_field": "title",
		"status_field": "status",
		"added_date_field": None,
		"route": None,
		"created_label": lambda: _("created this task"),
	},
	"Ticket": {
		"entity": "ticket",
		"title_field": "subject",
		"status_field": "status",
		"added_date_field": None,
		"route": {"name": "Ticket", "param": "ticketId"},
		"created_label": lambda: _("raised this ticket"),
	},
}

FEED_DOCTYPES = list(ENTITIES)

# entity slug -> doctype, for the `entities` filter the frontend sends. The
# frontend filters in the vocabulary the sidebar uses ("client"), not in
# doctype names.
ENTITY_TO_DOCTYPE = {config["entity"]: doctype for doctype, config in ENTITIES.items()}


@frappe.whitelist()
def get_feed(
	before: str | None = None,
	limit: int | None = None,
	entities: str | list | None = None,
	user: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
) -> dict:
	"""Return a page of cross-record activity, newest first.

	Permission is enforced by resolving every event's *parent* record through
	frappe.get_list before the event is returned — see the module comment for
	why that is the only boundary available. A Sales User therefore sees
	comments and status changes on the leads crm's org_hierarchy grants them and
	nothing else, and a record they cannot read produces no events rather than
	an error.

	Pagination is by opaque cursor, not offset. Offset cannot work here: the
	permission pass removes rows *after* the database has applied LIMIT, so the
	number of candidates consumed and the number of events returned differ by an
	amount no caller can know. `before` is an encoded (timestamp, id) pair
	rather than a bare timestamp, because 674 rows on this site share a
	four-minute import window and some share a timestamp exactly; a bare
	timestamp would either drop or repeat every row on that boundary.

	Pass `before` back verbatim from the previous response's `next_cursor`.
	Never construct one.
	"""
	limit = min(cint(limit) or DEFAULT_LIMIT, MAX_LIMIT)
	cursor = _decode_cursor(before)
	doctypes = _resolve_entities(entities)
	if not doctypes:
		return {"events": [], "has_more": False, "next_cursor": None}

	window = limit * WINDOW_MULTIPLIER
	# `to_date` and the cursor constrain the same axis, so they collapse into one
	# ceiling rather than being applied as two separate predicates.
	ceiling = _earliest(cursor[0] if cursor else None, to_date)

	collected = []
	seen_ids = set()
	exhausted = False

	for _attempt in range(MAX_REFETCH):
		candidates, any_window_full = _gather(ceiling, window, doctypes, user, from_date)

		if cursor:
			candidates = [c for c in candidates if (c["timestamp"], c["id"]) < cursor]
		candidates = [c for c in candidates if c["id"] not in seen_ids]
		_sort_newest_first(candidates)
		candidates = candidates[:window]

		if not candidates:
			exhausted = not any_window_full
			break

		seen_ids.update(c["id"] for c in candidates)
		collected.extend(_resolve_and_filter(candidates))

		if len(collected) >= limit or not any_window_full:
			exhausted = not any_window_full
			break

		# Widen: continue from the oldest candidate we have already considered.
		ceiling = candidates[-1]["timestamp"]

	_sort_newest_first(collected)
	page = collected[:limit]
	# Honest rather than optimistic: a short page returned with has_more=False
	# silently ends the caller's infinite scroll, which is the bug the refetch
	# loop above exists to prevent — don't reintroduce it here.
	has_more = bool(page) and (len(collected) > limit or not exhausted)

	return {
		"events": page,
		"has_more": has_more,
		"next_cursor": _encode_cursor(page[-1]) if page and has_more else None,
	}


@frappe.whitelist()
def get_recent_count(hours: int | None = 24) -> int:
	"""Count the events of the last `hours`, for the sidebar's Activity Feed chip.

	Deliberately a bounded window rather than a lifetime total: the other four
	sidebar counts answer "how big is this thing?", which is a useful number for
	a record collection and a useless one for a stream. This answers "is
	anything happening?".

	It runs the same permission-filtered pipeline as get_feed and caps at
	MAX_LIMIT, so a busy day reads "50" rather than costing a full scan to say
	"312". The chip is a nudge, not a report.
	"""
	since = add_to_date(now_datetime(), hours=-max(cint(hours) or 24, 1))
	# get_feed is whitelisted, and inside a request frappe validates its type
	# hints even on an in-process call, so from_date must be the string an HTTP
	# caller would send, not a datetime.
	page = get_feed(limit=MAX_LIMIT, from_date=get_datetime_str(since))
	return len(page["events"])


def _gather(ceiling, window, doctypes, user, from_date):
	"""Run every enabled source and return (candidate events, any window full).

	The second value drives the refetch loop: a source that returned a full
	window is a source that has more rows behind it, which is the only evidence
	that widening is worth another round trip.
	"""
	events = []
	any_window_full = False

	sources = [
		_creation_events,
		_comment_events,
		_status_log_events,
		_communication_events,
		_call_log_events,
		_todo_events,
	]
	if ENABLE_VERSION_SOURCE:
		sources.append(_version_events)

	for source in sources:
		rows, window_full = source(ceiling, window, doctypes, user, from_date)
		events.extend(rows)
		any_window_full = any_window_full or window_full

	return events, any_window_full


def _resolve_and_filter(candidates):
	"""Permission-filter a merged window and resolve every reference's title.

	One get_list per distinct doctype in the window — never one has_permission
	per row. frappe.has_permission on a CRM Lead runs crm's org_hierarchy
	condition as its own query per document, so a 60-row window would be 60
	queries each carrying a CRM Sales Hierarchy subquery; this is at most four.

	Every outcome that should hide a row — deleted, hidden by a permission query
	condition, blocked by a User Permission — produces the same result here: the
	reference is absent from `allowed` and the event vanishes. Fail closed.
	"""
	by_doctype = {}
	for candidate in candidates:
		by_doctype.setdefault(candidate["reference_doctype"], set()).add(
			candidate["reference_name"]
		)

	allowed = {}
	for doctype, names in by_doctype.items():
		config = ENTITIES.get(doctype)
		if not config:
			continue

		title_field = config["title_field"]
		fields = ["name"]
		if title_field != "name":
			fields.append(title_field)
		if config["status_field"] and frappe.get_meta(doctype).has_field(
			config["status_field"]
		):
			fields.append(config["status_field"])

		try:
			rows = frappe.get_list(
				doctype,
				filters={"name": ["in", list(names)]},
				fields=fields,
				# Not optional. get_list defaults to 20 and this window is 60
				# names; omitting it silently drops two thirds of every page and
				# looks exactly like a permission bug.
				limit_page_length=0,
			)
		except frappe.PermissionError:
			# No read on the doctype at all — a Support Agent and CRM Lead. The
			# whole doctype drops out and the rest of the feed stands.
			continue

		for row in rows:
			allowed[(doctype, row["name"])] = {
				"title": row.get(title_field) or row["name"],
				"status": row.get(config["status_field"]) if config["status_field"] else None,
			}

	resolved = []
	for candidate in candidates:
		key = (candidate["reference_doctype"], candidate["reference_name"])
		if key not in allowed:
			continue
		candidate["reference_title"] = allowed[key]["title"]
		candidate["reference_status"] = allowed[key]["status"]
		candidate["route"] = _route_for(candidate)
		resolved.append(candidate)

	# Names before summaries: an assignment's sentence names its assignee.
	_attach_user_names(resolved)
	for event in resolved:
		event["summary"] = _summarize(event)
	return resolved


# ---------------------------------------------------------------------------
# Event sources
#
# Each returns (events, window_full). Every one of them must produce the
# normalized row shape documented in README.md, and every one but
# _creation_events leaves permission to _resolve_and_filter.
# ---------------------------------------------------------------------------


def _creation_events(ceiling, window, doctypes, user, from_date):
	"""New leads, clients, tasks and tickets.

	The only source that covers CRM Organization and CRM Task at all, since
	neither has track_changes, and the only one whose rows *are* the records —
	so get_list permission-filters it exactly, in the database, and it can never
	under-fill the page downstream.

	Imported records are the wrinkle — see `added_date_field` on ENTITIES. For
	a doctype that has one, this runs two disjoint queries: records whose added
	date is set, ordered on that, and records whose added date is empty, ordered
	on `creation`. Two plain indexed-column queries through get_list, rather than
	one ORDER BY COALESCE(...), because get_list is what carries the permission
	conditions and it will not order on an expression.
	"""
	events = []
	window_full = False

	for doctype in doctypes:
		config = ENTITIES[doctype]
		meta = frappe.get_meta(doctype)

		fields = ["name", "creation", "owner"]
		# A CRM Task event should land on the lead it is about, not float
		# unattached, so carry its reference through when it has one.
		if doctype == "CRM Task" and meta.has_field("reference_doctype"):
			fields += ["reference_doctype", "reference_docname"]

		added_field = config["added_date_field"]
		if added_field and not meta.has_field(added_field):
			added_field = None

		passes = []
		if added_field:
			fields.append(added_field)
			# Backfilled records have no known actor (the owner is whoever ran
			# the import), so they cannot answer a "what did this user do?"
			# filter and are left out of it entirely.
			if not user:
				backfilled = _time_filters(added_field, ceiling, from_date)
				backfilled.setdefault(added_field, ["is", "set"])
				passes.append((backfilled, f"{added_field} desc"))
			native = _time_filters("creation", ceiling, from_date)
			native[added_field] = ["is", "not set"]
			passes.append((native, "creation desc"))
		else:
			passes.append((_time_filters("creation", ceiling, from_date), "creation desc"))

		for filters, order_by in passes:
			if user:
				filters["owner"] = user
			try:
				rows = frappe.get_list(
					doctype,
					filters=filters,
					fields=fields,
					order_by=order_by,
					limit_page_length=window,
				)
			except frappe.PermissionError:
				rows = []

			window_full = window_full or len(rows) == window
			for row in rows:
				events.append(_creation_event(doctype, config, row, added_field))

	return events, window_full


def _creation_event(doctype, config, row, added_field):
	"""Shape one creation row, placing a backfilled record at its real date.

	A record counts as backfilled when its added date is on a different day
	from its `creation` — the import wrote today's timestamp and carried the
	true date across separately. Such a record is placed at that true date, and
	its actor is left empty rather than credited to whoever ran the import:
	"Thirupathy added this client" in 2019 would be a false statement. A record
	whose added date matches its creation day was simply created normally, and
	keeps its precise timestamp and its real owner.
	"""
	timestamp = row["creation"]
	actor = row["owner"]
	legacy = False

	added = row.get(added_field) if added_field else None
	if added and getdate(added) != getdate(row["creation"]):
		timestamp = added
		actor = None
		legacy = True

	data = _task_reference(row) if doctype == "CRM Task" else {}
	if legacy:
		data["legacy"] = True

	return {
		"id": f"created:{doctype}:{row['name']}",
		"event_type": "created",
		"timestamp": _ts(timestamp),
		"actor": actor,
		"reference_doctype": doctype,
		"reference_name": row["name"],
		"entity": config["entity"],
		"detail": None,
		"data": data,
	}


def _comment_events(ceiling, window, doctypes, user, from_date):
	"""Human comments and TSI notes on any of the four entities."""
	filters = _time_filters("creation", ceiling, from_date)
	filters["comment_type"] = ["in", COMMENT_TYPES]
	filters["reference_doctype"] = ["in", doctypes]
	if user:
		filters["comment_email"] = user

	fields = [
		"name",
		"creation",
		"owner",
		"comment_email",
		"reference_doctype",
		"reference_name",
		"content",
	]
	# The note type is a tsi_* Custom Field; a half-migrated site may not have it.
	has_note_type = frappe.get_meta("Comment").has_field("tsi_note_type")
	if has_note_type:
		fields.append("tsi_note_type")

	rows = frappe.get_all(
		"Comment",
		filters=filters,
		fields=fields,
		order_by="creation desc",
		limit_page_length=window,
	)

	events = [
		{
			"id": f"comment:{row['name']}",
			"event_type": "comment",
			"timestamp": _ts(row["creation"]),
			# comment_email, not owner. Frappe's own convention is that
			# comment_email is the author and owner is whoever inserted the row
			# — normally the same person, but not for the 2,849 legacy
			# comments, whose owner is the Administrator who ran the import and
			# whose comment_email carries the real author across from the old
			# CRM (Import_crm_data/import_lead_comments.py).
			"actor": row.get("comment_email") or row["owner"],
			"reference_doctype": row["reference_doctype"],
			"reference_name": row["reference_name"],
			"entity": ENTITIES[row["reference_doctype"]]["entity"],
			"detail": _excerpt(row.get("content")),
			"data": {"note_type": row.get("tsi_note_type")} if has_note_type else {},
		}
		for row in rows
	]
	return events, len(rows) == window


def _status_log_events(ceiling, window, doctypes, user, from_date):
	"""Status transitions, from CRM Status Change Log rather than Version.

	The child table is written by the controllers (crm_lead.py, crm_deal.py,
	ticket.py) regardless of track_changes, and carries a typed from/to plus the
	actor — where a Version row is a JSON blob that only exists if the doctype
	opted in.

	Reading it needs one non-obvious fact from crm_status_change_log.py's
	add_status_change_log: each save *appends* an open-ended row whose `from` is
	the NEW status and whose from_date is the moment of the change, then closes
	the previous row's `to`. So the event "entered status X at time T" lives in
	the from_* columns, not the to_* ones.

	The consequence is that the first row of every parent is written on insert
	and duplicates that record's creation event — which is what all 718 rows on
	this site currently are. _is_creation_echo drops them.
	"""
	logged = [d for d in doctypes if d in STATUS_LOGGED_DOCTYPES]
	if not logged:
		return [], False

	events = []
	window_full = False

	# One query per parent doctype rather than a single `parenttype in (...)`,
	# because the `parent` kwarg below is a *single* doctype name — it becomes
	# parent_doctype and drives the blanket read check. Passing one doctype
	# while returning another's rows would refuse the whole source for anyone
	# without read on that one (a Support Agent has Ticket and not CRM Lead).
	for parenttype in logged:
		filters = _time_filters("from_date", ceiling, from_date)
		filters["parenttype"] = parenttype
		if user:
			# Not `owner`: the actor column differs per source, and hardcoding
			# owner here would silently drop every status change.
			filters["log_owner"] = user

		try:
			rows = frappe.get_all(
				"CRM Status Change Log",
				filters=filters,
				fields=["name", "parent", "from_date", "log_owner", "`from`"],
				order_by="from_date desc",
				limit_page_length=window,
				# A child-table query needs its parent named, and the name
				# drives a blanket read check on the parent *doctype*, not a
				# per-row one. That is exactly why these rows still go through
				# _resolve_and_filter.
				parent_doctype=parenttype,
			)
		except frappe.PermissionError:
			continue

		window_full = window_full or len(rows) == window
		echoes = _creation_echoes(parenttype, rows)

		for row in rows:
			if row["name"] in echoes:
				continue
			events.append(
				{
					"id": f"status:{row['name']}",
					"event_type": "status_change",
					"timestamp": _ts(row["from_date"]),
					"actor": row.get("log_owner"),
					"reference_doctype": parenttype,
					"reference_name": row["parent"],
					"entity": ENTITIES[parenttype]["entity"],
					"detail": None,
					# The machine bits, so the frontend can render a status pill
					# without parsing the English summary back apart.
					"data": {"to": row.get("from")},
				}
			)

	return events, window_full


def _communication_events(ceiling, window, doctypes, user, from_date):
	"""Emails sent and received against any of the four entities.

	Zero rows reference a CRM doctype today, but ticket.json carries
	email_append_to / sender_field, so this becomes the richest source the day
	the support mailbox starts landing mail. Cheap enough to leave on until
	then: ~4,600 rows behind comm_ref_type_date_idx.
	"""
	filters = _time_filters("creation", ceiling, from_date)
	filters["reference_doctype"] = ["in", doctypes]
	filters["communication_type"] = "Communication"
	if user:
		filters["owner"] = user

	rows = frappe.get_all(
		"Communication",
		filters=filters,
		fields=[
			"name",
			"creation",
			"owner",
			"reference_doctype",
			"reference_name",
			"subject",
			"sent_or_received",
		],
		order_by="creation desc",
		limit_page_length=window,
	)

	events = [
		{
			"id": f"email:{row['name']}",
			"event_type": "email",
			"timestamp": _ts(row["creation"]),
			"actor": row["owner"],
			"reference_doctype": row["reference_doctype"],
			"reference_name": row["reference_name"],
			"entity": ENTITIES[row["reference_doctype"]]["entity"],
			"detail": _excerpt(row.get("subject")),
			"data": {"direction": row.get("sent_or_received")},
		}
		for row in rows
	]
	return events, len(rows) == window


def _call_log_events(ceiling, window, doctypes, user, from_date):
	"""Telephony call logs linked to any of the four entities.

	Zero rows today — telephony is not configured on this site — but the
	adapter costs one small query and means the feed is already correct on the
	day it is.
	"""
	filters = _time_filters("creation", ceiling, from_date)
	filters["reference_doctype"] = ["in", doctypes]
	if user:
		filters["owner"] = user

	rows = frappe.get_all(
		"CRM Call Log",
		filters=filters,
		fields=[
			"name",
			"creation",
			"owner",
			"reference_doctype",
			"reference_docname",
			"type",
			"status",
			"duration",
		],
		order_by="creation desc",
		limit_page_length=window,
	)

	events = [
		{
			"id": f"call:{row['name']}",
			"event_type": "call",
			"timestamp": _ts(row["creation"]),
			"actor": row["owner"],
			"reference_doctype": row["reference_doctype"],
			"reference_name": row["reference_docname"],
			"entity": ENTITIES[row["reference_doctype"]]["entity"],
			"detail": None,
			"data": {
				"direction": row.get("type"),
				"status": row.get("status"),
				"duration": row.get("duration"),
			},
		}
		for row in rows
	]
	return events, len(rows) == window


def _todo_events(ceiling, window, doctypes, user, from_date):
	"""Assignments, via core ToDo.

	Read with get_all and permission-filtered by the parent record like every
	other source — see the ToDo visibility note at the top of this module for
	why that deliberately differs from crm_overrides/todo.py. Preferred over
	the 'Assigned' comment rows, which on this site are 674 import artefacts
	with no assignee field to read.

	The legacy import also wrote all 174 lead ToDos on this site, inside eight
	seconds, as Administrator. Unlike the records and the comments they carry
	no legacy date to place them at, so they are dropped rather than
	re-dated — see _import_day_rows. The assignment itself is not lost: it is
	still on the lead, which is where anyone asking "who owns this?" looks.
	"""
	filters = _time_filters("creation", ceiling, from_date)
	filters["reference_type"] = ["in", doctypes]
	if user:
		filters["allocated_to"] = user

	rows = frappe.get_all(
		"ToDo",
		filters=filters,
		fields=[
			"name",
			"creation",
			"owner",
			"allocated_to",
			"reference_type",
			"reference_name",
			"description",
		],
		order_by="creation desc",
		limit_page_length=window,
	)
	artefacts = _import_day_rows(rows, "reference_type", "reference_name")

	events = [
		{
			"id": f"assignment:{row['name']}",
			"event_type": "assignment",
			"timestamp": _ts(row["creation"]),
			# The person who did the assigning is the actor; the assignee is
			# what the event is *about* and goes in `data`.
			"actor": row["owner"],
			"reference_doctype": row["reference_type"],
			"reference_name": row["reference_name"],
			"entity": ENTITIES[row["reference_type"]]["entity"],
			"detail": _assignment_detail(row),
			"data": {"allocated_to": row.get("allocated_to")},
		}
		for row in rows
		if row["name"] not in artefacts
	]
	# Measured on the raw rows, not the survivors: a window that came back full
	# of artefacts still has more rows behind it.
	return events, len(rows) == window


def _version_events(ceiling, window, doctypes, user, from_date):
	"""Field changes, from tabVersion. Off by default — see
	ENABLE_VERSION_SOURCE for the index and track_changes prerequisites."""
	filters = _time_filters("creation", ceiling, from_date)
	filters["ref_doctype"] = ["in", doctypes]
	if user:
		filters["owner"] = user

	rows = frappe.get_all(
		"Version",
		filters=filters,
		fields=["name", "creation", "owner", "ref_doctype", "docname", "data"],
		order_by="creation desc",
		limit_page_length=window,
	)

	events = []
	for row in rows:
		change = _first_change(row.get("data"), row["ref_doctype"])
		if not change:
			continue
		events.append(
			{
				"id": f"change:{row['name']}",
				"event_type": "field_change",
				"timestamp": _ts(row["creation"]),
				"actor": row["owner"],
				"reference_doctype": row["ref_doctype"],
				"reference_name": row["docname"],
				"entity": ENTITIES[row["ref_doctype"]]["entity"],
				"detail": None,
				"data": change,
			}
		)
	return events, len(rows) == window


# ---------------------------------------------------------------------------
# Shaping helpers
# ---------------------------------------------------------------------------


def _summarize(event):
	"""The human sentence for a row, built and translated server-side.

	It belongs here rather than in the frontend because only the server knows
	which field changed and what its label is. `data` carries the same facts in
	machine form, so the UI can render a from -> to pill without parsing this
	sentence back apart.
	"""
	event_type = event["event_type"]
	data = event.get("data") or {}

	if event_type == "created":
		return ENTITIES[event["reference_doctype"]]["created_label"]()
	if event_type == "comment":
		note_type = data.get("note_type")
		return _("left a {0}").format(note_type.lower()) if note_type else _("commented")
	if event_type == "status_change":
		return _("moved this to {0}").format(data.get("to") or _("a new status"))
	if event_type == "email":
		return _("received an email") if data.get("direction") == "Received" else _("sent an email")
	if event_type == "call":
		return _("logged an incoming call") if data.get("direction") == "Incoming" else _("logged a call")
	if event_type == "assignment":
		assignee = data.get("allocated_to_name")
		return _("assigned this to {0}").format(assignee) if assignee else _("assigned this")
	if event_type == "field_change":
		return _("changed {0}").format(data.get("label") or data.get("field"))
	return _("updated this")


def _route_for(event):
	"""The vue-router named route this event's row links to.

	A named route object, not a URL string: a CRM Organization docname is free
	text and will eventually contain a slash or an ampersand, and router.push
	encodes params where a hand-built string would not.

	CRM Task has no per-task route, so a task event falls back to the record it
	references, or to the Tasks list when it references nothing.
	"""
	config = ENTITIES[event["reference_doctype"]]
	if config["route"]:
		return {
			"name": config["route"]["name"],
			"params": {config["route"]["param"]: event["reference_name"]},
		}

	referenced = (event.get("data") or {}).get("reference")
	if referenced:
		target = ENTITIES.get(referenced.get("doctype"))
		if target and target["route"] and referenced.get("name"):
			return {
				"name": target["route"]["name"],
				"params": {target["route"]["param"]: referenced["name"]},
			}
	return {"name": "Tasks", "params": {}}


def _attach_user_names(events):
	"""Resolve every user a page mentions — actors and assignees — to a full
	name, in one query for the whole page."""
	users = set()
	for event in events:
		if event.get("actor"):
			users.add(event["actor"])
		assignee = (event.get("data") or {}).get("allocated_to")
		if assignee:
			users.add(assignee)

	names = {}
	if users:
		names = {
			row["name"]: row["full_name"]
			for row in frappe.get_all(
				"User",
				filters={"name": ["in", list(users)]},
				fields=["name", "full_name"],
				limit_page_length=0,
			)
		}

	for event in events:
		data = event.get("data") or {}
		if data.get("allocated_to"):
			data["allocated_to_name"] = names.get(data["allocated_to"]) or data["allocated_to"]
		if (event.get("data") or {}).get("legacy"):
			# Backfilled by the import — see _creation_event. Naming the source
			# rather than leaving a blank is what stops the row reading as if
			# someone forgot to sign it.
			event["actor_name"] = _("Legacy CRM")
			continue
		event["actor_name"] = names.get(event.get("actor")) or event.get("actor")


def _task_reference(row):
	if not row.get("reference_doctype"):
		return {}
	return {
		"reference": {
			"doctype": row["reference_doctype"],
			"name": row.get("reference_docname"),
		}
	}


def _first_change(raw, doctype):
	"""Pull the first field change out of a Version row's JSON payload."""
	try:
		data = json.loads(raw or "{}")
	except ValueError:
		return None

	changes = data.get("changed") or []
	if not changes:
		return None

	field, old, new = (changes[0] + [None, None, None])[:3]
	if not field or (not old and not new):
		return None

	meta_field = frappe.get_meta(doctype).get_field(field)
	return {
		"field": field,
		"label": meta_field.label if meta_field else field,
		"from": old,
		"to": new,
	}


def _excerpt(html):
	"""Comment and email bodies are Text Editor HTML.

	frappe.utils.strip_html_tags does this without the BeautifulSoup import
	crm/api/activities.py reaches for.
	"""
	if not html:
		return None
	text = strip_html_tags(str(html)).strip()
	if len(text) <= DETAIL_LENGTH:
		return text
	return text[:DETAIL_LENGTH].rstrip() + "…"


def _import_day_rows(rows, doctype_key, name_key):
	"""The subset of rows the legacy import wrote about the records it imported.

	A row counts as an import artefact when it references a backfilled record
	(one whose added date and creation day differ — see _creation_event) and was
	itself written on that record's creation day, i.e. the day of the import.
	That is precise enough to need no hardcoded import date, and it is
	self-limiting: it can only ever match on the one day each record was
	imported, so anything written against those records afterwards is kept.

	One query per referenced doctype for the whole batch, for the same reason
	as _creation_echoes.
	"""
	by_doctype = {}
	for row in rows:
		config = ENTITIES.get(row.get(doctype_key))
		if config and config["added_date_field"] and row.get(name_key):
			by_doctype.setdefault(row[doctype_key], set()).add(row[name_key])

	imported_on = {}
	for doctype, names in by_doctype.items():
		added_field = ENTITIES[doctype]["added_date_field"]
		if not frappe.get_meta(doctype).has_field(added_field):
			continue
		for record in frappe.get_all(
			doctype,
			filters={"name": ["in", list(names)]},
			fields=["name", "creation", added_field],
			limit_page_length=0,
		):
			added = record.get(added_field)
			if added and getdate(added) != getdate(record["creation"]):
				imported_on[(doctype, record["name"])] = getdate(record["creation"])

	return {
		row["name"]
		for row in rows
		if imported_on.get((row.get(doctype_key), row.get(name_key)))
		== getdate(row["creation"])
	}


def _assignment_detail(row):
	"""The ToDo's description, unless it is frappe's own boilerplate.

	frappe.desk.form.assign_to.add writes "Assignment for <doctype> <name>" when
	the assigner gives no description, which is nearly always. Repeating the
	record's own name back under a row that already links to it is noise.
	"""
	text = _excerpt(row.get("description"))
	if not text or text.startswith(f"Assignment for {row.get('reference_type')}"):
		return None
	return text


def _creation_echoes(parenttype, rows):
	"""The subset of status rows that merely echo their record's creation.

	add_status_change_log appends its open-ended row on insert too, so every
	record's first status row lands at the same moment as the record itself and
	would otherwise show up twice in the feed — once as "created this lead" and
	once as "moved this to New". On this site all 718 existing rows are exactly
	that.

	One query for the whole batch, not one per row: the feed's whole cost model
	is "a fixed handful of queries per page", and a per-row lookup here would
	quietly make it a per-row model.
	"""
	parents = {row["parent"] for row in rows if row.get("parent")}
	if not parents:
		return set()

	created = {
		row["name"]: row["creation"]
		for row in frappe.get_all(
			parenttype,
			filters={"name": ["in", list(parents)]},
			fields=["name", "creation"],
			limit_page_length=0,
		)
	}

	echoes = set()
	for row in rows:
		reference_creation = created.get(row.get("parent"))
		if not reference_creation or not row.get("from_date"):
			continue
		drift = get_datetime(row["from_date"]) - get_datetime(reference_creation)
		if abs(drift.total_seconds()) < 2:
			echoes.add(row["name"])
	return echoes


# ---------------------------------------------------------------------------
# Filters, cursor and sorting
# ---------------------------------------------------------------------------


def _resolve_entities(entities):
	"""Map the frontend's entity slugs to doctypes, defaulting to all four."""
	if not entities:
		return FEED_DOCTYPES

	if isinstance(entities, str):
		entities = frappe.parse_json(entities) if entities.startswith("[") else [entities]

	resolved = [ENTITY_TO_DOCTYPE[e] for e in entities if e in ENTITY_TO_DOCTYPE]
	return resolved or FEED_DOCTYPES


def _time_filters(fieldname, ceiling, from_date):
	"""Build the time window for one source, on whichever column carries its
	timestamp. `ceiling` already folds together the cursor and any to_date."""
	if ceiling and from_date:
		return {fieldname: ["between", [from_date, ceiling]]}
	if ceiling:
		return {fieldname: ["<=", ceiling]}
	if from_date:
		return {fieldname: [">=", from_date]}
	return {}


def _earliest(*values):
	present = [v for v in values if v]
	if not present:
		return None
	return _ts(min(get_datetime(v) for v in present))


def _ts(value):
	"""Render any date or datetime as one fixed-width timestamp string.

	The cursor and the merge both compare timestamps *as strings*, which is only
	sound if every source renders them identically. str() does not:
	str(datetime) drops the microseconds when they are zero, and a backfilled
	tsi_added_date is a bare date with no time at all. Fixed width makes string
	order and chronological order the same thing.
	"""
	return get_datetime(value).strftime("%Y-%m-%d %H:%M:%S.%f")


def _sort_newest_first(events):
	"""Newest first, with `id` breaking ties.

	The tie-break is not decoration: 674 comments on this site share a
	four-minute import window and some share a timestamp exactly, so without a
	deterministic second key the cursor cannot tell which rows a page already
	returned.
	"""
	events.sort(key=lambda e: (e["timestamp"], e["id"]), reverse=True)


def _encode_cursor(event):
	"""Opaque on purpose — base64 so a caller is not tempted to build one, and
	so its internal shape can change without breaking a client that is round-
	tripping it verbatim."""
	raw = json.dumps([event["timestamp"], event["id"]])
	return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor):
	if not cursor:
		return None
	try:
		timestamp, event_id = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
		return (str(timestamp), str(event_id))
	except Exception:
		# A malformed cursor means a stale or hand-made link. Starting from the
		# top is a better answer than a 500 on a page the user just opened.
		return None
