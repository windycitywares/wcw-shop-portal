-- Who may sign in as a shopper while Test mode is on: comma-separated email addresses.
-- The copy holds every live customer and their password, so a copied shopper cannot sign in until their
-- address is listed here. Staff always can, and an account created inside the copy (someone signing up
-- during testing) is a tester, not a copied customer.
ALTER TABLE app_mode ADD COLUMN test_login_emails TEXT NOT NULL DEFAULT '';
