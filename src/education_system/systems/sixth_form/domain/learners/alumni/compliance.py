"""Sixth-form alumni — GDPR consent, retention/anonymise, self-service portal tokens, protected-characteristic gaps (#41), SAR bundle (#44), erasure (#45), data quality (#46), dedupe buckets (#47).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import csv as _csv
import datetime as _dt
import io as _io
import logging
import secrets
from dataclasses import dataclass
from typing import Any
from typing import Callable
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    CONSENT_SCOPES,
    CONSENT_VERSION,
    Consent,
    ERASURE_STATUSES,
    HARD_BOUNCE_THRESHOLD,
    K_SUPPRESSION_THRESHOLD,
    PORTAL_TOKEN_TTL_DAYS,
    PortalToken,
    _log_action,
    logger,
)
from .db import (
    IntegrationError,
    NotFoundError,
    ValidationError,
    _connect,
    _row,
    init_db,
)


# ── GDPR consent ──────────────────────────────────────────────────

def _row_consent(r: db.Row) -> Consent:
    return Consent(
        consent_id=r["consent_id"], alumni_id=r["alumni_id"],
        scope=r["scope"], version=r["version"],
        granted_at=r["granted_at"], withdrawn_at=r["withdrawn_at"],
        source=r["source"], notes=r["notes"],
    )


def grant_consent(alumni_id: int, scope: str, *,
                   version: str = CONSENT_VERSION,
                   source: str | None = None,
                   notes: str | None = None,
                   when: str | None = None) -> Consent:
    init_db()
    if scope not in CONSENT_SCOPES:
        raise ValidationError(
            f"Scope must be one of: {', '.join(CONSENT_SCOPES)}")
    granted_at = when or _dt.datetime.now().isoformat(
        timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_consent
                   (alumni_id, scope, version, granted_at,
                    source, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (alumni_id, scope, version, granted_at,
             (source or "").strip() or None,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_consent WHERE consent_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("consent.grant", alumni_id=alumni_id,
                  scope=scope, version=version, source=source)
    return _row_consent(r)


def withdraw_consent(consent_id: int, *,
                      when: str | None = None,
                      notes: str | None = None) -> Consent:
    init_db()
    when_iso = when or _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_consent WHERE consent_id = ?",
            (consent_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No consent #{consent_id}")
        if r["withdrawn_at"]:
            return _row_consent(r)
        merged_notes = ((r["notes"] or "") + ("\n" if r["notes"] else "")
                          + f"withdrawn: {notes}") if notes else r["notes"]
        conn.execute(
            "UPDATE alumni_consent SET withdrawn_at = ?, notes = ? "
            "WHERE consent_id = ?",
            (when_iso, merged_notes, consent_id))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_consent WHERE consent_id = ?",
            (consent_id,)).fetchone()
    out = _row_consent(r2)
    _log_action("consent.withdraw", alumni_id=out.alumni_id,
                  consent_id=consent_id, scope=out.scope)
    return out


def list_consents(alumni_id: int, *,
                   active_only: bool = False) -> list[Consent]:
    init_db()
    sql = ("SELECT * FROM alumni_consent WHERE alumni_id = ? "
            + ("AND withdrawn_at IS NULL " if active_only else "")
            + "ORDER BY granted_at DESC, consent_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, (alumni_id,)).fetchall()
    return [_row_consent(r) for r in rows]


def has_active_consent(alumni_id: int, scope: str) -> bool:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_consent "
            "WHERE alumni_id = ? AND scope = ? "
            "AND withdrawn_at IS NULL "
            "ORDER BY granted_at DESC LIMIT 1",
            (alumni_id, scope)).fetchone()
    return r is not None


# ── Retention / anonymise ─────────────────────────────────────────

def find_retention_candidates(*, years: int = 7
                                ) -> list[Alumnus]:
    """Alumni with status Opt-out or Deceased whose last update is
    older than ``years`` years."""
    init_db()
    cutoff = (_dt.date.today() - _dt.timedelta(days=365 * years)
                ).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni "
            "WHERE status IN ('Opt-out', 'Deceased') "
            "AND substr(updated_at, 1, 10) < ? "
            "ORDER BY updated_at ASC", (cutoff,)).fetchall()
    return [_row(r) for r in rows]


def anonymise_alumnus(alumni_id: int) -> Alumnus:
    """Replace identifying fields with placeholders and clear all
    child PII (emails, phones, address, bio, photo). Preserves
    aggregate fields useful for outcome stats (leaving year,
    destination type, sector)."""
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """UPDATE alumni SET
                   first_name = 'Anonymised',
                   last_name  = '#' || ?,
                   preferred_name = NULL, pronouns = NULL,
                   gender = NULL, dob = NULL,
                   original_student_id = NULL,
                   email = NULL, phone = NULL, address = NULL,
                   linkedin = NULL, other_social = NULL,
                   photo_path = NULL, bio = NULL,
                   notes = NULL, last_contacted = NULL,
                   current_role = NULL, current_employer = NULL,
                   current_location = NULL, region = NULL,
                   updated_at = datetime('now')
               WHERE alumni_id = ?""",
            (alumni_id, alumni_id))
        for tbl in ("alumni_emails", "alumni_phones",
                     "alumni_portal_tokens",
                     "alumni_achievements", "alumni_career",
                     "alumni_education"):
            try:
                conn.execute(
                    f"DELETE FROM {tbl} WHERE alumni_id = ?",
                    (alumni_id,))
            except db.OperationalError:
                continue
        conn.commit()
    a = get_alumnus(alumni_id)
    assert a is not None
    _log_action("alumnus.anonymise", alumni_id=alumni_id,
                  level=logging.WARNING)
    return a


# ── Self-service portal tokens ────────────────────────────────────

def _row_token(r: db.Row) -> PortalToken:
    return PortalToken(
        token=r["token"], alumni_id=r["alumni_id"],
        expires_at=r["expires_at"], used_at=r["used_at"],
        created_at=r["created_at"],
    )


def create_portal_token(alumni_id: int, *,
                         ttl_days: int = PORTAL_TOKEN_TTL_DAYS
                         ) -> PortalToken:
    init_db()
    tok = secrets.token_urlsafe(24)
    expires = (_dt.datetime.now()
                + _dt.timedelta(days=ttl_days)
                ).isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_portal_tokens
                   (token, alumni_id, expires_at) VALUES (?, ?, ?)""",
            (tok, alumni_id, expires))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_portal_tokens WHERE token = ?",
            (tok,)).fetchone()
    _log_action("portal.token_issued", alumni_id=alumni_id,
                  ttl_days=ttl_days, expires_at=expires)
    return _row_token(r)


def validate_portal_token(token: str) -> PortalToken | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_portal_tokens WHERE token = ?",
            (token,)).fetchone()
        if r is None:
            return None
        tok = _row_token(r)
    now_iso = _dt.datetime.now().isoformat(timespec="seconds")
    if tok.used_at:
        return None
    if tok.expires_at < now_iso:
        return None
    return tok


_SELF_SERVICE_FIELDS: frozenset[str] = frozenset({
    "preferred_name", "pronouns", "current_role", "current_employer",
    "current_sector", "current_location", "country", "region",
    "email", "phone", "linkedin", "other_social", "bio",
})


def apply_self_service_update(token: str,
                                payload: dict[str, Any]) -> Alumnus:
    """Apply an alumnus's own edits via a single-use portal token.
    Only a whitelisted set of fields can be updated. The token is
    marked used on success."""
    tok = validate_portal_token(token)
    if tok is None:
        raise ValidationError("Invalid or expired portal token")
    safe = {k: v for k, v in payload.items()
              if k in _SELF_SERVICE_FIELDS}
    if not safe:
        raise ValidationError("No editable fields in payload")
    out = update_alumnus(tok.alumni_id, safe, actor="self-service")
    with _connect() as conn:
        conn.execute(
            "UPDATE alumni_portal_tokens SET used_at = ? "
            "WHERE token = ?",
            (_dt.datetime.now().isoformat(timespec="seconds"), token))
        conn.commit()
    _log_action("portal.self_service_apply", actor="self-service",
                  alumni_id=tok.alumni_id, fields=len(safe))
    return out


# ── #41 Protected-characteristic gaps (k-suppression) ────────────

PROTECTED_CHARS: tuple[str, ...] = (
    "send", "fsm_ever_6", "eal", "looked_after",
)


def set_protected_characteristic(alumni_id: int, char: str,
                                       value: bool, *,
                                       actor: str | None = None) -> None:
    init_db()
    if char not in PROTECTED_CHARS:
        raise ValidationError(
            f"Characteristic must be one of: "
            f"{', '.join(PROTECTED_CHARS)}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            f"UPDATE alumni SET {char} = ? WHERE alumni_id = ?",
            (1 if value else 0, alumni_id))
        conn.commit()
    _log_action("protected.set", actor=actor, alumni_id=alumni_id,
                  char=char, value=value)


def set_ethnicity(alumni_id: int, value: str | None, *,
                      actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "UPDATE alumni SET ethnicity = ? WHERE alumni_id = ?",
            ((value or "").strip() or None, alumni_id))
        conn.commit()
    _log_action("ethnicity.set", actor=actor, alumni_id=alumni_id)


@dataclass
class ProtectedGapRow:
    characteristic: str
    bucket: str        # 'with' / 'without'
    cohort: int        # raw count (may be suppressed in display)
    he_rate_pct: float | None
    suppressed: bool


def protected_characteristic_gaps(*,
                                       leaving_year: str | None = None,
                                       k: int = K_SUPPRESSION_THRESHOLD
                                       ) -> list[ProtectedGapRow]:
    """For each binary protected characteristic, compare HE-entry
    rate between alumni with the flag set vs not. Any bucket with a
    cohort below ``k`` has its rate suppressed (set to ``None``) and
    is flagged via ``suppressed=True`` to satisfy small-n redaction
    rules."""
    init_db()
    he_set = ("University", "Further Study")
    out: list[ProtectedGapRow] = []
    sql_base = ("SELECT {col} AS flag, destination_type "
                  "FROM alumni WHERE deleted_at IS NULL")
    params_base: list[Any] = []
    if leaving_year:
        sql_base += " AND leaving_year = ?"
        params_base.append(leaving_year)
    with _connect() as conn:
        for char in PROTECTED_CHARS:
            rows = conn.execute(
                sql_base.format(col=char), params_base).fetchall()
            for bucket_label, want in (("with", 1), ("without", 0)):
                subset = [r for r in rows if int(r["flag"]) == want]
                cohort = len(subset)
                in_he = sum(1 for r in subset
                              if r["destination_type"] in he_set)
                suppressed = cohort < k
                rate = (round(100 * in_he / cohort, 1)
                          if (cohort and not suppressed) else None)
                out.append(ProtectedGapRow(
                    characteristic=char, bucket=bucket_label,
                    cohort=cohort, he_rate_pct=rate,
                    suppressed=suppressed))
    return out


# ── #44 SAR bundle generator ─────────────────────────────────────

def generate_sar_bundle(alumni_id: int, out_dir: str,  # type: ignore[name-defined]
                            *, actor: str | None = None) -> str:
    """Pack every row keyed to ``alumni_id`` across every table into
    one ZIP, one CSV per table. Returns the ZIP path."""
    init_db()
    from pathlib import Path as _Path
    import csv as _csv
    import io as _io
    import zipfile as _zip
    a = get_alumnus(alumni_id)
    if a is None:
        raise NotFoundError(f"No alumnus #{alumni_id}")
    d = _Path(out_dir)
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntegrationError(
            f"Cannot create SAR output directory {d}: {exc}") from exc
    zip_path = d / (
        f"sar-{alumni_id}-"
        f"{_dt.datetime.now().strftime('%Y%m%d%H%M%S')}.zip")
    try:
      with _connect() as conn:
        tables = [row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name LIKE 'alumni%'"
            ).fetchall()]
        with _zip.ZipFile(zip_path, "w",
                            compression=_zip.ZIP_DEFLATED) as z:
            for tbl in sorted(tables):
                cols = [row[1] for row in conn.execute(
                    f"PRAGMA table_info({tbl})").fetchall()]
                if "alumni_id" not in cols and tbl != "alumni":
                    continue
                if tbl == "alumni":
                    rows = conn.execute(
                        "SELECT * FROM alumni WHERE alumni_id = ?",
                        (alumni_id,)).fetchall()
                else:
                    rows = conn.execute(
                        f"SELECT * FROM {tbl} WHERE alumni_id = ?",
                        (alumni_id,)).fetchall()
                if not rows:
                    continue
                buf = _io.StringIO()
                w = _csv.writer(buf)
                w.writerow(cols)
                for r in rows:
                    w.writerow([r[c] for c in cols])
                z.writestr(f"{tbl}.csv", buf.getvalue())
    except OSError as exc:
        raise IntegrationError(
            f"SAR bundle write failed at {zip_path}: {exc}") from exc
    _log_action("sar.bundle", actor=actor, alumni_id=alumni_id,
                  path=str(zip_path))
    return str(zip_path)


# ── #45 Right-to-erasure workflow ────────────────────────────────

@dataclass
class ErasureRequest:
    request_id: int
    alumni_id: int
    requested_at: str
    requested_by: str | None
    reason: str | None
    status: str
    reviewer: str | None
    reviewed_at: str | None
    review_notes: str | None
    completed_at: str | None
    confirmation_sent_at: str | None


def _row_erasure(r: db.Row) -> ErasureRequest:
    return ErasureRequest(
        request_id=r["request_id"], alumni_id=r["alumni_id"],
        requested_at=r["requested_at"],
        requested_by=r["requested_by"], reason=r["reason"],
        status=r["status"], reviewer=r["reviewer"],
        reviewed_at=r["reviewed_at"],
        review_notes=r["review_notes"],
        completed_at=r["completed_at"],
        confirmation_sent_at=r["confirmation_sent_at"])


def request_erasure(alumni_id: int, *,
                        requested_by: str | None = None,
                        reason: str | None = None,
                        actor: str | None = None) -> ErasureRequest:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_erasure_requests
                   (alumni_id, requested_by, reason)
               VALUES (?, ?, ?)""",
            (alumni_id,
             (requested_by or "").strip() or None,
             (reason or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("erasure.request", actor=actor,
                  alumni_id=alumni_id, request_id=r["request_id"])
    _emit_webhook("alumnus.deleted", {"alumni_id": alumni_id,
                                          "stage": "requested"})
    return _row_erasure(r)


def review_erasure(request_id: int, *,
                       reviewer: str, decision: str,
                       review_notes: str | None = None,
                       actor: str | None = None) -> ErasureRequest:
    """Mark an erasure request as 'Approved' or 'Rejected'. Approval
    does NOT yet anonymise — call :func:`complete_erasure` after the
    statutory clock runs out (or as soon as you're ready)."""
    init_db()
    if decision not in ("Approved", "Rejected"):
        raise ValidationError(
            "decision must be 'Approved' or 'Rejected'")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_erasure_requests "
            "SET status = ?, reviewer = ?, reviewed_at = ?, "
            "    review_notes = ? "
            "WHERE request_id = ? AND status IN "
            "    ('Requested', 'Under Review')",
            (decision, reviewer, now,
             (review_notes or "").strip() or None, request_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No reviewable request #{request_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (request_id,)).fetchone()
    _log_action("erasure.review", actor=actor,
                  request_id=request_id, decision=decision)
    return _row_erasure(r)


def complete_erasure(request_id: int, *,
                         confirmation_sender: Callable[[int], None]
                         | None = None,
                         actor: str | None = None) -> ErasureRequest:
    """Carry out the anonymisation for an Approved request, stamp
    completed_at, and optionally fire ``confirmation_sender(alumni_id)``
    to email the data subject."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (request_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"No erasure request #{request_id}")
        if r["status"] != "Approved":
            raise ValidationError(
                "Request must be Approved before completion")
    anonymise_alumnus(r["alumni_id"])
    now = _dt.datetime.now().isoformat(timespec="seconds")
    conf_sent = None
    if confirmation_sender is not None:
        try:
            confirmation_sender(r["alumni_id"])
            conf_sent = now
        except Exception:
            logger.exception(
                "Erasure confirmation send failed for alumnus #%d",
                r["alumni_id"])
    with _connect() as conn:
        conn.execute(
            "UPDATE alumni_erasure_requests SET status = 'Completed', "
            "    completed_at = ?, confirmation_sent_at = ? "
            "WHERE request_id = ?",
            (now, conf_sent, request_id))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_erasure_requests "
            "WHERE request_id = ?", (request_id,)).fetchone()
    _log_action("erasure.complete", actor=actor,
                  request_id=request_id, alumni_id=r["alumni_id"])
    return _row_erasure(row)


def list_erasure_requests(*, status: str | None = None
                               ) -> list[ErasureRequest]:
    init_db()
    sql = "SELECT * FROM alumni_erasure_requests WHERE 1=1"
    params: list[Any] = []
    if status:
        if status not in ERASURE_STATUSES:
            raise ValidationError(
                f"Status must be one of: "
                f"{', '.join(ERASURE_STATUSES)}")
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY requested_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_erasure(r) for r in rows]


# ── #46 Data quality dashboard ───────────────────────────────────

@dataclass
class DataQuality:
    total: int
    with_email_pct: float
    with_phone_pct: float
    with_address_pct: float
    missing_destination_pct: float
    stale_24mo_pct: float
    bounce_rate_pct: float
    opt_in_pct: float
    consent_data_storage_pct: float


def data_quality_report() -> DataQuality:
    init_db()
    with _connect() as conn:
        total = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL").fetchone()[0])
        if total == 0:
            return DataQuality(
                total=0, with_email_pct=0, with_phone_pct=0,
                with_address_pct=0, missing_destination_pct=0,
                stale_24mo_pct=0, bounce_rate_pct=0,
                opt_in_pct=0, consent_data_storage_pct=0)
        em = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND email IS NOT NULL "
            "  AND TRIM(email) <> ''").fetchone()[0])
        ph = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND phone IS NOT NULL "
            "  AND TRIM(phone) <> ''").fetchone()[0])
        ad = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND address IS NOT NULL "
            "  AND TRIM(address) <> ''").fetchone()[0])
        missing_dest = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND (destination_type IS NULL "
            "       OR destination_type = 'Unknown')"
            ).fetchone()[0])
        bounce = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND bounce_count >= ?",
            (HARD_BOUNCE_THRESHOLD,)).fetchone()[0])
        opt_in = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL AND opt_in_contact = 1"
            ).fetchone()[0])
        ds_consent = int(conn.execute(
            "SELECT COUNT(DISTINCT alumni_id) FROM alumni_consent "
            "WHERE scope = 'Data Storage' "
            "  AND withdrawn_at IS NULL").fetchone()[0])
        two_yrs_ago = (_dt.date.today() - _dt.timedelta(days=730)
                            ).isoformat()
        stale = int(conn.execute(
            "SELECT COUNT(*) FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND (last_contacted IS NULL "
            "       OR last_contacted < ?)",
            (two_yrs_ago,)).fetchone()[0])
    p = lambda n: round(100 * n / total, 1)
    return DataQuality(
        total=total,
        with_email_pct=p(em), with_phone_pct=p(ph),
        with_address_pct=p(ad),
        missing_destination_pct=p(missing_dest),
        stale_24mo_pct=p(stale), bounce_rate_pct=p(bounce),
        opt_in_pct=p(opt_in),
        consent_data_storage_pct=p(ds_consent))


# ── #47 Dedupe confidence buckets ────────────────────────────────

@dataclass
class DedupeBuckets:
    very_high: list[DuplicateCandidate]   # >= 0.95
    high:      list[DuplicateCandidate]   # 0.85 – 0.95
    medium:    list[DuplicateCandidate]   # 0.70 – 0.85


def dedupe_buckets(*, max_results: int = 200) -> DedupeBuckets:
    init_db()
    cands = find_duplicates(threshold=0.70)[:max_results]
    out = DedupeBuckets(very_high=[], high=[], medium=[])
    for c in cands:
        if c.score >= 0.95:
            out.very_high.append(c)
        elif c.score >= 0.85:
            out.high.append(c)
        else:
            out.medium.append(c)
    return out


def batch_confirm_merges(pairs: list[tuple[int, int]], *,
                              actor: str | None = None
                              ) -> tuple[int, list[str]]:
    """Run :func:`merge_alumni` for every (keep_id, merge_id) pair.
    Returns (successful_count, errors)."""
    init_db()
    ok = 0
    errors: list[str] = []
    for keep, drop in pairs:
        try:
            merge_alumni(keep, drop, actor=actor)
            ok += 1
        except Exception as exc:
            errors.append(f"keep={keep} merge={drop}: {exc}")
    _log_action("dedupe.batch_merge", actor=actor,
                  ok=ok, failed=len(errors))
    return ok, errors


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .records import (  # noqa: E402,F401
    DuplicateCandidate,
    find_duplicates,
    get_alumnus,
    merge_alumni,
    update_alumnus,
)
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
from .integrations import (  # noqa: E402,F401
    _emit_webhook,
)
