"""
Async Database Operations

Provides async wrappers for database operations to prevent
blocking the main thread during queries.
"""

import asyncio
import threading
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Callable, List, Optional, Tuple, TypeVar, Union
from functools import wraps
from education_system.university_system.core.sql_safety import validate_table_name, validate_identifier

logger = logging.getLogger(__name__)

# Type variable for generic return types
T = TypeVar('T')

# Shared thread pool for database operations
_db_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def get_db_executor(max_workers: int = 3) -> ThreadPoolExecutor:
    """
    Get the shared thread pool for database operations.

    Using a dedicated pool prevents database operations from
    competing with other background tasks.
    """
    global _db_executor
    if _db_executor is None:
        with _executor_lock:
            if _db_executor is None:
                _db_executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix="db_async_"
                )
    return _db_executor


class AsyncDatabaseWrapper:
    """
    Wrapper to make synchronous database operations asynchronous.

    Example:
        from education_system.university_system.infrastructure.database.db import get_connection

        async_db = AsyncDatabaseWrapper()

        # Async query
        async def fetch_students():
            results = await async_db.query(
                "SELECT * FROM students WHERE status = ?",
                ("active",)
            )
            return results

        # Run in event loop
        students = asyncio.run(fetch_students())
    """

    def __init__(self, db_path: Optional[str] = None, max_workers: int = 3):
        """
        Initialize the async database wrapper.

        Args:
            db_path: Path to database (uses default if None)
            max_workers: Max concurrent database threads
        """
        self.db_path = db_path
        self._executor = get_db_executor(max_workers)
        self._local = threading.local()

    def _get_connection(self):
        """Get a database connection for the current thread."""
        # Import here to avoid circular imports
        from education_system.university_system.infrastructure.database.db import get_connection
        return get_connection()

    async def query(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        fetch: str = "all"
    ) -> Union[List[Tuple], Tuple, None]:
        """
        Execute a SELECT query asynchronously.

        Args:
            sql: SQL query string
            params: Query parameters
            fetch: "all" for fetchall, "one" for fetchone, "none" for no fetch

        Returns:
            Query results
        """
        loop = asyncio.get_event_loop()

        def execute():
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)

                if fetch == "all":
                    return cursor.fetchall()
                elif fetch == "one":
                    return cursor.fetchone()
                return None

        return await loop.run_in_executor(self._executor, execute)

    async def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query asynchronously.

        Args:
            sql: SQL statement
            params: Query parameters

        Returns:
            Number of affected rows
        """
        loop = asyncio.get_event_loop()

        def execute():
            from education_system.university_system.infrastructure.database.db import transaction
            with transaction() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                return cursor.rowcount

        return await loop.run_in_executor(self._executor, execute)

    async def execute_many(
        self,
        sql: str,
        params_list: List[Tuple]
    ) -> int:
        """
        Execute multiple INSERT/UPDATE/DELETE operations asynchronously.

        Args:
            sql: SQL statement
            params_list: List of parameter tuples

        Returns:
            Total number of affected rows
        """
        loop = asyncio.get_event_loop()

        def execute():
            from education_system.university_system.infrastructure.database.db import transaction
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, params_list)
                return cursor.rowcount

        return await loop.run_in_executor(self._executor, execute)

    async def fetch_dict(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> List[dict]:
        """
        Execute a query and return results as dictionaries.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of dictionaries with column names as keys
        """
        loop = asyncio.get_event_loop()

        def execute():
            with self._get_connection() as conn:
                conn.row_factory = lambda c, r: dict(
                    zip([col[0] for col in c.description], r)
                )
                cursor = conn.cursor()
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                return cursor.fetchall()

        return await loop.run_in_executor(self._executor, execute)

    @asynccontextmanager
    async def transaction(self):
        """
        Async context manager for transactions.

        Example:
            async with async_db.transaction() as conn:
                await async_db.execute("INSERT INTO ...", conn=conn)
                await async_db.execute("UPDATE ...", conn=conn)
        """
        from education_system.university_system.infrastructure.database.db import get_connection

        loop = asyncio.get_event_loop()

        def get_conn():
            conn = get_connection()
            conn.execute("BEGIN")
            return conn

        conn = await loop.run_in_executor(self._executor, get_conn)

        try:
            yield conn

            def commit():
                conn.commit()
                conn.close()

            await loop.run_in_executor(self._executor, commit)

        except Exception:
            def rollback():
                conn.rollback()
                conn.close()

            await loop.run_in_executor(self._executor, rollback)
            raise


# Singleton instance
_async_db: Optional[AsyncDatabaseWrapper] = None


def get_async_db() -> AsyncDatabaseWrapper:
    """Get the global async database wrapper."""
    global _async_db
    if _async_db is None:
        _async_db = AsyncDatabaseWrapper()
    return _async_db


def async_query(sql: str, params: Optional[Tuple] = None):
    """
    Decorator to make a function return async query results.

    The decorated function should return (sql, params) tuple.

    Example:
        @async_query
        def get_active_students():
            return "SELECT * FROM students WHERE status = ?", ("active",)

        # Use in async context
        students = await get_active_students()
    """
    async def wrapper():
        db = get_async_db()
        return await db.query(sql, params)
    return wrapper


def async_execute(sql: str, params: Optional[Tuple] = None):
    """
    Execute an async database operation.

    Example:
        affected = await async_execute(
            "UPDATE students SET status = ? WHERE id = ?",
            ("inactive", 123)
        )
    """
    async def wrapper():
        db = get_async_db()
        return await db.execute(sql, params)
    return wrapper()


async def async_transaction(operations: List[Tuple[str, Optional[Tuple]]]) -> int:
    """
    Execute multiple operations in a single transaction.

    Args:
        operations: List of (sql, params) tuples

    Returns:
        Total affected rows

    Example:
        await async_transaction([
            ("INSERT INTO students (name) VALUES (?)", ("John",)),
            ("INSERT INTO enrollments (student_id) VALUES (?)", (123,)),
        ])
    """
    db = get_async_db()
    total_rows = 0

    async with db.transaction():
        for sql, params in operations:
            rows = await db.execute(sql, params)
            total_rows += rows

    return total_rows


def run_sync_in_thread(func: Callable[..., T]) -> Callable[..., 'asyncio.Future[T]']:
    """
    Decorator to run a synchronous database function in a thread.

    Example:
        @run_sync_in_thread
        def get_student(student_id):
            with get_connection() as conn:
                return conn.execute(
                    "SELECT * FROM students WHERE id = ?",
                    (student_id,)
                ).fetchone()

        # Now can be awaited
        student = await get_student(123)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        executor = get_db_executor()
        return await loop.run_in_executor(
            executor,
            lambda: func(*args, **kwargs)
        )
    return wrapper


class DatabaseQueryBuilder:
    """
    Async query builder for common database operations.

    Example:
        builder = DatabaseQueryBuilder("students")
        results = await builder.where("status", "active").order_by("name").fetch()
    """

    def __init__(self, table: str):
        self.table = table
        self._columns = ["*"]
        self._conditions: List[Tuple[str, Any]] = []
        self._order: Optional[str] = None
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None

    def select(self, *columns: str) -> 'DatabaseQueryBuilder':
        """Select specific columns."""
        self._columns = list(columns) if columns else ["*"]
        return self

    def where(self, column: str, value: Any, op: str = "=") -> 'DatabaseQueryBuilder':
        """Add a WHERE condition."""
        self._conditions.append((f"{column} {op} ?", value))
        return self

    def where_in(self, column: str, values: List[Any]) -> 'DatabaseQueryBuilder':
        """Add a WHERE IN condition."""
        placeholders = ", ".join("?" * len(values))
        self._conditions.append((f"{column} IN ({placeholders})", tuple(values)))
        return self

    def order_by(self, column: str, desc: bool = False) -> 'DatabaseQueryBuilder':
        """Set ORDER BY clause."""
        self._order = f"{column} {'DESC' if desc else 'ASC'}"
        return self

    def limit(self, count: int, offset: int = 0) -> 'DatabaseQueryBuilder':
        """Set LIMIT and OFFSET."""
        self._limit = count
        self._offset = offset
        return self

    def _build_query(self) -> Tuple[str, Tuple]:
        """Build the SQL query."""
        safe_table = validate_table_name(self.table)
        safe_columns = ", ".join(
            validate_identifier(c, "column") if c != "*" else c
            for c in self._columns
        )
        sql = "SELECT " + safe_columns + " FROM [" + safe_table + "]"

        params = []
        if self._conditions:
            conditions = " AND ".join(cond for cond, _ in self._conditions)
            sql += " WHERE " + conditions
            for _, value in self._conditions:
                if isinstance(value, tuple):
                    params.extend(value)
                else:
                    params.append(value)

        if self._order:
            sql += " ORDER BY " + self._order

        if self._limit:
            sql += " LIMIT " + str(int(self._limit))
            if self._offset:
                sql += " OFFSET " + str(int(self._offset))

        return sql, tuple(params)

    async def fetch(self) -> List[Tuple]:
        """Execute the query and fetch all results."""
        sql, params = self._build_query()
        db = get_async_db()
        return await db.query(sql, params)

    async def fetch_one(self) -> Optional[Tuple]:
        """Execute the query and fetch one result."""
        sql, params = self._build_query()
        db = get_async_db()
        return await db.query(sql, params, fetch="one")

    async def fetch_dict(self) -> List[dict]:
        """Execute the query and return results as dictionaries."""
        sql, params = self._build_query()
        db = get_async_db()
        return await db.fetch_dict(sql, params)

    async def count(self) -> int:
        """Get count of matching records."""
        original_columns = self._columns
        self._columns = ["COUNT(*)"]
        sql, params = self._build_query()
        self._columns = original_columns

        db = get_async_db()
        result = await db.query(sql, params, fetch="one")
        return result[0] if result else 0
