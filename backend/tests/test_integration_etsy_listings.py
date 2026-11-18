"""Listing sync against PostgreSQL with Etsy replaced: Etsy columns follow Etsy, the team's columns are never touched."""

import unittest
from unittest import mock

from tests.integration_support import RUN, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


def _raw(i, title, state="active"):
    return {"listing_id": i, "title": title, "state": state, "quantity": 3, "price": {"amount": 1500, "divisor": 100, "currency_code": "USD"}}


@skip_unless_db
class EtsyListingTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()
        self.w.put("/admin/etsy/credentials", {"client_id": "k", "client_secret": "s"}, self.w.admin)
        self.w.sql("UPDATE etsy_connection SET access_token='x', refresh_token='y', etsy_shop_id=5, token_expires_at=now()+interval '1 day', listings_synced_at=NULL")

    def _sync(self, pages):
        from app.services.etsy_listings import EtsyListingSync

        async def fake_get(path, **kw):
            return {"results": pages.get(kw["params"]["state"], [])}

        async def go(session):
            with mock.patch("app.services.etsy_client.get", fake_get), \
                    mock.patch("app.core.secretbox.unseal", lambda v: "tok"):
                return await EtsyListingSync(session).run(force=True)

        return self.w.db(go)

    def test_sync_keeps_team_fields_and_marks_removed(self):
        w = self.w
        base = 9_000_000 + abs(hash(w.sfx)) % 100_000
        first = self._sync({"active": [_raw(base, "Mug"), _raw(base + 1, "Tee")]})
        self.assertGreaterEqual(first["created"], 2)

        rows = w.get("/admin/etsy/listings", w.publisher, q="Mug").json()["items"]
        mug = next(r for r in rows if r["etsy_listing_id"] == base)
        w.supplier("Acme")
        patched = w.client.patch(w.url(f"/admin/etsy/listings/{mug['id']}"),
                                 json={"internal_supplier": "Acme", "internal_purchase_cost": "6.50"}, headers=w.publisher)
        self.assertEqual(patched.status_code, 200, patched.text)

        # Etsy renames the mug and drops the tee.
        second = self._sync({"active": [_raw(base, "Mug v2")]})
        self.assertEqual(second["removed"] >= 1, True)
        mug2 = next(r for r in w.get("/admin/etsy/listings", w.publisher, q="Mug v2").json()["items"] if r["etsy_listing_id"] == base)
        self.assertEqual(mug2["internal_supplier"], "Acme")
        by_supplier = [r["etsy_listing_id"] for r in w.get("/admin/etsy/listings", w.publisher, supplier="acme", page_size=100).json()["items"]]
        self.assertIn(base, by_supplier)
        self.assertNotIn(base + 1, by_supplier)
        self.assertEqual(str(mug2["internal_purchase_cost"]), "6.50")
        tee = next(r for r in w.get("/admin/etsy/listings", w.publisher, q="Tee").json()["items"] if r["etsy_listing_id"] == base + 1)
        self.assertEqual(tee["state"], "removed")

    def test_etsy_columns_are_not_editable(self):
        w = self.w
        base = 9_100_000 + abs(hash(w.sfx)) % 100_000
        self._sync({"active": [_raw(base, "Locked")]})
        row = w.get("/admin/etsy/listings", w.publisher, q="Locked").json()["items"][0]
        w.client.patch(w.url(f"/admin/etsy/listings/{row['id']}"), json={"title": "Hacked", "price": "1.00"}, headers=w.publisher)
        again = w.get("/admin/etsy/listings", w.publisher, q="Locked").json()["items"][0]
        self.assertEqual(again["title"], "Locked")


if __name__ == "__main__":
    unittest.main()
