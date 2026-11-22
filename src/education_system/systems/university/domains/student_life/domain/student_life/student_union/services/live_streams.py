"""Scheduled Student Union live streams.

Backs the Live Streaming screens, which used to list made-up streams,
viewer counts, chat and recordings. Two new tables:

* ``live_streams`` — one row per stream: title, the club and/or SU event
  it belongs to, platform, stream URL, scheduled start/end, status
  (scheduled → live → ended, or cancelled), the actual start/end times,
  an optional recording URL, and viewer figures **only if someone
  recorded them** (NULL otherwise — nothing is estimated).
* ``live_stream_chat`` — messages posted on the stream's moderation
  chat from this app, with a hidden flag for moderation.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

STATUSES = ("scheduled", "live", "ended", "cancelled")
PLATFORMS = ("YouTube Live", "Facebook Live", "Twitch", "LinkedIn Live",
             "Instagram Live", "Microsoft Teams", "Zoom", "Custom RTMP", "Other")
QUALITIES = ("1080p", "720p", "480p", "360p", "Auto")

_STREAMS_SQL = """
CREATE TABLE IF NOT EXISTS live_streams (
    stream_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    club_id INTEGER,
    event_id INTEGER,
    platform TEXT,
    stream_url TEXT,
    quality TEXT,
    scheduled_start TEXT NOT NULL,
    scheduled_end TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled', 'live', 'ended', 'cancelled')),
    actual_start TEXT,
    actual_end TEXT,
    record_stream INTEGER NOT NULL DEFAULT 1,
    chat_enabled INTEGER NOT NULL DEFAULT 1,
    chat_banned TEXT,
    peak_viewers INTEGER,
    recording_url TEXT,
    recording_views INTEGER,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (club_id) REFERENCES student_clubs (club_id),
    FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
)"""

_CHAT_SQL = """
CREATE TABLE IF NOT EXISTS live_stream_chat (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stream_id INTEGER NOT NULL,
    author TEXT NOT NULL,
    message TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (stream_id) REFERENCES live_streams (stream_id) ON DELETE CASCADE
)"""

_ensured: set[str] = set()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dicts(cur) -> list[dict[str, Any]]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def ensure_schema(conn) -> None:
    try:
        key = str(conn.execute("PRAGMA database_list").fetchone()[2])
    except Exception:  # pragma: no cover - defensive
        key = str(id(conn))
    if key in _ensured:
        return
    conn.execute(_STREAMS_SQL)
    conn.execute(_CHAT_SQL)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_live_streams_status "
                 "ON live_streams (status, scheduled_start)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_live_stream_chat_stream "
                 "ON live_stream_chat (stream_id, posted_at)")
    conn.commit()
    _ensured.add(key)


def _parse_dt(value: str | None, label: str, required: bool = False) -> str | None:
    text = (value or "").strip().replace("T", " ")
    if not text:
        if required:
            raise ValueError(f"{label} is required (YYYY-MM-DD HH:MM).")
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    raise ValueError(f"{label} must be YYYY-MM-DD HH:MM.")


_SELECT = (
    "SELECT ls.*, sc.club_name, ue.title AS event_title, "
    "(SELECT COUNT(*) FROM live_stream_chat c WHERE c.stream_id = ls.stream_id "
    " AND c.hidden = 0) AS chat_count "
    "FROM live_streams ls "
    "LEFT JOIN student_clubs sc ON sc.club_id = ls.club_id "
    "LEFT JOIN unified_events ue ON ue.event_id = ls.event_id ")


def list_streams(conn, *, status: str | tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    ensure_schema(conn)
    params: list[Any] = []
    sql = _SELECT
    if status:
        wanted = (status,) if isinstance(status, str) else tuple(status)
        sql += "WHERE ls.status IN (%s) " % ",".join("?" for _ in wanted)
        params.extend(wanted)
    sql += "ORDER BY ls.scheduled_start"
    return _dicts(conn.execute(sql, params))


def get_stream(conn, stream_id: int) -> dict[str, Any] | None:
    ensure_schema(conn)
    rows = _dicts(conn.execute(_SELECT + "WHERE ls.stream_id = ?", (stream_id,)))
    return rows[0] if rows else None


def save_stream(conn, data: dict[str, Any], *, actor: str | None,
                stream_id: int | None = None) -> int:
    ensure_schema(conn)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("A stream title is required.")
    start = _parse_dt(data.get("scheduled_start"), "Start", required=True)
    end = _parse_dt(data.get("scheduled_end"), "End")
    if end and end <= start:
        raise ValueError("The end must be after the start.")
    url = (data.get("stream_url") or "").strip()
    if url and "://" not in url:
        raise ValueError("The stream URL must start with http://, https:// or rtmp://.")
    club_id = data.get("club_id") or None
    event_id = data.get("event_id") or None
    values = (title, (data.get("description") or "").strip() or None, club_id, event_id,
              (data.get("platform") or "").strip() or None, url or None,
              (data.get("quality") or "").strip() or None, start, end,
              1 if data.get("record_stream", True) else 0,
              1 if data.get("chat_enabled", True) else 0)
    if stream_id is None:
        cur = conn.execute(
            "INSERT INTO live_streams (title, description, club_id, event_id, platform, "
            "stream_url, quality, scheduled_start, scheduled_end, record_stream, chat_enabled, "
            "status, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?, 'scheduled', ?, ?)",
            values + (actor, _now()))
        conn.commit()
        return int(cur.lastrowid)
    conn.execute(
        "UPDATE live_streams SET title=?, description=?, club_id=?, event_id=?, platform=?, "
        "stream_url=?, quality=?, scheduled_start=?, scheduled_end=?, record_stream=?, "
        "chat_enabled=?, updated_at=? WHERE stream_id=?", values + (_now(), stream_id))
    conn.commit()
    return int(stream_id)


def set_status(conn, stream_id: int, status: str, *, peak_viewers: int | None = None) -> None:
    """Move a stream along scheduled → live → ended (or cancel it)."""
    ensure_schema(conn)
    if status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}.")
    row = get_stream(conn, stream_id)
    if not row:
        raise ValueError("That stream no longer exists.")
    current = row["status"]
    allowed = {"scheduled": ("live", "cancelled"), "live": ("ended",),
               "ended": (), "cancelled": ("scheduled",)}
    if status not in allowed.get(current, ()):
        raise ValueError(f"A {current} stream cannot be marked {status}.")
    if status == "live":
        conn.execute("UPDATE live_streams SET status='live', actual_start=?, updated_at=? "
                     "WHERE stream_id=?", (_now(), _now(), stream_id))
    elif status == "ended":
        conn.execute("UPDATE live_streams SET status='ended', actual_end=?, peak_viewers="
                     "COALESCE(?, peak_viewers), updated_at=? WHERE stream_id=?",
                     (_now(), peak_viewers, _now(), stream_id))
    else:
        conn.execute("UPDATE live_streams SET status=?, updated_at=? WHERE stream_id=?",
                     (status, _now(), stream_id))
    conn.commit()


def set_record_flag(conn, stream_id: int, on: bool) -> None:
    """Turn recording on/off for a stream (e.g. Stop Recording on a live stream)."""
    ensure_schema(conn)
    conn.execute("UPDATE live_streams SET record_stream=?, updated_at=? WHERE stream_id=?",
                 (1 if on else 0, _now(), stream_id))
    conn.commit()


def set_recording(conn, stream_id: int, url: str | None, views: int | None = None) -> None:
    ensure_schema(conn)
    url = (url or "").strip() or None
    if url and "://" not in url:
        raise ValueError("The recording link must be a full URL.")
    conn.execute("UPDATE live_streams SET recording_url=?, recording_views=?, updated_at=? "
                 "WHERE stream_id=?", (url, views if url else None, _now(), stream_id))
    conn.commit()


def duration_text(start: str | None, end: str | None) -> str:
    if not start:
        return "—"
    try:
        a = datetime.strptime(start[:16], "%Y-%m-%d %H:%M")
        b = datetime.strptime(end[:16], "%Y-%m-%d %H:%M") if end else datetime.now()
    except ValueError:
        return "—"
    minutes = max(0, int((b - a).total_seconds() // 60))
    return f"{minutes // 60}h {minutes % 60:02d}m" if minutes >= 60 else f"{minutes}m"


# ---------------------------------------------------------------- chat

def _banned(row: dict[str, Any]) -> list[str]:
    try:
        return list(json.loads(row.get("chat_banned") or "[]"))
    except (TypeError, ValueError):
        return []


def chat_messages(conn, stream_id: int) -> list[dict[str, Any]]:
    ensure_schema(conn)
    return _dicts(conn.execute(
        "SELECT message_id, author, message, posted_at FROM live_stream_chat "
        "WHERE stream_id = ? AND hidden = 0 ORDER BY posted_at, message_id", (stream_id,)))


def post_chat(conn, stream_id: int, author: str, message: str) -> None:
    ensure_schema(conn)
    message = (message or "").strip()
    if not message:
        raise ValueError("Type a message first.")
    row = get_stream(conn, stream_id)
    if not row:
        raise ValueError("That stream no longer exists.")
    if not row["chat_enabled"]:
        raise ValueError("Chat is paused for this stream.")
    if author in _banned(row):
        raise ValueError("You have been removed from this stream's chat.")
    conn.execute("INSERT INTO live_stream_chat (stream_id, author, message, posted_at) "
                 "VALUES (?, ?, ?, ?)", (stream_id, author, message[:1000], _now()))
    conn.commit()


def ban_author(conn, stream_id: int, author: str) -> int:
    """Ban ``author`` from a stream's chat and hide their messages; returns hidden count."""
    ensure_schema(conn)
    row = get_stream(conn, stream_id)
    if not row:
        raise ValueError("That stream no longer exists.")
    banned = _banned(row)
    if author not in banned:
        banned.append(author)
    conn.execute("UPDATE live_streams SET chat_banned=? WHERE stream_id=?",
                 (json.dumps(banned), stream_id))
    cur = conn.execute("UPDATE live_stream_chat SET hidden=1 WHERE stream_id=? AND author=?",
                       (stream_id, author))
    conn.commit()
    return cur.rowcount


def toggle_chat(conn, stream_id: int) -> bool:
    """Pause/resume chat; returns the new chat_enabled value."""
    ensure_schema(conn)
    row = get_stream(conn, stream_id)
    if not row:
        raise ValueError("That stream no longer exists.")
    enabled = 0 if row["chat_enabled"] else 1
    conn.execute("UPDATE live_streams SET chat_enabled=? WHERE stream_id=?", (enabled, stream_id))
    conn.commit()
    return bool(enabled)


# ---------------------------------------------------------------- report

def analytics_report(conn) -> str:
    """Plain-text summary computed from the recorded streams only."""
    rows = list_streams(conn)
    if not rows:
        return "No live streams have been scheduled yet, so there is nothing to report."
    by_status: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    minutes = 0
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        by_platform[r.get("platform") or "Not set"] = by_platform.get(r.get("platform") or "Not set", 0) + 1
        if r.get("actual_start") and r.get("actual_end"):
            try:
                a = datetime.strptime(r["actual_start"][:16], "%Y-%m-%d %H:%M")
                b = datetime.strptime(r["actual_end"][:16], "%Y-%m-%d %H:%M")
                minutes += max(0, int((b - a).total_seconds() // 60))
            except ValueError:
                pass
    with_viewers = [r for r in rows if r.get("peak_viewers") is not None]
    recorded = [r for r in rows if r.get("recording_url")]
    chat_total = sum(int(r.get("chat_count") or 0) for r in rows)
    out = ["LIVE STREAMING SUMMARY", "=" * 60, "",
           f"Streams on record: {len(rows)}"]
    out += [f"  {s.title()}: {by_status.get(s, 0)}" for s in STATUSES]
    out += ["", f"Hours actually streamed: {minutes / 60:.1f}", "", "By platform:"]
    out += [f"  {p}: {n}" for p, n in sorted(by_platform.items(), key=lambda kv: -kv[1])]
    out += ["", "Viewer figures (only where they were recorded at the end of a stream):"]
    if with_viewers:
        for r in sorted(with_viewers, key=lambda r: -int(r["peak_viewers"]))[:10]:
            out.append(f"  {r['title']}: peak {r['peak_viewers']}")
    else:
        out.append("  None recorded.")
    out += ["", f"Recordings linked: {len(recorded)}",
            f"Chat messages posted here: {chat_total}"]
    return "\n".join(out)


__all__ = ["PLATFORMS", "QUALITIES", "STATUSES", "analytics_report", "ban_author",
           "chat_messages", "duration_text", "ensure_schema", "get_stream", "list_streams",
           "post_chat", "save_stream", "set_record_flag", "set_recording", "set_status", "toggle_chat"]
