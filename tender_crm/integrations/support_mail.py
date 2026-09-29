# The CRM half of the nightly Support Mailbox Digest (see this package's README).
#
# n8n's "TSIERP - Support Mailbox Digest" workflow reads a day of mail from
# support@tendersoftware.in (through tsiconnect's integrations/support_mailbox.py,
# which owns the Microsoft Graph access), asks an LLM to summarise and rank each
# conversation, and calls the two endpoints here:
#
#   match_contacts(emails)  — which lead or client is this thread about, and what
#                             has happened with them lately? The answer is the
#                             context the LLM ranks against ("third complaint
#                             this month").
#   post_support_summary(…) — writes that summary onto the lead/client as a
#                             Comment, so it shows up in the record's Activity and
#                             Comments tabs next to everything else.
#
# Lives in tender_crm, not tsiconnect, because it reads and writes CRM records.
# The Graph side stays in tsiconnect and neither app imports the other, so the
# contract between them is only the JSON n8n passes along.
#
# MATCHING ORDER (first hit wins, per address; addresses are tried in the order
# given, so n8n passes the latest external sender first):
#   1. exact email on CRM Lead.email
#   2. exact email on a Contact (child Contact Email rows, or its legacy primary
#      email), giving Contact.tsi_organization
#   3. exact email on CRM Organization.tsi_contact_email
#   4. domain: the client's website host, then a client contact email on the
#      same domain, then a lead email on the same domain. Free-mail domains
#      (gmail, outlook…) never match by domain, because thousands of unrelated
#      people share them.
# A matched lead that was converted to a client resolves to that client
# (tsi_converted_from_lead), since the sales team works the client from then on.
#
# PERMISSION: both endpoints are System Manager only; n8n calls them as
# autoflow@tendersoftware.in. Candidates are found through frappe.get_list, and
# every record returned or written is checked with has_permission. The Comment
# is authored by the calling API user, so the timeline says honestly that the
# automation wrote it.

import hashlib
import re
from html import unescape
from urllib.parse import quote, urlparse

import frappe
from frappe import _
from frappe.utils import cint, strip_html

from tender_crm.crm_overrides.default_app import DEFAULT_CRM_HOSTS, TSI_CRM_ROUTE

# Domains shared by the public, never evidence of which client a sender is.
FREE_MAIL_DOMAINS = frozenset(
	{
		"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
		"yahoo.com", "yahoo.co.in", "yahoo.co.uk", "ymail.com", "icloud.com", "me.com",
		"aol.com", "proton.me", "protonmail.com", "zoho.com", "rediffmail.com", "gmx.com",
		"bigpond.com", "bigpond.net.au", "btinternet.com", "optusnet.com.au",
	}
)

# Tender Software's own domains: an internal address is never a client match.
TSI_DOMAINS = frozenset(
	{"tendersoftware.in", "tendersoftware.com", "tendersoftware.co.uk", "tendersoftware.com.au"}
)

TARGET_DOCTYPES = ("CRM Lead", "CRM Organization")
RECENT_ACTIVITY_LIMIT = 8
ACTIVITY_TEXT_CHARS = 300

# Hidden in every digest comment so a rerun of the same night updates the
# comment it wrote before, instead of stacking a duplicate. Comment.content has
# ignore_xss_filter set, so the HTML comment survives the save. The Graph
# conversationId (~150 chars of base64) is hashed down to keep the marker short
# and LIKE-safe.
MARKER_TEMPLATE = "<!-- support-digest:{conversation_key}:{digest_date} -->"


# ---------------------------------------------------------------------------
# match_contacts
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def match_contacts(emails):
	"""Best CRM lead/client for a thread's external addresses, with recent activity.

	Returns {"match": {...} | None, "candidates": [...]}. `candidates` lists
	every distinct record any address matched, so the digest can show that one
	thread involves two clients. `match` is the first of them.
	"""
	frappe.only_for("System Manager")

	addresses = _normalise_emails(emails)
	candidates, seen = [], set()
	for address in addresses:
		hit = _match_one(address)
		if hit and (hit["doctype"], hit["name"]) not in seen:
			seen.add((hit["doctype"], hit["name"]))
			candidates.append(hit)

	match = None
	if candidates:
		match = dict(candidates[0])
		match.update(_record_context(match["doctype"], match["name"]))
	return {"match": match, "candidates": candidates}


def _normalise_emails(emails):
	if isinstance(emails, str):
		emails = frappe.parse_json(emails) if emails.strip().startswith("[") else emails.split(",")
	out = []
	for raw in emails or []:
		address = (raw or "").strip().lower()
		domain = address.rpartition("@")[2]
		if "@" in address and address not in out and not _is_tsi(domain):
			out.append(address)
	return out


def _is_tsi(domain):
	return any(domain == d or domain.endswith("." + d) for d in TSI_DOMAINS)


def _match_one(address):
	"""Resolve one address to a lead/client, trying exact matches before the domain."""
	domain = address.rpartition("@")[2]

	lead = _first("CRM Lead", {"email": address})
	if lead:
		return _hit_from_lead(lead, "lead_email", address)

	contact_org = _contact_organization(address)
	if contact_org:
		return _hit("CRM Organization", contact_org, "contact_email", address)

	org = _first("CRM Organization", {"tsi_contact_email": address})
	if org:
		return _hit("CRM Organization", org, "client_contact_email", address)

	if domain in FREE_MAIL_DOMAINS:
		return None

	org = _organization_by_website(domain)
	if org:
		return _hit("CRM Organization", org, "website_domain", address)

	org = _first("CRM Organization", {"tsi_contact_email": ["like", f"%@{domain}"]})
	if org:
		return _hit("CRM Organization", org, "client_email_domain", address)

	lead = _first("CRM Lead", {"email": ["like", f"%@{domain}"]})
	if lead:
		return _hit_from_lead(lead, "lead_email_domain", address)
	return None


def _first(doctype, filters):
	"""First permitted record matching `filters`, most recently modified first."""
	rows = frappe.get_list(doctype, filters=filters, pluck="name", order_by="modified desc", limit=1)
	return rows[0] if rows else None


def _contact_organization(address):
	"""The client a Contact with this email belongs to, if the Contact is linked."""
	contact_names = frappe.get_all(
		"Contact Email", filters={"email_id": address, "parenttype": "Contact"}, pluck="parent"
	)
	contact_names += frappe.get_all("Contact", filters={"tsi_legacy_primary_email": address}, pluck="name")
	if not contact_names:
		return None
	orgs = frappe.get_list(
		"Contact",
		filters={"name": ["in", list(set(contact_names))], "tsi_organization": ["is", "set"]},
		pluck="tsi_organization",
		order_by="modified desc",
		limit=1,
	)
	return orgs[0] if orgs else None


def _website_host(website):
	"""'https://www.acme.com.au/contact' -> 'acme.com.au'."""
	value = (website or "").strip().lower()
	if not value:
		return ""
	if "://" not in value:
		value = "http://" + value
	host = urlparse(value).hostname or ""
	return host[4:] if host.startswith("www.") else host


def _organization_by_website(domain):
	"""The client whose website host is this email domain (or its parent domain).

	`LIKE %domain%` narrows the candidates in SQL; the exact host comparison in
	Python keeps 'acme.com' from matching 'notacme.com'. A mail subdomain
	(it.acme.com) still matches a website of acme.com.
	"""
	base = domain.split(".", 1)[1] if domain.count(".") >= 2 else domain
	rows = frappe.get_list(
		"CRM Organization",
		filters={"website": ["like", f"%{base}%"]},
		fields=["name", "website"],
		order_by="modified desc",
		limit=20,
	)
	for row in rows:
		host = _website_host(row.website)
		if host and (domain == host or domain.endswith("." + host)):
			return row.name
	return None


def _hit_from_lead(lead, match_type, address):
	"""A lead match, redirected to its client when the lead was converted."""
	client = frappe.get_list(
		"CRM Organization", filters={"tsi_converted_from_lead": lead}, pluck="name", limit=1
	)
	if client:
		return _hit("CRM Organization", client[0], match_type + "_converted", address)
	return _hit("CRM Lead", lead, match_type, address)


def _hit(doctype, name, match_type, address):
	if doctype == "CRM Lead":
		row = frappe.db.get_value(
			"CRM Lead", name, ["lead_name", "organization", "status", "lead_owner"], as_dict=True
		)
		title = row.organization or row.lead_name or name
		status, owner, route = row.status, row.lead_owner, f"/leads/{quote(name, safe='')}"
	else:
		row = frappe.db.get_value(
			"CRM Organization", name, ["tsi_client_status", "tsi_account_owner"], as_dict=True
		)
		title, status, owner = name, row.tsi_client_status, row.tsi_account_owner
		route = f"/organizations/{quote(name, safe='')}"
	return {
		"doctype": doctype,
		"name": name,
		"title": title,
		"match_type": match_type,
		"matched_email": address,
		"status": status,
		"owner": owner,
		"url": _crm_url(route),
	}


def _crm_url(route):
	"""An absolute Tender CRM link for the digest email.

	Built on the CRM host rather than frappe.utils.get_url(): the digest is read
	in a mail client, and the client timeline (with its converted-lead history)
	only exists in the tsi-crm frontend. It uses the same `tsi_crm_hosts`
	site_config override as default_app.py.
	"""
	host = (frappe.conf.get("tsi_crm_hosts") or DEFAULT_CRM_HOSTS)[0]
	return f"https://{host}{TSI_CRM_ROUTE}{route}"


# ---------------------------------------------------------------------------
# Recent activity context
# ---------------------------------------------------------------------------

def _record_context(doctype, name):
	"""The last few human touches on a record, trimmed for an LLM prompt.

	A client's history includes the lead it was converted from, the same rule
	api/client_activities.py applies to the client timeline. Only read access
	on the record itself is checked (and on the source lead). This is context
	for a summary, not a timeline a user browses.
	"""
	if not frappe.has_permission(doctype, "read", name):
		return {"recent_activity": [], "last_contacted": None}

	references = [(doctype, name)]
	if doctype == "CRM Organization":
		source = frappe.db.get_value(doctype, name, "tsi_converted_from_lead")
		if source and frappe.db.exists("CRM Lead", source) and frappe.has_permission("CRM Lead", "read", source):
			references.append(("CRM Lead", source))

	items = []
	for ref_doctype, ref_name in references:
		items += _comments(ref_doctype, ref_name)
		items += _communications(ref_doctype, ref_name)
		items += _tasks_and_notes(ref_doctype, ref_name)

	items.sort(key=lambda i: str(i["at"]), reverse=True)
	recent = items[:RECENT_ACTIVITY_LIMIT]
	return {
		"recent_activity": recent,
		"last_contacted": str(recent[0]["at"]) if recent else None,
	}


def _trim(html):
	text = " ".join(unescape(strip_html(html or "")).split())
	return text[:ACTIVITY_TEXT_CHARS] + ("…" if len(text) > ACTIVITY_TEXT_CHARS else "")


def _comments(doctype, name):
	rows = frappe.get_all(
		"Comment",
		filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
		fields=["creation", "owner", "content"],
		order_by="creation desc",
		limit=RECENT_ACTIVITY_LIMIT,
	)
	return [{"type": "comment", "at": r.creation, "by": r.owner, "text": _trim(r.content)} for r in rows]


def _communications(doctype, name):
	rows = frappe.get_all(
		"Communication",
		filters={"reference_doctype": doctype, "reference_name": name},
		fields=["communication_date", "sender", "subject", "content", "sent_or_received"],
		order_by="communication_date desc",
		limit=RECENT_ACTIVITY_LIMIT,
	)
	return [
		{
			"type": "email_" + (r.sent_or_received or "").lower(),
			"at": r.communication_date,
			"by": r.sender,
			"text": _trim(f"{r.subject or ''}: {r.content or ''}"),
		}
		for r in rows
	]


def _tasks_and_notes(doctype, name):
	out = []
	for task in frappe.get_all(
		"CRM Task",
		filters={"reference_doctype": doctype, "reference_docname": name},
		fields=["modified", "assigned_to", "title", "status", "due_date"],
		order_by="modified desc",
		limit=RECENT_ACTIVITY_LIMIT,
	):
		due = f" (due {task.due_date})" if task.due_date else ""
		out.append(
			{"type": "task", "at": task.modified, "by": task.assigned_to, "text": _trim(f"[{task.status}] {task.title}{due}")}
		)
	for note in frappe.get_all(
		"FCRM Note",
		filters={"reference_doctype": doctype, "reference_docname": name},
		fields=["modified", "owner", "title", "content"],
		order_by="modified desc",
		limit=RECENT_ACTIVITY_LIMIT,
	):
		out.append({"type": "note", "at": note.modified, "by": note.owner, "text": _trim(f"{note.title}: {note.content}")})
	return out


# ---------------------------------------------------------------------------
# post_support_summary
# ---------------------------------------------------------------------------

@frappe.whitelist(methods=["POST"])
def post_support_summary(doctype, name, conversation_id, digest_date, subject, rank, summary, action_needed=None):
	"""Write (or refresh) one thread's digest summary as a Comment on the record.

	Idempotent per conversation per digest date: the marker hidden in the
	content finds the comment a previous run wrote, and it is updated in
	place. So a manual rerun of a night's workflow never doubles the timeline.
	"""
	frappe.only_for("System Manager")

	if doctype not in TARGET_DOCTYPES:
		frappe.throw(_("Support summaries can only be posted on {0}").format(", ".join(TARGET_DOCTYPES)))
	if not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} not found").format(doctype, name), frappe.DoesNotExistError)
	frappe.has_permission(doctype, "write", name, throw=True)

	if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(digest_date or "")):
		frappe.throw(_("digest_date must be YYYY-MM-DD"))
	rank = min(max(cint(rank), 1), 5)

	lines = frappe.parse_json(summary) if isinstance(summary, str) and summary.strip().startswith("[") else summary
	if isinstance(lines, str):
		lines = [line for line in lines.splitlines() if line.strip()]
	lines = [str(line).strip() for line in (lines or []) if str(line).strip()][:10]

	marker = MARKER_TEMPLATE.format(conversation_key=_conversation_key(conversation_id), digest_date=digest_date)
	content = _render(marker, subject, rank, lines, action_needed)

	existing = frappe.get_all(
		"Comment",
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"comment_type": "Comment",
			"content": ["like", f"%{marker}%"],
		},
		pluck="name",
		limit=1,
	)
	if existing:
		comment = frappe.get_doc("Comment", existing[0])
		comment.content = content
		comment.save()
		return {"comment": comment.name, "action": "updated"}

	comment = frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Comment",
			"reference_doctype": doctype,
			"reference_name": name,
			"content": content,
		}
	).insert()
	return {"comment": comment.name, "action": "created"}


def _conversation_key(conversation_id):
	"""A short stable key for a Graph conversationId, safe inside a LIKE pattern."""
	if not conversation_id:
		frappe.throw(_("conversation_id is required"))
	return hashlib.sha1(str(conversation_id).encode()).hexdigest()[:16]


def _render(marker, subject, rank, lines, action_needed):
	esc = frappe.utils.escape_html
	items = "".join(f"<li>{esc(line)}</li>" for line in lines)
	action = (
		f"<p><b>{_('Action needed')}:</b> {esc(action_needed)}</p>"
		if action_needed and str(action_needed).strip().lower() != "none"
		else ""
	)
	return (
		f"{marker}<p><b>📧 {_('Support mail')} — {_('Attention')} {rank}/5</b> — {esc(subject or '')}</p>"
		f"<ul>{items}</ul>{action}"
	)
