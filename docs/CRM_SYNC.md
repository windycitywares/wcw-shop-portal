# CRM sync (shop → crm.windycitywares.com)

The shop tells the CRM about customer accounts, orders, newsletter consent and contact-form messages, so the team
sees each customer's orders and consent in the CRM — and a message sent through the contact page opens a support
ticket there (SPEC 3.5). The event format is defined by the CRM: `wcw-crm-portal/docs/SHOP_EVENTS.md`.

## How it works

1. **Recording** — `app/core/crm_events.py` hooks every database session. When an order, a customer account, a
   newsletter row or a contact message is written through the ORM, it adds a `crm_outbox` row ("order 987 changed")
   **in the same transaction**. Nothing is recorded while the sync is off. In Test mode the rows go into the Test copy's own outbox. A
   contact message is recorded once, when it arrives: opening, replying to or closing it is the shop's own
   bookkeeping and does not send anything (the CRM already has the ticket).
2. **Sending** — the `crm_sync` job (`python -m app.scripts.run_jobs --only crm_sync`, run by the deploy cron) reads
   each changed record *as it is now*, signs the event (HMAC-SHA256 with the shared secret) and posts it. Several
   changes to the same record go out as one event. Failures retry with backoff (1 min … 6 h, 12 tries); a body the
   CRM rejects (400/413/422) is marked `failed` and logged. Sent rows are purged after 30 days.
   **Test mode:** the job sends the live outbox always, and the Test copy's outbox as well when the copy exists. Test
   events carry the id prefix `shop-test-`; the CRM files them in *its* Test copy (and drops them if it has none), so a
   test signup or order appears in the CRM's test data and never in its live data. Needs the CRM release that
   understands the prefix — deploy the CRM first.

Raw SQL updates (e.g. `UPDATE orders …`) are not seen; change orders, users, subscribers and messages through the
ORM.

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

`GET /api/v1/integrations/crm/{contacts|customers|orders|newsletter|products}?after_id=0&limit=200` (max 500), header
`Authorization: Bearer <CRM_API_TOKEN>`. Pages by id: pass the answer's `next_after_id` until it is `null`.
`orders` also takes `email=`. Items have the same shape as the events' `data`; newsletter items add `type` and `at` (when they joined or left)
(`newsletter.subscribed` / `newsletter.unsubscribed`). Always live data. Answers 404 while `CRM_API_TOKEN` is unset;
bad tokens are rate-limited per IP.

`products` is the published catalog, for the CRM's deal-line picker: `q` searches name, SKU or slug (case-insensitive).
Each item carries `id` (the line's `shop_product_id`), `sku`, `name`, `slug`, `price`, `compare_at_price`, `currency`,
`status`, `stock_status`, `parent_id` (set on a variant) and `image`. `price` is the base price — a starting unit price
the salesperson can adjust on the deal.

To switch it on, add a long random value to the shop's `backend/.env` and the same value in CRM → Integrations →
*Shop API token*:
```ini
CRM_API_TOKEN=<python -c "import secrets; print(secrets.token_urlsafe(36))">
```
The CRM uses it to bring in customers and orders from before the sync was switched on.

## Opt-outs from the CRM

The one thing the CRM writes back. When someone leaves the list in the CRM (a campaign's unsubscribe link, or
staff unsubscribing, removing or deleting them), the CRM calls

`POST /api/v1/integrations/crm/newsletter/opt-out` with `{"email": "…", "at": "<ISO time>"}` and the same
`Authorization: Bearer <CRM_API_TOKEN>`.

The shop marks that address unsubscribed on the live data, so its own mail (cart reminders, the welcome offer)
stops too. It answers `{"result": "unsubscribed" | "already" | "unknown"}`; repeating it is harmless. Signing up
again on the shop is the person's own fresh consent and works as before. The change goes back to the CRM as a
normal `newsletter.unsubscribed` event, which the CRM already has, so nothing loops.

## Checking

```sql
SELECT kind, status, count(*) FROM crm_outbox GROUP BY 1, 2;            -- what is waiting / sent / failed
SELECT * FROM crm_outbox WHERE status IN ('pending','failed') ORDER BY id DESC LIMIT 20;
```
