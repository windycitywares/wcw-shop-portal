#!/bin/bash
# Update the API on HostItBro to the latest code from GitHub.
# Run in cPanel → Terminal:   bash ~/repos/wcw-portal/deploy/update-api.sh [branch]
# If installing or the tests fail, the previous code is restored and the running app is untouched.
set -euo pipefail
BRANCH="${1:-main}"
APP_ROOT="repos/wcw-portal/backend"
VENV="$HOME/virtualenv/$APP_ROOT/3.11/bin/activate"
RESTARTED=0

cd "$HOME/repos/wcw-portal"
PREV=$(git rev-parse HEAD)
rollback() {
  if [ "$RESTARTED" = "0" ]; then
    echo "✗ update failed before restart — restoring $(git log --oneline -1 "$PREV")"
    git checkout -q -B "$BRANCH" "$PREV"
  fi
}
trap rollback ERR

echo "→ Fetching $BRANCH"
git fetch -q origin "$BRANCH"
git checkout -q -B "$BRANCH" "origin/$BRANCH"
git log --oneline -1

cd backend
# shellcheck disable=SC1090
source "$VENV"
echo "→ Installing packages"
pip install -q -r requirements.txt
echo "→ Running tests"
python -m unittest discover -q tests
echo "→ Database migrations"
alembic upgrade head
echo "→ Restarting the app"
RESTARTED=1
cloudlinux-selector restart --json --interpreter=python --app-root="$APP_ROOT" >/dev/null
sleep 2
code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' https://api.windycitywares.com/health)
if [ "$code" = "200" ]; then echo "✓ API is up (health 200)"; else echo "✗ health check returned $code — see backend/stderr.log"; exit 1; fi
