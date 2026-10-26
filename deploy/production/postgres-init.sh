#!/bin/sh
set -eu
# psql variables quote passwords as SQL literals; no secret is printed.
OWNER_PASSWORD=$(cat /run/secrets/owner-password)
RUNTIME_PASSWORD=$(cat /run/secrets/runtime-password)
export OWNER_PASSWORD RUNTIME_PASSWORD
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv owner_password OWNER_PASSWORD
\getenv runtime_password RUNTIME_PASSWORD
CREATE ROLE wbe_owner LOGIN PASSWORD :'owner_password';
CREATE ROLE wbe_runtime LOGIN PASSWORD :'runtime_password';
CREATE DATABASE wbe OWNER wbe_owner;
REVOKE ALL ON DATABASE wbe FROM PUBLIC;
GRANT CONNECT ON DATABASE wbe TO wbe_runtime;
\connect wbe
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO wbe_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE wbe_owner IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wbe_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE wbe_owner IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO wbe_runtime;
SQL
