#!/bin/bash
# Fresh install of the shop on the HostItBro server, straight from GitHub. Safe to run again: it creates only what
# is missing and never deletes data.
#
# Before running (once, in cPanel):
#   - Domains: shop.windycitywares.com, shop-api.windycitywares.com, media.windycitywares.com (with SSL).
#   - PostgreSQL Databases: the database and user named in DATABASE_URL, user added with ALL PRIVILEGES.
#   - The deploy key in ~/.ssh/config as Host github-wcw (docs/DEPLOYMENT.md → "Get the code").
#   - A filled-in backend .env at ~/wcw-shop.env (chmod 600). It is copied into the checkout; never committed.
#
#   bash clean-install.sh            # run from anywhere, e.g. after: curl … or copying it to ~
set -euo pipefail

REPO="$HOME/repos/wcw-shop-portal"
APP_ROOT="repos/wcw-shop-portal/backend"
API_DOMAIN="shop-api.windycitywares.com"
SHOP_DOMAIN="shop.windycitywares.com"
ENV_SRC="$HOME/wcw-shop.env"
VENV="$HOME/virtualenv/$APP_ROOT/3.11"
CRON_LINE='* * * * * bash $HOME/repos/wcw-shop-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-deploy.log 2>&1'

step() { echo; echo "== $*"; }
mkdir -p "$HOME/repos" "$HOME/apps" "$HOME/logs"

step "Code"
if [ -d "$REPO/.git" ]; then
  git -C "$REPO" fetch -q origin && git -C "$REPO" checkout -q main && git -C "$REPO" reset -q --hard origin/main
else
  git clone -q git@github-wcw:windycitywares/wcw-shop-portal.git "$REPO"
fi
git -C "$REPO" log --oneline -1

step "Settings (.env)"
if [ ! -f "$REPO/backend/.env" ]; then
  [ -f "$ENV_SRC" ] || { echo "Missing $ENV_SRC — create it first (see backend/.env.example)"; exit 1; }
  install -m 600 "$ENV_SRC" "$REPO/backend/.env"
fi
grep -q '^DATABASE_URL=' "$REPO/backend/.env" || { echo "DATABASE_URL is not set in backend/.env"; exit 1; }

step "API app ($API_DOMAIN)"
if [ ! -d "$VENV" ]; then
  cloudlinux-selector create --json --interpreter python --version 3.11 --app-root "$APP_ROOT" \
    --domain "$API_DOMAIN" --app-uri / --startup-file wsgi.py --entry-point application
  echo
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
cd "$REPO/backend"
pip install -q -r requirements.txt
alembic upgrade head
python -m app.seed
mkdir -p media
cloudlinux-selector restart --json --interpreter python --app-root "$APP_ROOT"; echo
deactivate

step "Storefront ($SHOP_DOMAIN)"
if [ ! -d "$HOME/apps/wcw-storefront" ]; then
  cloudlinux-selector create --json --interpreter=nodejs --version=20 --app-root=apps/wcw-storefront \
    --domain="$SHOP_DOMAIN" --app-uri=/ --app-mode=production --startup-file=server.js
  echo
fi
bash "$REPO/deploy/update-storefront.sh"

step "Cron"
if ! crontab -l 2>/dev/null | grep -qF 'repos/wcw-shop-portal/deploy/auto-deploy.sh'; then
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
fi
crontab -l | grep auto-deploy

step "Check"
sleep 5
for url in "https://$API_DOMAIN/health" "https://$SHOP_DOMAIN/"; do
  printf '%s %s\n' "$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$url" || true)" "$url"
done
echo "Done. Sign in at https://$SHOP_DOMAIN/admin with ADMIN_EMAIL from the .env."
