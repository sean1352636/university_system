"""library: physical copies, loan rules, recalls, charges, module reading
lists, acquisitions, stocktake, e-resources

Revision ID: f3c5e7a9b1d2
Revises: e2b4d6f8a1c3
Create Date: 2026-10-16 00:00:00.000000

See ``infrastructure/database/schemas/library_catalogue_schema.py``. Creates a
copy row for each unit of every title's quantity and attaches active loans to
copies. Idempotent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f3c5e7a9b1d2'
down_revision: Union[str, Sequence[str], None] = 'e2b4d6f8a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("library_eresource_usage", "library_eresources", "library_stocktake_scans",
           "library_stocktakes", "library_orders", "library_funds", "library_charges",
           "library_borrower_overrides", "library_item_rules", "library_borrower_rules",
           "library_copies")


def upgrade() -> None:
    from education_system.systems.university.infrastructure.database.schemas import (
        library_catalogue_schema as schema,
    )
    schema.apply(op.get_bind().exec_driver_sql)


def downgrade() -> None:
    # Added columns on books / book_loans / book_reservations / reading lists
    # stay; SQLite cannot drop them without rebuilding those tables.
    op.execute("UPDATE book_loans SET copy_id = NULL")
    for table in _TABLES:
        op.execute(f'DROP TABLE IF EXISTS "{table}"')
