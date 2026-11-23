"""Pull e2W registrations from the Vahan dashboard (vahan.parivahan.gov.in) into CSVs.

Usage: python3 vahan_fetch.py OUT_DIR
Queries the public report view: two-wheeler vehicle classes, electric fuels, month-wise,
by Maker and by State, one calendar year per request. Standard library only.
"""
import html, http.cookiejar, re, sys, time, urllib.parse, urllib.request

URL = "https://vahan.parivahan.gov.in/vahan4dashboard/vahan/view/reportview.xhtml"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) e2w-dashboard/1.0"
TWO_W_CLASSES = ["1", "2", "3", "4", "51", "52", "53"]   # M-cycle/scooter variants, moped, motorised cycle
EV_FUELS = ["4", "23"]                                    # ELECTRIC(BOV), PURE EV

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get(url, data=None, ajax=False):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data, doseq=True).encode() if data else None,
                                 headers={"User-Agent": UA})
    if ajax:
        req.add_header("Faces-Request", "partial/ajax")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
    with op.open(req, timeout=90) as r:
        return r.read().decode("utf-8", "ignore")

class Session:
    """One browser-like session on the report page. ViewState is refreshed from every reply."""
    def __init__(self):
        page = get(URL)
        self.vs = re.search(r'name="javax.faces.ViewState"[^>]*value="([^"]+)"', page).group(1)
        self.action = "https://vahan.parivahan.gov.in" + html.unescape(
            re.search(r'<form id="masterLayout_formlogin"[^>]*action="([^"]+)"', page).group(1))
        un = html.unescape(page)
        self.main_btn = re.search(r'<button id="(j_idt\d+)"[^>]*u:"VhCatg norms fuel VhClass combTablePnl', un).group(1)
        self.filter_btns = re.findall(r'<button id="(j_idt\d+)"[^>]*u:"combTablePnl"', un)
        self.fields = {}

    def post(self, source, render, extra=None):
        form = {"javax.faces.partial.ajax": "true", "javax.faces.source": source,
                "javax.faces.partial.execute": "@all", "javax.faces.partial.render": render,
                "masterLayout_formlogin": "masterLayout_formlogin", "javax.faces.ViewState": self.vs}
        form.update(self.fields)
        if extra:
            form.update(extra)
        x = get(self.action, form, ajax=True)
        m = re.search(r'ViewState:0"><!\[CDATA\[([^\]]+)\]\]>', x)
        if m:
            self.vs = m.group(1)
        return x

    def report(self, y_axis, year, fuels, categories):
        self.fields = {"j_idt25_input": "A", "j_idt36_input": "-1", "selectedRto_input": "-1",
                       "yaxisVar_input": y_axis, "xaxisVar_input": "Month Wise",
                       "selectedYearType_input": "C", "selectedYear_input": str(year)}
        self.post(self.main_btn, "VhCatg norms fuel VhClass combTablePnl groupingTable msg vhCatgPnl", {self.main_btn: self.main_btn})
        if categories:
            self.fields["VhCatg"] = categories
        if fuels:
            self.fields["fuel"] = fuels
        b = self.filter_btns[0]
        first = self.post(b, "combTablePnl", {b: b})
        head, rows = parse(first)
        total = int((re.search(r"rowCount:(\d+)", first) or [0, len(rows)])[1])
        start = len(rows)
        while start < total:      # the table pages 25 rows at a time
            x = get(self.action, {"javax.faces.partial.ajax": "true", "javax.faces.source": "groupingTable",
                                  "javax.faces.partial.execute": "groupingTable", "javax.faces.partial.render": "groupingTable",
                                  "groupingTable": "groupingTable", "groupingTable_pagination": "true",
                                  "groupingTable_first": str(start), "groupingTable_rows": "25",
                                  "groupingTable_skipChildren": "true", "groupingTable_encodeFeature": "true",
                                  "masterLayout_formlogin": "masterLayout_formlogin", "javax.faces.ViewState": self.vs}, ajax=True)
            _, more = parse(x)
            if not more:
                break
            rows += more
            start += len(more)
        return head, rows

TWO_W_CATEGORIES = ["2WIC", "2WN", "2WT"]

def query(y_axis, year, fuels=EV_FUELS, categories=TWO_W_CATEGORIES):
    return Session().report(y_axis, year, fuels, categories)

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

def parse(xml):
    """Return (header, rows) from the groupingTable in the partial response."""
    body = html.unescape(xml)
    th = re.search(r'id="groupingTable".*?<tbody', body, re.S)
    head = [re.sub(r"<[^>]+>|\s+", " ", c).strip() for c in re.findall(r"<th[^>]*>(.*?)</th>", th.group(0), re.S)] if th else None
    t = body
    rows = []
    for tr in re.findall(r"<tr[^>]*data-ri[^>]*>(.*?)</tr>", t, re.S):
        cells = [re.sub(r"<[^>]+>|\s+", " ", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        rows.append(cells)
    return head, rows

BRANDS = [  # Vahan legal-entity name pattern -> brand shown on the dashboard (covers ~98% of volume)
    (r"^TVS MOTOR", "TVS"), (r"^BAJAJ AUTO", "Bajaj"), (r"^ATHER ENERGY", "Ather"),
    (r"^OLA ELECTRIC", "Ola Electric"), (r"^HERO MOTOCORP", "Hero (Vida)"),
    (r"^GREAVES ELECTRIC|^AMPERE VEHICLES", "Greaves (Ampere)"), (r"^HERO ELECTRIC VEHICLE", "Hero Electric"),
    (r"^OKINAWA", "Okinawa"), (r"^BGAUSS", "BGauss"), (r"^RIVER MOBILITY", "River"),
    (r"^PUR ENERGY", "Pure EV"), (r"^REVOLT", "Revolt"), (r"^KINETIC GREEN", "Kinetic Green"),
    (r"^KINETIC WATTS|^KINETIC MOTOR", "Kinetic (DX)"), (r"^BOUNCE ELECTRIC", "Bounce"),
    (r"^LECTRIX", "Lectrix"), (r"^SIMPLE ?ENERGY", "Simple Energy"), (r"^E-SPRINTO", "E-Sprinto"),
    (r"^WARDWIZARD", "Joy e-bike (Wardwizard)"), (r"^BENLING", "Benling"), (r"^KLB KOMAKI", "Komaki"),
    (r"^QUANTUM ENERGY|IMPORTER: QUANTUM", "Quantum"), (r"^JITENDRA", "Jitendra EV"),
    (r"^OBEN ELECTRIC", "Oben"), (r"^MOTOVOLT", "Motovolt"), (r"^HONDA MOTORCYCLE", "Honda"),
    (r"^ULTRAVIOLETTE", "Ultraviolette"), (r"^ODYSSE", "Odysse"), (r"^SUZUKI MOTORCYCLE", "Suzuki"),
    (r"^INDIA YAMAHA", "Yamaha"), (r"^OKAYA", "Okaya"),
]

STATE_FIX = {"Ut Of Dnh And Dd": "Dadra & Nagar Haveli and Daman & Diu", "Andaman & Nicobar Island": "Andaman & Nicobar Islands"}

def state_name(raw):
    t = re.sub(r"\bAnd\b", "and", raw.strip().title())
    return STATE_FIX.get(raw.strip().title(), t)

def brand(maker):
    for pat, name in BRANDS:
        if re.search(pat, maker, re.I):
            return name
    return "Others"

def num(s):
    return int(s.replace(",", "") or 0)

def fy_of(month):
    y, m = map(int, month.split("-"))
    return f"FY{(y + 1 if m >= 4 else y) % 100:02d}"

def month_cols(head, row):
    """Pair month names in the header with values in the row (row: S No, name, months..., TOTAL)."""
    months = [h for h in (head or []) if h in MONTHS]
    vals = row[2:2 + len(months)]
    return list(zip(months, vals))

def main(out, first_year=2021):
    import csv, datetime
    today = datetime.date.today()
    cur = f"{today.year}-{today.month:02d}"
    oem, ev_state, all_state, raw = {}, {}, {}, []
    for year in range(first_year, today.year + 1):
        for (y_axis, fuels, store) in [("Maker", EV_FUELS, "oem"), ("State", EV_FUELS, "ev"), ("State", None, "all")]:
            for attempt in range(3):
                try:
                    head, rows = Session().report(y_axis, year, fuels, TWO_W_CATEGORIES)
                    break
                except Exception as e:  # Vahan is flaky; retry
                    print("retry", year, y_axis, e, file=sys.stderr); time.sleep(5)
            else:
                raise SystemExit(f"Vahan query failed: {year} {y_axis}")
            print(year, y_axis, "fuel" if fuels else "all", len(rows), "rows", file=sys.stderr)
            for row in rows:
                name = re.sub(r"\(\d+\)$", "", row[1]).strip()
                for mon, v in month_cols(head, row):
                    m = f"{year}-{MONTHS.index(mon) + 1:02d}"
                    if m < "2021-04":
                        continue
                    if store == "oem":
                        k = (m, brand(name)); oem[k] = oem.get(k, 0) + num(v)
                        if num(v): raw.append([m, fy_of(m), name, num(v)])
                    else:
                        d = ev_state if store == "ev" else all_state
                        d[(m, state_name(name))] = d.get((m, state_name(name)), 0) + num(v)
    months = sorted({m for m, _ in all_state})
    with open(f"{out}/monthly.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["month", "fy", "e2w_units", "total_2w_units", "partial"])
        for m in months:
            e = sum(v for (mm, _), v in ev_state.items() if mm == m)
            t = sum(v for (mm, _), v in all_state.items() if mm == m)
            w.writerow([m, fy_of(m), e, t, 1 if m == cur else 0])
    with open(f"{out}/oem_monthly.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["month", "fy", "oem", "units", "partial"])
        for (m, b), v in sorted(oem.items()):
            w.writerow([m, fy_of(m), b, v, 1 if m == cur else 0])
    with open(f"{out}/maker_monthly_raw.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["month", "fy", "maker", "units"]); w.writerows(raw)
    agg = {}
    for (m, s), v in all_state.items():
        if m == cur: continue
        a = agg.setdefault((fy_of(m), s), [0, 0]); a[1] += v
    for (m, s), v in ev_state.items():
        if m == cur: continue
        agg.setdefault((fy_of(m), s), [0, 0])[0] += v
    with open(f"{out}/states.csv", "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n"); w.writerow(["fy", "state", "e2w_units", "total_2w_units"])
        for (fy, s), (e, t) in sorted(agg.items()):
            if t: w.writerow([fy, s, e, t])
    print("wrote", out, "through", cur, file=sys.stderr)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
