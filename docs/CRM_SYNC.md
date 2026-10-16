# CRM sync (shop → crm.windycitywares.com)

The shop tells the CRM about customer accounts, orders and newsletter consent, so the team sees each customer's
orders and consent in the CRM. The event format is defined by the CRM: `wcw-crm-portal/docs/SHOP_EVENTS.md`.

## How it works

1. **Recording** — `app/core/crm_events.py` hooks every database session. When an order, a customer account or a
   newsletter row is written through the ORM, it adds a `crm_outbox` row ("order 987 changed") **in the same
   transaction**. Nothing is recorded while the sync is off or while Admin → Test mode is on.
2. **Sending** — the `crm_sync` job (`python -m app.scripts.run_jobs --only crm_sync`, run by the deploy cron) reads
   each changed record *as it is now*, signs the event (HMAC-SHA256 with the shared secret) and posts it. Several
   changes to the same record go out as one event. Failures retry with backoff (1 min … 6 h, 12 tries); a body the
   CRM rejects (400/413/422) is marked `failed` and logged. Sent rows are purged after 30 days.

Raw SQL updates (e.g. `UPDATE orders …`) are not seen; change orders, users and subscribers through the ORM.

## Switching it on

1. CRM → Administration → **Integrations**: *Generate secret*, copy it, tick *Accept events from the shop*, save.
2. Shop server, `~/repos/wcw-shop-portal/backend/.env` (keep it `chmod 600`):
   ```ini
   CRM_WEBHOOK_URL=https://crm-api.windycitywares.com/api/v1/integrations/shop/webhook
   CRM_WEBHOOK_SECRET=<the secret from the CRM>
   ```
3. Restart the shop API (Setup Python App → Restart). From then on changes are recorded and sent on the next job
   run (every 10 minutes with the deploy cron). Check CRM → Integrations → *Recent events*.

## Read API (for the CRM's backfill)

`GET /api/v1/integrations/crm/{customers|orders|newsletter}?after_id=0&limit=200` (max 500), header
`Authorization: Bearer <CRM_API_TOKEN>`. Pages by id: pass the answer's `next_after_id` until it is `null`.
`orders` also takes `email=`. Items have the same shape as the events' `data`; newsletter items add `type`
(`newsletter.subscribed` / `newsletter.unsubscribed`). Always live data. Answers 404 while `CRM_API_TOKEN` is unset;
bad tokens are rate-limited per IP.

To switch it on, add a long random value to the shop's `backend/.env` and the same value in CRM → Integrations →
*Shop API token*:
```ini
CRM_API_TOKEN=<python -c "import secrets; print(secrets.token_urlsafe(36))">
```
The CRM uses it to bring in customers and orders from before the sync was switched on.

## Checking

```sql
SELECT kind, status, count(*) FROM crm_outbox GROUP BY 1, 2;            -- what is waiting / sent / failed
SELECT * FROM crm_outbox WHERE status IN ('pending','failed') ORDER BY id DESC LIMIT 20;
```
