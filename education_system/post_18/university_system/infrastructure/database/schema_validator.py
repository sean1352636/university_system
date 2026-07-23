"""
Automated Schema Validation for the University System.

Validates database schema consistency at startup and provides tools
for detecting schema drift and missing migrations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from education_system.post_18.university_system.infrastructure.database.db import get_connection, DEFAULT_DB_PATH
from education_system.post_18.university_system.core.exceptions import DatabaseError
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)

class SchemaValidationError(DatabaseError):
    """Exception raised when schema validation fails."""

    def __init__(
        self,
        message: str = "Schema validation failed",
        differences: Optional[List[Dict]] = None,
        **kwargs
    ):
        details = kwargs.get('details', {})
        if differences:
            details['differences'] = differences
        kwargs['details'] = details
        kwargs.pop('code', None)
        super().__init__(message, code="SCHEMA_VALIDATION_ERROR", **kwargs)
        self.differences = differences or []

@dataclass
class TableSchema:
    """Schema definition for a database table."""
    name: str
    columns: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    indexes: List[str] = field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = field(default_factory=list)
    primary_key: Optional[List[str]] = None

@dataclass
class SchemaDifference:
    """Represents a difference between expected and actual schema."""
    type: str  # 'missing_table', 'extra_table', 'missing_column', 'type_mismatch', etc.
    table: str
    column: Optional[str] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None
    severity: str = 'error'  # 'error', 'warning', 'info'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.type,
            'table': self.table,
            'column': self.column,
            'expected': self.expected,
            'actual': self.actual,
            'severity': self.severity,
        }

class SchemaValidator:
    """
    Validates database schema against expected structure.

    Example:
        >>> validator = SchemaValidator()
        >>>
        >>> # Validate at startup
        >>> try:
        ...     validator.validate_schema_at_startup()
        ... except SchemaValidationError as e:
        ...     logger.error(f"Schema issues: {e.differences}")
        >>>
        >>> # Get current schema
        >>> schema = validator.get_actual_schema()
    """

    # Core tables that must exist for the system to function
    REQUIRED_TABLES = {
        'users',
        'user_accounts',
        'students',
        'courses',
        'enrollments',
    }

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize schema validator.

        Args:
            db_path: Path to database file (uses default if None)
        """
        self.db_path = db_path or DEFAULT_DB_PATH

    def get_actual_schema(self, conn: Optional[sqlite3.Connection] = None) -> Dict[str, TableSchema]:
        """
        Get the actual schema from the database.

        Args:
            conn: Optional database connection

        Returns:
            Dictionary mapping table names to TableSchema objects
        """
        close_conn = False
        if conn is None:
            conn = get_connection(self.db_path)
            close_conn = True

        try:
            schema = {}

            # Get all tables
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row[0] for row in cursor.fetchall()]

            for table_name in tables:
                # Validate table name format for defense-in-depth
                # (names come from sqlite_master but we validate anyway)
                try:
                    validate_identifier(table_name, "table name")
                except ValueError:
                    logger.warning(f"Skipping table with invalid name format: {table_name!r}")
                    continue

                table_schema = TableSchema(name=table_name)

                # Get columns - use bracket quoting for table name (defense-in-depth)
                # Table names come from sqlite_master, but quoting prevents edge cases
                cursor = conn.execute(f"PRAGMA table_info([{table_name}])")
                for row in cursor.fetchall():
                    col_info = {
                        'cid': row[0],
                        'type': row[2],
                        'notnull': bool(row[3]),
                        'default': row[4],
                        'pk': bool(row[5]),
                    }
                    table_schema.columns[row[1]] = col_info

                    if col_info['pk']:
                        if table_schema.primary_key is None:
                            table_schema.primary_key = []
                        table_schema.primary_key.append(row[1])

                # Get indexes - use bracket quoting for table name
                cursor = conn.execute(f"PRAGMA index_list([{table_name}])")
                for row in cursor.fetchall():
                    table_schema.indexes.append(row[1])

                # Get foreign keys - use bracket quoting for table name
                cursor = conn.execute(f"PRAGMA foreign_key_list([{table_name}])")
                for row in cursor.fetchall():
                    fk_info = {
                        'id': row[0],
                        'table': row[2],
                        'from': row[3],
                        'to': row[4],
                        'on_update': row[5],
                        'on_delete': row[6],
                    }
                    table_schema.foreign_keys.append(fk_info)

                schema[table_name] = table_schema

            return schema

        finally:
            if close_conn:
                conn.close()

    def load_expected_schema(self, schema_path: Optional[str] = None) -> Dict[str, TableSchema]:
        """
        Load expected schema from a JSON file.

        Args:
            schema_path: Path to schema definition file

        Returns:
            Dictionary mapping table names to TableSchema objects
        """
        if schema_path and os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                data = json.load(f)

            schema = {}
            for table_name, table_data in data.get('tables', {}).items():
                schema[table_name] = TableSchema(
                    name=table_name,
                    columns=table_data.get('columns', {}),
                    indexes=table_data.get('indexes', []),
                    foreign_keys=table_data.get('foreign_keys', []),
                    primary_key=table_data.get('primary_key'),
                )
            return schema

        # Return minimal expected schema if no file provided
        return self._get_minimal_expected_schema()

    def _get_minimal_expected_schema(self) -> Dict[str, TableSchema]:
        """Get minimal expected schema for core tables."""
        return {
            'users': TableSchema(
                name='users',
                columns={
                    'id': {'type': 'INTEGER', 'pk': True},
                    'username': {'type': 'TEXT', 'notnull': True},
                    'email': {'type': 'TEXT'},
                    'role': {'type': 'TEXT'},
                },
                primary_key=['id'],
            ),
            'user_accounts': TableSchema(
                name='user_accounts',
                columns={
                    'id': {'type': 'INTEGER', 'pk': True},
                    'username': {'type': 'TEXT', 'notnull': True},
                    'password_hash': {'type': 'TEXT', 'notnull': True},
                    'user_id': {'type': 'INTEGER'},
                },
                primary_key=['id'],
            ),
            'students': TableSchema(
                name='students',
                columns={
                    'id': {'type': 'INTEGER', 'pk': True},
                },
                primary_key=['id'],
            ),
            'courses': TableSchema(
                name='courses',
                columns={
                    'id': {'type': 'INTEGER', 'pk': True},
                },
                primary_key=['id'],
            ),
            'enrollments': TableSchema(
                name='enrollments',
                columns={
                    'id': {'type': 'INTEGER', 'pk': True},
                },
                primary_key=['id'],
            ),
        }

    def compare_schemas(
        self,
        expected: Dict[str, TableSchema],
        actual: Dict[str, TableSchema],
        strict: bool = False
    ) -> List[SchemaDifference]:
        """
        Compare expected schema with actual schema.

        Args:
            expected: Expected schema definition
            actual: Actual schema from database
            strict: If True, extra tables/columns are also flagged

        Returns:
            List of SchemaDifference objects
        """
        differences = []
        expected_tables = set(expected.keys())
        actual_tables = set(actual.keys())

        # Check for missing tables
        for table in expected_tables - actual_tables:
            differences.append(SchemaDifference(
                type='missing_table',
                table=table,
                expected=table,
                actual=None,
                severity='error',
            ))

        # Check for extra tables (if strict)
        if strict:
            for table in actual_tables - expected_tables:
                differences.append(SchemaDifference(
                    type='extra_table',
                    table=table,
                    expected=None,
                    actual=table,
                    severity='warning',
                ))

        # Compare columns for common tables
        for table in expected_tables & actual_tables:
            exp_table = expected[table]
            act_table = actual[table]

            exp_cols = set(exp_table.columns.keys())
            act_cols = set(act_table.columns.keys())

            # Missing columns
            for col in exp_cols - act_cols:
                differences.append(SchemaDifference(
                    type='missing_column',
                    table=table,
                    column=col,
                    expected=exp_table.columns[col],
                    actual=None,
                    severity='error',
                ))

            # Extra columns (if strict)
            if strict:
                for col in act_cols - exp_cols:
                    differences.append(SchemaDifference(
                        type='extra_column',
                        table=table,
                        column=col,
                        expected=None,
                        actual=act_table.columns[col],
                        severity='info',
                    ))

            # Type mismatches for common columns
            for col in exp_cols & act_cols:
                exp_col = exp_table.columns[col]
                act_col = act_table.columns[col]

                # Compare types (normalize for comparison)
                exp_type = exp_col.get('type', '').upper()
                act_type = act_col.get('type', '').upper()

                # Normalize common SQLite type variations
                type_map = {
                    'INT': 'INTEGER',
                    'BOOL': 'INTEGER',
                    'BOOLEAN': 'INTEGER',
                    'VARCHAR': 'TEXT',
                    'STRING': 'TEXT',
                    'DOUBLE': 'REAL',
                    'FLOAT': 'REAL',
                }
                exp_type = type_map.get(exp_type, exp_type)
                act_type = type_map.get(act_type, act_type)

                if exp_type and act_type and exp_type != act_type:
                    differences.append(SchemaDifference(
                        type='type_mismatch',
                        table=table,
                        column=col,
                        expected=exp_col.get('type'),
                        actual=act_col.get('type'),
                        severity='warning',
                    ))

        return differences

    def validate_schema_at_startup(
        self,
        schema_path: Optional[str] = None,
        strict: bool = False,
        raise_on_error: bool = True
    ) -> Tuple[bool, List[SchemaDifference]]:
        """
        Validate database schema matches expected structure.

        Args:
            schema_path: Path to expected schema definition
            strict: Check for extra tables/columns too
            raise_on_error: Raise exception on validation failure

        Returns:
            Tuple of (is_valid, differences)

        Raises:
            SchemaValidationError: If validation fails and raise_on_error is True
        """
        logger.info("Starting schema validation...")

        try:
            expected = self.load_expected_schema(schema_path)
            actual = self.get_actual_schema()

            differences = self.compare_schemas(expected, actual, strict)

            # Separate by severity
            errors = [d for d in differences if d.severity == 'error']
            warnings = [d for d in differences if d.severity == 'warning']

            if errors:
                logger.error(f"Schema validation failed: {len(errors)} errors found")
                for diff in errors:
                    logger.error(f"  - {diff.type}: {diff.table}.{diff.column or '*'}")

                if raise_on_error:
                    raise SchemaValidationError(
                        f"Schema validation failed: {len(errors)} errors",
                        differences=[d.to_dict() for d in errors]
                    )

                return False, differences

            if warnings:
                logger.warning(f"Schema validation passed with {len(warnings)} warnings")
                for diff in warnings:
                    logger.warning(f"  - {diff.type}: {diff.table}.{diff.column or '*'}")
            else:
                logger.info("Schema validation passed")

            return True, differences

        except Exception as e:
            if isinstance(e, SchemaValidationError):
                raise
            logger.error(f"Schema validation error: {e}")
            if raise_on_error:
                raise SchemaValidationError(f"Validation error: {e}")
            return False, []

    def get_schema_hash(self) -> str:
        """
        Get a hash of the current schema for change detection.

        Returns:
            SHA256 hash of schema structure
        """
        schema = self.get_actual_schema()

        # Create deterministic representation
        schema_repr = {}
        for table_name in sorted(schema.keys()):
            table = schema[table_name]
            schema_repr[table_name] = {
                'columns': {k: v for k, v in sorted(table.columns.items())},
                'indexes': sorted(table.indexes),
                'primary_key': table.primary_key,
            }

        schema_json = json.dumps(schema_repr, sort_keys=True)
        return hashlib.sha256(schema_json.encode()).hexdigest()

    def export_schema(self, output_path: str) -> None:
        """
        Export current schema to a JSON file.

        Args:
            output_path: Path to write schema file
        """
        schema = self.get_actual_schema()

        export_data = {
            'version': '1.0',
            'exported_at': datetime.now().isoformat(),
            'schema_hash': self.get_schema_hash(),
            'tables': {},
        }

        for table_name, table_schema in schema.items():
            export_data['tables'][table_name] = {
                'columns': table_schema.columns,
                'indexes': table_schema.indexes,
                'foreign_keys': table_schema.foreign_keys,
                'primary_key': table_schema.primary_key,
            }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Schema exported to {output_path}")

    def check_required_tables(self) -> Tuple[bool, Set[str]]:
        """
        Check that all required core tables exist.

        Returns:
            Tuple of (all_present, missing_tables)
        """
        schema = self.get_actual_schema()
        actual_tables = set(schema.keys())
        missing = self.REQUIRED_TABLES - actual_tables

        if missing:
            logger.error(f"Missing required tables: {missing}")
            return False, missing

        logger.info("All required tables present")
        return True, set()

def validate_schema_at_startup(
    db_path: Optional[str] = None,
    schema_path: Optional[str] = None,
    strict: bool = False,
    raise_on_error: bool = True
) -> bool:
    """
    Convenience function to validate schema at startup.

    Args:
        db_path: Path to database file
        schema_path: Path to expected schema definition
        strict: Check for extra tables/columns
        raise_on_error: Raise exception on failure

    Returns:
        True if validation passed, False otherwise
    """
    validator = SchemaValidator(db_path)
    is_valid, _ = validator.validate_schema_at_startup(
        schema_path=schema_path,
        strict=strict,
        raise_on_error=raise_on_error
    )
    return is_valid

__all__ = [
    'SchemaValidator',
    'SchemaValidationError',
    'TableSchema',
    'SchemaDifference',
    'validate_schema_at_startup',
]
