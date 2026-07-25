"""GDPR Data Subject Request service.

Searches and manages student/pupil data across all 4 education system
databases for GDPR compliance: Subject Access Requests, data export,
anonymisation, and data retention reporting.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent

from education_system.platform.kernel.database.paths import SYSTEM_DB_PATHS, AUTH_DB, SYSTEM_LABELS, SYSTEM_ORDER
from education_system.platform.kernel.database.sql_safety import validate_identifier  # nosec B608


def _default_db_paths():
    return dict(SYSTEM_DB_PATHS)


def _auth_db_path():
    return AUTH_DB


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
                table = "pupils" if system == "primary" else "students"
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_expr = _name_search_expr(cols)
                id_col = "pupil_id" if system == "primary" and "pupil_id" in cols else (
                    "student_id" if "student_id" in cols else "id"
                )

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

    def get_full_data_export(self, student_name):
        """Collect ALL data about a student from all systems.

        Returns a dict keyed by system, each containing personal_info,
        grades, attendance, transfers, notifications.
        """
        export = {}
        if not student_name or not student_name.strip():
            return export

        for system, db_path in self._db_paths.items():
            conn = _connect(db_path)
            if not conn:
                continue
            try:
                sys_data = {"personal_info": {}, "grades": [], "attendance": [],
                            "other_records": []}

                table = "pupils" if system == "primary" else "students"
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_expr = _name_search_expr(cols)
                if not name_expr:
                    continue

                # Personal info
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE {name_expr} LIKE ? LIMIT 1",
                    (f"%{student_name.strip()}%",),
                ).fetchone()
                if not row:
                    continue

                sys_data["personal_info"] = dict(row)

                rk = row.keys()
                id_col = "pupil_id" if system == "primary" and "pupil_id" in rk else (
                    "student_id" if "student_id" in rk else "id"
                )
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

        # Add cross-system data from auth DB
        auth_conn = _connect(self._auth_db)
        if auth_conn:
            try:
                export["cross_system"] = {"notifications": [], "transfers": []}
                if _table_exists(auth_conn, "cross_system_notifications"):
                    rows = auth_conn.execute(
                        """SELECT n.* FROM cross_system_notifications n
                           JOIN users u ON u.id = n.recipient_user_id
                           WHERE u.display_name LIKE ?
                           ORDER BY n.created_at DESC LIMIT 100""",
                        (f"%{student_name.strip()}%",),
                    ).fetchall()
                    export["cross_system"]["notifications"] = [dict(r) for r in rows]

                if _table_exists(auth_conn, "cross_system_transfers"):
                    rows = auth_conn.execute(
                        """SELECT * FROM cross_system_transfers
                           WHERE student_name LIKE ?
                           ORDER BY rowid DESC LIMIT 50""",
                        (f"%{student_name.strip()}%",),
                    ).fetchall()
                    export["cross_system"]["transfers"] = [dict(r) for r in rows]
            except Exception:
                pass
            finally:
                auth_conn.close()

        return export

    # ------------------------------------------------------------------
    # Subject Access Request Report
    # ------------------------------------------------------------------

    def generate_sar_report(self, student_name):
        """Generate a Subject Access Request report as formatted text."""
        data = self.get_full_data_export(student_name)
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

    def anonymise_student(self, student_name, system):
        """Replace PII with anonymised values in the specified system.

        Replaces first_name/forename with 'REDACTED', last_name/surname
        with 'REDACTED', email with 'redacted@removed.local', dob with
        '1900-01-01'.

        Returns the number of records updated, or raises ValueError on
        failure.
        """
        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")

        conn = _connect(db_path)
        if not conn:
            raise ValueError(f"Database not found for system: {system}")

        try:
            table = "pupils" if system == "primary" else "students"
            if not _table_exists(conn, table):
                raise ValueError(f"Table '{table}' not found in {system} database")

            cols = _get_columns(conn, table)
            name_expr = _name_search_expr(cols)
            if not name_expr:
                raise ValueError("Cannot determine name columns")

            # Find matching records
            rows = conn.execute(
                f"SELECT rowid FROM {table} WHERE {name_expr} LIKE ?",
                (f"%{student_name.strip()}%",),
            ).fetchall()

            if not rows:
                raise ValueError(f"No records found for '{student_name}' in {system}")

            rowids = [r[0] for r in rows]

            # Build UPDATE with available columns
            updates = []
            if "first_name" in cols:
                updates.append("first_name = 'REDACTED'")
            if "forename" in cols:
                updates.append("forename = 'REDACTED'")
            if "last_name" in cols:
                updates.append("last_name = 'REDACTED'")
            if "surname" in cols:
                updates.append("surname = 'REDACTED'")
            if "full_name" in cols:
                updates.append("full_name = 'REDACTED REDACTED'")
            if "name" in cols:
                updates.append("name = 'REDACTED REDACTED'")
            if "email" in cols:
                updates.append("email = 'redacted@removed.local'")
            if "date_of_birth" in cols:
                updates.append("date_of_birth = '1900-01-01'")
            if "dob" in cols:
                updates.append("dob = '1900-01-01'")
            if "phone" in cols:
                updates.append("phone = 'REDACTED'")
            if "address" in cols:
                updates.append("address = 'REDACTED'")
            if "postcode" in cols:
                updates.append("postcode = 'REDACTED'")

            if not updates:
                raise ValueError("No PII columns found to anonymise")

            placeholders = ",".join(["?"] * len(rowids))
            sql = f"UPDATE {table} SET {', '.join(updates)} WHERE rowid IN ({placeholders})"
            conn.execute(sql, rowids)
            conn.commit()
            return len(rowids)
        finally:
            conn.close()

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
                table = "pupils" if system == "primary" else "students"
                if not _table_exists(conn, table):
                    continue
                cols = _get_columns(conn, table)
                name_expr = _name_search_expr(cols)
                id_col = "pupil_id" if system == "primary" and "pupil_id" in cols else (
                    "student_id" if "student_id" in cols else "id"
                )

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

    def rectify_student_data(self, student_name: str, system: str, field_updates: dict) -> int:
        """Update/correct student personal data (Right to Rectification).

        Args:
            student_name: Name to search for
            system: System to update in
            field_updates: Dict of {column_name: new_value} to update

        Returns the number of records updated.
        """
        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")

        conn = _connect(db_path)
        if not conn:
            raise ValueError(f"Database not found for system: {system}")

        try:
            table = "pupils" if system == "primary" else "students"
            if not _table_exists(conn, table):
                raise ValueError(f"Table '{table}' not found in {system}")

            cols = _get_columns(conn, table)
            name_expr = _name_search_expr(cols)
            if not name_expr:
                raise ValueError("Cannot determine name columns")

            # Validate field names exist
            safe_updates = {}
            for field, value in field_updates.items():
                validate_identifier(field)
                if field not in cols:
                    raise ValueError(f"Field '{field}' does not exist in {table}")
                safe_updates[field] = value

            if not safe_updates:
                raise ValueError("No valid fields to update")

            # Build parameterised UPDATE
            set_parts = ", ".join(f"{k} = ?" for k in safe_updates)
            params = list(safe_updates.values()) + [f"%{student_name.strip()}%"]

            validate_identifier(table)
            cursor = conn.execute(
                f"UPDATE {table} SET {set_parts} WHERE {name_expr} LIKE ?",
                params,
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Right to Restrict Processing
    # ------------------------------------------------------------------

    def restrict_processing(self, student_name: str, system: str) -> int:
        """Mark a student's data as restricted (Right to Restrict Processing).

        Sets a 'processing_restricted' flag if the column exists,
        otherwise sets status to 'restricted'.

        Returns the number of records updated.
        """
        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")

        conn = _connect(db_path)
        if not conn:
            raise ValueError(f"Database not found for system: {system}")

        try:
            table = "pupils" if system == "primary" else "students"
            if not _table_exists(conn, table):
                raise ValueError(f"Table '{table}' not found in {system}")

            cols = _get_columns(conn, table)
            name_expr = _name_search_expr(cols)
            if not name_expr:
                raise ValueError("Cannot determine name columns")

            # Try to add processing_restricted column if it doesn't exist
            if "processing_restricted" not in cols:
                try:
                    validate_identifier(table)
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN processing_restricted INTEGER DEFAULT 0")
                    conn.commit()
                except Exception:
                    pass  # Column might already exist from concurrent migration

            if "processing_restricted" in _get_columns(conn, table):
                cursor = conn.execute(
                    f"UPDATE {table} SET processing_restricted = 1 WHERE {name_expr} LIKE ?",
                    (f"%{student_name.strip()}%",),
                )
            elif "status" in cols:
                cursor = conn.execute(
                    f"UPDATE {table} SET status = 'restricted' WHERE {name_expr} LIKE ?",
                    (f"%{student_name.strip()}%",),
                )
            else:
                raise ValueError("Cannot restrict processing: no suitable column")

            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def unrestrict_processing(self, student_name: str, system: str) -> int:
        """Remove processing restriction from a student's data."""
        db_path = self._db_paths.get(system)
        if not db_path:
            raise ValueError(f"Unknown system: {system}")

        conn = _connect(db_path)
        if not conn:
            raise ValueError(f"Database not found for system: {system}")

        try:
            table = "pupils" if system == "primary" else "students"
            cols = _get_columns(conn, table)
            name_expr = _name_search_expr(cols)
            if not name_expr:
                raise ValueError("Cannot determine name columns")

            if "processing_restricted" in cols:
                cursor = conn.execute(
                    f"UPDATE {table} SET processing_restricted = 0 WHERE {name_expr} LIKE ?",
                    (f"%{student_name.strip()}%",),
                )
                conn.commit()
                return cursor.rowcount
            return 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Right to Data Portability
    # ------------------------------------------------------------------

    def export_portable_data(self, student_name: str, format: str = "json") -> dict | str:
        """Export student data in a standard portable format.

        Supports 'json' and 'csv' formats. Returns structured data
        suitable for transferring to another education provider.
        """
        data = self.get_full_data_export(student_name)
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
                              source_system: str, target_system: str) -> dict:
        """Transfer student data between systems with consent verification.

        Raises ValueError if consent has not been granted.
        """
        if not self.check_transfer_consent(user_id, target_system):
            raise ValueError(
                "Data transfer requires consent. Please grant 'data_sharing_third_party' "
                "or 'data_sharing_authorities' consent before transferring data."
            )

        # Get data from source system
        data = self.get_full_data_export(student_name)
        source_data = data.get(source_system, {})

        if not source_data:
            raise ValueError(f"No data found for '{student_name}' in {source_system}")

        # Log the transfer in audit
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
        except Exception:
            pass

        return {
            "transferred": True,
            "source_system": source_system,
            "target_system": target_system,
            "student_name": student_name,
            "data": source_data,
        }
