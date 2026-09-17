# Idempotent seeding of the TSI pipeline onto a site.
#
# Called from both tender_crm/patches/ (which covers an already-migrated site, and
# re-runs on every fresh migrate) and tender_crm/install.py (so a newly installed
# site does not have to wait for the next migrate). Both paths must be safe to run
# any number of times.
#
# Two different kinds of idempotency are in play here, and mixing them up is the
# easy mistake:
#
#   * Creating a missing status is **always** safe, so it happens on every run.
#     A status someone deleted on purpose comes back, which is the intended
#     behaviour — the pipeline is defined by this app, not by the database.
#
#   * Re-ordering and re-colouring statuses that already exist is **not** safe to
#     repeat. crm ships its own defaults with its own positions, and TSI's order
#     interleaves new stages between them; applying that once is a migration,
#     applying it on every migrate would silently undo any reordering the sales
#     manager did on the kanban board afterwards. So it is guarded by a global
#     flag and runs exactly once per site.

import frappe

from tender_crm.pipeline import (
    DEAL_STATUSES,
    LEAD_STATUSES,
    LOST_REASONS,
    TERRITORIES,
    TERRITORY_ROOT,
    TICKET_CATEGORIES,
    TICKET_PRIORITIES,
    TICKET_STATUSES,
    TICKET_TYPES,
)
from tender_crm.sales_units import SALES_UNITS

# Set once the one-shot reordering has been applied to this site. Stored as global
# defaults rather than fields on Tender CRM Settings so that resetting the settings
# single cannot accidentally re-trigger a pipeline rewrite.
#
# Deal and lead pipelines get a flag each. They used to share one, which meant the
# deal seed — which runs first — set the flag before the lead seed had read it, and
# the lead statuses were created but never re-ordered. Two flags, because they are
# two independent one-shot migrations that merely happen to run on the same migrate.
DEAL_ORDERING_APPLIED_FLAG = "tender_crm_deal_pipeline_ordering_applied"
LEAD_ORDERING_APPLIED_FLAG = "tender_crm_lead_pipeline_ordering_applied"

# A distinct one-shot from LEAD_ORDERING_APPLIED_FLAG on purpose: that flag is
# already set on this site (the pipeline was seeded before the TSI design's
# Kanban palette existed), so a change to LEAD_STATUSES' colors would silently
# never reach the database if it rode on the same flag. Recoloring is its own
# independent migration and gets its own flag, per the one-flag-per-concern
# rule this app already learned the hard way once.
LEAD_RECOLOR_APPLIED_FLAG = "tender_crm_lead_status_recolor_applied"

# The support queue's own one-shots. Its own flags, not shared with the deal or
# lead ones and not shared with each other: statuses and priorities are two
# independent orderings, and this app has already been bitten once by a single
# flag being set by whichever seed ran first and read as "done" by the next.
TICKET_STATUS_ORDERING_APPLIED_FLAG = "tender_crm_ticket_status_ordering_applied"
TICKET_PRIORITY_ORDERING_APPLIED_FLAG = "tender_crm_ticket_priority_ordering_applied"


def seed_deal_statuses():
    """Create the TSI deal stages, and order the pipeline once."""
    for position, (status, type_, probability, color) in enumerate(DEAL_STATUSES, start=1):
        if frappe.db.exists("CRM Deal Status", status):
            continue
        frappe.get_doc(
            {
                "doctype": "CRM Deal Status",
                "deal_status": status,
                "type": type_,
                "position": position,
                "probability": probability,
                "color": color,
            }
        ).insert(ignore_permissions=True)

    if frappe.db.get_global(DEAL_ORDERING_APPLIED_FLAG):
        return

    for position, (status, type_, probability, color) in enumerate(DEAL_STATUSES, start=1):
        if not frappe.db.exists("CRM Deal Status", status):
            continue
        # Type is left alone deliberately: it is the one property with meaning
        # beyond presentation (it decides what counts as an open deal), and crm's
        # values for its own statuses already agree with ours.
        frappe.db.set_value(
            "CRM Deal Status",
            status,
            {"position": position, "probability": probability, "color": color},
        )

    frappe.db.set_global(DEAL_ORDERING_APPLIED_FLAG, "1")


def seed_lead_statuses():
    """Create the TSI lead stages, and order them once.

    Reads its own flag, not the deal one — see the note on the flag constants.
    """
    ordering_applied = frappe.db.get_global(LEAD_ORDERING_APPLIED_FLAG)

    for position, (status, type_, color) in enumerate(LEAD_STATUSES, start=1):
        if not frappe.db.exists("CRM Lead Status", status):
            frappe.get_doc(
                {
                    "doctype": "CRM Lead Status",
                    "lead_status": status,
                    "type": type_,
                    "position": position,
                    "color": color,
                }
            ).insert(ignore_permissions=True)
        elif not ordering_applied:
            frappe.db.set_value(
                "CRM Lead Status", status, {"position": position, "color": color}
            )

    if not ordering_applied:
        frappe.db.set_global(LEAD_ORDERING_APPLIED_FLAG, "1")


def recolor_lead_statuses():
    """Apply the TSI design system's Kanban palette to lead statuses, once.

    Only touches `color` — position was already settled by
    LEAD_ORDERING_APPLIED_FLAG and re-applying it here would risk undoing a
    manual re-order the same way sharing one flag would. A status this app
    does not seed (Converted/Unqualified/Junk are unaffected by this design
    pass) or one that does not exist yet is left alone.
    """
    if frappe.db.get_global(LEAD_RECOLOR_APPLIED_FLAG):
        return

    for status, _type, color in LEAD_STATUSES:
        if frappe.db.exists("CRM Lead Status", status):
            frappe.db.set_value("CRM Lead Status", status, "color", color)

    frappe.db.set_global(LEAD_RECOLOR_APPLIED_FLAG, "1")


def seed_lost_reasons():
    """Add TSI's lost reasons alongside the ones crm ships.

    Purely additive — the generic reasons stay, because plenty of TSI deals are
    lost for generic reasons.
    """
    for reason in LOST_REASONS:
        if frappe.db.exists("CRM Lost Reason", reason):
            continue
        frappe.get_doc(
            {"doctype": "CRM Lost Reason", "lost_reason": reason}
        ).insert(ignore_permissions=True)


def seed_territories():
    """Create the territory tree, root first.

    CRM Territory is a nested set. Inserting a child before its parent exists
    raises, and inserting anything at all on a site with no root produces a second
    root — hence the explicit ordering rather than one loop.
    """
    if not frappe.db.exists("CRM Territory", TERRITORY_ROOT):
        frappe.get_doc(
            {
                "doctype": "CRM Territory",
                "territory_name": TERRITORY_ROOT,
                "is_group": 1,
            }
        ).insert(ignore_permissions=True)

    for territory in TERRITORIES:
        if frappe.db.exists("CRM Territory", territory):
            continue
        frappe.get_doc(
            {
                "doctype": "CRM Territory",
                "territory_name": territory,
                "parent_crm_territory": TERRITORY_ROOT,
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)


def seed_sales_units():
    """Create TSI's sales units.

    Creation-only, like seed_lost_reasons() and the territory leaves: a sales
    unit someone deletes on purpose does not come back reordered or
    recoloured, because there is no position or colour on this doctype to fight
    over — so no flag is needed here.
    """
    for unit in SALES_UNITS:
        if frappe.db.exists("TSI Sales Unit", unit):
            continue
        frappe.get_doc({"doctype": "TSI Sales Unit", "unit_name": unit}).insert(
            ignore_permissions=True
        )


def seed_ticket_statuses():
    """Create the support queue's stages, and order them once.

    Same two-speed idempotency as the deal and lead pipelines: a missing status
    is created on every run, but re-ordering and re-colouring statuses that
    already exist would undo whatever the support lead arranged on the kanban
    board, so that half happens exactly once and is then left alone.
    """
    ordering_applied = frappe.db.get_global(TICKET_STATUS_ORDERING_APPLIED_FLAG)

    for position, (status, category, color) in enumerate(TICKET_STATUSES, start=1):
        if not frappe.db.exists("Ticket Status", status):
            frappe.get_doc(
                {
                    "doctype": "Ticket Status",
                    "status": status,
                    "category": category,
                    "position": position,
                    "color": color,
                }
            ).insert(ignore_permissions=True)
        elif not ordering_applied:
            # Category is left alone for the same reason CRM Deal Status' type
            # is: it is the one property with meaning beyond presentation, and
            # a site that has deliberately re-categorised a status should keep
            # that decision.
            frappe.db.set_value(
                "Ticket Status", status, {"position": position, "color": color}
            )

    if not ordering_applied:
        frappe.db.set_global(TICKET_STATUS_ORDERING_APPLIED_FLAG, "1")


def seed_ticket_priorities():
    """Create the priority levels, and order them once.

    Ordering matters more here than anywhere else in this module — a queue
    sorted by priority is unusable if Urgent sorts below Low — but it is still
    a one-shot, because a site is entitled to decide its own order.
    """
    ordering_applied = frappe.db.get_global(TICKET_PRIORITY_ORDERING_APPLIED_FLAG)

    for position, (priority, color) in enumerate(TICKET_PRIORITIES, start=1):
        if not frappe.db.exists("Ticket Priority", priority):
            frappe.get_doc(
                {
                    "doctype": "Ticket Priority",
                    "priority_name": priority,
                    "position": position,
                    "color": color,
                }
            ).insert(ignore_permissions=True)
        elif not ordering_applied:
            frappe.db.set_value(
                "Ticket Priority", priority, {"position": position, "color": color}
            )

    if not ordering_applied:
        frappe.db.set_global(TICKET_PRIORITY_ORDERING_APPLIED_FLAG, "1")


def seed_ticket_types():
    """Create the ticket types.

    Creation-only and unflagged, like the lost reasons: there is no position or
    colour on this doctype for a re-run to fight a human over.
    """
    for type_name in TICKET_TYPES:
        if frappe.db.exists("Ticket Type", type_name):
            continue
        frappe.get_doc(
            {"doctype": "Ticket Type", "type_name": type_name}
        ).insert(ignore_permissions=True)


def seed_ticket_categories():
    """Create the starter product categories.

    Creation-only, like seed_ticket_types(). This list is a guess at TSI's
    product surface and is expected to be edited on the site; nothing in the
    code reads a category by name, so editing it breaks nothing.
    """
    for category_name in TICKET_CATEGORIES:
        if frappe.db.exists("Ticket Category", category_name):
            continue
        frappe.get_doc(
            {"doctype": "Ticket Category", "category_name": category_name}
        ).insert(ignore_permissions=True)


def seed_all():
    """Everything, in dependency order. Used by after_install."""
    seed_deal_statuses()
    seed_lead_statuses()
    recolor_lead_statuses()
    seed_lost_reasons()
    seed_territories()
    seed_sales_units()
    seed_ticket_statuses()
    seed_ticket_priorities()
    seed_ticket_types()
    seed_ticket_categories()
