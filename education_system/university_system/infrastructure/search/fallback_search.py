"""
Fallback search service using SQLite FTS (Full-Text Search)

Used when Elasticsearch is not available. Provides basic full-text search
capabilities using SQLite's FTS5 extension.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier  # nosec B608

logger = logging.getLogger(__name__)


class FallbackSearchService:
    """
    SQLite FTS-based search service

    Provides basic full-text search when Elasticsearch is unavailable.
    Uses SQLite FTS5 virtual tables for full-text indexing.
    """

    def __init__(self):
        """Initialize fallback search service"""
        self._create_fts_tables()

    def _create_fts_tables(self):
        """Create FTS5 virtual tables for search"""
        with transaction() as conn:
            # Students FTS table
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS students_fts
                USING fts5(
                    student_id UNINDEXED,
                    name,
                    email,
                    major,
                    course,
                    content='',
                    tokenize='porter'
                )
            ''')

            # Courses FTS table
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS courses_fts
                USING fts5(
                    course_id UNINDEXED,
                    code,
                    name,
                    description,
                    instructor,
                    department,
                    content='',
                    tokenize='porter'
                )
            ''')

            # Staff FTS table
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS staff_fts
                USING fts5(
                    staff_id UNINDEXED,
                    name,
                    email,
                    department,
                    position,
                    content='',
                    tokenize='porter'
                )
            ''')

            # Events FTS table
            conn.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS events_fts
                USING fts5(
                    event_id UNINDEXED,
                    title,
                    description,
                    location,
                    category,
                    content='',
                    tokenize='porter'
                )
            ''')

    def index_document(
        self,
        index: str,
        doc_id: str,
        document: Dict[str, Any]
    ) -> bool:
        """Index a document in FTS table"""
        try:
            table_name = validate_table_name(index + "_fts")

            # Build column names and values
            columns = []
            values = []

            # Always include ID
            id_field = validate_identifier(self._get_id_field(index), "column")
            columns.append(id_field)
            values.append(doc_id)

            # Add searchable fields
            searchable_fields = self._get_searchable_fields(index)
            for field in searchable_fields:
                if field in document:
                    safe_field = validate_identifier(field, "column")
                    columns.append(safe_field)
                    values.append(str(document[field]))

            with transaction() as conn:
                placeholders = ', '.join(['?' for _ in values])
                cols = ', '.join(columns)

                # Delete existing entry first
                conn.execute(
                    "DELETE FROM [" + table_name + "] WHERE [" + id_field + "] = ?",
                    (doc_id,)
                )

                # Insert new entry
                conn.execute(
                    "INSERT INTO [" + table_name + "] (" + cols + ") VALUES (" + placeholders + ")",
                    values
                )

            return True

        except Exception as e:
            logger.error(f"Error indexing document in FTS: {e}")
            return False

    def search(
        self,
        index: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 10,
        from_: int = 0
    ) -> Dict[str, Any]:
        """
        Search documents using FTS

        Args:
            index: Index name
            query: Search query
            filters: Filter criteria (applied via JOIN with source table)
            size: Number of results
            from_: Offset for pagination

        Returns:
            Search results in Elasticsearch-compatible format
        """
        try:
            table_name = validate_table_name(index + "_fts")
            id_field = validate_identifier(self._get_id_field(index), "column")

            # Build FTS query
            # Escape special characters and add wildcard
            fts_query = query.replace('"', '').strip()
            fts_query = '"' + fts_query + '"*'  # Prefix match

            # Base FTS search
            sql = (
                "SELECT [" + id_field + "], rank"
                " FROM [" + table_name + "]"
                " WHERE [" + table_name + "] MATCH ?"
                " ORDER BY rank"
                " LIMIT ? OFFSET ?"
            )

            with get_connection() as conn:
                cursor = conn.execute(sql, (fts_query, size, from_))
                fts_results = cursor.fetchall()

                # Get full documents from source table
                hits = []
                for row in fts_results:
                    doc_id = row[0]
                    score = -row[1]  # FTS rank is negative (closer to 0 is better)

                    # Fetch full document
                    doc = self._fetch_document(conn, index, doc_id, filters)
                    if doc:
                        hits.append({
                            '_id': doc_id,
                            '_score': score,
                            '_source': doc
                        })

                # Get total count
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM [" + table_name + "] WHERE [" + table_name + "] MATCH ?",
                    (fts_query,)
                )
                total = cursor.fetchone()[0]

            return {
                'hits': {
                    'hits': hits,
                    'total': {'value': total}
                }
            }

        except Exception as e:
            logger.error(f"Error searching FTS: {e}")
            return {'hits': {'hits': [], 'total': {'value': 0}}}

    def _fetch_document(
        self,
        conn,
        index: str,
        doc_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch full document from source table"""
        try:
            # Map index to table name
            table_map = {
                'students': 'students',
                'courses': 'courses',
                'staff': 'staff_members',
                'events': 'campus_events'
            }

            table = validate_table_name(table_map.get(index, index))
            id_field = validate_identifier(self._get_id_field(index), "column")

            # Build query
            sql = "SELECT * FROM [" + table + "] WHERE [" + id_field + "] = ?"
            params = [doc_id]

            # Add filters if provided
            if filters:
                for field, value in filters.items():
                    safe_field = validate_identifier(field, "column")
                    sql += " AND [" + safe_field + "] = ?"
                    params.append(value)

            cursor = conn.execute(sql, params)
            row = cursor.fetchone()

            if not row:
                return None

            # Convert to dict
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"Error fetching document: {e}")
            return None

    def delete_document(self, index: str, doc_id: str) -> bool:
        """Delete document from FTS table"""
        try:
            table_name = validate_table_name(index + "_fts")
            id_field = validate_identifier(self._get_id_field(index), "column")

            with transaction() as conn:
                conn.execute(
                    "DELETE FROM [" + table_name + "] WHERE [" + id_field + "] = ?",
                    (doc_id,)
                )

            return True

        except Exception as e:
            logger.error(f"Error deleting from FTS: {e}")
            return False

    def count(self, index: str, query: Optional[str] = None) -> int:
        """Count matching documents"""
        try:
            table_name = validate_table_name(index + "_fts")

            if query:
                fts_query = '"' + query.replace(chr(34), "").strip() + '"*'
                sql = "SELECT COUNT(*) FROM [" + table_name + "] WHERE [" + table_name + "] MATCH ?"
                params = (fts_query,)
            else:
                sql = "SELECT COUNT(*) FROM [" + table_name + "]"
                params = ()

            with get_connection() as conn:
                cursor = conn.execute(sql, params)
                return cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Error counting FTS: {e}")
            return 0

    def _get_id_field(self, index: str) -> str:
        """Get ID field name for index"""
        id_fields = {
            'students': 'student_id',
            'courses': 'course_id',
            'staff': 'staff_id',
            'events': 'event_id',
            'research': 'research_id'
        }
        return id_fields.get(index, 'id')

    def _get_searchable_fields(self, index: str) -> List[str]:
        """Get searchable fields for index"""
        fields = {
            'students': ['name', 'email', 'major', 'course'],
            'courses': ['code', 'name', 'description', 'instructor', 'department'],
            'staff': ['name', 'email', 'department', 'position'],
            'events': ['title', 'description', 'location', 'category'],
            'research': ['title', 'abstract', 'authors', 'keywords']
        }
        return fields.get(index, [])
