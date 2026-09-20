# Territory -> Country -> Currency / Timezone, as data.
#
# One source of truth shared by setup.py (creates the fields / installs the
# script on an existing site) and fixtures/custom_field.json + hooks.py (carry
# them to a new one) — the same shape as client_import_schema.py.
#
# Behaviour: crm_overrides/territory_geo.py (server rules) and the form script
# below (interactive dropdowns in the /tsi-crm SPA).

TERRITORY_GEO_FIELDS = [
    {
        # The countries a territory covers. Sits on the stock CRM Territory (vendor
        # doctype) as a Custom Field, so crm is not edited. Editable in desk only;
        # the SPA has no territory screen.
        "dt": "CRM Territory",
        "fieldname": "tsi_countries",
        "label": "Countries",
        "fieldtype": "Table",
        "options": "CRM Territory Country",
        "insert_after": "territory_manager",
        "description": "Countries this territory covers. Organizations in it choose from these.",
    },
    {
        # Data, not Select: the valid list depends on the chosen country, so the SPA
        # form script turns it into a Select at runtime and the server validates it
        # against the country's zones (crm_overrides/territory_geo.py).
        "dt": "CRM Organization",
        "fieldname": "tsi_timezone",
        "label": "Timezone",
        "fieldtype": "Data",
        "insert_after": "tsi_country",
        "description": "IANA timezone of the organization. Defaults to the country's first zone.",
    },
]

# Fields added to the CRM Organization Side Panel so the country/currency/timezone
# are visible and editable on the client page. Existing sites get them through
# setup.ensure_organization_geo_side_panel().
ORGANIZATION_GEO_SIDE_PANEL_FIELDS = ["territory", "tsi_country", "currency", "tsi_timezone"]

# CRM Organization form, client side. A second class beside the existing
# "TSI Client Country/State Filter" script (crm supports several controllers per
# doctype), so that script — and its tsi_state filtering — is left untouched.
#
#   territory changed -> 0 countries configured: leave Country unrestricted
#                        1 country: set it; >1: limit the Country dropdown to them
#   country changed   -> currency follows the country (still editable);
#                        timezone becomes a dropdown of the country's zones and
#                        defaults to the first when the current one is not in it.
# onLoad/onRender only re-apply the filters/options; they never overwrite values.
TERRITORY_GEO_FORM_SCRIPT = """\
class CRMOrganization {
  onLoad() {
    this._applyGeoOptions()
  }
  onRender() {
    this._applyGeoOptions()
  }
  async territory() {
    const rows = await this._territoryRows(this.doc.territory)
    const before = this.doc.tsi_country
    if (rows.length === 1) {
      this.doc.tsi_country = rows[0].country
    } else if (rows.length > 1 && !rows.some((r) => r.country === this.doc.tsi_country)) {
      this.doc.tsi_country = null
    }
    if (this.doc.tsi_country !== before) this.doc.tsi_state = null
    await this._applyGeoOptions()
    await this._countryChanged()
  }
  async tsi_country() {
    this.doc.tsi_state = null
    await this._countryChanged()
  }
  async _countryChanged() {
    const country = this.doc.tsi_country
    if (!country) {
      this.doc.tsi_timezone = null
      return this._applyGeoOptions()
    }
    const geo = await this._countryGeo(country)
    const row = (await this._territoryRows(this.doc.territory)).find((r) => r.country === country)
    const currency = (row && row.currency) || geo.currency
    if (currency) this.doc.currency = currency
    if (!geo.timezones.includes(this.doc.tsi_timezone)) {
      this.doc.tsi_timezone = geo.timezones[0] || null
    }
    await this._applyGeoOptions()
  }
  async _applyGeoOptions() {
    const rows = await this._territoryRows(this.doc.territory)
    this.setFieldProperty('tsi_country', 'link_filters', rows.length > 1
      ? JSON.stringify({ name: ['in', rows.map((r) => r.country)] })
      : '')
    const zones = this.doc.tsi_country ? (await this._countryGeo(this.doc.tsi_country)).timezones : []
    this.setFieldProperty('tsi_timezone', 'fieldtype', 'Select')
    this.setFieldProperty('tsi_timezone', 'options', zones.join('\\n'))
  }
  _cached(key, method, params) {
    this._geoCache = this._geoCache || {}
    if (!this._geoCache[key]) {
      this._geoCache[key] = this.call(method, params).then((r) => (r && r.message !== undefined ? r.message : r))
    }
    return this._geoCache[key]
  }
  async _territoryRows(territory) {
    if (!territory) return []
    const r = await this._cached('t:' + territory, 'tender_crm.api.territory_geo.get_territory_geo', { territory })
    return Array.isArray(r) ? r : []
  }
  async _countryGeo(country) {
    const r = await this._cached('c:' + country, 'tender_crm.api.territory_geo.get_country_geo', { country })
    return { currency: (r && r.currency) || null, timezones: (r && r.timezones) || [] }
  }
}
"""

TERRITORY_GEO_FORM_SCRIPTS = [
    {
        "name": "TSI Client Territory Geo",
        "dt": "CRM Organization",
        "view": "Form",
        "enabled": 1,
        "script": TERRITORY_GEO_FORM_SCRIPT,
    },
]
