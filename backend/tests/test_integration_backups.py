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
        self.assertEqual(self.put({**base, "repo": "windycitywares/wcw-shop-portal"}, w.admin).status_code, 422)  # not the code repo
        self.assertEqual(self.put({**base, "repo": "windycitywares/wcw-portal"}, w.admin).status_code, 422)  # its old name
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

    def test_restore_needs_the_exact_random_word(self):
        w = self.w
        file = "wcw-backup-20261015-030000.dump.enc"
        self.assertEqual(w.post("/admin/backups/restore/prepare", {"file": file}, w.publisher).status_code, 403)
        self.assertEqual(w.post("/admin/backups/restore/prepare", {"file": "../../etc/passwd"}, w.admin).status_code, 422)
        challenge = w.post("/admin/backups/restore/prepare", {"file": file}, w.admin).json()
        self.assertRegex(challenge["word"], r"^[a-z]+-\d{4}$")

        wrong = w.post("/admin/backups/restore", {"file": file, "word": "restore", "token": challenge["token"]}, w.admin)
        self.assertEqual(wrong.status_code, 422)
        self.assertIn("doesn't match", wrong.json()["detail"])

        # The right word passes the check; without the server secrets the restore stops before touching anything.
        r = w.post("/admin/backups/restore", {"file": file, "word": challenge["word"], "token": challenge["token"]}, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "failed")
        self.assertIn("BACKUP_", r.json()["error"])


if __name__ == "__main__":
    unittest.main()
