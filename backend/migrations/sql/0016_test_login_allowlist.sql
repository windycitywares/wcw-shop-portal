-- Test mode: which accounts may sign in while it is on (the copy holds real customers' password hashes).
-- Empty list = only admin accounts can sign in. Read and written as public.app_mode (live), whatever mode is on.
ALTER TABLE app_mode ADD COLUMN test_login_emails JSONB NOT NULL DEFAULT '[]'::jsonb;
