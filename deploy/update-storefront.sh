#!/bin/bash
# Install the latest storefront build (published by GitHub Actions to the `storefront-build`
# branch) into the cPanel Node.js app, then restart it.
#
#   bash ~/repos/wcw-portal/deploy/update-storefront.sh               # always redeploy
#   bash ~/repos/wcw-portal/deploy/update-storefront.sh --if-changed  # only when there's a new build (cron)
set -euo pipefail

APP_ROOT="apps/wcw-storefront"          # cPanel Setup Node.js App → application root
DEST="$HOME/$APP_ROOT"
# Dependencies live one level up: Node finds ~/apps/node_modules from ~/apps/wcw-storefront/server.js,
# and cPanel's Node selector doesn't allow a real node_modules folder inside the app root.
MODULES="$HOME/apps/node_modules"
CACHE="$HOME/repos/wcw-storefront-build"
REPO="git@github-wcw:windycitywares/wcw-portal.git"
SITE="https://shop.windycitywares.com"

if [ ! -d "$CACHE/.git" ]; then
  git clone -q --depth 1 --branch storefront-build "$REPO" "$CACHE"
fi
cd "$CACHE"
git fetch -q --depth 1 origin storefront-build
NEW=$(git rev-parse FETCH_HEAD)
OLD=$(cat "$DEST/.deployed_build" 2>/dev/null || echo none)
if [ "${1:-}" = "--if-changed" ] && [ "$NEW" = "$OLD" ]; then
  exit 0
fi
git reset -q --hard FETCH_HEAD
echo "$(date '+%F %T') deploying storefront build $(cat BUILD_SHA 2>/dev/null) (bundle ${NEW:0:7})"

mkdir -p "$DEST" "$MODULES"
rsync -a --delete "$CACHE/node_modules/" "$MODULES/"
rsync -a --delete \
  --exclude '.git' --exclude 'node_modules' --exclude 'tmp/' --exclude '.deployed_build' \
  "$CACHE/" "$DEST/"
echo "$NEW" > "$DEST/.deployed_build"

cloudlinux-selector restart --json --interpreter=nodejs --app-root="$APP_ROOT" >/dev/null
sleep 3
code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$SITE/")
if [ "$code" = "200" ]; then
  echo "✓ storefront is up ($SITE → 200)"
else
  echo "✗ storefront returned $code — check $DEST/stderr.log"
  exit 1
fi
