"""Test mode sign-in rule: only listed accounts (or, with an empty list, admins) may sign in."""

import unittest

from app.core.enums import UserRole
from app.domain.testlogin import test_login_allowed


class TestLoginRule(unittest.TestCase):
    def test_listed_account_may_sign_in_whatever_its_role(self):
        self.assertTrue(test_login_allowed("qa@windycitywares.com", UserRole.CUSTOMER, ["QA@windycitywares.com"]))

    def test_unlisted_customer_is_refused_even_with_a_real_account(self):
        self.assertFalse(test_login_allowed("buyer@example.com", UserRole.CUSTOMER, ["qa@windycitywares.com"]))

    def test_empty_list_lets_only_admins_in(self):
        self.assertTrue(test_login_allowed("owner@windycitywares.com", UserRole.ADMIN, []))
        self.assertFalse(test_login_allowed("author@windycitywares.com", UserRole.AUTHOR, []))

    def test_blank_entries_are_ignored(self):
        self.assertFalse(test_login_allowed("buyer@example.com", UserRole.CUSTOMER, ["", "  "]))
        self.assertTrue(test_login_allowed("buyer@example.com", UserRole.CUSTOMER, ["", "buyer@example.com"]))
