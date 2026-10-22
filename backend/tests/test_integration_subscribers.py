"""The newsletter list in the admin: joining from the site shows up, and staff can search, add, remove and export."""

import csv
import io
import unittest

from tests.integration_support import reset_limits, skip_unless_db, world


@skip_unless_db
class SubscriberAdminTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def listing(self, **params):
        r = self.w.get("/admin/subscribers", self.w.admin, **params)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_site_signup_appears_and_can_be_taken_off(self):
        w = self.w
        email = w.email("news")
        self.assertEqual(w.post("/newsletter", {"email": email, "locale": "en"}).status_code, 202)
        found = self.listing(q=email)
        self.assertEqual(found["total"], 1)
        row = found["items"][0]
        self.assertEqual((row["email"], row["source"], row["subscribed"]), (email, "site", True))
        self.assertGreaterEqual(found["counts"]["subscribed"], 1)

        gone = w.post(f"/admin/subscribers/{row['id']}/unsubscribe", None, w.admin)
        self.assertEqual(gone.status_code, 200)
        self.assertFalse(gone.json()["subscribed"])
        self.assertEqual(self.listing(q=email, status="subscribed")["total"], 0)
        self.assertEqual(self.listing(q=email, status="unsubscribed")["total"], 1)

        # Staff cannot sign someone back up; only the person can, from the site.
        again = w.post("/admin/subscribers", {"email": email, "locale": "en"}, w.admin)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(w.post("/newsletter", {"email": email, "locale": "en"}).status_code, 202)
        self.assertEqual(self.listing(q=email, status="subscribed")["total"], 1)

    def test_add_export_and_delete(self):
        w = self.w
        email = w.email("manual")
        added = w.post("/admin/subscribers", {"email": email, "locale": "es"}, w.admin)
        self.assertEqual(added.status_code, 201, added.text)
        self.assertEqual((added.json()["source"], added.json()["locale"]), ("admin", "es"))

        out = w.get("/admin/subscribers/export.csv", w.admin, status="subscribed")
        self.assertEqual(out.status_code, 200)
        self.assertIn("text/csv", out.headers["content-type"])
        rows = list(csv.reader(io.StringIO(out.text)))
        self.assertEqual(rows[0][:2], ["Email", "Status"])
        self.assertIn(email, [r[0] for r in rows[1:]])

        self.assertEqual(w.delete(f"/admin/subscribers/{added.json()['id']}", w.admin).status_code, 204)
        self.assertEqual(self.listing(q=email)["total"], 0)

    def test_service_only_rows_are_not_subscribers_and_access_is_limited(self):
        w = self.w
        email = w.email("cartonly")
        w.sql("INSERT INTO newsletter_subscribers (email, source, locale, created_at, updated_at) VALUES (:e, 'cart_reminder', 'en', now(), now())", e=email)
        self.assertEqual(self.listing(q=email)["total"], 0)
        # A signed-in shopper, or no one, cannot read the list.
        _, shopper = w.register("nosubs")
        self.assertEqual(w.get("/admin/subscribers", shopper).status_code, 403)
        self.assertEqual(w.get("/admin/subscribers").status_code, 401)


if __name__ == "__main__":
    unittest.main()
