"""Webhook registration, dispatch, and retry system.

Provides a shared webhook infrastructure for all education systems.
Events (e.g. student.enrolled, grade.updated) can be subscribed to
by external services via registered webhook URLs.
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from education_system.paths import PLATFORM_DB_FILES_DIR

logger = logging.getLogger(__name__)


class WebhookURLError(ValueError):
    """Raised when a webhook destination URL is not permitted."""


def _dev_env() -> bool:
    return os.getenv("APP_ENV", "production").strip().lower() in (
        "development", "dev", "local", "test", "testing",
    )


def validate_webhook_url(url: str) -> str:
    """Validate an outbound webhook destination against SSRF abuse.

    Enforces an https scheme (http permitted only in development), and refuses
    any URL whose host resolves to a loopback, private, link-local, multicast
    or reserved address — the ranges an attacker would target to reach the
    cloud metadata endpoint or internal services. Resolution happens here and
    again immediately before each delivery to blunt DNS-rebinding.
    """
    if not url or not isinstance(url, str):
        raise WebhookURLError("A webhook URL is required")
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    allowed_schemes = {"https", "http"} if _dev_env() else {"https"}
    if scheme not in allowed_schemes:
        raise WebhookURLError(
            f"Webhook URL scheme {scheme!r} not allowed; use https"
        )
    host = parts.hostname
    if not host:
        raise WebhookURLError("Webhook URL has no host")
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if scheme == "https" else 80),
                                   proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise WebhookURLError(f"Webhook host could not be resolved: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            if _dev_env() and (ip.is_loopback or ip.is_private):
                # Local dev targets (localhost) are allowed only in dev.
                continue
            raise WebhookURLError(
                f"Webhook host {host!r} resolves to a non-routable address ({ip})"
            )
    return url.strip()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT    NOT NULL,
    event_types TEXT    NOT NULL DEFAULT '["*"]',
    system_key  TEXT    NOT NULL DEFAULT 'all',
    secret      TEXT,
    is_active   INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    created_by  INTEGER
);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    subscription_id  INTEGER NOT NULL REFERENCES webhook_subscriptions(id),
    event_type       TEXT    NOT NULL,
    payload          TEXT,
    status_code      INTEGER,
    response_body    TEXT,
    attempt          INTEGER NOT NULL DEFAULT 1,
    delivered_at     TEXT,
    next_retry_at    TEXT,
    status           TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'delivered', 'failed', 'retrying')),
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_wh_delivery_status ON webhook_deliveries(status);
"""

_MAX_RETRIES = 3
_RETRY_DELAYS = [60, 300, 900]  # 1min, 5min, 15min


def _get_db_path():
    PLATFORM_DB_FILES_DIR.mkdir(parents=True, exist_ok=True)
    return str(PLATFORM_DB_FILES_DIR / "webhooks.db")


class WebhookService:
    """Webhook management and dispatch."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _get_db_path()
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def subscribe(self, url: str, event_types: list[str] | None = None,
                  system_key: str = "all", secret: str | None = None,
                  description: str | None = None, created_by: int | None = None) -> int:
        """Register a webhook subscription. Returns the subscription ID."""
        # Reject SSRF targets at registration time (and again at delivery).
        url = validate_webhook_url(url)
        # A subscription with no secret would receive unsigned deliveries the
        # receiver cannot authenticate; require one.
        if not secret:
            raise WebhookURLError("A signing secret is required for webhook subscriptions")
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO webhook_subscriptions
                   (url, event_types, system_key, secret, description, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (url, json.dumps(event_types or ["*"]), system_key, secret,
                 description, created_by),
            )
            conn.commit()
            logger.info("Webhook subscription created: id=%d url=%s", cursor.lastrowid, url)
            return cursor.lastrowid
        finally:
            conn.close()

    def unsubscribe(self, subscription_id: int) -> bool:
        """Deactivate a webhook subscription."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "UPDATE webhook_subscriptions SET is_active = 0 WHERE id = ?",
                (subscription_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def list_subscriptions(self, system_key: str | None = None, active_only: bool = True) -> list[dict]:
        """List webhook subscriptions."""
        conn = self._conn()
        try:
            conditions = []
            params = []
            if active_only:
                conditions.append("is_active = 1")
            if system_key:
                conditions.append("(system_key = ? OR system_key = 'all')")
                params.append(system_key)
            where = " AND ".join(conditions) if conditions else "1=1"
            rows = conn.execute(
                f"SELECT * FROM webhook_subscriptions WHERE {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
            # Never return the signing secret in a listing — it is write-only
            # from the API's perspective once set.
            result = []
            for r in rows:
                d = dict(r)
                if d.get("secret"):
                    d["secret"] = "***"
                result.append(d)
            return result
        finally:
            conn.close()

    def get_recent_deliveries(self, limit: int = 50) -> list[dict]:
        """Get recent webhook deliveries."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM webhook_deliveries ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def dispatch(self, event_type: str, payload: dict, system_key: str = "shared") -> int:
        """Dispatch an event to all matching subscribers.

        Returns the number of deliveries queued.
        """
        conn = self._conn()
        try:
            subs = conn.execute(
                "SELECT * FROM webhook_subscriptions WHERE is_active = 1 AND (system_key = ? OR system_key = 'all')",
                (system_key,),
            ).fetchall()

            count = 0
            for sub in subs:
                event_types = json.loads(sub["event_types"])
                if "*" not in event_types and event_type not in event_types:
                    continue

                conn.execute(
                    """INSERT INTO webhook_deliveries
                       (subscription_id, event_type, payload, status)
                       VALUES (?, ?, ?, 'pending')""",
                    (sub["id"], event_type, json.dumps(payload, default=str)),
                )
                count += 1

            conn.commit()
        finally:
            conn.close()

        # Process deliveries in background
        if count > 0:
            threading.Thread(target=self._process_pending, daemon=True).start()

        return count

    def _process_pending(self):
        """Process all pending webhook deliveries."""
        import urllib.request
        import urllib.error

        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT d.*, s.url, s.secret FROM webhook_deliveries d
                   JOIN webhook_subscriptions s ON s.id = d.subscription_id
                   WHERE d.status IN ('pending', 'retrying')
                   ORDER BY d.created_at LIMIT 50""",
            ).fetchall()
        finally:
            conn.close()

        for row in rows:
            self._deliver(dict(row))

    def _deliver(self, delivery: dict):
        """Attempt to deliver a single webhook."""
        import urllib.request
        import urllib.error

        payload = delivery["payload"]
        data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": delivery["event_type"],
            "X-Webhook-Delivery-Id": str(delivery["id"]),
            "X-Webhook-Timestamp": timestamp,
        }

        # Sign the timestamp AND body so a captured request cannot be replayed
        # indefinitely: the receiver rejects a stale timestamp, and the
        # timestamp is bound into the MAC so it cannot be rewritten.
        if delivery.get("secret"):
            signature = hmac.new(
                delivery["secret"].encode(),
                timestamp.encode() + b"." + data,
                hashlib.sha256,
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        try:
            # Re-validate immediately before connecting: the DNS answer may
            # have changed since subscription (rebinding).
            validate_webhook_url(delivery["url"])
            req = urllib.request.Request(
                delivery["url"], data=data, headers=headers, method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=10)
            status_code = resp.getcode()
            self._update_delivery(delivery["id"], "delivered", status_code)
        except urllib.error.HTTPError as e:
            self._handle_failure(delivery, e.code, str(e))
        except Exception as e:
            self._handle_failure(delivery, 0, str(e))

    def _handle_failure(self, delivery: dict, status_code: int, error: str):
        attempt = delivery.get("attempt", 1)
        if attempt < _MAX_RETRIES:
            delay = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
            next_retry = datetime.utcnow().timestamp() + delay
            self._update_delivery(
                delivery["id"], "retrying", status_code,
                response=error, attempt=attempt + 1,
                next_retry=datetime.utcfromtimestamp(next_retry).isoformat(),
            )
        else:
            self._update_delivery(delivery["id"], "failed", status_code, response=error)
            logger.warning("Webhook delivery %d permanently failed: %s", delivery["id"], error)

    def _update_delivery(self, delivery_id: int, status: str, status_code: int = 0,
                         response: str = "", attempt: int | None = None,
                         next_retry: str | None = None):
        conn = self._conn()
        try:
            updates = ["status = ?", "status_code = ?", "response_body = ?", "delivered_at = strftime('%Y-%m-%dT%H:%M:%S', 'now')"]
            params = [status, status_code, response[:1000] if response else ""]
            if attempt:
                updates.append("attempt = ?")
                params.append(attempt)
            if next_retry:
                updates.append("next_retry_at = ?")
                params.append(next_retry)
            params.append(delivery_id)
            conn.execute(f"UPDATE webhook_deliveries SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        finally:
            conn.close()
