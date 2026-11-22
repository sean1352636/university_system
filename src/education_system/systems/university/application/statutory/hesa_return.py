"""Building the HESA Data Futures student return.

1. The institution's UKPRN and HESA provider id must be set
   (``infrastructure/institution_settings``); without them nothing is built.
2. Choose a reference period: the whole HESA year (1 August - 31 July) or a
   period ending on one of the year's ``census_hesa`` key dates in the
   academic calendar (:func:`reference_periods`).
3. :func:`build` collects the entities (``hesa_entities``), validates them
   (``hesa_rules``) and stores the XML, report and entity counts on the
   ``hesa_returns`` row. When there are no errors the XML is written to the
   ``hesa_jisc`` connector's batch folder for the registry to upload to the
   HESA Data Futures portal - this system does not submit it.

The XML follows the Data Futures entity hierarchy (Provider > Student >
Engagement > StudentCourseSession > SessionYear / ModuleInstance /
FundingAndMonitoring, with Leaver, QualificationAwarded and
EntryProfile/EntryQualificationAwarded under Engagement). Element names are
the Data Futures field names this system can source; check them against
the HESA coding manual for the year being returned.
"""

from __future__ import annotations

import csv
import io
import json
import re

# Builds XML only - never parses it - so the standard library is safe here.
import xml.etree.ElementTree as ET  # nosec B405  # nosemgrep: use-defused-xml

from education_system.systems.university.application import connectors
from education_system.systems.university.application.statutory import access as sa
from education_system.systems.university.application.statutory import (
    hesa_entities,
    hesa_rules,
)
from education_system.systems.university.infrastructure import institution_settings

RETURN_TYPE = "Student"
CONNECTOR = "hesa_jisc"
_YEAR = re.compile(r"^(\d{4})\s*[/-]\s*(\d{2}|\d{4})$")


def hesa_year(academic_year: str) -> tuple[str, str]:
    """``2025/26`` or ``2025/2026`` -> ("2025-08-01", "2026-07-31")."""
    m = _YEAR.match(str(academic_year or "").strip())
    if not m:
        raise ValueError("The academic year looks like 2025/26")
    start = int(m.group(1))
    end = int(m.group(2)) if len(m.group(2)) == 4 else (start // 100) * 100 + int(m.group(2))
    if end != start + 1:
        raise ValueError("The academic year must span two consecutive years")
    return f"{start}-08-01", f"{end}-07-31"


def _calendar_code(academic_year) -> str:
    start, end = hesa_year(academic_year)
    return f"{start[:4]}/{end[:4]}"


def reference_periods(academic_year: str) -> list[dict]:
    """The selectable reference periods: the whole year, then one ending on
    each ``census_hesa`` key date the calendar holds for that year."""
    start, end = hesa_year(academic_year)
    out = [{"label": f"Full year {academic_year}", "start": start, "end": end}]
    with sa.session() as conn:
        if not sa.has_table(conn, "calendar_key_dates"):
            return out
        rows = conn.execute(
            "SELECT title, start_date FROM calendar_key_dates WHERE kind = 'census_hesa' "
            "AND year_code = ? ORDER BY start_date", (_calendar_code(academic_year),)).fetchall()
    for title, day in rows:
        if start <= str(day)[:10] <= end:
            out.append({"label": f"{title} (to {str(day)[:10]})", "start": start,
                        "end": str(day)[:10]})
    return out


def _identifiers() -> dict:
    return {"UKPRN": institution_settings.require_statutory_identifier("ukprn"),
            "INSTID": institution_settings.require_statutory_identifier("hesa_provider_id")}


def _add(parent, tag, value) -> None:
    if value not in (None, ""):
        ET.SubElement(parent, tag).text = str(value)


def _public(entity: dict) -> dict:
    """Plain fields only (no nested entities, no ``_raw`` notes)."""
    return {k: v for k, v in entity.items()
            if not k.startswith("_") and not isinstance(v, (dict, list))}


def _fields(parent, tag, entity) -> ET.Element:
    elem = ET.SubElement(parent, tag)
    for key, value in _public(entity).items():
        _add(elem, key, value)
    return elem


def _engagement_xml(parent, eng) -> None:
    elem = _fields(parent, "Engagement", eng)
    for scs in eng["StudentCourseSession"]:
        s = _fields(elem, "StudentCourseSession", scs)
        _fields(s, "SessionYear", scs["SessionYear"])
        for mod in scs["ModuleInstance"]:
            _fields(s, "ModuleInstance", mod)
        _fields(s, "FundingAndMonitoring", scs["FundingAndMonitoring"])
    if eng["Leaver"]:
        _fields(elem, "Leaver", eng["Leaver"])
    for qual in eng["QualificationAwarded"]:
        _fields(elem, "QualificationAwarded", qual)
    entry = eng.get("EntryQualificationAwarded")
    if entry and entry.get("QUALTYPEID"):
        _fields(ET.SubElement(elem, "EntryProfile"), "EntryQualificationAwarded", entry)


def to_xml(students, ids, period, reference_period, generated_at) -> str:
    root = ET.Element("Submission")
    root.set("Collection", "HESA Data Futures Student")
    root.set("ReferencePeriod", reference_period or "")
    root.set("PeriodStart", period[0])
    root.set("PeriodEnd", period[1])
    root.set("GeneratedAt", generated_at)
    provider = ET.SubElement(root, "Provider")
    _add(provider, "UKPRN", ids["UKPRN"])
    _add(provider, "INSTID", ids["INSTID"])
    for s in students:
        elem = _fields(provider, "Student", s)
        for eng in s["Engagement"]:
            _engagement_xml(elem, eng)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _ensure_return(conn, who, return_id, academic_year) -> int:
    if return_id:
        row = sa.one(conn, "SELECT id, return_type, status FROM hesa_returns WHERE id = ?",
                     (return_id,))
        if not row:
            raise ValueError(f"No HESA return {return_id}")
        if row["status"] == "submitted":
            raise ValueError("That return is marked submitted; create a new one")
        return int(row["id"])
    return int(conn.execute(
        "INSERT INTO hesa_returns (academic_year, return_type, created_by) VALUES (?, ?, ?)",
        (academic_year, RETURN_TYPE, who.username)).lastrowid)


def _store(conn, who, return_id, payload) -> None:
    conn.execute(
        "UPDATE hesa_returns SET xml_data = ?, validation_json = ?, entity_counts_json = ?, "
        "reference_period = ?, period_start = ?, period_end = ?, built_at = ?, built_by = ?, "
        "status = ?, output_path = NULL WHERE id = ?",
        (payload["xml"], json.dumps(payload["report"]), json.dumps(payload["counts"]),
         payload["label"], payload["period"][0], payload["period"][1], payload["built_at"],
         who.username, payload["status"], return_id))
    conn.execute("INSERT INTO hesa_submission_log (return_id, action, details, performed_by) "
                 "VALUES (?, ?, ?, ?)",
                 (return_id, "Built Data Futures return",
                  f"{payload['counts']['Student']} students, {payload['report']['errors']} "
                  f"errors, {payload['report']['warnings']} warnings", who.username))


def build(current, academic_year, period_start=None, period_end=None, reference_period="",
          return_id=None) -> dict:
    """Build (or rebuild) a Data Futures return. Returns the summary with
    the validation report and, when there were no errors, the upload file."""
    who = sa.officer(current)
    ids = _identifiers()
    year = hesa_year(academic_year)
    period = (sa.iso_date(period_start, "Period start", False) or year[0],
              sa.iso_date(period_end, "Period end", False) or year[1])
    if period[1] < period[0]:
        raise ValueError("The reference period ends before it starts")
    built_at = sa.now()
    _ensure_hesa_tables()
    with sa.session() as conn:
        students = hesa_entities.collect(conn, period)
        report = hesa_rules.validate(students, period)
        payload = {"xml": to_xml(students, ids, period, reference_period, built_at),
                   "report": report, "counts": hesa_entities.counts(students),
                   "label": reference_period, "period": period, "built_at": built_at,
                   "status": "validated" if not report["errors"] else "draft"}
        rid = _ensure_return(conn, who, return_id, academic_year)
        _store(conn, who, rid, payload)
        sa.audit(conn, who, "hesa", "hesa_return", rid, "built",
                 {"period": period, "counts": payload["counts"], "errors": report["errors"]})
    path = None
    if not report["errors"]:
        path = _write(who, rid, academic_year, payload)
    return {"return_id": rid, "status": payload["status"], "counts": payload["counts"],
            "errors": report["errors"], "warnings": report["warnings"],
            "issues": report["issues"], "output_path": path}


def _write(who, rid, academic_year, payload) -> str:
    year = academic_year.replace("/", "-")
    name = f"HESA-DF-{year}-R{rid}-{sa.stamp()}.xml"
    path = connectors.write_batch(CONNECTOR, f"hesa-return-{rid}-{payload['built_at']}", name,
                                  payload["xml"])
    with sa.session() as conn:
        conn.execute("UPDATE hesa_returns SET output_path = ? WHERE id = ?", (path, rid))
        conn.execute("INSERT INTO hesa_submission_log (return_id, action, details, performed_by) "
                     "VALUES (?, ?, ?, ?)",
                     (rid, "Upload file written", path, who.username))
        sa.audit(conn, who, "hesa", "hesa_return", rid, "file_written", {"path": path})
    return path


def _ensure_hesa_tables() -> None:
    """The return tables are created by ``HESAExportService``; make sure
    they exist (before our own transaction opens) when the builder runs on
    its own."""
    with sa.session() as conn:
        present = sa.has_table(conn, "hesa_submission_log")
    if not present:
        from education_system.systems.university.domains.governance.domain.compliance.hesa_export.services.hesa_export_service import (  # noqa: E501
            HESAExportService,
        )
        HESAExportService()


def report(current, return_id) -> dict:
    """The stored validation report and counts for a return."""
    sa.officer(current)
    with sa.session() as conn:
        row = sa.one(conn, "SELECT * FROM hesa_returns WHERE id = ?", (return_id,))
    if not row:
        raise ValueError(f"No HESA return {return_id}")
    return {"return": {k: v for k, v in row.items() if k != "xml_data"},
            "report": json.loads(row.get("validation_json") or '{"issues": []}'),
            "counts": json.loads(row.get("entity_counts_json") or "{}")}


def report_csv(current, return_id) -> str:
    """The validation issues as CSV text, for the registry to work through."""
    issues = report(current, return_id)["report"].get("issues", [])
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["level", "student_id", "entity", "field",
                                             "message"])
    writer.writeheader()
    writer.writerows(issues)
    return buf.getvalue()


# ── HESA student identifiers (SID) ──────────────────────────────────────

_SID = re.compile(r"^\d{13}$")


def set_sid(current, student_id, sid) -> None:
    """Record the HESA SID for a student (13 digits, issued via HESA)."""
    who = sa.officer(current)
    sid = str(sid or "").strip()
    if not _SID.match(sid):
        raise ValueError("A HESA SID is 13 digits")
    with sa.session() as conn:
        if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                            (str(student_id),)).fetchone():
            raise ValueError(f"No student {student_id}")
        conn.execute(
            "INSERT INTO hesa_student_identifiers (student_id, sid, recorded_by) VALUES (?, ?, ?) "
            "ON CONFLICT(student_id) DO UPDATE SET sid = excluded.sid, "
            "recorded_by = excluded.recorded_by, recorded_at = datetime('now')",
            (str(student_id), sid, who.username))
        sa.audit(conn, who, "hesa", "sid", student_id, "set", {"sid": sid})


def import_sids(current, csv_text) -> dict:
    """CSV with ``student_id`` and ``sid`` columns. Returns counts and the
    rows refused with why."""
    sa.officer(current)
    done, refused = 0, []
    for line, row in enumerate(csv.DictReader(io.StringIO(csv_text)), start=2):
        try:
            set_sid(current, (row.get("student_id") or "").strip(), row.get("sid"))
            done += 1
        except ValueError as exc:
            refused.append({"line": line, "error": str(exc)})
    return {"recorded": done, "refused": refused}


def missing_sids(current, academic_year) -> list[dict]:
    """Students in the year's return with no SID yet."""
    sa.officer(current)
    with sa.session() as conn:
        students = hesa_entities.collect(conn, hesa_year(academic_year))
    return [{"student_id": s["OWNSTU"], "name": f"{s.get('FNAMES') or ''} "
             f"{s.get('SURNAME') or ''}".strip()} for s in students if not s.get("SID")]


__all__ = ["CONNECTOR", "RETURN_TYPE", "build", "hesa_year", "import_sids", "missing_sids",
           "reference_periods", "report", "report_csv", "set_sid", "to_xml"]
