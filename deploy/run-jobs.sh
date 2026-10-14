#!/bin/bash
# Background jobs: send queued emails, cart and review reminders, restock alerts, the weekly owner digest,
# and clear out old analytics. auto-deploy.sh runs this every 10 minutes; to run it by hand:
#   bash ~/repos/wcw-portal/deploy/run-jobs.sh                 # whatever is due
#   bash ~/repos/wcw-portal/deploy/run-jobs.sh --only outbox   # just some jobs
#   bash ~/repos/wcw-portal/deploy/run-jobs.sh --force-digest  # send the weekly email now
set -euo pipefail
APP_ROOT="repos/wcw-portal/backend"
VENV="$HOME/virtualenv/$APP_ROOT/3.11/bin/activate"
cd "$HOME/$APP_ROOT"
# shellcheck disable=SC1090
source "$VENV"
exec python -m app.scripts.run_jobs "$@"
