"""Speed-ups shared by every Secondary School test (nothing here changes
what a test checks).

Most tests build a fresh database (``database.use_database(tmp_path / ...)``)
and several logins. Two set-up costs dominated the run:

* **The schema.** Every new database file ran every registered module's
  ``CREATE ...`` script (~0.65 s a test). Here it is built once per test
  process into a template and copied into each new, empty file with
  SQLite's backup API (a few ms). A file that already has tables, or a
  schema list that has changed since the template was built, goes the
  normal way, so the result is always the same schema.
* **Password hashing.** Logins made in tests (teachers, pupil and parent
  portal accounts) were hashed with production bcrypt cost (~0.25 s each).
  Tests use bcrypt's minimum cost instead; hashing and checking still work
  exactly the same way.
* **Disk syncs.** Every commit waited for the disk (``synchronous=FULL``,
  ~14 ms each, a dozen per pupil + parent). Test databases are throw-away
  temp files, so their connections skip the sync (``synchronous=OFF``);
  what is written and read back is unchanged.
* **Connections.** ``database.connect()`` opens and closes a connection
  for every call (~100 a test). Each open re-reads the whole schema and each
  close of the last connection checkpoints the WAL file. Here a closed
  connection is kept, idle, and handed out again for the same file on the
  same thread. Each ``connect()`` block is still its own transaction
  (committed or rolled back before the connection is handed back), and a
  ``connect()`` inside another one still gets a separate connection, as
  in the app.
* **The login database.** ``initialise_auth_db`` (tables + column
  migrations, ~0.15 s) is run once into a template; a test's new, empty
  auth file gets a copy. An existing file goes the normal way.
"""

from __future__ import annotations

# Import every rules module now (core/ and each module's domain/), so every
# schema is registered before the first template is built (a module imported
# later by a test would otherwise force a rebuild in each test process).
import importlib  # noqa: E402
import pkgutil  # noqa: E402
import sqlite3
import tempfile
import threading
from pathlib import Path

import bcrypt
import pytest

from education_system.platform.identity.auth import schema as auth_schema
from education_system.systems.secondary import core as _core
from education_system.systems.secondary import modules as _modules
from education_system.systems.secondary.infrastructure.database import connection as database

for _m in pkgutil.walk_packages(_core.__path__, f"{_core.__name__}."):
    if not _m.ispkg:
        importlib.import_module(_m.name)
for _m in pkgutil.walk_packages(_modules.__path__, f"{_modules.__name__}."):
    if ".domain." in f"{_m.name}." and not _m.ispkg:
        importlib.import_module(_m.name)

_real_ensure = database._ensure_schema
_real_gensalt = bcrypt.gensalt
_real_init_auth = auth_schema.initialise_auth_db
_template: dict[str, object] = {"names": None, "path": None}
_auth_template: list[Path] = []


def _template_for(names: tuple[str, ...]) -> Path:
    """A database file holding exactly the schemas in *names* (rebuilt only
    when a module registers another schema)."""
    if _template["names"] != names:
        path = Path(tempfile.mkdtemp(prefix="secondary-schema-")) / "template.db"
        conn = sqlite3.connect(path)
        try:
            # A scratch file: no journal, no disk syncs per CREATE.
            conn.execute("PRAGMA journal_mode = OFF")
            conn.execute("PRAGMA synchronous = OFF")
            for _name, ddl in list(database._schemas):
                conn.executescript(ddl)
            conn.commit()
        finally:
            conn.close()
        _template.update(names=names, path=path)
    return _template["path"]  # type: ignore[return-value]


def _fast_ensure(conn: sqlite3.Connection, path: Path) -> None:
    if path in database._initialised:
        return
    names = tuple(name for name, _ddl in database._schemas)
    empty = conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0
    if not empty or not names:
        _real_ensure(conn, path)
        return
    with database._lock:
        if path in database._initialised:
            return
        src = sqlite3.connect(_template_for(names))
        try:
            src.backup(conn)
        finally:
            src.close()
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        database._initialised.add(path)


class _Pooled(sqlite3.Connection):
    """A connection whose close() hands it back to the pool instead."""

    pool_key: tuple | None = None

    def close(self) -> None:
        key = self.pool_key
        if key is None or key in _idle:
            super().close()
            return
        if self.in_transaction:
            self.rollback()
        self.row_factory = sqlite3.Row
        _idle[key] = self


_idle: dict[tuple, _Pooled] = {}


def _fast_open(path: Path) -> sqlite3.Connection:
    key = (str(path), threading.get_ident())
    conn = _idle.pop(key, None)
    if conn is not None and Path(path).exists():
        return conn
    if conn is not None:  # the file went away: start again
        conn.pool_key = None
        conn.close()
    # Same settings as database._open, plus no disk syncs.
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, factory=_Pooled)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA synchronous = OFF")
    conn.pool_key = key
    return conn


def _close_pool() -> None:
    while _idle:
        _key, conn = _idle.popitem()
        conn.pool_key = None
        conn.close()


def _fast_init_auth(db_path: str | None = None):
    if db_path is None or (Path(db_path).exists() and Path(db_path).stat().st_size):
        return _real_init_auth(db_path)
    if not _auth_template:
        path = Path(tempfile.mkdtemp(prefix="secondary-auth-")) / "auth.db"
        _real_init_auth(str(path))
        _auth_template.append(path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    src, dst = sqlite3.connect(_auth_template[0]), sqlite3.connect(db_path)
    try:
        src.backup(dst)
        dst.execute("PRAGMA journal_mode = WAL")
        dst.commit()
    finally:
        src.close()
        dst.close()


@pytest.fixture(autouse=True)
def _fast_setup(monkeypatch):
    monkeypatch.setattr(database, "_ensure_schema", _fast_ensure)
    monkeypatch.setattr(database, "_open", _fast_open)
    monkeypatch.setattr(auth_schema, "initialise_auth_db", _fast_init_auth)
    monkeypatch.setattr(bcrypt, "gensalt",
                        lambda rounds=4, prefix=b"2b": _real_gensalt(4, prefix))
    yield
    _close_pool()
