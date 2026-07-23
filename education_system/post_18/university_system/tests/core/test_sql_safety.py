"""Tests for university_system.core.sql_safety."""
import sqlite3

import pytest

from education_system.post_18.university_system.core import sql_safety
from education_system.post_18.university_system.core.sql_safety import (
    ColumnDefinition,
    SQLIdentifierError,
    KNOWN_TABLES,
    VALID_SQLITE_TYPES,
    build_update_set,
    build_where_clause,
    escape_like,
    get_table_schema,
    get_valid_columns,
    get_valid_tables,
    is_valid_identifier_format,
    safe_alter_table_add_column,
    safe_table_query,
    validate_column_definition,
    validate_column_name,
    validate_field_for_query,
    validate_identifier,
    validate_table_name,
)


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL, grade INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE courses (id INTEGER PRIMARY KEY, title TEXT)")
    c.commit()
    yield c
    c.close()


class TestEscapeLike:
    def test_escapes_wildcards(self):
        assert escape_like("100%") == "100\\%"
        assert escape_like("a_b") == "a\\_b"
        assert escape_like("foo") == "foo"


class TestIsValidIdentifierFormat:
    @pytest.mark.parametrize("ident", ["users", "_priv", "tbl_1", "A", "x" * 128])
    def test_accepts_valid(self, ident):
        assert is_valid_identifier_format(ident) is True

    @pytest.mark.parametrize("ident", ["", "1users", "user-name", "user name", "users;", "x" * 129])
    def test_rejects_invalid(self, ident):
        assert is_valid_identifier_format(ident) is False

    def test_rejects_non_string(self):
        assert is_valid_identifier_format(None) is False
        assert is_valid_identifier_format(123) is False


class TestValidateTableName:
    def test_accepts_known_table(self):
        assert validate_table_name("students") == "students"

    def test_case_insensitive_whitelist(self):
        assert validate_table_name("STUDENTS") == "STUDENTS"

    def test_rejects_bad_format(self):
        with pytest.raises(SQLIdentifierError):
            validate_table_name("students; DROP TABLE x")

    def test_rejects_not_in_whitelist(self):
        with pytest.raises(SQLIdentifierError):
            validate_table_name("never_table_name_xyz")

    def test_allowed_tables_parameter(self):
        assert validate_table_name("custom_tbl", allowed_tables={"custom_tbl"}) == "custom_tbl"

    def test_conn_verifies_against_database(self, conn):
        # Not in KNOWN_TABLES but exists in this DB
        assert validate_table_name("courses", allowed_tables=set(), conn=conn) == "courses"

    def test_conn_rejects_missing_table(self, conn):
        with pytest.raises(SQLIdentifierError):
            validate_table_name("ghost_tbl", allowed_tables=set(), conn=conn)


class TestValidateColumnName:
    def test_format_rejection(self):
        with pytest.raises(SQLIdentifierError):
            validate_column_name("bad-name")

    def test_allowed_columns_accepts(self):
        assert validate_column_name("name", allowed_columns={"name"}) == "name"

    def test_allowed_columns_rejects(self):
        with pytest.raises(SQLIdentifierError):
            validate_column_name("name", allowed_columns={"other"})

    def test_schema_check_accepts(self, conn):
        assert validate_column_name("name", table_name="students", conn=conn) == "name"

    def test_schema_check_rejects_missing(self, conn):
        with pytest.raises(SQLIdentifierError):
            validate_column_name("ghost_col", table_name="students", conn=conn)


class TestValidateIdentifier:
    def test_accepts_valid(self):
        assert validate_identifier("col_name") == "col_name"

    def test_rejects_bad_format(self):
        with pytest.raises(SQLIdentifierError):
            validate_identifier("1bad")

    def test_rejects_trailing_underscore(self):
        with pytest.raises(SQLIdentifierError):
            validate_identifier("trailing_")


class TestGetValidTables:
    def test_no_conn_returns_known_tables(self):
        result = get_valid_tables()
        assert result == set(KNOWN_TABLES)

    def test_with_conn_returns_actual_tables(self, conn):
        result = get_valid_tables(conn=conn)
        assert "students" in result
        assert "courses" in result


class TestGetValidColumns:
    def test_returns_columns(self, conn):
        cols = get_valid_columns("students", conn=conn)
        assert cols == {"id", "name", "grade"}

    def test_invalid_table_raises(self, conn):
        with pytest.raises(SQLIdentifierError):
            get_valid_columns("ghost", conn=conn)


class TestSafeTableQuery:
    def test_wraps_in_brackets(self):
        assert safe_table_query("students") == "[students]"

    def test_invalid_table_raises(self):
        with pytest.raises(SQLIdentifierError):
            safe_table_query("bad-name")


class TestValidateFieldForQuery:
    def test_accepts_allowed_field(self):
        assert validate_field_for_query("status", {"status", "name"}) == "status"

    def test_rejects_unknown_field(self):
        with pytest.raises(SQLIdentifierError):
            validate_field_for_query("ghost", {"name"})

    def test_rejects_bad_format(self):
        with pytest.raises(SQLIdentifierError):
            validate_field_for_query("bad-name", {"bad-name"})


class TestValidateColumnDefinition:
    def test_accepts_simple_type(self):
        col = validate_column_definition("new_col", "TEXT")
        assert isinstance(col, ColumnDefinition)
        assert col.name == "new_col"
        assert col.type_def == "TEXT"

    def test_accepts_type_with_modifier(self):
        col = validate_column_definition("new_col", "INTEGER DEFAULT 0")
        assert col.type_def == "INTEGER DEFAULT 0"

    def test_rejects_invalid_name(self):
        with pytest.raises(SQLIdentifierError):
            validate_column_definition("bad-name", "TEXT")

    def test_rejects_empty_type(self):
        with pytest.raises(SQLIdentifierError):
            validate_column_definition("x", "")

    def test_rejects_unknown_base_type(self):
        with pytest.raises(SQLIdentifierError):
            validate_column_definition("x", "JIBBERISH")

    def test_rejects_when_column_exists(self, conn):
        with pytest.raises(SQLIdentifierError):
            validate_column_definition("name", "TEXT", table_name="students", conn=conn)

    def test_repr(self):
        col = ColumnDefinition("x", "TEXT")
        assert "x" in repr(col) and "TEXT" in repr(col)


class TestSafeAlterTableAddColumn:
    def test_adds_new_column(self, conn):
        # 'students' is in KNOWN_TABLES; insert allows safe ALTER
        added = safe_alter_table_add_column("students", "email", "TEXT", conn=conn)
        assert added is True
        cols = get_valid_columns("students", conn=conn)
        assert "email" in cols

    def test_if_not_exists_skips_existing(self, conn):
        # 'name' already exists in students
        assert safe_alter_table_add_column("students", "name", "TEXT", conn=conn) is False

    def test_if_not_exists_false_raises_on_existing(self, conn):
        with pytest.raises(SQLIdentifierError):
            safe_alter_table_add_column("students", "name", "TEXT", conn=conn, if_not_exists=False)


class TestGetTableSchema:
    def test_returns_full_schema(self, conn):
        schema = get_table_schema("students", conn=conn)
        assert schema["name"] == "students"
        assert "id" in schema["column_names"]
        # `id` is the primary key
        pk_cols = [c for c in schema["columns"] if c["pk"]]
        assert len(pk_cols) == 1 and pk_cols[0]["name"] == "id"
        # NOT NULL on name
        name_col = next(c for c in schema["columns"] if c["name"] == "name")
        assert name_col["notnull"] is True


class TestBuildWhereClause:
    def test_empty_returns_empty_string(self):
        assert build_where_clause([]) == ""

    def test_joins_with_and(self):
        result = build_where_clause(["a = ?", "b = ?"])
        assert result == " WHERE a = ? AND b = ?"


class TestBuildUpdateSet:
    def test_filters_by_allowed_fields(self):
        clause, vals = build_update_set(
            {"status": "active", "name": "x", "evil": "drop"},
            ["status", "name"],
        )
        assert "status = ?" in clause
        assert "name = ?" in clause
        assert "evil" not in clause
        assert vals == ["active", "x"]

    def test_empty_when_no_match(self):
        clause, vals = build_update_set({}, ["status"])
        assert clause == ""
        assert vals == []

    def test_rejects_invalid_field_name(self):
        # `bad-name` is in allowed_fields but invalid format
        with pytest.raises(SQLIdentifierError):
            build_update_set({"bad-name": 1}, ["bad-name"])


class TestKnownConstants:
    def test_valid_sqlite_types_subset(self):
        for required in ("TEXT", "INTEGER", "REAL", "BLOB"):
            assert required in VALID_SQLITE_TYPES

    def test_known_tables_has_core(self):
        for required in ("students", "users", "courses"):
            assert required in KNOWN_TABLES
