"""How a deployed version is described from its pull request — pure, no DB."""

import unittest

from app.domain.releases import describe_commit


class DescribeCommitTests(unittest.TestCase):
    def test_merge_commit_uses_the_pr_title_and_its_commits(self):
        pr, title, details = describe_commit(
            "Merge pull request #157 from windycitywares/fix/follow-in-footer",
            "Follow us: tiles inside the footer, five per row\n",
            ["Follow us: back inside the footer, five tiles to a row", "Tidy spacing"],
        )
        self.assertEqual(pr, 157)
        self.assertEqual(title, "Follow us: tiles inside the footer, five per row")
        self.assertEqual(details, "Follow us: back inside the footer, five tiles to a row\nTidy spacing")

    def test_squash_commit(self):
        pr, title, details = describe_commit("Add store time zone (#154)", "Applies everywhere.\n\nCo-Authored-By: X", [])
        self.assertEqual((pr, title, details), (154, "Add store time zone", "Applies everywhere."))

    def test_plain_commit_has_no_pr(self):
        pr, title, details = describe_commit("Fix typo", "", [])
        self.assertEqual((pr, title, details), (None, "Fix typo", None))

    def test_trailers_are_not_a_description(self):
        _, _, details = describe_commit("Fix (#1)", "Claude-Session: https://claude.ai/code/x\n", [])
        self.assertIsNone(details)


if __name__ == "__main__":
    unittest.main()
