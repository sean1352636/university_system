"""Year 11 transition: read a feeder school's CTF in the *applicant* context.

The integrations module (``operations/integrations/ctf.py``) imports a
Common Transfer File into **student** records. Before enrolment the
college needs the same file against its **applicants**: which Year 11
pupils have applied, their UPN / ULN, address, and — once KS4 results
are in the file — their actual GCSE grades for results day.

This module uses only the CTF *parser* from that module (no student
records are touched) and:

* matches every pupil to an applicant — ULN, then UPN, then name + date
  of birth (the admissions dedupe rule);
* :func:`apply` fills blanks on matched applicants (UPN, ULN, address,
  previous school, date of birth) and records KS4 GCSE results as
  *Actual* results (source "CTF") — grades that are not GCSE grades are
  skipped and listed, never guessed;
* also carries the pupil's **contacts** (as applicant parent/carer
  contacts, skipping names already held), **gender** (as the applicant's
  sex, when blank) and **SEN** history: the LLDD / EHCP flags are set on
  the profile, and the SEN detail goes into the applicant's SEND
  sensitive area. When the person applying the file holds the ``send``
  capability it is written as them; otherwise it is still stored in
  that SEND-only area (as ``system:ctf-transition``, so admissions staff
  see only that SEND information is held) and a timeline note asks the
  SENCO to review it — the information is never dropped and never shown
  to staff without ``send``;
* lists unmatched pupils (feeder pupils who have not applied) for
  follow-up; no applicant is invented for them, because a CTF carries no
  subject choices, email or phone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from education_system.systems.sixth_form.domain.admissions import (
    _guard,
    admissions as _adm,
    applicant_details as _details,
    entry_requirements as _er,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError


def available() -> bool:
    """Whether the integrations CTF parser is installed."""
    try:
        from education_system.systems.sixth_form.domain.operations.integrations import (  # noqa: F401
            ctf,
        )
        return hasattr(ctf, "parse_file")
    except ImportError:
        return False


def _ctf():
    from education_system.systems.sixth_form.domain.operations.integrations import (
        ctf,
    )
    return ctf


@dataclass
class PupilMatch:
    index: int
    name: str
    dob: str | None
    upn: str | None
    uln: str | None
    applicant_id: str | None
    matched_on: str | None          # "ULN" / "UPN" / "name + DOB"
    gcses: list[tuple[str, str]] = field(default_factory=list)
    skipped_results: list[str] = field(default_factory=list)


@dataclass
class TransitionPreview:
    file_name: str
    source_school: str
    pupils: list[PupilMatch]

    @property
    def matched(self) -> list[PupilMatch]:
        return [p for p in self.pupils if p.applicant_id]

    @property
    def unmatched(self) -> list[PupilMatch]:
        return [p for p in self.pupils if not p.applicant_id]


@dataclass
class TransitionResult:
    preview: TransitionPreview
    updated: list[str]
    results_recorded: int
    notes: list[str]
    contacts_added: int = 0
    sen_recorded: list[str] = field(default_factory=list)
    sen_for_senco: list[str] = field(default_factory=list)


#: CTF contact relationship (parent-contacts vocabulary) -> applicant
#: contact relationship.
_REL_TO_APPLICANT: dict[str, str] = {
    "Mother": "Mother", "Father": "Father", "Parent": "Parent",
    "Step-mother": "Step-parent", "Step-father": "Step-parent",
    "Carer": "Carer", "Guardian": "Carer", "Foster Carer": "Foster carer",
    "Grandmother": "Grandparent", "Grandfather": "Grandparent",
    "Sibling": "Sibling", "Social Worker": "Social worker",
    "Aunt": "Other relative", "Uncle": "Other relative",
}
#: CTF SEN provision codes.
_SEN_PROVISION = {"K": "SEN support", "E": "Education, health and care plan",
                  "S": "Statement", "A": "School Action",
                  "P": "School Action Plus"}

SENCO_NOTE = "SEN information received from school, SENCO to review"


def _carry_contacts(a: _adm.Applicant, pupil, notes: list[str]) -> int:
    if not pupil.contacts:
        return 0
    have = {c.name.lower() for c in _details.list_contacts(a.applicant_id)}
    added = 0
    ordered = sorted(pupil.contacts,
                     key=lambda c: (c.order is None, c.order or 0))
    for i, c in enumerate(ordered):
        name = " ".join(x for x in (c.forename, c.surname) if x).strip()
        if not name or name.lower() in have:
            continue
        phone = next((n for _t, n in c.phones if n), None)
        try:
            _details.add_contact(a.applicant_id, {
                "name": name,
                "relationship": _REL_TO_APPLICANT.get(c.relationship, "Other"),
                "phone": phone, "email": c.email, "address": c.address,
                "is_emergency": i == 0,
                "parental_responsibility": bool(c.responsibility),
            })
            have.add(name.lower())
            added += 1
        except ValidationError as e:
            notes.append(f"{a.applicant_id}: contact {name} not added ({e})")
    return added


def _sen_text(pupil, file_name: str, school: str | None) -> str | None:
    lines = []
    for s in pupil.sen:
        prov = (s.provision or "").strip().upper()
        if prov == "N" and not s.needs:
            continue
        label = _SEN_PROVISION.get(prov, s.provision or "provision not given")
        lines.append(f"{label}" + (f" from {s.start_date}" if s.start_date
                                   else "")
                     + (f"; needs: {', '.join(s.needs)}" if s.needs else ""))
    if not lines:
        return None
    src = f"{school} " if school else ""
    return (f"SEN history from {src}CTF {file_name}:\n- "
            + "\n- ".join(lines))


def _carry_sen(a: _adm.Applicant, pupil, file_name: str,
               school: str | None, result: "TransitionResult") -> None:
    text = _sen_text(pupil, file_name, school)
    if text is None:
        return
    provs = {(s.provision or "").strip().upper() for s in pupil.sen}
    flags: dict[str, bool] = {}
    if not a.lldd:
        flags["lldd"] = True
    if provs & {"E", "S"} and not a.ehcp:
        flags["ehcp"] = True
    if flags:
        _details.update_profile(a.applicant_id, **flags)
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )

    def write() -> bool:
        old = (_details.sensitive_for_conversion(a.applicant_id)
               .get("send") or "").strip()
        if text in old:
            return False
        _details.set_sensitive(a.applicant_id, "send",
                               f"{old}\n\n{text}" if old else text)
        return True

    if _guard.can(access.SEND):
        if write():
            result.sen_recorded.append(a.applicant_id)
        return
    with _guard.system_actor("ctf-transition", capabilities=(access.SEND,)):
        written = write()
    if not written:
        return
    with _adm._connect() as conn:
        _adm._log_event(conn, a.applicant_id, SENCO_NOTE, kind="sensitive")
        conn.commit()
    result.sen_for_senco.append(a.applicant_id)


def _gcse_results(pupil) -> tuple[list[tuple[str, str]], list[str]]:
    """(subject, grade) KS4 results that are GCSE grades; the rest listed."""
    ok, skipped = [], []
    for r in pupil.ks4_results:
        subj = (r.subject or "").strip()
        grade = (r.result or "").strip().upper()
        if not subj or not grade:
            continue
        if grade in _er.GCSE_91_GRADES or grade in _er.LEGACY_GRADES:
            ok.append((subj, grade))
        else:
            skipped.append(f"{subj}: {r.result}")
    return ok, skipped


def _match(pupil, applicants: list[_adm.Applicant]
           ) -> tuple[str | None, str | None]:
    if pupil.uln:
        for a in applicants:
            if a.uln and a.uln == pupil.uln:
                return a.applicant_id, "ULN"
    if pupil.upn:
        for a in applicants:
            if a.upn and a.upn.upper() == pupil.upn.upper():
                return a.applicant_id, "UPN"
    first = pupil.preferred_forename or pupil.forename
    last = pupil.preferred_surname or pupil.surname
    if pupil.dob and pupil.surname:
        for f, l in ((first, last), (pupil.forename, pupil.surname)):
            if not (f and l):
                continue
            dupes = _adm.find_duplicates(first_name=f, last_name=l,
                                         dob=pupil.dob)
            if dupes:
                return dupes[0].applicant_id, "name + DOB"
    return None, None


def preview(path: str | Path) -> TransitionPreview:
    """Read-only: match each pupil in the CTF to an applicant."""
    if not available():
        raise ValidationError("The CTF integration is not available")
    ctf_file = _ctf().parse_file(path)
    applicants = _adm.list_applicants()
    pupils: list[PupilMatch] = []
    for p in ctf_file.pupils:
        aid, how = _match(p, applicants)
        gcses, skipped = _gcse_results(p)
        pupils.append(PupilMatch(
            index=p.index, name=p.full_name, dob=p.dob, upn=p.upn,
            uln=p.uln, applicant_id=aid, matched_on=how, gcses=gcses,
            skipped_results=skipped))
    return TransitionPreview(file_name=ctf_file.file_name,
                             source_school=ctf_file.header.source_label,
                             pupils=pupils)


def apply(path: str | Path, *, record_results: bool = True,
          entered_by: str | None = None) -> TransitionResult:
    """Fill matched applicants' blanks and record their KS4 results."""
    if not available():
        raise ValidationError("The CTF integration is not available")
    ctf_file = _ctf().parse_file(path)
    pv = preview(path)
    by_index = {p.index: p for p in ctf_file.pupils}
    school = ctf_file.header.source_name
    updated: list[str] = []
    notes: list[str] = []
    recorded = 0
    result = TransitionResult(preview=pv, updated=updated,
                              results_recorded=0, notes=notes)
    for m in pv.matched:
        pupil = by_index[m.index]
        a = _adm.get_applicant(m.applicant_id or "")
        if a is None:
            continue
        fill = {}
        if pupil.address and not a.address:
            fill["address"] = pupil.address
        if school and not a.previous_school:
            fill["previous_school"] = school
        if pupil.dob and not a.dob:
            fill["dob"] = pupil.dob
        try:
            if fill:
                _adm.update_applicant(a.applicant_id, fill)
            extra = {}
            if pupil.upn and not a.upn:
                extra["upn"] = pupil.upn.upper()
            if pupil.uln and not a.uln:
                extra["uln"] = pupil.uln
            if extra:
                _adm._set_extra(a.applicant_id,
                                event=f"Identifiers from CTF "
                                      f"({ctf_file.file_name})", **extra)
            if pupil.gender and not a.sex:
                _details.update_profile(a.applicant_id, sex=pupil.gender)
                fill["sex"] = pupil.gender
            if fill or extra:
                updated.append(a.applicant_id)
        except ValidationError as e:
            notes.append(f"{a.applicant_id}: {e}")
        try:
            result.contacts_added += _carry_contacts(a, pupil, notes)
        except ValidationError as e:
            notes.append(f"{a.applicant_id}: contacts not carried ({e})")
        try:
            _carry_sen(a, pupil, ctf_file.file_name, school, result)
        except Exception as e:  # noqa: BLE001 — reported, never dropped silently
            logger.exception("CTF SEN carry failed for %s", a.applicant_id)
            notes.append(f"{a.applicant_id}: SEN information not stored "
                         f"({e}) — keep the CTF for the SENCO")
        if record_results:
            for subj, grade in m.gcses:
                try:
                    _er.record_gcse(a.applicant_id, subj, grade,
                                    result_type="Actual", source="CTF",
                                    entered_by=entered_by)
                    recorded += 1
                except ValidationError as e:
                    notes.append(f"{a.applicant_id} {subj} {grade}: {e}")
        for s in m.skipped_results:
            notes.append(f"{a.applicant_id}: result not a GCSE grade, "
                         f"skipped ({s})")
    logger.info("Year 11 CTF %s applied to applicants: %d updated, %d "
                "results, %d contacts, SEN %d recorded / %d for the SENCO",
                ctf_file.file_name, len(updated), recorded,
                result.contacts_added, len(result.sen_recorded),
                len(result.sen_for_senco))
    result.results_recorded = recorded
    return result
