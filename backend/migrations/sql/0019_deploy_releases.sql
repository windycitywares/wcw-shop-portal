-- Admin → Deployments: the versions the server has run, newest first (the page shows the last five).
-- One row per API commit that went live; the description comes from the pull request that brought it.
CREATE TABLE deploy_releases (
    id SERIAL PRIMARY KEY,
    commit VARCHAR(40) NOT NULL,
    pr_number INTEGER,
    title VARCHAR(300) NOT NULL,
    details TEXT,
    committed_at TIMESTAMPTZ,
    deployed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    storefront_build VARCHAR(40),
    main_site_build VARCHAR(40),
    reason VARCHAR(40)
);
CREATE INDEX ix_deploy_releases_deployed_at ON deploy_releases (deployed_at DESC);
