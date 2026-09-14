# Idempotent seeding of the legacy TSI CRM's master data (users, territories,
# lead sources/statuses, client statuses, states) from the CSVs Thiru exported
# before retiring the old PHP CRM.
#
# Deliberately NOT wired into install.py or patches.txt. Every function here
# is idempotent and safe to run any number of times, but the data itself is
# one-time historical data — TSI's own users, territories and legacy status
# names — not application schema, so it does not belong in the automatic,
# unattended setup path every `bench migrate` runs. It is called exactly once,
# by tender_crm/Import_crm_data/import_leads.py, as one step of the
# single one-off legacy import process (see that file's header). The schema
# these functions' output depends on (the disabled flag, tsi_* fields, the
# CRM Form Script) is the opposite case — permanent app capability — and stays
# in setup.py/patches.txt/install.py as usual.
#
# The CSVs themselves (tender_crm/Import_crm_data/*.csv) are
# deliberately NOT committed to git — they are a one-time export of TSI's own
# customer data, not application code. That means every function below fails
# loudly (a clear FileNotFoundError-derived message, not a silent no-op) if
# those files are missing, rather than leaving a site half-seeded with no
# indication why.

import csv
from pathlib import Path

import frappe

GLOBAL_ACCESS_ROLE = "TSI CRM Global Access"


def ensure_legacy_users():
    """Create the legacy CRM's sales users, and grant their roles.

    User.csv groups roles under a named row: a user with several roles is one
    row carrying the first role, followed by blank-everything-but-Role rows for
    each additional one (e.g. mrtender@tendersoftware.com carries Sales
    Manager, Sales User and TSI CRM Global Access across three rows). Read
    positionally with csv.reader, not DictReader — the file's header repeats
    "ID" and has three unnamed columns, which DictReader would silently
    collapse, losing data.

    Must run before ensure_legacy_territories(): territory_manager is a Link
    to User, so managers must exist before a territory can point at one.
    """
    _ensure_role(GLOBAL_ACCESS_ROLE)

    with _open_csv("User.csv") as f:
        reader = csv.reader(f)
        next(reader, None)  # header row

        current_email = None
        for row in reader:
            if len(row) < 8:
                continue

            email = row[1].strip()
            first_name = row[2].strip()
            last_name = row[3].strip()
            role = row[7].strip()

            if email:
                current_email = email
                if not frappe.db.exists("User", email):
                    frappe.get_doc(
                        {
                            "doctype": "User",
                            "email": email,
                            "first_name": first_name or email,
                            "last_name": last_name,
                            "send_welcome_email": 0,
                        }
                    ).insert(ignore_permissions=True)

            if not current_email or not role:
                continue

            user = frappe.get_doc("User", current_email)
            if role not in [r.role for r in user.roles]:
                user.add_roles(role)


def ensure_legacy_lead_sources():
    """Retire crm's stock CRM Lead Sources in favour of the legacy CRM's list.

    Data-driven rather than a hardcoded name list: any source that exists on
    this site right now and is not one of the legacy CSV's *enabled* rows gets
    disabled=1 — nothing that already references it breaks, it just stops
    being offered for new leads (see the CRM Form Script in
    lead_import_schema.py, which is what actually filters the picker).
    Only the CSV's enabled rows are created/enabled; its disabled rows are
    historical noise from the legacy export and are not worth recreating.
    """
    rows = _read_csv("CRM Lead Source.csv")
    enabled_names = {
        row["Source Name"].strip() for row in rows if row["Disabled"].strip() == "0"
    }

    for name in frappe.get_all("CRM Lead Source", pluck="name"):
        if name in enabled_names:
            continue
        if not frappe.db.get_value("CRM Lead Source", name, "disabled"):
            frappe.db.set_value("CRM Lead Source", name, "disabled", 1)

    for name in enabled_names:
        if frappe.db.exists("CRM Lead Source", name):
            if frappe.db.get_value("CRM Lead Source", name, "disabled"):
                frappe.db.set_value("CRM Lead Source", name, "disabled", 0)
            continue
        frappe.get_doc(
            {"doctype": "CRM Lead Source", "source_name": name, "disabled": 0}
        ).insert(ignore_permissions=True)


def ensure_legacy_lead_statuses():
    """Create the legacy CRM's lead statuses, all enabled.

    Retiring this app's own TSI pipeline statuses in favour of these is a
    separate, deliberately distinct step — see
    disable_tsi_pipeline_lead_statuses() below.
    """
    for row in _read_csv("CRM Lead Status.csv"):
        name = row["Status"].strip()
        if frappe.db.exists("CRM Lead Status", name):
            continue
        frappe.get_doc(
            {
                "doctype": "CRM Lead Status",
                "lead_status": name,
                "type": row["Type"].strip(),
                "color": row["Color"].strip(),
                "position": int(row["Position"].strip()),
                "disabled": 0,
            }
        ).insert(ignore_permissions=True)


def disable_tsi_pipeline_lead_statuses():
    """Disable the 9 lead statuses seed.py's seed_lead_statuses() created.

    Kept separate from ensure_legacy_lead_statuses() above on purpose: that
    function creates the legacy CRM's own statuses, a concern this module
    owns outright; this one edits data pipeline.py/seed.py own, for a
    different reason (retiring TSI's original pipeline once the legacy CRM's
    statuses have taken its place). Mixing the two into one loop would bury
    that distinction.
    """
    from tender_crm.pipeline import LEAD_STATUSES

    for status, *_rest in LEAD_STATUSES:
        if not frappe.db.exists("CRM Lead Status", status):
            continue
        if not frappe.db.get_value("CRM Lead Status", status, "disabled"):
            frappe.db.set_value("CRM Lead Status", status, "disabled", 1)


def ensure_legacy_territories():
    """Create the legacy CRM's territories, and point each at its manager.

    Must run after ensure_legacy_users(): territory_manager is a Link to User.

    "International" already exists on this site — seed.py's own
    seed_territories() created it as one of TSI's own zones (see
    pipeline.py's TERRITORIES). That name collision is a genuine reuse, not a
    duplicate to work around: this function updates its territory_manager in
    place rather than inserting a second record, and leaves its position in
    the existing tree (child of All Territories) exactly as seed.py put it —
    the legacy CSV's flat, no-parent shape is an artifact of a system with no
    tree at all, not a real structure to reproduce here. The guard on
    territory_manager being unset first means a value an administrator has
    since changed by hand is never silently overwritten by a re-run.
    """
    from tender_crm.pipeline import TERRITORY_ROOT

    for row in _read_csv("CRM Territory.csv"):
        name = row["Territory Name"].strip()
        manager = row["Territory Manager"].strip()

        if frappe.db.exists("CRM Territory", name):
            if manager and not frappe.db.get_value(
                "CRM Territory", name, "territory_manager"
            ):
                frappe.db.set_value("CRM Territory", name, "territory_manager", manager)
            continue

        frappe.get_doc(
            {
                "doctype": "CRM Territory",
                "territory_name": name,
                "parent_crm_territory": TERRITORY_ROOT,
                "is_group": 0,
                "territory_manager": manager or None,
            }
        ).insert(ignore_permissions=True)


def ensure_legacy_country_states():
    """Seed TSI Country State from the legacy CRM's TSI State.csv.

    No dependency beyond the DocType existing, which ordinary doctype sync
    covers during migrate. Dedupes on (state_name, country) itself, since the
    DocType declares no composite-unique constraint.
    """
    for row in _read_csv("TSI State.csv"):
        state_name = row["State Name"].strip()
        country = row["Country"].strip()
        if frappe.db.exists(
            "TSI Country State", {"state_name": state_name, "country": country}
        ):
            continue
        frappe.get_doc(
            {"doctype": "TSI Country State", "state_name": state_name, "country": country}
        ).insert(ignore_permissions=True)


def ensure_legacy_client_statuses(rows=None):
    """Create the legacy CRM's client statuses (account health, not pipeline).

    Unlike CRM Lead Status, there is no separate master CSV for this — the
    only source is the Client Status column of CRM_Client_Import.csv itself,
    so the distinct values are read from there (or passed in, so the import
    script that already has the rows loaded doesn't read the file twice).
    """
    if rows is None:
        rows = _read_csv("CRM_Client_Import.csv")

    seen = set()
    for row in rows:
        status = (row.get("Client Status") or "").strip()
        if not status or status in seen:
            continue
        seen.add(status)
        if frappe.db.exists("Tender Client Status", status):
            continue
        frappe.get_doc(
            {"doctype": "Tender Client Status", "client_status": status}
        ).insert(ignore_permissions=True)


def seed_legacy_import_masters():
    """Everything above, in dependency order. Used by install.py."""
    ensure_legacy_users()
    ensure_legacy_lead_sources()
    ensure_legacy_lead_statuses()
    disable_tsi_pipeline_lead_statuses()
    ensure_legacy_territories()
    ensure_legacy_country_states()


# --------------------------------------------------------------------------- #
# CSV plumbing
# --------------------------------------------------------------------------- #


def _import_data_dir():
    """Path to the folder holding the legacy CRM's CSVs — a sibling of this
    file, not of the doctype/ subpackage (easy to get wrong: this app's
    package layout doubles "tender_crm" one level down for its DocTypes).

    Deliberately not frappe.get_app_path("tender_crm", "Import_crm_data") —
    that scrubs every joined segment (lowercases, snake-cases), which mangles
    the folder's actual mixed-case name into "import_crm_data" and never
    finds it. Computed relative to this file instead, since it is a fixed,
    known-good relationship regardless of scrub()'s behaviour.
    """
    return Path(__file__).resolve().parent / "Import_crm_data"


def _open_csv(filename):
    path = _import_data_dir() / filename
    if not path.exists():
        frappe.throw(
            f"Tender CRM: legacy import file {filename!r} not found at {path}. "
            "These CSVs are not committed to git — copy them onto this bench at "
            "that path before running the legacy master seeding."
        )
    # cp1252, not utf-8: these are Excel exports from the legacy CRM's Windows
    # tooling. Confirmed by CRM_Lead_Import.csv's byte 0x97 (a cp1252 em-dash,
    # invalid as a UTF-8 start byte) inside a Lost Notes value.
    return open(path, encoding="cp1252", newline="")


def _read_csv(filename):
    with _open_csv(filename) as f:
        return list(csv.DictReader(f))


def _ensure_role(role_name):
    if frappe.db.exists("Role", role_name):
        return
    frappe.get_doc({"doctype": "Role", "role_name": role_name}).insert(
        ignore_permissions=True
    )
