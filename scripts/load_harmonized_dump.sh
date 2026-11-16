#!/usr/bin/env bash
# ==============================================================================
# Post-Delivery Loader for Teammates' `wildfire-armonizado.dump` (PostgreSQL 18)
# Aligned with docs/CONTRATO_DATOS_WEB_RESPUESTA_V02.md (Sections 7 & 8)
#
# Usage:
#   DUMP_FILE=./wildfire-armonizado.dump READONLY_PASS=secret ./scripts/load_harmonized_dump.sh
# Optional env vars: PGHOST, PGPORT, PGUSER, PGDATABASE, READONLY_USER, READONLY_PASS
# ==============================================================================
set -euo pipefail

DUMP_FILE="${DUMP_FILE:-}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-hotspots_db}"
READONLY_USER="${READONLY_USER:-wildfire_web}"
READONLY_PASS="${READONLY_PASS:-wildfire_web_readonly_change_me}"

if [[ -z "${DUMP_FILE}" || ! -f "${DUMP_FILE}" ]]; then
  echo "ERROR: Set DUMP_FILE to a valid .dump file path (e.g. DUMP_FILE=./wildfire-armonizado.dump)." >&2
  exit 1
fi

echo "[1/5] Ensuring schema harmonized exists on ${PGHOST}:${PGPORT}/${PGDATABASE}..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
  -c "CREATE SCHEMA IF NOT EXISTS harmonized;"

echo "[2/5] Restoring ${DUMP_FILE} (--no-owner)..."
pg_restore -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
  --no-owner --if-exists --clean "${DUMP_FILE}"

echo "[3/5] Verifying row count, SUM(n_eq), SUM(f_eq) and method_version..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "
SELECT
  COUNT(*)        AS row_count,
  MIN(month)      AS min_month,
  MAX(month)      AS max_month,
  SUM(n_eq::float8) AS sum_n_eq,
  SUM(f_eq::float8) AS sum_f_eq,
  array_agg(DISTINCT method_version) AS method_versions
FROM harmonized.cell_month;
"

echo "[4/5] Verifying index on (cell_id, month), running VACUUM ANALYZE..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "
DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'harmonized' AND tablename = 'cell_month'
      AND (indexdef LIKE '%(cell_id, month)%' OR indexdef LIKE '%(cell_id,month)%')
  ) THEN
    CREATE INDEX idx_cell_month_cell_month ON harmonized.cell_month (cell_id, month);
  END IF;
END \$\$;
"
# VACUUM no puede correr dentro de un bloque de transacción: un `psql -c` con varias sentencias
# se ejecuta como una sola transacción, así que cada VACUUM va en su propio -c.
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
  -c "VACUUM ANALYZE harmonized.cell_month;" \
  -c "VACUUM ANALYZE harmonized.map_month;" \
  -c "VACUUM ANALYZE harmonized.reference_plan;"

echo "[5/5] Configuring hardened read-only role ${READONLY_USER} (Sec 7)..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${READONLY_USER}') THEN
    CREATE ROLE ${READONLY_USER} LOGIN PASSWORD '${READONLY_PASS}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 20;
  END IF;
END \$\$;
REVOKE ALL ON DATABASE \"${PGDATABASE}\" FROM PUBLIC;
GRANT CONNECT ON DATABASE \"${PGDATABASE}\" TO ${READONLY_USER};
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA harmonized TO ${READONLY_USER};
GRANT SELECT ON ALL TABLES IN SCHEMA harmonized TO ${READONLY_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA harmonized GRANT SELECT ON TABLES TO ${READONLY_USER};

ALTER ROLE ${READONLY_USER} SET default_transaction_read_only = on;
ALTER ROLE ${READONLY_USER} SET search_path = harmonized, public;
ALTER ROLE ${READONLY_USER} SET statement_timeout = '5s';
ALTER ROLE ${READONLY_USER} SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE ${READONLY_USER} SET lock_timeout = '2s';
ALTER ROLE ${READONLY_USER} SET work_mem = '64MB';
ALTER ROLE ${READONLY_USER} SET jit = off;
"

echo "Done. Backend ready for read-only v0.2 harmonized queries."
