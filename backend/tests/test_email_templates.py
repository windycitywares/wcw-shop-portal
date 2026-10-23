"""Editable email wording: what may be changed, what never can, and the admin API around it."""

import unittest

from pydantic import ValidationError

from app.domain import emailtext
from app.schemas.settings import EmailTemplateSettings
from app.services.email_templates import SAMPLE, _sample
from tests.integration_support import reset_limits, skip_unless_db, world


def render(kind, overrides=None, locale="en", **ctx):
    return emailtext.render(kind, {**_sample(kind, locale), **ctx}, overrides=overrides if overrides is not None else {})


class OverrideTests(unittest.TestCase):
    def test_every_editable_email_renders_and_reports_its_defaults(self):
        for kind in emailtext.EDITABLE:
            for lang in emailtext.LOCALES:
                with self.subTest(kind=kind, lang=lang):
                    captured: dict = {}
                    emailtext.render(kind, _sample(kind, lang), overrides={}, capture=captured)
                    self.assertTrue(captured["subject"] and captured["intro"] and captured["signoff"], captured)

    def test_wording_is_replaced_and_placeholders_filled(self):
        r = render("order_confirmation", {"order_confirmation": {"en": {
            "subject": "Thanks! {number} is ours", "intro": "We love that you chose us. Order {number} is in.",
            "button": "See it", "signoff": "Warmly,\nAda"}}})
        self.assertEqual(r.subject, "Thanks! WCW-1042 is ours")
        self.assertIn("We love that you chose us. Order WCW-1042 is in.", r.text)
        self.assertIn("See it:", r.text)
        self.assertIn("Warmly,\nAda", r.text)
        self.assertNotIn("With care", r.text)

    def test_links_codes_and_totals_cannot_be_edited_away(self):
        r = render("welcome_offer", {"welcome_offer": {"en": {"intro": "Hi there", "button": "Go"}}})
        self.assertIn("WELCOME-AB12CD", r.text)
        self.assertIn("/shop", r.text)
        r = render("password_reset", {"password_reset": {"en": {"intro": "Pick a new one."}}})
        self.assertIn(_sample("password_reset", "en")["link"], r.text)

    def test_unknown_placeholders_and_markup_stay_plain_text(self):
        r = render("order_shipped", {"order_shipped": {"en": {"intro": "Hi {__class__} {0} <b>x</b> {number}"}}})
        self.assertIn("{__class__} {0}", r.text)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", r.html)
        self.assertNotIn("<b>x</b>", r.html)

    def test_only_the_chosen_language_changes(self):
        ovr = {"order_delivered": {"es": {"subject": "Entregado {number}"}}}
        self.assertEqual(render("order_delivered", ovr, "es").subject, "Entregado WCW-1042")
        self.assertNotEqual(render("order_delivered", ovr, "en").subject, "Entregado WCW-1042")

    def test_a_subject_cannot_smuggle_a_header(self):
        r = render("order_cancelled", {"order_cancelled": {"en": {"subject": "Hi\nBcc: x@y.z"}}})
        self.assertNotIn("\n", r.subject)

    def test_saved_wording_applies_when_no_override_is_passed(self):
        emailtext.set_overrides({"account_welcome": {"en": {"subject": "Hello and welcome"}}})
        try:
            self.assertEqual(emailtext.render("account_welcome", _sample("account_welcome", "en")).subject, "Hello and welcome")
        finally:
            emailtext.set_overrides({})
        self.assertNotEqual(emailtext.render("account_welcome", _sample("account_welcome", "en")).subject, "Hello and welcome")


class SchemaTests(unittest.TestCase):
    def test_blank_parts_drop_out_and_bad_input_is_refused(self):
        ok = EmailTemplateSettings(templates={"password_reset": {"en": {"subject": " ", "intro": "  Hi  "}}})
        self.assertEqual(ok.templates, {"password_reset": {"en": {"intro": "Hi"}}})
        for bad in ({"campaign": {"en": {"intro": "x"}}}, {"password_reset": {"fr": {"intro": "x"}}},
                    {"password_reset": {"en": {"html": "x"}}}, {"password_reset": {"en": {"subject": "a\nb"}}},
                    {"password_reset": {"en": {"button": "x" * 41}}}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                EmailTemplateSettings(templates=bad)


@skip_unless_db
class AdminTemplateApiTests(unittest.TestCase):
    def setUp(self):
        reset_limits()
        self.w = world()

    def tearDown(self):
        self.w.put("/admin/settings/email_templates", {"templates": {}}, self.w.admin)
        emailtext.set_overrides({})

    def test_catalog_save_preview_test_and_reset(self):
        w = self.w
        cat = w.get("/admin/email-templates", w.admin)
        self.assertEqual(cat.status_code, 200, cat.text)
        kinds = [e["kind"] for e in cat.json()["emails"]]
        self.assertEqual(set(kinds), set(emailtext.EDITABLE))
        pw = next(e for e in cat.json()["emails"] if e["kind"] == "password_reset")
        self.assertEqual(pw["languages"]["en"]["saved"], {})
        self.assertTrue(pw["languages"]["en"]["defaults"]["subject"])

        body = {"subject": "Reset it, friend", "intro": "Choose a new password below. {minutes} minutes."}
        saved = w.put("/admin/email-templates/password_reset/en", body, w.admin)
        self.assertEqual(saved.status_code, 200, saved.text)
        pw = next(e for e in saved.json()["emails"] if e["kind"] == "password_reset")
        self.assertEqual(pw["languages"]["en"]["saved"]["subject"], "Reset it, friend")

        pre = w.post("/admin/email-templates/password_reset/en/preview", {"subject": "Draft subject"}, w.admin)
        self.assertEqual(pre.json()["subject"], "Draft subject")
        sent_before = len(w.sent)
        t = w.post("/admin/email-templates/password_reset/en/test", {"subject": "Draft subject"}, w.admin)
        self.assertEqual(t.status_code, 200, t.text)
        self.assertTrue(any(m.subject == "[Test] Draft subject" for m in w.sent[sent_before:]))

        self.assertEqual(w.put("/admin/email-templates/password_reset/en", {}, w.admin).status_code, 200)  # reset
        after = w.get("/admin/email-templates", w.admin).json()["emails"]
        self.assertEqual(next(e for e in after if e["kind"] == "password_reset")["languages"]["en"]["saved"], {})

    def test_unknown_email_and_non_admins_are_refused(self):
        w = self.w
        self.assertEqual(w.put("/admin/email-templates/campaign/en", {"subject": "x"}, w.admin).status_code, 404)
        self.assertEqual(w.put("/admin/email-templates/password_reset/fr", {"subject": "x"}, w.admin).status_code, 422)
        self.assertEqual(w.get("/admin/email-templates", w.publisher).status_code, 403)


if __name__ == "__main__":
    unittest.main()
