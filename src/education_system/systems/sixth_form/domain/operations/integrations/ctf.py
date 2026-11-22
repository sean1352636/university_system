"""Common Transfer File (CTF) import and export.

The CTF is the DfE's XML format for moving a pupil's record between
schools. A sixth form receives one from each Year 11 feeder school at
intake and may send one when a learner leaves.

Structure handled (CTF spec, element names as published)::

    CTfile
      Header
        DocumentName, CTFversion, DateTime, DocumentQualifier,
        SourceSchool (LEA, Estab, SchoolName, AcademicYear),
        DestSchool (LEA, Estab)
      CTFpupilData
        Pupil
          UPN, UniqueLearnerNumber, UCI, Surname, Forename, MiddleNames,
          PreferredSurname, PreferredForename, DOB, Gender | Sex
            (any of these may instead sit inside a BasicDetails block)
          Address        (BS7666Address or AddressLines, PostCode)
          Contacts/Contact  (Order, Title, Surname, Forename, Relationship,
                             Responsibility, Phones/Phone, Email, Address,
                             AddressAsPupil)
          Attendance/YearData (Year, LEA, Estab, SessionsPossible,
                             SessionsAuthorised, SessionsUnauthorised,
                             AttendanceStartDate)
          StageAssessments/KeyStage (Stage, StageAssessment: Locale, Year,
                             Subject, Method, Component, ResultQualifier,
                             Result, ResultDate)
          SENhistory/SEN (StartDate, SENprovision, SENneeds/SENneed/Type)
          FSMhistory (FSMreviewDate, FSMinstance: FSMstartDate, FSMendDate,
                      UKcountry)

Every section except the pupil's name is optional and missing sections
are simply skipped. Nothing is ever invented: a field absent from the
file stays empty here. XML namespaces are stripped, and the file is
parsed with ``defusedxml`` (entity expansion and external entities are
refused) because CTFs arrive from outside the college.

Import is two steps: :func:`preview` (read-only: each pupil is *matched*
to an existing student, *new*, *conflict* or *invalid*) and :func:`apply`
(writes, through the students / parent_contacts public functions). An
applied file's SHA-256 is logged in ``ctf_imports`` and the same file is
refused a second time.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import importlib
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from education_system import paths
from education_system.systems.sixth_form.infrastructure.integrations import (
    store,
)

logger = logging.getLogger(__name__)

#: The CTF specification version written into exported files' headers.
CTF_VERSION = "24.0"
SUPPLIER_ID = "EducationSystem"

#: Destination codes the CTF uses when the receiving school is unknown
#: (the Lost Pupils Database) — the default for a leaver's export.
UNKNOWN_DEST_LA = "XXX"
UNKNOWN_DEST_ESTAB = "XXXX"

EXPORT_DIR = paths.SIXTH_FORM_DATA_DIR / "ctf_exports"

_UPN_RE = re.compile(r"^[A-Z]\d{11}[0-9A-Z]$")
_LA_RE = re.compile(r"^\d{3}$")
_ESTAB_RE = re.compile(r"^\d{4}$")

# CBDS "relationship to pupil" codes -> parent_contacts.RELATIONSHIPS.
# Codes that have no equivalent there become "Other" with the code kept
# in the contact's notes.
_REL_FROM_CTF: dict[str, str] = {
    "PAM": "Mother", "PAF": "Father", "PAR": "Parent",
    "STM": "Step-mother", "STF": "Step-father",
    "CAR": "Carer", "FOM": "Foster Carer", "FOF": "Foster Carer",
    "GRM": "Grandmother", "GRF": "Grandfather",
    "SWR": "Social Worker",
}
_REL_TO_CTF: dict[str, str] = {
    "Mother": "PAM", "Father": "PAF", "Parent": "PAR",
    "Step-mother": "STM", "Step-father": "STF", "Carer": "CAR",
    "Foster Carer": "CAR", "Grandmother": "GRM", "Grandfather": "GRF",
    "Social Worker": "SWR", "Guardian": "CAR",
    "Aunt": "REL", "Uncle": "REL", "Sibling": "FAM", "Other": "OTH",
}


class ValidationError(ValueError):
    """Bad input to an import/export."""


class AlreadyApplied(ValidationError):
    """This exact file (by SHA-256) has been applied before."""


# ── Parsed model ───────────────────────────────────────────────────

@dataclass
class CTFHeader:
    document_name: str | None = None
    version: str | None = None
    generated_at: str | None = None
    qualifier: str | None = None
    source_la: str | None = None
    source_estab: str | None = None
    source_name: str | None = None
    source_year: str | None = None
    dest_la: str | None = None
    dest_estab: str | None = None

    @property
    def source_label(self) -> str:
        code = f"{self.source_la or '?'}/{self.source_estab or '?'}"
        return f"{self.source_name} ({code})" if self.source_name else code


@dataclass
class CTFContact:
    order: int | None
    title: str | None
    surname: str | None
    forename: str | None
    relationship_code: str | None
    responsibility: bool | None
    phones: list[tuple[str | None, str]]
    email: str | None
    address: str | None

    @property
    def relationship(self) -> str:
        code = (self.relationship_code or "").strip()
        if code.upper() in _REL_FROM_CTF:
            return _REL_FROM_CTF[code.upper()]
        # Some suppliers write the word rather than the code.
        for rel in _REL_TO_CTF:
            if rel.lower() == code.lower():
                return rel
        return "Other"


@dataclass
class CTFAttendanceYear:
    year: str | None
    la: str | None
    estab: str | None
    possible: int | None
    authorised: int | None
    unauthorised: int | None
    start_date: str | None

    @property
    def percentage(self) -> float | None:
        if not self.possible:
            return None
        missed = (self.authorised or 0) + (self.unauthorised or 0)
        return round(100.0 * (self.possible - missed) / self.possible, 1)


@dataclass
class CTFResult:
    stage: str | None
    locale: str | None
    year: str | None
    subject: str | None
    method: str | None
    component: str | None
    qualifier: str | None
    result: str | None
    result_date: str | None


@dataclass
class CTFSen:
    start_date: str | None
    provision: str | None
    needs: list[str]


@dataclass
class CTFFsm:
    start_date: str | None
    end_date: str | None
    country: str | None
    review_date: str | None


@dataclass
class CTFPupil:
    index: int
    upn: str | None
    uln: str | None
    uci: str | None
    surname: str | None
    forename: str | None
    middle_names: str | None
    preferred_surname: str | None
    preferred_forename: str | None
    dob: str | None
    gender_code: str | None
    address: str | None
    contacts: list[CTFContact] = field(default_factory=list)
    attendance: list[CTFAttendanceYear] = field(default_factory=list)
    results: list[CTFResult] = field(default_factory=list)
    sen: list[CTFSen] = field(default_factory=list)
    fsm: list[CTFFsm] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.forename, self.middle_names,
                                    self.surname) if p)

    @property
    def gender(self) -> str | None:
        """students.GENDERS value, or None when the file gives none/unknown."""
        g = (self.gender_code or "").strip().upper()
        return {"M": "male", "F": "female", "MALE": "male",
                "FEMALE": "female"}.get(g)

    @property
    def ks4_results(self) -> list[CTFResult]:
        return [r for r in self.results
                if (r.stage or "").upper().replace(" ", "") == "KS4"]


@dataclass
class CTFFile:
    file_name: str
    sha256: str
    header: CTFHeader
    pupils: list[CTFPupil]


# ── Parsing ────────────────────────────────────────────────────────

def _strip_namespaces(root: ET.Element) -> None:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]


def _text(el: ET.Element | None, *paths_: str) -> str | None:
    """First non-blank text found at any of *paths_* under *el*."""
    if el is None:
        return None
    for p in paths_:
        found = el.find(p)
        if found is not None and found.text and found.text.strip():
            return found.text.strip()
    return None


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("true", "1", "yes", "y"):
        return True
    if v in ("false", "0", "no", "n"):
        return False
    return None


def _iso_date(value: str | None) -> str | None:
    """YYYY-MM-DD from a CTF date (which may carry a time part)."""
    if not value:
        return None
    s = value.strip()[:10]
    try:
        return _dt.date.fromisoformat(s).isoformat()
    except ValueError:
        return None


_BS7666_ORDER = ("SAON", "PAON", "Street", "Locality", "Town",
                 "AdministrativeArea", "PostTown", "County")


def _address(el: ET.Element | None) -> str | None:
    """One-line-per-part address text from a CTF Address block."""
    if el is None:
        return None
    lines: list[str] = []
    bs = el.find("BS7666Address")
    if bs is not None:
        for tag in _BS7666_ORDER:
            t = _text(bs, tag)
            if t:
                lines.append(t)
    al = el.find("AddressLines")
    if al is not None:
        for child in list(al):
            if child.text and child.text.strip():
                lines.append(child.text.strip())
    if not lines:
        # Flat address: AddressLine1..5 straight under Address.
        for child in list(el):
            if (isinstance(child.tag, str) and child.tag.startswith("AddressLine")
                    and child.text and child.text.strip()):
                lines.append(child.text.strip())
    pc = _text(el, "PostCode", "BS7666Address/PostCode",
               "AddressLines/PostCode")
    if pc and pc not in lines:
        lines.append(pc)
    return "\n".join(lines) or None


def _parse_contact(el: ET.Element, pupil_address: str | None) -> CTFContact:
    phones: list[tuple[str | None, str]] = []
    for ph in el.findall("Phones/Phone") + el.findall("Phone"):
        num = _text(ph, "PhoneNo", "TelephoneNumber", "Number")
        if num:
            phones.append((_text(ph, "TelephoneType", "Type"), num))
    email = _text(el, "Email/EmailAddress", "EmailAddress", "Email")
    if _bool(_text(el, "AddressAsPupil")):
        address = pupil_address
    else:
        address = _address(el.find("Address"))
    return CTFContact(
        order=_int(_text(el, "Order")),
        title=_text(el, "Title"),
        surname=_text(el, "Surname"),
        forename=_text(el, "Forename"),
        relationship_code=_text(el, "Relationship"),
        responsibility=_bool(_text(el, "Responsibility",
                                   "ParentalResponsibility")),
        phones=phones,
        email=email,
        address=address,
    )


def _parse_results(pupil: ET.Element) -> list[CTFResult]:
    out: list[CTFResult] = []
    # Results grouped by key stage (current spec) ...
    for ks in pupil.findall("StageAssessments/KeyStage"):
        stage = _text(ks, "Stage")
        for a in ks.findall("StageAssessment"):
            out.append(_result(a, stage))
    # ... or flat (older files), each assessment carrying its own stage.
    if not out:
        for a in pupil.iter("StageAssessment"):
            out.append(_result(a, _text(a, "Stage")))
    return [r for r in out if r.result or r.subject]


def _result(a: ET.Element, stage: str | None) -> CTFResult:
    return CTFResult(
        stage=stage,
        locale=_text(a, "Locale"),
        year=_text(a, "Year"),
        subject=_text(a, "Subject"),
        method=_text(a, "Method"),
        component=_text(a, "Component"),
        qualifier=_text(a, "ResultQualifier"),
        result=_text(a, "Result"),
        result_date=_iso_date(_text(a, "ResultDate")),
    )


def _parse_pupil(el: ET.Element, index: int) -> CTFPupil:
    def f(*names: str) -> str | None:
        paths_ = []
        for n in names:
            paths_ += [n, f"BasicDetails/{n}"]
        return _text(el, *paths_)

    upn = f("UPN")
    pupil_address = _address(el.find("Address"))
    p = CTFPupil(
        index=index,
        upn=upn.upper() if upn else None,
        uln=f("UniqueLearnerNumber", "ULN"),
        uci=f("UCI"),
        surname=f("Surname"),
        forename=f("Forename"),
        middle_names=f("MiddleNames"),
        preferred_surname=f("PreferredSurname"),
        preferred_forename=f("PreferredForename"),
        dob=_iso_date(f("DOB")),
        gender_code=f("Gender", "Sex"),
        address=pupil_address,
    )
    for c in el.findall("Contacts/Contact"):
        p.contacts.append(_parse_contact(c, pupil_address))
    for y in el.findall("Attendance/YearData"):
        p.attendance.append(CTFAttendanceYear(
            year=_text(y, "Year"), la=_text(y, "LEA"),
            estab=_text(y, "Estab"),
            possible=_int(_text(y, "SessionsPossible")),
            authorised=_int(_text(y, "SessionsAuthorised")),
            unauthorised=_int(_text(y, "SessionsUnauthorised")),
            start_date=_iso_date(_text(y, "AttendanceStartDate")),
        ))
    p.results = _parse_results(el)
    for s in el.findall("SENhistory/SEN"):
        needs = [t.text.strip() for t in s.findall("SENneeds/SENneed/Type")
                 if t.text and t.text.strip()]
        p.sen.append(CTFSen(start_date=_iso_date(_text(s, "StartDate")),
                            provision=_text(s, "SENprovision"), needs=needs))
    fsm_root = el.find("FSMhistory")
    if fsm_root is not None:
        review = _iso_date(_text(fsm_root, "FSMreviewDate"))
        for i in fsm_root.findall("FSMinstance"):
            p.fsm.append(CTFFsm(
                start_date=_iso_date(_text(i, "FSMstartDate")),
                end_date=_iso_date(_text(i, "FSMendDate")),
                country=_text(i, "UKcountry"), review_date=review))
    return p


def parse_bytes(raw: bytes, file_name: str = "ctf.xml") -> CTFFile:
    """Parse CTF XML bytes. Raises ValidationError if it is not a CTF."""
    try:
        from defusedxml import ElementTree as SafeET
        root = SafeET.fromstring(raw)
    except ImportError:  # pragma: no cover - defusedxml is a dependency
        if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
            raise ValidationError(
                "CTF contains a DOCTYPE/ENTITY declaration; refused") from None
        root = ET.fromstring(raw)  # noqa: S314 - DTDs refused above
    except Exception as e:
        raise ValidationError(f"Not valid XML: {e}") from None
    _strip_namespaces(root)
    if root.tag.lower() != "ctfile":
        raise ValidationError(
            f"Not a Common Transfer File (root element is <{root.tag}>, "
            "expected <CTfile>)")
    h = root.find("Header")
    header = CTFHeader(
        document_name=_text(h, "DocumentName"),
        version=_text(h, "CTFversion"),
        generated_at=_text(h, "DateTime"),
        qualifier=_text(h, "DocumentQualifier"),
        source_la=_text(h, "SourceSchool/LEA"),
        source_estab=_text(h, "SourceSchool/Estab"),
        source_name=_text(h, "SourceSchool/SchoolName"),
        source_year=_text(h, "SourceSchool/AcademicYear"),
        dest_la=_text(h, "DestSchool/LEA"),
        dest_estab=_text(h, "DestSchool/Estab"),
    )
    pupils = [_parse_pupil(el, i)
              for i, el in enumerate(root.findall("CTFpupilData/Pupil"))]
    return CTFFile(file_name=file_name,
                   sha256=hashlib.sha256(raw).hexdigest(),
                   header=header, pupils=pupils)


def parse_file(path: str | Path) -> CTFFile:
    p = Path(path)
    if not p.is_file():
        raise ValidationError(f"No such file: {p}")
    return parse_bytes(p.read_bytes(), p.name)


# ── Preview / matching ─────────────────────────────────────────────

STATUS_MATCHED = "matched"
STATUS_NEW = "new"
STATUS_CONFLICT = "conflict"
STATUS_INVALID = "invalid"


@dataclass
class PreviewRow:
    pupil: CTFPupil
    status: str
    student_id: str | None = None
    match_basis: str | None = None
    candidates: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ImportPreview:
    file: CTFFile
    rows: list[PreviewRow]
    applied_import_id: int | None   # set when this file was applied before

    def count(self, status: str) -> int:
        return sum(1 for r in self.rows if r.status == status)


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return students


def _identifiers():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        identifiers,
    )
    return identifiers


def student_for_upn(upn: str) -> str | None:
    store.init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT student_id FROM ctf_upn_links WHERE upn = ?",
                         ((upn or "").strip().upper(),)).fetchone()
    return r["student_id"] if r else None


def upn_for_student(student_id: str) -> str | None:
    store.init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT upn FROM ctf_upn_links WHERE student_id = ?",
                         (student_id,)).fetchone()
    return r["upn"] if r else None


def upns_by_student() -> dict[str, str]:
    """Every linked UPN, keyed by student id, in one read."""
    store.init_db()
    with store.connect() as conn:
        rows = conn.execute("SELECT student_id, upn FROM ctf_upn_links").fetchall()
    return {r["student_id"]: r["upn"] for r in rows}


def set_student_upn(student_id: str, upn: str | None, *,
                    source: str = "manual") -> None:
    """Make *upn* the student's UPN (None removes it).

    A UPN belongs to one learner: raises ValueError if another student
    already holds it. Validation of the UPN itself is the caller's.
    """
    store.init_db()
    with store.connect() as conn:
        if upn:
            other = conn.execute(
                "SELECT student_id FROM ctf_upn_links WHERE upn = ?",
                (upn,)).fetchone()
            if other and other["student_id"] != student_id:
                raise ValueError(
                    f"UPN {upn} already belongs to {other['student_id']}")
        conn.execute("DELETE FROM ctf_upn_links WHERE student_id = ?",
                     (student_id,))
        if upn:
            conn.execute("INSERT INTO ctf_upn_links (upn, student_id, source) "
                         "VALUES (?, ?, ?)", (upn, student_id, source))
        conn.commit()


def _applied_import_id(sha: str) -> int | None:
    store.init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT import_id FROM ctf_imports WHERE file_sha256 = ?",
                         (sha,)).fetchone()
    return r["import_id"] if r else None


def _match(p: CTFPupil, seen_upns: set[str]) -> PreviewRow:
    st = _students()
    row = PreviewRow(pupil=p, status=STATUS_NEW)
    if not p.surname or not p.forename:
        row.status = STATUS_INVALID
        row.notes.append("Surname and forename are required")
        return row
    if not p.dob:
        row.notes.append("No (valid) date of birth in the file")
    if p.upn and not _UPN_RE.match(p.upn):
        row.notes.append(f"UPN {p.upn} is not in the 13-character UPN format")
    if p.upn and p.upn in seen_upns:
        row.status = STATUS_CONFLICT
        row.notes.append(f"UPN {p.upn} appears more than once in this file")
        return row
    if p.upn:
        seen_upns.add(p.upn)

    uln_ok = bool(p.uln) and _identifiers().is_valid_uln(p.uln)
    if p.uln and not uln_ok:
        row.notes.append(f"ULN {p.uln} fails the LRS check digit; it will not be stored")

    by_upn = student_for_upn(p.upn) if p.upn else None
    by_uln_s = st.find_by_uln(p.uln) if uln_ok else None
    by_uln = by_uln_s.student_id if by_uln_s else None
    by_name: list[str] = []
    if p.dob:
        for s in st.search_students(p.surname):
            if (s.last_name.strip().lower() == p.surname.lower()
                    and s.first_name.strip().lower() == p.forename.lower()
                    and s.date_of_birth == p.dob):
                by_name.append(s.student_id)
    row.candidates = sorted({x for x in [by_upn, by_uln, *by_name] if x})

    def _check(sid: str, basis: str) -> PreviewRow:
        s = st.get_student(sid)
        if s is None:
            row.status = STATUS_CONFLICT
            row.notes.append(f"{basis} points at {sid}, which no longer exists")
            return row
        if s.date_of_birth and p.dob and s.date_of_birth != p.dob:
            row.status = STATUS_CONFLICT
            row.notes.append(
                f"{basis} matches {sid} but the date of birth differs "
                f"({s.date_of_birth} on record, {p.dob} in file)")
            return row
        linked = upn_for_student(sid)
        if p.upn and linked and linked != p.upn:
            row.status = STATUS_CONFLICT
            row.notes.append(f"{sid} is already linked to a different UPN ({linked})")
            return row
        if s.uln and uln_ok and s.uln != p.uln:
            row.status = STATUS_CONFLICT
            row.notes.append(f"{sid} already has a different ULN ({s.uln})")
            return row
        row.status = STATUS_MATCHED
        row.student_id = sid
        row.match_basis = basis
        if (s.last_name.lower() != p.surname.lower()
                or s.first_name.lower() != p.forename.lower()):
            row.notes.append(
                f"Name differs: '{s.full_name}' on record, '{p.full_name}' in "
                "file (record name is kept)")
        return row

    if by_upn:
        if by_uln and by_uln != by_upn:
            row.status = STATUS_CONFLICT
            row.notes.append(f"UPN matches {by_upn} but ULN matches {by_uln}")
            return row
        return _check(by_upn, "UPN")
    if by_uln:
        return _check(by_uln, "ULN")
    if len(by_name) > 1:
        row.status = STATUS_CONFLICT
        row.notes.append("Name and date of birth match more than one student: "
                         + ", ".join(by_name))
        return row
    if by_name:
        return _check(by_name[0], "name + DOB")
    return row


def preview_file(ctf: CTFFile) -> ImportPreview:
    """Match every pupil in a parsed CTF. Read-only."""
    store.init_db()
    seen: set[str] = set()
    rows = [_match(p, seen) for p in ctf.pupils]
    return ImportPreview(file=ctf, rows=rows,
                         applied_import_id=_applied_import_id(ctf.sha256))


def preview(path: str | Path) -> ImportPreview:
    return preview_file(parse_file(path))


# ── Prior attainment hand-off ──────────────────────────────────────

# KS4 results are handed to qualifications.prior_attainment.add_result
# (looked up at run time, so this module still works if that store is
# absent). A result it cannot take - not identifiably a GCSE, or a grade
# it does not accept - stays in ctf_import_results with forwarded_to NULL
# and is listed by pending_results(); forward_pending_results() retries.
_PRIOR_MODULE = (
    "education_system.systems.sixth_form.domain.academics.qualifications.prior_attainment"
)
_PRIOR_FUNCTION = "add_result"

#: CTF KS4 subject codes we can name with confidence. Other codes are
#: passed through unchanged (and noted) rather than guessed at.
_SUBJECT_NAMES: dict[str, str] = {"MAT": "Mathematics", "ENG": "English"}
_GCSE_91 = {"9", "8", "7", "6", "5", "4", "3", "2", "1"}


def prior_attainment_sink() -> tuple[str, Callable[..., Any]] | None:
    """(dotted name, function) of the prior-attainment writer, if present."""
    try:
        mod = importlib.import_module(_PRIOR_MODULE)
    except ImportError:
        return None
    fn = getattr(mod, _PRIOR_FUNCTION, None)
    return (f"{_PRIOR_MODULE}.{_PRIOR_FUNCTION}", fn) if callable(fn) else None


def _gcse_kind(r: dict[str, Any]) -> str | None:
    """'GCSE' / 'IGCSE' / 'GCSE short course', or None if not a GCSE."""
    label = f"{r.get('component') or ''} {r.get('method') or ''}".upper()
    if "IGCSE" in label:
        return "IGCSE"
    if "GCSE" in label:
        return "GCSE short course" if "SHORT" in label else "GCSE"
    # Numeric 9-1 grades are only awarded for GCSEs.
    if (r.get("result") or "").strip() in _GCSE_91 and not label.strip():
        return "GCSE"
    return None


def _forward(sink: tuple[str, Callable[..., Any]], student_id: str,
             r: dict[str, Any]) -> bool:
    name, fn = sink
    kind = _gcse_kind(r)
    if kind is None or not r.get("subject") or not r.get("result"):
        return False
    code = (r["subject"] or "").strip()
    year = (r.get("year") or "").strip()
    try:
        fn(student_id, {
            "subject": _SUBJECT_NAMES.get(code.upper(), code),
            "grade": r["result"], "kind": kind,
            "year": int(year) if year.isdigit() and len(year) == 4 else None,
            "notes": f"Imported from CTF (subject code {code})",
        })
        return True
    except Exception as e:
        logger.warning("Prior-attainment hand-off to %s refused %s %s for %s "
                       "(raw result kept): %s", name, code, r.get("result"),
                       student_id, e)
        return False


def forward_pending_results() -> tuple[int, int]:
    """Hand unforwarded KS4 results to the prior-attainment store.

    Returns (forwarded, still pending). Raises ValidationError when no
    prior-attainment store exists yet.
    """
    store.require("STUDENTS_MANAGE", "prior attainment import")
    sink = prior_attainment_sink()
    if sink is None:
        raise ValidationError(
            "No prior-attainment store is available yet; results stay listed "
            "under 'Pending results'")
    done = 0
    with store.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ctf_import_results WHERE forwarded_to IS NULL "
            "AND upper(replace(coalesce(stage,''),' ','')) = 'KS4'").fetchall()
    for r in rows:
        if _forward(sink, r["student_id"], dict(r)):
            with store.connect() as conn:
                conn.execute(
                    "UPDATE ctf_import_results SET forwarded_to = ?, "
                    "forwarded_at = datetime('now') WHERE result_id = ?",
                    (sink[0], r["result_id"]))
                conn.commit()
            done += 1
    return done, len(rows) - done


# ── Apply ──────────────────────────────────────────────────────────

#: Resolution values for :func:`apply`: a student_id, or one of these.
RESOLVE_NEW = "new"
RESOLVE_SKIP = "skip"


@dataclass
class PupilOutcome:
    index: int
    name: str
    action: str           # created / updated / unchanged / skipped / error
    student_id: str | None
    notes: list[str]


@dataclass
class ApplyResult:
    import_id: int
    outcomes: list[PupilOutcome]

    def count(self, action: str) -> int:
        return sum(1 for o in self.outcomes if o.action == action)


def _pupil_fields(p: CTFPupil) -> tuple[tuple[str, str | None], ...]:
    """The student-record fields a CTF can supply, by record key."""
    preferred = p.preferred_forename if (
        p.preferred_forename and p.preferred_forename != p.forename) else None
    return (("middle_name", p.middle_names), ("gender", p.gender),
            ("date_of_birth", p.dob), ("preferred_name", preferred),
            ("address", p.address))


def _create_from_pupil(p: CTFPupil) -> str:
    st = _students()
    # The preview has already matched the file against the college's
    # learners, and a person chose "new" for this pupil, so the record
    # module's own duplicate check is not asked again; any match it finds
    # is noted in the new record's history.
    s = st.create_student(allow_duplicate=True, data={
        "first_name": p.forename, "last_name": p.surname, "status": "Active",
        **{k: v for k, v in _pupil_fields(p) if v},
    })
    return s.student_id


def _fill_blanks(student_id: str, p: CTFPupil, notes: list[str]) -> bool:
    """Fill empty middle name, gender, DOB, preferred name and address from
    the file. True if changed."""
    st = _students()
    s = st.get_student(student_id)
    payload: dict[str, Any] = {}
    for key, value in _pupil_fields(p):
        if value and not getattr(s, key, None):
            payload[key] = value
    changed = list(payload)
    if not changed:
        return False
    try:
        # update_student keeps every field not in the payload.
        st.update_student(student_id, payload)
    except Exception as e:
        notes.append(f"Could not fill {', '.join(changed)}: {e}")
        return False
    notes.append("Filled " + ", ".join(changed))
    return True


def _link_upn(conn, student_id: str, upn: str, source: str,
              notes: list[str]) -> None:
    other = conn.execute("SELECT student_id FROM ctf_upn_links WHERE upn = ?",
                         (upn,)).fetchone()
    if other and other["student_id"] != student_id:
        notes.append(f"UPN {upn} already linked to {other['student_id']}; not linked")
        return
    mine = conn.execute("SELECT upn FROM ctf_upn_links WHERE student_id = ?",
                        (student_id,)).fetchone()
    if mine and mine["upn"] != upn:
        notes.append(f"Student already linked to UPN {mine['upn']}; kept")
        return
    if not other:
        conn.execute("INSERT INTO ctf_upn_links (upn, student_id, source) "
                     "VALUES (?, ?, ?)", (upn, student_id, source))


def _set_identifiers(student_id: str, p: CTFPupil, notes: list[str]) -> None:
    st = _students()
    s = st.get_student(student_id)
    kw: dict[str, str] = {}
    if p.uln and not s.uln and _identifiers().is_valid_uln(p.uln):
        kw["uln"] = p.uln
    if p.uci and not s.uci:
        try:
            kw["uci"] = _identifiers().validate_uci(p.uci) or ""
        except ValueError as e:
            notes.append(f"UCI not stored: {e}")
    kw = {k: v for k, v in kw.items() if v}
    if not kw:
        return
    try:
        st.set_identifiers(student_id, **kw)
        notes.append("Set " + ", ".join(k.upper() for k in kw))
    except Exception as e:
        notes.append(f"Identifiers not stored: {e}")


def _parent_contacts():
    try:
        from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
            parent_contacts,
        )
    except ImportError:
        return None
    needed = ("contacts_for_student", "create_contact")
    return parent_contacts if all(hasattr(parent_contacts, n) for n in needed) else None


def _import_contacts(student_id: str, p: CTFPupil, notes: list[str]) -> None:
    if not p.contacts:
        return
    pc = _parent_contacts()
    if pc is None:
        notes.append("Parent contacts module unavailable; contacts not imported")
        return
    existing = pc.contacts_for_student(student_id)
    names = {(c.first_name.lower(), c.last_name.lower()) for c in existing}
    has_primary = any(c.is_primary for c in existing)
    added = 0
    for c in sorted(p.contacts, key=lambda c: (c.order is None, c.order or 0)):
        if not c.forename or not c.surname:
            notes.append("Skipped a contact with no name")
            continue
        label = f"{c.forename} {c.surname}"
        if (c.forename.lower(), c.surname.lower()) in names:
            continue
        numbers = [n for _t, n in c.phones]
        if not numbers and not c.email:
            notes.append(f"Contact {label} has no phone or email in the file; not added")
            continue
        rel = c.relationship
        code_note = (f"CTF relationship code {c.relationship_code}"
                     if rel == "Other" and c.relationship_code else None)
        data = {
            "student_id": student_id, "relationship": rel,
            "title": c.title, "first_name": c.forename,
            "last_name": c.surname, "email": c.email,
            "primary_phone": numbers[0] if numbers else None,
            "secondary_phone": numbers[1] if len(numbers) > 1 else None,
            "address": c.address,
            "preferred_method": "Email" if c.email else "Phone (primary)",
            "is_primary": not has_primary,
            "has_parental_responsibility": (
                c.responsibility if c.responsibility is not None else False),
            "notes": "; ".join(x for x in ("Imported from CTF", code_note) if x),
        }
        try:
            pc.create_contact(data)
        except Exception as e:
            notes.append(f"Contact {label} not added: {e}")
            continue
        has_primary = True
        names.add((c.forename.lower(), c.surname.lower()))
        added += 1
    if added:
        notes.append(f"Added {added} contact(s)")


def _store_history(conn, import_id: int, student_id: str, p: CTFPupil
                   ) -> list[tuple[int, dict[str, Any]]]:
    """Insert the pupil's history rows; return (result_id, result) for KS4."""
    for a in p.attendance:
        conn.execute(
            "INSERT INTO ctf_import_attendance (import_id, student_id, year, "
            "source_la, source_estab, sessions_possible, sessions_authorised, "
            "sessions_unauthorised, start_date) VALUES (?,?,?,?,?,?,?,?,?)",
            (import_id, student_id, a.year, a.la, a.estab, a.possible,
             a.authorised, a.unauthorised, a.start_date))
    for s in p.sen:
        conn.execute(
            "INSERT INTO ctf_import_sen (import_id, student_id, start_date, "
            "provision, needs) VALUES (?,?,?,?,?)",
            (import_id, student_id, s.start_date, s.provision,
             ", ".join(s.needs) or None))
    for f in p.fsm:
        conn.execute(
            "INSERT INTO ctf_import_fsm (import_id, student_id, start_date, "
            "end_date, country, review_date) VALUES (?,?,?,?,?,?)",
            (import_id, student_id, f.start_date, f.end_date, f.country,
             f.review_date))
    ks4: list[tuple[int, dict[str, Any]]] = []
    for r in p.results:
        cur = conn.execute(
            "INSERT INTO ctf_import_results (import_id, student_id, stage, "
            "locale, year, subject, method, component, result_qualifier, "
            "result, result_date) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (import_id, student_id, r.stage, r.locale, r.year, r.subject,
             r.method, r.component, r.qualifier, r.result, r.result_date))
        if (r.stage or "").upper().replace(" ", "") == "KS4":
            ks4.append((cur.lastrowid, dict(r.__dict__)))
    return ks4


def _after_history(import_id: int, student_id: str, p: CTFPupil, sink,
                   ks4: list[tuple[int, dict[str, Any]]],
                   notes: list[str]) -> None:
    """Steps that write through other modules: run after our commit, so
    no connection of ours is holding the write lock."""
    forwarded = 0
    if sink is not None:
        for result_id, r in ks4:
            if _forward(sink, student_id, r):
                with store.connect() as conn:
                    conn.execute(
                        "UPDATE ctf_import_results SET forwarded_to = ?, "
                        "forwarded_at = datetime('now') WHERE result_id = ?",
                        (sink[0], result_id))
                    conn.commit()
                forwarded += 1
    if p.sen or p.fsm:
        from education_system.systems.sixth_form.domain.governance.user_management import (
            access,
        )
        access.log_sensitive_access(
            access.current(), "send" if p.sen else "funding",
            "import CTF SEN/FSM history", student_id=student_id,
            record_ref=f"ctf_import:{import_id}")
    if p.results:
        pending = len(ks4) - forwarded
        msg = f"Stored {len(p.results)} assessment result(s)"
        if forwarded:
            msg += f", {forwarded} passed to prior attainment"
        if pending:
            msg += (f", {pending} KS4 result(s) listed as pending"
                    + (" (no prior-attainment store)" if sink is None else ""))
        notes.append(msg)


def apply(path: str | Path, resolutions: dict[int, str] | None = None
          ) -> ApplyResult:
    """Apply a CTF. *resolutions* maps pupil index -> student_id / 'new' / 'skip'.

    Matched pupils are updated (blank fields only), new pupils are
    created, conflicts without a resolution and invalid rows are skipped.
    """
    who = store.require("STUDENTS_MANAGE", "CTF import")
    ctf = parse_file(path)
    pv = preview_file(ctf)
    if pv.applied_import_id is not None:
        raise AlreadyApplied(
            f"This file was already applied (import #{pv.applied_import_id})")
    resolutions = resolutions or {}
    st = _students()
    sink = prior_attainment_sink()
    h = ctf.header
    with store.connect() as conn:
        cur = conn.execute(
            "INSERT INTO ctf_imports (file_name, file_sha256, ctf_version, "
            "generated_at, source_la, source_estab, source_name, pupil_count, "
            "applied_by) VALUES (?,?,?,?,?,?,?,?,?)",
            (ctf.file_name, ctf.sha256, h.version, h.generated_at, h.source_la,
             h.source_estab, h.source_name, len(ctf.pupils), who))
        import_id = cur.lastrowid
        conn.commit()

    outcomes: list[PupilOutcome] = []
    for row in pv.rows:
        p = row.pupil
        notes = list(row.notes)
        action, sid = "skipped", None
        res = resolutions.get(p.index)
        try:
            if res == RESOLVE_SKIP or row.status == STATUS_INVALID:
                notes.append("Skipped")
            elif res == RESOLVE_NEW or (res is None and row.status == STATUS_NEW):
                sid = _create_from_pupil(p)
                action = "created"
            elif res or row.status == STATUS_MATCHED:
                sid = res or row.student_id
                if st.get_student(sid) is None:
                    raise ValidationError(f"No student with id {sid}")
                action = "updated" if _fill_blanks(sid, p, notes) else "unchanged"
            else:
                notes.append("Conflict not resolved; skipped")
            if sid:
                _set_identifiers(sid, p, notes)
                _import_contacts(sid, p, notes)
                with store.connect() as conn:
                    if p.upn and _UPN_RE.match(p.upn):
                        _link_upn(conn, sid, p.upn,
                                  f"CTF import #{import_id}", notes)
                    ks4 = _store_history(conn, import_id, sid, p)
                    conn.commit()
                _after_history(import_id, sid, p, sink, ks4, notes)
        except Exception as e:
            logger.exception("CTF import #%s: pupil %d failed", import_id, p.index)
            notes.append(f"Error: {e}")
            action = "error"
        with store.connect() as conn:
            conn.execute(
                "INSERT INTO ctf_import_pupils (import_id, upn, surname, "
                "forename, dob, student_id, action, notes, address) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (import_id, p.upn, p.surname, p.forename, p.dob,
                 sid if sid and st.get_student(sid) else None, action,
                 "; ".join(notes) or None, p.address))
            conn.commit()
        outcomes.append(PupilOutcome(p.index, p.full_name, action, sid, notes))

    result = ApplyResult(import_id=import_id, outcomes=outcomes)
    with store.connect() as conn:
        conn.execute(
            "UPDATE ctf_imports SET created_count = ?, updated_count = ?, "
            "skipped_count = ? WHERE import_id = ?",
            (result.count("created"),
             result.count("updated") + result.count("unchanged"),
             result.count("skipped") + result.count("error"), import_id))
        conn.commit()
    logger.info("CTF import #%d (%s) applied by %s: %d created, %d updated, "
                "%d skipped/errors", import_id, ctf.file_name, who,
                result.count("created"),
                result.count("updated") + result.count("unchanged"),
                result.count("skipped") + result.count("error"))
    return result


# ── Import history / stored data ───────────────────────────────────

def list_imports() -> list[dict[str, Any]]:
    store.init_db()
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ctf_imports ORDER BY import_id DESC").fetchall()]


def import_pupils(import_id: int) -> list[dict[str, Any]]:
    store.init_db()
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ctf_import_pupils WHERE import_id = ? ORDER BY row_id",
            (import_id,)).fetchall()]


def pending_results() -> list[dict[str, Any]]:
    """KS4 results kept raw because no prior-attainment store took them."""
    store.init_db()
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT r.*, s.first_name || ' ' || s.last_name AS student_name "
            "FROM ctf_import_results r JOIN students s USING (student_id) "
            "WHERE r.forwarded_to IS NULL "
            "AND upper(replace(coalesce(r.stage,''),' ','')) = 'KS4' "
            "ORDER BY s.last_name, s.first_name, r.subject").fetchall()]


def results_for_student(student_id: str) -> list[dict[str, Any]]:
    store.init_db()
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ctf_import_results WHERE student_id = ? "
            "ORDER BY stage, subject", (student_id,)).fetchall()]


def attendance_for_student(student_id: str) -> list[dict[str, Any]]:
    store.init_db()
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ctf_import_attendance WHERE student_id = ? "
            "ORDER BY year", (student_id,)).fetchall()]


def _sensitive(capability: str, area: str, student_id: str) -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    cap = getattr(access, capability)
    allowed = p.can(cap) and access.can_see_student(p, student_id, capability=cap)
    access.log_sensitive_access(p, area, "view CTF history",
                                student_id=student_id, allowed=allowed)
    if not allowed:
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not see {area} history "
            f"for student {student_id}.")


def sen_for_student(student_id: str) -> list[dict[str, Any]]:
    """SEN history from imported CTFs (SEND capability, access logged)."""
    store.init_db()
    _sensitive("SEND", "send", student_id)
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ctf_import_sen WHERE student_id = ? "
            "ORDER BY start_date", (student_id,)).fetchall()]


def fsm_for_student(student_id: str) -> list[dict[str, Any]]:
    """FSM history from imported CTFs (FUNDING capability, access logged)."""
    store.init_db()
    _sensitive("FUNDING", "funding", student_id)
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ctf_import_fsm WHERE student_id = ? "
            "ORDER BY start_date", (student_id,)).fetchall()]


# ── Export ─────────────────────────────────────────────────────────

def list_leavers() -> list:
    """Students whose record status is 'Left' (candidates for export)."""
    return [s for s in _students().list_students() if s.status == "Left"]


def _school_identity() -> tuple[str, str, str]:
    la = store.get_setting("school_la")
    estab = store.get_setting("school_estab")
    name = store.get_setting("school_name")
    if not _LA_RE.match(la or "") or not _ESTAB_RE.match(estab or ""):
        raise ValidationError(
            "Set the college's 3-digit LA number and 4-digit establishment "
            "number (Settings tab) before exporting a CTF")
    return la, estab, name


def _academic_year_start(today: _dt.date) -> int:
    return today.year if today.month >= 9 else today.year - 1


def _sub(parent: ET.Element, tag: str, text: Any = None) -> ET.Element:
    el = ET.SubElement(parent, tag)
    if text not in (None, ""):
        el.text = str(text)
    return el


def build_leaver_xml(student_id: str, *, dest_la: str = UNKNOWN_DEST_LA,
                     dest_estab: str = UNKNOWN_DEST_ESTAB) -> bytes:
    """The CTF XML for one leaver (no file written)."""
    st = _students()
    s = st.get_student(student_id)
    if s is None:
        raise ValidationError(f"No student with id {student_id}")
    if s.status != "Left":
        raise ValidationError(
            f"{student_id} is not a leaver (status {s.status}); set the record "
            "to 'Left' first")
    dest_la = (dest_la or UNKNOWN_DEST_LA).strip().upper()
    dest_estab = (dest_estab or UNKNOWN_DEST_ESTAB).strip().upper()
    if not (_LA_RE.match(dest_la) or dest_la in ("XXX", "MMM")):
        raise ValidationError("Destination LA must be 3 digits, XXX or MMM")
    if not (_ESTAB_RE.match(dest_estab) or dest_estab in ("XXXX", "MMMM")):
        raise ValidationError("Destination establishment must be 4 digits, XXXX or MMMM")
    la, estab, school_name = _school_identity()
    now = _dt.datetime.now().replace(microsecond=0)
    year0 = _academic_year_start(now.date())

    root = ET.Element("CTfile")
    h = _sub(root, "Header")
    _sub(h, "DocumentName", "Common Transfer File")
    _sub(h, "CTFversion", CTF_VERSION)
    _sub(h, "DateTime", now.isoformat())
    _sub(h, "DocumentQualifier", "partial")
    _sub(h, "SupplierID", SUPPLIER_ID)
    src = _sub(h, "SourceSchool")
    _sub(src, "LEA", la)
    _sub(src, "Estab", estab)
    _sub(src, "SchoolName", school_name)
    _sub(src, "AcademicYear", year0 + 1)
    dst = _sub(h, "DestSchool")
    _sub(dst, "LEA", dest_la)
    _sub(dst, "Estab", dest_estab)

    pupil = _sub(_sub(root, "CTFpupilData"), "Pupil")
    _sub(pupil, "UPN", upn_for_student(student_id))
    _sub(pupil, "UniqueLearnerNumber", s.uln)
    _sub(pupil, "UCI", s.uci)
    _sub(pupil, "Surname", s.last_name)
    _sub(pupil, "Forename", s.first_name)
    _sub(pupil, "MiddleNames", s.middle_name)
    _sub(pupil, "DOB", s.date_of_birth)
    _sub(pupil, "Gender", {"male": "M", "female": "F"}.get(s.gender or ""))
    for child in list(pupil):
        if child.text is None:
            pupil.remove(child)

    pc = _parent_contacts()
    contacts = pc.contacts_for_student(student_id) if pc else []
    if contacts:
        cs = _sub(pupil, "Contacts")
        ordered = sorted(contacts, key=lambda c: (not c.is_primary, c.contact_id))
        for i, c in enumerate(ordered, 1):
            ce = _sub(cs, "Contact")
            _sub(ce, "Order", i)
            if c.title:
                _sub(ce, "Title", c.title)
            _sub(ce, "Surname", c.last_name)
            _sub(ce, "Forename", c.first_name)
            _sub(ce, "Relationship", _REL_TO_CTF.get(c.relationship, "OTH"))
            _sub(ce, "Responsibility",
                 "true" if c.has_parental_responsibility else "false")
            phones = [p for p in (c.primary_phone, c.secondary_phone) if p]
            if phones:
                pe = _sub(ce, "Phones")
                for num in phones:
                    ph = _sub(pe, "Phone")
                    _sub(ph, "PhoneNo", num)
            if c.email:
                _sub(ce, "Email", c.email)
            if c.address:
                ad = _sub(_sub(ce, "Address"), "AddressLines")
                for n, line in enumerate(
                        [x.strip() for x in re.split(r"[\n,]", c.address)
                         if x.strip()][:5], 1):
                    _sub(ad, f"AddressLine{n}", line)

    # Attendance: the sixth form registers lessons, not AM/PM sessions,
    # so these counts are register marks (Present/Late = attended,
    # Authorised, Absent = unauthorised) for each academic year.
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance,
    )
    years = []
    for y in (year0 - 1, year0):
        summ = attendance.summary_for_student(
            student_id, date_from=f"{y}-09-01", date_to=f"{y + 1}-08-31")
        if summ.total:
            years.append((y, summ))
    if years:
        att = _sub(pupil, "Attendance")
        att.append(ET.Comment(
            " Counts are lesson register marks, not AM/PM sessions "))
        for y, summ in years:
            yd = _sub(att, "YearData")
            _sub(yd, "Year", y)
            _sub(yd, "LEA", la)
            _sub(yd, "Estab", estab)
            _sub(yd, "SessionsPossible", summ.total)
            _sub(yd, "SessionsAuthorised", summ.authorised)
            _sub(yd, "SessionsUnauthorised", summ.absent)

    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@dataclass
class ExportResult:
    export_id: int
    path: Path
    sha256: str


def export_leaver(student_id: str, *, dest_la: str = UNKNOWN_DEST_LA,
                  dest_estab: str = UNKNOWN_DEST_ESTAB) -> ExportResult:
    """Write a leaver's CTF into the sixth form data dir (ctf_exports/)."""
    who = store.require("STUDENTS_MANAGE", "CTF export")
    store.init_db()
    raw = build_leaver_xml(student_id, dest_la=dest_la, dest_estab=dest_estab)
    la, estab, _name = _school_identity()
    dest = f"{(dest_la or UNKNOWN_DEST_LA).upper()}{(dest_estab or UNKNOWN_DEST_ESTAB).upper()}"
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    seq = 1
    while True:
        out = EXPORT_DIR / f"{la}{estab}_CTF_{dest}_{seq:03d}.xml"
        if not out.exists():
            break
        seq += 1
    out.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    with store.connect() as conn:
        cur = conn.execute(
            "INSERT INTO ctf_exports (student_id, file_path, file_sha256, "
            "dest_la, dest_estab, exported_by) VALUES (?,?,?,?,?,?)",
            (student_id, str(out), sha, dest_la, dest_estab, who))
        conn.commit()
        export_id = cur.lastrowid
    logger.info("CTF export #%d for %s written to %s by %s",
                export_id, student_id, out, who)
    return ExportResult(export_id=export_id, path=out, sha256=sha)


def list_exports() -> list[dict[str, Any]]:
    store.init_db()
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM ctf_exports ORDER BY export_id DESC").fetchall()]
