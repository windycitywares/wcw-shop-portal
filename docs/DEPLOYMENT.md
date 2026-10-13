# Deploying to HostItBro (cPanel shared hosting)

## The server (checked 2026-10-11)

| | |
|---|---|
| Plan | HostItBro Managed Web Hosting SSD – Business |
| Server | `bharat.hostitbro.com` · CloudLinux + LiteSpeed · cPanel 138 |
| Account / home | `windycit` · `/home2/windycit` |
| Python | Setup Python App: **3.11.17** (use this), also 2.7, 3.5–3.9 |
| Node.js | Setup Node.js App: 18, 19, **20** (recommended), 22, 24 |
| PostgreSQL | **13.23** · created from cPanel → PostgreSQL Databases · **no extensions available** (no `ltree`, no contrib) — the app doesn't need any |
| Git | Git Version Control in cPanel, git 2.56, SSH + Terminal enabled |
| Limits | 2 GB RAM, 30 entry processes, 200 processes, unlimited disk/bandwidth |
| SSL | Active on windycitywares.com |

Already on the account — leave alone: `crm.windycitywares.com` (its own folder + MySQL databases),
WordPress backups, and the current single-page site (`public_html/index.html`).

### Plan: build on a subdomain, then move to the main domain

While the store is being built, **windycitywares.com keeps serving the existing `index.html`** and
the new store runs on `shop.windycitywares.com`, hidden from search engines. When everything is
ready, follow [Go live on the main domain](#go-live-on-the-main-domain).

| URL | App | Folder | Phase |
|---|---|---|---|
| `https://windycitywares.com` | existing `index.html` | `public_html` | unchanged until launch |
| `https://shop.windycitywares.com` | Next.js storefront (Node 20) | `~/apps/wcw-storefront` | build-out |
| `https://api.windycitywares.com` | FastAPI (Python 3.11) | `~/repos/wcw-portal/backend` | build-out → stays |

## 1. Database

cPanel → **PostgreSQL Databases**: create database `windycit_wcw` and user `windycit_wcw`, then add the
user to the database with **ALL PRIVILEGES**.
Connection string: `postgresql+asyncpg://windycit_wcw:PASSWORD@localhost:5432/windycit_wcw`

## 2. Get the code from GitHub (private repo)

1. cPanel → **Terminal**: `ssh-keygen -t ed25519 -f ~/.ssh/wcw_deploy -N ""` and `cat ~/.ssh/wcw_deploy.pub`.
2. GitHub → repo **Settings → Deploy keys → Add deploy key**: paste it, leave *write access* off.
3. Back in Terminal:
   ```bash
   cat >> ~/.ssh/config <<'CFG'
   Host github-wcw
     HostName github.com
     User git
     IdentityFile ~/.ssh/wcw_deploy
   CFG
   mkdir -p ~/repos && cd ~/repos && git clone git@github-wcw:windycitywares/wcw-portal.git
   ```
   (cPanel → Git Version Control will now list the repo too.)

## 3. API (Setup Python App)

> **Live since 2026-10-11** at `https://api.windycitywares.com` — database `windycit_wcw`, user
> `windycit_wcwapp`, app root `repos/wcw-portal/backend`, startup file `wsgi.py`. Secrets are in
> `backend/.env` and `~/.wcw-secrets` (both chmod 600, never committed).

1. cPanel → **Domains** → create `api.windycitywares.com` (document root e.g. `api.windycitywares.com`).
2. **Setup Python App** → Create application:
   - Python version **3.11.17** · Application root `repos/wcw-portal/backend`
   - Application URL `api.windycitywares.com` · Startup file **`wsgi.py`** · Entry point `application`
   - (cPanel writes its own `passenger_wsgi.py` that loads `wsgi.py` — don't name our file `passenger_wsgi.py`,
     or the generated loader imports itself and every request fails with a RecursionError.)
3. Copy the "source …/activate" command it shows, then in Terminal:
   ```bash
   source /home2/windycit/virtualenv/repos/wcw-portal/backend/3.11/bin/activate   # path shown by cPanel
   cd ~/repos/wcw-portal/backend
   pip install -r requirements.txt
   cp .env.example .env && nano .env
   #   ENVIRONMENT=production
   #   DATABASE_URL=postgresql+asyncpg://windycit_wcw:PASSWORD@localhost:5432/windycit_wcw
   #   DB_USE_NULL_POOL=true
   #   JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
   #   CORS_ORIGINS=["https://shop.windycitywares.com"]
   #   ADMIN_EMAIL=...  ADMIN_PASSWORD=...
   alembic upgrade head
   python -m app.seed
   ```
4. **Restart** the app in Setup Python App. Check `https://api.windycitywares.com/health` → `{"status":"ok"}`.

## 4. Storefront (Setup Node.js App)

> **Live since 2026-10-11** at `https://shop.windycitywares.com` (hidden from search engines) — Node
> **20.20.2**, app root `apps/wcw-storefront`, startup file `server.js`. Its dependencies live in
> `~/apps/node_modules` (cPanel's Node selector doesn't allow a `node_modules` folder in the app root).

The 2 GB memory limit is too small for `next build`, so **GitHub Actions builds it**
(`.github/workflows/storefront.yml`): every PR touching `frontend/` is built, type-checked and
smoke-tested; every merge to `main` also publishes the ready-to-run bundle to the
`storefront-build` branch. Public build settings (`NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_API_URL`,
`NEXT_PUBLIC_ALLOW_INDEXING`) default to the `shop.` values and can be overridden with repository
**Variables** `SITE_URL`, `API_URL`, `ALLOW_INDEXING`.

One-time server setup (already done):
1. cPanel → Domains → `shop.windycitywares.com`.
2. `cloudlinux-selector create --interpreter=nodejs --version=20 --app-root=apps/wcw-storefront
   --domain=shop.windycitywares.com --app-uri=/ --app-mode=production --startup-file=server.js`
3. `bash ~/repos/wcw-portal/deploy/update-storefront.sh` — installs the latest build and restarts.

Check: `https://shop.windycitywares.com/robots.txt` says `Disallow: /` while building.

## Updating (automatic)

A cron job runs every 10 minutes (`crontab -l`):

```
*/10 * * * * bash $HOME/repos/wcw-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-deploy.log 2>&1
```

- **API** — when `main` has new commits it runs `deploy/update-api.sh`: install packages, run the
  tests, run migrations, restart, check `/health`. If install or tests fail, the previous code is
  restored and the running API is untouched.
- **Storefront** — when Actions has published a new build it runs `deploy/update-storefront.sh`.
- **Main site** — when [wcw-main-site](https://github.com/windycitywares/wcw-main-site) has new commits on
  `main` it runs `deploy/update-main-site.sh`, which copies that repo's files into `public_html`
  (see [Main site](#main-site-windycitywarescom)).
- History: `~/logs/wcw-deploy.log`. Run any of these scripts by hand in cPanel → Terminal to deploy
  immediately.

So the release flow is: **merge a PR into `main` → live within ~10 minutes.**

## Main site (windycitywares.com)

Until the store moves to the main domain, `public_html` serves the landing page from the separate
repo **windycitywares/wcw-main-site** (collections grid linking into `shop.`). The cron job above
publishes it: merge to that repo's `main` → live within ~10 minutes. `deploy/update-main-site.sh`
copies every file except `README.md` and dot-files into `public_html` and deletes nothing; on the first
publish the old homepage is kept as `public_html/index.old.html`.

The server needs read access to that repo, once. Either:

- **Make the repo public** (GitHub → wcw-main-site → Settings → Danger zone → Change visibility). It's
  only the public web page, and nothing else is needed; or
- **Keep it private** and give it its own deploy key (a key can be a deploy key on one repo only):
  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/wcw_main_deploy -N "" && cat ~/.ssh/wcw_main_deploy.pub
  # GitHub → wcw-main-site → Settings → Deploy keys → Add deploy key: paste it, write access off
  cat >> ~/.ssh/config <<'CFG'
  Host github-wcw-main
    HostName github.com
    User git
    IdentityFile ~/.ssh/wcw_main_deploy
  CFG
  ```

Until one of these is done, the log shows "main site: can't read …" once and the current homepage
stays as it is. Publish right away: `bash ~/repos/wcw-portal/deploy/update-main-site.sh`.
Roll back: `cp ~/public_html/index.old.html ~/public_html/index.html`.

At go-live the store takes over the main domain: remove the `update-main-site.sh` line from
`deploy/auto-deploy.sh` at the same time.

## Email and CAPTCHA

Password-reset emails and contact-form notifications go out through a HostItBro mailbox; sign-up and
the contact form are protected by Cloudflare Turnstile. Both are set in `backend/.env` (never in Git),
then the Python app is restarted (Setup Python App → Restart, or wait for the next deploy).

**Mailbox** — cPanel → Email Accounts → Create `no-reply@windycitywares.com` with a strong password.
cPanel → Email Deliverability → make sure SPF and DKIM show *Valid* for windycitywares.com (click
*Repair* if not) so Gmail and Outlook don't treat the emails as spam. Then in `backend/.env`:

```
SITE_URL=https://shop.windycitywares.com          # links in emails (change at go-live)
SMTP_HOST=mail.windycitywares.com
SMTP_PORT=465
SMTP_SECURITY=ssl
SMTP_USER=no-reply@windycitywares.com
SMTP_PASSWORD=<the mailbox password>
MAIL_FROM=no-reply@windycitywares.com
MAIL_FROM_NAME=WindyCityWares
CONTACT_TO=windycitywaresllc@gmail.com            # where contact-form messages are delivered
```

Contact messages are also saved in the `contact_messages` table, so nothing is lost if an email fails.

**Without a mailbox (current setup)** — the server's own mail system accepts mail from the app on
`localhost` without a password, and cPanel signs it with the domain's DKIM key. These non-secret
settings are in `backend/production.env` (in Git, loaded only when `ENVIRONMENT=production`):
`SITE_URL`, `SMTP_HOST=localhost`, `SMTP_PORT=25`, `SMTP_SECURITY=none`, `MAIL_FROM`, `CONTACT_TO`.
Anything set in `.env` (or an optional, untracked `backend/site.env`) overrides them.

Switch to the authenticated mailbox settings above if HostItBro ever blocks local relay.

**Turnstile** — the widget exists in Cloudflare (dash.cloudflare.com → Turnstile, hostnames
`shop.windycitywares.com`, `windycitywares.com`, `www.windycitywares.com`). The public site key and the
allowed hostnames are in `backend/production.env`. Only the **secret key** goes on the server, in
`backend/.env` (git-ignored), added by the owner:

```
TURNSTILE_SECRET=<secret key from the widget's settings>
```

The API checks each token's `success`, its `action` (`signup` or `contact`, matching the form it was
solved on) and its `hostname`. If the log says `TURNSTILE_SECRET is invalid`, the key in `.env` is wrong.
To change the secret: Cloudflare → Turnstile → the widget → Rotate secret key, then update `.env`.

Until `TURNSTILE_SECRET` is set the check is skipped (a warning is logged), so sign-up keeps working.

## Go live on the main domain

When the store is ready to replace the current homepage:

1. **Back up the old page**: File Manager → `public_html/index.html` → rename to `index.old.html`
   (or download a copy).
2. **Rebuild for the main domain**: GitHub → repo Settings → Secrets and variables → Actions →
   **Variables**: `SITE_URL=https://windycitywares.com`, `ALLOW_INDEXING=true`. Then re-run the
   Storefront workflow on `main` (Actions → Storefront → Run workflow); the server picks it up.
3. **Point the Node app at the main domain**: Setup Node.js App → edit the app → Application URL
   `windycitywares.com` → Save → Restart. (If cPanel won't change the URL, create a second app on
   `windycitywares.com` with the same folder, then stop the `shop.` one.)
4. **Allow the main domain in the API**: in `backend/.env` set
   `CORS_ORIGINS=["https://windycitywares.com","https://www.windycitywares.com","https://shop.windycitywares.com"]`
   and `SITE_URL=https://windycitywares.com` (links in emails), then Restart the Python app.
5. **Keep old links working**: cPanel → Redirects → `shop.windycitywares.com` → permanent (301) to
   `https://windycitywares.com` — or keep `shop.` serving the store, either is fine. Turn on Domains →
   **Force HTTPS Redirect** for the main domain.
6. **Check**: home, a category, a product, cart, `/admin` sign-in; `https://windycitywares.com/robots.txt`
   now lists the sitemap; submit `https://windycitywares.com/sitemap.xml` in Google Search Console.

The API, database, admin users and products don't change at launch — only the storefront's address.

## Static-only fallback

`NEXT_OUTPUT=export npm run build` writes plain files to `out/` for `public_html`. Pages are then
fixed at build time (no live search/filters or new products until you rebuild).
