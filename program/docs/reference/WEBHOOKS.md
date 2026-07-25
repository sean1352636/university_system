# Webhook System Guide

The Education System includes a shared webhook service for dispatching event notifications to external services. Webhooks are available across all four subsystems.

## Overview

- **Database:** `shared/data/db_files/webhooks.db` (SQLite)
- **Service:** `education_system.shared.webhooks.WebhookService`
- **API routes:** `/api/v1/webhooks/*` (admin only)
- **Retry policy:** 3 attempts with exponential backoff (1 min, 5 min, 15 min)
- **Security:** HMAC-SHA256 payload signing, SSRF protection

## Subscribing to Events

### Via the REST API

```http
POST /api/v1/webhooks/subscriptions
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "url": "https://example.com/hook",
  "event_types": ["student.enrolled", "grade.updated"],
  "system_key": "university",
  "secret": "my-hmac-secret",
  "description": "Notify external SIS on enrollment"
}
```

**Response:**
```json
{
  "message": "Subscription created",
  "id": 1
}
```

### Via Python

```python
from education_system.shared.webhooks import WebhookService

svc = WebhookService()

sub_id = svc.subscribe(
    url="https://example.com/hook",
    event_types=["student.enrolled", "grade.updated"],
    system_key="university",
    secret="my-hmac-secret",
    description="Notify external SIS",
)
```

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `url` | Yes | | HTTPS endpoint to receive POST requests |
| `event_types` | No | `["*"]` | List of event types to subscribe to, or `["*"]` for all |
| `system_key` | No | `"all"` | Filter events by system (`university`, `college`, `school`, `primary`, `all`) |
| `secret` | No | | HMAC-SHA256 secret for payload signing |
| `description` | No | | Human-readable description |

## Event Types

The system uses convention-based event names. Common patterns:

| Event Type | Triggered When |
|------------|----------------|
| `student.enrolled` | A student is enrolled in a course |
| `grade.updated` | A grade is recorded or changed |
| `assignment.submitted` | A student submits an assignment |
| `attendance.recorded` | Attendance is marked |
| `webhook.test` | Manual test via API |

Use `["*"]` to subscribe to all events.

## Dispatching Events

Events are dispatched from application code:

```python
svc.dispatch(
    event_type="student.enrolled",
    payload={"student_id": 123, "course": "CS101", "semester": "2026-S1"},
    system_key="university",
)
```

The service finds all matching subscriptions (by event type and system key) and queues deliveries in a background thread.

## Payload Delivery

Each delivery is an HTTP POST to the subscription URL with these headers:

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `X-Webhook-Event` | The event type (e.g. `student.enrolled`) |
| `X-Webhook-Delivery-Id` | Unique delivery ID |
| `X-Webhook-Signature` | `sha256=<hex>` (only if a secret is configured) |

### Verifying Signatures

If you configured a secret, verify the signature on your receiving end:

```python
import hmac
import hashlib

def verify_signature(payload_bytes, signature_header, secret):
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
```

## Retry Policy

Failed deliveries are retried automatically:

| Attempt | Delay |
|---------|-------|
| 1st retry | 1 minute |
| 2nd retry | 5 minutes |
| 3rd retry | 15 minutes |

After 3 failed attempts the delivery is marked as `failed`.

Delivery statuses: `pending` > `delivered` | `retrying` > `delivered` | `failed`

## Managing Subscriptions

### List Subscriptions

```http
GET /api/v1/webhooks/subscriptions?system_key=university&active_only=true
```

### Delete a Subscription

```http
DELETE /api/v1/webhooks/subscriptions/1
```

This performs a soft delete (sets `is_active = 0`).

### Test a Subscription

```http
POST /api/v1/webhooks/test/1
```

Sends a `webhook.test` event to verify connectivity.

### View Delivery History

```http
GET /api/v1/webhooks/deliveries?limit=50
```

## Security

- **SSRF protection:** Private network URLs (localhost, 10.x, 192.168.x, 172.x) are blocked
- **URL validation:** Only `http://` and `https://` schemes are allowed
- **Timing-safe comparison:** HMAC signatures use `secrets.compare_digest()`
- **Admin-only API:** All webhook endpoints require admin role
