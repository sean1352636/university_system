"""student disabilities (Disability & Accessibility)

``student_disabilities``: the disabilities a student has told the university
about — at enrolment (Create Student), through the portal themselves, or
added by disability services. ``details`` is sealed at rest (health
``sealed_fields``); a row is never deleted, only marked ``removed``.
``adjustment_request_id`` links the accommodation request raised for it.

Idempotent: CREATE ... IF NOT EXISTS (the service creates it too).

Revision ID: 5d7f9b1c3e8a
Revises: 0b09872e815a
Create Date: 2026-10-19 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = '5d7f9b1c3e8a'
down_revision: Union[str, Sequence[str], None] = '0b09872e815a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS student_disabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            category TEXT NOT NULL,
            details TEXT,
            adjustment_type TEXT,
            adjustment_request_id INTEGER,
            source TEXT NOT NULL DEFAULT 'student',
            status TEXT NOT NULL DEFAULT 'active',
            declared_by TEXT,
            declared_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_student_disabilities_student "
               "ON student_disabilities (student_id, status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_student_disabilities_student")
    op.execute("DROP TABLE IF EXISTS student_disabilities")
