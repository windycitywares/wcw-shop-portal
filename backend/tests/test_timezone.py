"""The store's time zone: a list to pick from, used for report days, and the same list in the admin page."""

import re
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.domain import timeutil
from app.domain.timezones import DEFAULT_TIMEZONE, TIMEZONE_IDS, TIMEZONES
from app.schemas.settings import GeneralSettings, PublicConfig, StoreSettings


class TimezoneTests(unittest.TestCase):
    def tearDown(self):
        timeutil.set_store_tz(DEFAULT_TIMEZONE)

    def test_default_is_chicago_and_unknown_falls_back(self):
        self.assertEqual(StoreSettings().general.timezone, "America/Chicago")
        timeutil.set_store_tz("Mars/Olympus")
        self.assertEqual(timeutil.store_tz_name(), "America/Chicago")

    def test_only_listed_zones_are_accepted(self):
        self.assertEqual(GeneralSettings(timezone="Europe/Amsterdam").timezone, "Europe/Amsterdam")
        for bad in ("Mars/Olympus", "", "america/chicago", "EST"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                GeneralSettings(timezone=bad)

    def test_every_listed_zone_loads(self):
        from zoneinfo import ZoneInfo

        for zid, _ in TIMEZONES:
            ZoneInfo(zid)
        self.assertEqual(len(TIMEZONE_IDS), len(TIMEZONES))  # no duplicates

    def test_the_day_follows_the_zone(self):
        moment = datetime(2026, 10, 24, 2, 30, tzinfo=timezone.utc)  # still the 23rd in Chicago, the 24th in Amsterdam
        timeutil.set_store_tz("America/Chicago")
        self.assertEqual(timeutil.store_today(moment), date(2026, 10, 23))
        timeutil.set_store_tz("Europe/Amsterdam")
        self.assertEqual(timeutil.store_today(moment), date(2026, 10, 24))
        self.assertEqual(timeutil.day_start_utc(date(2026, 10, 24)), datetime(2026, 10, 23, 22, 0, tzinfo=timezone.utc))

    def test_public_config_carries_the_zone(self):
        self.assertEqual(PublicConfig.model_fields["timezone"].default, "America/Chicago")

    def test_admin_list_matches_the_server_list(self):
        ts = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "timezones.ts"
        if not ts.exists():
            self.skipTest("frontend not checked out")
        ids = re.findall(r'\[\s*"([A-Za-z_/]+)"\s*,', ts.read_text(encoding="utf-8"))
        self.assertEqual(ids, [i for i, _ in TIMEZONES])


if __name__ == "__main__":
    unittest.main()
