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
)

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


def seed_all():
    """Everything, in dependency order. Used by after_install."""
    seed_deal_statuses()
    seed_lead_statuses()
    seed_lost_reasons()
    seed_territories()
