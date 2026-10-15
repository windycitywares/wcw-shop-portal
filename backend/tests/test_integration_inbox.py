"""Contact inbox API tests against PostgreSQL: listing, read state, notes, replies by email, spam and permissions."""

import unittest

from tests.integration_support import RUN, item, reset_limits, skip_unless_db, world


def setUpModule():
    if RUN:
        world()


@skip_unless_db
class InboxTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def send(self, email: str, subject: str, **extra) -> int:
        reset_limits()
        body = {"name": "Mia Park", "email": email, "subject": subject, "message": "Can the urn be engraved with two names?", **extra}
        r = self.w.post("/contact", body)
        self.assertEqual(r.status_code, 202, r.text)
        found = self.w.get("/admin/messages", self.w.admin, q=subject).json()["items"]
        self.assertEqual(len(found), 1)
        return found[0]["id"]

    def patch(self, path: str, body: dict):
        return self.w.client.patch(self.w.url(path), json=body, headers=self.w.admin)

    def test_read_note_reply_and_close(self):
        w = self.w
        email = w.email("asker")
        p = w.product("55.00")
        order = w.place(email, [item(p)])
        subject = f"Engraving {w.sfx}"
        mid = self.send(email, subject, order_number=order["order"]["number"])

        listed = w.get("/admin/messages", w.admin, q=subject).json()
        self.assertEqual(listed["items"][0]["status"], "new")
        self.assertGreaterEqual(listed["counts"]["new"], 1)

        opened = w.get(f"/admin/messages/{mid}", w.admin).json()
        self.assertEqual(opened["status"], "open")  # opening marks it read
        self.assertEqual(opened["order_id"], order["order"]["id"])
        self.assertIn(order["order"]["number"], [o["number"] for o in opened["orders"]])

        r = self.patch(f"/admin/messages/{mid}", {"staff_note": "Check with the engraver first."})
        self.assertEqual(r.json()["staff_note"], "Check with the engraver first.")

        w.sent.clear()
        r = w.post(f"/admin/messages/{mid}/reply", {"body": "Yes, up to two names fit nicely."}, w.admin)
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        self.assertTrue(out["emailed"])
        self.assertEqual(out["message"]["status"], "replied")
        self.assertEqual(len(out["message"]["replies"]), 1)
        mail = next(m for m in w.sent if m.to == email.lower())
        self.assertEqual(mail.subject, f"Re: {subject}")
        self.assertIn("Yes, up to two names fit nicely.", mail.text)
        self.assertIn("> Can the urn be engraved with two names?", mail.text)  # their message is quoted

        self.assertNotIn(mid, [m["id"] for m in w.get("/admin/messages", w.admin, q=subject).json()["items"]])  # no longer active
        self.assertIn(mid, [m["id"] for m in w.get("/admin/messages", w.admin, status="replied", q=subject).json()["items"]])

        audit = w.get("/admin/audit", w.admin, q=email.lower()).json()["items"]
        self.assertTrue(any(a["action"] == "inbox.reply" for a in audit))

    def test_spam_is_hidden_and_cannot_be_answered(self):
        w = self.w
        subject = f"Cheap followers {w.sfx}"
        mid = self.send(w.email("spammer"), subject)
        self.assertEqual(self.patch(f"/admin/messages/{mid}", {"status": "spam"}).json()["status"], "spam")
        self.assertEqual(w.get("/admin/messages", w.admin, status="all", q=subject).json()["items"], [])
        self.assertEqual(len(w.get("/admin/messages", w.admin, status="spam", q=subject).json()["items"]), 1)
        self.assertEqual(w.post(f"/admin/messages/{mid}/reply", {"body": "No thanks."}, w.admin).status_code, 422)
        self.assertEqual(w.delete(f"/admin/messages/{mid}", w.admin).status_code, 204)
        self.assertEqual(w.get(f"/admin/messages/{mid}", w.admin).status_code, 404)

    def test_only_admins_see_the_inbox(self):
        w = self.w
        self.assertEqual(w.get("/admin/messages", w.publisher).status_code, 403)
        self.assertEqual(w.get("/admin/messages", w.customer).status_code, 403)
        self.assertEqual(w.get("/admin/messages").status_code, 401)

    def test_dashboard_counts_messages_to_answer(self):
        w = self.w
        self.send(w.email("dash"), f"Shipping time {w.sfx}")
        attention = w.get("/admin/reports/overview", w.admin).json()["attention"]
        self.assertTrue(any(a["key"] == "messages" and a["count"] >= 1 for a in attention))


if __name__ == "__main__":
    unittest.main()
