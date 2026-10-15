"""Backups API against PostgreSQL: settings, permissions, and a run that can't reach GitHub failing cleanly."""

import unittest

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class BackupApiTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def put(self, body, headers):
        return self.w.client.put(self.w.url("/admin/backups"), json=body, headers=headers)

    def test_settings_validation_and_a_failed_run_is_recorded(self):
        w = self.w
        self.assertEqual(w.get("/admin/backups", w.publisher).status_code, 403)
        base = {"enabled": False, "hour": 3, "keep": 5, "branch": "main"}
        self.assertEqual(self.put({**base, "repo": "not a repo"}, w.admin).status_code, 422)
        self.assertEqual(self.put({**base, "repo": "windycitywares/wcw-portal"}, w.admin).status_code, 422)  # not the code repo
        self.assertEqual(self.put({**base, "enabled": True, "repo": ""}, w.admin).status_code, 422)
        self.assertEqual(self.put({**base, "keep": 0, "repo": "windycitywares/wcw-backups"}, w.admin).status_code, 422)

        r = self.put({**base, "repo": "windycitywares/wcw-backups", "keep": 7}, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["repo"], r.json()["keep"], r.json()["enabled"]), ("windycitywares/wcw-backups", 7, False))
        self.assertIn("token", r.json()["secrets"])

        # No token in the test environment: the run fails with a clear message and is kept in the history
        result = w.post("/admin/backups/run", None, w.admin).json()
        self.assertEqual(result["status"], "failed")
        self.assertIn("BACKUP_", result["error"])
        latest = w.get("/admin/backups", w.admin).json()["runs"][0]
        self.assertEqual((latest["status"], latest["trigger"]), ("failed", "manual"))
        self.put({**base, "repo": None}, w.admin)


if __name__ == "__main__":
    unittest.main()
