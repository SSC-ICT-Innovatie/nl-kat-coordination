-- Make sure all plugin_state entries point to the LOCAL repository
DELETE FROM plugin_state ps WHERE EXISTS(SELECT 1 FROM repository r WHERE ps.repository_pk = r.pk AND r.id != 'LOCAL');

-- Make the plugin_state entries unique by plugin_id and organisation_pk only, as they all point to the LOCAL repository
ALTER TABLE plugin_state DROP CONSTRAINT unique_plugin_per_repo_per_org;
ALTER TABLE plugin_state ADD CONSTRAINT unique_plugin_id_per_org UNIQUE (plugin_id, organisation_pk);

-- Remove the repository foreign key for plugin_state
ALTER TABLE plugin_state DROP CONSTRAINT plugin_state_repository_pk_fkey;
ALTER TABLE plugin_state DROP COLUMN repository_pk;

-- Remove the many-to-many relation to organisations and the repository table itself
DROP TABLE organisation_repository;
DROP TABLE repository;
