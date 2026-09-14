# TSI's sales units, as data. Kept separate from pipeline.py because it is not
# part of the tender pipeline that module describes — it is the team-territory
# axis the Tender CRM design's Leads/Clients screens filter and group by,
# distinct from CRM Territory (geography).
#
# Only "AU/NZ" appears anywhere in the design; the rest of TSI's actual sales
# units are not yet known here. Add to this list once they are confirmed —
# do not invent siblings for a Link field that will show up in a dropdown.
SALES_UNITS = [
    "AU/NZ",
]
