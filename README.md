# India e2W Pulse

Data pipeline behind the India e2W Pulse dashboard (https://claude.ai/artifact/Nn9MPPKszgt1Ur5tYEbx3w).

- `vahan_fetch.py OUT_DIR` pulls electric two-wheeler registrations from the public Vahan report view
  (vahan.parivahan.gov.in): two-wheeler categories 2WIC/2WN/2WT, fuels ELECTRIC(BOV) and PURE EV, month-wise,
  by maker and by state, Apr 2021 to today. Writes `monthly.csv`, `oem_monthly.csv`, `states.csv`, `maker_monthly_raw.csv`.
- `validate.py NEW_DIR [OLD_DIR]` runs the data checks and writes `checks.csv`. Exit code 1 means a check failed.
- `data/` is the data currently on the dashboard. `data/reconciliation.csv` holds published figures used for cross-checks.
- `dashboard_page.html` is a copy of the dashboard page, for reference.

A daily cloud routine refreshes the data: fetch → validate → commit → upload to the dashboard (only if all checks pass).
