"""Certificate generation and management service.

Provides certificate creation, listing, revocation, HTML export, and
external verification for all education subsystems.

Usage::

    svc = CertificateService(db_path)
    cert = svc.generate_certificate("STU001", "completion", "Mathematics", "2025-07-15")
    html = svc.export_certificate_html(cert["id"])
    result = svc.verify_certificate(cert["certificate_number"])
"""

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from string import Template

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

CERTIFICATE_TYPES = ("completion", "achievement", "attendance", "merit", "distinction")

_TYPE_LABELS = {
    "completion": "Certificate of Completion",
    "achievement": "Certificate of Achievement",
    "attendance": "Certificate of Attendance",
    "merit": "Certificate of Merit",
    "distinction": "Certificate of Distinction",
}

# Institution detection (same logic as transcript_service)
_INSTITUTIONS = {
    "primary_school": "Primary School",
    "secondary_school": "Secondary School",
    "sixthform": "Sixth Form College",
    "student_records": "University",
}


def _detect_institution(db_path: str | None) -> str:
    if not db_path:
        return "Education Institution"
    p = str(db_path).lower()
    for key, label in _INSTITUTIONS.items():
        if key in p:
            return label
    return "Education Institution"


def _connect(db_path: str | None):
    path = db_path or ":memory:"
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row[0] > 0


def _get_columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _esc(value) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


class CertificateService:
    """Manages certificates within a single subsystem database."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return _connect(self._db_path)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def generate_certificate(
        self,
        student_id,
        certificate_type: str,
        course_name: str,
        award_date: str,
        grade: str | None = None,
        additional_info: str | None = None,
        issued_by: str | None = None,
    ) -> dict:
        """Create a new certificate record.

        Args:
            student_id: The student/pupil identifier.
            certificate_type: One of ``CERTIFICATE_TYPES``.
            course_name: Name of the course or programme.
            award_date: Date the award is given (YYYY-MM-DD).
            grade: Optional grade or classification.
            additional_info: Optional additional text.
            issued_by: Optional name of the issuer.

        Returns:
            dict with certificate details including ``certificate_number``.
        """
        if certificate_type not in CERTIFICATE_TYPES:
            raise ValueError(
                f"Invalid certificate type '{certificate_type}'. "
                f"Must be one of: {', '.join(CERTIFICATE_TYPES)}"
            )

        certificate_number = f"CERT-{uuid.uuid4().hex[:12].upper()}"
        conn = self._conn()
        try:
            if not _table_exists(conn, "certificates"):
                conn.execute("""CREATE TABLE IF NOT EXISTS certificates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    certificate_number TEXT UNIQUE NOT NULL,
                    certificate_type TEXT NOT NULL,
                    course_name TEXT NOT NULL,
                    award_date TEXT NOT NULL,
                    grade TEXT,
                    additional_info TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    issued_by TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )""")

            cursor = conn.execute(
                """INSERT INTO certificates
                   (student_id, certificate_number, certificate_type,
                    course_name, award_date, grade, additional_info,
                    status, issued_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
                (
                    student_id,
                    certificate_number,
                    certificate_type,
                    course_name,
                    award_date,
                    grade,
                    additional_info,
                    issued_by or "system",
                ),
            )
            conn.commit()
            cert_id = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM certificates WHERE id = ?", (cert_id,)
            ).fetchone()
            logger.info(
                "Certificate %s generated for student %s",
                certificate_number,
                student_id,
            )
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to generate certificate: {e}") from e
        finally:
            conn.close()

    def list_certificates(self, student_id=None) -> list[dict]:
        """List certificates, optionally filtered by student."""
        conn = self._conn()
        try:
            if not _table_exists(conn, "certificates"):
                return []
            sql = "SELECT * FROM certificates"
            params: list = []
            if student_id is not None:
                sql += " WHERE student_id = ?"
                params.append(student_id)
            sql += " ORDER BY created_at DESC"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def revoke_certificate(self, certificate_id, reason: str) -> dict:
        """Revoke a certificate by ID."""
        conn = self._conn()
        try:
            if not _table_exists(conn, "certificates"):
                raise RuntimeError("Certificates table not found.")
            row = conn.execute(
                "SELECT * FROM certificates WHERE id = ?", (certificate_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Certificate {certificate_id} not found.")
            if row["status"] == "revoked":
                raise ValueError(
                    f"Certificate {certificate_id} is already revoked."
                )

            conn.execute(
                """UPDATE certificates
                   SET status = 'revoked',
                       additional_info = COALESCE(additional_info, '') || ?
                   WHERE id = ?""",
                (f"\n[REVOKED: {reason}]", certificate_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM certificates WHERE id = ?", (certificate_id,)
            ).fetchone()
            logger.info("Certificate %d revoked: %s", certificate_id, reason)
            return dict(updated)
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Failed to revoke certificate: {e}") from e
        finally:
            conn.close()

    def verify_certificate(self, certificate_number: str) -> dict:
        """Verify a certificate by its unique certificate number.

        Returns a dict with verification status and certificate details
        (suitable for external verification portals).
        """
        conn = self._conn()
        try:
            if not _table_exists(conn, "certificates"):
                return {
                    "valid": False,
                    "message": "Certificate system not initialised.",
                }
            row = conn.execute(
                "SELECT * FROM certificates WHERE certificate_number = ?",
                (certificate_number,),
            ).fetchone()
            if not row:
                return {
                    "valid": False,
                    "message": "Certificate number not found.",
                }

            cert = dict(row)
            student_name = self._resolve_student_name(conn, cert["student_id"])

            return {
                "valid": cert["status"] == "active",
                "status": cert["status"],
                "certificate_number": cert["certificate_number"],
                "certificate_type": cert["certificate_type"],
                "course_name": cert["course_name"],
                "student_name": student_name,
                "award_date": cert["award_date"],
                "grade": cert.get("grade"),
                "issued_by": cert.get("issued_by"),
                "issued_at": cert.get("created_at"),
                "message": (
                    "Certificate is valid and active."
                    if cert["status"] == "active"
                    else f"Certificate has been {cert['status']}."
                ),
            }
        finally:
            conn.close()

    def export_certificate_html(self, certificate_id) -> str:
        """Render a certificate as a professional HTML document."""
        conn = self._conn()
        try:
            if not _table_exists(conn, "certificates"):
                raise RuntimeError("Certificates table not found.")
            row = conn.execute(
                "SELECT * FROM certificates WHERE id = ?", (certificate_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Certificate {certificate_id} not found.")

            cert = dict(row)
            student_name = self._resolve_student_name(conn, cert["student_id"])
            institution = _detect_institution(self._db_path)

            return self._render_html(cert, student_name, institution)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_student_name(self, conn, student_id) -> str:
        """Look up student name from various table schemas."""
        for table in ("students", "pupils"):
            if not _table_exists(conn, table):
                continue
            cols = _get_columns(conn, table)
            id_col = None
            for candidate in ("student_id", "pupil_id"):
                if candidate in cols:
                    id_col = candidate
                    break

            row = None
            if id_col:
                row = conn.execute(
                    f"SELECT * FROM {table} WHERE {id_col} = ? LIMIT 1",
                    (student_id,),
                ).fetchone()
            if not row:
                try:
                    row = conn.execute(
                        f"SELECT * FROM {table} WHERE id = ? LIMIT 1",
                        (student_id,),
                    ).fetchone()
                except Exception:
                    pass
            if row:
                rk = row.keys()
                if "full_name" in rk and row["full_name"]:
                    return row["full_name"]
                if "name" in rk and row["name"]:
                    return row["name"]
                parts = []
                for fn in ("first_name", "forename"):
                    if fn in rk and row[fn]:
                        parts.append(row[fn])
                        break
                for ln in ("last_name", "surname"):
                    if ln in rk and row[ln]:
                        parts.append(row[ln])
                        break
                if parts:
                    return " ".join(parts)
        return str(student_id)

    def _render_html(self, cert: dict, student_name: str, institution: str) -> str:
        """Render certificate using the HTML template."""
        template_path = _TEMPLATE_DIR / "certificate_template.html"
        tpl_str = template_path.read_text(encoding="utf-8")

        cert_type = cert.get("certificate_type", "completion")
        type_label = _TYPE_LABELS.get(cert_type, "Certificate")

        # Grade section
        grade = cert.get("grade")
        grade_section = ""
        if grade:
            grade_section = (
                f'<div class="grade-text">'
                f'with a grade of <span class="grade-value">{_esc(grade)}</span>'
                f"</div>"
            )

        # Additional info section
        additional = cert.get("additional_info")
        additional_section = ""
        if additional and "[REVOKED:" not in str(additional):
            additional_section = (
                f'<div class="additional-info">{_esc(additional)}</div>'
            )

        # Revoked overlay
        revoked_overlay = ""
        if cert.get("status") == "revoked":
            revoked_overlay = '<div class="status-revoked">REVOKED</div>'

        tpl = Template(tpl_str)
        return tpl.safe_substitute(
            institution=_esc(institution),
            certificate_type_label=_esc(type_label),
            student_name=_esc(student_name),
            course_name=_esc(cert.get("course_name", "")),
            grade_section=grade_section,
            additional_info_section=additional_section,
            award_date=_esc(cert.get("award_date", "")),
            certificate_number=_esc(cert.get("certificate_number", "")),
            issued_at=_esc(cert.get("created_at", "")),
            revoked_overlay=revoked_overlay,
        )
