# Deploying to cPanel shared hosting

The app is two pieces: the Python API and the Next.js storefront. Both run on a typical cPanel host
that offers **Setup Python App** and **Setup Node.js App** (CloudLinux), plus PostgreSQL.

Suggested layout:

| URL | What |
|---|---|
| `https://windycitywares.com` | Next.js storefront |
| `https://api.windycitywares.com` | FastAPI (subdomain) |

## 1. Database

cPanel → **PostgreSQL Databases**: create a database and user, add the user to the database.
The `ltree` extension must exist. If `alembic upgrade head` fails with *permission denied to create
extension "ltree"*, ask the host's support to run `CREATE EXTENSION ltree;` in your database.

## 2. API (Setup Python App)

1. Upload/clone the repo, e.g. to `~/wcw-portal`.
2. cPanel → **Setup Python App** → Create:
   - Python version: **3.11 or newer**
   - Application root: `wcw-portal/backend`
   - Application URL: `api.windycitywares.com`
   - Startup file: `passenger_wsgi.py` · Entry point: `application`
3. Open the terminal command cPanel shows ("Enter to the virtual environment"), then:
   ```bash
   cd ~/wcw-portal/backend
   pip install -r requirements.txt
   cp .env.example .env && nano .env
   #   ENVIRONMENT=production
   #   DATABASE_URL=postgresql+asyncpg://USER:PASS@localhost:5432/DBNAME
   #   DB_USE_NULL_POOL=true
   #   JWT_SECRET=<long random string>
   #   CORS_ORIGINS=["https://windycitywares.com"]
   alembic upgrade head
   python -m app.seed
   ```
4. **Restart** the app. Check `https://api.windycitywares.com/health` → `{"status":"ok"}`.

## 3. Storefront (Setup Node.js App)

Build on your computer (shared hosts often lack the memory for `next build`):

```bash
cd frontend
# .env.production
#   NEXT_PUBLIC_SITE_URL=https://windycitywares.com
#   NEXT_PUBLIC_API_URL=https://api.windycitywares.com/api/v1
npm ci
npm run build
```

This creates `.next/standalone`. Upload to the server (e.g. `~/wcw-storefront`):

- the contents of `.next/standalone/` (includes `server.js`)
- `.next/static/` → `~/wcw-storefront/.next/static/`
- `public/` → `~/wcw-storefront/public/`

cPanel → **Setup Node.js App** → Create: Node 20+, application root `wcw-storefront`, URL
`windycitywares.com`, startup file `server.js`. Start it.

### Static-only hosting (no Node)

`NEXT_OUTPUT=export npm run build` writes plain files to `out/`. Upload them to `public_html`.
Trade-off: pages are generated at build time only. Search/filters, new products and the sitemap won't
update until you rebuild, and product/category pages need `generateStaticParams` added.

## Updating

- API: pull, `pip install -r requirements.txt`, `alembic upgrade head`, restart the Python app.
- Storefront: rebuild locally, re-upload `standalone` + `static`, restart the Node app.
