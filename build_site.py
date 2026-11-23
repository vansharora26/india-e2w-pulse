"""Build the public Netlify site from the dashboard page: site/index.html + site/data/*.csv"""
import pathlib, re, shutil

root = pathlib.Path(__file__).parent
page = (root / "dashboard_page.html").read_text()
page = page.replace('<meta name="dash-one-writer">\n', "")
style = re.search(r"<style>(.*?)</style>", page, re.S).group(1)
script = re.search(r"<script>(.*)</script>", page, re.S).group(1)
body = re.sub(r"<style>.*?</style>|<script>.*</script>", "", page, flags=re.S).strip()

TOKENS = """
  /* Navy report palette; light by default, dark follows the system or the toggle */
  :root {
    --color-bg: #f4f6f9; --color-panel: #ffffff; --color-fg: #051c2c; --color-fg-muted: #566676; --color-border-line: #d9e0e8;
    --color-ok: #0a7a3a; --color-warn: #8a5a00; --color-bad: #a12c2c;
    --c0: #051c2c; --c1: #2251ff; --c2: #00a9f4; --c3: #1f9e8f; --c4: #8c9ef7; --c5: #6e7b87; --c6: #c9952b; --c7: #b4325a;
    --cds-chart-muted: #b9c3cd; --cds-chart-grid: #e3e8ee; --cds-chart-axis: #c5ced8; --cds-chart-reference: #8a98a6;
    --cds-text-secondary: #5b6b7a; --cds-surface-popover: #ffffff; --cds-border: #d9e0e8; --cds-shadow-popover: 0 8px 24px rgba(5, 28, 44, .14);
    --font-anthropic-sans: "Public Sans", "Helvetica Neue", Arial, sans-serif;
    --font-anthropic-serif: "Newsreader", Georgia, "Times New Roman", serif;
    --cds-font-size-caption: 12px; --cds-font-size-body: 14px; --cds-font-size-heading: 18px; --cds-font-size-title: 28px; --cds-font-weight-medium: 600;
    --cds-gap-xs: 4px; --cds-gap-sm: 8px; --cds-gap-md: 12px; --cds-gap-lg: 20px; --cds-gap-xl: 32px;
    --cds-pad-xs: 4px; --cds-pad-sm: 8px; --cds-pad-md: 12px; --cds-pad-lg: 20px; --cds-pad-xl: 32px; --cds-radius: 12px;
    --cds-ease-out: cubic-bezier(.2, .7, .2, 1); --cds-dur-slow: 600ms;
  }
  @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
    --color-bg: #061019; --color-panel: #0c1b28; --color-fg: #eef2f6; --color-fg-muted: #93a1af; --color-border-line: #1c2f3f;
    --color-ok: #3ccf74; --color-warn: #e8b04a; --color-bad: #f08a8a;
    --c0: #dfe7f1; --c1: #5b7cff; --c2: #3fc3ff; --c3: #3cc2b1; --c4: #b7c3ff; --c5: #9aa6b2; --c6: #e0bc4a; --c7: #e0688a;
    --cds-chart-muted: #4a5b6a; --cds-chart-grid: #1c2f3f; --cds-chart-axis: #2a3f52; --cds-chart-reference: #7d8d9c;
    --cds-text-secondary: #9fadba; --cds-surface-popover: #10222f; --cds-border: #2a3f52; --cds-shadow-popover: 0 8px 24px rgba(0, 0, 0, .5);
    color-scheme: dark; } }
  :root[data-theme="dark"] {
    --color-bg: #061019; --color-panel: #0c1b28; --color-fg: #eef2f6; --color-fg-muted: #93a1af; --color-border-line: #1c2f3f;
    --color-ok: #3ccf74; --color-warn: #e8b04a; --color-bad: #f08a8a;
    --c0: #dfe7f1; --c1: #5b7cff; --c2: #3fc3ff; --c3: #3cc2b1; --c4: #b7c3ff; --c5: #9aa6b2; --c6: #e0bc4a; --c7: #e0688a;
    --cds-chart-muted: #4a5b6a; --cds-chart-grid: #1c2f3f; --cds-chart-axis: #2a3f52; --cds-chart-reference: #7d8d9c;
    --cds-text-secondary: #9fadba; --cds-surface-popover: #10222f; --cds-border: #2a3f52; --cds-shadow-popover: 0 8px 24px rgba(0, 0, 0, .5);
    color-scheme: dark; }
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body { margin: 0; background: var(--color-bg); color: var(--color-fg); font: 14px/1.5 var(--font-anthropic-sans); }
  .site { max-width: 1280px; margin: 0 auto; padding-block: 24px 48px;
    padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
  .dash-select { appearance: none; font: inherit; padding: 8px 34px 8px 12px; border-radius: 8px; border: 1px solid var(--color-border-line);
    background-color: var(--color-panel); color: var(--color-fg); cursor: pointer;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' fill='none' stroke='%2393a1af' stroke-width='1.8'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 12px center; }
  .mk-foot a { color: inherit; }
"""

SHIM = r"""
// Minimal stand-in for the dashboard runtime: loads the CSVs, runs calculations, redraws on change.
window.dash = (function () {
  const FILES = { monthly: 'data/monthly.csv', oem_monthly: 'data/oem_monthly.csv', states: 'data/states.csv',
                  reconciliation: 'data/reconciliation.csv', refresh_checks: 'data/checks.csv',
                  state_monthly: 'data/state_monthly.csv', oem_state_monthly: 'data/oem_state_monthly.csv' };
  const store = {}, calcs = {}, draws = [], listeners = [];
  // filters live in the URL (?state=Bihar&period=FY26) so any drill-down can be shared as a link
  const DEFAULTS = { period: 'FY27', state: '' };
  const fromUrl = () => { const q = new URLSearchParams(location.search); return { period: q.get('period') || DEFAULTS.period, state: q.get('state') || DEFAULTS.state }; };
  let params = fromUrl(), version = 0, cache = {};
  const toUrl = () => {
    const q = new URLSearchParams();
    if (params.state) q.set('state', params.state);
    if (params.period !== DEFAULTS.period) q.set('period', params.period);
    const u = location.pathname + (q.toString() ? '?' + q : '') + location.hash;
    if (u !== location.pathname + location.search + location.hash) history.pushState(null, '', u);
    document.title = params.state ? `${params.state} · India e2W Pulse` : 'India e2W Pulse';
  };
  window.addEventListener('popstate', () => { params = fromUrl(); cache = {}; schedule(); });
  document.title = params.state ? `${params.state} · India e2W Pulse` : 'India e2W Pulse';
  const bump = () => { version++; cache = {}; schedule(); };
  Object.entries(FILES).forEach(([id, url]) => {
    store[id] = { status: 'loading', data: [] };
    fetch(url, { cache: 'no-cache' }).then((r) => { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then((t) => { store[id] = { status: 'ok', data: d3.csvParse(t) }; bump(); })
      .catch(() => { store[id] = { status: 'error', data: [] }; bump(); });
  });
  function data(id) {
    if (store[id]) return store[id];
    const c = calcs[id];
    if (!c) return { status: 'missing', data: [] };
    if (cache[id]) return cache[id];
    const ins = c.inputs.map(data);
    const bad = ins.find((d) => d.status !== 'ok');
    let res;
    if (bad) res = { status: bad.status, data: null };
    else { try { res = { status: 'ok', data: c.fn(...ins.map((d) => d.data)) }; } catch (e) { console.error(id, e); res = { status: 'error', data: null }; } }
    return (cache[id] = res);
  }
  let pending = false;
  function schedule() { if (pending) return; pending = true; requestAnimationFrame(() => { pending = false; render(); }); }
  function render() {
    listeners.forEach((f) => { try { f(); } catch (e) { console.error(e); } });
    draws.forEach(([name, fn]) => document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => { try { fn(el); } catch (e) { console.error(name, e); } }));
  }
  let lastW = window.innerWidth;
  window.addEventListener('resize', () => { if (Math.abs(window.innerWidth - lastW) > 4) { lastW = window.innerWidth; schedule(); } });
  return {
    colors: ['var(--c0)', 'var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)', 'var(--c6)', 'var(--c7)'],
    data, params: () => params,
    setParams: (p) => { params = { ...params, ...p }; cache = {}; toUrl(); schedule(); },
    resetParams: () => { params = { ...DEFAULTS }; cache = {}; toUrl(); schedule(); },
    calc: (id, o) => { calcs[id] = o; },
    loader: () => {}, refresh: () => {}, setLink: () => {},
    draw: (name, fn) => { draws.push([name, fn]); },
    onData: (fn) => { listeners.push(fn); },
    _render: schedule,
  };
})();
"""

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>India e2W Pulse</title>
<meta name="description" content="Electric two-wheeler registrations in India from the Vahan dashboard: volume, penetration, makers and states, refreshed daily.">
<meta property="og:title" content="India e2W Pulse">
<meta property="og:description" content="Electric two-wheeler registrations in India from Vahan, refreshed daily.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;1,6..72,400&family=Public+Sans:wght@400;500;600;700&display=swap">
<style>{TOKENS}{style}</style>
</head>
<body>
<main class="site" id="dash-root">
{body}
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>{SHIM}</script>
<script>{script}
dash._render();
</script>
</body>
</html>
"""
out = root / "docs"   # GitHub Pages serves /docs on main
(out / "data").mkdir(parents=True, exist_ok=True)
(out / "index.html").write_text(html)
for f in ["monthly.csv", "oem_monthly.csv", "states.csv", "reconciliation.csv", "checks.csv", "state_monthly.csv", "oem_state_monthly.csv"]:
    shutil.copy(root / "data" / f, out / "data" / f)
(out / ".nojekyll").write_text("")
print("built", out)
