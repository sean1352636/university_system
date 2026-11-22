"""Who can see an assignment. A draft, hidden or scheduled assignment has
``is_active = 0``, so every student screen that already filters on it leaves
it out. Publishing is the moment students are told."""

from __future__ import annotations

from datetime import datetime

VISIBILITIES = ("draft", "published", "hidden", "scheduled")
_STATUS = {"draft": "draft", "published": "active", "hidden": "hidden", "scheduled": "scheduled"}
_LABELS = {"draft": "Draft", "hidden": "Hidden", "scheduled": "Scheduled"}
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def parse_when(value) -> datetime | None:
    text = str(value or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M:%S")


def visibility_of(status, is_active) -> str:
    status = str(status or "").lower()
    if status in ("draft", "hidden", "scheduled"):
        return status
    return "published" if is_active else "hidden"


def label(status, is_active) -> str:
    """The Manage Assignments wording for an assignment students can't see."""
    return _LABELS.get(visibility_of(status, is_active), "Inactive")


def check_settings(visibility, available_from, due_date, now=None) -> datetime | None:
    """The opening date, or ``ValueError`` when the choice can't work."""
    if visibility not in VISIBILITIES:
        raise ValueError(f"Visibility must be one of {', '.join(VISIBILITIES)}")
    if visibility != "scheduled":
        return None
    opens = parse_when(available_from)
    if not opens:
        raise ValueError("Give the opening date for a scheduled assignment, as YYYY-MM-DD HH:MM")
    due = parse_when(due_date)
    if due and opens >= due:
        raise ValueError("The opening date must be before the due date")
    if opens <= (now or datetime.now()):
        raise ValueError("The opening date has passed. Choose a later date, or publish it now.")
    return opens


def set_visibility(conn, assignment_id, visibility, available_from=None, now=None) -> bool:
    """Apply ``visibility``. ``True`` when students should now be told: it has
    just become visible and they haven't been told before."""
    now = now or datetime.now()
    row = conn.execute("SELECT due_date, announced_at FROM assignments WHERE id = ?",
                       (assignment_id,)).fetchone()
    if not row:
        raise ValueError("That assignment no longer exists")
    opens = check_settings(visibility, available_from, row[0], now)
    published = visibility == "published"
    tell = published and not row[1]
    conn.execute(
        "UPDATE assignments SET status = ?, is_active = ?, available_from = ?, "
        "announced_at = COALESCE(announced_at, ?), updated_at = ? WHERE id = ?",
        (_STATUS[visibility], 1 if published else 0, _stamp(opens) if opens else None,
         _stamp(now) if published else None, _stamp(now), assignment_id))
    return tell


def publish_due(conn, now=None) -> list[int]:
    """Open every scheduled assignment whose date has come; returns the ones
    students should be told about."""
    now = now or datetime.now()
    due = conn.execute("SELECT id FROM assignments WHERE status = 'scheduled' "
                       "AND available_from IS NOT NULL AND available_from <= ?",
                       (_stamp(now),)).fetchall()
    return [row[0] for row in due if set_visibility(conn, row[0], "published", now=now)]
