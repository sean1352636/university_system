"""retire the internal LMS

Revision ID: c7a3e91f4d20
Revises: b4e19d7a3c62
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c7a3e91f4d20'
down_revision: Union[str, Sequence[str], None] = 'b4e19d7a3c62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: Dropped children-first so a foreign key never outlives its target.
_LMS_TABLES = (
    "lms_quiz_submissions", "lms_quiz_attempts", "lms_quiz_questions",
    "lms_quizzes", "lms_questions",
    "lms_discussion_posts", "lms_discussion_forums",
    "lms_video_lectures", "lms_course_content",
    "lms_student_enrollment", "lms_gradebook",
    "lms_progress", "lms_lessons", "lms_modules", "lms_resources",
    "lms_courses",
)


def upgrade() -> None:
    """Drop the internal LMS tables and create the module forum tables.

    The LMS was a third naming layer over concepts the university already
    models. ``lms_courses`` keyed on a ``module_code`` and carried an
    instructor, dates, an enrolment cap and a published flag — all of which
    ``modules`` already holds, with real enrolments in ``student_modules``.
    The content layer that would have justified it (``lms_modules`` ->
    ``lms_lessons`` -> ``lms_progress``) was never populated.

    Its features moved to their natural homes first: quizzes to
    ``assignments`` + ``exam_portal_*``, the gradebook to Grade Tracking,
    course discussion to chat rooms.

    ``lms_access_grants`` is deliberately NOT dropped: despite the prefix it
    belongs to absence tracking (#46), is keyed on module_code + session_date,
    and is created by that feature's own schema.

    Module Discussion Forums (#39) stored in ``lms_discussion_forums`` /
    ``lms_discussion_posts`` only because their foreign key pointed at
    ``lms_courses``. It gets its own module-keyed tables here; the data is
    carried across by ``tools/university/retire_lms.py``.
    """
    op.execute("""
        CREATE TABLE IF NOT EXISTS module_forums (
            forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_code TEXT NOT NULL,
            topic TEXT NOT NULL,
            description TEXT,
            created_by TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (module_code) REFERENCES modules(module_code)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS module_forum_posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            forum_id INTEGER,
            user_id TEXT,
            content TEXT,
            parent_post_id INTEGER,
            attachments TEXT,
            likes_count INTEGER DEFAULT 0,
            is_instructor_post INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (forum_id) REFERENCES module_forums(forum_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_module_forums_module "
               "ON module_forums(module_code)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_module_forum_posts_forum "
               "ON module_forum_posts(forum_id)")

    for table in _LMS_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    """Not reversible.

    The LMS tables can be recreated from the baseline, but their contents
    cannot: the retirement tool migrates what was worth keeping into
    ``course_materials`` and ``module_forums`` and discards the rest. Restore
    from the backup the tool writes to
    ``var/backups/maintenance/lms_retirement/`` instead.
    """
    raise NotImplementedError(
        "Retiring the internal LMS is not reversible; restore from the "
        "backup written by tools/university/retire_lms.py."
    )
