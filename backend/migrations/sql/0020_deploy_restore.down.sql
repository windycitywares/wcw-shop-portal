-- Reverses 0020_deploy_restore.sql
ALTER TABLE deploy_control DROP COLUMN pinned_at;
ALTER TABLE deploy_control DROP COLUMN pinned_by_email;
ALTER TABLE deploy_control DROP COLUMN restore_pending;
ALTER TABLE deploy_control DROP COLUMN pinned_commit;
