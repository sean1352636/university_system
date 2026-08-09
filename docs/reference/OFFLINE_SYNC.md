# Offline Sync Guide

The Education System includes an offline-first data synchronisation service for caching data locally and queuing mutations when the network is unavailable.

## Overview

- **Database:** `shared/data/db_files/offline_sync.db` (SQLite)
- **Service:** `education_system.shared.offline.OfflineSyncService`
- **Cache TTL:** Configurable per entry (default 1 hour)
- **Conflict resolution:** Automatic for simple cases, manual review for conflicts

## Architecture

The offline sync system has three layers:

1. **Cache layer** — stores fetched data locally with TTL-based expiration
2. **Mutation queue** — buffers create/update/delete operations while offline
3. **Sync state** — tracks the last successful sync per entity type and system

```
ONLINE:     App <---> Server       (normal operation)
OFFLINE:    App <---> Local Cache  (reads from cache, writes to queue)
RECONNECT:  Queue --> Server       (replay pending mutations)
```

## Caching Data

### Store Data Locally

```python
from education_system.shared.offline import OfflineSyncService

svc = OfflineSyncService()

svc.cache_set(
    cache_key="student:12345",
    data={"name": "Alice Smith", "course": "CS101", "year": 2},
    system_key="university",
    entity_type="student",
    ttl_seconds=3600,     # 1 hour (default)
    etag="abc123",        # optional, for conditional requests
)
```

### Read Cached Data

```python
data = svc.cache_get("student:12345")
# Returns the dict if cached and not expired, or None
```

### Invalidate Cache

```python
# Invalidate a specific key
svc.cache_invalidate(cache_key="student:12345")

# Invalidate all students in the university system
svc.cache_invalidate(system_key="university", entity_type="student")

# Invalidate everything
svc.cache_invalidate()
```

### Clean Up Expired Entries

```python
deleted_count = svc.cleanup_expired_cache()
```

## Queueing Offline Mutations

When the app is offline, mutations are queued locally instead of being sent to the server.

### Queue a Mutation

```python
mutation_id = svc.queue_mutation(
    operation="update",           # "create", "update", or "delete"
    entity_type="student",
    system_key="university",
    payload={"name": "Alice Smith", "year": 3},
    entity_id="12345",            # optional
    user_id=1,                    # optional
)
```

### Retrieve Pending Mutations

```python
pending = svc.get_pending_mutations(system_key="university", limit=100)

for mutation in pending:
    print(mutation["id"], mutation["operation"], mutation["entity_type"])
```

## Syncing When Back Online

When connectivity is restored, replay the mutation queue:

```python
pending = svc.get_pending_mutations()

for mutation in pending:
    try:
        # Send mutation to the server
        response = send_to_server(mutation)

        if response.ok:
            svc.mark_synced(mutation["id"])
        elif response.status_code == 409:
            svc.mark_conflict(mutation["id"], "Server has a newer version")
        else:
            svc.mark_failed(mutation["id"], f"HTTP {response.status_code}")

    except ConnectionError as e:
        svc.mark_failed(mutation["id"], str(e))

# Update sync state after successful batch
svc.update_sync_state(
    system_key="university",
    entity_type="student",
    sync_token="cursor_abc123",   # optional, for incremental syncs
)
```

## Mutation Statuses

| Status | Meaning |
|--------|---------|
| `pending` | Queued, waiting to be synced |
| `syncing` | Currently being sent to the server |
| `synced` | Successfully synced |
| `conflict` | Server conflict, requires manual resolution |
| `failed` | Failed after retries |

## Conflict Resolution

When a conflict is detected (e.g. server data was modified by another user while offline):

1. The mutation is marked with status `conflict`
2. The error message describes the conflict
3. An admin or the user reviews the conflict
4. The mutation can be retried or discarded

**Default policies:**
- **Enrollment status:** External/server data wins
- **Grades:** Internal/local data wins (unless `force_external_grades` is set)
- **Other entities:** Flagged for manual review

## Monitoring Sync Status

```python
status = svc.get_sync_status()
print(status)
# {
#   "pending_mutations": 3,
#   "conflicts": 1,
#   "failed": 0,
#   "cached_items": 42,
#   "is_online": True,
# }
```

## Checking Last Sync

```python
state = svc.get_sync_state("university", "student")
if state:
    print(f"Last synced: {state['last_sync_at']}")
    print(f"Sync token: {state['last_sync_token']}")
```

## Database Schema

The offline sync database (`offline_sync.db`) contains three tables:

**`sync_cache`** — locally cached data with TTL

**`sync_mutation_queue`** — queued create/update/delete operations

**`sync_state`** — last sync timestamp and token per system/entity
