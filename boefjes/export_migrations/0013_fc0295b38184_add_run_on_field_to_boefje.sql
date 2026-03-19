CREATE TYPE run_on AS ENUM ('create', 'update', 'create_update');
ALTER TABLE boefje ADD COLUMN run_on run_on;
