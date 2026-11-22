"""support teams and per-team SLA targets

1. **Teams.** ``departments.team_key`` (nullable, unique when set) names the
   support team a Helpdesk department is (wellbeing, disability, finance,
   accommodation, academic_registry, international_visa, it_services,
   careers, general, and ``duty`` for the out-of-hours duty officers).
   Existing departments are matched by name ('IT Support' -> it_services,
   'Academic Affairs' -> academic_registry, 'Financial Services' -> finance,
   'Student Services' -> general); a team with no department gets one
   (name and description only — no e-mail or manager is invented).
   Membership stays in ``staff_assignments`` (``category`` = team key).
2. **SLA.** ``sla_policies.team`` (nullable: NULL = every team) lets a team
   have its own first-response / resolution targets per priority. The row
   named 'Critical' that was stored with priority 'high' (so it could never
   be told apart from 'Standard High Priority') gets priority 'critical'.

Idempotent: each step checks what exists first.

Revision ID: 0b09872e815a
Revises: 47ac7f60fc96
Create Date: 2026-10-19 15:30:00.000000
"""
import logging
from datetime import datetime
from typing import Sequence, Union

from alembic import op


revision: str = '0b09872e815a'
down_revision: Union[str, Sequence[str], None] = '47ac7f60fc96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)

# key -> (department name to create, description, names an existing row may have)
TEAMS = (
    ('wellbeing', 'Wellbeing', 'Student wellbeing and mental health support',
     ('Wellbeing', 'Student Wellbeing', 'Counselling')),
    ('disability', 'Disability & Inclusion', 'Disability support and reasonable adjustments',
     ('Disability & Inclusion', 'Disability Service', 'Disability Services')),
    ('finance', 'Financial Services', 'Fees, funding and hardship support',
     ('Financial Services', 'Student Funding', 'Fees & Funding')),
    ('accommodation', 'Accommodation', 'University and private accommodation',
     ('Accommodation', 'Accommodation Services', 'Housing')),
    ('academic_registry', 'Academic Affairs', 'Registration, records, assessment and awards',
     ('Academic Affairs', 'Academic Registry', 'Registry')),
    ('international_visa', 'International Student Support', 'Student visas and international students',
     ('International Student Support', 'International Office')),
    ('it_services', 'IT Support', 'IT services and accounts',
     ('IT Support', 'IT Services')),
    ('careers', 'Careers Service', 'Careers and employability',
     ('Careers Service', 'Careers')),
    ('general', 'Student Services', 'General student enquiries',
     ('Student Services', 'General Enquiries')),
    ('duty', 'Duty Officer', 'Out-of-hours duty officers for critical tickets',
     ('Duty Officer',)),
)


def _x():
    return op.get_bind().exec_driver_sql


def _table(name) -> bool:
    return _x()("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (name,)).fetchone() is not None


def _cols(table) -> set:
    return {r[1] for r in _x()(f'PRAGMA table_info("{table}")').fetchall()}


def _teams() -> None:
    x = _x()
    if not _table('departments'):
        logger.info("No departments table; teams left for the Helpdesk schema to create")
        return
    if 'team_key' not in _cols('departments'):
        x("ALTER TABLE departments ADD COLUMN team_key TEXT")
    x("CREATE UNIQUE INDEX IF NOT EXISTS idx_departments_team_key ON departments (team_key) "
      "WHERE team_key IS NOT NULL")
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for key, name, description, names in TEAMS:
        if x("SELECT 1 FROM departments WHERE team_key = ?", (key,)).fetchone():
            continue
        marks = ", ".join("?" * len(names))
        row = x(f"SELECT dept_id, name FROM departments WHERE team_key IS NULL AND name IN ({marks}) "
                "ORDER BY dept_id LIMIT 1", names).fetchone()
        if row:
            x("UPDATE departments SET team_key = ? WHERE dept_id = ?", (key, row[0]))
            logger.info("Department '%s' is team %s", row[1], key)
        elif x("SELECT 1 FROM departments WHERE name = ?", (name,)).fetchone():
            logger.warning("Department '%s' already belongs to another team; %s has none", name, key)
        else:
            x("INSERT INTO departments (name, description, is_active, created_at, team_key) "
              "VALUES (?, ?, 1, ?, ?)", (name, description, now, key))
            logger.info("Department '%s' created for team %s", name, key)


def _sla() -> None:
    x = _x()
    if not _table('sla_policies'):
        logger.info("No sla_policies table; SLA team column left for the Helpdesk schema")
        return
    if 'team' not in _cols('sla_policies'):
        x("ALTER TABLE sla_policies ADD COLUMN team TEXT")
    x("UPDATE sla_policies SET priority = 'critical' WHERE name = 'Critical' "
      "AND lower(priority) = 'high'")


def upgrade() -> None:
    _teams()
    _sla()


def downgrade() -> None:
    # The columns are nullable and harmless to older code; nothing is undone.
    logger.info("support teams / SLA columns kept on downgrade")
