-- Reverses 0009_contact_inbox.sql
DROP TABLE contact_replies;
DROP INDEX ix_contact_messages_email;
DROP INDEX ix_contact_messages_status_created;
ALTER TABLE contact_messages DROP CONSTRAINT ck_contact_messages_status;
ALTER TABLE contact_messages DROP COLUMN handled_by_id, DROP COLUMN handled_at, DROP COLUMN staff_note, DROP COLUMN status;
