"""University-side UCAS tables.

The four tables the UCAS admissions module owns in ``student_records.db``
were each created by an ``executescript`` on first use, so they existed
only once somebody had opened the feature. That made them invisible to a
schema diff, absent from a freshly migrated database, and impossible to
change except by editing a ``CREATE TABLE IF NOT EXISTS`` that would
quietly do nothing on any database that already had the old shape.

They are declared here instead, alongside the rest of the admissions
schema. The modules keep their ``IF NOT EXISTS`` bootstrap — it is
idempotent and costs a no-op — so an existing installation is unaffected
either way; what changes is that a new one gets the tables from the
migration, and the next change to their shape has somewhere to live.

Revision ID: b2e7f4a91c58
Revises: a83f5c7d9e12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2e7f4a91c58"
down_revision: Union[str, Sequence[str], None] = "a83f5c7d9e12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A sixth-form UCAS choice naming this university, mapped to our own
    # application and (once admitted) our own student record.
    op.execute("""
        CREATE TABLE IF NOT EXISTS ucas_application_links (
            link_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sf_application_id    INTEGER NOT NULL,
            sf_choice_id         INTEGER NOT NULL,
            sf_student_id        TEXT NOT NULL,
            uni_application_id   INTEGER,
            uni_student_id       TEXT,
            status               TEXT NOT NULL DEFAULT 'open',
            linked_by            TEXT,
            linked_at            TEXT DEFAULT (datetime('now')),
            updated_at           TEXT DEFAULT (datetime('now')),
            UNIQUE(sf_choice_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_links_sf_app "
               "ON ucas_application_links(sf_application_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_links_sf_student "
               "ON ucas_application_links(sf_student_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_links_uni_app "
               "ON ucas_application_links(uni_application_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_links_status "
               "ON ucas_application_links(status)")

    # Internal admissions notes. Deliberately uni-only — the sixth form
    # never sees these.
    op.execute("""
        CREATE TABLE IF NOT EXISTS ucas_admissions_notes (
            note_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id              INTEGER NOT NULL,
            body                 TEXT NOT NULL,
            author               TEXT,
            created_at           TEXT DEFAULT (datetime('now')),
            updated_at           TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (link_id)
                REFERENCES ucas_application_links(link_id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_notes_link "
               "ON ucas_admissions_notes(link_id)")

    # The terms attached to an offer we issued. These used to be typed
    # into the sixth form's own offer_details table from a letter.
    op.execute("""
        CREATE TABLE IF NOT EXISTS ucas_offer_terms (
            terms_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            sf_choice_id             INTEGER NOT NULL UNIQUE,
            grade_requirement        TEXT,
            grade_alternative        TEXT,
            reply_deadline           TEXT,
            expiry_date              TEXT,
            scholarship              TEXT,
            accommodation_guaranteed INTEGER NOT NULL DEFAULT 0,
            notes                    TEXT,
            issued_by                TEXT,
            issued_at                TEXT DEFAULT (datetime('now')),
            updated_at               TEXT DEFAULT (datetime('now'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_terms_choice "
               "ON ucas_offer_terms(sf_choice_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_terms_deadline "
               "ON ucas_offer_terms(reply_deadline)")

    # Who decided what, and when. A history, not a current state: a
    # conditional offer later confirmed leaves both rows standing.
    op.execute("""
        CREATE TABLE IF NOT EXISTS ucas_decisions (
            decision_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            sf_choice_id      INTEGER NOT NULL,
            sf_application_id INTEGER,
            sf_student_id     TEXT,
            decision_status   TEXT NOT NULL,
            offer_terms       TEXT,
            notes             TEXT,
            decided_by        TEXT,
            decided_at        TEXT DEFAULT (datetime('now'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_decisions_choice "
               "ON ucas_decisions(sf_choice_id, decided_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_decisions_student "
               "ON ucas_decisions(sf_student_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ucas_decisions_when "
               "ON ucas_decisions(decided_at)")


def downgrade() -> None:
    # Notes cascade off links, so they go first.
    op.execute("DROP TABLE IF EXISTS ucas_decisions")
    op.execute("DROP TABLE IF EXISTS ucas_offer_terms")
    op.execute("DROP TABLE IF EXISTS ucas_admissions_notes")
    op.execute("DROP TABLE IF EXISTS ucas_application_links")
