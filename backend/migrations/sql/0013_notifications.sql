-- Admin notifications: when each staff member last opened the activity list (anything newer counts as unread).
ALTER TABLE users ADD COLUMN notifications_seen_at TIMESTAMPTZ;
