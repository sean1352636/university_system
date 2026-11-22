"""university: record who liked a forum post, so each person can like it once

``module_forum_posts.likes_count`` was a bare counter, so nothing stopped one
person liking a post repeatedly. Likes already counted have no owner and stay in
the counter. Purely additive and idempotent.

Revision ID: a7c9e1b3d5f7
Revises: f6a8c0e2b4d6
Create Date: 2026-11-01 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a7c9e1b3d5f7'
down_revision: Union[str, Sequence[str], None] = 'f6a8c0e2b4d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS module_forum_post_likes (
            post_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            liked_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (post_id, user_id),
            FOREIGN KEY (post_id) REFERENCES module_forum_posts (post_id) ON DELETE CASCADE
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS module_forum_post_likes")
