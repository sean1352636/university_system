"""Laboratory and insurance integration records, kept honestly.

There is no live connection to an outside laboratory or insurer. What the
portal *does* receive — a result typed in from a lab report, a results file
from a lab, an insurer's verification by phone or letter — is recorded
here: every lab result goes to ``lab_results`` with a matching
``lab_integration_events`` row (manual entry or file import), and every
insurance verification to ``insurance_integration_events``. The health
check (:func:`health_summary`) reports from those rows and from
``integration_logs``, never from made-up figures.

Functions take an open connection and do not commit.
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime

LAB_FIELDS = ("student_id", "test_name", "test_code", "result_value", "units",
              "reference_range", "status", "ordered_date", "collected_date", "resulted_date",
              "ordering_provider", "lab_name", "abnormal_flag")
VERIFICATION_OUTCOMES = ("verified", "not_covered", "pending", "failed")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _student_exists(conn, student_id) -> bool:
    return conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                        (str(student_id),)).fetchone() is not None


def record_lab_result(conn, values: dict, *, by: str, source: str = "manual") -> int:
    """One lab result (``source`` 'manual' or 'import'); returns the
    ``lab_results`` id. Needs ``student_id``, ``test_name`` and
    ``result_value``."""
    data = {k: (str(values[k]).strip() if values.get(k) not in (None, "") else None)
            for k in LAB_FIELDS}
    for need in ("student_id", "test_name", "result_value"):
        if not data[need]:
            raise ValueError(f"{need} is required")
    if not _student_exists(conn, data["student_id"]):
        raise LookupError(f"Student {data['student_id']} not found")
    data["status"] = data["status"] or "final"
    data["resulted_date"] = data["resulted_date"] or datetime.now().strftime("%Y-%m-%d")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(lab_results)")}
    row = {k: v for k, v in data.items() if k in cols}
    if "created_at" in cols:
        row["created_at"] = _now()
    cur = conn.execute(f"INSERT INTO lab_results ({', '.join(row)}) VALUES "  # nosec B608
                       f"({', '.join('?' * len(row))})", list(row.values()))
    result_id = cur.lastrowid
    conn.execute(
        "INSERT INTO lab_integration_events (order_id, patient_id, test_code, event_type, status, "
        "external_id, correlation_id, payload, result_at, created_at) VALUES "
        "(?, ?, ?, 'result_received', ?, ?, ?, ?, ?, ?)",
        (None, data["student_id"], data["test_code"], source, str(result_id),
         uuid.uuid4().hex, json.dumps({"lab_result_id": result_id, "by": by,
                                       "test_name": data["test_name"]}),
         data["resulted_date"], _now()))
    return result_id


def import_lab_file(conn, path, *, by: str) -> tuple[int, list[str]]:
    """Import a lab results CSV (header row; columns named as
    :data:`LAB_FIELDS`, at least student_id, test_name, result_value).
    Returns ``(imported, errors)``; bad rows are reported, not guessed."""
    imported, errors = 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = {"student_id", "test_name", "result_value"} - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"The file has no {', '.join(sorted(missing))} column")
        for line, row in enumerate(reader, start=2):
            try:
                record_lab_result(conn, {k.strip(): v for k, v in row.items() if k},
                                  by=by, source="import")
                imported += 1
            except (ValueError, LookupError) as exc:
                errors.append(f"line {line}: {exc}")
    conn.execute("INSERT INTO lab_integration_events (event_type, status, payload, created_at) "
                 "VALUES ('file_import', ?, ?, ?)",
                 ("ok" if not errors else "partial",
                  json.dumps({"file": str(path), "imported": imported, "errors": len(errors),
                              "by": by}), _now()))
    return imported, errors


def record_insurance_verification(conn, *, student_id, outcome: str, by: str,
                                  reference: str | None = None, notes: str | None = None) -> int:
    """An insurer's answer about a student's cover (phone, letter, portal)."""
    if outcome not in VERIFICATION_OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(VERIFICATION_OUTCOMES)}")
    if not _student_exists(conn, student_id):
        raise LookupError(f"Student {student_id} not found")
    policy = conn.execute("SELECT insurance_provider, policy_number FROM insurance_information "
                          "WHERE student_id = ? ORDER BY id DESC LIMIT 1",
                          (str(student_id),)).fetchone()
    return conn.execute(
        "INSERT INTO insurance_integration_events (claim_id, patient_id, event_type, status, "
        "external_id, correlation_id, payload, created_at) VALUES "
        "(?, ?, 'verification', ?, ?, ?, ?, ?)",
        (None, str(student_id), outcome, reference, uuid.uuid4().hex,
         json.dumps({"by": by, "notes": notes,
                     "provider": policy[0] if policy else None,
                     "policy_number": policy[1] if policy else None}), _now())).lastrowid


def recent_events(conn, table: str, limit: int = 20) -> list[tuple]:
    if table not in ("lab_integration_events", "insurance_integration_events"):
        raise ValueError(table)
    return conn.execute(f"SELECT created_at, event_type, status, patient_id, payload "  # nosec B608
                        f"FROM {table} ORDER BY created_at DESC, id DESC LIMIT ?",
                        (limit,)).fetchall()


def health_summary(conn) -> list[dict]:
    """Per integration: last activity, events and failures in 30 days."""
    out = []
    for name, table, bad in (("Laboratory results", "lab_integration_events", ("error", "partial")),
                             ("Insurance verification", "insurance_integration_events",
                              ("failed", "error"))):
        last = conn.execute(f"SELECT MAX(created_at) FROM {table}").fetchone()[0]  # nosec B608
        n, failures = conn.execute(
            f"SELECT COUNT(*), SUM(CASE WHEN status IN ({','.join('?' * len(bad))}) THEN 1 ELSE 0 END) "  # nosec B608
            f"FROM {table} WHERE created_at >= datetime('now', '-30 days')", bad).fetchone()
        out.append({"system": name, "last_activity": last, "events_30d": n or 0,
                    "failures_30d": failures or 0, "mode": "manual entry / file import"})
    try:
        for provider, last, n, errors in conn.execute(
                "SELECT COALESCE(provider, system, 'unknown'), MAX(created_at), COUNT(*), "
                "SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) FROM integration_logs "
                "WHERE created_at >= datetime('now', '-30 days') GROUP BY 1").fetchall():
            out.append({"system": provider, "last_activity": last, "events_30d": n,
                        "failures_30d": errors or 0, "mode": "integration log"})
    except Exception:
        pass
    return out


def insurance_verifications(conn, student_id=None, limit=100) -> list[dict]:
    """Recorded insurer answers (:func:`record_insurance_verification`),
    newest first: ``{id, at, student_id, outcome, reference, by, notes,
    provider, policy_number}``."""
    sql = ("SELECT id, created_at, patient_id, status, external_id, payload FROM "
           "insurance_integration_events WHERE event_type = 'verification'")
    args: list = []
    if student_id:
        sql += " AND patient_id = ?"
        args.append(str(student_id))
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    args.append(int(limit))
    out = []
    for vid, at, sid, outcome, reference, payload in conn.execute(sql, args).fetchall():
        try:
            extra = json.loads(payload or "{}")
        except ValueError:
            extra = {}
        out.append({"id": vid, "at": at, "student_id": sid, "outcome": outcome,
                    "reference": reference, "by": extra.get("by"), "notes": extra.get("notes"),
                    "provider": extra.get("provider"),
                    "policy_number": extra.get("policy_number")})
    return out
