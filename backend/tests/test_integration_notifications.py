"""Admin bell against PostgreSQL: activity from several sources, per-role filtering, unread count, links."""

import unittest

from tests.integration_support import RUN, item, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class NotificationTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_feed_roles_unread_and_links(self):
        w = self.w
        self.assertEqual(w.post("/admin/notifications/seen", None, w.admin).status_code, 204)
        self.assertEqual(w.get("/admin/notifications", w.admin).json()["unread"], 0)

        order = w.place(w.email("bell"), [item(w.product("25.00"))])["order"]
        email, _ = w.register("bell-signup")
        reset_limits()
        w.post("/contact", {"name": "Lee", "email": w.email("asker"), "subject": f"Bell {w.sfx}", "message": "Do you ship to Canada?"})

        feed = w.get("/admin/notifications", w.admin).json()
        self.assertGreaterEqual(feed["unread"], 3)
        by_type = {i["type"]: i for i in feed["items"]}
        self.assertEqual(by_type["order"]["href"], f"/admin/orders/{order['id']}")
        self.assertIn(order["number"], by_type["order"]["title"])
        self.assertTrue(by_type["message"]["href"].startswith("/admin/messages?id="))
        signup = next(i for i in feed["items"] if i["type"] == "signup" and email.lower() in i["detail"])
        self.assertEqual(signup["href"], f"/admin/customers?q={email.lower()}")
        self.assertTrue(all(i["unread"] for i in feed["items"][:3]))

        only_orders = w.get("/admin/notifications", w.admin, kind="order").json()["items"]
        self.assertTrue(only_orders and all(i["type"] == "order" for i in only_orders))

        # A publisher only sees what their role can act on (reviews), never orders or customer messages
        pub = w.get("/admin/notifications", w.publisher).json()
        self.assertEqual(pub["kinds"], ["review"])
        self.assertFalse([i for i in pub["items"] if i["type"] != "review"])
        self.assertEqual(w.get("/admin/notifications", w.customer).status_code, 403)

        w.post("/admin/notifications/seen", None, w.admin)
        after = w.get("/admin/notifications", w.admin).json()
        self.assertEqual(after["unread"], 0)
        self.assertFalse(any(i["unread"] for i in after["items"]))


if __name__ == "__main__":
    unittest.main()
