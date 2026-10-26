-- Each member of staff chooses how live updates reach them (pop-up, sound, desktop alert per kind of event, the
-- sound and its volume, "updates available" bars). Only what they changed is stored; app/domain/live_prefs.py fills
-- in the defaults.
ALTER TABLE users ADD COLUMN notification_prefs JSONB NOT NULL DEFAULT '{}'::jsonb;
