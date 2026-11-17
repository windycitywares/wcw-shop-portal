"""Etsy connection against PostgreSQL, with Etsy itself replaced: credentials, "Allow access", who may do what."""

import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class EtsyConnectionTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_staff_can_see_status_but_not_change_settings(self):
        w = self.w
        self.assertEqual(w.get("/admin/etsy/connection", w.publisher).status_code, 200)
        self.assertEqual(w.put("/admin/etsy/credentials", {"client_id": "x"}, w.publisher).status_code, 403)
        self.assertEqual(w.post("/admin/etsy/connect", None, w.publisher).status_code, 403)
        self.assertEqual(w.get("/admin/etsy/connection").status_code, 401)

    def test_secret_is_never_returned(self):
        w = self.w
        r = w.put("/admin/etsy/credentials", {"client_id": "keystring123", "client_secret": "s3cret-value"}, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["client_id"], "keystring123")
        self.assertTrue(body["secret_set"])
        self.assertNotIn("s3cret-value", r.text)
        self.assertNotIn("s3cret-value", w.get("/admin/etsy/connection", w.admin).text)

    def test_allow_access_round_trip(self):
        w = self.w
        w.put("/admin/etsy/credentials", {"client_id": "keystring123"}, w.admin)
        url = w.post("/admin/etsy/connect", None, w.admin).json()["url"]
        q = parse_qs(urlparse(url).query)
        self.assertEqual(q["client_id"], ["keystring123"])
        state = q["state"][0]

        tokens = {"access_token": "4242.tok", "refresh_token": "4242.ref", "expires_in": 3600}
        shops = {"shop_id": 99, "shop_name": "WindyCityWaresUS"}
        with mock.patch("app.services.etsy_client.exchange_code", mock.AsyncMock(return_value=tokens)), \
                mock.patch("app.services.etsy_client.get", mock.AsyncMock(return_value=shops)):
            def back(state_value):
                r = w.client.get(w.url("/integrations/etsy/callback"), params={"state": state_value, "code": "c"},
                                 follow_redirects=False)
                self.assertEqual(r.status_code, 307, r.text)
                return r.headers["location"]

            self.assertIn("etsy=failed", back("wrong"))
            self.assertIn("etsy=connected", back(state))
            self.assertIn("etsy=failed", back(state))  # the state works once

        status = w.get("/admin/etsy/connection", w.admin).json()
        self.assertTrue(status["connected"])
        self.assertEqual(status["shop_name"], "WindyCityWaresUS")
        self.assertNotIn("4242.tok", w.get("/admin/etsy/connection", w.admin).text)

        self.assertFalse(w.post("/admin/etsy/disconnect", None, w.admin).json()["connected"])


if __name__ == "__main__":
    unittest.main()
