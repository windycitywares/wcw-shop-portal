#!/bin/bash
# Cron entry point (every 10 minutes): deploy whatever is new on GitHub.
#   */10 * * * * bash $HOME/repos/wcw-shop-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-deploy.log 2>&1
# - API: when `main` has new commits, run update-api.sh (tests must pass before it restarts).
# - Storefront: when GitHub Actions has published a new build, run update-storefront.sh.
# - Main site: when windycitywares/wcw-main-site Actions has published a new build, run update-main-site.sh.
# - Then the background jobs (queued emails, reminders, weekly digest, clean-up): run-jobs.sh.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"   # cron's default PATH is minimal
exec 9>"$HOME/.wcw-deploy.lock"
flock -n 9 || exit 0   # a previous run is still going

# This checkout: ~/repos/wcw-shop-portal, or ~/repos/wcw-portal on a server set up before the rename.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WCW_REPO_DIR="$REPO"   # update-api.sh runs from a copy in $HOME, so tell it where the checkout is
cd "$REPO" || exit 1
# The GitHub repo was renamed wcw-portal → wcw-shop-portal. GitHub redirects the old address, but point the
# remote at the new name once so it keeps working if the redirect ever goes.
URL=$(git remote get-url origin)
case "$URL" in
  *windycitywares/wcw-portal.git|*windycitywares/wcw-portal)
    git remote set-url origin "${URL/windycitywares\/wcw-portal/windycitywares\/wcw-shop-portal}"
    echo "$(date '+%F %T') git remote now $(git remote get-url origin)" ;;
esac
git fetch -q origin main || { echo "$(date '+%F %T') git fetch failed"; exit 1; }
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "$(date '+%F %T') API: updating to $(git log --oneline -1 origin/main)"
  # Run the copy from origin/main so script changes take effect immediately.
  git show origin/main:deploy/update-api.sh > "$HOME/.wcw-update-api.sh"
  bash "$HOME/.wcw-update-api.sh" main || echo "$(date '+%F %T') API update FAILED — see the ✗ line above for whether the old or new code is running"
fi

bash "$REPO/deploy/update-storefront.sh" --if-changed || echo "$(date '+%F %T') storefront update FAILED"
bash "$REPO/deploy/update-main-site.sh" --if-changed || echo "$(date '+%F %T') main site update FAILED"

bash "$REPO/deploy/run-jobs.sh" || echo "$(date '+%F %T') background jobs FAILED"
