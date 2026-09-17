# The legacy TSI CRM's client-contact fields, as data — mirrors
# lead_import_schema.py / client_import_schema.py's role, but for the standard
# Frappe `Contact` doctype instead of a Tender CRM one. One source of truth
# shared by setup.py (which creates the fields) and fixtures/custom_field.json
# (which carries them to a new site).
#
# Field-mapping source: CRM_Client_Contacts_Import.csv's own header. Fields
# already covered by a native Contact field (first_name, last_name,
# designation <- Position, is_primary_contact <- Is Primary, company_name <-
# Company, as plain text) are reused as-is and are not here. Email/mobile/phone
# are set through Contact's own child tables (email_ids/phone_nos) by the
# import script, not through a custom field.

CRM_CONTACT_FIELDS = [
    {
        "fieldname": "tsi_organization",
        "label": "Organization",
        "fieldtype": "Link",
        "options": "CRM Organization",
        "insert_after": "company_name",
        "description": (
            "Resolved from the legacy CSV's Company column against an "
            "already-imported CRM Organization — see "
            "tender_crm/Import_crm_data/import_client_contacts.py."
        ),
    },
    {
        "fieldname": "tsi_legacy_primary_email",
        "label": "Legacy Primary Email",
        "fieldtype": "Data",
        "options": "Email",
        "read_only": 1,
        "insert_after": "tsi_organization",
        "description": (
            "The legacy CRM's separate 'Primary Email' column — differs from "
            "this contact's own email on part of the source data, and looks "
            "like a legacy account/login grouping key shared across people at "
            "the same org rather than this person's own address, so it is "
            "kept as a raw reference rather than guessed at."
        ),
    },
    {
        "fieldname": "tsi_reporting_contact",
        "label": "Reporting Contact",
        "fieldtype": "Check",
        "insert_after": "tsi_legacy_primary_email",
    },
    {
        "fieldname": "tsi_billing_contact",
        "label": "Billing Contact",
        "fieldtype": "Check",
        "insert_after": "tsi_reporting_contact",
    },
    {
        "fieldname": "tsi_holiday_email_only",
        "label": "Holiday Email Only",
        "fieldtype": "Check",
        "insert_after": "tsi_billing_contact",
    },
    {
        "fieldname": "tsi_is_rmr",
        "label": "Is RMR",
        "fieldtype": "Check",
        "insert_after": "tsi_holiday_email_only",
    },
    {
        "fieldname": "tsi_rmr_added_by",
        "label": "RMR Added By",
        "fieldtype": "Link",
        "options": "User",
        "insert_after": "tsi_is_rmr",
    },
    {
        "fieldname": "tsi_linkedin_sent",
        "label": "LinkedIn Sent",
        "fieldtype": "Check",
        "insert_after": "tsi_rmr_added_by",
    },
    {
        "fieldname": "tsi_status",
        "label": "Status",
        "fieldtype": "Check",
        "default": "1",
        "insert_after": "tsi_linkedin_sent",
        "description": "Legacy CRM's own enabled/active flag for this contact.",
    },
    {
        "fieldname": "tsi_approve_status",
        "label": "Approve Status",
        "fieldtype": "Check",
        "insert_after": "tsi_status",
    },
    {
        "fieldname": "tsi_legacy_created_by",
        "label": "Legacy Created By",
        "fieldtype": "Link",
        "options": "User",
        "insert_after": "tsi_approve_status",
    },
    {
        "fieldname": "tsi_added_date",
        "label": "Added Date",
        "fieldtype": "Date",
        "insert_after": "tsi_legacy_created_by",
        "description": "Date this contact was first entered in the legacy CRM.",
    },
]
