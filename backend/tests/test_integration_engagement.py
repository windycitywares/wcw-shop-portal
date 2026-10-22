"""Batch 4 API tests against PostgreSQL: reviews, wishlist, back-in-stock, review requests, customers and campaigns."""

import csv
import json
import io
import unittest

from tests.integration_support import RUN, item, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


def run_job(fn):
    """Run an async job with its own session, e.g. run_job(lambda s: SomeJob(s).run())."""
    return world().db(fn)


def flush_outbox() -> None:
    async def go(session):
        from app.services import emails

        return await emails.process_outbox(session, limit=500)

    for _ in range(20):
        if not run_job(go)["sent"]:
            break


@skip_unless_db
class ReviewTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_verified_review_moderation_and_votes(self):
        w = self.w
        p = w.product("40.00")
        email, author = w.register("reviewer", name="Ana Lopez")
        order = w.place(email, [item(p)], author)["order"]
        body = {"rating": 5, "title": "Beautiful", "body": "Exactly as pictured and arrived quickly."}
        # Paid but not delivered yet: no review.
        self.assertFalse(w.get(f"/products/{p['slug']}/reviews", author).json()["can_review"])
        self.assertEqual(w.post(f"/products/{p['slug']}/reviews", body, author).status_code, 403)
        w.post(f"/admin/orders/{order['id']}/ship", {"notify_customer": False}, w.admin)
        w.post(f"/admin/orders/{order['id']}/status", {"status": "delivered"}, w.admin)
        self.assertTrue(w.get(f"/products/{p['slug']}/reviews", author).json()["can_review"])
        r = w.post(f"/products/{p['slug']}/reviews", body, author)
        self.assertEqual(r.status_code, 201, r.text)
        submitted = r.json()
        self.assertEqual(submitted["status"], "pending")
        self.assertTrue(submitted["review"]["verified"])
        self.assertEqual(submitted["review"]["author_name"], "Ana L.")  # never the full name or email
        self.assertEqual(w.post(f"/products/{p['slug']}/reviews", body, author).status_code, 409)
        self.assertEqual(w.get(f"/products/{p['slug']}/reviews").json()["summary"]["count"], 0)  # not shown until approved

        queue = w.get("/admin/reviews", w.publisher, status="pending").json()  # publishers can moderate
        self.assertIn(submitted["review"]["id"], [x["id"] for x in queue["items"]])
        rid = submitted["review"]["id"]
        r = w.put(f"/admin/reviews/{rid}", {"status": "approved", "reply": "Thank you, Ana."}, w.publisher)
        self.assertEqual(r.json()["status"], "approved")
        listed = w.get(f"/products/{p['slug']}/reviews").json()
        self.assertEqual((listed["summary"]["count"], listed["summary"]["average"]), (1, 5.0))
        self.assertEqual(listed["items"][0]["reply"], "Thank you, Ana.")
        self.assertNotIn(email, w.get(f"/products/{p['slug']}/reviews").text)
        detail = w.get(f"/products/{p['slug']}").json()
        self.assertEqual((detail["rating_count"], detail["rating_avg"]), (1, 5.0))

        _, voter = w.register("voter")
        voted = w.post(f"/reviews/{rid}/helpful", None, voter).json()
        self.assertEqual((voted["helpful_count"], voted["helpful_by_me"]), (1, True))
        self.assertEqual(w.post(f"/reviews/{rid}/helpful", None, voter).json()["helpful_count"], 0)  # toggles
        self.assertEqual(w.post(f"/reviews/{rid}/helpful", None, author).status_code, 422)  # not your own

        _, stranger = w.register("stranger")  # never bought it: may not review
        self.assertEqual(w.post(f"/products/{p['slug']}/reviews", {"rating": 2, "body": "Never bought it but here I am."}, stranger).status_code, 403)
        mine = w.get(f"/products/{p['slug']}/reviews", author).json()
        self.assertEqual((mine["can_review"], mine["reviewed"]), (False, True))
        self.assertEqual(w.get(f"/products/{p['slug']}/reviews").json()["summary"]["count"], 1)

        # Shipped but never marked delivered: counts as received after Settings → Reviews "ask after" days (10).
        email2, buyer = w.register("shipped")
        later = w.place(email2, [item(p)], buyer)["order"]
        w.post(f"/admin/orders/{later['id']}/ship", {"notify_customer": False}, w.admin)
        self.assertFalse(w.get(f"/products/{p['slug']}/reviews", buyer).json()["can_review"])
        w.sql("UPDATE orders SET shipped_at = now() - interval '11 days' WHERE id = :id", id=later["id"])
        self.assertTrue(w.get(f"/products/{p['slug']}/reviews", buyer).json()["can_review"])
        self.assertEqual(w.post(f"/products/{p['slug']}/reviews", {"rating": 4, "body": "Arrived well packed."}, buyer).status_code, 201)
        self.assertEqual(w.post(f"/products/{p['slug']}/reviews", body).status_code, 401)
        self.assertEqual(w.get("/admin/reviews", w.customer).status_code, 403)

    def test_review_request_after_delivery(self):
        w = self.w
        p = w.product()
        email = w.email("askme")
        order = w.place(email, [item(p)])["order"]
        w.post(f"/admin/orders/{order['id']}/ship", {"notify_customer": False}, w.admin)
        w.sql("UPDATE orders SET shipped_at = now() - interval '11 days' WHERE id = :id", id=order["id"])

        async def ask(session):
            from app.services.engagement import ReviewRequestJob

            return await ReviewRequestJob(session).run()

        self.assertGreaterEqual(run_job(ask)["sent"], 1)
        mails = w.mails_to(email, "how is everything")
        self.assertEqual(len(mails), 1)
        self.assertIn(f"/product/{p['slug']}#reviews", mails[0].text)
        run_job(ask)
        self.assertEqual(len(w.mails_to(email, "how is everything")), 1)  # once per order


@skip_unless_db
class WishlistAndStockAlertTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_wishlist(self):
        w = self.w
        p = w.product()
        _, me = w.register("wish")
        self.assertEqual(w.put(f"/account/wishlist/{p['id']}", None, me).status_code, 204)
        self.assertEqual(w.put(f"/account/wishlist/{p['id']}", None, me).status_code, 204)  # adding twice is fine
        self.assertEqual(w.get("/account/wishlist/ids", me).json(), [p["id"]])
        self.assertEqual(w.get("/account/wishlist", me).json()[0]["slug"], p["slug"])
        self.assertEqual(w.delete(f"/account/wishlist/{p['id']}", me).status_code, 204)
        self.assertEqual(w.get("/account/wishlist/ids", me).json(), [])
        self.assertEqual(w.get("/account/wishlist/ids").status_code, 401)
        self.assertEqual(w.put("/account/wishlist/987654321", None, me).status_code, 404)

    def test_back_in_stock_email_once(self):
        w = self.w
        p = w.product(out_of_stock=True)
        self.assertEqual(w.post(f"/products/{p['id']}/notify-me", {"email": w.email("guest")}).status_code, 401)  # signed in only
        email, me = w.register("waiting")
        for _ in range(2):
            self.assertEqual(w.post(f"/products/{p['id']}/notify-me", {}, me).status_code, 202)
        self.assertEqual(w.value("SELECT count(*) FROM stock_alerts WHERE email = :e", e=email), 1)

        async def notify(session):
            from app.services.engagement import StockAlertService

            return await StockAlertService(session).notify_back_in_stock()

        run_job(notify)
        self.assertEqual(w.mails_to(email, "back in stock"), [])  # still sold out: nothing sent
        w.sql("UPDATE products SET stock_status = 'in_stock', stock_quantity = 3 WHERE id = :id", id=p["id"])
        run_job(notify)
        run_job(notify)
        self.assertEqual(len(w.mails_to(email, "back in stock")), 1)


@skip_unless_db
class StockRequestTests(unittest.TestCase):
    """Requests for option combinations: back-in-stock emails, special requests answered by staff, the customer's list."""

    def setUp(self):
        reset_limits()
        self.w = world()

    def variant(self, parent: dict, attrs: dict, in_stock: bool) -> dict:
        v = self.w.product(out_of_stock=not in_stock)
        self.w.sql("UPDATE products SET parent_id = :p, attributes = CAST(:a AS jsonb) WHERE id = :id", p=parent["id"], a=json.dumps(attrs), id=v["id"])
        return v

    def notify(self):
        async def go(session):
            from app.services.engagement import StockAlertService

            return await StockAlertService(session).notify_back_in_stock()

        return run_job(go)

    def test_list_options_on_a_sold_out_product(self):
        w = self.w
        p = w.product(out_of_stock=True)
        w.sql("UPDATE products SET attributes = CAST(:a AS jsonb) WHERE id = :id", a=json.dumps({"Size": ["Small", "Large"], "Wood": "Oak"}), id=p["id"])
        email, me = w.register("sizes")
        url = f"/products/{p['id']}/stock-requests"
        self.assertEqual(w.post(url, {"options": {"Size": "Large"}}).status_code, 401)
        self.assertEqual(w.post(url, {"options": {"Size": "Huge"}}, me).status_code, 422)
        self.assertEqual(w.post(url, {"options": {}}, me).status_code, 422)  # a size must be chosen
        r = w.post(url, {"options": {"Size": "Large"}, "note": "For my mother's ashes", "locale": "en"}, me)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual((r.json()["kind"], r.json()["already"]), ("restock", False))
        self.assertTrue(w.post(url, {"options": {"Size": "Large"}}, me).json()["already"])  # asking twice is fine
        mine = w.get("/account/stock-requests", me).json()
        self.assertEqual((mine[0]["options"], mine[0]["status"], mine[0]["note"]), ({"Size": "Large"}, "waiting", "For my mother's ashes"))

        w.sql("UPDATE products SET stock_status = 'in_stock', stock_quantity = 2 WHERE id = :id", id=p["id"])
        self.notify()
        mails = w.mails_to(email, "back in stock")
        self.assertEqual(len(mails), 1)
        self.assertIn("Size: Large", mails[0].subject)
        self.assertEqual(w.get("/account/stock-requests", me).json()[0]["status"], "notified")
        # in stock now: no request needed
        self.assertEqual(w.post(url, {"options": {"Size": "Small"}}, me).status_code, 409)

    def test_product_out_of_stock_switches_off_its_variants(self):
        w = self.w
        parent = w.product()
        small = self.variant(parent, {"Size": "Small"}, True)
        large = self.variant(parent, {"Size": "Large"}, True)
        # Older data: the product was marked out of stock while its variants still say in stock
        w.sql("UPDATE products SET stock_status = 'out_of_stock' WHERE id = :id", id=parent["id"])
        q = w.quote([item(small)])
        self.assertIn("out of stock", " ".join(q["messages"]))
        self.assertEqual(q["lines"], [])
        _, me = w.register("switch")
        self.assertEqual(w.post(f"/products/{parent['id']}/stock-requests", {"options": {"Size": "Small"}}, me).json()["kind"], "restock")

        # Saving the product as out of stock switches the variants off; back in stock switches them on again
        r = w.client.patch(w.url(f"/products/{parent['id']}"), json={"stock_status": "out_of_stock"}, headers=w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual({v["stock_status"] for v in r.json()["variants"]}, {"out_of_stock"})
        w.sql("UPDATE products SET stock_quantity = 0 WHERE id = :id", id=large["id"])
        r = w.client.patch(w.url(f"/products/{parent['id']}"), json={"stock_status": "in_stock"}, headers=w.admin)
        status = {v["id"]: v["stock_status"] for v in r.json()["variants"]}
        self.assertEqual((status[small["id"]], status[large["id"]]), ("in_stock", "out_of_stock"))  # none left of Large
        self.assertEqual(w.quote([item(small)])["messages"], [])

    def test_add_variant_continues_the_sku_numbering(self):
        w = self.w
        parent = w.product()
        sku = w.value("SELECT sku FROM products WHERE id = :id", id=parent["id"])
        w.sql("UPDATE products SET category_id = (SELECT id FROM categories ORDER BY id LIMIT 1) WHERE id = :id", id=parent["id"])
        for n in (1, 2, 4):
            v = self.variant(parent, {"Size": f"S{n}"}, True)
            w.sql("UPDATE products SET sku = :s WHERE id = :id", s=f"{sku}-{n}", id=v["id"])
        tpl = w.get(f"/products/{parent['id']}/variant-template", w.admin).json()
        self.assertEqual(tpl["sku"], f"{sku}-5")
        self.assertEqual((tpl["option_names"], tpl["variant_count"], tpl["parent_id"]), (["Size"], 3, parent["id"]))
        self.assertEqual(w.get(f"/products/{parent['id']}/variant-template", w.customer).status_code, 403)

        # A variant created without a category goes into its product's category
        r = w.post("/products", {"title": "Variant", "sku": tpl["sku"], "base_price": 30, "parent_id": parent["id"], "attributes": {"Size": "S5"}}, w.admin)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["category_id"], tpl["category_id"])
        self.assertEqual(w.get(f"/products/{parent['id']}/variant-template", w.admin).json()["sku"], f"{sku}-6")

    def test_variant_combinations_and_special_requests(self):
        w = self.w
        parent = w.product()
        self.variant(parent, {"Size": "Small", "Wood": "Oak"}, True)
        large_oak = self.variant(parent, {"Size": "Large", "Wood": "Oak"}, False)
        self.variant(parent, {"Size": "Small", "Wood": "Walnut"}, True)
        email, me = w.register("combo")
        url = f"/products/{parent['id']}/stock-requests"

        self.assertEqual(w.post(url, {"options": {"Size": "Small", "Wood": "Oak"}}, me).status_code, 409)  # buy it instead
        r = w.post(url, {"options": {"Size": "Large", "Wood": "Oak"}}, me)
        self.assertEqual(r.json()["kind"], "restock")
        self.assertEqual(w.value("SELECT product_id FROM stock_alerts WHERE email = :e AND kind = 'restock'", e=email), large_oak["id"])
        r = w.post(url, {"options": {"Size": "Large", "Wood": "Walnut"}, "note": "Could you make this?"}, me)
        self.assertEqual(r.json()["kind"], "request")  # not a combination the shop sells

        self.assertEqual(w.get("/admin/stock-requests", w.publisher).status_code, 403)
        listed = w.get("/admin/stock-requests", w.admin, kind="request", q=email).json()
        self.assertEqual(len(listed["items"]), 1)
        special = listed["items"][0]
        self.assertEqual((special["options"], special["note"], special["product_id"]), ({"Size": "Large", "Wood": "Walnut"}, "Could you make this?", parent["id"]))

        self.notify()  # the back-in-stock job never answers special requests
        self.assertEqual(w.mails_to(email, "back in stock"), [])
        r = w.post(f"/admin/stock-requests/{special['id']}/notify", {"message": "We can make it, ships in a week."}, w.admin)
        self.assertEqual(r.status_code, 204, r.text)
        mail = w.mails_to(email, "Good news")[0]
        self.assertIn("ships in a week", mail.text)
        self.assertEqual(w.post(f"/admin/stock-requests/{special['id']}/notify", {}, w.admin).status_code, 409)

        restock = next(m for m in w.get("/account/stock-requests", me).json() if m["kind"] == "restock")
        self.assertEqual(w.delete(f"/account/stock-requests/{restock['id']}", me).status_code, 204)
        self.assertEqual(next(m for m in w.get("/account/stock-requests", me).json() if m["id"] == restock["id"])["status"], "closed")
        _, other = w.register("stranger")
        self.assertEqual(w.delete(f"/account/stock-requests/{restock['id']}", other).status_code, 404)


@skip_unless_db
class CustomerAndCampaignTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def test_customer_list_detail_and_export(self):
        from app.domain.rfm import SEGMENTS

        w = self.w
        email = w.email("loyal")
        order = w.place(email, [item(w.product("40.00"))])["order"]
        listed = w.get("/admin/customers", w.admin, q=email).json()
        self.assertEqual(listed["total"], 1)
        row = listed["items"][0]
        self.assertEqual((row["email"], row["orders"], row["revenue"]), (email, 1, 48.95))
        self.assertIn(row["segment"], SEGMENTS)
        detail = w.get("/admin/customers/detail", w.admin, email=email.upper()).json()
        self.assertEqual([o["number"] for o in detail["orders"]], [order["number"]])
        rows = list(csv.reader(io.StringIO(w.get("/admin/customers/export.csv", w.admin, q=email).text)))
        self.assertEqual(rows[1][0], email)
        self.assertEqual(w.get("/admin/customers/detail", w.admin, email=w.email()).status_code, 404)
        self.assertEqual(w.get("/admin/customers", w.publisher).status_code, 403)

    def test_campaign_reaches_only_people_who_opted_in(self):
        w = self.w
        fan, gone, service_only = w.email("fan"), w.email("gone"), w.email("orders-only")
        w.post("/newsletter", {"email": fan})
        w.post("/newsletter", {"email": gone})
        w.sql("UPDATE newsletter_subscribers SET unsubscribed_at = now() WHERE email = :e", e=gone)
        w.sql("INSERT INTO newsletter_subscribers (email, source) VALUES (:e, 'order')", e=service_only)

        draft = {"name": f"Thank you {w.sfx}", "subject": "A small thank-you", "body": "Thank you for being here.\n\nHere is a code.",
                 "segment": "subscribers", "coupon_kind": "percent", "coupon_value": 10}
        r = w.post("/admin/campaigns", draft, w.admin)
        self.assertEqual(r.status_code, 201, r.text)
        campaign = r.json()
        self.assertEqual((campaign["status"], campaign["coupon_expires_days"]), ("draft", 14))
        audience = w.get("/admin/campaigns/audience", w.admin, segment="subscribers").json()["count"]
        self.assertGreaterEqual(audience, 1)

        self.assertEqual(w.post(f"/admin/campaigns/{campaign['id']}/test", None, w.admin).status_code, 200)
        self.assertTrue(w.mails_to(w.admin_email, "[test]"))

        sent = w.post(f"/admin/campaigns/{campaign['id']}/send", None, w.admin).json()
        self.assertEqual((sent["status"], sent["recipients"]), ("sent", audience))
        self.assertEqual(sent["coupons_issued"], audience)
        flush_outbox()
        mails = w.mails_to(fan, "thank-you")
        self.assertEqual(len(mails), 1)
        self.assertIn("/unsubscribe?token=", mails[0].text)
        self.assertTrue(dict(mails[0].headers).get("List-Unsubscribe", "").startswith("<https://"))  # one-click unsubscribe in mail apps
        self.assertEqual(w.mails_to(gone, "thank-you"), [])
        self.assertEqual(w.mails_to(service_only, "thank-you"), [])

        self.assertEqual(w.post(f"/admin/campaigns/{campaign['id']}/send", None, w.admin).status_code, 409)  # only once
        self.assertEqual(w.put(f"/admin/campaigns/{campaign['id']}", draft, w.admin).status_code, 409)
        self.assertEqual(w.delete(f"/admin/campaigns/{campaign['id']}", w.admin).status_code, 409)
        spare = w.post("/admin/campaigns", {**draft, "name": "Spare"}, w.admin).json()
        self.assertEqual(w.delete(f"/admin/campaigns/{spare['id']}", w.admin).status_code, 204)
        self.assertEqual(w.post("/admin/campaigns", {**draft, "coupon_value": 150}, w.admin).status_code, 422)
        self.assertEqual(w.get("/admin/campaigns", w.publisher).status_code, 403)


if __name__ == "__main__":
    unittest.main()
