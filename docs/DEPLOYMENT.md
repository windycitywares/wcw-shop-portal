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
| `https://shop-api.windycitywares.com` | FastAPI (Python 3.11) | `~/repos/wcw-shop-portal/backend` | build-out → stays |

## 1. Database

cPanel → **PostgreSQL Databases**: create database `windycit_wcw` and user `windycit_wcw`, then add the
user to the database with **ALL PRIVILEGES**.
Connection string: `postgresql+asyncpg://windycit_wcw:PASSWORD@localhost:5432/windycit_wcw`

## 2. Get the code from GitHub (private repo)

> **Renamed on 16 Oct 2026:** the repo is now `windycitywares/wcw-shop-portal` (it was `wcw-portal`; GitHub
> redirects the old address). The live server was set up before the rename, so its checkout is still
> `~/repos/wcw-portal` with app root `repos/wcw-portal/backend` — that's fine: the deploy scripts find their
> own folder, and `auto-deploy.sh` points the git remote at the new name by itself. Renaming the server
> folder too is optional: see [Renaming the server folder](#renaming-the-server-folder-optional).

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
   mkdir -p ~/repos && cd ~/repos && git clone git@github-wcw:windycitywares/wcw-shop-portal.git
   ```
   (cPanel → Git Version Control will now list the repo too.)

## 3. API (Setup Python App)

> **Live since 2026-10-11** at `https://shop-api.windycitywares.com` — database `windycit_wcw`, user
> `windycit_wcwapp`, app root `repos/wcw-shop-portal/backend`, startup file `wsgi.py`. Secrets are in
> `backend/.env` and `~/.wcw-secrets` (both chmod 600, never committed).

1. cPanel → **Domains** → create `shop-api.windycitywares.com` (document root e.g. `shop-api.windycitywares.com`).
2. **Setup Python App** → Create application:
   - Python version **3.11.17** · Application root `repos/wcw-shop-portal/backend`
   - Application URL `shop-api.windycitywares.com` · Startup file **`wsgi.py`** · Entry point `application`
   - (cPanel writes its own `passenger_wsgi.py` that loads `wsgi.py` — don't name our file `passenger_wsgi.py`,
     or the generated loader imports itself and every request fails with a RecursionError.)
3. Copy the "source …/activate" command it shows, then in Terminal:
   ```bash
   source /home2/windycit/virtualenv/repos/wcw-shop-portal/backend/3.11/bin/activate   # path shown by cPanel
   cd ~/repos/wcw-shop-portal/backend
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
4. **Restart** the app in Setup Python App. Check `https://shop-api.windycitywares.com/health` → `{"status":"ok"}`.

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
3. `bash ~/repos/wcw-shop-portal/deploy/update-storefront.sh` — installs the latest build and restarts.

Check: `https://shop.windycitywares.com/robots.txt` says `Disallow: /` while building.

## Updating (automatic) — Admin → Deployments

**Recent versions and Restore.** The page lists the latest version and the three before it (V1–V3), each described by its pull request, with the
live one on top. *Restore this version* puts an earlier one back on the next cron run: the API code goes back to that commit (migrations
are **not** run or undone, so restore is meant for changes that only add to the database) and the storefront comes back from the copy
`update-storefront.sh` saved when it installed that build (`~/apps/wcw-storefront-releases`, the last five). The version is then
**held**: newer API and storefront builds are not installed until *Return to latest*. A restore that fails leaves the previous version running
and releases the hold. windycitywares.com is not part of a restore. Every restore and return is in the audit log.

A cron job runs **every minute** (`crontab -l`):

```
* * * * * bash $HOME/repos/wcw-shop-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-deploy.log 2>&1
```

(Servers set up earlier had `*/10 * * * *`; that still works, but *Deploy now* then waits up to 10 minutes.
Change it in cPanel → **Cron Jobs**.)

Each run first asks **Admin → Deployments** whether to look for updates now:

- **Automatic** — every N minutes (default 10).
- **At set times** — e.g. `02:00` only (store time: America/Chicago unless changed in Admin → Settings → General); a time missed while the server was down is
  caught up on the next run.
- **Paused** — never on its own.
- **Deploy now** — on the next run (within a minute), whatever the mode. *Cancel* takes it back before it starts.

When it looks:

- **API** — when `main` has new commits it runs `deploy/update-api.sh`: install packages, run the
  tests, run migrations, restart, check `/health`. If install or tests fail, the previous code is
  restored and the running API is untouched.
- **Storefront** — when Actions has published a new build it runs `deploy/update-storefront.sh`.
- **Main site** — when [wcw-main-site](https://github.com/windycitywares/wcw-main-site) Actions has
  published a new build it runs `deploy/update-main-site.sh` (see [Main site](#main-site-windycitywarescom)).
- The result ("API updated to …", "storefront build …", "already up to date" or what failed) is shown on
  Admin → Deployments, with the versions now live and the last lines of the log.

If the gate can't answer (the database is down, or the API code is older than the gate), the script looks for
updates anyway, so deploys never get stuck. Gate errors go to `~/logs/wcw-deploy-gate.err`.
History: `~/logs/wcw-deploy.log`. Run any of these scripts by hand in cPanel → Terminal to deploy immediately.

So the release flow is: **merge a PR into `main` → live at the next check (default within 10 minutes), or click
*Deploy now* (within a minute).**

## Background jobs

The same cron line also runs `deploy/run-jobs.sh` every 5 minutes and after every update check, which calls
`python -m app.scripts.run_jobs`: queued emails and retries, abandoned-cart reminders, review requests,
back-in-stock emails, expiry of unpaid card orders, the Monday 7am owner digest (Settings → Digest) and a nightly
clean-up of analytics older than the retention period. It is safe to run by hand and two runs never overlap.

```bash
bash ~/repos/wcw-shop-portal/deploy/run-jobs.sh                 # whatever is due
bash ~/repos/wcw-shop-portal/deploy/run-jobs.sh --only outbox   # just some jobs
bash ~/repos/wcw-shop-portal/deploy/run-jobs.sh --force-digest  # send the weekly email now
```

It prints a line to `~/logs/wcw-deploy.log` only when it did something or a job failed.

## Main site (windycitywares.com)

windycitywares.com runs the brand site from the separate repo **windycitywares/wcw-main-site**
(Next.js; product data from this repo's API). It's built like the storefront: GitHub Actions in that
repo publishes a ready-to-run bundle to its `site-build` branch, and the 10-minute cron job runs
`deploy/update-main-site.sh`, which installs it into a cPanel Node.js app and restarts it.
So: **merge to wcw-main-site `main` → live within ~10–15 minutes.**

| | |
|---|---|
| Node.js app | Node 20 · app root `apps/wcw-main/site` · URL `windycitywares.com` · startup file `server.js` |
| Dependencies | `~/apps/wcw-main/node_modules` (one level up, like the storefront) |
| Build cache | `~/repos/wcw-main-site-build` (clone of the `site-build` branch) |
| Old static homepage | `public_html/index.static.html` and `index.old.html` (not served) |

One-time server setup (after the first `site-build` exists):

```bash
git -C ~/repos/wcw-shop-portal fetch -q origin main
git -C ~/repos/wcw-shop-portal show origin/main:deploy/update-main-site.sh > ~/.wcw-update-main-site.sh
bash ~/.wcw-update-main-site.sh                                # installs the build into apps/wcw-main/site
cloudlinux-selector create --interpreter=nodejs --version=20 --app-root=apps/wcw-main/site \
  --domain=windycitywares.com --app-uri=/ --app-mode=production --startup-file=server.js
mv ~/public_html/index.html ~/public_html/index.static.html   # LiteSpeed would serve it instead of the app
```

**Access to the repo.** While wcw-main-site is public the server reads it over HTTPS. Before making it
private, give the server its own deploy key (a key can be a deploy key on one repo only):

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

The script uses that alias automatically once it's in `~/.ssh/config`. Without access the log says
"main site: can't read …" once and the running site stays as it is.

**If windycitywares.com shows "Index of /":** changing the PHP version (MultiPHP Manager) rewrites
`public_html/.htaccess` and drops the app's Passenger lines. The script checks for this on every
10-minute run and repairs it by stopping and starting the app (the PHP lines stay; the old file is kept as
`~/.htaccess-before-repair`). To fix it by hand: Setup Node.js App → windycitywares.com → Stop, then Start.

Deploy right away: `bash ~/repos/wcw-shop-portal/deploy/update-main-site.sh`. Log: `~/logs/wcw-deploy.log`;
app errors: `~/apps/wcw-main/site/stderr.log`.
Roll back to the old static page: Setup Node.js App → stop the windycitywares.com app, then
`mv ~/public_html/index.static.html ~/public_html/index.html`.

At go-live the store takes over the main domain: stop this app and remove the `update-main-site.sh`
line from `deploy/auto-deploy.sh` at the same time.

## Test mode (Admin → Test mode)

Admins can switch the whole shop between the **live** data and a **test copy** of it. The copy is a second schema,
`wcw_test`, in the same database (no extra cPanel database needed; the database user must be allowed to create
schemas, which the owner of a cPanel database is). Turning test on always copies the live data afresh; "Copy live
data again" refreshes it; after switching back to live the copy can be deleted.

While test mode is on:
- every page shows a "Test mode" banner; everyone is signed out by a switch and signs in again;
- only staff and the customer addresses listed on the Test mode page ("Who can sign in") can sign in: the copy
  holds every live customer and their password, so a copied shopper is otherwise refused. Accounts created while
  testing (a tester signing up) can sign in again;
- emails never reach customers: all of them go to the test inbox set on the Test mode page (or nowhere);
- card payments use `STRIPE_TEST_SECRET_KEY` / `STRIPE_TEST_WEBHOOK_SECRET` from `backend/.env` (no real charges;
  without them only the no-charge "Test payment" is offered). Live Stripe events still update the live data;
- ids and order numbers in the copy start 1,000,000 above live, so test records are easy to tell apart.

After a deploy with a migration, `update-api.sh` refreshes the copy (`python -m app.scripts.test_env sync-if-active`).
Emergency switch back: `python -m app.scripts.test_env live`.

## Backups (Admin → Backups)

Every day after the hour set in Admin → Backups (shop time), the jobs cron dumps the **live** data (`pg_dump`, the
`public` schema only, never the test copy), encrypts it with AES-256-GCM and commits it to `backups/` in a
**private** GitHub repository, keeping only the newest few (5 by default). Older backups are dropped from the
repository's history too, so they really go away. "Back up now" in the admin does the same on demand.

Setup, once:
1. On GitHub create a **private** repository, e.g. `windycitywares/wcw-backups` (the shop refuses a public one).
2. Create a fine-grained personal access token: Repository access → only that repository; Permissions →
   Contents: Read and write. Copy it.
3. In `backend/.env` on the server set `BACKUP_GITHUB_TOKEN=` (the token) and `BACKUP_PASSPHRASE=` (a long random
   phrase, at least 12 characters). **Store the passphrase in your password manager as well**: without it no
   backup can be opened. If `pg_dump` isn't on the PATH, set `BACKUP_PG_DUMP=` to its full path.
4. In Admin → Backups enter the repository, choose the hour and how many to keep, turn backups on, and press
   "Back up now" to check everything works.

Restore a backup from the admin: Admin → Backups → **Restore** next to a backup. Type the random word shown to
confirm. The shop first makes a fresh backup of the current data (so the restore can be undone), then restores in
one transaction (a failure changes nothing) and runs the migrations. It refuses while Test mode is on or a test copy
exists, and while the scheduled jobs run. `pg_restore` is looked for next to `pg_dump`; set `BACKUP_PG_RESTORE` to
its full path if needed.

Restore by hand (e.g. if the admin itself is down):
```bash
# download backups/wcw-backup-YYYYMMDD-HHMMSS.dump.enc from the GitHub repository, then on the server:
cd ~/repos/wcw-shop-portal/backend && source ~/virtualenv/repos/wcw-shop-portal/backend/3.11/bin/activate
python -m app.scripts.backup decrypt wcw-backup-YYYYMMDD-HHMMSS.dump.enc restore.dump
pg_restore --clean --if-exists --no-owner --no-privileges -h localhost -U <db user> -d <database> restore.dump
rm restore.dump   # it holds customer data
```
Restoring replaces the live tables with the backup: put the shop in maintenance (or at least stop the cron) first.

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

## Renaming the server folder (optional)

Only needed if you want the server folder to match the repo name. The API is briefly down (a minute or two)
while the Python app is recreated, so do it at a quiet time. In cPanel:

1. **Terminal** — move the checkout (the `.env` and uploaded files inside it move along):
   ```bash
   mv ~/repos/wcw-portal ~/repos/wcw-shop-portal
   git -C ~/repos/wcw-shop-portal remote set-url origin git@github-wcw:windycitywares/wcw-shop-portal.git
   ```
2. **Setup Python App** — the application root of an existing app can't be changed, so: note the old app's
   settings, **delete** it (this doesn't delete files), then **create** it again with application root
   `repos/wcw-shop-portal/backend`, URL `shop-api.windycitywares.com`, startup file `wsgi.py`, entry point
   `application`, Python 3.11.17.
3. **Terminal** — install the packages into the new virtualenv and restart:
   ```bash
   source ~/virtualenv/repos/wcw-shop-portal/backend/3.11/bin/activate
   cd ~/repos/wcw-shop-portal/backend && pip install -r requirements.txt
   cloudlinux-selector restart --json --interpreter=python --app-root=repos/wcw-shop-portal/backend
   ```
4. **Cron Jobs** — change the auto-deploy line to
   `* * * * * bash $HOME/repos/wcw-shop-portal/deploy/auto-deploy.sh >> $HOME/logs/wcw-deploy.log 2>&1`.
5. Check `https://shop-api.windycitywares.com/health` and the shop, then remove the old virtualenv
   (`rm -rf ~/virtualenv/repos/wcw-portal`).


## Clean reinstall

`deploy/clean-install.sh` installs the shop from GitHub on a server that has the domains, database, deploy key and a
filled-in `~/wcw-shop.env` (see the comments at the top of the script). It creates only what is missing — the code,
the API app on `shop-api.windycitywares.com`, migrations and the admin user, the storefront app and the cron line — and
never deletes data, so it is safe to run again. Wiping the old install is a separate, manual step.
