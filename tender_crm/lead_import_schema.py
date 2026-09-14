# The legacy TSI CRM's lead fields, as data — one source of truth shared by
# setup.py (which creates them) and fixtures/custom_field.json (which carries
# them to a new site), matching how pipeline.py backs seed.py.
#
# Field-mapping source: the legacy PHP CRM's own field list, worked out by hand
# against a CSV export (CRM_Lead_Field_Mapping.docx) before this module was
# written. Fields already covered by a native CRM Lead field (name, email,
# mobile_no, phone, organization, website, status, lost_reason, lost_notes,
# source, lead_owner, territory, converted) are reused as-is and are not here.

CRM_LEAD_FIELDS = [
    {
        "fieldname": "tsi_skype",
        "label": "Skype",
        "fieldtype": "Data",
        "insert_after": "phone",
        "description": "Legacy CRM field with no native equivalent on CRM Lead.",
    },
    {
        "fieldname": "tsi_country",
        "label": "Country",
        "fieldtype": "Link",
        "options": "Country",
        "insert_after": "territory",
    },
    {
        "fieldname": "tsi_state",
        "label": "State",
        "fieldtype": "Link",
        "options": "TSI Country State",
        "insert_after": "tsi_country",
        "description": (
            "Filtered to the selected Country by a CRM Form Script — see "
            "FORM_SCRIPTS below."
        ),
    },
    {
        "fieldname": "tsi_legacy_id",
        "label": "Legacy CRM ID",
        "fieldtype": "Data",
        "unique": 1,
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "naming_series",
        "description": (
            "Deterministic key computed from the legacy CSV row (name, email, "
            "added date). Lets the import script re-run without creating "
            "duplicate leads — see tender_crm/Import_crm_data/import_leads.py."
        ),
    },
    {
        "fieldname": "tsi_added_date",
        "label": "Added Date",
        "fieldtype": "Date",
        "insert_after": "annual_revenue",
        "description": "Date this lead was first entered in the legacy CRM.",
    },
    {
        "fieldname": "tsi_converted_date",
        "label": "Converted Date",
        "fieldtype": "Date",
        "read_only": 1,
        "insert_after": "converted",
        "description": (
            "Stamped automatically when Converted is checked — see "
            "crm_overrides/lead_import.py. Set directly from the legacy CSV "
            "for imported leads, and never overwritten by the automatic stamp "
            "for those (doc.flags.tsi_importing)."
        ),
    },
    {
        "fieldname": "tsi_last_status_change",
        "label": "Last Status Change",
        "fieldtype": "Date",
        "read_only": 1,
        "insert_after": "tsi_converted_date",
        "description": (
            "Stamped automatically whenever Status changes — see "
            "crm_overrides/lead_import.py. Set directly from the legacy CSV "
            "for imported leads, and never overwritten by the automatic stamp "
            "for those (doc.flags.tsi_importing)."
        ),
    },
    {
        "fieldname": "tsi_contacted_today",
        "label": "Contacted Today",
        "fieldtype": "Check",
        "insert_after": "tsi_last_status_change",
    },
    {
        "fieldname": "tsi_linkedin_sent",
        "label": "LinkedIn Sent",
        "fieldtype": "Check",
        "insert_after": "tsi_contacted_today",
    },
    {
        "fieldname": "tsi_chronic_nonresponder",
        "label": "Chronic Nonresponder",
        "fieldtype": "Check",
        "insert_after": "tsi_linkedin_sent",
    },
    {
        "fieldname": "tsi_weak_lead",
        "label": "Weak Lead",
        "fieldtype": "Check",
        "insert_after": "tsi_chronic_nonresponder",
    },
    {
        "fieldname": "tsi_difficult_personality",
        "label": "Difficult Personality",
        "fieldtype": "Check",
        "insert_after": "tsi_weak_lead",
    },
    {
        "fieldname": "tsi_time_waster",
        "label": "Time Waster",
        "fieldtype": "Check",
        "insert_after": "tsi_difficult_personality",
    },
]

# Neither CRM Lead Status nor CRM Lead Source has a "disabled" concept
# upstream. The legacy import needs one so TSI's own pipeline statuses and
# crm's stock sources can be retired in favour of the legacy set without
# deleting a value any existing lead might still reference — see
# legacy_masters.py.
DISABLED_FLAG_FIELDS = [
    {
        "dt": "CRM Lead Status",
        "fieldname": "disabled",
        "label": "Disabled",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "color",
        "description": "Hides this status from new-record pickers without deleting it.",
    },
    {
        "dt": "CRM Lead Source",
        "fieldname": "disabled",
        "label": "Disabled",
        "fieldtype": "Check",
        "default": "0",
        "insert_after": "details",
        "description": "Hides this source from new-record pickers without deleting it.",
    },
]

# CRM Lead's Vue form, client side. Two independent concerns share one script
# because crm's own CRM Form Script rows for CRM Deal (Create Quotation,
# Forecasting, Product Details) already prove multiple scripts on the same
# dt+view run additively — no need to fight that, but no need for a second
# script here either.
#
#   * tsi_state's choices are scoped to whichever Country is selected, via
#     setFieldProperty(..., "link_filters", ...), which is the mechanism crm's
#     own Address.state filtering uses (fieldTransforms.js) — that one is
#     hardcoded to Address, so it does not pick up a custom field on CRM Lead.
#   * status/source are filtered to the not-yet-disabled set, so the
#     DISABLED_FLAG_FIELDS flag actually hides something in the UI rather than
#     just sitting inert in the database.
LEAD_FORM_SCRIPT = """\
class CRMLead {
  onLoad() {
    this._applyFilters()
  }
  onRender() {
    this._applyFilters()
  }
  tsi_country() {
    this.doc.tsi_state = null
    this._applyFilters()
  }
  _applyFilters() {
    this.setFieldProperty('tsi_state', 'link_filters', JSON.stringify({
      country: this.doc.tsi_country || '__none__',
    }))
    this.setFieldProperty('status', 'link_filters', JSON.stringify({ disabled: 0 }))
    this.setFieldProperty('source', 'link_filters', JSON.stringify({ disabled: 0 }))
  }
}
"""

FORM_SCRIPTS = [
    {
        "name": "TSI Lead Country, State and Master Filters",
        "dt": "CRM Lead",
        "view": "Form",
        "enabled": 1,
        "script": LEAD_FORM_SCRIPT,
    },
]
