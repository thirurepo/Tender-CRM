# Creates the Support Agent role the ticketing doctypes are permissioned to.
# The doctype JSONs sync fine without it (frappe skips link validation on
# import), but their permission rows apply to nobody until the role exists.
# See tender_crm/setup.py::ensure_support_agent_role.

from tender_crm.setup import ensure_support_agent_role


def execute():
    ensure_support_agent_role()
