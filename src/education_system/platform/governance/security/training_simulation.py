"""Authorised ICT security-awareness email simulations.

The link records only that an invited recipient clicked it.  It never asks for
credentials or captures form data.  Campaign creation is intended to be
restricted to superadmins by the delivery layer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import os
import secrets
import socket
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from string import Template
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlparse

from education_system.paths import PLATFORM_EMAIL_TEMPLATES_DIR

_TEMPLATE = PLATFORM_EMAIL_TEMPLATES_DIR / "ict_security_training_simulation.json"
_INVITATION_TEMPLATE = PLATFORM_EMAIL_TEMPLATES_DIR / "ict_security_training_invitation.json"
_UTC = timezone.utc
logger = logging.getLogger(__name__)
_LOCAL_SERVERS: dict[int, Any] = {}
_LOCAL_SERVERS_LOCK = threading.Lock()


class SimulationError(ValueError):
    """Raised when a campaign cannot be safely created or opened."""


@dataclass(frozen=True)
class ClickResult:
    campaign_id: str
    course_name: str
    training_date: str
    training_time: str
    location: str
    first_click: bool


class DatabaseOnlyEmailService:
    """Store campaign messages in the application database; never use SMTP."""

    def __init__(self, store: Callable[..., bool] | None = None) -> None:
        self._store = store

    def send_email(
        self, to: str, subject: str, body: str, html_body: str | None = None, **_kwargs: Any,
    ) -> dict[str, Any]:
        if self._store is not None:
            stored = self._store(
                to, subject, body, None, None, None,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        else:
            recipient_id = _kwargs.get("recipient_id")
            recipient_system = _kwargs.get("recipient_system")
            if recipient_id is None or not recipient_system:
                return {
                    "success": False,
                    "delivery_mode": "database",
                    "error": "Database inbox recipient metadata is missing",
                }
            from education_system.platform.features.messaging.messaging_service import (
                InterSystemMessagingService,
            )
            message = InterSystemMessagingService().send_message(
                sender_id=_kwargs.get("sender_id") or recipient_id,
                sender_system="security_training",
                sender_name="ICT Security Training",
                recipient_id=recipient_id,
                recipient_system=recipient_system,
                recipient_name=_kwargs.get("recipient_name") or to,
                student_name="",
                student_id="",
                subject=subject,
                body=body,
            )
            stored = message is not None
        return {
            "success": bool(stored),
            "delivery_mode": "database",
            **({} if stored else {"error": "Could not store the message in the email database"}),
        }

class SecurityTrainingSimulation:
    """Create, deliver, and record a security-awareness simulation."""

    def __init__(
        self,
        auth_db: str,
        calendar_db: str,
        secret_key: str,
        base_url: str,
        email_service: Any | None = None,
        template_path: str | Path = _TEMPLATE,
    ) -> None:
        if not secret_key:
            raise SimulationError("A persistent signing key is required")
        self.auth_db = auth_db
        self.calendar_db = calendar_db
        self.secret_key = secret_key.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.email_service = email_service or DatabaseOnlyEmailService()
        self.template_path = Path(template_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.auth_db, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_local_invitation_server(self) -> None:
        """Serve invitation links in desktop mode when the main API is absent."""
        parsed = urlparse(self.base_url)
        if parsed.hostname not in {"localhost", "127.0.0.1"}:
            return
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                return  # The unified API (or another configured server) is available.
        except OSError:
            pass

        with _LOCAL_SERVERS_LOCK:
            if port in _LOCAL_SERVERS:
                return
            from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

            service = self

            class InvitationHandler(BaseHTTPRequestHandler):
                def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
                    request_url = urlparse(self.path)
                    if request_url.path != "/security-training/invitation":
                        self.send_error(404)
                        return
                    try:
                        token = parse_qs(request_url.query).get("token", [""])[0]
                        body = invitation_html(service.record_click(token)).encode("utf-8")
                        status = 200
                    except SimulationError as exc:
                        body = (
                            "<!doctype html><title>Invalid invitation</title>"
                            f"<h1>Invitation unavailable</h1><p>{html.escape(str(exc))}</p>"
                        ).encode("utf-8")
                        status = 400
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header(
                        "Content-Security-Policy",
                        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
                    )
                    self.end_headers()
                    self.wfile.write(body)

                def log_message(self, _format: str, *_args: Any) -> None:
                    return

            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), InvitationHandler)
            except OSError as exc:
                raise SimulationError(
                    f"Could not start the local invitation service on port {port}: {exc}"
                ) from exc
            threading.Thread(
                target=server.serve_forever,
                name=f"security-training-invitations-{port}",
                daemon=True,
            ).start()
            _LOCAL_SERVERS[port] = server

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS security_training_campaigns (
                    id TEXT PRIMARY KEY,
                    target_user_id INTEGER NOT NULL,
                    target_system TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    training_date TEXT NOT NULL,
                    training_time TEXT NOT NULL DEFAULT '09:00',
                    location TEXT NOT NULL,
                    calendar_event_id TEXT,
                    created_by INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(target_user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS security_training_recipients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    recipient_type TEXT NOT NULL,
                    email TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    sent_at TEXT,
                    delivery_status TEXT NOT NULL DEFAULT 'pending',
                    first_clicked_at TEXT,
                    click_count INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(campaign_id) REFERENCES security_training_campaigns(id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_security_training_campaign
                    ON security_training_recipients(campaign_id);
                """
            )
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(security_training_campaigns)")
            }
            if "training_time" not in columns:
                conn.execute(
                    "ALTER TABLE security_training_campaigns "
                    "ADD COLUMN training_time TEXT NOT NULL DEFAULT '09:00'"
                )
            recipient_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(security_training_recipients)")
            }
            if "invitation_sent_at" not in recipient_columns:
                conn.execute(
                    "ALTER TABLE security_training_recipients ADD COLUMN invitation_sent_at TEXT"
                )
            if "invitation_delivery_status" not in recipient_columns:
                conn.execute(
                    "ALTER TABLE security_training_recipients "
                    "ADD COLUMN invitation_delivery_status TEXT NOT NULL DEFAULT 'pending'"
                )

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")

    def _make_token(self, recipient_id: int, expires_at: datetime) -> str:
        payload = json.dumps(
            {"rid": recipient_id, "exp": int(expires_at.timestamp()), "n": secrets.token_urlsafe(16)},
            separators=(",", ":"),
        ).encode("utf-8")
        encoded = self._b64(payload)
        signature = self._b64(hmac.new(self.secret_key, encoded.encode(), hashlib.sha256).digest())
        return f"{encoded}.{signature}"

    def _decode_token(self, token: str) -> dict[str, Any]:
        try:
            encoded, supplied = token.split(".", 1)
            expected = self._b64(hmac.new(self.secret_key, encoded.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(supplied, expected):
                raise SimulationError("Invalid invitation link")
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))
            if datetime.now(_UTC).timestamp() > int(payload["exp"]):
                raise SimulationError("This invitation link has expired")
            return payload
        except SimulationError:
            raise
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SimulationError("Invalid invitation link") from exc

    def _recipients(
        self, target_user_id: int, target_system: str, *, include_oversight: bool = True,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            target = conn.execute(
                "SELECT id, username, display_name, email FROM users WHERE id=? AND is_active=1",
                (target_user_id,),
            ).fetchone()
            if not target or not target["email"]:
                raise SimulationError("The selected user has no active email account")
            admins = conn.execute(
                """SELECT DISTINCT u.id, u.username, u.display_name, u.email
                   FROM users u JOIN user_systems us ON us.user_id=u.id
                   WHERE us.system_key=? AND LOWER(us.role)='admin'
                     AND u.is_active=1 AND u.email IS NOT NULL AND u.email!=''""",
                (target_system,),
            ).fetchall()
            superadmins = conn.execute(
                """SELECT u.id, u.username, u.display_name, u.email
                   FROM users u JOIN user_systems us ON us.user_id=u.id
                   WHERE LOWER(us.role)='admin' AND u.is_active=1
                     AND u.email IS NOT NULL AND u.email!=''
                   GROUP BY u.id HAVING COUNT(DISTINCT us.system_key) >= 4"""
            ).fetchall()

        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        groups = [("user", [target])]
        if include_oversight:
            groups.extend((("admin", admins), ("superadmin", superadmins)))
        for recipient_type, rows in groups:
            for row in rows:
                email_address = row["email"].strip().lower()
                if email_address in seen:
                    continue
                seen.add(email_address)
                selected.append({**dict(row), "email": email_address, "recipient_type": recipient_type})
        if include_oversight and not admins:
            raise SimulationError(f"No active admin email was found for {target_system}")
        if include_oversight and not superadmins:
            raise SimulationError("No active superadmin email was found")
        return selected

    def _add_calendar_event(
        self, campaign_id: str, user_id: int, username: str, course_name: str,
        training_date: str, training_time: str, location: str, created_by: int,
    ) -> str:
        event_id = str(uuid.uuid4())
        now = datetime.now(_UTC).isoformat()
        with sqlite3.connect(self.calendar_db, timeout=30) as conn:
            table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='academic_calendar_events'"
            ).fetchone()
            if not table:
                raise SimulationError("The canonical calendar is not available")
            conn.execute(
                """INSERT INTO academic_calendar_events
                   (id, name, date, date_start, date_end, description, event_type,
                    date_added, last_modified, created_by, location, audience,
                    participants, status, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (event_id, course_name, training_date,
                 f"{training_date}T{training_time}:00", f"{training_date}T{training_time}:00",
                 "ICT security-awareness training invitation", "Training", now, now,
                 str(created_by), location, "Private",
                 json.dumps([{"user_id": user_id, "username": username}]), "scheduled"),
            )
        return event_id

    def launch(
        self, target_user_id: int, target_system: str, training_date: str,
        created_by: int, course_name: str = "ICT Security Awareness Training",
        location: str = "Online", training_time: str = "09:00",
        *, include_oversight: bool = True,
    ) -> dict[str, Any]:
        self._ensure_local_invitation_server()
        try:
            parsed_date = date.fromisoformat(training_date)
        except ValueError as exc:
            raise SimulationError("training_date must use YYYY-MM-DD") from exc
        if parsed_date < date.today():
            raise SimulationError("training_date cannot be in the past")
        try:
            datetime.strptime(training_time, "%H:%M")
        except ValueError as exc:
            raise SimulationError("training_time must use 24-hour HH:MM") from exc
        recipients = self._recipients(
            target_user_id, target_system, include_oversight=include_oversight,
        )
        campaign_id = str(uuid.uuid4())
        target = recipients[0]
        calendar_event_id = self._add_calendar_event(
            campaign_id, target_user_id, target["username"], course_name,
            training_date, training_time, location, created_by,
        )
        now = datetime.now(_UTC)
        expires = now + timedelta(days=30)
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO security_training_campaigns
                   (id, target_user_id, target_system, course_name, training_date,
                    training_time, location, calendar_event_id, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (campaign_id, target_user_id, target_system, course_name, training_date,
                 training_time, location, calendar_event_id, created_by, now.isoformat()),
            )
            pending: list[tuple[dict[str, Any], int, str]] = []
            for recipient in recipients:
                cursor = conn.execute(
                    """INSERT INTO security_training_recipients
                       (campaign_id,user_id,recipient_type,email,token_hash,expires_at)
                       VALUES (?,?,?,?,?,?)""",
                    (campaign_id, recipient["id"], recipient["recipient_type"],
                     recipient["email"], secrets.token_hex(32), expires.isoformat()),
                )
                token = self._make_token(cursor.lastrowid, expires)
                conn.execute(
                    "UPDATE security_training_recipients SET token_hash=? WHERE id=?",
                    (hashlib.sha256(token.encode()).hexdigest(), cursor.lastrowid),
                )
                pending.append((recipient, cursor.lastrowid, token))

        template = json.loads(self.template_path.read_text(encoding="utf-8"))
        sent = failed = 0
        results = []
        for recipient, recipient_id, token in pending:
            tracking_url = f"{self.base_url}/security-training/invitation?token={quote(token)}"
            context = {
                "recipient_name": recipient["display_name"] or recipient["username"],
                "tracking_url": tracking_url,
                "link_expiry": expires.date().isoformat(),
                "course_name": course_name,
                "training_date": training_date,
                "training_time": training_time,
                "training_location": location,
            }
            try:
                result = self.email_service.send_email(
                    recipient["email"], Template(template["subject"]).safe_substitute(context),
                    Template(template["body"]).safe_substitute(context),
                    html_body=Template(template["html_body"]).safe_substitute(context),
                    recipient_id=recipient["id"],
                    recipient_system=target_system,
                    recipient_name=recipient["display_name"] or recipient["username"],
                    sender_id=created_by,
                )
            except Exception as exc:
                # A problem delivering to one recipient must not leave all later
                # recipients stuck in the misleading ``pending`` state.
                result = {"success": False, "error": str(exc) or type(exc).__name__}
            status = (
                "stored" if result.get("success") and result.get("delivery_mode") == "database"
                else "sent" if result.get("success") else "failed"
            )
            sent += status in {"sent", "stored"}
            failed += status == "failed"
            with self._connect() as conn:
                conn.execute(
                    "UPDATE security_training_recipients SET delivery_status=?, sent_at=? WHERE id=?",
                    (status, now.isoformat() if status in {"sent", "stored"} else None, recipient_id),
                )
            delivery = {
                "recipient_type": recipient["recipient_type"],
                "email": recipient["email"],
                "status": status,
            }
            if status == "failed":
                delivery["error"] = result.get("error") or "Email provider returned no error details"
            results.append(delivery)
        return {"campaign_id": campaign_id, "calendar_event_id": calendar_event_id,
                "sent": sent, "failed": failed, "recipients": results}

    def launch_all(
        self, training_date: str, created_by: int,
        course_name: str = "ICT Security Awareness Training",
        location: str = "Online", training_time: str = "09:00",
    ) -> dict[str, Any]:
        """Send one simulation to every active user, without duplicate admin copies."""
        try:
            parsed_date = date.fromisoformat(training_date)
        except ValueError as exc:
            raise SimulationError("training_date must use YYYY-MM-DD") from exc
        if parsed_date < date.today():
            raise SimulationError("training_date cannot be in the past")
        try:
            datetime.strptime(training_time, "%H:%M")
        except ValueError as exc:
            raise SimulationError("training_time must use 24-hour HH:MM") from exc

        with self._connect() as conn:
            rows = conn.execute(
                """SELECT u.id, MIN(us.system_key) AS target_system
                   FROM users u
                   JOIN user_systems us ON us.user_id=u.id
                   WHERE u.is_active=1 AND u.email IS NOT NULL AND TRIM(u.email)!=''
                   GROUP BY u.id ORDER BY u.id"""
            ).fetchall()
        if not rows:
            raise SimulationError("No active users with email addresses were found")

        campaigns = []
        sent = failed = 0
        recipients: list[dict[str, Any]] = []
        calendar_event_ids = []
        for row in rows:
            try:
                result = self.launch(
                    int(row["id"]), row["target_system"], training_date, created_by,
                    course_name, location, training_time, include_oversight=False,
                )
            except Exception as exc:
                failed += 1
                recipients.append({
                    "recipient_type": "user", "email": "", "status": "failed",
                    "user_id": int(row["id"]),
                    "error": str(exc) or type(exc).__name__,
                })
                continue
            campaigns.append(result["campaign_id"])
            calendar_event_ids.append(result["calendar_event_id"])
            sent += result["sent"]
            failed += result["failed"]
            recipients.extend(result["recipients"])
        return {
            "campaign_ids": campaigns,
            "calendar_event_ids": calendar_event_ids,
            "targeted": len(rows),
            "sent": sent,
            "failed": failed,
            "recipients": recipients,
        }

    def record_click(self, token: str) -> ClickResult:
        payload = self._decode_token(token)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(_UTC).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """SELECT r.id, r.user_id, r.email, r.token_hash, r.expires_at,
                          r.first_clicked_at, r.invitation_delivery_status,
                          c.id campaign_id, c.course_name, c.training_date,
                          c.training_time, c.location, c.target_system
                   FROM security_training_recipients r
                   JOIN security_training_campaigns c ON c.id=r.campaign_id
                   WHERE r.id=?""",
                (int(payload["rid"]),),
            ).fetchone()
            if not row or not hmac.compare_digest(row["token_hash"], token_hash):
                raise SimulationError("Invalid invitation link")
            if datetime.fromisoformat(row["expires_at"]) < datetime.now(_UTC):
                raise SimulationError("This invitation link has expired")
            first_click = row["first_clicked_at"] is None
            conn.execute(
                """UPDATE security_training_recipients
                   SET first_clicked_at=COALESCE(first_clicked_at, ?), click_count=click_count+1
                   WHERE id=?""",
                (now, row["id"]),
            )
            should_notify = row["invitation_delivery_status"] not in {"sending", "sent", "stored"}
            if should_notify:
                conn.execute(
                    "UPDATE security_training_recipients "
                    "SET invitation_delivery_status='sending' WHERE id=?",
                    (row["id"],),
                )
        if should_notify:
            self._send_click_invitation(dict(row))
        return ClickResult(
            row["campaign_id"], row["course_name"], row["training_date"],
            row["training_time"], row["location"], first_click,
        )

    def _send_click_invitation(self, recipient: dict[str, Any]) -> None:
        """Send the real course invitation after a simulation link is opened."""
        context = {
            "course_name": recipient["course_name"],
            "training_date": recipient["training_date"],
            "training_time": recipient["training_time"],
            "training_location": recipient["location"],
        }
        template = json.loads(_INVITATION_TEMPLATE.read_text(encoding="utf-8"))
        try:
            result = self.email_service.send_email(
                recipient["email"],
                Template(template["subject"]).safe_substitute(context),
                Template(template["body"]).safe_substitute(context),
                html_body=Template(template["html_body"]).safe_substitute(context),
                recipient_id=recipient["user_id"],
                recipient_system=recipient["target_system"],
                recipient_name=recipient["email"],
            )
            status = (
                "stored" if result.get("success") and result.get("delivery_mode") == "database"
                else "sent" if result.get("success") else "failed"
            )
        except Exception:
            status = "failed"
            logger.exception("Could not send security-training click invitation")
        with self._connect() as conn:
            conn.execute(
                """UPDATE security_training_recipients
                   SET invitation_delivery_status=?, invitation_sent_at=? WHERE id=?""",
                (status, datetime.now(_UTC).isoformat() if status in {"sent", "stored"} else None,
                 recipient["id"]),
            )

    def campaign_report(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return aggregate delivery and click results for admin interfaces."""
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                """SELECT c.id, c.course_name, c.training_date, c.training_time, c.target_system,
                          c.created_at, COUNT(r.id) AS recipients,
                          SUM(CASE WHEN r.delivery_status IN ('sent','stored') THEN 1 ELSE 0 END) AS sent,
                          SUM(CASE WHEN r.delivery_status='failed' THEN 1 ELSE 0 END) AS failed,
                          SUM(CASE WHEN r.first_clicked_at IS NOT NULL THEN 1 ELSE 0 END) AS clicked
                   FROM security_training_campaigns c
                   LEFT JOIN security_training_recipients r ON r.campaign_id=c.id
                   GROUP BY c.id ORDER BY c.created_at DESC LIMIT ?""",
                (max(1, min(int(limit), 500)),),
            ).fetchall()]

    def training_register(self, limit: int = 2000) -> list[dict[str, Any]]:
        """Return recipient-level click results and course registrations."""
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(
                """SELECT r.id recipient_id, r.campaign_id, r.user_id,
                          u.username, u.display_name, r.email, r.recipient_type,
                          r.delivery_status, r.first_clicked_at, r.click_count,
                          r.invitation_delivery_status, r.invitation_sent_at,
                          c.target_system, c.course_name, c.training_date,
                          c.training_time, c.location, c.calendar_event_id,
                          CASE WHEN r.user_id=c.target_user_id THEN 1 ELSE 0 END AS registered
                   FROM security_training_recipients r
                   JOIN security_training_campaigns c ON c.id=r.campaign_id
                   JOIN users u ON u.id=r.user_id
                   ORDER BY c.training_date DESC, c.training_time DESC,
                            COALESCE(u.display_name, u.username), r.id DESC
                   LIMIT ?""",
                (max(1, min(int(limit), 10000)),),
            ).fetchall()]


def default_simulation(email_service: Any | None = None) -> SecurityTrainingSimulation:
    """Build the shared service for CLI/GUI use from production configuration."""
    from education_system.platform.identity.auth.db import AUTH_DB_FILE
    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH

    secret = os.environ.get("SECURITY_TRAINING_SIGNING_KEY") or os.environ.get("API_SECRET_KEY")
    base_url = os.environ.get("SECURITY_TRAINING_BASE_URL", "").rstrip("/")
    if not secret:
        raise SimulationError(
            "Set SECURITY_TRAINING_SIGNING_KEY (or API_SECRET_KEY) before launching a campaign"
        )
    if not base_url.startswith(("https://", "http://localhost", "http://127.0.0.1")):
        raise SimulationError(
            "Set SECURITY_TRAINING_BASE_URL to the HTTPS address of the web application"
        )
    service = SecurityTrainingSimulation(
        str(AUTH_DB_FILE), str(UNIVERSITY_DEFAULT_DB_PATH), secret, base_url,
        email_service=email_service or DatabaseOnlyEmailService(),
    )
    # Opening the dashboard/CLI section also revives links from earlier
    # database-stored campaigns, not only links created in this process.
    service._ensure_local_invitation_server()
    return service


def invitation_html(result: ClickResult) -> str:
    """Return the intentionally non-interactive training invitation page."""
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ICT security training invitation</title></head>
<body style='font-family:Arial,sans-serif;background:#eef2f5;padding:32px'>
<main style='max-width:680px;margin:auto;background:white;border-radius:10px;padding:36px'>
<h1 style='color:#173b57'>You have been invited to ICT security training</h1>
<p>This was an authorised security-awareness email test. No password or personal information was collected.</p>
<h2>{html.escape(result.course_name)}</h2>
<p><strong>Date:</strong> {html.escape(result.training_date)}<br>
<strong>Time:</strong> {html.escape(result.training_time)}<br>
<strong>Location:</strong> {html.escape(result.location)}</p>
<p>The course has been added to your calendar.</p>
</main></body></html>"""
