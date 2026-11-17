-- Etsy app credentials, typed into Admin → Settings → Etsy (never in chat or Git). The secret is sealed like the SMTP password.
ALTER TABLE etsy_connection ADD COLUMN client_id VARCHAR(100);
ALTER TABLE etsy_connection ADD COLUMN client_secret_enc TEXT;
