# integrations

Whitelisted endpoints that **external automations** call, meaning n8n at
autoflow.tendersoftware.in, logged in as `autoflow@tendersoftware.in`.

The package exists because the other two don't fit:

- `api/` is read-only endpoints for the tsi-crm frontend. By design, nothing
  there changes anything.
- `crm_overrides/` changes how Frappe CRM behaves and is wired from `hooks.py`.

The endpoints here *may* write, but only records an automation is meant to
touch, and never through `ignore_permissions`. Every endpoint is System Manager
only (`frappe.only_for`), and every record it writes is checked with
`has_permission`. The record's owner is the API user, so the timeline says the
automation wrote it.

| File | Endpoints | Called from |
| --- | --- | --- |
| `support_mail.py` | `match_contacts(emails)`: the lead/client a support thread's external addresses belong to, plus its last few touches as LLM context. `post_support_summary(...)`: writes ONE Comment per lead/client per day: the AI summary of all that client's support mail, its highest 1–5 attention rank, and the threads it covers. Idempotent per record per day. | n8n "TSIERP - Support Mailbox Digest" (nightly, 23:00 IST). The mailbox is read by tsiconnect's `integrations/support_mailbox.py`. |
