"""Tracking-code settings: safe defaults and the size limit."""

import unittest

from pydantic import ValidationError

from app.schemas.settings import GROUPS, PublicConfig, ScriptSettings, StoreSettings


class ScriptSettingsTests(unittest.TestCase):
    def test_nothing_is_added_and_consent_is_required_by_default(self):
        s = ScriptSettings()
        self.assertEqual((s.head_code, s.body_code, s.require_consent), (None, None, True))
        self.assertIs(GROUPS["scripts"], ScriptSettings)
        self.assertTrue(StoreSettings().scripts.require_consent)

    def test_a_snippet_is_kept_as_pasted_up_to_the_limit(self):
        code = '<script async src="https://www.googletagmanager.com/gtag/js?id=G-TEST"></script>'
        self.assertEqual(ScriptSettings(head_code=code).head_code, code)
        with self.assertRaises(ValidationError):
            ScriptSettings(body_code="x" * 20001)

    def test_the_public_config_defaults_add_nothing(self):
        fields = PublicConfig.model_fields
        self.assertIsNone(fields["head_code"].default)
        self.assertIsNone(fields["body_code"].default)
        self.assertTrue(fields["scripts_need_consent"].default)


if __name__ == "__main__":
    unittest.main()
