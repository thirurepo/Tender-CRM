# Account-health status for a CRM Organization (Active/Inactive/Lost/etc.),
# distinct from CRM Deal Status (pipeline stage) — a client can be Active
# with no open deal, or Inactive with one still technically open. Seeded from
# the legacy CRM's CRM_Client_Import.csv (no separate master file exists for
# this one, unlike CRM Lead Status) — see legacy_masters.py.

from frappe.model.document import Document


class TenderClientStatus(Document):
    pass
