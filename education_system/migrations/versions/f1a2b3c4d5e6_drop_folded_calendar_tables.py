"""drop folded calendar tables

Revision ID: f1a2b3c4d5e6
Revises: e8c4197a3b21
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e8c4197a3b21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the four duplicate/related calendar tables folded into the single
    canonical ``academic_calendar_events`` table.

    Calendar reconciliation consolidated all university-system calendar data
    into ``academic_calendar_events`` (superset columns added in the same
    effort):

    * ``calendar_events`` (Schema A) — duplicate event table, folded 1:1.
    * ``school_calendar`` — parent-portal event table, folded (event_type
      discriminator + start_time/end_time/location/audience columns).
    * ``trip_calendar_events`` — trip↔event junction, folded via the
      ``trip_id`` column on the canonical table.
    * ``holiday_calendars`` — holiday-calendar definitions, folded
      (event_type='holiday_calendar' + country_code/region/is_active columns).

    All four were empty at reconciliation time; every runtime writer/reader was
    repointed to ``academic_calendar_events`` first.
    """
    op.execute("DROP TABLE IF EXISTS calendar_events")
    op.execute("DROP TABLE IF EXISTS school_calendar")
    op.execute("DROP TABLE IF EXISTS trip_calendar_events")
    op.execute("DROP TABLE IF EXISTS holiday_calendars")


def downgrade() -> None:
    """Recreate the four tables (original baseline schemas) for rollback
    parity. Empty — nothing repopulates them; canonical data stays in
    ``academic_calendar_events``."""
    op.execute("CREATE TABLE IF NOT EXISTS holiday_calendars (\n"
               "                    id TEXT PRIMARY KEY,\n"
               "                    name TEXT NOT NULL,\n"
               "                    country_code TEXT NOT NULL,\n"
               "                    region TEXT,\n"
               "                    is_active BOOLEAN DEFAULT TRUE,\n"
               "                    date_added TEXT NOT NULL\n"
               "                )")
    op.execute("CREATE TABLE IF NOT EXISTS trip_calendar_events (\n"
               "                    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
               "                    trip_id INTEGER NOT NULL,\n"
               "                    event_id TEXT NOT NULL,\n"
               "                    event_type TEXT DEFAULT 'trip_event',\n"
               "                    created_at TEXT NOT NULL, \"description\" TEXT, \"end_date\" TEXT,"
               " \"location\" TEXT, \"organizer\" TEXT, \"participants\" TEXT, \"start_date\" TEXT,"
               " \"status\" TEXT DEFAULT 'planned', \"title\" TEXT,"
               " \"updated_at\" TEXT DEFAULT CURRENT_TIMESTAMP,\n"
               "                    UNIQUE (trip_id, event_id)\n"
               "                )")
    op.execute("CREATE TABLE IF NOT EXISTS school_calendar (\n"
               "                id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
               "                event_name TEXT,\n"
               "                event_description TEXT,\n"
               "                event_date TEXT,\n"
               "                start_time TEXT,\n"
               "                end_time TEXT,\n"
               "                location TEXT,\n"
               "                event_type TEXT,\n"
               "                audience TEXT\n"
               "            )")
    op.execute("CREATE TABLE IF NOT EXISTS calendar_events (\n"
               "                id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
               "                title TEXT NOT NULL,\n"
               "                description TEXT,\n"
               "                start_date TEXT NOT NULL,\n"
               "                end_date TEXT,\n"
               "                event_type TEXT NOT NULL,\n"
               "                assignment_id INTEGER,\n"
               "                created_by INTEGER,\n"
               "                created_at TEXT NOT NULL,\n"
               "                FOREIGN KEY (assignment_id) REFERENCES assignments (id) ON DELETE CASCADE,\n"
               "                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE CASCADE\n"
               "            )")
