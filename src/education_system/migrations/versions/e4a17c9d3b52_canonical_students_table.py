"""The ``students`` table, owned by a migration for the first time.

No migration has ever created ``students``. It was created by whichever of
48 ``CREATE TABLE IF NOT EXISTS students`` statements — spread across 31
files, no two agreeing — happened to run first, and then widened by a dozen
scattered ``ALTER TABLE students ADD COLUMN`` calls in unrelated modules.
The 35-column table on an established installation matches none of those
definitions; it is the residue of that race.

The practical consequences were real. ``nationality`` is declared in most
of the superseded definitions and exists in none of them. The duplicate-
import path wrote ``date_of_birth``, ``email`` and ``phone_number``, none
of which are column names here, so it failed outright. And
``student_lifecycle`` requires ``academic_year``, ``mode_of_study``,
``campus_code``, ``expected_return_date`` and ``record_closed_at``, which
existed only because an unrelated bootstrap had already run.

This migration states the shape once. It is written as create-if-absent
plus add-column-if-missing rather than a plain ``CREATE TABLE`` because
every existing database already has the table, and the point is to make a
*new* database match an old one rather than to rebuild anything.

The same shape is kept in
``systems/university/infrastructure/database/schemas/students_table.py``
for the runtime bootstrap; ``test_students_table_canonical.py`` asserts the
two do not drift.

Revision ID: e4a17c9d3b52
Revises: b2e7f4a91c58
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4a17c9d3b52"
down_revision: Union[str, Sequence[str], None] = "b2e7f4a91c58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name, declaration) in the order the established table carries them.
STUDENT_COLUMNS: tuple[tuple[str, str], ...] = (
    ("student_id", "TEXT PRIMARY KEY"),
    ("email_address", "TEXT"),
    ("title", "TEXT"),
    ("first_name", "TEXT"),
    ("middle_name", "TEXT"),
    ("last_name", "TEXT"),
    ("gender", "TEXT"),
    ("dob", "TEXT"),
    ("age", "INTEGER"),
    ("course", "TEXT"),
    ("registration_datetime", "TEXT"),
    ("status", "TEXT DEFAULT 'Active'"),
    ("enrollment_date", "TEXT"),
    ("emergency_contact", "TEXT DEFAULT ''"),
    ("pronouns", "TEXT DEFAULT ''"),
    ("previous_system", "TEXT"),
    ("previous_system_id", "TEXT"),
    ("year", "INTEGER"),
    ("program", "TEXT"),
    ("phone", "TEXT"),
    ("address", "TEXT"),
    ("is_active", "BOOLEAN DEFAULT 1"),
    ("grade_level", "TEXT"),
    ("created_date", "TIMESTAMP DEFAULT NULL"),
    ("year_of_study", "INTEGER"),
    ("gpa", "REAL"),
    ("journey_id", "TEXT"),
    ("entry_qualifications", "TEXT"),
    ("conditions_met", "INTEGER"),
    ("ucas_tariff", "INTEGER"),
    ("academic_year", "TEXT"),
    ("mode_of_study", "TEXT DEFAULT 'full-time'"),
    ("campus_code", "TEXT"),
    ("expected_return_date", "TEXT"),
    ("record_closed_at", "TEXT"),
)

INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_students_name "
    "ON students(first_name, last_name)",
    "CREATE INDEX IF NOT EXISTS idx_students_course ON students(course)",
    "CREATE INDEX IF NOT EXISTS idx_students_age ON students(age)",
    "CREATE INDEX IF NOT EXISTS idx_students_email ON students(email_address)",
    "CREATE INDEX IF NOT EXISTS idx_students_status ON students(status)",
    "CREATE INDEX IF NOT EXISTS idx_students_enrollment_date "
    "ON students(enrollment_date)",
    "CREATE INDEX IF NOT EXISTS idx_students_journey_id "
    "ON students(journey_id)",
)


def upgrade() -> None:
    body = ",\n    ".join(f'"{name}" {decl}' for name, decl in STUDENT_COLUMNS)
    op.execute(f"CREATE TABLE IF NOT EXISTS students (\n    {body}\n)")

    bind = op.get_bind()
    existing = {
        row[1] for row in bind.execute(sa.text("PRAGMA table_info(students)"))
    }
    for name, decl in STUDENT_COLUMNS:
        if name in existing or "PRIMARY KEY" in decl.upper():
            continue
        op.execute(f'ALTER TABLE students ADD COLUMN "{name}" {decl}')

    for statement in INDEXES:
        op.execute(statement)


def downgrade() -> None:
    # Deliberately not reversible. Dropping columns would destroy student
    # records, and dropping the table would take the whole institution with
    # it. The previous state — "whichever definition ran first" — is not a
    # state a migration can restore anyway.
    pass
