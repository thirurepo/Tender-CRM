# The legacy TSI CRM's lead-comment identity fields, as data — same role as
# lead_import_schema.py / client_import_schema.py / contact_import_schema.py,
# but for core `Comment` instead of a Tender CRM or crm doctype. One source of
# truth shared by setup.py (which creates the fields) and
# fixtures/custom_field.json (which carries them to a new site).
#
# Comment doctype's tsi_note_type field (setup.py's CLIENT_LEAD_FIELDS) already
# exists; these two are additive, for
# tender_crm/Import_crm_data/import_lead_comments.py and
# import_lead_comment_replies.py specifically.

COMMENT_IMPORT_FIELDS = [
    {
        "fieldname": "tsi_legacy_comment_id",
        "label": "Legacy Comment ID",
        "fieldtype": "Data",
        "unique": 1,
        "read_only": 1,
        "no_copy": 1,
        "insert_after": "tsi_note_type",
        "description": (
            "Deterministic key for a legacy CRM comment/reply row — "
            "'<lead id>:<comment id>' for a comment, "
            "'<lead id>:<comment id>:reply:<reply id>' for a reply. Lets both "
            "import scripts re-run without creating duplicates, and is how "
            "import_lead_comment_replies.py finds a reply's parent comment."
        ),
    },
    {
        "fieldname": "tsi_reply_to_comment",
        "label": "Reply To",
        "fieldtype": "Link",
        "options": "Comment",
        "insert_after": "tsi_legacy_comment_id",
        "description": (
            "Set only on rows imported from the legacy CRM's replies CSV — "
            "the parent Comment this one replied to. The CRM UI does not "
            "render nested threads; this preserves the relationship as data."
        ),
    },
]
