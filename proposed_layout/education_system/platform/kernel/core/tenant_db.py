"""Tenant database provisioning and connection management.

Responsibilities
----------------
* ``provision_tenant`` — create a tenant's data directory and initialise one
  SQLite database per requested system (college / school / primary / university).
* ``get_tenant_connection`` — return a live ``sqlite3.Connection`` to the
  correct tenant database (with a simple per-slug connection cache).
* ``backup_tenant`` — copy all tenant DBs to a timestamped backup directory.
* ``delete_tenant_data`` — remove a tenant's data directory entirely (admin).

Connection pooling
------------------
A simple dict-based pool is maintained per (tenant_slug, system_key) pair.
Connections are reused until they are explicitly evicted or the process
exits.  The pool is capped at ``MAX_POOL_SIZE`` connections per key; once
the cap is reached the oldest connection is closed before adding the new one.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_SHARED_ROOT = Path(__file__).resolve().parent.parent           # …/shared/
_TENANTS_BASE = (_SHARED_ROOT / "data" / "tenants").resolve()

#: Strict slug pattern: lowercase/uppercase letters, digits, hyphen, underscore.
#: No dots, no path separators, no null bytes, length 1–64.
_SLUG_RE = re.compile(r"\A[A-Za-z0-9_\-]{1,64}\Z")

#: Systems we know how to provision (all five; keys match the canonical
#: SYSTEM_DB_PATHS registry in shared/database/paths.py).
KNOWN_SYSTEMS: tuple[str, ...] = ("nursery", "primary", "secondary", "sixth_form", "university")

#: Maximum cached connections per (slug, system_key) pair.
MAX_POOL_SIZE = 5

# ── Connection pool ───────────────────────────────────────────────────────────

_pool_lock = threading.Lock()
# pool[slug][system_key] = list[sqlite3.Connection]
_pool: dict[str, dict[str, list[sqlite3.Connection]]] = {}


def _pool_get(slug: str, system_key: str) -> sqlite3.Connection | None:
    with _pool_lock:
        conns = _pool.get(slug, {}).get(system_key, [])
        # Return the last added connection (LIFO)
        while conns:
            conn = conns.pop()
            try:
                conn.execute("SELECT 1")
                return conn
            except sqlite3.ProgrammingError:
                pass  # closed — discard and try next
    return None


def _pool_put(slug: str, system_key: str, conn: sqlite3.Connection) -> None:
    with _pool_lock:
        _pool.setdefault(slug, {}).setdefault(system_key, [])
        bucket = _pool[slug][system_key]
        if len(bucket) >= MAX_POOL_SIZE:
            evicted = bucket.pop(0)
            try:
                evicted.close()
            except Exception:
                pass
        bucket.append(conn)


def _pool_evict(slug: str, system_key: str | None = None) -> None:
    """Close and remove all pooled connections for *slug* (optionally scoped to one system)."""
    with _pool_lock:
        if slug not in _pool:
            return
        keys = [system_key] if system_key else list(_pool[slug].keys())
        for key in keys:
            for conn in _pool[slug].pop(key, []):
                try:
                    conn.close()
                except Exception:
                    pass


# ── Internal helpers ──────────────────────────────────────────────────────────

def _validate_slug(slug: str) -> str:
    """Validate a slug to prevent path traversal attacks.

    Only bare alphanumerics, hyphens, and underscores are accepted. Anything
    that could yield a directory separator, parent reference, or null byte is
    rejected before the string ever touches a filesystem API.
    """
    if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug):
        raise ValueError(
            "Invalid slug: must match [A-Za-z0-9_-]{1,64}"
        )
    return slug


def _safe_tenant_path(tenant_slug: str, *slug_parts: str) -> Path:
    """Return an absolute Path under ``_TENANTS_BASE`` for the given slug.

    Each element of ``slug_parts`` must itself match ``_SLUG_RE``; file suffixes
    are appended by the caller via :func:`_db_path_for`, not via this helper.

    Performs three layered defences that CodeQL recognises as sanitisation
    for ``py/path-injection``:

    1. A strict whitelist regex on the slug and on every sub-component.
    2. Resolving the candidate path and requiring it to be *relative to*
       the tenants root (``Path.is_relative_to``).
    3. Rejecting any ``..`` / absolute segment before joining.
    """
    _validate_slug(tenant_slug)
    for part in slug_parts:
        _validate_slug(part)

    # Sanitise each component with os.path.normpath *before* the join so
    # CodeQL can trace the taint removal on the inputs themselves.
    safe_slug = os.path.normpath(tenant_slug)
    safe_parts = tuple(os.path.normpath(p) for p in slug_parts)
    candidate = (_TENANTS_BASE / safe_slug).joinpath(*safe_parts).resolve()
    if not candidate.is_relative_to(_TENANTS_BASE):
        raise ValueError(
            f"Path traversal detected for slug={tenant_slug!r}"
        )
    return candidate


def _tenant_dir(tenant_slug: str) -> Path:
    """Return the absolute directory for *tenant_slug* (validated)."""
    return _safe_tenant_path(tenant_slug)


def _db_path_for(tenant_slug: str, system_key: str) -> str:
    """Return the absolute DB path for *tenant_slug* / *system_key* (validated).

    Both ``tenant_slug`` and ``system_key`` must pass :func:`_validate_slug`;
    the ``.db`` suffix is a static constant so it cannot introduce traversal.
    """
    _validate_slug(system_key)
    safe_key = os.path.normpath(system_key)
    tenant_dir = _safe_tenant_path(tenant_slug)
    db_path = (tenant_dir / f"{safe_key}.db").resolve()
    if not db_path.is_relative_to(_TENANTS_BASE):
        raise ValueError(
            f"Path traversal detected for slug={tenant_slug!r}"
        )
    return str(db_path)


def _open_connection(db_path: str) -> sqlite3.Connection:
    # Defence-in-depth: even though callers use _db_path_for/_safe_tenant_path,
    # re-verify that the DB lives under the tenants root before opening it.
    safe_path = os.path.normpath(db_path)
    resolved = Path(safe_path).resolve()
    if not resolved.is_relative_to(_TENANTS_BASE):
        raise ValueError(
            f"Refusing to open database outside tenants root: {db_path!r}"
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema initialisation per system ─────────────────────────────────────────

def _init_system_schema(conn: sqlite3.Connection, system_key: str) -> None:
    """Run the schema initialiser for a given system against *conn*.

    Each system's ``init_db`` / ``initialise_database`` function is called
    with the database *path* (not the connection) so we pass the path derived
    from the connection's database file.
    """
    try:
        db_path = conn.execute("PRAGMA database_list").fetchone()["file"]
    except Exception:
        db_path = None

    try:
        if system_key == "university":
            from education_system.systems.university.infrastructure.database.database_utils import init_db
            init_db(db_path)
    except Exception as exc:
        logger.warning(
            "Schema init for system=%r tenant db=%r failed (non-fatal): %s",
            system_key, db_path, exc,
        )


# ── Public API ────────────────────────────────────────────────────────────────

class TenantDatabaseManager:
    """Manages per-tenant SQLite databases."""

    # ── Provisioning ─────────────────────────────────────────────────────

    @staticmethod
    def provision_tenant(
        tenant_slug: str,
        systems: list[str] | None = None,
    ) -> dict[str, str]:
        """Create the tenant directory and initialise databases.

        Parameters
        ----------
        tenant_slug:
            The URL-safe slug identifying the tenant.
        systems:
            List of system keys to provision.  Defaults to all known systems.

        Returns
        -------
        dict mapping system_key → absolute db_path for each provisioned system.
        """
        systems = systems or list(KNOWN_SYSTEMS)
        tenant_dir = _tenant_dir(tenant_slug)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Provisioning tenant %r in %s", tenant_slug, tenant_dir)

        result: dict[str, str] = {}
        for system_key in systems:
            db_path = _db_path_for(tenant_slug, system_key)
            try:
                conn = _open_connection(db_path)
                try:
                    _init_system_schema(conn, system_key)
                    conn.commit()
                finally:
                    conn.close()
                result[system_key] = db_path
                logger.info("  Provisioned %s → %s", system_key, db_path)
            except Exception as exc:
                logger.error(
                    "Failed to provision system=%r for tenant=%r: %s",
                    system_key, tenant_slug, exc,
                )

        return result

    # ── Connection access ─────────────────────────────────────────────────

    @staticmethod
    def get_tenant_connection(
        tenant_slug: str,
        system_key: str,
        *,
        use_pool: bool = True,
    ) -> sqlite3.Connection:
        """Return a ``sqlite3.Connection`` for *tenant_slug* / *system_key*.

        Connections are drawn from the pool when *use_pool* is True (default).
        The caller is responsible for returning the connection via
        ``return_connection`` when finished, or closing it directly.

        Raises
        ------
        FileNotFoundError
            If the tenant database file does not exist (tenant not yet
            provisioned).
        """
        db_path = _db_path_for(tenant_slug, system_key)
        if not Path(db_path).exists():
            raise FileNotFoundError(
                f"Tenant DB not found: {db_path!r}. "
                f"Run provision_tenant('{tenant_slug}') first."
            )

        if use_pool:
            conn = _pool_get(tenant_slug, system_key)
            if conn is not None:
                return conn

        return _open_connection(db_path)

    @staticmethod
    def return_connection(
        tenant_slug: str,
        system_key: str,
        conn: sqlite3.Connection,
    ) -> None:
        """Return *conn* to the pool for reuse."""
        _pool_put(tenant_slug, system_key, conn)

    # ── Backup ───────────────────────────────────────────────────────────

    @staticmethod
    def backup_tenant(
        tenant_slug: str,
        backup_base: str | Path | None = None,
    ) -> str:
        """Back up all databases for *tenant_slug* to a timestamped directory.

        Parameters
        ----------
        backup_base:
            Parent directory for backups.  Defaults to
            ``data/tenants/_backups/``.

        Returns
        -------
        Absolute path to the backup directory created.
        """
        # Validate slug before constructing any paths.
        _validate_slug(tenant_slug)
        tenant_dir = _tenant_dir(tenant_slug)

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup_base = Path(backup_base) if backup_base else (_TENANTS_BASE / "_backups")
        backup_dir = backup_base / f"{tenant_slug}_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        if not tenant_dir.exists():
            raise FileNotFoundError(f"Tenant directory not found: {tenant_dir}")

        # Evict pool connections before backup to avoid WAL inconsistency
        _pool_evict(tenant_slug)

        backed_up = 0
        for db_file in tenant_dir.glob("*.db"):
            dest = backup_dir / db_file.name
            try:
                # Use sqlite3 online backup API for consistency
                src_conn = sqlite3.connect(str(db_file))
                dst_conn = sqlite3.connect(str(dest))
                try:
                    src_conn.backup(dst_conn)
                finally:
                    src_conn.close()
                    dst_conn.close()
                backed_up += 1
            except Exception as exc:
                logger.error("Backup of %s failed: %s", db_file, exc)

        logger.info(
            "Backed up %d DBs for tenant=%r to %s", backed_up, tenant_slug, backup_dir
        )
        return str(backup_dir)

    # ── Deletion ─────────────────────────────────────────────────────────

    @staticmethod
    def delete_tenant_data(tenant_slug: str) -> bool:
        """Permanently remove all data for *tenant_slug*.

        **This is irreversible.** Consider calling ``backup_tenant`` first.

        Returns True if the directory was removed, False if it did not exist.
        """
        tenant_dir = _tenant_dir(tenant_slug)
        if not tenant_dir.exists():
            logger.warning("delete_tenant_data: directory not found for %r", tenant_slug)
            return False

        # Evict all pool connections first
        _pool_evict(tenant_slug)

        shutil.rmtree(str(tenant_dir), ignore_errors=False)
        logger.warning("Deleted all data for tenant %r at %s", tenant_slug, tenant_dir)
        return True

    # ── Stats ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_tenant_db_sizes(tenant_slug: str) -> dict[str, int]:
        """Return a dict mapping system_key → file size in bytes."""
        tenant_dir = _tenant_dir(tenant_slug)
        sizes: dict[str, int] = {}
        if not tenant_dir.exists():
            return sizes
        for db_file in tenant_dir.glob("*.db"):
            system_key = db_file.stem
            sizes[system_key] = db_file.stat().st_size
        return sizes
