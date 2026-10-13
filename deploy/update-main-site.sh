#!/bin/bash
# Install the latest main-site build (windycitywares.com) into its cPanel Node.js app, then restart it.
# The build is made by GitHub Actions in repo windycitywares/wcw-main-site and published to its
# `site-build` branch (a ready-to-run Next.js standalone bundle).
#
#   bash ~/repos/wcw-portal/deploy/update-main-site.sh               # always redeploy
#   bash ~/repos/wcw-portal/deploy/update-main-site.sh --if-changed  # only when there's a new build (cron)
#
# Access: GitHub deploy keys work for one repo only, so wcw-main-site has its own key and an ssh alias
# `github-wcw-main` (docs/DEPLOYMENT.md → "Main site"). Without that alias plain HTTPS is used, which
# works only while the repo is public.
set -euo pipefail
export GIT_TERMINAL_PROMPT=0   # never wait for a password in cron

APP_ROOT="apps/wcw-main/site"            # cPanel Setup Node.js App → application root (windycitywares.com)
DEST="$HOME/$APP_ROOT"
# Dependencies live one level up: Node finds ~/apps/wcw-main/node_modules from ~/apps/wcw-main/site/server.js,
# and cPanel's Node selector doesn't allow a real node_modules folder inside the app root.
MODULES="$HOME/apps/wcw-main/node_modules"
CACHE="$HOME/repos/wcw-main-site-build"
NOACCESS="$HOME/.wcw-main-site-noaccess"  # log "no access" once, not every 10 minutes
SITE="https://windycitywares.com"
IF_CHANGED=0; [ "${1:-}" = "--if-changed" ] && IF_CHANGED=1

if grep -qE '^Host[[:space:]]+github-wcw-main$' "$HOME/.ssh/config" 2>/dev/null; then
  REPO="git@github-wcw-main:windycitywares/wcw-main-site.git"
else
  REPO="https://github.com/windycitywares/wcw-main-site.git"
fi

no_access() {
  if [ "$IF_CHANGED" = 1 ]; then
    [ -f "$NOACCESS" ] || echo "$(date '+%F %T') main site: can't read the site-build branch of $REPO — see docs/DEPLOYMENT.md → Main site"
    touch "$NOACCESS"; exit 0
  fi
  echo "main site: can't read the site-build branch of $REPO — see docs/DEPLOYMENT.md → Main site" >&2; exit 1
}

if [ ! -d "$CACHE/.git" ]; then
  rm -rf "$CACHE"
  git clone -q --depth 1 --branch site-build "$REPO" "$CACHE" 2>/dev/null || no_access
fi
cd "$CACHE"
git remote set-url origin "$REPO"
git fetch -q --depth 1 origin site-build 2>/dev/null || no_access
rm -f "$NOACCESS"

NEW=$(git rev-parse FETCH_HEAD)
OLD=$(cat "$DEST/.deployed_build" 2>/dev/null || echo none)
if [ "$IF_CHANGED" = 1 ] && [ "$NEW" = "$OLD" ]; then
  exit 0
fi
git reset -q --hard FETCH_HEAD
[ -f server.js ] || { echo "$(date '+%F %T') main site: build ${NEW:0:7} has no server.js, not deploying"; exit 1; }
echo "$(date '+%F %T') main site: deploying build $(cat BUILD_SHA 2>/dev/null | cut -c1-7) (bundle ${NEW:0:7})"

mkdir -p "$DEST"
# Dependencies: copy alongside, then swap in (no rsync on the server).
rm -rf "$MODULES.new" "$MODULES.old"
cp -a "$CACHE/node_modules" "$MODULES.new"
[ -d "$MODULES" ] && mv "$MODULES" "$MODULES.old"
mv "$MODULES.new" "$MODULES"
rm -rf "$MODULES.old"
# App files: clear the app root (keeping cPanel's tmp/ and any symlinked node_modules) and unpack the build.
find "$DEST" -mindepth 1 -maxdepth 1 ! -name tmp ! -name node_modules ! -name .deployed_build -exec rm -rf {} +
tar -C "$CACHE" --exclude=./.git --exclude=./node_modules -cf - . | tar -C "$DEST" -xf -
echo "$NEW" > "$DEST/.deployed_build"

# Cron runs with a minimal PATH (no /usr/sbin): find the selector explicitly, else use Passenger's restart.txt.
SELECTOR=$(command -v cloudlinux-selector || ls /usr/sbin/cloudlinux-selector /usr/bin/cloudlinux-selector 2>/dev/null | head -1 || true)
if [ -z "$SELECTOR" ] || ! "$SELECTOR" restart --json --interpreter=nodejs --app-root="$APP_ROOT" >/dev/null 2>&1; then
  mkdir -p "$DEST/tmp" && touch "$DEST/tmp/restart.txt"
fi
sleep 3
code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$SITE/" || true)
if [ "$code" = "200" ]; then
  echo "$(date '+%F %T') main site: live (${NEW:0:7})"
else
  echo "$(date '+%F %T') main site: deployed ${NEW:0:7} but $SITE returned $code — check $DEST/stderr.log"
  exit 1
fi
