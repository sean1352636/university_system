"""GDPR Data Subject Request service.

Searches and manages learner data across every education system database
for GDPR compliance: Subject Access Requests, data export, anonymisation,
and data retention reporting.

The system list comes from ``paths.SYSTEM_DB_PATHS``, so a system that
joins the registry is covered here without further change — which matters,
because a system quietly missing from a SAR or an erasure is a compliance
failure rather than a cosmetic gap.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent

from education_system.paths import (
    SYSTEM_DB_PATHS,
    PLATFORM_AUTH_DB,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
    learner_table,
)
from education_system.platform.kernel.database.sql_safety import validate_identifier  # nosec B608

# Two audit-failure handlers below log through this. It was previously
# undefined, so the moment an erasure or transfer audit failed, the except
# block raised NameError over the top of the real error.
logger = logging.getLogger(__name__)


def _default_db_paths():
    return dict(SYSTEM_DB_PATHS)


def _auth_db_path():
    return PLATFORM_AUTH_DB


def _connect(path):
    if not path or not Path(path).exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, table_name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table_name):
    validate_identifier(table_name)
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {r[1] for r in rows}


def _learner_table(system):
    """The table holding ``system``'s learners.

    Was ``"pupils" if system == "primary" else "students"``, which assumed
    every non-primary system uses a ``students`` table. Apprenticeships
    does not — it keeps ``apprentices`` — and under the old rule its
    learners were silently absent from every search, export and erasure
    here, which for a GDPR service is a compliance failure rather than a
    missing feature. The registry now answers this in one place.
    """
    table, _id_col = learner_table(system)
    return table


def _learner_id_col(system, columns):
    """The primary-key column for ``system``'s learner table.

    ``columns`` is what the table actually has, so a database that
    predates a rename still resolves rather than raising.
    """
    _table, id_col = learner_table(system)
    if id_col in columns:
        return id_col
    for fallback in ("student_id", "pupil_id", "apprentice_id", "id"):
        if fallback in columns:
            return fallback
    return "id"


def _name_search_expr(columns):
    """Build a SQL expression for full-name searching."""
    if "full_name" in columns:
        return "full_name"
    if "name" in columns:
        return "name"
    if "first_name" in columns and "last_name" in columns:
        return "(first_name || ' ' || last_name)"
    if "forename" in columns and "surname" in columns:
        return "(forename || ' ' || surname)"
    if "first_name" in columns and "surname" in columns:
        return "(first_name || ' ' || surname)"
    if "forename" in columns and "last_name" in columns:
        return "(forename || ' ' || last_name)"
    return None



class AmbiguousSubjectError(ValueError):
    """An exact name matched more than one distinct person.

    ``candidates`` maps system -> list of ``{rowid, id, name,
    date_of_birth}`` so a caller can re-run with the right student id.
    """

    def __init__(self, message, candidates):
        super().__init__(message)
        self.candidates = candidates


class GDPRService:
    """GDPR compliance service operating across all education system databases."""

    def __init__(self, db_paths=None, auth_db=None):
        self._db_paths = db_paths or _default_db_paths()
        self._auth_db = Path(auth_db) if auth_db else _auth_db_path()

    # ------------------------------------------------------------------
    # Search across all systems
    # ------------------------------------------------------------------

    def search_all_systems(self, name=None, email=None, dob=None):
        """Search all 4 databases for matching student/pupil records.

        Returns a list of dicts: system, student_id, name, email, dob, status.
        """
        results = []
        if not name and not email and not dob:
            return results

        for system, db_path in self._db_paths.items():
            conn = _connect(db_path)
            if not conn:
                continue
            try:
                table = _learner_table(system)
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_expr = _name_search_expr(cols)
                id_col = _learner_id_col(system, cols)

                conditions = []
                params = []
                if name and name_expr:
                    conditions.append(f"{name_expr} LIKE ?")
                    params.append(f"%{name.strip()}%")
                if email and "email" in cols:
                    conditions.append("email LIKE ?")
                    params.append(f"%{email.strip()}%")
                if dob:
                    dob_col = "date_of_birth" if "date_of_birth" in cols else (
                        "dob" if "dob" in cols else None
                    )
                    if dob_col:
                        conditions.append(f"{dob_col} = ?")
                        params.append(dob.strip())

                if not conditions:
                    continue

                where = " OR ".join(conditions)
                select_parts = [f"{id_col}"]
                if name_expr:
                    select_parts.append(f"{name_expr} AS full_name")
                if "email" in cols:
                    select_parts.append("email")
                dob_col = "date_of_birth" if "date_of_birth" in cols else (
                    "dob" if "dob" in cols else None
                )
                if dob_col:
                    select_parts.append(f"{dob_col} AS dob_val")
                if "status" in cols:
                    select_parts.append("status")

                validate_identifier(table)
                sql = f"SELECT {', '.join(select_parts)} FROM {table} WHERE {where} LIMIT 100"
                rows = conn.execute(sql, params).fetchall()

                for r in rows:
                    rk = r.keys()
                    results.append({
                        "system": system,
                        "system_label": SYSTEM_LABELS.get(system, system),
                        "student_id": str(r[id_col]) if id_col in rk else "",
                        "name": r["full_name"] if "full_name" in rk else "",
                        "email": r["email"] if "email" in rk else "",
                        "dob": r["dob_val"] if "dob_val" in rk else "",
                        "status": r["status"] if "status" in rk else "unknown",
                    })
            except Exception:
                pass
            finally:
                conn.close()

        return results

    # ------------------------------------------------------------------
    # Full Data Export
    # ------------------------------------------------------------------

    def get_full_data_export(self, student_name, *, student_ids=None):
        """Collect ALL data about a student from all systems.

        Returns a dict keyed by system, each containing personal_info,
        grades, attendance, transfers, notifications.

        The data subject is matched exactly — never by substring, so a
        request for 'Ann' cannot disclose Joanne's records. In each
        system the learner is found by ``student_ids[system]`` when
        given, otherwise by exact full-name equality. If a name matches
        more than one distinct person in any system the whole request
        is refused with :class:`AmbiguousSubjectError` (its
        ``candidates`` list them per system); re-run with
        ``student_ids={system: id}`` for those systems.
        """
        export = {}
        student_ids = dict(student_ids or {})
        if (not student_name or not student_name.strip()) and not student_ids:
            return export
        ambiguous = {}

        for system, db_path in self._db_paths.items():
            conn = _connect(db_path)
            if not conn:
                continue
            try:
                sys_data = {"personal_info": {}, "grades": [], "attendance": [],
                            "other_records": []}

                table = _learner_table(system)
                if not _table_exists(conn, table):
                    continue
                sid_given = student_ids.get(system)
                if sid_given in (None, "") and not (student_name or "").strip():
                    continue
                try:
                    table, _idc, _cols, matched, _kind = self._resolve_subject(
                        conn, system, student_name, sid_given)
                except AmbiguousSubjectError as amb:
                    ambiguous.update(amb.candidates)
                    continue
                except ValueError:
                    continue  # no name columns / id mismatch: nothing to disclose
                if not matched:
                    continue

                # Personal info — exactly the matched learner row
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE rowid = ?",  # nosec B608 - validated
                    (matched[0]["rowid"],),
                ).fetchone()
                if not row:
                    continue

                sys_data["personal_info"] = dict(row)

                rk = row.keys()
                id_col = _learner_id_col(system, rk)
                sid = row[id_col] if id_col in rk else row["id"] if "id" in rk else None

                # Grades
                for grade_table in ("grades", "assessment", "assessments", "results"):
                    if _table_exists(conn, grade_table):
                        gcols = _get_columns(conn, grade_table)
                        gid_col = None
                        for c in ("student_id", "pupil_id"):
                            if c in gcols:
                                gid_col = c
                                break
                        if gid_col and sid:
                            try:
                                grows = conn.execute(
                                    f"SELECT * FROM {grade_table} WHERE {gid_col} = ? LIMIT 200",
                                    (sid,),
                                ).fetchall()
                                sys_data["grades"].extend([dict(g) for g in grows])
                            except Exception:
                                pass

                # Attendance
                if _table_exists(conn, "attendance"):
                    acols = _get_columns(conn, "attendance")
                    aid_col = None
                    for c in ("student_id", "pupil_id"):
                        if c in acols:
                            aid_col = c
                            break
                    if aid_col and sid:
                        try:
                            arows = conn.execute(
                                f"SELECT * FROM attendance WHERE {aid_col} = ? LIMIT 500",
                                (sid,),
                            ).fetchall()
                            sys_data["attendance"] = [dict(a) for a in arows]
                        except Exception:
                            pass

                export[system] = sys_data
            except Exception:
                pass
            finally:
                conn.close()

        if ambiguous:
            n = sum(len({r["id"] for r in rows}) for rows in ambiguous.values())
            raise AmbiguousSubjectError(
                f"'{student_name}' matches more than one person "
                f"({n} candidates in {', '.join(sorted(ambiguous))}) — "
                "request refused so nobody else's data is disclosed. "
                "Give the student id for those systems.",
                ambiguous)

        # Add cross-system data from auth DB — exact display-name match
        # on one user only; a shared name is withheld, not merged.
        wanted = self._norm_name(student_name)
        auth_conn = _connect(self._auth_db) if wanted else None
        if auth_conn:
            try:
                export["cross_system"] = {"notifications": [], "transfers": []}
                if _table_exists(auth_conn, "cross_system_notifications"):
                    first = wanted.split()[0]
                    users = [u["id"] for u in auth_conn.execute(
                        "SELECT id, display_name FROM users WHERE display_name LIKE ?",
                        (f"%{first}%",)).fetchall()
                        if self._norm_name(u["display_name"]) == wanted]
                    if len(users) == 1:
                        rows = auth_conn.execute(
                            """SELECT * FROM cross_system_notifications
                               WHERE recipient_user_id = ?
                               ORDER BY created_at DESC LIMIT 100""",
                            (users[0],),
                        ).fetchall()
                        export["cross_system"]["notifications"] = [dict(r) for r in rows]
                    elif len(users) > 1:
                        export["cross_system"]["notifications_withheld"] = (
                            f"{len(users)} platform accounts share this name")

                if _table_exists(auth_conn, "cross_system_transfers"):
                    rows = [r for r in auth_conn.execute(
                        """SELECT * FROM cross_system_transfers
                           WHERE student_name LIKE ?
                           ORDER BY rowid DESC LIMIT 200""",
                        (f"%{wanted.split()[0]}%",),
                    ).fetchall()
                        if self._norm_name(r["student_name"]) == wanted][:50]
                    export["cross_system"]["transfers"] = [dict(r) for r in rows]
            except Exception:
                pass
            finally:
                auth_conn.close()

        return export

    # ------------------------------------------------------------------
    # Subject Access Request Report
    # ------------------------------------------------------------------

    def generate_sar_report(self, student_name, *, student_ids=None):
        """Generate a Subject Access Request report as formatted text.

        Exact matching; raises :class:`AmbiguousSubjectError` for a name
        shared by more than one person (see get_full_data_export)."""
        data = self.get_full_data_export(student_name, student_ids=student_ids)
        if not data:
            return f"No data found for '{student_name}' across any system."

        lines = [
            "=" * 70,
            "SUBJECT ACCESS REQUEST (SAR) REPORT",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Data Subject: {student_name}",
            "=" * 70,
            "",
        ]

        # Drive the report off the canonical registry order so every system is
        # included and the keys match what get_full_data_export() collects. The
        # old hardcoded tuple omitted nursery entirely and used "secondary"
        # where the data is keyed "secondary", silently dropping both from the SAR.
        for system in SYSTEM_ORDER:
            if system not in data:
                continue
            sys_data = data[system]
            label = SYSTEM_LABELS.get(system, system)
            lines.append(f"--- {label} ---")
            lines.append("")

            # Personal info
            pi = sys_data.get("personal_info", {})
            if pi:
                lines.append("  Personal Information:")
                for key, val in pi.items():
                    if val is not None and val != "":
                        lines.append(f"    {key}: {val}")
                lines.append("")

            # Grades
            grades = sys_data.get("grades", [])
            if grades:
                lines.append(f"  Academic Records ({len(grades)} entries):")
                for g in grades[:20]:
                    parts = []
                    for k in ("subject", "course", "grade", "score", "mark", "date"):
                        if k in g and g[k] is not None:
                            parts.append(f"{k}={g[k]}")
                    lines.append(f"    {', '.join(parts)}")
                if len(grades) > 20:
                    lines.append(f"    ... and {len(grades) - 20} more records")
                lines.append("")

            # Attendance
            att = sys_data.get("attendance", [])
            if att:
                lines.append(f"  Attendance Records ({len(att)} entries):")
                for a in att[:10]:
                    parts = []
                    for k in ("date", "status", "period", "session"):
                        if k in a and a[k] is not None:
                            parts.append(f"{k}={a[k]}")
                    lines.append(f"    {', '.join(parts)}")
                if len(att) > 10:
                    lines.append(f"    ... and {len(att) - 10} more records")
                lines.append("")

        # Cross-system data
        if "cross_system" in data:
            cs = data["cross_system"]
            notifs = cs.get("notifications", [])
            transfers = cs.get("transfers", [])
            if notifs or transfers:
                lines.append("--- Cross-System Activity ---")
                lines.append("")
                if notifs:
                    lines.append(f"  Notifications ({len(notifs)} entries):")
                    for n in notifs[:10]:
                        lines.append(f"    [{n.get('created_at', '')}] {n.get('title', '')}")
                    lines.append("")
                if transfers:
                    lines.append(f"  Transfers ({len(transfers)} entries):")
                    for t in transfers[:10]:
                        lines.append(f"    {t}")
                    lines.append("")

        lines.append("=" * 70)
        lines.append("END OF SAR REPORT")
        lines.append("=" * 70)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Anonymisation
    # ------------------------------------------------------------------

    @staticmethod
    def _norm_name(value):
        return " ".join(str(value or "").split()).casefold()

    def _match_learner_rows(self, conn, system, student_name, student_id):
        """Rows of ``system``'s learner table that an erasure would touch.

        Matching is exact, never a substring: by the learner id column
        when ``student_id`` is given, otherwise by full-name equality
        (case and surrounding/inner whitespace ignored). Returns
        ``(table, id_col_or_None, cols, rows, match_kind)`` where each row
        is a dict with ``rowid``, ``id``, ``name`` and ``date_of_birth``.
        """
        table = _learner_table(system)
        if not _table_exists(conn, table):
            raise ValueError(f"Table '{table}' not found in {system} database")
        validate_identifier(table)
        cols = _get_columns(conn, table)
        name_expr = _name_search_expr(cols)
        id_col = _learner_id_col(system, cols)
        if id_col not in cols:
            id_col = None
        else:
            validate_identifier(id_col)
        dob_col = next((c for c in ("date_of_birth", "dob") if c in cols), None)
        sel = ["rowid AS _rid",
               f"{id_col} AS _id" if id_col else "rowid AS _id",
               f"{name_expr} AS _name" if name_expr else "NULL AS _name",
               f"{dob_col} AS _dob" if dob_col else "NULL AS _dob"]
        select = f"SELECT {', '.join(sel)} FROM {table}"  # nosec B608 - identifiers validated

        if student_id not in (None, ""):
            if not id_col:
                raise ValueError(
                    f"{system} learner table has no id column; "
                    "match by exact full name instead")
            raw = conn.execute(
                f"{select} WHERE CAST({id_col} AS TEXT) = ?",
                (str(student_id).strip(),)).fetchall()
            match_kind = "id"
            if raw and student_name and str(student_name).strip():
                wanted = self._norm_name(student_name)
                for r in raw:
                    if self._norm_name(r["_name"]) != wanted:
                        raise ValueError(
                            f"{id_col} {student_id} in {system} belongs to "
                            f"{r['_name']!r}, not {student_name!r}")
        else:
            if not name_expr:
                raise ValueError("Cannot determine name columns")
            wanted = self._norm_name(student_name)
            if not wanted:
                raise ValueError("A student name or id is required")
            # Coarse case-insensitive pre-filter, then exact equality in
            # Python so 'Ann' never matches 'Joanne' or 'Hannah'.
            first = wanted.split()[0]
            raw = [r for r in conn.execute(
                       f"{select} WHERE {name_expr} LIKE ?",
                       (f"%{first}%",)).fetchall()
                   if self._norm_name(r["_name"]) == wanted]
            match_kind = "name"
        rows = [{"rowid": r["_rid"], "id": r["_id"], "name": r["_name"],
                 "date_of_birth": r["_dob"]} for r in raw]
        return table, id_col, cols, rows, match_kind

    def _resolve_subject(self, conn, system, student_name, student_id):
        """:meth:`_match_learner_rows`, refusing an ambiguous name.

        Raises :class:`AmbiguousSubjectError` when an exact-name match
        finds more than one distinct person (by learner id).
        """
        table, id_col, cols, rows, kind = self._match_learner_rows(
            conn, system, student_name, student_id)
        people = {r["id"] for r in rows}
        if kind == "name" and len(people) > 1:
            listing = "; ".join(
                f"{id_col or 'rowid'} {r['id']}: {r['name']}"
                + (f" (born {r['date_of_birth']})" if r["date_of_birth"] else "")
                for r in rows)
            raise AmbiguousSubjectError(
                f"'{student_name}' matches {len(people)} different people "
                f"in {system} — refused. Give the student id. "
                f"Candidates: {listing}",
                {system: rows})
        return table, id_col, cols, rows, kind

    def preview_match(self, student_name, system, *, student_id=None):
        """Read-only: exactly which learner rows a rectify / restrict /
        unrestrict / erasure call with these arguments would touch.

        Same dict as :meth:`preview_anonymisation` (``rows``,
        ``ambiguous``, ``id_column`` …); ``columns`` lists the PII
        columns an erasure would redact.
        """
        return self.preview_anonymisation(
            student_name, system, student_id=student_id)

    def _open_system(self, system):
        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")
        conn = _connect(db_path)
        if not conn:
            raise ValueError(f"Database not found for system: {system}")
        return conn

    @staticmethod
    def _pii_updates(cols):
        updates = []
        for col, value in (
            ("first_name", "'REDACTED'"), ("forename", "'REDACTED'"),
            ("last_name", "'REDACTED'"), ("surname", "'REDACTED'"),
            ("full_name", "'REDACTED REDACTED'"),
            ("name", "'REDACTED REDACTED'"),
            ("email", "'redacted@removed.local'"),
            ("date_of_birth", "'1900-01-01'"), ("dob", "'1900-01-01'"),
            ("phone", "'REDACTED'"), ("address", "'REDACTED'"),
            ("postcode", "'REDACTED'"),
        ):
            if col in cols:
                updates.append(f"{col} = {value}")
        return updates

    def preview_anonymisation(self, student_name, system, *, student_id=None):
        """Dry run of :meth:`anonymise_student` — changes nothing.

        Returns ``{"system", "table", "id_column", "match" ("id"|"name"),
        "rows": [{rowid, id, name, date_of_birth}], "ambiguous": bool,
        "columns": [columns that would be redacted]}``. ``ambiguous`` is
        True when an exact-name match found more than one distinct
        person; erasure is refused in that case until an id is given.
        """
        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")
        conn = _connect(db_path)
        if not conn:
            raise ValueError(f"Database not found for system: {system}")
        try:
            table, id_col, cols, rows, kind = self._match_learner_rows(
                conn, system, student_name, student_id)
        finally:
            conn.close()
        people = {r["id"] for r in rows}
        return {
            "system": system, "table": table, "id_column": id_col,
            "match": kind, "rows": rows,
            "ambiguous": kind == "name" and len(people) > 1,
            "columns": [u.split(" = ")[0] for u in self._pii_updates(cols)],
        }

    def anonymise_student(self, student_name, system, *, student_id=None,
                          dry_run=False):
        """Replace PII with anonymised values in the specified system.

        Replaces first_name/forename with 'REDACTED', last_name/surname
        with 'REDACTED', email with 'redacted@removed.local', dob with
        '1900-01-01'.

        Rows are matched exactly: by ``student_id`` (the system's learner
        id column) when given, otherwise by exact full-name equality —
        never by substring. A name that matches more than one distinct
        person is refused (ValueError listing the candidates' ids) so the
        caller can retry with ``student_id``. ``dry_run=True`` changes
        nothing and returns :meth:`preview_anonymisation`'s dict.

        Returns the number of records updated, or raises ValueError on
        failure.
        """
        if dry_run:
            return self.preview_anonymisation(
                student_name, system, student_id=student_id)

        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")

        conn = _connect(db_path)
        if not conn:
            raise ValueError(f"Database not found for system: {system}")

        try:
            table, id_col, cols, rows, kind = self._resolve_subject(
                conn, system, student_name, student_id)

            if not rows:
                who = (f"id {student_id}" if kind == "id"
                       else f"'{student_name}'")
                raise ValueError(f"No records found for {who} in {system}")

            people = {r["id"] for r in rows}

            rowids = [r["rowid"] for r in rows]

            # Build UPDATE with available columns
            updates = self._pii_updates(cols)

            if not updates:
                raise ValueError("No PII columns found to anonymise")

            placeholders = ",".join(["?"] * len(rowids))
            sql = f"UPDATE {table} SET {', '.join(updates)} WHERE rowid IN ({placeholders})"
            conn.execute(sql, rowids)
            conn.commit()

            # A GDPR erasure MUST leave an audit trail (who erased whose data,
            # when, how many records). The redaction has committed, so a failed
            # audit is alerted rather than rolled back — but never silently
            # dropped.
            self._audit_erasure(student_name, system, len(rowids),
                                student_ids=sorted(str(p) for p in people))
            return len(rowids)
        finally:
            conn.close()

    @staticmethod
    def _audit_erasure(student_name: str, system: str, record_count: int,
                       student_ids=None) -> None:
        try:
            from education_system.platform.governance.audit.audit_service import AuditService

            AuditService().log(
                action="gdpr_erasure",
                system_key=system,
                resource_type="student_data",
                details={
                    "student_name": student_name,
                    "records_anonymised": record_count,
                    "student_ids": list(student_ids or []),
                },
                severity="warning",
            )
        except Exception as exc:
            try:
                from education_system.platform.governance.security.fail_closed import (
                    alert_security_failure,
                )
                alert_security_failure(
                    "gdpr.erasure_audit",
                    f"erasure of {student_name!r} in {system} was not audited",
                    severity="high",
                    exc=exc,
                )
            except Exception:
                logger.error("GDPR erasure audit failed and alerting unavailable", exc_info=True)

    # ------------------------------------------------------------------
    # Data Retention Report
    # ------------------------------------------------------------------

    def get_data_retention_report(self, retention_years=None, retention_config=None):
        """List students across systems with data older than the retention threshold.

        Default threshold is 6 years (UK GDPR typical for education).
        Returns a list of dicts: system, student_id, name, oldest_date, age_years.
        """
        # Support per-entity-type retention configuration
        if retention_config is None:
            retention_config = {}
        # Default retention years (configurable per entity type)
        default_years = retention_years if retention_years is not None else int(
            os.environ.get("GDPR_RETENTION_YEARS", "6")
        )
        cutoff = datetime.now() - timedelta(days=default_years * 365)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        results = []

        for system, db_path in self._db_paths.items():
            conn = _connect(db_path)
            if not conn:
                continue
            try:
                table = _learner_table(system)
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_expr = _name_search_expr(cols)
                id_col = _learner_id_col(system, cols)

                # Find a date column to check
                date_col = None
                for candidate in ("created_at", "enrollment_date", "enrolled_date",
                                  "admission_date", "registration_date"):
                    if candidate in cols:
                        date_col = candidate
                        break

                if not date_col or not name_expr:
                    continue

                rows = conn.execute(
                    f"SELECT {id_col}, {name_expr} AS full_name, {date_col} "
                    f"FROM {table} WHERE {date_col} < ? AND {date_col} IS NOT NULL "
                    f"ORDER BY {date_col} LIMIT 200",
                    (cutoff_str,),
                ).fetchall()

                for r in rows:
                    rk = r.keys()
                    oldest = r[date_col] if date_col in rk else ""
                    age_days = 0
                    try:
                        dt = datetime.strptime(str(oldest)[:10], "%Y-%m-%d")
                        age_days = (datetime.now() - dt).days
                    except (ValueError, TypeError):
                        pass

                    results.append({
                        "system": system,
                        "system_label": SYSTEM_LABELS.get(system, system),
                        "student_id": str(r[id_col]) if id_col in rk else "",
                        "name": r["full_name"] if "full_name" in rk else "",
                        "oldest_date": str(oldest)[:10] if oldest else "",
                        "age_years": round(age_days / 365, 1),
                    })
            except Exception:
                pass
            finally:
                conn.close()

        results.sort(key=lambda r: r.get("oldest_date", ""))
        return results

    # ------------------------------------------------------------------
    # Right to Rectification
    # ------------------------------------------------------------------

    def rectify_student_data(self, student_name: str, system: str,
                             field_updates: dict, *, student_id=None,
                             dry_run=False):
        """Update/correct student personal data (Right to Rectification).

        Args:
            student_name: Exact full name of the data subject
            system: System to update in
            field_updates: Dict of {column_name: new_value} to update
            student_id: The learner id — matched exactly; preferred
            dry_run: change nothing, return :meth:`preview_match`'s dict

        Matching is exact (id, else full-name equality — never a
        substring) and an ambiguous name is refused with
        :class:`AmbiguousSubjectError`. Returns the number of records
        updated.
        """
        conn = self._open_system(system)
        try:
            table, _id_col, cols, rows, _kind = self._resolve_subject(
                conn, system, student_name, student_id)

            # Validate field names exist
            safe_updates = {}
            for field, value in field_updates.items():
                validate_identifier(field)
                if field not in cols:
                    raise ValueError(f"Field '{field}' does not exist in {table}")
                safe_updates[field] = value

            if not safe_updates:
                raise ValueError("No valid fields to update")
            if dry_run:
                preview = self.preview_match(
                    student_name, system, student_id=student_id)
                preview["field_updates"] = dict(safe_updates)
                return preview
            if not rows:
                return 0

            # Build parameterised UPDATE
            set_parts = ", ".join(f"{k} = ?" for k in safe_updates)
            rowids = [r["rowid"] for r in rows]
            marks = ",".join("?" for _ in rowids)
            params = list(safe_updates.values()) + rowids
            cursor = conn.execute(
                f"UPDATE {table} SET {set_parts} WHERE rowid IN ({marks})",  # nosec B608 - identifiers validated
                params,
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Right to Restrict Processing
    # ------------------------------------------------------------------

    def restrict_processing(self, student_name: str, system: str, *,
                            student_id=None, dry_run=False):
        """Mark a student's data as restricted (Right to Restrict Processing).

        Sets a 'processing_restricted' flag if the column exists,
        otherwise sets status to 'restricted'. Exact matching and the
        ambiguity rule as :meth:`rectify_student_data`; ``dry_run``
        returns the preview dict without changing anything.

        Returns the number of records updated.
        """
        if dry_run:
            return self.preview_match(student_name, system, student_id=student_id)
        conn = self._open_system(system)
        try:
            table, _id_col, cols, rows, _kind = self._resolve_subject(
                conn, system, student_name, student_id)
            if not rows:
                return 0
            rowids = [r["rowid"] for r in rows]
            marks = ",".join("?" for _ in rowids)

            # Try to add processing_restricted column if it doesn't exist
            if "processing_restricted" not in cols:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN processing_restricted INTEGER DEFAULT 0")
                    conn.commit()
                except Exception:
                    pass  # Column might already exist from concurrent migration

            if "processing_restricted" in _get_columns(conn, table):
                cursor = conn.execute(
                    f"UPDATE {table} SET processing_restricted = 1 WHERE rowid IN ({marks})",  # nosec B608
                    rowids,
                )
            elif "status" in cols:
                cursor = conn.execute(
                    f"UPDATE {table} SET status = 'restricted' WHERE rowid IN ({marks})",  # nosec B608
                    rowids,
                )
            else:
                raise ValueError("Cannot restrict processing: no suitable column")

            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def unrestrict_processing(self, student_name: str, system: str, *,
                              student_id=None, dry_run=False):
        """Remove processing restriction from a student's data (exact
        matching, ambiguity refused; ``dry_run`` previews)."""
        if dry_run:
            return self.preview_match(student_name, system, student_id=student_id)
        conn = self._open_system(system)
        try:
            table, _id_col, cols, rows, _kind = self._resolve_subject(
                conn, system, student_name, student_id)
            if "processing_restricted" in cols and rows:
                rowids = [r["rowid"] for r in rows]
                marks = ",".join("?" for _ in rowids)
                cursor = conn.execute(
                    f"UPDATE {table} SET processing_restricted = 0 WHERE rowid IN ({marks})",  # nosec B608
                    rowids,
                )
                conn.commit()
                return cursor.rowcount
            return 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Right to Data Portability
    # ------------------------------------------------------------------

    def export_portable_data(self, student_name: str, format: str = "json", *,
                             student_ids=None) -> dict | str:
        """Export student data in a standard portable format.

        Supports 'json' and 'csv' formats. Returns structured data
        suitable for transferring to another education provider.
        """
        data = self.get_full_data_export(student_name, student_ids=student_ids)
        if not data:
            raise ValueError(f"No data found for '{student_name}'")

        if format == "csv":
            return self._export_as_csv(data, student_name)

        # JSON portable format
        portable = {
            "export_metadata": {
                "format": "education_system_portable_v1",
                "exported_at": datetime.now().isoformat(),
                "data_subject": student_name,
                "systems_included": list(data.keys()),
            },
            "personal_information": {},
            "academic_records": [],
            "attendance_records": [],
        }

        for system, sys_data in data.items():
            if system == "cross_system":
                continue
            pi = sys_data.get("personal_info", {})
            if pi:
                portable["personal_information"][system] = {
                    k: v for k, v in pi.items()
                    if k not in ("password_hash", "mfa_secret", "totp_secret", "token")
                }
            for g in sys_data.get("grades", []):
                g["_source_system"] = system
                portable["academic_records"].append(g)
            for a in sys_data.get("attendance", []):
                a["_source_system"] = system
                portable["attendance_records"].append(a)

        return portable

    def _export_as_csv(self, data: dict, student_name: str) -> str:
        """Convert export data to CSV format."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Personal info
        writer.writerow(["=== Personal Information ==="])
        for system, sys_data in data.items():
            if system == "cross_system":
                continue
            pi = sys_data.get("personal_info", {})
            if pi:
                writer.writerow([f"System: {system}"])
                for k, v in pi.items():
                    if k not in ("password_hash", "mfa_secret", "totp_secret", "token"):
                        writer.writerow([k, str(v) if v is not None else ""])
                writer.writerow([])

        # Academic records
        writer.writerow(["=== Academic Records ==="])
        all_grades = []
        for system, sys_data in data.items():
            if system != "cross_system":
                for g in sys_data.get("grades", []):
                    g["system"] = system
                    all_grades.append(g)

        if all_grades:
            headers = sorted(set().union(*(g.keys() for g in all_grades)))
            writer.writerow(headers)
            for g in all_grades:
                writer.writerow([str(g.get(h, "")) for h in headers])

        return output.getvalue()

    # ------------------------------------------------------------------
    # Cross-System Transfer Consent
    # ------------------------------------------------------------------

    def check_transfer_consent(self, user_id: int, target_system: str) -> bool:
        """Check if user has consented to cross-system data sharing.

        Returns True if consent is granted for data_sharing_third_party
        or data_sharing_authorities consent types.
        """
        try:
            from education_system.platform.governance.gdpr.consent_service import ConsentService
            svc = ConsentService()
            return (svc.has_consent(user_id, "data_sharing_third_party") or
                    svc.has_consent(user_id, "data_sharing_authorities"))
        except Exception:
            return False

    def transfer_with_consent(self, user_id: int, student_name: str,
                              source_system: str, target_system: str, *,
                              student_id=None) -> dict:
        """Transfer student data between systems with consent verification.

        Raises ValueError if consent has not been granted.
        """
        if not self.check_transfer_consent(user_id, target_system):
            raise ValueError(
                "Data transfer requires consent. Please grant 'data_sharing_third_party' "
                "or 'data_sharing_authorities' consent before transferring data."
            )

        # Get data from source system (exact match; ambiguity refused)
        # Only the source system is read, so a namesake elsewhere cannot
        # block (or leak into) the transfer.
        scoped = GDPRService(
            db_paths={source_system: self._db_paths.get(source_system)},
            auth_db=self._auth_db)
        data = scoped.get_full_data_export(
            student_name,
            student_ids={source_system: student_id} if student_id else None)
        source_data = data.get(source_system, {})

        if not source_data:
            raise ValueError(f"No data found for '{student_name}' in {source_system}")

        # Log the transfer in audit. A consent-gated transfer of personal data
        # that is not recorded is a compliance gap: the audit is mandatory, so
        # if it cannot be written we alert and refuse to report success rather
        # than moving the data silently.
        try:
            from education_system.platform.governance.audit.audit_service import AuditService
            audit = AuditService()
            audit.log(
                action="cross_system_transfer",
                system_key=source_system,
                user_id=user_id,
                resource_type="student_data",
                details={
                    "student_name": student_name,
                    "source_system": source_system,
                    "target_system": target_system,
                    "consent_verified": True,
                },
                severity="info",
            )
        except Exception as exc:
            try:
                from education_system.platform.governance.security.fail_closed import (
                    alert_security_failure,
                )
                alert_security_failure(
                    "gdpr.transfer_audit",
                    f"cross-system transfer audit failed for {student_name!r}",
                    severity="high",
                    exc=exc,
                )
            except Exception:
                logger.error("Cross-system transfer audit failed and alerting unavailable", exc_info=True)
            raise RuntimeError(
                "Cross-system data transfer could not be audited; refusing to complete it."
            ) from exc

        return {
            "transferred": True,
            "source_system": source_system,
            "target_system": target_system,
            "student_name": student_name,
            "data": source_data,
        }
