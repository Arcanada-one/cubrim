# Hub deployment (OPERATOR-GATED: the hub is a prod node)

Deploying the sync/ingest side on the hub **is a prod-deploy** and happens
only on the operator's go. Everything below is prepared and tested locally
(two-directory simulation) without touching any fleet host.

1. `setup.sh <store-root> hub` — layout; asserts staging/store share one fs;
   `staging/` and `journal/` are chmod 700 and OUTSIDE the rrsync trees.
2. Create a dedicated low-privilege user for sync; install per-spoke keys
   from `authorized_keys.template` (rrsync write-only inbox + read-only
   snapshots; `restrict` — no shell, no pty, no forwarding).
3. Schedule `ingest-hub.sh <store-root>` (systemd timer or cron on the
   operator's terms). Quota via `ADDR_SPOKE_QUOTA_BYTES` (default 10 GiB).
4. Publish epochs with `publish-snapshot.sh` after catalog/bloom updates.
5. No new listeners: everything rides the existing sshd over Tailscale.
