"""Admin → Deployments API and the cron gate, against PostgreSQL."""

import asyncio
import unittest

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


def _service():
    from app.core.database import engine
    from app.services.deploy import DeployService

    return DeployService(engine)


@skip_unless_db
class DeployTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()
        self.w.put("/admin/deploy/config", {"mode": "auto", "interval_minutes": 10}, self.w.admin)
        self.w.delete("/admin/deploy/now", self.w.admin)

    def gate(self):
        return self.w.db(lambda _s: _service().gate_begin())

    def test_admins_only(self):
        self.assertEqual(self.w.get("/admin/deploy", self.w.publisher).status_code, 403)
        self.assertEqual(self.w.post("/admin/deploy/now", None, self.w.publisher).status_code, 403)
        body = self.w.get("/admin/deploy", self.w.admin).json()
        self.assertEqual(body["mode"], "auto")
        self.assertEqual(body["timezone"], "America/Chicago")
        self.assertIn("commit", body["api"])

    def test_pause_then_deploy_now_then_resume(self):
        w = self.w
        res = w.put("/admin/deploy/config", {"mode": "paused", "interval_minutes": 10}, w.admin)
        self.assertEqual(res.json()["mode"], "paused")
        self.assertFalse(self.gate().go)
        self.assertTrue(w.get("/admin/deploy", w.admin).json()["cron_seen"])  # the gate call is a heartbeat

        queued = w.post("/admin/deploy/now", None, w.admin)
        self.assertEqual(queued.status_code, 202)
        self.assertIsNotNone(queued.json()["requested_at"])
        self.assertEqual(queued.json()["requested_by"], w.admin_email)
        decision = self.gate()
        self.assertEqual((decision.go, decision.reason), (True, "manual"))
        self.assertTrue(w.get("/admin/deploy", w.admin).json()["running"])
        self.assertFalse(self.gate().go)  # request used up; still paused

        w.db(lambda _s: _service().gate_end(True, "API updated to abc1234"))
        status = w.get("/admin/deploy", w.admin).json()
        self.assertEqual(status["last_result"], "✓ API updated to abc1234")
        self.assertFalse(status["running"])
        actions = {r["action"] for r in w.sql("SELECT action FROM audit_log WHERE entity_type = 'deploy'")}
        self.assertTrue({"deploy.configure", "deploy.requested"} <= actions)

    def test_schedule_needs_valid_times(self):
        w = self.w
        self.assertEqual(w.put("/admin/deploy/config", {"mode": "schedule", "schedule_times": []}, w.admin).status_code, 422)
        self.assertEqual(w.put("/admin/deploy/config", {"mode": "schedule", "schedule_times": ["25:00"]}, w.admin).status_code, 422)
        ok = w.put("/admin/deploy/config", {"mode": "schedule", "schedule_times": ["16:00", "02:00", "02:00"]}, w.admin)
        self.assertEqual(ok.json()["schedule_times"], ["02:00", "16:00"])

    def test_cancel_request(self):
        w = self.w
        w.put("/admin/deploy/config", {"mode": "paused"}, w.admin)
        w.post("/admin/deploy/now", None, w.admin)
        self.assertIsNone(w.delete("/admin/deploy/now", w.admin).json()["requested_at"])
        self.assertFalse(self.gate().go)

    def test_log_endpoint(self):
        res = self.w.get("/admin/deploy/log", self.w.admin)
        self.assertEqual(res.status_code, 200)
        self.assertIn("log", res.json())

    def test_gate_cli_speaks_one_word(self):
        from app.scripts.deploy_gate import _main

        self.w.put("/admin/deploy/config", {"mode": "paused"}, self.w.admin)
        self.assertEqual(asyncio.run(_main(["begin"])), "skip paused")
        self.assertEqual(asyncio.run(_main(["end", "ok", "no", "changes"])), "recorded")


if __name__ == "__main__":
    unittest.main()

    def test_releases_lists_at_most_five_with_the_live_one_first(self):
        r = self.w.get("/admin/deploy/releases", self.w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        rel = r.json()["releases"]
        self.assertLessEqual(len(rel), 5)
        if rel:
            self.assertTrue(rel[0]["current"])
            self.assertFalse(any(x["current"] for x in rel[1:]))

