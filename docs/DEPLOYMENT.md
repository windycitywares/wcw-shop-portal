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
WordPress backups, and the current single-page site (`public_html/index.html`). **Back up
`public_html/index.html` before the storefront takes over the main domain.**

Target layout:

| URL | App | Folder |
|---|---|---|
| `https://windycitywares.com` | Next.js storefront (Node 20) | `~/apps/wcw-storefront` |
| `https://api.windycitywares.com` | FastAPI (Python 3.11) | `~/repos/wcw-portal/backend` |

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

1. cPanel → **Domains** → create `api.windycitywares.com` (document root e.g. `api.windycitywares.com`).
2. **Setup Python App** → Create application:
   - Python version **3.11.17** · Application root `repos/wcw-portal/backend`
   - Application URL `api.windycitywares.com` · Startup file `passenger_wsgi.py` · Entry point `application`
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
   #   CORS_ORIGINS=["https://windycitywares.com","https://www.windycitywares.com"]
   #   ADMIN_EMAIL=...  ADMIN_PASSWORD=...
   alembic upgrade head
   python -m app.seed
   ```
4. **Restart** the app in Setup Python App. Check `https://api.windycitywares.com/health` → `{"status":"ok"}`.

## 4. Storefront (Setup Node.js App)

The 2 GB memory limit is too small for `next build`, so build elsewhere (your PC, or GitHub Actions)
and upload only the output.

```bash
cd frontend
# .env.production
#   NEXT_PUBLIC_SITE_URL=https://windycitywares.com
#   NEXT_PUBLIC_API_URL=https://api.windycitywares.com/api/v1
npm ci && npm run build
```

Upload to `~/apps/wcw-storefront/`:
- everything inside `.next/standalone/` (includes `server.js`)
- `.next/static/` → `~/apps/wcw-storefront/.next/static/`
- `public/` → `~/apps/wcw-storefront/public/`

cPanel → **Setup Node.js App** → Create: Node **20**, mode Production, root `apps/wcw-storefront`,
URL `windycitywares.com`, startup file `server.js`. Start it.

## Updating

- API: `cd ~/repos/wcw-portal && git pull`, activate the venv, `pip install -r backend/requirements.txt`,
  `alembic upgrade head`, then Restart in Setup Python App.
- Storefront: rebuild, re-upload `standalone` + `static`, Restart in Setup Node.js App.

## Static-only fallback

`NEXT_OUTPUT=export npm run build` writes plain files to `out/` for `public_html`. Pages are then
fixed at build time (no live search/filters or new products until you rebuild).
