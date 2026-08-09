#!/usr/bin/env bash
# Apply the independently reviewed NEW-30 matrix transaction exactly.
set -euo pipefail

readonly EXPECTED_SQL_SHA256=4f12c1c968f3e3d8239ed2ce2bc77dcb2b4eab1d5ef468b07413efd184cd2ea8
readonly DB_HOST=root@100.97.136.74
readonly DB_CONTAINER=arcana-postgres
readonly DB_NAME=arcanada_cubrim
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly SCRIPT_DIR
readonly SQL_FILE=$SCRIPT_DIR/db-insert.sql

[[ $# == 1 && $1 == --apply ]] || {
    printf 'usage: %s --apply\n' "$0" >&2
    exit 2
}

actual_sql_sha=$(sha256sum "$SQL_FILE" | cut -d ' ' -f1)
[[ $actual_sql_sha == "$EXPECTED_SQL_SHA256" ]] || {
    printf 'reviewed SQL hash mismatch: expected %s, got %s\n' \
        "$EXPECTED_SQL_SHA256" "$actual_sql_sha" >&2
    exit 1
}

timeout 60 ssh -o BatchMode=yes "$DB_HOST" \
    "docker exec -i $DB_CONTAINER psql -X -v ON_ERROR_STOP=1 -U postgres -d $DB_NAME -P pager=off" \
    <"$SQL_FILE"
