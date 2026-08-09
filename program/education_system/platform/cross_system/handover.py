"""What information crosses each phase boundary, and under what consent.

A handover is the selected subset of a learner's record that the *source*
system approves for release to the *destination*. It is deliberately not
"everything we hold": the nursery's informal daily observations are the
right thing to keep for two years and the wrong thing to hand to a
secondary school eight years later.

Each boundary declares its fields as a :class:`HandoverSpec`. A spec is
data, not code, so the answer to "what does primary send secondary?" is
readable in one place and testable without standing up two systems.

Fields carry a :class:`Sensitivity`:

``routine``
    Ordinary record-keeping — attendance summaries, year groups.
``sensitive``
    Special-category or support data (SEND, medical, pupil premium).
    Released only when the handover consent covers it.
``restricted``
    Never carried in the payload itself. Safeguarding detail crosses as a
    *reference* for a designated lead to request through the safeguarding
    channel, so a routine progression event never contains a disclosure.

Adapters call :func:`build_handover` to assemble a payload and
:func:`validate_handover` to check one they have received.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class Sensitivity(enum.Enum):
    ROUTINE = "routine"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


@dataclass(frozen=True)
class HandoverField:
    """One item of information crossing a boundary."""

    key: str
    description: str
    sensitivity: Sensitivity = Sensitivity.ROUTINE
    required: bool = False

    @property
    def needs_consent(self) -> bool:
        return self.sensitivity is not Sensitivity.ROUTINE


@dataclass(frozen=True)
class HandoverSpec:
    """The agreed payload for one phase boundary."""

    source_system: str
    destination_system: str
    fields: tuple[HandoverField, ...]
    creates: str = "applicant"
    notes: str = ""

    @property
    def boundary(self) -> str:
        return f"{self.source_system}->{self.destination_system}"

    def field_keys(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.fields)

    def required_keys(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.fields if f.required)

    def keys_needing_consent(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.fields if f.needs_consent)

    def restricted_keys(self) -> tuple[str, ...]:
        return tuple(f.key for f in self.fields
                     if f.sensitivity is Sensitivity.RESTRICTED)

    def get(self, key: str) -> HandoverField | None:
        for f in self.fields:
            if f.key == key:
                return f
        return None


_R = Sensitivity.ROUTINE
_S = Sensitivity.SENSITIVE
_X = Sensitivity.RESTRICTED


# ── Nursery → Primary ───────────────────────────────────────────────
NURSERY_TO_PRIMARY = HandoverSpec(
    source_system="nursery",
    destination_system="primary",
    notes=(
        "EYFS profile and the practical facts a reception teacher needs on "
        "day one. Individual daily observations are NOT carried across — "
        "the summary judgement is, the raw log stays with the nursery and "
        "ages out under its own retention rule."
    ),
    fields=(
        HandoverField("child_identity",
                      "Legal name, DOB, preferred name, language(s)",
                      _R, required=True),
        HandoverField("guardians",
                      "Parent/guardian relationships and parental "
                      "responsibility", _R, required=True),
        HandoverField("emergency_contacts",
                      "Emergency contacts and collection permissions",
                      _R, required=True),
        HandoverField("eyfs_profile",
                      "Early Years Foundation Stage profile — the summary "
                      "judgement against each area of learning", _R),
        HandoverField("communication_needs",
                      "Language and communication needs, EAL status", _S),
        HandoverField("send_support",
                      "SEND support, EHCP status and accessibility needs",
                      _S),
        HandoverField("medical_alerts",
                      "Allergies and essential medical alerts", _S,
                      required=True),
        HandoverField("attendance_summary",
                      "Sessions offered/attended, funded hours pattern", _R),
        HandoverField("safeguarding_reference",
                      "Reference to the safeguarding handover — detail is "
                      "requested DSL-to-DSL, never carried in the payload",
                      _X),
    ),
)

# ── Primary → Secondary ─────────────────────────────────────────────
PRIMARY_TO_SECONDARY = HandoverSpec(
    source_system="primary",
    destination_system="secondary",
    notes=(
        "Feeds the pending Year 7 cohort the secondary system builds before "
        "September, so form groups and interventions are set before the "
        "learner arrives rather than in the first half-term."
    ),
    fields=(
        HandoverField("child_identity", "Legal name, DOB, UPN", _R,
                      required=True),
        HandoverField("guardians",
                      "Parent/guardian relationships and parental "
                      "responsibility", _R, required=True),
        HandoverField("ks2_results",
                      "Key Stage 2 scaled scores and teacher assessments",
                      _R),
        HandoverField("core_assessments",
                      "Reading, writing and mathematics assessment record",
                      _R),
        HandoverField("send_provision",
                      "SEND provision, EHCP, access arrangements", _S),
        HandoverField("support_indicators",
                      "Pupil Premium, free school meals, LAC/PLAC status",
                      _S),
        HandoverField("attendance_summary",
                      "Attendance and persistent-absence summary", _R),
        HandoverField("current_interventions",
                      "Interventions in flight that should continue", _S),
        HandoverField("medical_requirements",
                      "Medical and accessibility requirements, care plans",
                      _S),
        HandoverField("safeguarding_reference",
                      "Reference to the safeguarding handover", _X),
    ),
)

# ── Secondary → Sixth Form ──────────────────────────────────────────
SECONDARY_TO_SIXTH_FORM = HandoverSpec(
    source_system="secondary",
    destination_system="sixth_form",
    notes=(
        "Creates a sixth-form APPLICANT. The applicant becomes an enrolled "
        "learner only after results day and registration — predicted grades "
        "are not an enrolment."
    ),
    fields=(
        HandoverField("student_identity", "Legal name, DOB, UPN", _R,
                      required=True),
        HandoverField("gcse_entries",
                      "GCSE entries — subjects, tiers, boards", _R),
        HandoverField("gcse_results",
                      "Achieved GCSE grades once issued", _R),
        HandoverField("predicted_grades", "Predicted grades", _R),
        HandoverField("attendance_behaviour",
                      "Attendance and behaviour summary", _S),
        HandoverField("subject_recommendations",
                      "Recommended level 3 subjects and pathway", _R),
        HandoverField("access_arrangements",
                      "SEND provision and exam access arrangements", _S),
        HandoverField("careers_intentions",
                      "Careers guidance record and stated intentions", _R),
        HandoverField("application_details",
                      "Application, interview and offer details", _R,
                      required=True),
        HandoverField("references", "Staff reference(s)", _S),
        HandoverField("bursary_indicators",
                      "16–19 bursary eligibility indicators", _S),
        HandoverField("safeguarding_reference",
                      "Reference to the safeguarding handover", _X),
    ),
)

# ── Sixth Form → University ─────────────────────────────────────────
SIXTH_FORM_TO_UNIVERSITY = HandoverSpec(
    source_system="sixth_form",
    destination_system="university",
    notes=(
        "Creates a university APPLICANT. Confirmation against offer "
        "conditions on results day is what promotes it to an active "
        "student — an insurance choice must not create an enrolment."
    ),
    fields=(
        HandoverField("student_identity", "Legal name, DOB", _R,
                      required=True),
        HandoverField("ucas_application",
                      "UCAS application, personal ID and scheme code", _R,
                      required=True),
        HandoverField("predicted_qualifications",
                      "Predicted level 3 qualifications and grades", _R),
        HandoverField("achieved_qualifications",
                      "Achieved qualifications and grades", _R),
        HandoverField("personal_statement", "Personal statement", _R),
        HandoverField("reference", "Academic reference", _S),
        HandoverField("choices",
                      "Firm and insurance choices", _R),
        HandoverField("offer_conditions",
                      "University offer and its conditions", _R,
                      required=True),
        HandoverField("support_referral",
                      "Accessibility / disability support referral and "
                      "DSA indication", _S),
        HandoverField("handover_consent",
                      "The learner's consent record for this handover", _R,
                      required=True),
        HandoverField("confirmed_destination",
                      "Confirmed institution and course on confirmation",
                      _R),
        HandoverField("safeguarding_reference",
                      "Reference to the safeguarding handover", _X),
    ),
)


# ── Into an apprenticeship ──────────────────────────────────────────
#
# Three systems feed apprenticeships, and they send almost the same
# dataset because the receiving end is the same: a training provider
# deciding eligibility and building a training plan. What differs is the
# prior attainment on offer (GCSEs from secondary, level 3 from sixth
# form, a vocational profile from FE), so each boundary declares that
# field in its own vocabulary and shares the rest.
#
# Two fields here have no equivalent on the school boundaries and are
# required on all three, because without them a provider cannot lawfully
# start a programme:
#
# ``eligibility_evidence``
#     Right to work, residency and prior-qualification checks. A funding
#     claim for an ineligible apprentice is clawed back in audit.
# ``prior_attainment``
#     English and maths. A learner without level 2 must take Functional
#     Skills *as part of* the apprenticeship, so this changes the shape
#     of the programme rather than merely describing the learner.

_APPRENTICESHIP_COMMON: tuple[HandoverField, ...] = (
    HandoverField("learner_identity",
                  "Legal name, DOB, ULN — the ULN is what matches this "
                  "learner to their record at the previous provider", _R,
                  required=True),
    HandoverField("contact_details",
                  "Address, personal email and phone. An apprentice is an "
                  "employee, so provider contact is direct rather than "
                  "through a parent", _R, required=True),
    HandoverField("eligibility_evidence",
                  "Right to work, residency and prior-qualification "
                  "evidence for the funding eligibility check", _R,
                  required=True),
    HandoverField("prior_attainment",
                  "English and maths attainment — decides whether "
                  "Functional Skills must be built into the programme",
                  _R, required=True),
    HandoverField("careers_record",
                  "Careers guidance record and the occupation the learner "
                  "is aiming at", _R),
    HandoverField("employer_details",
                  "Employing organisation, workplace and line manager, "
                  "where the learner already has a job offer", _R),
    HandoverField("send_support",
                  "SEND provision, EHCP status and the reasonable "
                  "adjustments the employer and EPAO will need", _S),
    HandoverField("support_indicators",
                  "Learning support funding indicators (LLDD, bursary, "
                  "care leaver status)", _S),
    HandoverField("medical_requirements",
                  "Medical and accessibility requirements relevant to a "
                  "workplace risk assessment", _S),
    HandoverField("attendance_behaviour",
                  "Attendance and behaviour summary", _S),
    HandoverField("safeguarding_reference",
                  "Reference to the safeguarding handover — an apprentice "
                  "under 18 is still a child in a workplace", _X),
)

SECONDARY_TO_APPRENTICESHIPS = HandoverSpec(
    source_system="secondary",
    destination_system="apprenticeships",
    notes=(
        "Year 11 leaving at 16 into an intermediate/advanced apprenticeship. "
        "Creates an APPLICANT: the apprentice does not exist until an "
        "employer has signed and the eligibility check has passed, which is "
        "usually weeks after the school has finished with them."
    ),
    fields=_APPRENTICESHIP_COMMON + (
        HandoverField("gcse_results",
                      "Achieved GCSE grades once issued", _R),
        HandoverField("predicted_grades",
                      "Predicted grades, for an offer made before results "
                      "day", _R),
    ),
)

SIXTH_FORM_TO_APPRENTICESHIPS = HandoverSpec(
    source_system="sixth_form",
    destination_system="apprenticeships",
    notes=(
        "Post-18 route into a higher or degree apprenticeship, the "
        "alternative to the UCAS route in SIXTH_FORM_TO_UNIVERSITY. Creates "
        "an APPLICANT."
    ),
    fields=_APPRENTICESHIP_COMMON + (
        HandoverField("achieved_qualifications",
                      "Achieved level 3 qualifications and grades", _R),
        HandoverField("predicted_qualifications",
                      "Predicted level 3 qualifications and grades", _R),
        HandoverField("reference", "Academic reference", _S),
    ),
)

FE_COLLEGE_TO_APPRENTICESHIPS = HandoverSpec(
    source_system="fe_college",
    destination_system="apprenticeships",
    notes=(
        "The most common conversion of the three, and the one most likely "
        "to be CONCURRENT: an FE learner who picks up an apprenticeship "
        "often stays enrolled for the qualification the college delivers. "
        "Close the FE enrolment only when the learner has genuinely left."
    ),
    fields=_APPRENTICESHIP_COMMON + (
        HandoverField("vocational_profile",
                      "Study programme, learning aims and units achieved "
                      "so far", _R),
        HandoverField("prior_learning",
                      "Recognised prior learning — reduces the funding "
                      "band and may shorten the programme, so it must "
                      "cross rather than be re-evidenced", _R),
        HandoverField("functional_skills",
                      "Functional Skills already achieved or in progress",
                      _R),
    ),
)

UNIVERSITY_TO_APPRENTICESHIPS = HandoverSpec(
    source_system="university",
    destination_system="apprenticeships",
    notes=(
        "A degree apprenticeship, where the university is the training "
        "provider for the academic side and the apprenticeship record "
        "carries the employment, off-the-job hours and EPA. This is a DUAL "
        "REGISTRATION, not a transfer: complete the transition with "
        "close_source=False or the learner will appear to have left the "
        "university they are still studying at."
    ),
    creates="concurrent_enrolment",
    fields=_APPRENTICESHIP_COMMON + (
        HandoverField("programme_registration",
                      "Course, cohort and university student id the "
                      "apprenticeship is delivered alongside", _R,
                      required=True),
        HandoverField("achieved_qualifications",
                      "Qualifications on entry", _R),
        HandoverField("module_credits",
                      "Credits achieved so far, for the off-the-job "
                      "hours record", _R),
    ),
)

# ── Out of an apprenticeship ────────────────────────────────────────
APPRENTICESHIPS_TO_UNIVERSITY = HandoverSpec(
    source_system="apprenticeships",
    destination_system="university",
    notes=(
        "A completed higher apprentice progressing onto a degree or top-up. "
        "The EPA grade is the qualification being admitted on, so it is "
        "required — a distinction at level 5 is what the offer is made "
        "against. Creates a university APPLICANT."
    ),
    fields=(
        HandoverField("learner_identity", "Legal name, DOB, ULN", _R,
                      required=True),
        HandoverField("standard_completed",
                      "Apprenticeship standard, level and completion date",
                      _R, required=True),
        HandoverField("epa_result",
                      "End-Point Assessment grade and the awarding EPAO",
                      _R, required=True),
        HandoverField("functional_skills",
                      "English and maths achieved during the programme", _R),
        HandoverField("prior_learning",
                      "Recognised prior learning and credit transfer claim",
                      _R),
        HandoverField("employer_reference",
                      "Reference from the employer, who has supervised the "
                      "learner for the whole programme", _S),
        HandoverField("portfolio_summary",
                      "Summary of the KSB portfolio — evidence for a "
                      "credit-transfer or advanced-entry claim", _R),
        HandoverField("support_referral",
                      "Accessibility / disability support referral and DSA "
                      "indication", _S),
        HandoverField("handover_consent",
                      "The learner's consent record for this handover", _R,
                      required=True),
        HandoverField("safeguarding_reference",
                      "Reference to the safeguarding handover", _X),
    ),
)


HANDOVER_SPECS: dict[tuple[str, str], HandoverSpec] = {
    (s.source_system, s.destination_system): s
    for s in (NURSERY_TO_PRIMARY, PRIMARY_TO_SECONDARY,
              SECONDARY_TO_SIXTH_FORM, SIXTH_FORM_TO_UNIVERSITY,
              SECONDARY_TO_APPRENTICESHIPS, SIXTH_FORM_TO_APPRENTICESHIPS,
              FE_COLLEGE_TO_APPRENTICESHIPS, UNIVERSITY_TO_APPRENTICESHIPS,
              APPRENTICESHIPS_TO_UNIVERSITY)
}


class HandoverError(ValueError):
    """A handover payload is invalid for its boundary."""


def get_spec(source_system: str, destination_system: str
             ) -> HandoverSpec | None:
    """The agreed spec for a boundary, or ``None`` if the pair has no
    declared one.

    A missing spec is normal and not an error: moves to an external
    provider, an apprenticeship, home education, or a sideways move
    within the same phase have no fixed national dataset. Those hand over
    whatever the source chooses to include, with consent still enforced.
    """
    return HANDOVER_SPECS.get((source_system, destination_system))


@dataclass
class HandoverResult:
    """The outcome of assembling a payload against a spec."""

    payload: dict
    boundary: str
    included: list[str] = field(default_factory=list)
    withheld_no_consent: list[str] = field(default_factory=list)
    withheld_restricted: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing_required


def build_handover(
    source_system: str,
    destination_system: str,
    record: dict,
    *,
    consent: bool | set[str] | None = None,
    safeguarding_reference: str | None = None,
) -> HandoverResult:
    """Assemble the payload the source system will release.

    ``record`` is whatever the source adapter gathered, keyed by the
    spec's field keys. ``consent`` controls the sensitive fields:

    ``True``
        blanket consent — every sensitive field may cross.
    a set of keys
        granular consent — only those sensitive fields cross.
    ``False`` / ``None``
        no consent — sensitive fields are withheld and reported.

    Restricted fields are never copied from ``record`` whatever the
    consent says; the payload instead carries
    ``safeguarding_reference`` so the receiving DSL can request the
    detail through the safeguarding channel.
    """
    spec = get_spec(source_system, destination_system)
    boundary = f"{source_system}->{destination_system}"
    result = HandoverResult(payload={}, boundary=boundary)

    if spec is None:
        # Undeclared boundary: pass the record through, but still refuse
        # to carry anything the caller marked as safeguarding detail.
        result.payload = {k: v for k, v in record.items()
                          if k != "safeguarding_detail"}
        result.included = sorted(result.payload)
        if safeguarding_reference:
            result.payload["safeguarding_reference"] = safeguarding_reference
        logger.info("Handover %s has no declared spec — passing %d "
                    "caller-selected field(s)", boundary, len(result.included))
        return result

    granted: set[str]
    if consent is True:
        granted = set(spec.keys_needing_consent())
    elif isinstance(consent, set):
        granted = consent
    else:
        granted = set()

    for f in spec.fields:
        if f.sensitivity is Sensitivity.RESTRICTED:
            result.withheld_restricted.append(f.key)
            continue
        if f.key not in record or record[f.key] is None:
            if f.required:
                result.missing_required.append(f.key)
            continue
        if f.needs_consent and f.key not in granted:
            result.withheld_no_consent.append(f.key)
            if f.required:
                result.missing_required.append(f.key)
            continue
        result.payload[f.key] = record[f.key]
        result.included.append(f.key)

    result.unknown = sorted(set(record) - set(spec.field_keys()))
    if result.unknown:
        logger.debug("Handover %s ignoring %d field(s) not in the spec: %s",
                     boundary, len(result.unknown), ", ".join(result.unknown))

    if safeguarding_reference and spec.restricted_keys():
        result.payload["safeguarding_reference"] = safeguarding_reference

    logger.info(
        "Built handover %s: %d included, %d withheld for consent, "
        "%d restricted, %d required missing",
        boundary, len(result.included), len(result.withheld_no_consent),
        len(result.withheld_restricted), len(result.missing_required))
    return result


def validate_handover(source_system: str, destination_system: str,
                      payload: dict) -> list[str]:
    """Problems with a received payload, as a list of human-readable
    strings. Empty means acceptable.

    Used by a destination adapter before it creates an applicant, so a
    half-built handover is rejected at the boundary rather than becoming
    a half-populated learner record.
    """
    spec = get_spec(source_system, destination_system)
    if spec is None:
        return []
    problems: list[str] = []
    for key in spec.required_keys():
        f = spec.get(key)
        if f is not None and f.sensitivity is Sensitivity.RESTRICTED:
            continue
        if payload.get(key) is None:
            problems.append(f"missing required field {key!r}")
    for key in spec.restricted_keys():
        if payload.get(key) is not None:
            problems.append(
                f"restricted field {key!r} must not be carried in the "
                f"payload — send a reference instead")
    return problems


__all__ = [
    "Sensitivity",
    "HandoverField",
    "HandoverSpec",
    "HandoverError",
    "HandoverResult",
    "NURSERY_TO_PRIMARY",
    "PRIMARY_TO_SECONDARY",
    "SECONDARY_TO_SIXTH_FORM",
    "SIXTH_FORM_TO_UNIVERSITY",
    "SECONDARY_TO_APPRENTICESHIPS",
    "SIXTH_FORM_TO_APPRENTICESHIPS",
    "FE_COLLEGE_TO_APPRENTICESHIPS",
    "UNIVERSITY_TO_APPRENTICESHIPS",
    "APPRENTICESHIPS_TO_UNIVERSITY",
    "HANDOVER_SPECS",
    "get_spec",
    "build_handover",
    "validate_handover",
]
