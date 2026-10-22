#!/bin/bash
# Update the API on HostItBro to the latest code from GitHub.
# Run in cPanel → Terminal:   bash ~/repos/wcw-shop-portal/deploy/update-api.sh [branch]
# If installing or the tests fail, the previous code is restored and the running app is untouched.
set -euo pipefail
BRANCH="${1:-main}"
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
RESTARTED=0

cd "$REPO_DIR"
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
echo "→ Test mode: refresh the test data if the migration changed the tables"
python -m app.scripts.test_env sync-if-active || echo "✗ could not refresh the test data (Admin → Test mode → Copy live data again)"
echo "→ Restarting the app"
RESTARTED=1
# Cron runs with a minimal PATH (no /usr/sbin), so find the selector explicitly; Passenger's
# tmp/restart.txt is the fallback and works for both the Python and the Node.js app.
SELECTOR=$(command -v cloudlinux-selector || ls /usr/sbin/cloudlinux-selector /usr/bin/cloudlinux-selector 2>/dev/null | head -1 || true)
if [ -z "$SELECTOR" ] || ! "$SELECTOR" restart --json --interpreter=python --app-root="$APP_ROOT" >/dev/null; then
  mkdir -p "$HOME/$APP_ROOT/tmp" && touch "$HOME/$APP_ROOT/tmp/restart.txt"
fi
# The app can take a while to start after a restart (a 503 meanwhile): retry for up to ~90 seconds.
code=000
for _ in $(seq 1 18); do
  sleep 5
  code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' https://shop-api.windycitywares.com/health || true)
  [ "$code" = "200" ] && break
done
if [ "$code" = "200" ]; then echo "✓ API is up (health 200)"; else echo "✗ restarted on the new code, but the health check still returns $code after 90 s — see backend/stderr.log"; exit 1; fi
