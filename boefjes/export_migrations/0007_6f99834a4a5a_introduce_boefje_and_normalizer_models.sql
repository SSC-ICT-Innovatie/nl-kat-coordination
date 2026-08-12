CREATE TYPE scan_level AS ENUM ('0', '1', '2', '3', '4');

CREATE TABLE boefje (
  id SERIAL NOT NULL,
  plugin_id VARCHAR(64) NOT NULL,
  created TIMESTAMP WITH TIME ZONE,
  name VARCHAR(64) NOT NULL,
  description TEXT,
  scan_level scan_level NOT NULL,
  consumes VARCHAR(128)[] NOT NULL,
  produces VARCHAR(128)[] NOT NULL,
  environment_keys VARCHAR(128)[] NOT NULL,
  oci_image VARCHAR(256),
  oci_arguments VARCHAR(128)[] NOT NULL,
  version VARCHAR(16),
  PRIMARY KEY (id),
  UNIQUE (plugin_id)
);

CREATE TABLE normalizer (
    id SERIAL NOT NULL,
    plugin_id VARCHAR(64) NOT NULL,
    created TIMESTAMP WITH TIME ZONE,
    name VARCHAR(64) NOT NULL,
    description TEXT,
    consumes VARCHAR(128)[] NOT NULL,
    produces VARCHAR(128)[] NOT NULL,
    environment_keys VARCHAR(128)[] NOT NULL,
    version VARCHAR(16),
    PRIMARY KEY (id),
    UNIQUE (plugin_id)
);
