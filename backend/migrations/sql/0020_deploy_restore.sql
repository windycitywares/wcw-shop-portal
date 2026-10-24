-- Admin → Deployments: restore an earlier version. While a commit is pinned, the server stops installing newer
-- API and storefront builds; "Return to latest" clears the pin.
ALTER TABLE deploy_control ADD COLUMN pinned_commit VARCHAR(40);
ALTER TABLE deploy_control ADD COLUMN restore_pending BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE deploy_control ADD COLUMN pinned_by_email VARCHAR(320);
ALTER TABLE deploy_control ADD COLUMN pinned_at TIMESTAMPTZ;
