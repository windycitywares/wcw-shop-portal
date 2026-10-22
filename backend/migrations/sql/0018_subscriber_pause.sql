-- A subscriber the shop owner has paused: still on the list, but left out of campaigns until resumed.
ALTER TABLE newsletter_subscribers ADD COLUMN paused_at timestamptz;
