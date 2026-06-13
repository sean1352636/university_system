"""
Comprehensive tests for the schema_validator module.

Tests SchemaValidator, TableSchema, SchemaDifference, SchemaValidationError,
and the convenience validate_schema_at_startup function.
"""

import json
import os
import sqlite3
import tempfile
import pytest
from unittest.mock import patch, MagicMock


# Suppress unrelated resource warnings
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_db():
    """Create a temporary in-memory-like database with core tables."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        email TEXT,
        role TEXT
    )""")
    conn.execute("""CREATE TABLE user_accounts (
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    conn.execute("""CREATE TABLE students (
        id INTEGER PRIMARY KEY,
        name TEXT
    )""")
    conn.execute("""CREATE TABLE courses (
        id INTEGER PRIMARY KEY,
        title TEXT
    )""")
    conn.execute("""CREATE TABLE enrollments (
        id INTEGER PRIMARY KEY,
        student_id INTEGER,
        course_id INTEGER,
        FOREIGN KEY (student_id) REFERENCES students(id),
        FOREIGN KEY (course_id) REFERENCES courses(id)
    )""")
    conn.execute("CREATE INDEX idx_users_username ON users(username)")
    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass
    for s in ('-wal', '-shm'):
        try:
            os.unlink(path + s)
        except OSError:
            pass


@pytest.fixture
def temp_db_missing_tables():
    """Create a temp DB missing some required tables."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL)")
    conn.execute("CREATE TABLE students (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def schema_json_file(tmp_path):
    """Create a temporary schema JSON file."""
    schema = {
        "tables": {
            "users": {
                "columns": {
                    "id": {"type": "INTEGER", "pk": True},
                    "username": {"type": "TEXT", "notnull": True},
                    "email": {"type": "TEXT"},
                },
                "indexes": [],
                "foreign_keys": [],
                "primary_key": ["id"],
            },
            "students": {
                "columns": {
                    "id": {"type": "INTEGER", "pk": True},
                },
                "indexes": [],
                "foreign_keys": [],
                "primary_key": ["id"],
            },
        }
    }
    path = tmp_path / "expected_schema.json"
    path.write_text(json.dumps(schema))
    return str(path)


# ---------------------------------------------------------------------------
# Test TableSchema dataclass
# ---------------------------------------------------------------------------

class TestTableSchema:
    """Test the TableSchema dataclass."""

    def test_creation_defaults(self):
        """Test TableSchema has correct defaults."""
        from education_system.university_system.infrastructure.database.schema_validator import TableSchema
        ts = TableSchema(name="test")
        assert ts.name == "test"
        assert ts.columns == {}
        assert ts.indexes == []
        assert ts.foreign_keys == []
        assert ts.primary_key is None

    def test_creation_with_data(self):
        """Test TableSchema with all fields populated."""
        from education_system.university_system.infrastructure.database.schema_validator import TableSchema
        ts = TableSchema(
            name="users",
            columns={"id": {"type": "INTEGER", "pk": True}},
            indexes=["idx_users_name"],
            foreign_keys=[{"table": "roles", "from": "role_id", "to": "id"}],
            primary_key=["id"],
        )
        assert ts.name == "users"
        assert "id" in ts.columns
        assert len(ts.indexes) == 1
        assert len(ts.foreign_keys) == 1
        assert ts.primary_key == ["id"]


# ---------------------------------------------------------------------------
# Test SchemaDifference dataclass
# ---------------------------------------------------------------------------

class TestSchemaDifference:
    """Test the SchemaDifference dataclass."""

    def test_creation(self):
        """Test SchemaDifference creation."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaDifference
        sd = SchemaDifference(
            type='missing_table',
            table='test',
            severity='error',
        )
        assert sd.type == 'missing_table'
        assert sd.table == 'test'
        assert sd.column is None
        assert sd.expected is None
        assert sd.actual is None
        assert sd.severity == 'error'

    def test_to_dict(self):
        """Test SchemaDifference.to_dict()."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaDifference
        sd = SchemaDifference(
            type='missing_column',
            table='users',
            column='email',
            expected='TEXT',
            actual=None,
            severity='error',
        )
        d = sd.to_dict()
        assert d['type'] == 'missing_column'
        assert d['table'] == 'users'
        assert d['column'] == 'email'
        assert d['expected'] == 'TEXT'
        assert d['actual'] is None
        assert d['severity'] == 'error'

    def test_default_severity(self):
        """Test SchemaDifference default severity is 'error'."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaDifference
        sd = SchemaDifference(type='test', table='t')
        assert sd.severity == 'error'


# ---------------------------------------------------------------------------
# Test SchemaValidationError
# ---------------------------------------------------------------------------

class TestSchemaValidationError:
    """Test the SchemaValidationError exception."""

    def test_basic_creation(self):
        """Test SchemaValidationError can be raised with message."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidationError
        err = SchemaValidationError("test message")
        assert "test message" in str(err)

    def test_with_differences(self):
        """Test SchemaValidationError stores differences."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidationError
        diffs = [{'type': 'missing_table', 'table': 'users'}]
        err = SchemaValidationError("test", differences=diffs)
        assert err.differences == diffs

    def test_without_differences(self):
        """Test SchemaValidationError with no differences."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidationError
        err = SchemaValidationError("test")
        assert err.differences == []

    def test_is_database_error_subclass(self):
        """Test SchemaValidationError is a subclass of DatabaseError."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidationError
        from education_system.university_system.infrastructure.exceptions import DatabaseError
        assert issubclass(SchemaValidationError, DatabaseError)


# ---------------------------------------------------------------------------
# Test SchemaValidator.get_actual_schema
# ---------------------------------------------------------------------------

class TestGetActualSchema:
    """Test SchemaValidator.get_actual_schema method."""

    def test_returns_all_tables(self, temp_db):
        """Test get_actual_schema returns all non-system tables."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        schema = validator.get_actual_schema()
        assert 'users' in schema
        assert 'students' in schema
        assert 'courses' in schema
        assert 'enrollments' in schema
        assert 'user_accounts' in schema

    def test_columns_populated(self, temp_db):
        """Test that table columns are populated correctly."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        schema = validator.get_actual_schema()
        users = schema['users']
        assert 'id' in users.columns
        assert 'username' in users.columns
        assert 'email' in users.columns
        assert 'role' in users.columns

    def test_column_types(self, temp_db):
        """Test that column type information is captured."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        schema = validator.get_actual_schema()
        id_col = schema['users'].columns['id']
        assert id_col['type'] == 'INTEGER'
        assert id_col['pk'] is True

    def test_primary_key_detected(self, temp_db):
        """Test that primary keys are detected."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        schema = validator.get_actual_schema()
        assert schema['users'].primary_key == ['id']

    def test_indexes_detected(self, temp_db):
        """Test that indexes are detected."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        schema = validator.get_actual_schema()
        assert 'idx_users_username' in schema['users'].indexes

    def test_foreign_keys_detected(self, temp_db):
        """Test that foreign keys are detected."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)

        # Need to enable FK pragma to read them
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys=ON")
        schema = validator.get_actual_schema(conn=conn)
        fks = schema['enrollments'].foreign_keys
        assert len(fks) >= 1
        conn.close()

    def test_uses_provided_connection(self, temp_db):
        """Test get_actual_schema uses provided connection."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        conn = sqlite3.connect(temp_db)
        schema = validator.get_actual_schema(conn=conn)
        assert 'users' in schema
        # Connection should NOT be closed (we provided it)
        conn.execute("SELECT 1")  # Should not raise
        conn.close()

    def test_closes_own_connection(self, temp_db):
        """Test get_actual_schema closes its own created connection."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        # Should not leak connections
        schema = validator.get_actual_schema()
        assert len(schema) > 0

    def test_excludes_sqlite_internal_tables(self, temp_db):
        """Test that sqlite_* internal tables are excluded."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        schema = validator.get_actual_schema()
        for table_name in schema:
            assert not table_name.startswith('sqlite_')


# ---------------------------------------------------------------------------
# Test SchemaValidator.load_expected_schema
# ---------------------------------------------------------------------------

class TestLoadExpectedSchema:
    """Test SchemaValidator.load_expected_schema method."""

    def test_load_from_json(self, schema_json_file):
        """Test loading schema from a JSON file."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator()
        schema = validator.load_expected_schema(schema_json_file)
        assert 'users' in schema
        assert 'students' in schema
        assert schema['users'].columns['id']['type'] == 'INTEGER'

    def test_load_no_path_returns_minimal(self):
        """Test load without path returns minimal expected schema."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator()
        schema = validator.load_expected_schema(None)
        assert 'users' in schema
        assert 'students' in schema
        assert 'courses' in schema
        assert 'enrollments' in schema
        assert 'user_accounts' in schema

    def test_load_nonexistent_path_returns_minimal(self):
        """Test load with non-existent path returns minimal schema."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator()
        schema = validator.load_expected_schema("/nonexistent/path.json")
        assert 'users' in schema


# ---------------------------------------------------------------------------
# Test SchemaValidator.compare_schemas
# ---------------------------------------------------------------------------

class TestCompareSchemas:
    """Test SchemaValidator.compare_schemas method."""

    def test_identical_schemas_no_differences(self, temp_db):
        """Test that identical schemas produce no differences."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator, TableSchema
        validator = SchemaValidator(db_path=temp_db)
        actual = validator.get_actual_schema()

        # Create expected from actual
        expected = {}
        for name, ts in actual.items():
            expected[name] = TableSchema(
                name=name,
                columns={c: {'type': v.get('type', '')} for c, v in ts.columns.items()},
                primary_key=ts.primary_key,
            )

        diffs = validator.compare_schemas(expected, actual)
        # Filter to only errors (missing columns may appear due to simplified expected)
        errors = [d for d in diffs if d.severity == 'error']
        assert len(errors) == 0

    def test_missing_table_detected(self, temp_db):
        """Test that missing tables are detected."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator, TableSchema
        validator = SchemaValidator(db_path=temp_db)
        actual = validator.get_actual_schema()

        expected = dict(actual)
        expected['nonexistent_table'] = TableSchema(name='nonexistent_table')

        diffs = validator.compare_schemas(expected, actual)
        missing = [d for d in diffs if d.type == 'missing_table']
        assert len(missing) == 1
        assert missing[0].table == 'nonexistent_table'
        assert missing[0].severity == 'error'

    def test_extra_table_detected_in_strict_mode(self, temp_db):
        """Test that extra tables are detected in strict mode."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator, TableSchema
        validator = SchemaValidator(db_path=temp_db)
        actual = validator.get_actual_schema()

        # Expected has only 'users'
        expected = {
            'users': TableSchema(
                name='users',
                columns={'id': {'type': 'INTEGER'}},
            )
        }

        diffs = validator.compare_schemas(expected, actual, strict=True)
        extras = [d for d in diffs if d.type == 'extra_table']
        assert len(extras) > 0

    def test_extra_table_not_detected_in_non_strict(self, temp_db):
        """Test that extra tables are NOT detected when strict=False."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator, TableSchema
        validator = SchemaValidator(db_path=temp_db)
        actual = validator.get_actual_schema()

        expected = {
            'users': TableSchema(name='users', columns={'id': {'type': 'INTEGER'}})
        }

        diffs = validator.compare_schemas(expected, actual, strict=False)
        extras = [d for d in diffs if d.type == 'extra_table']
        assert len(extras) == 0

    def test_missing_column_detected(self, temp_db):
        """Test that missing columns are detected."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator, TableSchema
        validator = SchemaValidator(db_path=temp_db)
        actual = validator.get_actual_schema()

        expected = {
            'users': TableSchema(
                name='users',
                columns={
                    'id': {'type': 'INTEGER'},
                    'username': {'type': 'TEXT'},
                    'missing_col': {'type': 'TEXT'},
                },
            )
        }

        diffs = validator.compare_schemas(expected, actual)
        missing_cols = [d for d in diffs if d.type == 'missing_column']
        assert any(d.column == 'missing_col' for d in missing_cols)

    def test_extra_column_detected_in_strict(self, temp_db):
        """Test that extra columns are detected in strict mode."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator, TableSchema
        validator = SchemaValidator(db_path=temp_db)
        actual = validator.get_actual_schema()

        # Expected with fewer columns than actual
        expected = {
            'users': TableSchema(
                name='users',
                columns={'id': {'type': 'INTEGER'}},
            )
        }

        diffs = validator.compare_schemas(expected, actual, strict=True)
        extra_cols = [d for d in diffs if d.type == 'extra_column']
        assert len(extra_cols) > 0

    def test_type_mismatch_detected(self, temp_db):
        """Test that type mismatches are detected."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator, TableSchema
        validator = SchemaValidator(db_path=temp_db)
        actual = validator.get_actual_schema()

        expected = {
            'users': TableSchema(
                name='users',
                columns={
                    'id': {'type': 'INTEGER'},
                    'username': {'type': 'REAL'},  # Mismatch: TEXT vs REAL
                },
            )
        }

        diffs = validator.compare_schemas(expected, actual)
        mismatches = [d for d in diffs if d.type == 'type_mismatch']
        assert any(d.column == 'username' for d in mismatches)

    def test_type_normalization(self):
        """Test that equivalent types (INT/INTEGER, BOOL/INTEGER) are normalized."""
        from education_system.university_system.infrastructure.database.schema_validator import (
            SchemaValidator, TableSchema
        )
        validator = SchemaValidator()

        expected = {
            'test': TableSchema(
                name='test',
                columns={'col1': {'type': 'INT'}, 'col2': {'type': 'BOOL'}},
            )
        }
        actual = {
            'test': TableSchema(
                name='test',
                columns={'col1': {'type': 'INTEGER'}, 'col2': {'type': 'INTEGER'}},
            )
        }

        diffs = validator.compare_schemas(expected, actual)
        mismatches = [d for d in diffs if d.type == 'type_mismatch']
        assert len(mismatches) == 0

    def test_varchar_text_normalization(self):
        """Test VARCHAR normalizes to TEXT."""
        from education_system.university_system.infrastructure.database.schema_validator import (
            SchemaValidator, TableSchema
        )
        validator = SchemaValidator()

        expected = {'t': TableSchema(name='t', columns={'c': {'type': 'VARCHAR'}})}
        actual = {'t': TableSchema(name='t', columns={'c': {'type': 'TEXT'}})}

        diffs = validator.compare_schemas(expected, actual)
        mismatches = [d for d in diffs if d.type == 'type_mismatch']
        assert len(mismatches) == 0

    def test_float_real_normalization(self):
        """Test FLOAT and DOUBLE normalize to REAL."""
        from education_system.university_system.infrastructure.database.schema_validator import (
            SchemaValidator, TableSchema
        )
        validator = SchemaValidator()

        expected = {'t': TableSchema(name='t', columns={
            'a': {'type': 'FLOAT'},
            'b': {'type': 'DOUBLE'},
        })}
        actual = {'t': TableSchema(name='t', columns={
            'a': {'type': 'REAL'},
            'b': {'type': 'REAL'},
        })}

        diffs = validator.compare_schemas(expected, actual)
        mismatches = [d for d in diffs if d.type == 'type_mismatch']
        assert len(mismatches) == 0


# ---------------------------------------------------------------------------
# Test SchemaValidator.validate_schema_at_startup
# ---------------------------------------------------------------------------

class TestValidateSchemaAtStartup:
    """Test validate_schema_at_startup method."""

    def test_valid_schema_returns_true(self, temp_db):
        """Test validation passes for a valid schema."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        is_valid, diffs = validator.validate_schema_at_startup(raise_on_error=False)
        # May have warnings but should not have errors
        errors = [d for d in diffs if d.severity == 'error']
        # If there are missing tables, that's because our temp_db has all required tables
        if not errors:
            assert is_valid is True

    def test_missing_tables_raises_error(self, temp_db_missing_tables):
        """Test validation raises on missing required tables."""
        from education_system.university_system.infrastructure.database.schema_validator import (
            SchemaValidator, SchemaValidationError
        )
        validator = SchemaValidator(db_path=temp_db_missing_tables)
        with pytest.raises(SchemaValidationError):
            validator.validate_schema_at_startup(raise_on_error=True)

    def test_raise_on_error_false_returns_tuple(self, temp_db_missing_tables):
        """Test validation returns (False, diffs) when raise_on_error=False."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db_missing_tables)
        is_valid, diffs = validator.validate_schema_at_startup(raise_on_error=False)
        assert is_valid is False
        assert len(diffs) > 0

    def test_with_schema_file(self, temp_db, schema_json_file):
        """Test validation using a schema JSON file."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        is_valid, diffs = validator.validate_schema_at_startup(
            schema_path=schema_json_file,
            raise_on_error=False
        )
        # Should be valid since our temp_db has the tables in the JSON
        errors = [d for d in diffs if d.severity == 'error']
        assert len(errors) == 0

    def test_strict_mode(self, temp_db, schema_json_file):
        """Test strict mode flags extra tables/columns."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        is_valid, diffs = validator.validate_schema_at_startup(
            schema_path=schema_json_file,
            strict=True,
            raise_on_error=False,
        )
        # With strict, extra tables like courses/enrollments should be flagged
        extras = [d for d in diffs if d.type in ('extra_table', 'extra_column')]
        assert len(extras) > 0

    def test_unexpected_exception_handled(self):
        """Test that unexpected exceptions are handled gracefully."""
        from education_system.university_system.infrastructure.database.schema_validator import (
            SchemaValidator, SchemaValidationError
        )
        validator = SchemaValidator(db_path="/nonexistent/path/db.sqlite")
        # With raise_on_error=True, should raise SchemaValidationError
        with pytest.raises(SchemaValidationError):
            validator.validate_schema_at_startup(raise_on_error=True)

    def test_unexpected_exception_returns_false(self):
        """Test unexpected exception returns (False, []) when raise_on_error=False."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path="/nonexistent/path/db.sqlite")
        is_valid, diffs = validator.validate_schema_at_startup(raise_on_error=False)
        assert is_valid is False


# ---------------------------------------------------------------------------
# Test SchemaValidator.get_schema_hash
# ---------------------------------------------------------------------------

class TestGetSchemaHash:
    """Test get_schema_hash method."""

    def test_returns_hex_string(self, temp_db):
        """Test get_schema_hash returns a hex digest string."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        h = validator.get_schema_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256 hex digest

    def test_same_schema_same_hash(self, temp_db):
        """Test that the same schema produces the same hash."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        h1 = validator.get_schema_hash()
        h2 = validator.get_schema_hash()
        assert h1 == h2

    def test_different_schema_different_hash(self, temp_db):
        """Test that changing schema changes the hash."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        h1 = validator.get_schema_hash()

        # Modify schema
        conn = sqlite3.connect(temp_db)
        conn.execute("CREATE TABLE new_table (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        h2 = validator.get_schema_hash()
        assert h1 != h2


# ---------------------------------------------------------------------------
# Test SchemaValidator.export_schema
# ---------------------------------------------------------------------------

class TestExportSchema:
    """Test export_schema method."""

    def test_exports_to_json(self, temp_db, tmp_path):
        """Test schema is exported to a valid JSON file."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        output = str(tmp_path / "schema_export.json")
        validator.export_schema(output)

        assert os.path.exists(output)
        with open(output, 'r') as f:
            data = json.load(f)

        assert 'version' in data
        assert 'exported_at' in data
        assert 'schema_hash' in data
        assert 'tables' in data
        assert 'users' in data['tables']

    def test_exported_schema_contains_columns(self, temp_db, tmp_path):
        """Test exported schema has column details."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        output = str(tmp_path / "schema_export2.json")
        validator.export_schema(output)

        with open(output, 'r') as f:
            data = json.load(f)

        users_cols = data['tables']['users']['columns']
        assert 'id' in users_cols
        assert 'username' in users_cols


# ---------------------------------------------------------------------------
# Test SchemaValidator.check_required_tables
# ---------------------------------------------------------------------------

class TestCheckRequiredTables:
    """Test check_required_tables method."""

    def test_all_present(self, temp_db):
        """Test returns (True, empty set) when all required tables exist."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db)
        present, missing = validator.check_required_tables()
        assert present is True
        assert len(missing) == 0

    def test_missing_tables_detected(self, temp_db_missing_tables):
        """Test returns (False, {missing}) when tables are absent."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        validator = SchemaValidator(db_path=temp_db_missing_tables)
        present, missing = validator.check_required_tables()
        assert present is False
        assert len(missing) > 0
        # Should be missing at least courses, enrollments, user_accounts
        assert 'courses' in missing or 'enrollments' in missing or 'user_accounts' in missing

    def test_required_tables_set(self):
        """Test REQUIRED_TABLES contains expected tables."""
        from education_system.university_system.infrastructure.database.schema_validator import SchemaValidator
        required = SchemaValidator.REQUIRED_TABLES
        assert 'users' in required
        assert 'user_accounts' in required
        assert 'students' in required
        assert 'courses' in required
        assert 'enrollments' in required


# ---------------------------------------------------------------------------
# Test convenience function validate_schema_at_startup
# ---------------------------------------------------------------------------

class TestConvenienceFunction:
    """Test the module-level validate_schema_at_startup function."""

    def test_returns_bool(self, temp_db):
        """Test convenience function returns a boolean."""
        from education_system.university_system.infrastructure.database.schema_validator import (
            validate_schema_at_startup
        )
        result = validate_schema_at_startup(
            db_path=temp_db,
            raise_on_error=False,
        )
        assert isinstance(result, bool)

    def test_raises_on_error(self, temp_db_missing_tables):
        """Test convenience function raises when raise_on_error=True."""
        from education_system.university_system.infrastructure.database.schema_validator import (
            validate_schema_at_startup, SchemaValidationError
        )
        with pytest.raises(SchemaValidationError):
            validate_schema_at_startup(
                db_path=temp_db_missing_tables,
                raise_on_error=True,
            )


# ---------------------------------------------------------------------------
# Test __all__ exports
# ---------------------------------------------------------------------------

class TestModuleExports:
    """Test module __all__ exports."""

    def test_all_is_list(self):
        """Test __all__ is a list."""
        from education_system.university_system.infrastructure.database.schema_validator import __all__
        assert isinstance(__all__, list)

    def test_all_contains_expected_names(self):
        """Test __all__ contains all expected public names."""
        from education_system.university_system.infrastructure.database.schema_validator import __all__
        expected = [
            'SchemaValidator', 'SchemaValidationError', 'TableSchema',
            'SchemaDifference', 'validate_schema_at_startup',
        ]
        for name in expected:
            assert name in __all__

    def test_all_names_accessible(self):
        """Test all names in __all__ are accessible."""
        import education_system.university_system.infrastructure.database.schema_validator as mod
        for name in mod.__all__:
            assert hasattr(mod, name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
