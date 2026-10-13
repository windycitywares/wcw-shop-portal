#!/bin/bash
# Publish the main-domain landing page (repo windycitywares/wcw-main-site, branch main) into public_html.
#
#   bash ~/repos/wcw-portal/deploy/update-main-site.sh               # always republish
#   bash ~/repos/wcw-portal/deploy/update-main-site.sh --if-changed  # only when main has new commits (cron)
#
# Copies every file in the repo except README.md and dot-files (.github, .gitignore …) into
# public_html. Nothing else in public_html is touched or deleted. The homepage that was there before
# the first publish is kept as public_html/index.old.html.
#
# Access: the repo is private unless made public. GitHub deploy keys work for one repo only, so give
# this repo its own key and an ssh alias `github-wcw-main` (docs/DEPLOYMENT.md → "Main site").
# Without that alias, plain HTTPS is used, which works only while the repo is public.
set -euo pipefail
export GIT_TERMINAL_PROMPT=0   # never wait for a password in cron

CACHE="$HOME/repos/wcw-main-site"
DEST="$HOME/public_html"
STAMP="$HOME/.wcw-main-site-deployed"     # outside public_html so it isn't served
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
    [ -f "$NOACCESS" ] || echo "$(date '+%F %T') main site: can't read $REPO — see docs/DEPLOYMENT.md → Main site"
    touch "$NOACCESS"; exit 0
  fi
  echo "main site: can't read $REPO — see docs/DEPLOYMENT.md → Main site" >&2; exit 1
}

if [ ! -d "$CACHE/.git" ]; then
  rm -rf "$CACHE"
  git clone -q --depth 1 --branch main "$REPO" "$CACHE" 2>/dev/null || no_access
fi
cd "$CACHE"
git remote set-url origin "$REPO"
git fetch -q --depth 1 origin main 2>/dev/null || no_access
rm -f "$NOACCESS"

NEW=$(git rev-parse FETCH_HEAD)
OLD=$(cat "$STAMP" 2>/dev/null || echo none)
if [ "$IF_CHANGED" = 1 ] && [ "$NEW" = "$OLD" ]; then
  exit 0
fi
git reset -q --hard FETCH_HEAD
[ -f index.html ] || { echo "$(date '+%F %T') main site: no index.html in ${NEW:0:7}, not publishing"; exit 1; }
echo "$(date '+%F %T') main site: publishing $(git log --oneline -1)"

mkdir -p "$DEST"
# First publish: keep the old homepage.
if [ "$OLD" = none ] && [ -f "$DEST/index.html" ] && [ ! -f "$DEST/index.old.html" ]; then
  cp -p "$DEST/index.html" "$DEST/index.old.html"
fi
git ls-files -z | grep -zv -e '^README\.md$' -e '^\.' -e '/\.' | tar --null -T - -cf - | tar -C "$DEST" -xf -
echo "$NEW" > "$STAMP"

code=$(curl -s -m 30 -o /dev/null -w '%{http_code}' "$SITE/" || true)
if [ "$code" = "200" ]; then
  echo "$(date '+%F %T') main site: live (${NEW:0:7})"
else
  echo "$(date '+%F %T') main site: published ${NEW:0:7} but $SITE returned $code"
fi
