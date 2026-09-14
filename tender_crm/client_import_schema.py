# The legacy TSI CRM's client fields, as data — mirrors lead_import_schema.py's
# role for CRM Organization instead of CRM Lead. One source of truth shared by
# setup.py (which creates the fields) and fixtures/custom_field.json (which
# carries them to a new site).
#
# Field-mapping source: CRM_Client_Import.csv's own header. Unlike the lead
# CSV, several columns are already named in this app's tsi_* convention
# (tsi_contact_first_name etc.) — a strong signal they were staged to become
# custom fields with exactly those names, so they are used verbatim rather
# than re-derived. Fields already covered by a native CRM Organization field
# (organization_name, website, territory) are reused as-is and are not here.

CRM_ORGANIZATION_FIELDS = [
    {
        "fieldname": "tsi_contact_first_name",
        "label": "Contact First Name",
        "fieldtype": "Data",
        "insert_after": "organization_name",
    },
    {
        "fieldname": "tsi_contact_last_name",
        "label": "Contact Last Name",
        "fieldtype": "Data",
        "insert_after": "tsi_contact_first_name",
    },
    {
        "fieldname": "tsi_contact_email",
        "label": "Contact Email",
        "fieldtype": "Data",
        "options": "Email",
        "insert_after": "tsi_contact_last_name",
    },
    {
        "fieldname": "tsi_contact_mobile",
        "label": "Contact Mobile",
        "fieldtype": "Data",
        "options": "Phone",
        "insert_after": "tsi_contact_email",
    },
    {
        "fieldname": "tsi_contact_phone",
        "label": "Contact Phone",
        "fieldtype": "Data",
        "options": "Phone",
        "insert_after": "tsi_contact_mobile",
    },
    {
        "fieldname": "tsi_contact_skype",
        "label": "Contact Skype",
        "fieldtype": "Data",
        "insert_after": "tsi_contact_phone",
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
        "description": "Filtered to the selected Country by a CRM Form Script — see FORM_SCRIPTS below. Same TSI Country State master CRM Lead uses.",
    },
    {
        "fieldname": "tsi_client_status",
        "label": "Client Status",
        "fieldtype": "Link",
        "options": "Tender Client Status",
        "insert_after": "tsi_state",
        "description": "Account health (Active/Inactive/Lost/etc.), distinct from any deal's pipeline status.",
    },
    {
        "fieldname": "tsi_account_owner",
        "label": "Account Owner",
        "fieldtype": "Link",
        "options": "User",
        "insert_after": "tsi_client_status",
    },
    {
        "fieldname": "tsi_added_date",
        "label": "Added Date",
        "fieldtype": "Date",
        "insert_after": "tsi_account_owner",
        "description": "Date this client was first entered in the legacy CRM.",
    },
    {
        "fieldname": "tsi_converted_from_lead",
        "label": "Converted From Lead",
        "fieldtype": "Link",
        "options": "CRM Lead",
        "insert_after": "tsi_added_date",
        "description": "Set only when the legacy CRM's Lead Name resolved to exactly one imported CRM Lead — see tsi_legacy_lead_name/tsi_legacy_lead_company for the raw values when it did not.",
    },
    {
        "fieldname": "tsi_legacy_lead_name",
        "label": "Legacy Lead Name",
        "fieldtype": "Data",
        "read_only": 1,
        "insert_after": "tsi_converted_from_lead",
    },
    {
        "fieldname": "tsi_legacy_lead_company",
        "label": "Legacy Lead Company",
        "fieldtype": "Data",
        "read_only": 1,
        "insert_after": "tsi_legacy_lead_name",
    },
    {
        "fieldname": "tsi_linkedin_sent",
        "label": "LinkedIn Sent",
        "fieldtype": "Check",
        "insert_after": "tsi_legacy_lead_company",
    },
    {
        "fieldname": "tsi_30_day_report",
        "label": "Include in 30-Day Report",
        "fieldtype": "Check",
        "insert_after": "tsi_linkedin_sent",
    },
    {
        "fieldname": "tsi_60_day_report",
        "label": "Include in 60-Day Report",
        "fieldtype": "Check",
        "insert_after": "tsi_30_day_report",
    },
    {
        "fieldname": "tsi_90_day_report",
        "label": "Include in 90-Day Report",
        "fieldtype": "Check",
        "insert_after": "tsi_60_day_report",
    },
    {
        "fieldname": "tsi_chronic_nonresponder",
        "label": "Chronic Nonresponder",
        "fieldtype": "Check",
        "insert_after": "tsi_90_day_report",
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
    {
        "fieldname": "tsi_low_value_client",
        "label": "Low Value Client",
        "fieldtype": "Check",
        "insert_after": "tsi_time_waster",
    },
    {
        "fieldname": "tsi_cost_code",
        "label": "Cost Code",
        "fieldtype": "Data",
        "insert_after": "tsi_low_value_client",
        "description": "Legacy accounting reference. Plain text — not linked to any ERPNext master, since none is confirmed to match yet.",
    },
    {
        "fieldname": "tsi_tax_code_name",
        "label": "Tax Code Name",
        "fieldtype": "Data",
        "insert_after": "tsi_cost_code",
        "description": "Legacy accounting reference. Plain text — not linked to any ERPNext master, since none is confirmed to match yet.",
    },
    {
        "fieldname": "tsi_sales_term_name",
        "label": "Sales Term Name",
        "fieldtype": "Data",
        "insert_after": "tsi_tax_code_name",
        "description": "Legacy accounting reference. Plain text — not linked to any ERPNext master, since none is confirmed to match yet.",
    },
    {
        "fieldname": "tsi_exact_accounting_name",
        "label": "Exact Accounting Name",
        "fieldtype": "Data",
        "insert_after": "tsi_sales_term_name",
        "description": "Legacy accounting reference. Plain text — not linked to any ERPNext master, since none is confirmed to match yet.",
    },
    {
        "fieldname": "tsi_invoice_projects_separately",
        "label": "Invoice Projects Separately",
        "fieldtype": "Check",
        "insert_after": "tsi_exact_accounting_name",
    },
    {
        "fieldname": "tsi_accept_credit_card",
        "label": "Accept Credit Card",
        "fieldtype": "Check",
        "insert_after": "tsi_invoice_projects_separately",
    },
]

# CRM Organization's Vue form, client side. Same tsi_state/tsi_country
# filtering CRM Lead's form script does — see lead_import_schema.py for why a
# Form Script (not the built-in Address.state filter) is required.
CLIENT_FORM_SCRIPT = """\
class CRMOrganization {
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
  }
}
"""

CLIENT_FORM_SCRIPTS = [
    {
        "name": "TSI Client Country/State Filter",
        "dt": "CRM Organization",
        "view": "Form",
        "enabled": 1,
        "script": CLIENT_FORM_SCRIPT,
    },
]
