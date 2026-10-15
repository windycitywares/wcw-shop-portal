"""Restoring a backup: the typed confirmation word, and the pg_restore command (all-or-nothing, live schema only)."""

import unittest

from app.core.exceptions import ValidationFailedError
from app.services import restore

FILE = "wcw-backup-20261015-030000.dump.enc"


class ChallengeTests(unittest.TestCase):
    def test_the_shown_word_confirms_this_file_only(self):
        c = restore.new_challenge(FILE, now=1000)
        word, token = c["word"], c["token"]
        self.assertRegex(word, r"^[a-z]+-\d{4}$")
        restore.check_challenge(FILE, word, token, now=1100)
        restore.check_challenge(FILE, f"  {word.upper()} ", token, now=1100)  # spaces and capitals are forgiven
        for typed, file, now in (("wrong-1234", FILE, 1100), (word, "wcw-backup-20261001-030000.dump.enc", 1100), (word, FILE, 1000 + 301)):
            with self.subTest(typed=typed, file=file, now=now), self.assertRaises(ValidationFailedError):
                restore.check_challenge(file, typed, token, now=now)

    def test_tampered_or_garbage_tokens_fail(self):
        c = restore.new_challenge(FILE, now=1000)
        expires, sig = c["token"].split(".")
        for token in (f"{int(expires) + 999}.{sig}", "nonsense", ""):
            with self.subTest(token=token), self.assertRaises(ValidationFailedError):
                restore.check_challenge(FILE, c["word"], token, now=1100)

    def test_words_are_random(self):
        self.assertGreater(len({restore.new_challenge(FILE)["word"] for _ in range(30)}), 20)


class CommandTests(unittest.TestCase):
    def test_restore_is_one_transaction_on_the_live_schema(self):
        args, env = restore.restore_command("/usr/bin/pg_restore", "/tmp/x.dump")
        for flag in ("--single-transaction", "--exit-on-error", "--clean", "--if-exists", "--schema=public", "--no-owner"):
            self.assertIn(flag, args)
        self.assertEqual(args[-1], "/tmp/x.dump")
        self.assertIn("lock_timeout", env["PGOPTIONS"])


if __name__ == "__main__":
    unittest.main()
