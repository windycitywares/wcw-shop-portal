"""Live / Test switch against PostgreSQL: the copy, what testers do staying out of the live data, emails, sign-in."""

import unittest

from tests.integration_support import PASSWORD, RUN, item, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class TestModeTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def tearDown(self):
        # Whatever happened, leave the shared database on live data with no copy, for the other test modules.
        w = self.w
        admin = w.login(w.admin_email, "admin-password-1")
        w.client.put(w.url("/admin/environment/mode"), json={"mode": "live"}, headers=admin)
        admin = w.login(w.admin_email, "admin-password-1")
        w.delete("/admin/environment/test-data", admin)
        w.admin = w.login(w.admin_email, "admin-password-1")

    def put(self, path, body, headers):
        return self.w.client.put(self.w.url(path), json=body, headers=headers)

    def test_switch_copy_isolate_and_delete(self):
        w = self.w
        p = w.product("30.00")
        live_customer_email, live_customer = w.register("before-test")

        self.assertEqual(w.get("/admin/environment", w.publisher).status_code, 403)  # admins only
        r = self.put("/admin/environment/mail-to", {"email": "qa-inbox@example.com"}, w.admin)
        self.assertEqual(r.json()["test_mail_to"], "qa-inbox@example.com")

        r = self.put("/admin/environment/mode", {"mode": "test"}, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        state = r.json()
        self.assertEqual((state["mode"], state["effective"], state["test_exists"], state["out_of_date"]), ("test", "test", True, False))
        self.assertGreater(state["stats"]["tables"], 10)
        self.assertTrue(w.get("/environment").json()["test"])

        # Tokens from the live data don't work on the copy (an id there may be someone else)
        self.assertEqual(w.get("/auth/me", live_customer).status_code, 401)
        admin = w.login(w.admin_email, "admin-password-1")  # the copy has the same accounts
        w.login(live_customer_email, PASSWORD)

        # A tester signs up and orders on the copy; emails go to the test inbox, never the customer
        tester_email, tester = w.register("tester")
        w.sent.clear()
        order = w.place(tester_email, [item(p)], tester)["order"]
        self.assertGreaterEqual(order["id"], 1_000_000)  # ids in the copy can't collide with live ones
        self.assertTrue(w.sent)
        self.assertTrue(all(m.to == "qa-inbox@example.com" and m.subject.startswith("[TEST] ") for m in w.sent))
        self.assertIn(order["number"], [o["number"] for o in w.get("/admin/orders", admin, q=order["number"]).json()["items"]])

        # Sync replaces the copy: the tester's order is gone
        r = w.post("/admin/environment/sync", None, admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(w.get("/admin/orders", admin, q=order["number"]).json()["items"], [])

        # Deleting needs live first
        self.assertEqual(w.delete("/admin/environment/test-data", admin).status_code, 409)
        self.assertEqual(self.put("/admin/environment/mode", {"mode": "live"}, admin).json()["effective"], "live")
        admin = w.login(w.admin_email, "admin-password-1")
        self.assertFalse(w.get("/environment").json()["test"])

        # Nothing from testing reached the live data
        self.assertEqual(w.get("/admin/orders", admin, q=order["number"]).json()["items"], [])
        self.assertEqual(w.client.post(w.url("/auth/login"), data={"username": tester_email, "password": PASSWORD}).status_code, 401)

        self.assertEqual(w.delete("/admin/environment/test-data", admin).status_code, 204)
        self.assertFalse(w.get("/admin/environment", admin).json()["test_exists"])
        actions = [a["action"] for a in w.get("/admin/audit", admin, action=None, q="", page_size=100).json()["items"]]
        self.assertIn("environment.test_on", actions)
        self.assertIn("environment.delete_test", actions)


if __name__ == "__main__":
    unittest.main()
