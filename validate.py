"""Check a fresh Vahan pull before it replaces the dashboard's data.

Usage: python3 validate.py NEW_DIR [OLD_DIR]
Writes NEW_DIR/checks.csv (one row per check) and exits 1 if any check FAILS.
WARN rows are reported but do not block the upload.
"""
import csv, datetime, sys

new = sys.argv[1]
old = sys.argv[2] if len(sys.argv) > 2 else None
read = lambda d, f: list(csv.DictReader(open(f"{d}/{f}")))
checks = []
def add(name, status, detail):
    checks.append({"check": name, "status": status, "detail": detail})

monthly = read(new, "monthly.csv")
oem = read(new, "oem_monthly.csv")
states = read(new, "states.csv")
full = [r for r in monthly if r["partial"] != "1"]
by_month = {r["month"]: r for r in monthly}

# 1. every month from Apr 2021 to the latest is present
months = sorted(by_month)
y, m = 2021, 4
expected = []
while f"{y}-{m:02d}" <= months[-1]:
    expected.append(f"{y}-{m:02d}"); m += 1
    if m == 13: y, m = y + 1, 1
missing = [x for x in expected if x not in by_month]
add("No missing months", "FAIL" if missing else "PASS",
    f"{len(expected)} months from Apr 2021 to {months[-1]}" + (f"; missing {', '.join(missing)}" if missing else ""))

# 2. data is current: latest complete month is last month
today = datetime.date.today()
lm = (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
latest_full = full[-1]["month"]
add("Data is current", "PASS" if latest_full >= lm else "FAIL", f"latest complete month {latest_full}, expected {lm}")

# 3. latest month is plausible against the same month a year earlier
last = full[-1]
ly = f"{int(last['month'][:4]) - 1}{last['month'][4:]}"
if ly in by_month:
    ratio = int(last["e2w_units"]) / max(1, int(by_month[ly]["e2w_units"]))
    add("Latest month within 0.5x–2.5x of last year", "PASS" if 0.5 <= ratio <= 2.5 else "FAIL",
        f"{last['month']}: {int(last['e2w_units']):,} vs {int(by_month[ly]['e2w_units']):,} ({ratio:.2f}x)")

# 4. penetration is plausible every month
bad = [r["month"] for r in full if not (0.002 <= int(r["e2w_units"]) / max(1, int(r["total_2w_units"])) <= 0.35)]
add("Penetration between 0.2% and 35% every month", "FAIL" if bad else "PASS", ", ".join(bad) or "all months")

# 5. maker file adds up to the monthly totals
oem_tot = {}
for r in oem:
    oem_tot[r["month"]] = oem_tot.get(r["month"], 0) + int(r["units"])
off = [k for k, v in oem_tot.items() if k in by_month and abs(v - int(by_month[k]["e2w_units"])) > max(50, 0.01 * v)]
add("Maker totals match monthly totals (±1%)", "FAIL" if off else "PASS", ", ".join(off[:6]) or "all months")

# 6. brand coverage: unmapped makers stay small
lo = [r for r in oem if r["month"] == latest_full]
others = sum(int(r["units"]) for r in lo if r["oem"] == "Others") / max(1, sum(int(r["units"]) for r in lo))
add("Unmapped makers under 5% of the latest month", "PASS" if others < 0.05 else "WARN", f"{others:.1%} in {latest_full}")

# 7. all states and UTs present for the current FY
fys = sorted({r["fy"] for r in states})
n = len({r["state"] for r in states if r["fy"] == fys[-1]})
add("States and UTs present (latest FY)", "PASS" if n >= 34 else "FAIL", f"{n} in {fys[-1]}")

# 8. history did not move: months older than 6 months change by under 2% vs the previous pull
if old:
    prev = {r["month"]: int(r["e2w_units"]) for r in read(old, "monthly.csv") if r["partial"] != "1"}
    cutoff = expected[-7] if len(expected) > 7 else expected[0]
    moved = [f"{k} {prev[k]:,}→{int(by_month[k]['e2w_units']):,}" for k in prev
             if k < cutoff and k in by_month and abs(int(by_month[k]["e2w_units"]) - prev[k]) > 0.02 * prev[k]]
    add("History stable vs previous pull (older months ±2%)", "FAIL" if moved else "PASS", "; ".join(moved[:5]) or f"months before {cutoff} unchanged within 2%")

# 9. state data adds up to All India, and makers within each state add up to the state
import os
if os.path.exists(f"{new}/state_monthly.csv") and os.path.exists(f"{new}/oem_state_monthly.csv"):
    sm = read(new, "state_monthly.csv"); osm = read(new, "oem_state_monthly.csv")
    st_tot = {}
    for r in sm:
        st_tot[r["month"]] = st_tot.get(r["month"], 0) + int(r["e2w_units"])
    off = [k for k, v in st_tot.items() if k in by_month and abs(v - int(by_month[k]["e2w_units"])) > max(50, 0.01 * v)]
    add("States add up to All India (±1%)", "FAIL" if off else "PASS", ", ".join(off[:6]) or "all months")
    ms = {}
    for r in osm:
        ms[(r["month"], r["state"])] = ms.get((r["month"], r["state"]), 0) + int(r["units"])
    big = [(k, int(r["e2w_units"])) for r in sm for k in [(r["month"], r["state"])] if int(r["e2w_units"]) >= 500]
    bad = [f"{k[1]} {k[0]}" for k, v in big if abs(ms.get(k, 0) - v) > 0.03 * v]
    add("Makers add up to each state (±3%)", "FAIL" if len(bad) > len(big) * 0.02 else ("WARN" if bad else "PASS"),
        f"{len(big) - len(bad)} of {len(big)} state-months match" + (f"; e.g. {', '.join(bad[:3])}" if bad else ""))
else:
    add("State drill-down files present", "FAIL", "state_monthly.csv or oem_state_monthly.csv missing")

stamp = datetime.datetime.now().astimezone().isoformat(timespec="minutes")
with open(f"{new}/checks.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["check", "status", "detail", "run_at"], lineterminator="\n")
    w.writeheader()
    for c in checks:
        w.writerow({**c, "run_at": stamp})
for c in checks:
    print(f"{c['status']:4}  {c['check']}: {c['detail']}")
sys.exit(1 if any(c["status"] == "FAIL" for c in checks) else 0)
