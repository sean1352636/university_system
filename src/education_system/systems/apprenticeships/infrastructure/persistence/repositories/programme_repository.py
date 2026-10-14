"""Apprenticeship standards, their KSBs and their occupational duties."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.domain.programmes.curriculum import (
    ProgrammeModule,
)
from education_system.systems.apprenticeships.domain.programmes.models import (
    KSB,
    OccupationalDuty,
    Programme,
)
from education_system.systems.apprenticeships.domain.programmes.versions import version_key
from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    QueryBuilder,
    col,
    connect,
    init_db,
    to_float,
    to_int,
)

_FIELDS = (
    "reference", "title", "level", "funding_band", "duration_months",
    "epa_methods", "sector", "description", "status",
    "version", "supersedes_programme_id",
)

_MODULE_FIELDS = (
    "programme_id", "stage", "position", "title", "description", "ksb_codes",
    "planned_hours",
)

# Copied verbatim when a new version is cut. Status, version and the
# supersedes link are set by clone_version, not copied.
_CLONED_FIELDS = (
    "reference", "title", "level", "funding_band", "duration_months",
    "epa_methods", "sector", "description",
)

_KSB_FIELDS = ("programme_id", "code", "ksb_type", "description", "duty_ref")

_DUTY_FIELDS = ("programme_id", "code", "description")


def _split_methods(value: Any) -> list[str]:
    """The stored TEXT column back into the dataclass's list."""
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _write_value(column: str, value: Any) -> Any:
    """Normalise one payload value on its way into the table.

    ``epa_methods`` is a list on the dataclass but a single
    comma-separated column in the table, and callers hand over whichever
    of the two they happen to hold — a form gives a string, the domain
    gives a list.
    """
    if column != "epa_methods":
        return value
    if value is None:
        return None
    parts = value.split(",") if isinstance(value, str) else [str(part) for part in value]
    return ", ".join(part.strip() for part in parts if part.strip())


def _map(row: Any) -> Programme:
    return Programme(
        programme_id=row["programme_id"],
        reference=row["reference"],
        title=row["title"],
        level=to_int(col(row, "level")),
        funding_band=to_int(col(row, "funding_band")),
        duration_months=to_int(col(row, "duration_months")),
        epa_methods=_split_methods(col(row, "epa_methods")),
        sector=col(row, "sector"),
        description=col(row, "description"),
        status=col(row, "status", "Draft"),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
        version=col(row, "version") or "1.0",
        supersedes_programme_id=col(row, "supersedes_programme_id"),
    )


def _map_module(row: Any) -> ProgrammeModule:
    return ProgrammeModule(
        module_id=row["module_id"],
        programme_id=row["programme_id"],
        title=row["title"],
        stage=col(row, "stage", "Year 1"),
        position=to_int(col(row, "position"), 1),
        description=col(row, "description"),
        ksb_codes=col(row, "ksb_codes"),
        planned_hours=to_float(col(row, "planned_hours")),
        created_at=col(row, "created_at", ""),
        updated_at=col(row, "updated_at", ""),
    )


def _map_ksb(row: Any) -> KSB:
    return KSB(
        ksb_id=row["ksb_id"],
        programme_id=row["programme_id"],
        code=row["code"],
        ksb_type=col(row, "ksb_type", "Knowledge"),
        description=col(row, "description", ""),
        duty_ref=col(row, "duty_ref"),
        created_at=col(row, "created_at", ""),
    )


def _map_duty(row: Any) -> OccupationalDuty:
    return OccupationalDuty(
        duty_id=row["duty_id"],
        programme_id=row["programme_id"],
        code=row["code"],
        description=col(row, "description", ""),
        created_at=col(row, "created_at", ""),
    )


# ── Reads ───────────────────────────────────────────────────────────

def get(programme_id: int) -> Programme | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM programmes WHERE programme_id = ?", (programme_id,)
        ).fetchone()
    return _map(row) if row else None


def get_by_reference(reference: str) -> Programme | None:
    """Find a standard by its published reference, such as ``ST0119``.

    Matched case-insensitively: references are stored upper-cased, but
    this must not depend on the caller having normalised the value
    first. Every version of a standard shares its reference, so this
    returns the one to use now: the Active version if there is one,
    otherwise the newest.
    """
    versions = list_versions(reference)
    if not versions:
        return None
    active = [p for p in versions if p.status == "Active"]
    return (active or versions)[-1]


def get_by_reference_and_version(reference: str, version: str) -> Programme | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM programmes WHERE UPPER(reference) = UPPER(?) AND version = ?",
            (reference, version),
        ).fetchone()
    return _map(row) if row else None


def list_versions(reference: str) -> list[Programme]:
    """Every version of one standard, oldest first (1.9 before 1.10)."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM programmes WHERE UPPER(reference) = UPPER(?)", (reference,)
        ).fetchall()
    return sorted((_map(r) for r in rows), key=lambda p: (version_key(p.version), p.programme_id))


def list_all(
    *,
    status: str | None = None,
    statuses: list[str] | tuple[str, ...] | None = None,
    level: int | None = None,
    search: str | None = None,
    active_only: bool = False,
) -> list[Programme]:
    """The standards catalogue, filtered as the list screen asks."""
    init_db()
    qb = QueryBuilder()
    qb.add_if(status, "status = ?", status)
    qb.add_in("status", list(statuses) if statuses else None)
    qb.add_if(level, "level = ?", level)
    if active_only:
        qb.add("status = 'Active'")
    if search and search.strip():
        term = f"%{search.strip()}%"
        qb.add("(reference LIKE ? OR title LIKE ? OR sector LIKE ?)", term, term, term)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM programmes {qb.where} ORDER BY level, title, reference", qb.args
        ).fetchall()
    return sorted(
        (_map(r) for r in rows),
        key=lambda p: (p.level, p.title, p.reference, version_key(p.version)),
    )


def count_apprentices(programme_id: int) -> int:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM apprentices WHERE programme_id = ?", (programme_id,)
        ).fetchone()
    return to_int(row["n"]) if row else 0


# ── Writes ──────────────────────────────────────────────────────────

def create(payload: dict[str, Any]) -> int:
    """Insert a programme and return the new id."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [_write_value(c, payload[c]) for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO programmes ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update(programme_id: int, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [_write_value(c, payload[c]) for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE programmes SET {assignments}, updated_at = datetime('now') "
            "WHERE programme_id = ?",
            [*values, programme_id],
        )


def delete(programme_id: int) -> None:
    """Remove a standard along with its KSBs and duties.

    Apprentices are not cascaded away — they keep their record with a
    null programme — so a standard that anyone is enrolled on should be
    withdrawn rather than deleted. Check ``count_apprentices`` first.
    """
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM programmes WHERE programme_id = ?", (programme_id,))


# ── KSBs ────────────────────────────────────────────────────────────

def list_ksbs(programme_id: int, *, ksb_type: str | None = None) -> list[KSB]:
    """The standard's KSBs in code order.

    Ordered in Python on ``KSB.sort_key`` because SQL sorts the codes as
    strings, which puts K10 ahead of K2 — a mapping grid in that order
    reads as a bug.
    """
    init_db()
    qb = QueryBuilder()
    qb.add("programme_id = ?", programme_id)
    qb.add_if(ksb_type, "ksb_type = ?", ksb_type)
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM programme_ksbs {qb.where}", qb.args).fetchall()
    return sorted((_map_ksb(r) for r in rows), key=lambda ksb: ksb.sort_key)


def get_ksb(ksb_id: int) -> KSB | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM programme_ksbs WHERE ksb_id = ?", (ksb_id,)
        ).fetchone()
    return _map_ksb(row) if row else None


def create_ksb(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _KSB_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO programme_ksbs ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_ksb(ksb_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _KSB_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE programme_ksbs SET {assignments} WHERE ksb_id = ?",
            [*values, ksb_id],
        )


def delete_ksb(ksb_id: int) -> None:
    """Remove a KSB and every piece of evidence mapped to it.

    The mapping rows cascade; the evidence itself survives, having simply
    lost one of the things it covered.
    """
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM programme_ksbs WHERE ksb_id = ?", (ksb_id,))


def count_ksbs(programme_id: int) -> int:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM programme_ksbs WHERE programme_id = ?", (programme_id,)
        ).fetchone()
    return to_int(row["n"]) if row else 0


# ── Occupational duties ─────────────────────────────────────────────

def get_duty(duty_id: int) -> OccupationalDuty | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM occupational_duties WHERE duty_id = ?", (duty_id,)
        ).fetchone()
    return _map_duty(row) if row else None


def list_duties(programme_id: int) -> list[OccupationalDuty]:
    """The standard's duties in code order.

    ``LENGTH(code)`` first so D2 precedes D10; the codes share a single
    letter prefix, so length stands in for the numeric part.
    """
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM occupational_duties WHERE programme_id = ? "
            "ORDER BY LENGTH(code), code",
            (programme_id,),
        ).fetchall()
    return [_map_duty(r) for r in rows]


def create_duty(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _DUTY_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO occupational_duties ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
        return int(cur.lastrowid)


def update_duty(duty_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _DUTY_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    values = [payload[c] for c in columns]
    with connect() as conn:
        conn.execute(
            f"UPDATE occupational_duties SET {assignments} WHERE duty_id = ?",
            [*values, duty_id],
        )


def delete_duty(duty_id: int) -> None:
    """Remove a duty. KSBs referencing it by ``duty_ref`` keep the text."""
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM occupational_duties WHERE duty_id = ?", (duty_id,))


# ── Curriculum modules ──────────────────────────────────────────────

def list_modules(programme_id: int) -> list[ProgrammeModule]:
    """A standard's modules in stored order; see curriculum.ordered for delivery order."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM programme_modules WHERE programme_id = ? "
            "ORDER BY position, module_id",
            (programme_id,),
        ).fetchall()
    return [_map_module(r) for r in rows]


def get_module(module_id: int) -> ProgrammeModule | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM programme_modules WHERE module_id = ?", (module_id,)
        ).fetchone()
    return _map_module(row) if row else None


def create_module(payload: dict[str, Any]) -> int:
    init_db()
    columns = [f for f in _MODULE_FIELDS if f in payload]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        cur = conn.execute(
            f"INSERT INTO programme_modules ({', '.join(columns)}) VALUES ({placeholders})",
            [payload[c] for c in columns],
        )
        return int(cur.lastrowid)


def update_module(module_id: int, payload: dict[str, Any]) -> None:
    init_db()
    columns = [f for f in _MODULE_FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE programme_modules SET {assignments}, updated_at = datetime('now') "
            "WHERE module_id = ?",
            [*(payload[c] for c in columns), module_id],
        )


def delete_module(module_id: int) -> None:
    """Remove a module. Objectives already applied from it stay on the plans."""
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM programme_modules WHERE module_id = ?", (module_id,))


# ── Curriculum applied to apprentices ───────────────────────────────

def applied_module_ids(apprentice_id: int) -> set[int]:
    """Modules already applied to this apprentice's learning plan."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT module_id FROM curriculum_applications WHERE apprentice_id = ?",
            (apprentice_id,),
        ).fetchall()
    return {int(r["module_id"]) for r in rows}


def record_application(
    *,
    apprentice_id: int,
    module_id: int,
    objective_id: int | None,
    item_id: int | None,
    applied_by: str,
) -> None:
    """Note that a module is on an apprentice's plan. A repeat is ignored."""
    init_db()
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO curriculum_applications
                   (apprentice_id, module_id, objective_id, item_id, applied_by)
               VALUES (?, ?, ?, ?, ?)""",
            (apprentice_id, module_id, objective_id, item_id, applied_by),
        )


# ── Versions ────────────────────────────────────────────────────────

def clone_version(source_id: int, *, version: str, status: str) -> int:
    """Cut a new version of a standard, and supersede the old one.

    One transaction: the new row, its KSBs, duties and curriculum
    modules, and the old row's move to 'Superseded' all land together
    or not at all — a half-made version would leave a standard with no
    KSBs, or two live versions.
    """
    init_db()
    fields = ", ".join(_CLONED_FIELDS)
    with connect() as conn:
        cur = conn.execute(
            f"""INSERT INTO programmes ({fields}, status, version, supersedes_programme_id)
                SELECT {fields}, ?, ?, programme_id FROM programmes
                 WHERE programme_id = ?""",  # noqa: S608 - fixed column list
            (status, version, source_id),
        )
        new_id = int(cur.lastrowid)
        conn.execute(
            """INSERT INTO programme_ksbs (programme_id, code, ksb_type, description, duty_ref)
               SELECT ?, code, ksb_type, description, duty_ref
                 FROM programme_ksbs WHERE programme_id = ?""",
            (new_id, source_id),
        )
        conn.execute(
            """INSERT INTO occupational_duties (programme_id, code, description)
               SELECT ?, code, description FROM occupational_duties WHERE programme_id = ?""",
            (new_id, source_id),
        )
        conn.execute(
            """INSERT INTO programme_modules
                   (programme_id, stage, position, title, description, ksb_codes,
                    planned_hours)
               SELECT ?, stage, position, title, description, ksb_codes, planned_hours
                 FROM programme_modules WHERE programme_id = ?""",
            (new_id, source_id),
        )
        conn.execute(
            "UPDATE programmes SET status = 'Superseded', updated_at = datetime('now') "
            "WHERE programme_id = ?",
            (source_id,),
        )
        return new_id
