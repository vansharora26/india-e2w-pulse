#!/bin/bash
# Daily refresh: pull Vahan -> run checks -> (only if all pass) update data, rebuild the site, commit and push (GitHub Pages redeploys).
# A failed check leaves the live site as it was and raises a macOS notification.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")"
LOG="logs/refresh-$(date +%Y-%m-%d).log"; mkdir -p logs tmp
exec >>"$LOG" 2>&1
echo "== $(date '+%F %T') refresh start"
notify() { osascript -e "display notification \"$1\" with title \"India e2W Pulse\"" >/dev/null 2>&1 || true; }

rm -rf tmp/new && mkdir -p tmp/new && cp data/reconciliation.csv tmp/new/
for attempt in 1 2 3; do
  python3 -I vahan_fetch.py tmp/new && break
  echo "fetch attempt $attempt failed"; sleep 60
done
[ -f tmp/new/monthly.csv ] || { notify "Refresh failed: could not reach Vahan. Live site unchanged."; echo "FETCH FAILED"; exit 1; }

if ! python3 -I validate.py tmp/new data; then
  cp tmp/new/checks.csv logs/failed-checks-$(date +%Y-%m-%d).csv
  notify "Data checks failed. Live site unchanged. See logs in ~/e2w-dashboard/logs."
  echo "CHECKS FAILED"; exit 1
fi

cp tmp/new/{monthly,oem_monthly,states,maker_monthly_raw,checks,state_monthly,oem_state_monthly}.csv data/
python3 -I build_site.py
git add data docs cache
git -c user.email="vansharora26@users.noreply.github.com" commit -qm "Data refresh $(date +%F)" || echo "no data change"
if git push -q origin main; then
  echo "DEPLOYED (pushed to GitHub Pages)"
else
  notify "Push to GitHub failed. Data was refreshed locally."; echo "DEPLOY FAILED"; exit 1
fi
find logs -name "refresh-*.log" -mtime +30 -delete
echo "== $(date '+%F %T') refresh done"
