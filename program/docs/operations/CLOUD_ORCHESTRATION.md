# Cloud orchestration runbook

The production topology separates the authenticated gateway from the public,
read-only credential verifier. Both use the same immutable image. Institution
data remains database-per-tenant on persistent storage. Containers run behind
Gunicorn; Flask's development server is not used by either workload.

## Kubernetes

1. Build and push the image; replace `education-system:latest` through a
   Kustomize overlay with an immutable digest.
2. Copy `deploy/kubernetes/secret.example.yaml`, replace every value using a
   secret manager, and apply it. Never commit the resulting file.
3. Set the ingress hostname/TLS secret and storage class, then run
   `kubectl apply -k deploy/kubernetes/base`.
4. Confirm rollout and probes with `kubectl -n education-system get pods` and
   `kubectl -n education-system rollout status deployment/education-api`.
5. Run tenant provisioning as a one-off administrative job before routing an
   institution. `MULTI_TENANT_REQUIRED=true` ensures unidentified requests
   fail closed.

Run `python program/tools/validate_deployment.py` in CI and before applying a
release. Legacy databases are moved with
`TenantDatabaseManager.migrate_database_to_tenant`; it refuses overwrite by
default and performs an SQLite integrity check before promotion.

SQLite uses a ReadWriteOnce volume and a single API writer replica. Do not
increase API replicas until moving tenant storage to a multi-writer database.
The read-only verifier may be scaled only where the storage provider permits
multiple pod mounts on the same node; otherwise use one replica.

## Docker Swarm

Create the three external secrets named in `deploy/docker-stack.yml`, provide
the TLS/proxy configuration, then deploy with
`docker stack deploy -c deploy/docker-stack.yml education`. Validate both
service health endpoints after every rollout and take a tenant-aware backup
before schema changes.

## Rollback and recovery

Use immutable image tags. Roll back the Deployment/stack image, restore only
the affected tenant database from its online SQLite backup, and verify tenant
headers plus credential proofs before reopening traffic.
