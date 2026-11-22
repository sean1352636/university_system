"""Interactive features and recording settings for SU live streams.

Backs the Interactive Virtual Features and Recording & Replay screens,
which used to show sample polls, questions, rooms, videos and analytics.
Everything hangs off ``live_streams`` (see ``live_streams.py``):

* ``live_stream_polls`` / ``live_stream_poll_votes`` — polls (and quizzes,
  a poll with a correct option) and one vote per person per poll.
* ``live_stream_questions`` / ``live_stream_question_votes`` — audience
  Q&A with one upvote per person.
* ``live_stream_rooms`` / ``live_stream_room_members`` — networking and
  breakout rooms (name, topic, capacity, the room's own meeting link,
  an end time for breakouts) and who is in each.
* ``live_stream_settings`` — key/value recording defaults.
* ``live_stream_playlist`` — a viewer's saved recordings.

Nothing here invents numbers: counts are counts of rows.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from education_system.systems.university.domains.student_life.domain.student_life.student_union.services import (
    live_streams as ls,
)

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS live_stream_polls (
        poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stream_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        options TEXT NOT NULL,
        is_quiz INTEGER NOT NULL DEFAULT 0,
        correct_option INTEGER,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
        created_by TEXT,
        created_at TEXT NOT NULL,
        closed_at TEXT,
        FOREIGN KEY (stream_id) REFERENCES live_streams (stream_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS live_stream_poll_votes (
        poll_id INTEGER NOT NULL,
        voter TEXT NOT NULL,
        option_index INTEGER NOT NULL,
        voted_at TEXT NOT NULL,
        PRIMARY KEY (poll_id, voter),
        FOREIGN KEY (poll_id) REFERENCES live_stream_polls (poll_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS live_stream_questions (
        question_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stream_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        question TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'answered')),
        asked_at TEXT NOT NULL,
        answered_at TEXT,
        FOREIGN KEY (stream_id) REFERENCES live_streams (stream_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS live_stream_question_votes (
        question_id INTEGER NOT NULL,
        voter TEXT NOT NULL,
        PRIMARY KEY (question_id, voter),
        FOREIGN KEY (question_id) REFERENCES live_stream_questions (question_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS live_stream_rooms (
        room_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stream_id INTEGER NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('networking', 'breakout')),
        name TEXT NOT NULL,
        topic TEXT,
        capacity INTEGER,
        meeting_link TEXT,
        is_private INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
        ends_at TEXT,
        created_by TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (stream_id) REFERENCES live_streams (stream_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS live_stream_room_members (
        room_id INTEGER NOT NULL,
        member TEXT NOT NULL,
        joined_at TEXT NOT NULL,
        PRIMARY KEY (room_id, member),
        FOREIGN KEY (room_id) REFERENCES live_stream_rooms (room_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS live_stream_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT,
        updated_by TEXT,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS live_stream_playlist (
        owner TEXT NOT NULL,
        stream_id INTEGER NOT NULL,
        added_at TEXT NOT NULL,
        PRIMARY KEY (owner, stream_id),
        FOREIGN KEY (stream_id) REFERENCES live_streams (stream_id) ON DELETE CASCADE
    )""",
)

DEFAULT_SETTINGS = {
    "auto_record_streams": "1",
    "auto_record_virtual_events": "0",
    "auto_record_conferences": "0",
    "recording_quality": "1080p",
    "storage_location": "",
    "download_subtitles": "0",
    "download_thumbnail": "0",
}

_ensured: set[str] = set()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dicts(cur) -> list[dict[str, Any]]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def ensure_schema(conn) -> None:
    ls.ensure_schema(conn)
    try:
        key = str(conn.execute("PRAGMA database_list").fetchone()[2])
    except Exception:  # pragma: no cover - defensive
        key = str(id(conn))
    if key in _ensured:
        return
    for sql in _SCHEMA:
        conn.execute(sql)
    conn.commit()
    _ensured.add(key)


def _require_stream(conn, stream_id: int) -> dict[str, Any]:
    row = ls.get_stream(conn, stream_id)
    if not row:
        raise ValueError("That stream no longer exists.")
    return row


# ---------------------------------------------------------------- polls

def create_poll(conn, stream_id: int, question: str, options: list[str], *, actor: str | None,
                correct_option: int | None = None) -> int:
    ensure_schema(conn)
    _require_stream(conn, stream_id)
    question = (question or "").strip()
    options = [o.strip() for o in options if o and o.strip()]
    if not question:
        raise ValueError("Enter the poll question.")
    if not 2 <= len(options) <= 6:
        raise ValueError("A poll needs between 2 and 6 options.")
    if len({o.lower() for o in options}) != len(options):
        raise ValueError("Options must be different from each other.")
    if correct_option is not None and not 0 <= correct_option < len(options):
        raise ValueError("The correct answer must be one of the options.")
    cur = conn.execute(
        "INSERT INTO live_stream_polls (stream_id, question, options, is_quiz, correct_option, "
        "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (stream_id, question, json.dumps(options), 1 if correct_option is not None else 0,
         correct_option, actor, _now()))
    conn.commit()
    return int(cur.lastrowid)


def polls(conn, stream_id: int) -> list[dict[str, Any]]:
    """Polls for a stream, newest first, each with per-option vote counts."""
    ensure_schema(conn)
    rows = _dicts(conn.execute(
        "SELECT * FROM live_stream_polls WHERE stream_id = ? ORDER BY poll_id DESC", (stream_id,)))
    for r in rows:
        r["options"] = json.loads(r["options"])
        counts = dict(conn.execute(
            "SELECT option_index, COUNT(*) FROM live_stream_poll_votes WHERE poll_id = ? "
            "GROUP BY option_index", (r["poll_id"],)).fetchall())
        r["counts"] = [int(counts.get(i, 0)) for i in range(len(r["options"]))]
        r["total"] = sum(r["counts"])
    return rows


def vote(conn, poll_id: int, voter: str, option_index: int) -> None:
    ensure_schema(conn)
    if not voter:
        raise ValueError("Sign in to vote.")
    row = conn.execute("SELECT status, options FROM live_stream_polls WHERE poll_id = ?",
                       (poll_id,)).fetchone()
    if not row:
        raise ValueError("That poll no longer exists.")
    if row[0] != "open":
        raise ValueError("This poll has closed.")
    if not 0 <= option_index < len(json.loads(row[1])):
        raise ValueError("Choose one of the options.")
    if conn.execute("SELECT 1 FROM live_stream_poll_votes WHERE poll_id = ? AND voter = ?",
                    (poll_id, voter)).fetchone():
        raise ValueError("You have already voted in this poll.")
    conn.execute("INSERT INTO live_stream_poll_votes (poll_id, voter, option_index, voted_at) "
                 "VALUES (?, ?, ?, ?)", (poll_id, voter, option_index, _now()))
    conn.commit()


def close_poll(conn, poll_id: int) -> None:
    ensure_schema(conn)
    conn.execute("UPDATE live_stream_polls SET status = 'closed', closed_at = ? "
                 "WHERE poll_id = ? AND status = 'open'", (_now(), poll_id))
    conn.commit()


def poll_summary(poll: dict[str, Any]) -> str:
    """Leading option text, e.g. 'B (3 of 5, 60%)', or 'no votes'."""
    if not poll["total"]:
        return "No votes"
    best = max(range(len(poll["counts"])), key=lambda i: poll["counts"][i])
    pct = poll["counts"][best] * 100 / poll["total"]
    return f"{poll['options'][best]} ({pct:.0f}%)"


# ---------------------------------------------------------------- Q&A

def ask(conn, stream_id: int, author: str, question: str) -> int:
    ensure_schema(conn)
    if not author:
        raise ValueError("Sign in to ask a question.")
    _require_stream(conn, stream_id)
    question = (question or "").strip()
    if not question:
        raise ValueError("Type your question first.")
    cur = conn.execute("INSERT INTO live_stream_questions (stream_id, author, question, asked_at) "
                       "VALUES (?, ?, ?, ?)", (stream_id, author, question[:1000], _now()))
    conn.commit()
    return int(cur.lastrowid)


def questions(conn, stream_id: int) -> list[dict[str, Any]]:
    ensure_schema(conn)
    return _dicts(conn.execute(
        "SELECT q.*, (SELECT COUNT(*) FROM live_stream_question_votes v "
        " WHERE v.question_id = q.question_id) AS votes FROM live_stream_questions q "
        "WHERE q.stream_id = ? ORDER BY q.status = 'answered', votes DESC, q.asked_at",
        (stream_id,)))


def upvote(conn, question_id: int, voter: str) -> None:
    ensure_schema(conn)
    if not voter:
        raise ValueError("Sign in to upvote.")
    row = conn.execute("SELECT author FROM live_stream_questions WHERE question_id = ?",
                       (question_id,)).fetchone()
    if not row:
        raise ValueError("That question no longer exists.")
    if row[0] == voter:
        raise ValueError("You cannot upvote your own question.")
    if conn.execute("SELECT 1 FROM live_stream_question_votes WHERE question_id = ? AND voter = ?",
                    (question_id, voter)).fetchone():
        raise ValueError("You have already upvoted this question.")
    conn.execute("INSERT INTO live_stream_question_votes (question_id, voter) VALUES (?, ?)",
                 (question_id, voter))
    conn.commit()


def mark_answered(conn, question_id: int) -> None:
    ensure_schema(conn)
    conn.execute("UPDATE live_stream_questions SET status = 'answered', answered_at = ? "
                 "WHERE question_id = ?", (_now(), question_id))
    conn.commit()


# ---------------------------------------------------------------- rooms

def create_room(conn, stream_id: int, kind: str, name: str, *, topic: str = "",
                capacity=None, meeting_link: str = "", is_private: bool = False,
                minutes: int | None = None, actor: str | None = None) -> int:
    ensure_schema(conn)
    _require_stream(conn, stream_id)
    if kind not in ("networking", "breakout"):
        raise ValueError("Unknown room type.")
    name = (name or "").strip()
    if not name:
        raise ValueError("Give the room a name.")
    cap = None
    if str(capacity or "").strip():
        try:
            cap = int(str(capacity).strip())
        except ValueError as exc:
            raise ValueError("Capacity must be a whole number.") from exc
        if cap < 1:
            raise ValueError("Capacity must be at least 1.")
    link = (meeting_link or "").strip()
    if link and not link.lower().startswith(("http://", "https://")):
        raise ValueError("The room link must start with https://.")
    ends = ((datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
            if minutes else None)
    cur = conn.execute(
        "INSERT INTO live_stream_rooms (stream_id, kind, name, topic, capacity, meeting_link, "
        "is_private, ends_at, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (stream_id, kind, name, (topic or "").strip() or None, cap, link or None,
         1 if is_private else 0, ends, actor, _now()))
    conn.commit()
    return int(cur.lastrowid)


def rooms(conn, stream_id: int, kind: str, *, include_closed: bool = False) -> list[dict[str, Any]]:
    ensure_schema(conn)
    sql = ("SELECT r.*, (SELECT COUNT(*) FROM live_stream_room_members m "
           " WHERE m.room_id = r.room_id) AS members FROM live_stream_rooms r "
           "WHERE r.stream_id = ? AND r.kind = ?")
    if not include_closed:
        sql += " AND r.status = 'open'"
    return _dicts(conn.execute(sql + " ORDER BY r.room_id", (stream_id, kind)))


def room_members(conn, room_id: int) -> list[str]:
    ensure_schema(conn)
    return [r[0] for r in conn.execute(
        "SELECT member FROM live_stream_room_members WHERE room_id = ? ORDER BY joined_at", (room_id,))]


def join_room(conn, room_id: int, member: str) -> dict[str, Any]:
    """Add ``member``; returns the room row (with its link)."""
    ensure_schema(conn)
    if not member:
        raise ValueError("Sign in to join a room.")
    rows = _dicts(conn.execute("SELECT * FROM live_stream_rooms WHERE room_id = ?", (room_id,)))
    if not rows or rows[0]["status"] != "open":
        raise ValueError("That room is closed.")
    room = rows[0]
    if conn.execute("SELECT 1 FROM live_stream_room_members WHERE room_id = ? AND member = ?",
                    (room_id, member)).fetchone():
        return room
    count = conn.execute("SELECT COUNT(*) FROM live_stream_room_members WHERE room_id = ?",
                         (room_id,)).fetchone()[0]
    if room["capacity"] and count >= room["capacity"]:
        raise ValueError("That room is full.")
    conn.execute("INSERT INTO live_stream_room_members (room_id, member, joined_at) VALUES (?,?,?)",
                 (room_id, member, _now()))
    conn.commit()
    return room


def participants(conn, stream_id: int) -> list[str]:
    """Everyone known to be at a stream: event registrants plus chat/Q&A posters."""
    ensure_schema(conn)
    row = _require_stream(conn, stream_id)
    people: list[str] = []
    if row.get("event_id"):
        try:
            people += [str(r[0]) for r in conn.execute(
                "SELECT user_id FROM unified_event_registrations WHERE event_id = ? "
                "AND user_id IS NOT NULL", (row["event_id"],))]
        except Exception:
            pass
    people += [r[0] for r in conn.execute(
        "SELECT author FROM live_stream_chat WHERE stream_id = ? AND hidden = 0", (stream_id,))]
    people += [r[0] for r in conn.execute(
        "SELECT author FROM live_stream_questions WHERE stream_id = ?", (stream_id,))]
    seen: dict[str, None] = {}
    for p in people:
        seen.setdefault(p, None)
    return list(seen)


def create_breakouts(conn, stream_id: int, count: int, *, minutes: int = 15,
                     actor: str | None = None) -> tuple[int, int]:
    """Open ``count`` breakout rooms and spread the known participants across them.

    Closes any breakout rooms already open for the stream first. Returns
    ``(rooms created, people assigned)``.
    """
    ensure_schema(conn)
    if not 2 <= count <= 20:
        raise ValueError("Choose between 2 and 20 rooms.")
    close_breakouts(conn, stream_id)
    people = participants(conn, stream_id)
    ids = [create_room(conn, stream_id, "breakout", f"Breakout {chr(65 + i) if i < 26 else i + 1}",
                       minutes=minutes, actor=actor) for i in range(count)]
    now = _now()
    for i, person in enumerate(people):
        conn.execute("INSERT OR IGNORE INTO live_stream_room_members (room_id, member, joined_at) "
                     "VALUES (?, ?, ?)", (ids[i % count], person, now))
    conn.commit()
    return len(ids), len(people)


def extend_breakouts(conn, stream_id: int, minutes: int = 10) -> int:
    ensure_schema(conn)
    n = 0
    for r in rooms(conn, stream_id, "breakout"):
        base = datetime.now()
        if r.get("ends_at"):
            try:
                base = max(base, datetime.strptime(r["ends_at"], "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                pass
        conn.execute("UPDATE live_stream_rooms SET ends_at = ? WHERE room_id = ?",
                     ((base + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S"), r["room_id"]))
        n += 1
    conn.commit()
    return n


def close_breakouts(conn, stream_id: int) -> int:
    ensure_schema(conn)
    cur = conn.execute("UPDATE live_stream_rooms SET status = 'closed' WHERE stream_id = ? "
                       "AND kind = 'breakout' AND status = 'open'", (stream_id,))
    conn.commit()
    return cur.rowcount


def time_left(ends_at: str | None) -> str:
    if not ends_at:
        return "—"
    try:
        secs = int((datetime.strptime(ends_at, "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds())
    except ValueError:
        return "—"
    if secs <= 0:
        return "Time up"
    return f"{secs // 60}:{secs % 60:02d}"


# ---------------------------------------------------------------- recording settings / library

def get_settings(conn) -> dict[str, str]:
    ensure_schema(conn)
    out = dict(DEFAULT_SETTINGS)
    out.update({k: v for k, v in conn.execute(
        "SELECT setting_key, setting_value FROM live_stream_settings")})
    return out


def save_settings(conn, values: dict[str, Any], *, actor: str | None) -> None:
    ensure_schema(conn)
    for key, value in values.items():
        if key not in DEFAULT_SETTINGS:
            continue
        conn.execute("INSERT INTO live_stream_settings (setting_key, setting_value, updated_by, "
                     "updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(setting_key) DO UPDATE SET "
                     "setting_value = excluded.setting_value, updated_by = excluded.updated_by, "
                     "updated_at = excluded.updated_at",
                     (key, str(value), actor, _now()))
    conn.commit()


def library(conn, *, search: str = "", club: str | None = None) -> list[dict[str, Any]]:
    """Ended streams that have a recording link."""
    rows = [r for r in ls.list_streams(conn, status="ended") if r.get("recording_url")]
    if search:
        s = search.lower()
        rows = [r for r in rows if s in (r["title"] or "").lower()
                or s in (r.get("description") or "").lower()]
    if club and club != "All Events":
        rows = [r for r in rows if (r.get("club_name") or "Student Union") == club]
    rows.sort(key=lambda r: r.get("actual_start") or r["scheduled_start"], reverse=True)
    return rows


def recording_minutes(r: dict[str, Any]) -> int | None:
    try:
        a = datetime.strptime(r["actual_start"][:16], "%Y-%m-%d %H:%M")
        b = datetime.strptime(r["actual_end"][:16], "%Y-%m-%d %H:%M")
        return max(0, int((b - a).total_seconds() // 60))
    except (TypeError, ValueError, KeyError):
        return None


def add_to_playlist(conn, owner: str, stream_id: int) -> bool:
    """True if added, False if it was already there."""
    ensure_schema(conn)
    if not owner:
        raise ValueError("Sign in to keep a playlist.")
    cur = conn.execute("INSERT OR IGNORE INTO live_stream_playlist (owner, stream_id, added_at) "
                       "VALUES (?, ?, ?)", (owner, stream_id, _now()))
    conn.commit()
    return cur.rowcount > 0


def playlist(conn, owner: str) -> list[dict[str, Any]]:
    ensure_schema(conn)
    ids = [r[0] for r in conn.execute(
        "SELECT stream_id FROM live_stream_playlist WHERE owner = ? ORDER BY added_at", (owner,))]
    rows = {r["stream_id"]: r for r in ls.list_streams(conn, status="ended")}
    return [rows[i] for i in ids if i in rows]


def playback_report(conn) -> str:
    rows = library(conn)
    if not rows:
        return "No recordings have been linked yet, so there is nothing to report."
    with_views = [r for r in rows if r.get("recording_views") is not None]
    mins = [m for m in (recording_minutes(r) for r in rows) if m is not None]
    by_club: dict[str, int] = {}
    for r in rows:
        by_club[r.get("club_name") or "Student Union"] = by_club.get(r.get("club_name") or "Student Union", 0) + 1
    saved = conn.execute("SELECT COUNT(*), COUNT(DISTINCT owner) FROM live_stream_playlist").fetchone()
    out = ["PLAYBACK SUMMARY", "=" * 60, "",
           f"Recordings linked: {len(rows)}",
           f"Total recorded length: {sum(mins) / 60:.1f} hours"
           + (f" ({len(rows) - len(mins)} without start/end times)" if len(mins) < len(rows) else ""),
           "", "Views (only where the platform's count was entered):"]
    if with_views:
        out.append(f"  Total: {sum(int(r['recording_views']) for r in with_views)}")
        for r in sorted(with_views, key=lambda r: -int(r["recording_views"]))[:10]:
            out.append(f"  {r['title']}: {r['recording_views']}")
    else:
        out.append("  None entered.")
    out += ["", "Recordings by club:"]
    out += [f"  {k}: {v}" for k, v in sorted(by_club.items(), key=lambda kv: -kv[1])]
    out += ["", f"Saved to playlists: {saved[0]} time(s) by {saved[1]} viewer(s)",
            "", "Watch time, completion and device figures are held by the streaming "
            "platform and are not recorded here."]
    return "\n".join(out)


__all__ = [
    "DEFAULT_SETTINGS", "add_to_playlist", "ask", "close_breakouts", "close_poll",
    "create_breakouts", "create_poll", "create_room", "ensure_schema", "extend_breakouts",
    "get_settings", "join_room", "library", "mark_answered", "participants", "playback_report",
    "playlist", "poll_summary", "polls", "questions", "recording_minutes", "room_members",
    "rooms", "save_settings", "time_left", "upvote", "vote",
]
