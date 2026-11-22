"""Sixth-form alumni — Webhooks (#48, owns ``_webhook_transport``), custom fields (#49) and media attachments (#50).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import json as _json
from dataclasses import dataclass
from typing import Any
from typing import Callable
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    CUSTOM_FIELD_TYPES,
    WEBHOOK_EVENT_TYPES,
    _log_action,
    logger,
)
from .db import (
    ValidationError,
    _connect,
    _row,
    _validate_date,
    init_db,
)


# ── #48 Webhook events ───────────────────────────────────────────

@dataclass
class Webhook:
    webhook_id: int
    url: str
    secret: str | None
    event_types: list[str]
    active: bool
    created_at: str


def _row_webhook(r: db.Row) -> Webhook:
    return Webhook(
        webhook_id=r["webhook_id"], url=r["url"],
        secret=r["secret"],
        event_types=(r["event_types"] or "").split(","),
        active=bool(r["active"]),
        created_at=r["created_at"])


def register_webhook(url: str, *,
                          event_types: list[str],
                          secret: str | None = None,
                          actor: str | None = None) -> Webhook:
    init_db()
    if not (url or "").strip():
        raise ValidationError("Webhook URL is required")
    bad = [e for e in event_types if e not in WEBHOOK_EVENT_TYPES]
    if bad:
        raise ValidationError(
            f"Unknown event type(s): {', '.join(bad)}")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alumni_webhooks
                   (url, secret, event_types) VALUES (?, ?, ?)""",
            (url.strip(),
             (secret or "").strip() or None,
             ",".join(event_types)))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_webhooks WHERE webhook_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("webhook.register", actor=actor, url=url)
    return _row_webhook(r)


def list_webhooks() -> list[Webhook]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_webhooks "
            "ORDER BY webhook_id").fetchall()
    return [_row_webhook(r) for r in rows]


def set_webhook_active(webhook_id: int, active: bool, *,
                            actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_webhooks SET active = ? "
            "WHERE webhook_id = ?", (1 if active else 0, webhook_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No webhook #{webhook_id}")
        conn.commit()
    _log_action("webhook.active", actor=actor,
                  webhook_id=webhook_id, active=active)


def delete_webhook(webhook_id: int, *,
                        actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_webhooks WHERE webhook_id = ?",
            (webhook_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("webhook.delete", actor=actor,
                      webhook_id=webhook_id)
    return cur.rowcount > 0


# Pluggable transport: tests/callers can install their own delivery
# function. The default writes the queued row and leaves delivery to
# an out-of-process worker; pass set_webhook_transport(...) to
# integrate with the shared webhooks bus directly.
_webhook_transport: Callable[[str, str, dict[str, Any]], None] | None \
    = None


def set_webhook_transport(
        fn: Callable[[str, str, dict[str, Any]], None] | None
        ) -> None:
    global _webhook_transport
    _webhook_transport = fn


def _emit_webhook(event_type: str, payload: dict[str, Any]) -> None:
    """Internal helper. Queues a row in alumni_webhook_events and
    fires the configured transport for each subscribed webhook."""
    init_db()
    if event_type not in WEBHOOK_EVENT_TYPES:
        return  # defensive: unknown types are silently dropped
    import json as _json
    payload_json = _json.dumps(payload, default=str)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_webhook_events
                   (event_type, payload_json) VALUES (?, ?)""",
            (event_type, payload_json))
        webhooks = conn.execute(
            "SELECT * FROM alumni_webhooks WHERE active = 1"
            ).fetchall()
        conn.commit()
    if _webhook_transport is None:
        return
    for w in webhooks:
        types = (w["event_types"] or "").split(",")
        if event_type not in types:
            continue
        try:
            _webhook_transport(w["url"], event_type, payload)
        except Exception:
            logger.exception("webhook transport failed url=%s", w["url"])


def list_recent_webhook_events(*, limit: int = 50
                                    ) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_webhook_events "
            "ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── #49 Custom fields per institution ────────────────────────────

@dataclass
class CustomField:
    field_id: int
    name: str
    label: str
    type: str
    created_at: str


def _row_field(r: db.Row) -> CustomField:
    return CustomField(
        field_id=r["field_id"], name=r["name"], label=r["label"],
        type=r["type"], created_at=r["created_at"])


def add_custom_field(name: str, label: str, *,
                          type: str = "text",
                          actor: str | None = None) -> CustomField:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Field name is required")
    if not (label or "").strip():
        raise ValidationError("Field label is required")
    if type not in CUSTOM_FIELD_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(CUSTOM_FIELD_TYPES)}")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_custom_fields
                       (name, label, type) VALUES (?, ?, ?)""",
                (name, label.strip(), type))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"Custom field {name!r} already exists") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_custom_fields WHERE field_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("custom_field.add", actor=actor, name=name, type=type)
    return _row_field(r)


def list_custom_fields() -> list[CustomField]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_custom_fields "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [_row_field(r) for r in rows]


def delete_custom_field(field_id: int, *,
                             actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_custom_fields WHERE field_id = ?",
            (field_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("custom_field.delete", actor=actor,
                      field_id=field_id)
    return cur.rowcount > 0


def _coerce_custom(value: Any, type: str) -> str:
    if value in (None, ""):
        return ""
    if type == "boolean":
        return "1" if value else "0"
    if type == "number":
        return str(float(value))
    if type == "date":
        out = _validate_date(value, "value", required=False)
        return out or ""
    return str(value).strip()


def set_custom_value(alumni_id: int, name: str, value: Any, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT field_id, type FROM alumni_custom_fields "
            "WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        if r is None:
            raise ValidationError(f"No custom field {name!r}")
        coerced = _coerce_custom(value, r["type"])
        _require_alumnus(conn, alumni_id)
        if coerced == "":
            conn.execute(
                "DELETE FROM alumni_custom_values "
                "WHERE alumni_id = ? AND field_id = ?",
                (alumni_id, r["field_id"]))
        else:
            conn.execute(
                """INSERT INTO alumni_custom_values
                       (alumni_id, field_id, value) VALUES (?, ?, ?)
                   ON CONFLICT(alumni_id, field_id) DO UPDATE SET
                       value = excluded.value""",
                (alumni_id, r["field_id"], coerced))
        conn.commit()
    _log_action("custom_field.set", actor=actor,
                  alumni_id=alumni_id, name=name)


def get_custom_values(alumni_id: int) -> dict[str, str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT f.name, v.value
                 FROM alumni_custom_values v
                 JOIN alumni_custom_fields f
                   ON f.field_id = v.field_id
                WHERE v.alumni_id = ?""", (alumni_id,)).fetchall()
    return {r["name"]: r["value"] for r in rows}


def search_by_custom(name: str, value: str) -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.* FROM alumni a
                 JOIN alumni_custom_values v
                   ON v.alumni_id = a.alumni_id
                 JOIN alumni_custom_fields f
                   ON f.field_id = v.field_id
                WHERE f.name = ? COLLATE NOCASE
                  AND v.value = ? COLLATE NOCASE
                  AND a.deleted_at IS NULL
                ORDER BY a.last_name, a.first_name""",
            (name, value)).fetchall()
    return [_row(r) for r in rows]


# ── #50 Photo / media attachments ────────────────────────────────

MEDIA_KINDS: tuple[str, ...] = (
    "photo", "graduation", "speaker_visit", "document", "video",
)


@dataclass
class MediaAttachment:
    media_id: int
    alumni_id: int
    kind: str
    file_path: str
    caption: str | None
    consent_granted: bool
    exif_stripped: bool
    is_profile: bool
    created_at: str


def _row_media(r: db.Row) -> MediaAttachment:
    return MediaAttachment(
        media_id=r["media_id"], alumni_id=r["alumni_id"],
        kind=r["kind"], file_path=r["file_path"],
        caption=r["caption"],
        consent_granted=bool(r["consent_granted"]),
        exif_stripped=bool(r["exif_stripped"]),
        is_profile=bool(r["is_profile"]),
        created_at=r["created_at"])


def _strip_exif(file_path: str) -> bool:
    """Best-effort EXIF strip. Returns True if a strip actually
    happened, False if the file is non-image or Pillow isn't
    installed. Never raises."""
    from pathlib import Path as _Path
    p = _Path(file_path)
    if p.suffix.lower() not in (".jpg", ".jpeg", ".tiff", ".webp",
                                   ".png"):
        return False
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return False
    try:
        with Image.open(p) as im:
            data = list(im.getdata())
            stripped = Image.new(im.mode, im.size)
            stripped.putdata(data)
            stripped.save(p)
        return True
    except Exception:
        logger.exception("EXIF strip failed for %s", file_path)
        return False


def attach_media(alumni_id: int, file_path: str, *,
                      kind: str = "photo",
                      caption: str | None = None,
                      consent_granted: bool = False,
                      strip_exif: bool = True,
                      is_profile: bool = False,
                      actor: str | None = None
                      ) -> MediaAttachment:
    init_db()
    if kind not in MEDIA_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(MEDIA_KINDS)}")
    from pathlib import Path as _Path
    if not _Path(file_path).exists():
        raise ValidationError(f"File not found: {file_path}")
    stripped = _strip_exif(file_path) if strip_exif else False
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if is_profile:
            conn.execute(
                "UPDATE alumni_media SET is_profile = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            """INSERT INTO alumni_media
                   (alumni_id, kind, file_path, caption,
                    consent_granted, exif_stripped, is_profile)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, kind, str(file_path),
             (caption or "").strip() or None,
             1 if consent_granted else 0,
             1 if stripped else 0,
             1 if is_profile else 0))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_media WHERE media_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("media.attach", actor=actor,
                  alumni_id=alumni_id, kind=kind,
                  exif_stripped=stripped, is_profile=is_profile)
    return _row_media(r)


def list_media(alumni_id: int, *,
                    kind: str | None = None
                    ) -> list[MediaAttachment]:
    init_db()
    sql = "SELECT * FROM alumni_media WHERE alumni_id = ?"
    params: list[Any] = [alumni_id]
    if kind:
        sql += " AND kind = ?"; params.append(kind)
    sql += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_media(r) for r in rows]


def set_media_consent(media_id: int, granted: bool, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_media SET consent_granted = ? "
            "WHERE media_id = ?", (1 if granted else 0, media_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No media #{media_id}")
        conn.commit()
    _log_action("media.consent", actor=actor,
                  media_id=media_id, granted=granted)


def set_profile_media(alumni_id: int, media_id: int, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_media "
            "WHERE media_id = ? AND alumni_id = ?",
            (media_id, alumni_id)).fetchone()
        if r is None:
            raise ValidationError(
                f"Media #{media_id} not attached to alumnus "
                f"#{alumni_id}")
        conn.execute(
            "UPDATE alumni_media SET is_profile = 0 "
            "WHERE alumni_id = ?", (alumni_id,))
        conn.execute(
            "UPDATE alumni_media SET is_profile = 1 "
            "WHERE media_id = ?", (media_id,))
        conn.commit()
    _log_action("media.profile", actor=actor,
                  alumni_id=alumni_id, media_id=media_id)


def delete_media(media_id: int, *,
                      delete_file: bool = False,
                      actor: str | None = None) -> bool:
    init_db()
    from pathlib import Path as _Path
    with _connect() as conn:
        r = conn.execute(
            "SELECT file_path FROM alumni_media WHERE media_id = ?",
            (media_id,)).fetchone()
        if r is None:
            return False
        path = r["file_path"]
        conn.execute(
            "DELETE FROM alumni_media WHERE media_id = ?",
            (media_id,))
        conn.commit()
    if delete_file:
        try:
            _Path(path).unlink(missing_ok=True)
        except Exception:
            logger.exception("Failed to unlink %s", path)
    _log_action("media.delete", actor=actor, media_id=media_id)
    return True


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
