"""Batch 5 API tests against PostgreSQL: consent-based tracking, reports and suggestions, CSV exports, scheduled jobs."""

import argparse
import asyncio
import csv
import io
import unittest
import uuid
from datetime import timedelta

from tests.integration_support import IPHONE, RUN, item, reset_limits, skip_unless_db, world

REPORTS = ("overview", "sales", "products", "traffic", "funnel", "behavior", "performance", "customers", "promotions",
           "inventory", "catalog", "suggestions")
EXPORTS = ("sales", "products", "traffic", "funnel", "customers", "promotions", "inventory", "catalog")


def setUpModule():
    if RUN:
        world()


def visit_id() -> str:
    return uuid.uuid4().hex[:24]


@skip_unless_db
class TrackingTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def send(self, session_id, visitor_id, events, landing=None, headers=IPHONE):
        body = {"session_id": session_id, "visitor_id": visitor_id, "events": events}
        if landing:
            body["landing"] = landing
        return self.w.client.post("/api/v1/events", json=body, headers=headers)

    def test_events_are_cleaned_and_anonymous(self):
        w = self.w
        p = w.product()
        sid, vid = visit_id(), visit_id()
        r = self.send(sid, vid, [
            {"type": "page_view", "path": "/es/product/oak-urn?utm_source=x&email=a@b.com#top"},
            {"type": "product_view", "path": f"/product/{p['slug']}", "product_id": p["id"]},
            {"type": "search", "path": "/search", "data": {"q": "  Oak   URN ", "results": 3}},
            {"type": "search", "data": {"q": "me@example.com"}},  # looks like an email: dropped
            {"type": "page_view", "path": "/order/secret-token-123"},
            {"type": "made_up_event"},
        ], landing={"path": "/es/?gclid=123", "referrer": "https://www.google.com/search?q=urns", "locale": "es"})
        self.assertEqual(r.status_code, 204)
        visit = w.sql("SELECT channel, device, browser, landing_path, page_views FROM analytics_sessions WHERE id = :id", id=sid)[0]
        self.assertEqual(visit, {"channel": "organic_search", "device": "mobile", "browser": "Safari", "landing_path": "/", "page_views": 2})
        events = w.sql("SELECT type, path, data FROM analytics_events WHERE session_id = :id ORDER BY id", id=sid)
        self.assertEqual([e["type"] for e in events], ["page_view", "product_view", "search", "page_view"])
        self.assertEqual(events[0]["path"], "/product/oak-urn")
        self.assertEqual(events[2]["data"], {"q": "oak urn", "results": 3})
        self.assertEqual(events[3]["path"], "/order/:token")
        self.assertNotIn("example.com", str(events))

        # Someone else can't add events to this visit by guessing its id.
        self.send(sid, visit_id(), [{"type": "page_view", "path": "/"}])
        self.assertEqual(w.value("SELECT count(*) FROM analytics_events WHERE session_id = :id", id=sid), 4)

    def test_bots_and_consent(self):
        from app.core.config import get_settings

        w = self.w
        sid = visit_id()
        self.send(sid, visit_id(), [{"type": "page_view", "path": "/"}], headers={"user-agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"})
        if not get_settings().analytics_accept_bots:
            self.assertEqual(w.value("SELECT count(*) FROM analytics_sessions WHERE id = :id", id=sid), 0)
        before = w.value("SELECT COALESCE(sum(accepted), 0) FROM consent_daily")
        self.assertEqual(w.client.post("/api/v1/events/consent", json={"accepted": True}).status_code, 204)
        self.assertEqual(w.value("SELECT COALESCE(sum(accepted), 0) FROM consent_daily"), before + 1)
        # Bad input never shows the visitor an error page, but nothing is stored.
        self.assertEqual(self.send("short", "id", [{"type": "page_view"}]).status_code, 422)


@skip_unless_db
class ReportTests(unittest.TestCase):
    """Loads the demo shop history (DEMO- orders, @demo.example customers) for these tests, then removes it."""

    @classmethod
    def setUpClass(cls):
        from app.domain.timeutil import resolve_range, store_today
        from app.scripts import demo_data

        cls.w = world()
        asyncio.run(demo_data.load(demo_data.build(days=60)))
        end = store_today()
        cls.range = {"start": (end - timedelta(days=59)).isoformat(), "end": end.isoformat()}
        cls.rng = resolve_range(end - timedelta(days=59), end)

    @classmethod
    def tearDownClass(cls):
        from app.scripts import demo_data

        asyncio.run(demo_data.remove())

    def report(self, name, **params):
        r = self.w.get(f"/admin/reports/{name}", self.w.admin, **{**self.range, **params})
        self.assertEqual(r.status_code, 200, f"{name}: {r.text[:500]}")
        self.assertEqual(r.headers["cache-control"], "no-store")
        return r.json()

    def test_every_report_answers(self):
        for name in REPORTS:
            with self.subTest(report=name):
                data = self.report(name)
                self.assertIsInstance(data, dict)
                if name not in ("inventory", "catalog"):
                    self.assertEqual(data["range"]["days"], 60)

    def test_sales_match_the_orders_table(self):
        w = self.w
        expected = w.sql("""
            SELECT count(*) AS orders, COALESCE(sum(grand_total), 0) AS gross FROM orders
            WHERE paid_at >= :s AND paid_at < :e AND status <> 'cancelled'
        """, s=self.rng.start_utc, e=self.rng.end_utc)[0]
        sales = self.report("sales")
        self.assertGreater(expected["orders"], 20)  # the demo data really is in range
        self.assertEqual(sales["totals"]["orders"], expected["orders"])
        self.assertAlmostEqual(sales["totals"]["gross"], float(expected["gross"]), places=2)
        self.assertEqual(len(sales["series"]), 60)
        self.assertEqual(sum(p["orders"] for p in sales["series"]), expected["orders"])
        self.assertAlmostEqual(sales["totals"]["net"], sales["totals"]["gross"] - sales["totals"]["refunds"], places=2)
        overview = self.report("overview")
        kpis = {k["key"]: k for k in overview["kpis"]}
        self.assertEqual(kpis["orders"]["value"], expected["orders"])
        for key in ("net", "orders", "aov", "conversion_rate", "visitors", "new_customers", "refund_rate"):
            self.assertIn(key, kpis)
            self.assertIn("previous", kpis[key])

    def test_suggestions_are_actionable(self):
        data = self.report("suggestions")
        self.assertTrue(data["items"])
        for s in data["items"]:
            self.assertIn(s["severity"], ("critical", "warning", "opportunity", "info", "success"))
            self.assertTrue(s["title"] and s["detail"])
            if s.get("href"):
                self.assertTrue(s["href"].startswith("/admin"), s["href"])
        self.assertEqual(sum(data["counts"].values()), len(data["items"]))

    def test_exports(self):
        for kind in EXPORTS:
            with self.subTest(kind=kind):
                r = self.w.get(f"/admin/reports/export/{kind}.csv", self.w.admin, **self.range)
                self.assertEqual(r.status_code, 200, r.text[:300])
                self.assertTrue(r.headers["content-type"].startswith("text/csv"))
                self.assertIn("attachment", r.headers["content-disposition"])
                rows = list(csv.reader(io.StringIO(r.text)))
                self.assertTrue(rows and rows[0])
        self.assertEqual(self.w.get("/admin/reports/export/secrets.csv", self.w.admin).status_code, 422)

    def test_staff_only(self):
        w = self.w
        for name in ("overview", "customers"):
            self.assertEqual(w.get(f"/admin/reports/{name}").status_code, 401)
            self.assertEqual(w.get(f"/admin/reports/{name}", w.customer).status_code, 403)
            self.assertEqual(w.get(f"/admin/reports/{name}", w.publisher).status_code, 403)

    def test_dates_are_forgiving(self):
        swapped = self.report("sales", start=self.range["end"], end=self.range["start"])
        self.assertEqual(swapped["range"]["days"], 60)
        self.assertEqual(self.w.get("/admin/reports/sales", self.w.admin, start="not-a-date").status_code, 422)


@skip_unless_db
class JobTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_all_jobs_run_cleanly(self):
        from app.scripts import run_jobs

        results = asyncio.run(run_jobs.run())
        self.assertEqual(set(results), set(run_jobs.JOBS))
        for name, result in results.items():
            self.assertFalse(isinstance(result, dict) and "error" in result, f"{name}: {result}")
        self.assertEqual(set(asyncio.run(run_jobs.run({"outbox"}))), {"outbox"})

    def test_overlapping_runs_wait_their_turn(self):
        async def go():
            from sqlalchemy import text

            from app.core.database import engine
            from app.scripts import run_jobs

            async with engine.connect() as holder:
                await holder.execute(text("SELECT pg_advisory_lock(:k)"), {"k": run_jobs.LOCK_KEY})
                try:
                    return await run_jobs.run()
                finally:
                    await holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": run_jobs.LOCK_KEY})

        self.assertEqual(asyncio.run(go()), {"skipped": "another run is in progress"})

    def test_retention_keeps_recent_visits(self):
        w = self.w
        old, new = visit_id(), visit_id()
        w.sql("""INSERT INTO analytics_sessions (id, visitor_id, started_at, last_seen_at)
                 VALUES (:old, 'v', now() - interval '500 days', now() - interval '500 days'), (:new, 'v', now(), now())""", old=old, new=new)
        w.sql("INSERT INTO analytics_events (session_id, type, created_at) VALUES (:old, 'page_view', now() - interval '500 days')", old=old)

        async def purge(session):
            from app.services import retention

            return await retention.purge(session)

        deleted = w.db(purge)
        self.assertGreaterEqual(deleted["analytics_sessions"], 1)
        self.assertEqual(w.value("SELECT count(*) FROM analytics_sessions WHERE id IN (:old, :new)", old=old, new=new), 1)

    def test_weekly_digest(self):
        from app.scripts import run_jobs

        w = self.w
        owner = w.email("owner")
        w.put("/admin/settings/digest", {"enabled": True, "recipients": [owner]}, w.admin)
        try:
            w.place(w.email("digest"), [item(w.product())])
            result = asyncio.run(run_jobs.run({"digest"}, argparse.Namespace(force_digest=True)))["digest"]
            if result.get("reason") != "already sent":  # one digest per day
                self.assertEqual(result["sent"], 1, result)
                mail = w.mails_to(owner, "your week")[0]
                self.assertIn("Net revenue", mail.text)
        finally:
            w.put("/admin/settings/digest", {"recipients": []}, w.admin)


if __name__ == "__main__":
    unittest.main()
