"""The bells against PostgreSQL: the admin activity list (per-role, many sources) and the shopper's
own order bell, both unread-until-opened."""

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
        by_type: dict = {}
        for i in feed["items"]:  # newest first: keep the first of each kind
            by_type.setdefault(i["type"], i)
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

    def test_newsletter_signup_reaches_the_bell(self):
        w = self.w
        w.post("/admin/notifications/seen", None, w.admin)
        email = w.email("bell-news")
        reset_limits()
        self.assertEqual(w.post("/newsletter", {"email": email, "locale": "en"}).status_code, 202)
        feed = w.get("/admin/notifications", w.admin, kind="subscriber").json()
        found = next(i for i in feed["items"] if email in i["detail"])
        self.assertEqual(found["title"], "New newsletter subscriber")
        self.assertEqual(found["href"], f"/admin/subscribers?q={email}")
        self.assertTrue(found["unread"])
        self.assertGreaterEqual(w.get("/admin/notifications", w.admin).json()["unread"], 1)
        # A publisher (who cannot see customers) never gets it.
        self.assertNotIn("subscriber", w.get("/admin/notifications", w.publisher).json()["kinds"])


@skip_unless_db
class ShopperBellTests(unittest.TestCase):
    """The customer-side bell: their own order milestones, unread until they open it."""

    def setUp(self):
        reset_limits()
        self.w = world()

    def test_the_bell_follows_the_shopper_s_own_orders(self):
        w = self.w
        email, shopper = w.register("bell-shopper")
        self.assertEqual(w.get("/account/notifications", shopper).json()["items"], [])
        self.assertEqual(w.get("/account/notifications").status_code, 401)  # not signed in, no bell

        order = w.place(email, [item(w.product("25.00"))], shopper)["order"]
        feed = w.get("/account/notifications", shopper).json()
        self.assertEqual([i["kind"] for i in feed["items"]], ["placed"])  # paid in the same breath: one line
        self.assertEqual(feed["unread"], 1)
        self.assertTrue(feed["items"][0]["unread"])
        self.assertEqual(feed["items"][0]["number"], order["number"])
        self.assertEqual(feed["items"][0]["id"], f"placed:{order['id']}")

        w.post(f"/admin/orders/{order['id']}/ship", {"carrier": "usps", "tracking_number": "9400 1000"}, w.admin)
        w.post(f"/admin/orders/{order['id']}/status", {"status": "delivered"}, w.admin)
        feed = w.get("/account/notifications", shopper).json()
        self.assertEqual([i["kind"] for i in feed["items"]], ["delivered", "shipped", "placed"])
        self.assertEqual(feed["unread"], 3)
        self.assertEqual(len(w.mails_to(email, "on its way")), 1)
        self.assertEqual(len(w.mails_to(email, "was delivered")), 1)  # the milestone emails the shopper too

        w.post("/account/notifications/seen", None, shopper)
        after = w.get("/account/notifications", shopper).json()
        self.assertEqual(after["unread"], 0)
        self.assertFalse(any(i["unread"] for i in after["items"]))

        # Someone else's order (placed as a guest) never shows in this bell
        guest = w.place(w.email("not-mine"), [item(w.product("10.00"))])["order"]
        mine = {i["number"] for i in w.get("/account/notifications", shopper).json()["items"]}
        self.assertNotIn(guest["number"], mine)

        # A refund appears as its own line, with the amount
        w.post(f"/admin/orders/{order['id']}/refund", {"amount": 5}, w.admin)
        refunds = [i for i in w.get("/account/notifications", shopper).json()["items"] if i["kind"] == "refunded"]
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds[0]["amount"], 5.0)
        self.assertEqual(refunds[0]["number"], order["number"])


if __name__ == "__main__":
    unittest.main()

    def test_pulse_changes_when_something_new_happens(self):
        w = self.w
        w.post("/admin/notifications/seen", None, w.admin)
        before = w.get("/admin/notifications/pulse", w.admin).json()
        self.assertEqual(before["unread"], 0)
        self.assertEqual(w.get("/admin/notifications/pulse").status_code, 401)  # staff only
        w.place(w.email("pulse"), [item(w.product("12.00"))])
        after = w.get("/admin/notifications/pulse", w.admin).json()
        self.assertGreaterEqual(after["unread"], 1)
        self.assertNotEqual(before, after)

    def test_live_socket_needs_a_staff_token_and_sends_a_pulse(self):
        from starlette.websockets import WebSocketDisconnect

        w = self.w
        url = "/api/v1/admin/notifications/live"
        token = w.admin["Authorization"].split(" ", 1)[1]
        with w.client.websocket_connect(url) as ws:
            ws.send_json({"token": token})
            self.assertEqual(ws.receive_json()["type"], "hello")
            first = ws.receive_json()
            self.assertEqual(first["type"], "pulse")
            self.assertIn("unread", first)
        with self.assertRaises(WebSocketDisconnect):
            with w.client.websocket_connect(url) as ws:
                ws.send_json({"token": "not-a-token"})
                ws.receive_json()

