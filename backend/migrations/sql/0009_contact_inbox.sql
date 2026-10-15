-- Contact inbox: a status for every message from the Contact page, staff notes, and replies sent from the admin.
ALTER TABLE contact_messages
    ADD COLUMN status        VARCHAR(16) NOT NULL DEFAULT 'new',
    ADD COLUMN staff_note    TEXT,
    ADD COLUMN handled_at    TIMESTAMPTZ,
    ADD COLUMN handled_by_id BIGINT REFERENCES users (id) ON DELETE SET NULL;

ALTER TABLE contact_messages
    ADD CONSTRAINT ck_contact_messages_status CHECK (status IN ('new', 'open', 'replied', 'closed', 'spam'));

CREATE INDEX ix_contact_messages_status_created ON contact_messages (status, created_at DESC);
CREATE INDEX ix_contact_messages_email ON contact_messages (lower(email));

CREATE TABLE contact_replies (
    id           BIGSERIAL PRIMARY KEY,
    message_id   BIGINT NOT NULL REFERENCES contact_messages (id) ON DELETE CASCADE,
    author_id    BIGINT REFERENCES users (id) ON DELETE SET NULL,
    author_email VARCHAR(320),
    body         TEXT NOT NULL,
    emailed      BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_contact_replies_message ON contact_replies (message_id, created_at);
