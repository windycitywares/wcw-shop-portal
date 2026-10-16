#!/bin/bash
# Background jobs: send queued emails, cart and review reminders, restock alerts, the weekly owner digest,
# and clear out old analytics. auto-deploy.sh runs this every 10 minutes; to run it by hand:
#   bash ~/repos/wcw-shop-portal/deploy/run-jobs.sh                 # whatever is due
#   bash ~/repos/wcw-shop-portal/deploy/run-jobs.sh --only outbox   # just some jobs
#   bash ~/repos/wcw-shop-portal/deploy/run-jobs.sh --force-digest  # send the weekly email now
set -euo pipefail
# Where this checkout lives: ~/repos/wcw-shop-portal (or ~/repos/wcw-portal on a server set up before the rename).
# auto-deploy.sh passes it on in WCW_REPO_DIR; run by hand, the script works it out from its own location.
REPO_DIR="${WCW_REPO_DIR:-}"
if [ -z "$REPO_DIR" ]; then
  HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [ -f "$HERE/deploy/auto-deploy.sh" ]; then REPO_DIR="$HERE"           # run from inside the checkout
  elif [ -d "$HOME/repos/wcw-shop-portal/.git" ]; then REPO_DIR="$HOME/repos/wcw-shop-portal"
  else REPO_DIR="$HOME/repos/wcw-portal"; fi                                 # run from a copy (auto-deploy)
fi
APP_ROOT="${REPO_DIR#"$HOME"/}/backend"   # cPanel Setup Python App → application root
VENV="$HOME/virtualenv/$APP_ROOT/3.11/bin/activate"
cd "$HOME/$APP_ROOT"
# shellcheck disable=SC1090
source "$VENV"
exec python -m app.scripts.run_jobs "$@"
