"""Tracking-code snippets: defaults, limits and the move from the old two boxes."""

import unittest

from pydantic import ValidationError

from app.schemas.settings import GROUPS, PublicConfig, ScriptSettings, Snippet, StoreSettings

GA = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST"></script>'


class SnippetTests(unittest.TestCase):
    def test_nothing_is_added_by_default(self):
        self.assertEqual(ScriptSettings().snippets, [])
        self.assertIs(GROUPS["scripts"], ScriptSettings)
        self.assertEqual(StoreSettings().scripts.snippets, [])
        self.assertEqual(PublicConfig.model_fields["snippets"].default_factory(), [])

    def test_a_snippet_has_a_name_a_place_and_waits_for_consent(self):
        s = Snippet(id="ga", name="  Google   Analytics ", code=GA)
        self.assertEqual((s.name, s.placement, s.enabled, s.require_consent), ("Google Analytics", "head", True, True))
        for bad in ({"name": " "}, {"code": ""}, {"code": "x" * 20001}, {"placement": "sidebar"}, {"id": "a b"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                Snippet(**{"id": "ga", "name": "n", "code": GA, **bad})

    def test_ids_are_unique_and_the_list_is_capped(self):
        one = {"id": "a", "name": "A", "code": GA}
        with self.assertRaises(ValidationError):
            ScriptSettings(snippets=[one, one])
        with self.assertRaises(ValidationError):
            ScriptSettings(snippets=[{**one, "id": f"s{i}"} for i in range(31)])

    def test_the_old_two_boxes_become_two_named_snippets(self):
        s = ScriptSettings.model_validate({"head_code": GA, "body_code": "<div>chat</div>", "require_consent": False})
        self.assertEqual([(x.name, x.placement, x.require_consent) for x in s.snippets],
                         [("Header code", "head", False), ("Footer code", "body", False)])
        self.assertEqual(ScriptSettings.model_validate({"head_code": None, "body_code": ""}).snippets, [])


if __name__ == "__main__":
    unittest.main()
