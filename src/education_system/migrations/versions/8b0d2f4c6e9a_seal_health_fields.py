"""university health: seal the confidential free-text fields at rest

Counselling and mental-health notes (``counseling_appointments``,
``counselling_sessions``, ``wellness_checkins``, ``mental_health_checkins``,
``mental_health_appointments``) and the description of every health record
marked confidential are sealed with the one managed key
(``var/secrets/health_field_key``; see
``domains/health/infrastructure/health/field_crypto`` and
``domains/health/application/health/sealed_fields``). Values already
sealed (``enc1:`` prefix) are skipped, so the migration is idempotent.

No stored value was ever encrypted with the retired key file
(``var/data/university/health_encryption.key``), so nothing needs
decrypting and re-sealing; that file was moved to ``remove/``.

Also replaces the US crisis lines seeded into ``crisis_resources`` (988,
"Text HOME to 741741") with Samaritans 116 123 and Shout 85258, and adds
999 and NHS 111 - only where the rows still hold the original seed values.

Revision ID: 8b0d2f4c6e9a
Revises: 7a9c1e3b5d8f
Create Date: 2026-10-18 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = '8b0d2f4c6e9a'
down_revision: Union[str, Sequence[str], None] = '7a9c1e3b5d8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from education_system.systems.university.domains.health.application.health import (
        sealed_fields,
    )
    execute = op.get_bind().exec_driver_sql
    sealed_fields.seal_existing(execute)

    if execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'crisis_resources'"
               ).fetchone():
        execute("UPDATE crisis_resources SET resource_name = 'Samaritans', contact_info = '116 123' "
                "WHERE contact_info = '988'")
        execute("UPDATE crisis_resources SET resource_name = 'Shout', contact_info = "
                "'Text SHOUT to 85258', description = 'Free crisis support via text, 24/7' "
                "WHERE contact_info = 'Text HOME to 741741'")
        for name, kind, contact, description in (
                ('Emergency Services', 'Emergency', '999', 'Call if anyone is in immediate danger'),
                ('NHS 111', 'Urgent Help', '111',
                 'Urgent medical and mental health help; poisons advice, 24/7')):
            if not execute("SELECT 1 FROM crisis_resources WHERE contact_info = ?",
                           (contact,)).fetchone():
                execute("INSERT INTO crisis_resources (resource_name, resource_type, contact_info, "
                        "description) VALUES (?, ?, ?, ?)", (name, kind, contact, description))


def downgrade() -> None:
    # Sealed values stay sealed: unsealing them would put the most sensitive
    # health text back into the database in plain text. Every reader goes
    # through sealed_fields.reveal, which reads both forms.
    pass
