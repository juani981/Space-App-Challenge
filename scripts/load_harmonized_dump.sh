#!/usr/bin/env bash
# ==============================================================================
# Post-Delivery Loader for Teammates' `harmonized_web.dump` (PostgreSQL 18)
# Follows Section 5 of docs/DOCUMENTACION_TABLA_ARMONIZADA.md
#
# Usage:
#   DUMP_FILE=./harmonized_web.dump ./scripts/load_harmonized_dump.sh
# Optional env vars: PGHOST, PGPORT, PGUSER, PGDATABASE, READONLY_USER
# ==============================================================================
set -euo pipefail

DUMP_FILE="${DUMP_FILE:-}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-hotspots_db}"
READONLY_USER="${READONLY_USER:-web_readonly}"

if [[ -z "${DUMP_FILE}" || ! -f "${DUMP_FILE}" ]]; then
  echo "ERROR: Set DUMP_FILE to a valid .dump file path (e.g. DUMP_FILE=./harmonized_web.dump)." >&2
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
  SUM(n_eq)       AS sum_n_eq,
  SUM(f_eq)       AS sum_f_eq,
  array_agg(DISTINCT method_version) AS method_versions
FROM harmonized.cell_month;
"

echo "[4/5] Ensuring index on (cell_id, month), running CLUSTER + ANALYZE..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "
DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'harmonized' AND tablename = 'cell_month'
      AND indexdef LIKE '%(cell_id, month)%'
  ) THEN
    CREATE INDEX idx_cell_month_cell_month ON harmonized.cell_month (cell_id, month);
  END IF;
END \$\$;
"
IDX_NAME=$(psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "
SELECT indexname FROM pg_indexes
WHERE schemaname = 'harmonized' AND tablename = 'cell_month'
  AND indexdef LIKE '%(cell_id, month)%'
LIMIT 1;
")
if [[ -n "${IDX_NAME}" ]]; then
  psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
    -c "CLUSTER harmonized.cell_month USING ${IDX_NAME}; ANALYZE harmonized.cell_month;"
fi

echo "[5/5] Granting read-only SELECT privileges on schema harmonized to ${READONLY_USER}..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${READONLY_USER}') THEN
    CREATE ROLE ${READONLY_USER} NOLOGIN;
  END IF;
END \$\$;
GRANT USAGE ON SCHEMA harmonized TO ${READONLY_USER};
GRANT SELECT ON ALL TABLES IN SCHEMA harmonized TO ${READONLY_USER};
"

echo "Done. Inspect \\d+ harmonized.cell_month and update PENDING_TEAM_CONFIRMATION in backend/harmonized_cell_month.py."
