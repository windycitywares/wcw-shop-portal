"""Notification preferences: defaults, merging and cleaning — pure."""

import unittest

from app.domain.live_prefs import CATEGORIES, NotificationPrefs, to_store, with_defaults


class PrefsTests(unittest.TestCase):
    def test_defaults_interrupt_only_for_what_matters(self):
        p = with_defaults(None)
        self.assertEqual(set(p.categories), set(CATEGORIES))
        self.assertTrue(p.categories["orders_new"].popup and p.categories["orders_new"].sound)
        self.assertTrue(p.categories["messages"].popup)
        self.assertFalse(p.categories["newsletter"].popup)
        self.assertEqual((p.sound, p.volume, p.refresh_bars, p.new_version), ("chime", 70, True, True))

    def test_stored_choices_win_and_junk_is_dropped(self):
        p = with_defaults({"categories": {"newsletter": {"popup": True, "nonsense": True}, "gone": {"popup": True}}, "sound": "bell", "volume": 30})
        self.assertTrue(p.categories["newsletter"].popup)
        self.assertNotIn("gone", p.categories)
        self.assertEqual((p.sound, p.volume), ("bell", 30))

    def test_bad_values_fall_back_to_defaults(self):
        p = with_defaults({"sound": "siren", "volume": 500, "categories": "not a dict"})
        self.assertEqual((p.sound, p.volume), ("chime", 70))

    def test_store_keeps_only_known_categories(self):
        data = to_store(NotificationPrefs(categories={"orders_new": {"popup": True}, "made_up": {"popup": True}}))
        self.assertEqual(set(data["categories"]), {"orders_new"})


if __name__ == "__main__":
    unittest.main()
