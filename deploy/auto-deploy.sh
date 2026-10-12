#!/bin/bash
# Cron entry point (every 10 minutes): deploy whatever is new on GitHub.
#   */10 * * * * bash $HOME/repos/wcw-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-deploy.log 2>&1
# - API: when `main` has new commits, run update-api.sh (tests must pass before it restarts).
# - Storefront: when GitHub Actions has published a new build, run update-storefront.sh.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"   # cron's default PATH is minimal
exec 9>"$HOME/.wcw-deploy.lock"
flock -n 9 || exit 0   # a previous run is still going

REPO="$HOME/repos/wcw-portal"
cd "$REPO" || exit 1
git fetch -q origin main || { echo "$(date '+%F %T') git fetch failed"; exit 1; }
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "$(date '+%F %T') API: updating to $(git log --oneline -1 origin/main)"
  # Run the copy from origin/main so script changes take effect immediately.
  git show origin/main:deploy/update-api.sh > "$HOME/.wcw-update-api.sh"
  bash "$HOME/.wcw-update-api.sh" main || echo "$(date '+%F %T') API update FAILED — previous version still running"
fi

bash "$REPO/deploy/update-storefront.sh" --if-changed || echo "$(date '+%F %T') storefront update FAILED"
