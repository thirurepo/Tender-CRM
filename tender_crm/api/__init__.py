# Tender CRM's whitelisted read endpoints.
#
# The distinction from `crm_overrides/` is the point of this package existing:
# crm_overrides holds everything that *changes* the behaviour of Frappe CRM or
# ERPNext, and is wired from hooks.py. Nothing here changes anything — these are
# additive endpoints that read, called by the tsi-crm frontend for screens the
# vendor app has no equivalent of. See README.md.
