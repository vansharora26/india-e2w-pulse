#!/bin/bash
# Daily refresh: pull Vahan -> run checks -> (only if all pass) update data, commit, rebuild and deploy to Netlify.
# A failed check leaves the live site as it was and raises a macOS notification.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"
cd "$(dirname "$0")"
SITE_ID="727db92c-6120-4b70-8a65-e0ee22aa7bdf"
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
git add data && git -c user.email="vansharora26@users.noreply.github.com" commit -qm "Data refresh $(date +%F)" || echo "no data change"
if npx -y netlify-cli@17.38.1 deploy --prod --dir site --site "$SITE_ID" --message "Data refresh $(date +%F)"; then
  echo "DEPLOYED"
else
  notify "Netlify deploy failed. Data was refreshed locally."; echo "DEPLOY FAILED"; exit 1
fi
find logs -name "refresh-*.log" -mtime +30 -delete
echo "== $(date '+%F %T') refresh done"
