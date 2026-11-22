"""Collaborative (partner) provision and student mobility tables.

Two gaps in the university's academic model, both of which had no home:

* **Collaborative provision** — programme governance modelled a programme's
  versions, approvals and teach-out, but only ever as something we deliver
  ourselves. Nothing recorded that a programme is delivered by somebody
  else under our award: franchised, validated, joint, dual or articulated.
* **Student mobility** — study abroad existed only as an interest tag in
  social matching and a filter in the scholarship finder. Nothing recorded
  that a student was away, under which agreement, what they were supposed
  to study there, or what credit came back.

Both modules keep an idempotent ``ensure_*_schema`` bootstrap alongside
this migration, following the precedent set by ``b2e7f4a91c58``: the
migration is what a fresh database gets, the bootstrap is what the many
entry points that run before Alembic get. They agree by construction —
``test_partner_provision_migration.py`` checks it.

Revision ID: a91c47e2f8d3
Revises: f7b3d81e4c69
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a91c47e2f8d3"
down_revision: Union[str, Sequence[str], None] = "f7b3d81e4c69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.domains.curriculum.domain.collaborative_provision import (
        _db_init as collaborative,
    )
    from education_system.systems.university.domains.curriculum.domain.student_mobility import (
        _db_init as mobility,
    )

    # The DDL lives with the modules that own these tables, so the migration
    # and the runtime bootstrap cannot drift. Both are CREATE IF NOT EXISTS
    # plus CREATE INDEX/TRIGGER IF NOT EXISTS, so this is safe to re-run and
    # a no-op on a database where the feature has already been opened.
    for statement in (
        collaborative._CREATE_PARTNERS,
        collaborative._CREATE_AGREEMENTS,
        collaborative._CREATE_PROGRAMMES,
        collaborative._CREATE_COHORTS,
        collaborative._CREATE_REVIEWS,
        *collaborative._INDEXES,
        collaborative._TRIGGER_TOUCH_PARTNER,
        collaborative._TRIGGER_TOUCH_AGREEMENT,
        collaborative._TRIGGER_REVIEW_SETS_DUE,
        mobility._CREATE_AGREEMENTS,
        mobility._CREATE_PLACEMENTS,
        mobility._CREATE_LEARNING_AGREEMENTS,
        mobility._CREATE_RECOGNITIONS,
        *mobility._INDEXES,
        mobility._TRIGGER_TOUCH_PLACEMENT,
        mobility._TRIGGER_ROLLUP_INSERT,
        mobility._TRIGGER_ROLLUP_DELETE,
    ):
        op.execute(statement)


def downgrade() -> None:
    for trigger in (
        "mobility_recognition_rollup_delete",
        "mobility_recognition_rollup_insert",
        "mobility_placements_touch",
        "partner_review_sets_agreement_due",
        "partnership_agreements_touch",
        "partner_institutions_touch",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    # Children first — the foreign keys run the other way.
    for table in (
        "mobility_credit_recognitions",
        "mobility_learning_agreements",
        "mobility_placements",
        "mobility_agreements",
        "partner_reviews",
        "partner_cohorts",
        "collaborative_programmes",
        "partnership_agreements",
        "partner_institutions",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
