"""seed module catalog

Revision ID: d1bde3fa4179
Revises: 877b10b0175b
Create Date: 2026-04-27 17:22:19.485473

Seeds the 14 modules defined in
education_system.post_18.university_system.modules.domain.academics.services.modules
into the modules table.

Demo-student enrolments (S12345) are NOT done here — see
modules/scripts/seed_demo_data.py::seed_s12345_modules.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1bde3fa4179'
down_revision: Union[str, Sequence[str], None] = '877b10b0175b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATALOG = [
    ("CIS0001", "python programming", "compulsory", None),
    ("CIS0002", "data structures and algorithms", "compulsory", None),
    ("CIS1001", "Computational Thinking", "optional", None),
    ("CIS1002", "Design Patterns", "optional", None),
    ("CIS1003", "Test Driven Development", "optional", None),
    ("CIS1004", "SQL Relational Database", "optional", None),
    ("CIS2001", "software quality assurance principles", "course", "CS"),
    ("CIS2002", "software reliabilities", "course", "CS"),
    ("CIS2003", "formal methods for system verifications", "course", "CS"),
    ("CIS2004", "algorithm complexity", "course", "CS"),
    ("CIS3001", "data visualisation", "course", "DS"),
    ("CIS3002", "an introduction to artificial intelligence in data science", "course", "DS"),
    ("CIS3003", "an introduction to machine learning", "course", "DS"),
    ("CIS3004", "statistical methods", "course", "DS"),
]

def upgrade() -> None:
    bind = op.get_bind()
    for code, name, mtype, course in CATALOG:
        bind.execute(
            sa.text(
                "INSERT OR IGNORE INTO modules "
                "(module_id, module_code, module_name, module_type, course, is_active) "
                "VALUES (:code, :code, :name, :mtype, :course, 1)"
            ),
            {"code": code, "name": name, "mtype": mtype, "course": course},
        )


def downgrade() -> None:
    bind = op.get_bind()
    codes = tuple(c for c, *_ in CATALOG)
    placeholders = ",".join(f":c{i}" for i in range(len(codes)))
    params = {f"c{i}": c for i, c in enumerate(codes)}
    bind.execute(
        sa.text(f"DELETE FROM modules WHERE module_code IN ({placeholders})"),
        params,
    )
