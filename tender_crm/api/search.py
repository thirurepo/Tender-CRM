# The quick-jump search box (the "/" affordance in TsiSidebar.vue).
#
# One endpoint that loops the searchable doctypes, rather than a call per
# doctype from the frontend, because the ranking is cross-type: an exact Client
# name match has to be able to outrank a substring hit on a Lead's phone
# number, and only code that can see every candidate at once can decide that.
# It is also one round trip per debounced keystroke instead of five, and it
# gives a doctype the caller cannot read somewhere to be silently skipped — a
# Support Agent has Ticket read and no CRM Lead read, and their quick jump
# should find tickets rather than fail.
#
# Deliberately *not* built on frappe.desk.search.search_link, even though
# Controls/Link.vue uses it for link fields and it is the obvious reach.
# `search_widget()` builds its OR clause from `name` + the doctype's
# title_field + its `search_fields` (frappe/desk/search.py), and none of CRM
# Lead, CRM Organization, Contact, Ticket or CRM Deal declares search_fields.
# So search_link on CRM Lead searches the naming-series id and lead_name and
# nothing else — not email, not mobile_no, not tsi_legacy_id. Finding a lead by
# the phone number on a sticky note is the whole feature. Link.vue keeps using
# search_link, which is exactly what that endpoint is for.
#
# Every query goes through frappe.get_list, never frappe.get_all and never raw
# SQL: get_list is what applies CRM Lead's and CRM Deal's
# permission_query_conditions (crm's org_hierarchy — a Sales User sees their own
# records and their subtree's, not the company's) plus User Permissions.
# get_all bypasses both, silently.
#
# Scaling ceiling, so the next person does not have to rediscover it: `LIKE
# '%x%'` cannot use an index, so every query here is a table scan. That is the
# right trade at this site's ~700 leads / ~720 clients / ~1,200 contacts, where
# a scan is sub-millisecond. It stops being the right trade somewhere north of
# ~50k rows in a single doctype, at which point the move is a MariaDB FULLTEXT
# index plus MATCH ... AGAINST (see frappe.search.full_text_search), not a
# bigger LIMIT.

import frappe
from frappe import _
from frappe.utils import cint

# Below two characters every query returns most of the table, and no ranking
# makes that useful.
MIN_QUERY_LENGTH = 2

PER_DOCTYPE_LIMIT = 5
TOTAL_LIMIT = 20

# How many rows we pull per doctype before ranking. We rank in Python, so the
# LIMIT the database applies is not the LIMIT the user sees; pulling a wider
# slice is what stops "Acme" ranking below "Acme Holdings" purely because the
# latter happened to be modified more recently.
CANDIDATE_MULTIPLIER = 6


# The search surface, as data — adding a doctype is one dict.
#
# `title_field` is explicit rather than read off frappe.get_meta().title_field
# because two entries would break that: CRM Organization has no title_field at
# all (the docname *is* the organization name), and neither does Contact.
#
# `route` names a vue-router *named route* and its param, not a URL. The
# frontend does router.push({name, params}), and vue-router encodes the param
# for us — which matters because a CRM Organization docname is free text and
# will eventually contain a slash, an ampersand or a '#'.
#
# `search_fields` is ordered by how much a hit on it means: the first entries
# are "this is the record", the rest are "this is how you know the record".
# _score() reads that order.
SEARCH_TARGETS = [
	{
		"doctype": "CRM Lead",
		"entity": "lead",
		"title_field": "lead_name",
		"route": {"name": "Lead", "param": "leadId"},
		"search_fields": [
			"lead_name",
			"first_name",
			"last_name",
			"organization",
			"email",
			"mobile_no",
			"phone",
			"website",
			"tsi_skype",
			"tsi_legacy_id",
			"name",
		],
		"subtitle_fields": ["organization", "email", "mobile_no"],
		"extra_fields": ["status", "modified"],
		"status_field": "status",
	},
	{
		"doctype": "CRM Organization",
		"entity": "client",
		# No title_field on this doctype: the docname is the organization name.
		"title_field": "name",
		"route": {"name": "Organization", "param": "organizationId"},
		"search_fields": [
			"name",
			"organization_name",
			"website",
			"tsi_contact_first_name",
			"tsi_contact_last_name",
			"tsi_contact_email",
			"tsi_contact_mobile",
			"tsi_contact_phone",
		],
		"subtitle_fields": ["tsi_contact_email", "tsi_contact_mobile", "website"],
		"extra_fields": ["tsi_client_status", "modified"],
		"status_field": "tsi_client_status",
	},
	{
		"doctype": "Contact",
		"entity": "contact",
		"title_field": "name",
		"route": {"name": "Contact", "param": "contactId"},
		"search_fields": [
			"name",
			"first_name",
			"last_name",
			"email_id",
			"mobile_no",
			"phone",
			"company_name",
		],
		"subtitle_fields": ["tsi_organization", "email_id", "mobile_no"],
		"extra_fields": ["tsi_organization", "modified"],
		"status_field": None,
	},
	{
		"doctype": "Ticket",
		"entity": "ticket",
		"title_field": "subject",
		"route": {"name": "Ticket", "param": "ticketId"},
		"search_fields": ["name", "subject", "raised_by"],
		"subtitle_fields": ["organization", "raised_by"],
		"extra_fields": ["status", "organization", "modified"],
		"status_field": "status",
	},
	{
		"doctype": "CRM Deal",
		"entity": "deal",
		"title_field": "organization",
		"route": {"name": "Deal", "param": "dealId"},
		"search_fields": ["name", "organization", "lead_name", "email", "mobile_no"],
		"subtitle_fields": ["lead_name", "email"],
		"extra_fields": ["status", "modified"],
		"status_field": "status",
	},
]

# Human labels for the chip on each result row. Kept out of SEARCH_TARGETS so
# the registry stays data and the translation happens per request, not at
# import time (a module-level _() is evaluated once, in whatever language the
# first request happened to use).
ENTITY_LABELS = {
	"lead": lambda: _("Lead"),
	"client": lambda: _("Client"),
	"contact": lambda: _("Contact"),
	"ticket": lambda: _("Ticket"),
	"deal": lambda: _("Deal"),
}


@frappe.whitelist()
def quick_jump(query: str, limit: int | None = None) -> dict:
	"""Search every CRM entity at once and return one ranked, flat result list.

	Permission is enforced per doctype by `frappe.get_list`, which is the only
	reason this can be a single endpoint spanning five doctypes: each get_list
	applies that doctype's own permission_query_conditions and the caller's
	User Permissions before a row is ever ranked. For CRM Lead and CRM Deal
	that is crm's org_hierarchy condition, so a Sales User's quick jump reaches
	their own and their subtree's records and no further.

	A doctype the caller cannot read at all is *skipped*, not fatal. Results are
	flat rather than grouped by doctype: the frontend renders one
	keyboard-navigable list and inserts a header whenever `entity` changes,
	which it can do over a flat array, whereas grouping server-side would throw
	away the cross-type ranking — the one thing only the server can compute.
	"""
	query = (query or "").strip()
	if len(query) < MIN_QUERY_LENGTH:
		# Not an error. The box is simply not ready yet, and throwing here would
		# paint an error state under a half-typed word.
		return {"query": query, "results": [], "truncated": False}

	# The same sanitized term drives both halves, and that is not a tidiness
	# point: the database matches on the stripped term, so scoring against the
	# raw one would score every row zero the moment a query contained a '%' —
	# rows come back, and then rank as if nothing matched.
	term = _sanitize(query)
	if not term:
		return {"query": query, "results": [], "truncated": False}

	pattern = f"%{term}%"
	needle = term.casefold()
	limit = min(cint(limit) or TOTAL_LIMIT, TOTAL_LIMIT)

	rows = []
	for target in SEARCH_TARGETS:
		rows.extend(_search_one(target, pattern, needle))

	_rank(rows)

	truncated = len(rows) > limit
	rows = rows[:limit]
	for row in rows:
		row.pop("_score", None)
		row.pop("_modified", None)

	return {"query": query, "results": rows, "truncated": truncated}


def _search_one(target, pattern, needle):
	"""Search one doctype and return its best PER_DOCTYPE_LIMIT rows, scored."""
	doctype = target["doctype"]

	# Cheaper than catching PermissionError, and it does not put a
	# raised-and-swallowed exception in the error log on every keystroke.
	if not frappe.has_permission(doctype, "read"):
		return []

	meta = frappe.get_meta(doctype)

	def exists(fieldname):
		# A tsi_* Custom Field missing on a half-migrated site would otherwise
		# make get_list throw and take the whole search down with it.
		return fieldname == "name" or meta.has_field(fieldname)

	search_fields = [f for f in target["search_fields"] if exists(f)]
	if not search_fields:
		return []

	fields = _unique(
		["name", "modified", target["title_field"]]
		+ search_fields
		+ [f for f in target["subtitle_fields"] if exists(f)]
		+ [f for f in target["extra_fields"] if exists(f)]
	)

	try:
		records = frappe.get_list(
			doctype,
			fields=fields,
			or_filters=[[f, "like", pattern] for f in search_fields],
			order_by="modified desc",
			limit_page_length=PER_DOCTYPE_LIMIT * CANDIDATE_MULTIPLIER,
		)
	except frappe.PermissionError:
		return []

	scored = [_build_row(target, search_fields, record, needle) for record in records]
	_rank(scored)
	return scored[:PER_DOCTYPE_LIMIT]


def _build_row(target, search_fields, record, needle):
	"""Shape one result row: everything the dropdown needs, no follow-up call."""
	title = record.get(target["title_field"]) or record["name"]
	subtitle = " · ".join(
		str(record.get(f)) for f in target["subtitle_fields"] if record.get(f)
	)
	score, matched_field = _score(target, search_fields, record, needle, title)

	status_field = target.get("status_field")
	return {
		"doctype": target["doctype"],
		"entity": target["entity"],
		"badge": ENTITY_LABELS[target["entity"]](),
		"name": record["name"],
		"title": title,
		"subtitle": subtitle,
		"status": record.get(status_field) if status_field else None,
		# So the UI can say "matched on mobile" when the hit is not in the title
		# and the row would otherwise look like it came back for no reason.
		# None for a title match, which explains itself — decided here because
		# only the server knows which field is the title for each doctype.
		"matched_field": None if matched_field == target["title_field"] else matched_field,
		# A named route, not a URL — see SEARCH_TARGETS.
		"route": {
			"name": target["route"]["name"],
			"params": {target["route"]["param"]: record["name"]},
		},
		"_score": score,
		"_modified": str(record.get("modified") or ""),
	}


def _score(target, search_fields, record, needle, title):
	"""Rank a row: title beats identifier beats contact detail, and exact beats
	prefix beats substring.

	The tiers are spaced widely on purpose, so that later tuning inside one tier
	cannot silently reorder another one.
	"""
	title_cf = (title or "").casefold()
	if title_cf == needle:
		return 1000, target["title_field"]
	if title_cf.startswith(needle):
		return 800, target["title_field"]
	if needle in title_cf:
		return 600, target["title_field"]

	best, best_field = 0, None
	for index, fieldname in enumerate(search_fields):
		value = str(record.get(fieldname) or "").casefold()
		if not value or needle not in value:
			continue
		# Earlier entries in search_fields are the more meaningful matches, so
		# each step down the list costs a little.
		points = (400 if value == needle else 200) - index * 5
		if points > best:
			best, best_field = points, fieldname
	return best, best_field


def _sanitize(query: str) -> str:
	"""Strip the one character that would turn the search into a match-everything.

	frappe's db_query does `value.replace("\\\\", "\\\\\\\\").replace("%", "%%")`
	for a `like` filter (frappe/model/db_query.py) — that doubled % is Python
	%-format escaping, not SQL wildcard neutralisation, and the doubled
	backslash means an escape sequence we supply cannot survive to reach the
	database. So there is no escaping available here, only removal.

	`_` is deliberately left alone. It is a single-character wildcard, so it
	over-matches by exactly one character and never hides a result, whereas
	stripping it would break searching for john_doe@example.com.
	"""
	return query.replace("%", "").strip()


def _rank(rows):
	"""Order rows in place: best score first, most recently modified as the
	tie-break — a strong match on a stale record still beats a weak match on a
	fresh one, so recency only ever breaks ties.

	Two passes rather than one composite key because the secondary key is a
	timestamp *string*, which cannot be negated the way a score can. Python's
	sort is stable, so sorting by the weaker key first and the stronger key
	second gives exactly the composite ordering.
	"""
	rows.sort(key=lambda r: r["_modified"], reverse=True)
	rows.sort(key=lambda r: r["_score"], reverse=True)


def _unique(items):
	return list(dict.fromkeys(items))
