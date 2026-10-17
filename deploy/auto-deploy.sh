#!/bin/bash
# Cron entry point — runs EVERY MINUTE (docs/DEPLOYMENT.md → "Automatic deploys"):
#   * * * * * bash $HOME/repos/wcw-shop-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-deploy.log 2>&1
# 1. Ask the gate (Admin → Deployments) whether to look for updates now: "Deploy now" was clicked, automatic every
#    N minutes, at set times, or paused. If the gate can't answer (e.g. the API code is older, or the database is
#    down), look anyway — deploys never get stuck because of the gate.
# 2. API: when `main` has new commits, run update-api.sh (tests must pass before it restarts).
# 3. Storefront: when GitHub Actions has published a new build, run update-storefront.sh.
# 4. Main site: when windycitywares/wcw-main-site Actions has published a new build, run update-main-site.sh.
# 5. Tell the gate what happened (shown in Admin → Deployments).
# 6. Background jobs (queued emails, reminders, weekly digest, clean-up): run-jobs.sh, every 5 minutes and after a check.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"   # cron's default PATH is minimal
exec 9>"$HOME/.wcw-deploy.lock"
flock -n 9 || exit 0   # a previous run is still going

# This checkout: ~/repos/wcw-shop-portal, or ~/repos/wcw-portal on a server set up before the rename.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WCW_REPO_DIR="$REPO"   # update-api.sh runs from a copy in $HOME, so tell it where the checkout is
API_ROOT="${REPO#"$HOME"/}/backend"
VENV="$HOME/virtualenv/$API_ROOT/3.11/bin/activate"
ts() { date '+%F %T'; }
gate() {  # gate begin | gate end ok|failed "summary"
  # shellcheck disable=SC1090
  ( source "$VENV" && cd "$REPO/backend" && python -m app.scripts.deploy_gate "$@" ) 2>>"$HOME/logs/wcw-deploy-gate.err"
}
jobs_due() { [ $((10#$(date +%M) % 5)) -eq 0 ]; }
run_jobs() { bash "$REPO/deploy/run-jobs.sh" || echo "$(ts) background jobs FAILED"; }

decision=$(gate begin || true)
case "$decision" in
  go\ *) reason="${decision#go }" ;;
  skip\ *) jobs_due && run_jobs; exit 0 ;;
  *) reason="gate unavailable" ;;
esac

cd "$REPO" || exit 1
# The GitHub repo was renamed wcw-portal → wcw-shop-portal. GitHub redirects the old address, but point the
# remote at the new name once so it keeps working if the redirect ever goes.
URL=$(git remote get-url origin)
case "$URL" in
  *windycitywares/wcw-portal.git|*windycitywares/wcw-portal)
    git remote set-url origin "${URL/windycitywares\/wcw-portal/windycitywares\/wcw-shop-portal}"
    echo "$(ts) git remote now $(git remote get-url origin)" ;;
esac

ok=1
summary=""
add() { summary="${summary:+$summary; }$1"; }
if ! git fetch -q origin main; then
  echo "$(ts) git fetch failed"
  ok=0; add "git fetch failed"
elif [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  target="$(git log --oneline -1 origin/main)"
  echo "$(ts) API: updating to $target ($reason)"
  # Run the copy from origin/main so script changes take effect immediately.
  git show origin/main:deploy/update-api.sh > "$HOME/.wcw-update-api.sh"
  if bash "$HOME/.wcw-update-api.sh" main; then
    add "API updated to $target"
  else
    echo "$(ts) API update FAILED — see the ✗ line above for whether the old or new code is running"
    ok=0; add "API update to $target failed — the previous version keeps running"
  fi
fi

# Storefront and main site print a line only when they install a new build.
for part in storefront main-site; do
  out=$(bash "$REPO/deploy/update-$part.sh" --if-changed 2>&1); rc=$?
  [ -n "$out" ] && echo "$out"
  label=$([ "$part" = storefront ] && echo "storefront" || echo "main site")
  if [ "$rc" -ne 0 ]; then
    echo "$(ts) $label update FAILED"
    ok=0; add "$label update failed"
  elif echo "$out" | grep -q "deploying"; then
    add "$label build $(echo "$out" | grep -o 'build [0-9a-f]\{7\}' | head -1 | cut -c7-)"
  fi
done

[ "$reason" = "manual" ] && [ -z "$summary" ] && echo "$(ts) deploy now: already up to date"
if [ "$ok" = 1 ]; then gate end ok "${summary:-already up to date} ($reason)" >/dev/null
else gate end failed "$summary ($reason)" >/dev/null; fi

run_jobs
exit 0
