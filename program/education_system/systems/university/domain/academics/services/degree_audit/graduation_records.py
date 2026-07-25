"""
Graduation Records & Artefacts

Sits next to ``graduation_ceremony.py`` and ``GraduationAuditManager`` and
covers the post-conferral artefact workflow:

* PrintQueueManager      — parchment / certificate print queue, links rows in
                           the shared ``certificates`` table via
                           ``CertificateService.generate_certificate``.
* DigitalDiplomaManager  — issues a row in ``blockchain_credentials`` (the
                           same table used by the legacy CLI helper) so the
                           credential is verifiable on the existing portal.
* TranscriptFreezeManager — captures an immutable snapshot of a student's
                           transcript HTML + SHA-256 hash at conferral, and
                           hands out one-time access tokens for employers.
* AlumniProvisioner      — creates an ``alumni`` row at conferral and copies
                           the student's identity / cohort info across.

All managers are best-effort on email and external-system writes — a remote
failure logs and returns ``False`` rather than rolling back the local row.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import (
    get_connection, transaction,
)

logger = logging.getLogger("graduation_records")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lookup_student(conn, student_id: str) -> Dict[str, str]:
    """Fetch a compact student dict for downstream wiring."""
    try:
        row = conn.execute(
            "SELECT student_id, "
            "       COALESCE(first_name,'')   AS first_name, "
            "       COALESCE(middle_name,'')  AS middle_name, "
            "       COALESCE(last_name,'')    AS last_name, "
            "       COALESCE(email_address,'') AS email, "
            "       COALESCE(course,'')        AS course, "
            "       COALESCE(gender,'')        AS gender, "
            "       COALESCE(dob,'')           AS dob"
            "  FROM students WHERE student_id = ?",
            (student_id,),
        ).fetchone()
    except sqlite3.Error:
        logger.exception("student lookup failed sid=%s", student_id)
        return {}
    if not row:
        return {}
    d = dict(row)
    parts = [d['first_name'], d['middle_name'], d['last_name']]
    d['full_name'] = ' '.join(p for p in parts if p).strip() or student_id
    return d


# ---------------------------------------------------------------------------
# PrintQueueManager
# ---------------------------------------------------------------------------

class PrintQueueManager:
    """Queue parchments for the printer.

    For each (ceremony, student) pair we create:
      1. A row in the shared ``certificates`` table via ``CertificateService``
         so the certificate has a verifiable number.
      2. A row in ``graduation_print_queue`` that tracks the physical print
         job (queued → printing → printed → dispatched).
    """

    QUEUE_STATUSES = ('queued', 'printing', 'printed', 'dispatched', 'failed')

    @staticmethod
    def enqueue(ceremony_id: int, student_id: str,
                course_name: str = "",
                grade: str = "",
                issued_by: str = "Office of the Registrar") -> Dict[str, Any]:
        """Generate the certificate record and add it to the print queue.

        Returns the queue row (including ``certificate_number``)."""
        from education_system.platform.features.certificates.certificate_service import (
            CertificateService,
        )
        with get_connection() as conn:
            ceremony = conn.execute(
                "SELECT ceremony_date FROM graduation_ceremonies WHERE ceremony_id = ?",
                (ceremony_id,),
            ).fetchone()
            stud = _lookup_student(conn, student_id)
        if not ceremony:
            raise ValueError(f"ceremony {ceremony_id} not found")
        award_date = ceremony['ceremony_date']
        if not course_name:
            course_name = stud.get('course') or "Undergraduate Award"

        # CertificateService restricts certificate_type to its built-in list;
        # graduation parchments map to 'completion' (the closest semantic
        # match — the parchment is awarded on course completion).
        cert = CertificateService().generate_certificate(
            student_id=student_id,
            certificate_type='completion',
            course_name=course_name,
            award_date=award_date,
            grade=grade or None,
            additional_info=f"Graduation parchment, conferred at ceremony #{ceremony_id}",
            issued_by=issued_by,
        )

        with transaction() as conn:
            conn.execute(
                """INSERT INTO graduation_print_queue
                       (ceremony_id, student_id, certificate_id,
                        certificate_number, status)
                   VALUES (?,?,?,?, 'queued')
                   ON CONFLICT(ceremony_id, student_id) DO UPDATE SET
                       certificate_id     = excluded.certificate_id,
                       certificate_number = excluded.certificate_number,
                       status             = 'queued',
                       printed_at         = NULL,
                       dispatched_at      = NULL""",
                (ceremony_id, student_id, cert['id'], cert['certificate_number']),
            )
            row = conn.execute(
                "SELECT * FROM graduation_print_queue "
                "WHERE ceremony_id = ? AND student_id = ?",
                (ceremony_id, student_id),
            ).fetchone()
        return dict(row) if row else {}

    @staticmethod
    def set_status(queue_id: int, status: str,
                   notes: str = "") -> bool:
        if status not in PrintQueueManager.QUEUE_STATUSES:
            raise ValueError(f"invalid status: {status}")
        with transaction() as conn:
            cols = ["status = ?"]
            params: List[Any] = [status]
            if status == 'printed':
                cols.append("printed_at = datetime('now')")
            if status == 'dispatched':
                cols.append("dispatched_at = datetime('now')")
            if notes:
                cols.append("notes = ?")
                params.append(notes)
            params.append(queue_id)
            cur = conn.execute(
                f"UPDATE graduation_print_queue SET {', '.join(cols)} WHERE queue_id = ?",
                params,
            )
            return cur.rowcount > 0

    @staticmethod
    def list_queue(ceremony_id: int,
                   status: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            q = ("SELECT q.*, "
                 "       TRIM(COALESCE(s.first_name,'')||' '||COALESCE(s.last_name,'')) AS student_name,"
                 "       COALESCE(s.course,'') AS course"
                 "  FROM graduation_print_queue q"
                 "  LEFT JOIN students s ON s.student_id = q.student_id"
                 " WHERE q.ceremony_id = ?")
            params: List[Any] = [ceremony_id]
            if status:
                q += " AND q.status = ?"
                params.append(status)
            q += " ORDER BY student_name, q.student_id"
            rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# DigitalDiplomaManager
# ---------------------------------------------------------------------------

class DigitalDiplomaManager:
    """Issue digital diplomas through the existing blockchain_credentials store.

    We write directly to the ``blockchain_credentials`` table the legacy CLI
    helper uses, so the credential shows up in the same view / verification
    flows without forking that schema."""

    @staticmethod
    def _ensure_table(conn) -> None:
        # Same shape as the rows the CLI helper inserts. Created on demand
        # because this code path may run before the finance/blockchain init
        # has fired on a fresh DB.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS blockchain_credentials (
                credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                credential_type TEXT NOT NULL,
                credential_name TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                blockchain_hash TEXT NOT NULL,
                blockchain_address TEXT,
                ipfs_hash TEXT,
                metadata TEXT,
                revoked INTEGER NOT NULL DEFAULT 0,
                revoked_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

    @staticmethod
    def issue(student_id: str, credential_name: str,
              credential_type: str = "diploma",
              issue_date: Optional[str] = None,
              blockchain_address: Optional[str] = None,
              ipfs_hash: Optional[str] = None,
              extra_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Insert a new credential row. The blockchain hash is computed
        deterministically from (student_id, type, name, date) so the same
        inputs produce the same hash — useful for re-issue dedup."""
        if not student_id or not credential_name:
            raise ValueError("student_id and credential_name are required")
        if credential_type not in {'degree', 'certificate', 'diploma', 'transcript'}:
            raise ValueError(f"invalid credential_type: {credential_type}")
        issue_date = issue_date or datetime.now().strftime('%Y-%m-%d')

        hash_input = f"{student_id}{credential_type}{credential_name}{issue_date}"
        blockchain_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()

        metadata = {
            'issuer':          'University System',
            'issued_date':     issue_date,
            'credential_type': credential_type,
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        with transaction() as conn:
            DigitalDiplomaManager._ensure_table(conn)
            cur = conn.execute(
                """INSERT INTO blockchain_credentials
                       (student_id, credential_type, credential_name,
                        issue_date, blockchain_hash, blockchain_address,
                        ipfs_hash, metadata)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (student_id, credential_type, credential_name, issue_date,
                 blockchain_hash, blockchain_address or None,
                 ipfs_hash or None, json.dumps(metadata)),
            )
            credential_id = cur.lastrowid
        return {
            'credential_id':      credential_id,
            'blockchain_hash':    blockchain_hash,
            'credential_type':    credential_type,
            'credential_name':    credential_name,
            'issue_date':         issue_date,
            'metadata':           metadata,
        }

    @staticmethod
    def list_for_student(student_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            DigitalDiplomaManager._ensure_table(conn)
            rows = conn.execute(
                "SELECT * FROM blockchain_credentials WHERE student_id = ? "
                "ORDER BY issue_date DESC",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# TranscriptFreezeManager
# ---------------------------------------------------------------------------

class TranscriptFreezeManager:
    """Capture the immutable transcript snapshot at conferral and issue
    employer access tokens against it."""

    DEFAULT_TOKEN_TTL_DAYS = 30

    @staticmethod
    def freeze(student_id: str,
               program_id: Optional[int] = None,
               academic_year: Optional[str] = None,
               classification: str = "",
               frozen_by: str = "system") -> Dict[str, Any]:
        """Render the student's transcript via ``TranscriptService`` and store
        the bytes + SHA-256. Re-freezing the same (student, year) replaces
        the snapshot (the access tokens that point to it survive)."""
        from education_system.platform.features.certificates.transcript_service import (
            TranscriptService,
        )
        svc = TranscriptService()
        try:
            html = svc.export_transcript_html(student_id, academic_year=academic_year)
            data = svc.generate_transcript(student_id, academic_year=academic_year)
        except Exception as e:
            raise RuntimeError(f"transcript generation failed: {e}") from e
        if not html:
            raise RuntimeError("transcript renderer returned empty HTML")

        snapshot_hash = hashlib.sha256(html.encode('utf-8')).hexdigest()
        gpa = (data or {}).get('gpa') or ''

        with transaction() as conn:
            conn.execute(
                """INSERT INTO transcript_freezes
                       (student_id, program_id, academic_year, snapshot_html,
                        snapshot_hash, frozen_by, gpa, classification)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(student_id, academic_year) DO UPDATE SET
                       program_id     = excluded.program_id,
                       snapshot_html  = excluded.snapshot_html,
                       snapshot_hash  = excluded.snapshot_hash,
                       frozen_at      = datetime('now'),
                       frozen_by      = excluded.frozen_by,
                       gpa            = excluded.gpa,
                       classification = excluded.classification""",
                (student_id, program_id, academic_year or '',
                 html, snapshot_hash, frozen_by, gpa, classification),
            )
            row = conn.execute(
                "SELECT freeze_id, snapshot_hash, frozen_at FROM transcript_freezes "
                "WHERE student_id = ? AND academic_year = ?",
                (student_id, academic_year or ''),
            ).fetchone()
        return dict(row) if row else {}

    @staticmethod
    def get_freeze(freeze_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM transcript_freezes WHERE freeze_id = ?",
                (freeze_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_latest_for_student(student_id: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM transcript_freezes WHERE student_id = ? "
                "ORDER BY frozen_at DESC LIMIT 1",
                (student_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def issue_employer_token(freeze_id: int,
                             employer_email: str,
                             employer_name: str = "",
                             requested_by: str = "",
                             purpose: str = "Employment verification",
                             ttl_days: int = DEFAULT_TOKEN_TTL_DAYS,
                             verification_url_base: str = "https://verify.university.edu/transcript",
                             send_email_notice: bool = True) -> Dict[str, Any]:
        """Create a one-time access token and (best-effort) email it to the
        employer using the ``student_lifecycle/transcript_for_employer``
        template."""
        token = secrets.token_urlsafe(24)
        expires_at = (datetime.now() + timedelta(days=int(ttl_days))).strftime('%Y-%m-%d')

        with transaction() as conn:
            cur = conn.execute(
                """INSERT INTO transcript_access_tokens
                       (freeze_id, token, requested_by, employer_name,
                        employer_email, purpose, expires_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (freeze_id, token, requested_by, employer_name,
                 employer_email, purpose, expires_at),
            )
            token_id = cur.lastrowid
            freeze = conn.execute(
                "SELECT * FROM transcript_freezes WHERE freeze_id = ?",
                (freeze_id,),
            ).fetchone()
            stud = None
            if freeze:
                stud = _lookup_student(conn, freeze['student_id'])

        verification_url = f"{verification_url_base}/{token}"

        if send_email_notice and employer_email and freeze and stud:
            TranscriptFreezeManager._send_employer_email(
                employer_email=employer_email,
                employer_name=employer_name or 'Hiring Team',
                recipient_name=employer_name or 'Hiring Team',
                token=token,
                expires_at=expires_at,
                verification_url=verification_url,
                purpose=purpose,
                freeze_reference=f"FRZ-{freeze['freeze_id']}",
                stud=stud,
                freeze=dict(freeze),
            )
        return {
            'token_id':         token_id,
            'token':            token,
            'expires_at':       expires_at,
            'verification_url': verification_url,
        }

    @staticmethod
    def _send_employer_email(*, employer_email: str, employer_name: str,
                             recipient_name: str, token: str, expires_at: str,
                             verification_url: str, purpose: str,
                             freeze_reference: str,
                             stud: Dict[str, str],
                             freeze: Dict[str, Any]) -> bool:
        try:
            from education_system.systems.university.infrastructure.email.template_utils import (
                render_template,
            )
            from education_system.systems.university.infrastructure.email.email_service import (
                send_email,
            )
        except Exception:
            logger.exception("email infrastructure unavailable")
            return False
        subject, body = render_template(
            'student_lifecycle/transcript_for_employer', {
                'recipient_name':   recipient_name,
                'employer_name':    employer_name,
                'student_name':     stud.get('full_name', '(student)'),
                'student_id':       stud.get('student_id', ''),
                'program_name':     stud.get('course') or '(see transcript)',
                'classification':   freeze.get('classification') or '(see transcript)',
                'academic_year':    freeze.get('academic_year') or '(full record)',
                'freeze_reference': freeze_reference,
                'access_token':    token,
                'expires_at':       expires_at,
                'verification_url': verification_url,
                'purpose':          purpose,
                'frozen_at':        freeze.get('frozen_at') or '(see record)',
            })
        if not subject or not body:
            return False
        try:
            send_email(recipient_email=employer_email, subject=subject, body=body)
            return True
        except Exception:
            logger.exception("send_email failed transcript employer=%s", employer_email)
            return False

    @staticmethod
    def consume_token(token: str) -> Optional[Dict[str, Any]]:
        """Single-use redemption. Returns the freeze row + token metadata on
        success, ``None`` if the token is unknown / expired / already used /
        revoked."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with transaction() as conn:
            row = conn.execute(
                "SELECT * FROM transcript_access_tokens WHERE token = ?",
                (token,),
            ).fetchone()
            if not row:
                return None
            if row['revoked']:
                return None
            if row['accessed_at']:
                return None
            if row['expires_at'] and row['expires_at'] < datetime.now().strftime('%Y-%m-%d'):
                return None
            conn.execute(
                "UPDATE transcript_access_tokens SET accessed_at = ? WHERE token_id = ?",
                (now, row['token_id']),
            )
            freeze = conn.execute(
                "SELECT * FROM transcript_freezes WHERE freeze_id = ?",
                (row['freeze_id'],),
            ).fetchone()
        if not freeze:
            return None
        return {
            'freeze':           dict(freeze),
            'employer_email':   row['employer_email'],
            'employer_name':    row['employer_name'],
            'purpose':          row['purpose'],
            'accessed_at':      now,
        }

    @staticmethod
    def revoke_token(token_id: int) -> bool:
        with transaction() as conn:
            cur = conn.execute(
                "UPDATE transcript_access_tokens SET revoked = 1 WHERE token_id = ?",
                (token_id,),
            )
            return cur.rowcount > 0

    @staticmethod
    def list_tokens(student_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT t.*, f.student_id, f.academic_year
                     FROM transcript_access_tokens t
                     JOIN transcript_freezes f ON f.freeze_id = t.freeze_id
                    WHERE f.student_id = ?
                    ORDER BY t.issued_at DESC""",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# AlumniProvisioner
# ---------------------------------------------------------------------------

class AlumniProvisioner:
    """Create an alumni record at conferral.

    Uses the legacy ``alumni`` table from
    ``student_affairs/services/alumni_management/database.py``; alumni_id is
    set to the student_id so reverse lookups stay simple."""

    @staticmethod
    def _ensure_table(conn) -> None:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS alumni (
                alumni_id TEXT PRIMARY KEY,
                student_id TEXT,
                email_address TEXT,
                title TEXT,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                gender TEXT,
                dob TEXT,
                graduation_year INTEGER,
                degree_earned TEXT,
                current_employer TEXT,
                job_title TEXT,
                industry TEXT,
                address TEXT,
                city TEXT,
                country TEXT,
                phone TEXT,
                linkedin_url TEXT,
                date_registered TEXT,
                is_donor BOOLEAN DEFAULT 0,
                is_mentor BOOLEAN DEFAULT 0,
                is_board_member BOOLEAN DEFAULT 0,
                profile_photo TEXT,
                bio TEXT,
                skills TEXT,
                achievements TEXT,
                privacy_level INTEGER DEFAULT 1,
                engagement_score INTEGER DEFAULT 0,
                last_activity TEXT,
                social_media_links TEXT,
                is_ambassador BOOLEAN DEFAULT 0
            )
        ''')

    # Status set on the source ``students`` row once the record has been moved
    # across to the alumni system.
    GRADUATED_STATUS = 'Graduated'

    @staticmethod
    def provision(student_id: str,
                  graduation_year: Optional[int] = None,
                  degree_earned: str = "",
                  move_student: bool = True) -> Dict[str, Any]:
        """Upsert an ``alumni`` row from the student record and (by default)
        *move* the student over by marking their ``students.status`` as
        graduated, so they are no longer treated as an active student.

        The student row itself is retained — not deleted — so historical
        references (RSVPs, payments, certificates, transcript freezes) stay
        intact; ``move_student=False`` skips the status change. Returns the
        resulting alumni row with an added ``student_moved`` flag."""
        with transaction() as conn:
            AlumniProvisioner._ensure_table(conn)
            stud = _lookup_student(conn, student_id)
            if not stud:
                raise ValueError(f"student {student_id} not found")
            year = graduation_year or datetime.now().year
            degree = degree_earned or stud.get('course') or ''
            conn.execute(
                """INSERT INTO alumni (
                       alumni_id, student_id, email_address, first_name,
                       middle_name, last_name, gender, dob,
                       graduation_year, degree_earned, date_registered
                   ) VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))
                   ON CONFLICT(alumni_id) DO UPDATE SET
                       email_address   = excluded.email_address,
                       first_name      = excluded.first_name,
                       middle_name     = excluded.middle_name,
                       last_name       = excluded.last_name,
                       gender          = excluded.gender,
                       dob             = excluded.dob,
                       graduation_year = excluded.graduation_year,
                       degree_earned   = excluded.degree_earned""",
                (
                    student_id, student_id, stud.get('email', ''),
                    stud.get('first_name', ''), stud.get('middle_name', ''),
                    stud.get('last_name', ''), stud.get('gender', ''),
                    stud.get('dob', ''),
                    year, degree,
                ),
            )
            student_moved = False
            if move_student:
                cur = conn.execute(
                    "UPDATE students SET status = ? WHERE student_id = ?",
                    (AlumniProvisioner.GRADUATED_STATUS, student_id),
                )
                student_moved = cur.rowcount > 0
            row = conn.execute(
                "SELECT * FROM alumni WHERE alumni_id = ?", (student_id,),
            ).fetchone()
        result = dict(row) if row else {}
        result['student_moved'] = student_moved
        # Flip the login account over to the 'alumni' role so the graduate is
        # routed to the Alumni portal on their next sign-in (best-effort).
        result['account_promoted'] = (
            AlumniProvisioner._promote_account_to_alumni(student_id)
            if move_student else False)
        return result

    @staticmethod
    def _promote_account_to_alumni(student_id: str) -> bool:
        """Switch the shared-auth account's university role to 'alumni'.

        The student's login username is their student_id (the convention used
        across the system), so we look the account up by username. Best-effort:
        any failure (auth DB unavailable, no matching account) is logged and
        returns ``False`` without affecting the alumni/student writes."""
        try:
            from education_system.platform.identity.auth.db import connect as auth_connect
            from education_system.platform.identity.auth.role_manager import RoleManager
        except Exception:
            logger.debug("shared auth unavailable; skipping account promotion")
            return False
        try:
            conn = auth_connect()
            try:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (student_id,),
                ).fetchone()
            finally:
                conn.close()
            if not row:
                logger.info("no auth account for %s; alumni role not applied",
                            student_id)
                return False
            RoleManager().grant_system_access(row['id'], 'university', 'alumni')
            return True
        except Exception:
            logger.exception("failed to promote account to alumni sid=%s",
                             student_id)
            return False

    @staticmethod
    def is_provisioned(student_id: str) -> bool:
        with get_connection() as conn:
            try:
                row = conn.execute(
                    "SELECT 1 FROM alumni WHERE alumni_id = ?",
                    (student_id,),
                ).fetchone()
            except sqlite3.OperationalError:
                return False
        return bool(row)


# ---------------------------------------------------------------------------
# All-in-one bundle used by the GUI's "Conferral package" button
# ---------------------------------------------------------------------------

def issue_conferral_package(ceremony_id: int, student_id: str,
                           course_name: str = "",
                           grade: str = "",
                           classification: str = "",
                           graduation_year: Optional[int] = None,
                           academic_year: Optional[str] = None,
                           program_id: Optional[int] = None,
                           frozen_by: str = "system") -> Dict[str, Any]:
    """Run the four artefact steps in one go and return a summary.

    Designed to be called from the GUI's "Issue conferral package" button;
    any single step that fails is recorded in the summary, the rest continue."""
    summary: Dict[str, Any] = {
        'student_id':   student_id,
        'ceremony_id':  ceremony_id,
        'print_queue':  None,
        'diploma':      None,
        'freeze':       None,
        'alumni':       None,
        'errors':       [],
    }
    try:
        summary['print_queue'] = PrintQueueManager.enqueue(
            ceremony_id, student_id, course_name=course_name, grade=grade,
        )
    except Exception as e:
        logger.exception("print queue step failed sid=%s", student_id)
        summary['errors'].append(f"print_queue: {e}")
    try:
        summary['diploma'] = DigitalDiplomaManager.issue(
            student_id=student_id,
            credential_name=course_name or 'Award',
            credential_type='diploma',
            extra_metadata={'classification': classification} if classification else None,
        )
    except Exception as e:
        logger.exception("diploma step failed sid=%s", student_id)
        summary['errors'].append(f"diploma: {e}")
    try:
        summary['freeze'] = TranscriptFreezeManager.freeze(
            student_id=student_id, program_id=program_id,
            academic_year=academic_year, classification=classification,
            frozen_by=frozen_by,
        )
    except Exception as e:
        logger.exception("transcript freeze step failed sid=%s", student_id)
        summary['errors'].append(f"freeze: {e}")
    try:
        summary['alumni'] = AlumniProvisioner.provision(
            student_id=student_id, graduation_year=graduation_year,
            degree_earned=course_name,
        )
    except Exception as e:
        logger.exception("alumni step failed sid=%s", student_id)
        summary['errors'].append(f"alumni: {e}")
    return summary


__all__ = [
    'PrintQueueManager', 'DigitalDiplomaManager',
    'TranscriptFreezeManager', 'AlumniProvisioner',
    'issue_conferral_package',
]
