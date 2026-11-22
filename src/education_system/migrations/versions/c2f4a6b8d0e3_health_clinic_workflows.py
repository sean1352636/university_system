"""university health: clinic workflows, prescribing safety, dental sealing

Creates (``domains/health/infrastructure/health/workflow_schema``):

* diary — ``provider_time_off`` (blocks booking), ``provider_schedule_templates``
  (weekly patterns that write ``provider_schedules``; the four patterns the
  CLI used to print as text are seeded), ``appointment_waitlist``,
  ``appointment_reminders_sent`` (24h / 2h reminders, feedback requests and
  screening reminders, each sent once), ``appointment_feedback``
  (post-appointment satisfaction);
* prescribing safety — ``drug_classes``, ``drug_class_cross_reactivity``,
  ``drug_interactions`` (seeded, maintained in place) and
  ``prescription_safety_overrides``;
* ``outbreak_investigations``;
* ``health_records.archived`` / ``archived_at`` / ``archived_by`` /
  ``archive_reason`` (soft delete) and ``health_appointments.duration_minutes``.

Then seals the dental clinic's medical history, allergies and notes
(``dentist_patients``) and treatment notes (``dentist_treatments``) with the
managed health key, as ``application/health/sealed_fields`` now lists them
(``seal_existing`` skips values already sealed, so it is idempotent).

Every statement is ``IF NOT EXISTS`` / ``INSERT OR IGNORE`` / column-checked.

Revision ID: c2f4a6b8d0e3
Revises: 9c1e3a5d7f0b
Create Date: 2026-10-18 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c2f4a6b8d0e3'
down_revision: Union[str, Sequence[str], None] = '9c1e3a5d7f0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    from education_system.systems.university.domains.health.infrastructure.health import (
        workflow_schema,
    )
    execute = op.get_bind().exec_driver_sql
    workflow_schema.apply(execute)
    sealed_fields.seal_existing(execute)


def downgrade() -> None:
    # Deliberately a no-op. The new tables hold clinical and audit records
    # (safety overrides, outbreak investigations, feedback) that must not be
    # dropped by a schema rollback, the added columns are harmless to older
    # code, and sealed dental fields stay sealed (unsealing would write the
    # plaintext back to disk).
    pass
