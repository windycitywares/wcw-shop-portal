-- Reverses 0018_subscriber_pause.sql
ALTER TABLE newsletter_subscribers DROP COLUMN paused_at;
