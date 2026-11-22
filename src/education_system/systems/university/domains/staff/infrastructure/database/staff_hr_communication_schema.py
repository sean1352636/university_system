"""Staff HR schema — Communication: who has read a staff announcement, and the
moderation of announcements posted by ordinary staff.

Applied by ``staff_hr_ddl`` (see there for the module contract).

* ``staff_announcement_reads`` — one row per person per announcement. The
  name ``announcement_reads`` already belongs to the parent portal (keyed on
  ``parent_id``, pointing at ``school_announcements``), so staff reads live
  in their own table.
* ``staff_announcements`` gains ``priority`` and its moderation state.
  ``moderation_status`` is ``approved`` (the default, so everything already
  posted stays visible), ``pending`` or ``rejected``; only ``approved``
  announcements have ``is_active = 1``.
"""

from __future__ import annotations

TABLES = (
    """CREATE TABLE IF NOT EXISTS staff_announcement_reads (
        read_id INTEGER PRIMARY KEY AUTOINCREMENT,
        announcement_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        read_date TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(announcement_id, user_id),
        FOREIGN KEY (announcement_id) REFERENCES staff_announcements(announcement_id)
    )""",
)

ADDED_COLUMNS = (
    ('staff_announcements', 'priority', "TEXT DEFAULT 'normal'"),
    ('staff_announcements', 'moderation_status', "TEXT DEFAULT 'approved'"),
    ('staff_announcements', 'moderated_by', 'TEXT'),
    ('staff_announcements', 'moderated_at', 'TEXT'),
    ('staff_announcements', 'rejection_reason', 'TEXT'),
)

__all__ = ["TABLES", "ADDED_COLUMNS"]
