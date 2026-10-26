"""Live events against PostgreSQL: written by the save itself, read as "after id N", filtered by role."""

import unittest

from tests.integration_support import RUN, item, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class LiveEventTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def start(self, who):
        r = self.w.get("/admin/live/events", who)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["events"], [])
        return r.json()["last_id"]

    def since(self, after, who):
        return self.w.get("/admin/live/events", who, after=after).json()

    def test_order_message_and_signup_reach_staff_once(self):
        w = self.w
        after = self.start(w.admin)
        order = w.place(w.email("live"), [item(w.product("21.00"))])["order"]
        reset_limits()
        w.post("/contact", {"name": "Robin", "email": w.email("live-asker"), "subject": f"Live {w.sfx}", "message": "Is this in stock?"})
        email, _ = w.register("live-signup")

        got = self.since(after, w.admin)
        kinds = [e["kind"] for e in got["events"]]
        self.assertIn("order.new", kinds)
        self.assertEqual(kinds.count("order.new"), 1)  # placed and paid in one save: one line
        new_order = next(e for e in got["events"] if e["kind"] == "order.new")
        self.assertEqual(new_order["title"], f"New order #{order['number']}")
        self.assertEqual(new_order["href"], f"/admin/orders/{order['id']}")
        self.assertIn("message.new", kinds)
        self.assertIn("customer.new", kinds)
        self.assertGreaterEqual(got["last_id"], max(e["id"] for e in got["events"]))

        # Nothing new: an empty answer that keeps the place.
        again = self.since(got["last_id"], w.admin)
        self.assertEqual(again["events"], [])
        self.assertEqual(again["last_id"], got["last_id"])

    def test_shipping_an_order_is_news(self):
        w = self.w
        order = w.place(w.email("live-ship"), [item(w.product("8.00"))])["order"]
        after = self.start(w.admin)
        w.post(f"/admin/orders/{order['id']}/ship", {"carrier": "usps", "tracking_number": "9400 2000"}, w.admin)
        titles = [e["title"] for e in self.since(after, w.admin)["events"]]
        self.assertIn(f"Order #{order['number']} shipped", titles)

    def test_each_role_sees_only_what_it_can_act_on(self):
        w = self.w
        after = self.start(w.publisher)
        w.place(w.email("live-pub"), [item(w.product("4.00"))])
        kinds = [e["kind"] for e in self.since(after, w.publisher)["events"]]
        self.assertNotIn("order.new", kinds)  # a publisher works the catalog, not orders
        self.assertEqual(w.get("/admin/live/events").status_code, 401)
        _, customer = w.register("live-customer")
        self.assertEqual(w.get("/admin/live/events", customer).status_code, 403)
