#!/usr/bin/env bash
# Apply the independently reviewed NEW-30 matrix transaction exactly.
set -euo pipefail

readonly EXPECTED_SQL_SHA256=79dd34bf23e7b58d0015288a9eaec8fdefcfc2087aa38ccba192408dd67423ef
readonly DB_HOST=root@100.97.136.74
readonly DB_CONTAINER=arcana-postgres
readonly DB_NAME=arcanada_cubrim
readonly EXPECTED_HOSTNAME=arcana-dbs
readonly EXPECTED_MACHINE_ID_SHA256=748cf0730699f386dd0887f621659bc50704eea120753ea9ce0d52aae9e0327e
readonly EXPECTED_CONTAINER_IMAGE=sha256:42e7f6b4e1eceb02ff14e3e6bc6108bbe259abbe83879dc1845d0da1ddeb555d
readonly EXPECTED_PG_SYSTEM_IDENTIFIER=7648390441241305131
readonly EXPECTED_DATABASE_OID=55835
readonly EXPECTED_SERVER_VERSION_NUM=180004
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

read -r -d '' remote_command <<REMOTE || true
set -euo pipefail
actual_hostname=\$(hostname -s)
[[ \$actual_hostname == '$EXPECTED_HOSTNAME' ]] || {
    printf 'remote hostname mismatch: expected %s, got %s\\n' '$EXPECTED_HOSTNAME' "\$actual_hostname" >&2
    exit 1
}
actual_machine_id_sha=\$(sha256sum /etc/machine-id | cut -d ' ' -f1)
[[ \$actual_machine_id_sha == '$EXPECTED_MACHINE_ID_SHA256' ]] || {
    printf 'remote machine-id hash mismatch\\n' >&2
    exit 1
}
actual_container_image=\$(docker inspect '$DB_CONTAINER' --format '{{.Image}}')
[[ \$actual_container_image == '$EXPECTED_CONTAINER_IMAGE' ]] || {
    printf 'container image mismatch: expected %s, got %s\\n' '$EXPECTED_CONTAINER_IMAGE' "\$actual_container_image" >&2
    exit 1
}
actual_pg_identity=\$(docker exec '$DB_CONTAINER' psql -XAt -v ON_ERROR_STOP=1 -U postgres -d '$DB_NAME' -c "SELECT system_identifier FROM pg_control_system(); SELECT oid FROM pg_database WHERE datname=current_database(); SHOW server_version_num;")
expected_pg_identity=\$'$EXPECTED_PG_SYSTEM_IDENTIFIER\\n$EXPECTED_DATABASE_OID\\n$EXPECTED_SERVER_VERSION_NUM'
[[ \$actual_pg_identity == "\$expected_pg_identity" ]] || {
    printf 'PostgreSQL instance identity mismatch\\n' >&2
    exit 1
}
exec docker exec -i '$DB_CONTAINER' psql -X -v ON_ERROR_STOP=1 -U postgres -d '$DB_NAME' -P pager=off
REMOTE
readonly remote_command

timeout 60 ssh -o BatchMode=yes "$DB_HOST" "$remote_command" <"$SQL_FILE"
