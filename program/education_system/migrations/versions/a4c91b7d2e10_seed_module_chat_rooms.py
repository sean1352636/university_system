"""seed module chat rooms

Revision ID: a4c91b7d2e10
Revises: d39533373ffb
Create Date: 2026-05-09 08:30:00.000000

Creates one chat room per default module (the 14 modules seeded in
d1bde3fa4179) so newly enrolled students can be auto-joined.

Idempotent: skips any module whose chat room already exists (matched on
``chat_rooms.name == module_code``). Skipped silently if no admin user
exists yet — the rooms can be re-seeded by stamping down + up later.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4c91b7d2e10'
down_revision: Union[str, Sequence[str], None] = 'd39533373ffb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (module_code, module_name) — kept aligned with
# education_system.systems.university.domain.academics.services.modules
MODULE_ROOMS = [
    ("CIS0001", "python programming"),
    ("CIS0002", "data structures and algorithms"),
    ("CIS1001", "Computational Thinking"),
    ("CIS1002", "Design Patterns"),
    ("CIS1003", "Test Driven Development"),
    ("CIS1004", "SQL Relational Database"),
    ("CIS2001", "software quality assurance principles"),
    ("CIS2002", "software reliabilities"),
    ("CIS2003", "formal methods for system verifications"),
    ("CIS2004", "algorithm complexity"),
    ("CIS3001", "data visualisation"),
    ("CIS3002", "an introduction to artificial intelligence in data science"),
    ("CIS3003", "an introduction to machine learning"),
    ("CIS3004", "statistical methods"),
]


def upgrade() -> None:
    bind = op.get_bind()

    admin_row = bind.execute(
        sa.text(
            "SELECT id FROM users "
            "WHERE LOWER(role) = 'admin' OR LOWER(username) = 'admin' "
            "ORDER BY id LIMIT 1"
        )
    ).fetchone()
    if not admin_row:
        # No admin yet (fresh install before user seed) — leave empty;
        # rooms will be created on next stamp/upgrade once admin exists.
        return
    admin_id = admin_row[0]

    for code, name in MODULE_ROOMS:
        existing = bind.execute(
            sa.text("SELECT id FROM chat_rooms WHERE name = :n"),
            {"n": code},
        ).fetchone()
        if existing:
            continue

        result = bind.execute(
            sa.text(
                "INSERT INTO chat_rooms "
                "(name, description, room_type, created_by, created_at, "
                " is_active, max_members) "
                "VALUES (:name, :desc, 'course', :admin, "
                "        strftime('%Y-%m-%d %H:%M:%S','now'), 1, 500)"
            ),
            {"name": code, "desc": name, "admin": admin_id},
        )
        room_id = result.lastrowid

        bind.execute(
            sa.text(
                "INSERT INTO chat_room_members "
                "(room_id, user_id, joined_at, is_admin) "
                "VALUES (:rid, :uid, strftime('%Y-%m-%d %H:%M:%S','now'), 1)"
            ),
            {"rid": room_id, "uid": admin_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    codes = [c for c, _ in MODULE_ROOMS]
    placeholders = ",".join(f":c{i}" for i in range(len(codes)))
    params = {f"c{i}": c for i, c in enumerate(codes)}

    # Find the rooms first so we can clean dependants.
    rows = bind.execute(
        sa.text(f"SELECT id FROM chat_rooms WHERE name IN ({placeholders})"),
        params,
    ).fetchall()
    if not rows:
        return
    room_ids = [r[0] for r in rows]
    rid_placeholders = ",".join(f":r{i}" for i in range(len(room_ids)))
    rid_params = {f"r{i}": rid for i, rid in enumerate(room_ids)}

    bind.execute(sa.text(f"DELETE FROM chat_room_members WHERE room_id IN ({rid_placeholders})"), rid_params)
    bind.execute(sa.text(f"DELETE FROM chat_room_invitations WHERE room_id IN ({rid_placeholders})"), rid_params)
    bind.execute(sa.text(f"DELETE FROM chat_messages WHERE room_id IN ({rid_placeholders})"), rid_params)
    bind.execute(sa.text(f"DELETE FROM chat_rooms WHERE id IN ({rid_placeholders})"), rid_params)
