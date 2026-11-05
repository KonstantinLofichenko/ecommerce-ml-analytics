#!/bin/bash
set -euo pipefail
# Fresh PGDATA only. Existing databases (including historical metadata) are preserved.
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set metabase_user="$METABASE_DB_USER" \
  --set metabase_password="$METABASE_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'metabase_user', :'metabase_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname=:'metabase_user') \gexec
SELECT format('CREATE DATABASE metabase_metadata OWNER %I', :'metabase_user')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='metabase_metadata') \gexec
REVOKE ALL ON DATABASE metabase_metadata FROM PUBLIC;
SELECT format('GRANT CONNECT, TEMPORARY ON DATABASE metabase_metadata TO %I', :'metabase_user') \gexec
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
SQL
