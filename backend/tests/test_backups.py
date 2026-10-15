"""Backups: encryption, which files are kept, when a backup is due, and the commit sent to GitHub."""

import unittest
from datetime import datetime, timedelta, timezone

from app.services import backups

try:
    import cryptography  # noqa: F401

    HAVE_CRYPTO = True
except ImportError:  # pragma: no cover - in requirements.txt
    HAVE_CRYPTO = False


@unittest.skipUnless(HAVE_CRYPTO, "cryptography not installed")
class EncryptionTests(unittest.TestCase):
    def test_round_trip_and_wrong_passphrase(self):
        sealed = backups.encrypt(b"PGDMP database bytes", "correct horse battery")
        self.assertTrue(sealed.startswith(backups.MAGIC))
        self.assertNotIn(b"database bytes", sealed)
        self.assertEqual(backups.decrypt(sealed, "correct horse battery"), b"PGDMP database bytes")
        with self.assertRaises(backups.BackupError):
            backups.decrypt(sealed, "wrong passphrase!")
        with self.assertRaises(backups.BackupError):
            backups.decrypt(sealed[:-1] + bytes([sealed[-1] ^ 1]), "correct horse battery")  # tampered


class RetentionTests(unittest.TestCase):
    def test_keeps_the_newest_and_ignores_other_files(self):
        existing = [f"wcw-backup-202610{d:02d}-030000.dump.enc" for d in range(1, 8)] + ["notes.txt"]
        kept = backups.to_keep(existing, "wcw-backup-20261015-030000.dump.enc", 5)
        self.assertEqual(kept[0], "wcw-backup-20261015-030000.dump.enc")
        self.assertEqual(kept[1:], [f"wcw-backup-202610{d:02d}-030000.dump.enc" for d in (7, 6, 5, 4)])
        self.assertEqual(backups.to_keep([], "wcw-backup-20261015-030000.dump.enc", 1), ["wcw-backup-20261015-030000.dump.enc"])

    def test_file_name_is_utc(self):
        moment = datetime(2026, 10, 14, 22, 5, 9, tzinfo=timezone(timedelta(hours=-5)))
        self.assertEqual(backups.file_name(moment), "wcw-backup-20261015-030509.dump.enc")


class DueTests(unittest.TestCase):
    now = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)  # 04:00 in Chicago

    def test_once_a_day_after_the_hour(self):
        self.assertTrue(backups.is_due(self.now, 3, []))
        self.assertFalse(backups.is_due(self.now, 5, []))
        self.assertFalse(backups.is_due(self.now, 3, [{"status": "success", "started_at": self.now}]))

    def test_retries_a_few_times_and_waits_for_a_running_one(self):
        failed = {"status": "failed", "started_at": self.now - timedelta(hours=1)}
        self.assertTrue(backups.is_due(self.now, 3, [failed, failed]))
        self.assertFalse(backups.is_due(self.now, 3, [failed] * 3))
        self.assertFalse(backups.is_due(self.now, 3, [{"status": "running", "started_at": self.now - timedelta(minutes=5)}]))
        self.assertTrue(backups.is_due(self.now, 3, [{"status": "running", "started_at": self.now - timedelta(hours=2)}]))  # stuck


class FakeGitHub(backups.GitHub):
    def __init__(self, files):
        super().__init__("windycitywares/wcw-backups", "main", "t")
        self.files, self.calls = files, []

    def call(self, method, path, body=None, ok_missing=False):
        self.calls.append((method, path, body))
        if path == "/git/ref/heads/main":
            return {"object": {"sha": "head"}}
        if path.startswith("/git/trees/head"):
            return {"tree": [{"type": "blob", "path": f"backups/{n}", "sha": f"sha-{n}", "size": 10} for n in self.files]}
        if path == "/git/blobs":
            return {"sha": "new-blob" if body["encoding"] == "base64" else "readme-blob"}
        return {"sha": path.rsplit("/", 1)[-1]}


class PublishTests(unittest.TestCase):
    def test_commit_has_no_history_and_only_the_newest_files(self):
        old = [f"wcw-backup-202610{d:02d}-030000.dump.enc" for d in range(1, 9)]
        gh = FakeGitHub(old)
        kept = gh.publish("wcw-backup-20261015-030000.dump.enc", b"sealed", 5)
        self.assertEqual(len(kept), 5)
        tree = next(b for m, p, b in gh.calls if p == "/git/trees")["tree"]
        self.assertEqual(sorted(e["path"] for e in tree), sorted(["README.md", *(f"backups/{n}" for n in kept)]))
        self.assertIn({"path": "backups/wcw-backup-20261015-030000.dump.enc", "mode": "100644", "type": "blob", "sha": "new-blob"}, tree)
        commit = next(b for m, p, b in gh.calls if p == "/git/commits")
        self.assertEqual(commit["parents"], [])  # old backups leave the history
        self.assertEqual(next(b for m, p, b in gh.calls if m == "PATCH")["force"], True)


if __name__ == "__main__":
    unittest.main()
