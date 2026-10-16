#!/bin/bash
# Install the latest storefront build (published by GitHub Actions to the `storefront-build`
# branch) into the cPanel Node.js app, then restart it.
#
#   bash ~/repos/wcw-shop-portal/deploy/update-storefront.sh               # always redeploy
#   bash ~/repos/wcw-shop-portal/deploy/update-storefront.sh --if-changed  # only when there's a new build (cron)
set -euo pipefail

APP_ROOT="apps/wcw-storefront"          # cPanel Setup Node.js App → application root
DEST="$HOME/$APP_ROOT"
# Dependencies live one level up: Node finds ~/apps/node_modules from ~/apps/wcw-storefront/server.js,
# and cPanel's Node selector doesn't allow a real node_modules folder inside the app root.
MODULES="$HOME/apps/node_modules"
CACHE="$HOME/repos/wcw-storefront-build"
REPO="git@github-wcw:windycitywares/wcw-shop-portal.git"
SITE="https://shop.windycitywares.com"

if [ ! -d "$CACHE/.git" ]; then
  git clone -q --depth 1 --branch storefront-build "$REPO" "$CACHE"
fi
cd "$CACHE"
git remote set-url origin "$REPO"   # an older cache still points at the pre-rename address
git fetch -q --depth 1 origin storefront-build
NEW=$(git rev-parse FETCH_HEAD)
OLD=$(cat "$DEST/.deployed_build" 2>/dev/null || echo none)
if [ "${1:-}" = "--if-changed" ] && [ "$NEW" = "$OLD" ]; then
  exit 0
fi
git reset -q --hard FETCH_HEAD
echo "$(date '+%F %T') deploying storefront build $(cat BUILD_SHA 2>/dev/null) (bundle ${NEW:0:7})"

mkdir -p "$DEST"
# Dependencies: copy alongside, then swap in (no rsync on the server).
rm -rf "$MODULES.new" "$MODULES.old"
cp -a "$CACHE/node_modules" "$MODULES.new"
[ -d "$MODULES" ] && mv "$MODULES" "$MODULES.old"
mv "$MODULES.new" "$MODULES"
rm -rf "$MODULES.old"
# App files: clear the app root (keeping cPanel's tmp/) and unpack the new build.
find "$DEST" -mindepth 1 -maxdepth 1 ! -name tmp ! -name .deployed_build -exec rm -rf {} +
tar -C "$CACHE" --exclude=./.git --exclude=./node_modules -cf - . | tar -C "$DEST" -xf -
echo "$NEW" > "$DEST/.deployed_build"

# Cron runs with a minimal PATH (no /usr/sbin): find the selector explicitly, else use Passenger's restart.txt.
SELECTOR=$(command -v cloudlinux-selector || ls /usr/sbin/cloudlinux-selector /usr/bin/cloudlinux-selector 2>/dev/null | head -1 || true)
if [ -z "$SELECTOR" ] || ! "$SELECTOR" restart --json --interpreter=nodejs --app-root="$APP_ROOT" >/dev/null; then
  mkdir -p "$DEST/tmp" && touch "$DEST/tmp/restart.txt"
fi
sleep 3
code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$SITE/")
if [ "$code" = "200" ]; then
  echo "✓ storefront is up ($SITE → 200)"
else
  echo "✗ storefront returned $code — check $DEST/stderr.log"
  exit 1
fi
