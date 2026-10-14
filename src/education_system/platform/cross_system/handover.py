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
    The *detail* is never carried, whatever the consent says. The key
    itself does appear: it holds a **reference** — an opaque identifier a
    designated lead redeems through the safeguarding channel — so a
    routine progression event points at a disclosure without containing
    one. Sources never supply it; a value for a restricted key in the
    source record is dropped and reported in ``withheld_restricted``, and
    the reference comes from ``build_handover``'s own argument.

Adapters call :func:`build_handover` to assemble a payload and
:func:`validate_handover` to check one they have received.

Every spec also carries a practical **checklist** (report sent, visit
held, support meeting held, documents received) that seeds the
transition's ``checklist_json``, and three structured support fields —
``support_plan`` (with a review date), ``reasonable_adjustments`` and
``key_contacts`` — built with :func:`make_support_plan`,
:func:`make_reasonable_adjustment` and :func:`make_key_contact`.

Reading a handover back
-----------------------
The receiver should read an approved handover through
``transitions.get_handover_for``, which filters it by the viewer's role
and purpose using :func:`sensitivity_of` and the ``handover`` domain of
``governance.security.sensitive_access``. ``transitions.get_handover``
still returns the whole payload, but only for existing internal callers.
"""

from __future__ import annotations

import enum
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

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
class ChecklistItem:
    """One practical step of a transition that is not a workflow state.

    The seven workflow steps say where the *paperwork* is. A checklist says
    whether the things that make a move go well have actually happened:
    the visit, the support meeting, the documents arriving. Nursery and
    sixth form each kept a local list, so nobody could see across a
    boundary that the report had gone out and never arrived.

    ``owner`` is who is expected to tick the item: ``source``,
    ``destination`` or ``both``.
    """

    key: str
    label: str
    owner: str = "destination"


@dataclass(frozen=True)
class HandoverSpec:
    """The agreed payload for one phase boundary."""

    source_system: str
    destination_system: str
    fields: tuple[HandoverField, ...]
    creates: str = "applicant"
    notes: str = ""
    checklist: tuple[ChecklistItem, ...] = ()

    @property
    def boundary(self) -> str:
        return f"{self.source_system}->{self.destination_system}"

    def checklist_keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.checklist)

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


# ── Structured support data, common to every boundary ───────────────
# This used to exist only as prose inside the SEND and medical field
# descriptions. A receiver learned that a learner "has a support plan", but
# not when anyone next had to review it or which named person to ring.
# Each field is a structure — see make_support_plan,
# make_reasonable_adjustment and make_key_contact — and validate_handover
# checks its shape.
_SUPPORT_FIELDS: tuple[HandoverField, ...] = (
    HandoverField("support_plan",
                  "Current support plan: summary, outcomes, owner and the "
                  "date it must next be reviewed", _S),
    HandoverField("reasonable_adjustments",
                  "Reasonable adjustments in place (classroom, exam access, "
                  "workplace), each with the context it applies to", _S),
    # Routine because these are staff at the sending setting, not facts
    # about the learner. Family contacts travel as guardians, and
    # social-care involvement goes through the safeguarding channel; a
    # social worker listed here would disclose it.
    HandoverField("key_contacts",
                  "Named staff at the sending setting (key worker, SENCO, "
                  "tutor) the receiver can contact", _R),
)


# ── Default checklists per boundary ─────────────────────────────────
_TRANSITION_REPORT = ChecklistItem(
    "transition_report_sent", "Transition report sent", "source")
_SUPPORT_MEETING = ChecklistItem(
    "support_meeting_held",
    "Support / SEND transition meeting held (where the learner has support "
    "needs)", "both")
_DOCUMENTS_RECEIVED = ChecklistItem(
    "documents_received", "Handover documents received", "destination")

_EARLY_YEARS_CHECKLIST: tuple[ChecklistItem, ...] = (
    _TRANSITION_REPORT,
    ChecklistItem("visit_held",
                  "Reception teacher visit to the setting or home held"),
    _SUPPORT_MEETING,
    _DOCUMENTS_RECEIVED,
)
_SCHOOL_CHECKLIST: tuple[ChecklistItem, ...] = (
    _TRANSITION_REPORT,
    ChecklistItem("visit_held", "Induction / transition day attended"),
    _SUPPORT_MEETING,
    _DOCUMENTS_RECEIVED,
)
_POST16_CHECKLIST: tuple[ChecklistItem, ...] = (
    ChecklistItem("eligibility_confirmed",
                  "Entry requirements / eligibility confirmed"),
    ChecklistItem("interview_held",
                  "Enrolment interview or guidance meeting held"),
    _SUPPORT_MEETING,
    _DOCUMENTS_RECEIVED,
)
_HIGHER_EDUCATION_CHECKLIST: tuple[ChecklistItem, ...] = (
    ChecklistItem("offer_conditions_confirmed",
                  "Offer conditions confirmed against results"),
    ChecklistItem("support_referral_made",
                  "Disability / DSA support referral made", "both"),
    _DOCUMENTS_RECEIVED,
)
_APPRENTICESHIP_CHECKLIST: tuple[ChecklistItem, ...] = (
    ChecklistItem("eligibility_confirmed",
                  "Funding eligibility evidence checked"),
    ChecklistItem("initial_assessment_done",
                  "Initial assessment of English, maths and prior learning "
                  "done"),
    ChecklistItem("commitment_statement_signed",
                  "Commitment statement signed by apprentice, employer and "
                  "provider"),
    _SUPPORT_MEETING,
    _DOCUMENTS_RECEIVED,
)

#: For boundaries with no declared spec, such as a move to an external
#: provider or into employment. The two items hold on any move.
DEFAULT_CHECKLIST: tuple[ChecklistItem, ...] = (
    _TRANSITION_REPORT,
    _DOCUMENTS_RECEIVED,
)


# ── Nursery → Primary ───────────────────────────────────────────────
NURSERY_TO_PRIMARY = HandoverSpec(
    source_system="nursery",
    destination_system="primary",
    checklist=_EARLY_YEARS_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)

# ── Primary → Secondary ─────────────────────────────────────────────
PRIMARY_TO_SECONDARY = HandoverSpec(
    source_system="primary",
    destination_system="secondary",
    checklist=_SCHOOL_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)

# ── Secondary → Sixth Form ──────────────────────────────────────────
SECONDARY_TO_SIXTH_FORM = HandoverSpec(
    source_system="secondary",
    destination_system="sixth_form",
    checklist=_POST16_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)

SECONDARY_TO_FE_COLLEGE = HandoverSpec(
    source_system="secondary",
    destination_system="fe_college",
    checklist=_POST16_CHECKLIST,
    notes=(
        "Creates an FE applicant for a vocational, technical, T Level, BTEC "
        "or mixed study programme. Enrolment follows entry, funding and "
        "timetable checks."
    ),
    fields=(
        HandoverField("student_identity", "Legal name, DOB, UPN and ULN", _R,
                      required=True),
        HandoverField("contact_details", "Learner and parent contact details", _R),
        HandoverField("gcse_results", "Achieved GCSE subjects and grades", _R),
        HandoverField("predicted_grades", "Predicted GCSE grades", _R),
        HandoverField("prior_attainment", "Prior attainment including English and maths", _R,
                      required=True),
        HandoverField("course_request", "Course, qualification, level and campus", _R,
                      required=True),
        HandoverField("interview_requirements", "Interview, audition or assessment needs", _R),
        HandoverField("careers_intentions", "Careers guidance and intended occupation", _R),
        HandoverField("attendance_behaviour", "Attendance and behaviour summary", _S),
        HandoverField("send_support", "SEND provision and exam access arrangements", _S),
        HandoverField("medical_requirements", "Medical and accessibility requirements", _S),
        HandoverField("support_indicators", "Bursary and support indicators", _S),
        HandoverField("handover_consent", "Learner or parent consent record", _R,
                      required=True),
        HandoverField("safeguarding_reference", "Reference to safeguarding handover", _X),
    ) + _SUPPORT_FIELDS,
)

# ── Sixth Form → University ─────────────────────────────────────────
SIXTH_FORM_TO_FE_COLLEGE = HandoverSpec(
    source_system="sixth_form",
    destination_system="fe_college",
    checklist=_POST16_CHECKLIST,
    notes=(
        "Creates an FE applicant for a vocational or mixed post-16 pathway. "
        "Completion may leave the sixth-form enrolment open for concurrent study."
    ),
    fields=(
        HandoverField("student_identity", "Legal name, DOB and learner identifiers", _R,
                      required=True),
        HandoverField("contact_details", "Learner contact details", _R),
        HandoverField("current_programme", "Current subjects and study programme", _R),
        HandoverField("predicted_qualifications", "Predicted qualifications", _R),
        HandoverField("achieved_qualifications", "Qualifications already achieved", _R),
        HandoverField("prior_attainment", "Prior attainment relevant to entry", _R),
        HandoverField("referral_details", "Requested pathway, start and referral reason", _R,
                      required=True),
        HandoverField("send_support", "SEND provision and reasonable adjustments", _S),
        HandoverField("medical_requirements", "Medical and accessibility requirements", _S),
        HandoverField("support_indicators", "Bursary and other support indicators", _S),
        HandoverField("safeguarding_reference", "Reference to safeguarding handover", _X),
    ) + _SUPPORT_FIELDS,
)


FE_COLLEGE_TO_SIXTH_FORM = HandoverSpec(
    source_system="fe_college",
    destination_system="sixth_form",
    checklist=_POST16_CHECKLIST,
    notes=(
        "A change of provider, not an immediate withdrawal. FE remains active "
        "until Sixth Form has admitted the learner on the agreed start date."
    ),
    fields=(
        HandoverField("learner_identity", "Legal name, DOB and ULN", _R,
                      required=True),
        HandoverField("contact_details", "Learner contact details", _R),
        HandoverField("vocational_profile", "Current programme and units", _R),
        HandoverField("prior_attainment", "GCSE and equivalent attainment", _R,
                      required=True),
        HandoverField("functional_skills", "English and maths status", _R),
        HandoverField("transfer_request", "Reason, intended start and subject choices", _R,
                      required=True),
        HandoverField("send_support", "SEND provision and reasonable adjustments", _S),
        HandoverField("medical_requirements", "Medical and accessibility requirements", _S),
        HandoverField("support_indicators", "Funding and pastoral support indicators", _S),
        HandoverField("safeguarding_reference", "Reference to safeguarding handover", _X),
    ) + _SUPPORT_FIELDS,
)


SIXTH_FORM_TO_UNIVERSITY = HandoverSpec(
    source_system="sixth_form",
    destination_system="university",
    checklist=_HIGHER_EDUCATION_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)


FE_COLLEGE_TO_UNIVERSITY = HandoverSpec(
    source_system="fe_college",
    destination_system="university",
    checklist=_HIGHER_EDUCATION_CHECKLIST,
    notes=(
        "Creates a university APPLICANT for a vocational, Access to HE, "
        "BTEC or T Level route. The University owns decisions, confirmation "
        "and conversion to an enrolled student."
    ),
    fields=(
        HandoverField("student_identity", "Legal name, DOB, ULN and contact details", _R,
                      required=True),
        HandoverField("ucas_application", "UCAS application and personal ID", _R,
                      required=True),
        HandoverField("current_programme", "Current FE programme and learning aims", _R),
        HandoverField("predicted_qualifications", "Predicted vocational qualifications", _R),
        HandoverField("achieved_qualifications", "Qualifications and units achieved", _R),
        HandoverField("qualification_profile", "Qualification types, levels and grades", _R),
        HandoverField("recognised_prior_learning", "Recognised prior learning and credits", _R),
        HandoverField("personal_statement", "Personal statement", _R),
        HandoverField("reference", "Academic or tutor reference", _S),
        HandoverField("choices", "Ranked university and course choices", _R,
                      required=True),
        HandoverField("offer_conditions", "Conditions returned by the university", _R),
        HandoverField("support_referral", "SEND and accessibility support referral", _S),
        HandoverField("support_indicators", "Bursary and learner-support indicators", _S),
        HandoverField("handover_consent", "Learner consent record", _R,
                      required=True),
        HandoverField("confirmed_destination", "Firm confirmed institution and course", _R),
        HandoverField("safeguarding_reference", "Reference to safeguarding handover", _X),
    ) + _SUPPORT_FIELDS,
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
    HandoverField("intended_programme",
                  "Chosen apprenticeship standard, level and provider "
                  "programme identifier", _R, required=True),
    HandoverField("preferred_vacancy",
                  "Preferred vacancy or employer opportunity", _R),
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
    checklist=_APPRENTICESHIP_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)

SIXTH_FORM_TO_APPRENTICESHIPS = HandoverSpec(
    source_system="sixth_form",
    destination_system="apprenticeships",
    checklist=_APPRENTICESHIP_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)

FE_COLLEGE_TO_APPRENTICESHIPS = HandoverSpec(
    source_system="fe_college",
    destination_system="apprenticeships",
    checklist=_APPRENTICESHIP_CHECKLIST,
    creates="concurrent_enrolment",
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
    ) + _SUPPORT_FIELDS,
)

UNIVERSITY_TO_APPRENTICESHIPS = HandoverSpec(
    source_system="university",
    destination_system="apprenticeships",
    checklist=_APPRENTICESHIP_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)

# ── Out of an apprenticeship ────────────────────────────────────────
APPRENTICESHIPS_TO_UNIVERSITY = HandoverSpec(
    source_system="apprenticeships",
    destination_system="university",
    checklist=_HIGHER_EDUCATION_CHECKLIST,
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
    ) + _SUPPORT_FIELDS,
)


HANDOVER_SPECS: dict[tuple[str, str], HandoverSpec] = {
    (s.source_system, s.destination_system): s
    for s in (NURSERY_TO_PRIMARY, PRIMARY_TO_SECONDARY,
              SECONDARY_TO_SIXTH_FORM, SECONDARY_TO_FE_COLLEGE,
              SIXTH_FORM_TO_FE_COLLEGE,
              FE_COLLEGE_TO_SIXTH_FORM,
              SIXTH_FORM_TO_UNIVERSITY, FE_COLLEGE_TO_UNIVERSITY,
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


class HandoverAccessError(PermissionError):
    """The viewer is not a party to this handover."""


def checklist_for(source_system: str | None,
                  destination_system: str | None
                  ) -> tuple[ChecklistItem, ...]:
    """The checklist a new transition on this boundary starts with."""
    spec = (get_spec(source_system, destination_system)
            if source_system and destination_system else None)
    if spec is not None and spec.checklist:
        return spec.checklist
    return DEFAULT_CHECKLIST


_RANK = {Sensitivity.ROUTINE: 0, Sensitivity.SENSITIVE: 1,
         Sensitivity.RESTRICTED: 2}

# The most restrictive level each key has on any declared boundary. This
# classifies payloads on boundaries with no spec of their own, which
# carry whatever the source chose to include.
_KEY_SENSITIVITY: dict[str, Sensitivity] = {}
for _spec in HANDOVER_SPECS.values():
    for _f in _spec.fields:
        _held = _KEY_SENSITIVITY.get(_f.key)
        if _held is None or _RANK[_f.sensitivity] > _RANK[_held]:
            _KEY_SENSITIVITY[_f.key] = _f.sensitivity
del _spec, _f, _held


def sensitivity_of(key: str, source_system: str | None = None,
                   destination_system: str | None = None) -> Sensitivity:
    """How sensitive one payload key is on this boundary.

    The boundary's own spec wins. Failing that, the key's most restrictive
    level on any declared boundary applies. A key no spec knows is treated
    as SENSITIVE: an undeclared payload is caller-selected, and the key's
    name alone is no evidence that it is harmless.
    """
    if key == "safeguarding_reference":
        return Sensitivity.RESTRICTED
    if source_system and destination_system:
        spec = get_spec(source_system, destination_system)
        if spec is not None:
            f = spec.get(key)
            if f is not None:
                return f.sensitivity
    return _KEY_SENSITIVITY.get(key, Sensitivity.SENSITIVE)


def classify_payload(source_system: str | None,
                     destination_system: str | None,
                     payload: Mapping[str, Any]
                     ) -> dict[Sensitivity, list[str]]:
    """Payload keys grouped by sensitivity, each group sorted."""
    out: dict[Sensitivity, list[str]] = {s: [] for s in Sensitivity}
    for key in payload:
        out[sensitivity_of(key, source_system, destination_system)].append(
            key)
    for keys in out.values():
        keys.sort()
    return out


def withhold_sensitive(source_system: str | None,
                       destination_system: str | None,
                       payload: Mapping[str, Any]
                       ) -> tuple[dict[str, Any], list[str]]:
    """Drop every consent-dependent key; return (payload, withheld keys).

    The restricted safeguarding reference stays. Sharing for safeguarding
    rests on a statutory duty rather than on consent, and withdrawing
    consent must not cut the receiving DSL off from the pointer.
    """
    kept: dict[str, Any] = {}
    withheld: list[str] = []
    for key, value in payload.items():
        if sensitivity_of(key, source_system,
                          destination_system) is Sensitivity.SENSITIVE:
            withheld.append(key)
        else:
            kept[key] = value
    return kept, sorted(withheld)


# ---------------------------------------------------------------------------
# Structured support data
# ---------------------------------------------------------------------------

def _iso_date(value: object, what: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as exc:
        raise HandoverError(
            f"{what} must be an ISO date (YYYY-MM-DD), got {value!r}") from exc


def make_support_plan(summary: str, *, review_date: str,
                      owner: str | None = None,
                      outcomes: Sequence[str] = (),
                      plan_type: str | None = None) -> dict[str, Any]:
    """A ``support_plan`` value. ``review_date`` is required, because a
    plan with no review date is how a plan goes stale at a new setting."""
    if not summary or not summary.strip():
        raise HandoverError("A support plan needs a summary")
    return {
        "summary": summary.strip(),
        "review_date": _iso_date(review_date, "review_date"),
        "owner": owner,
        "outcomes": [str(o) for o in outcomes],
        "plan_type": plan_type,   # e.g. EHCP, SEN support, IHCP
    }


def make_reasonable_adjustment(adjustment: str, *,
                               context: str | None = None,
                               evidence: str | None = None
                               ) -> dict[str, Any]:
    """One entry of ``reasonable_adjustments``."""
    if not adjustment or not adjustment.strip():
        raise HandoverError("A reasonable adjustment needs a description")
    return {"adjustment": adjustment.strip(), "context": context,
            "evidence": evidence}


def make_key_contact(name: str, *, role: str, email: str | None = None,
                     phone: str | None = None,
                     institution: str | None = None) -> dict[str, Any]:
    """One entry of ``key_contacts``. A contact must be reachable."""
    if not name or not name.strip() or not role or not role.strip():
        raise HandoverError("A key contact needs a name and a role")
    if not (email or phone):
        raise HandoverError("A key contact needs an email or a phone number")
    return {"name": name.strip(), "role": role.strip(), "email": email,
            "phone": phone, "institution": institution}


def validate_support_data(payload: Mapping[str, Any]) -> list[str]:
    """Shape problems in the structured support fields, if present."""
    problems: list[str] = []
    plan = payload.get("support_plan")
    if plan is not None:
        if not isinstance(plan, Mapping):
            problems.append("support_plan must be a structured plan "
                            "(see make_support_plan)")
        else:
            if not plan.get("summary"):
                problems.append("support_plan has no summary")
            try:
                _iso_date(plan.get("review_date"), "review_date")
            except HandoverError:
                problems.append("support_plan needs an ISO review_date")
    adjustments = payload.get("reasonable_adjustments")
    if adjustments is not None:
        if not isinstance(adjustments, list) or not all(
                isinstance(a, Mapping) and a.get("adjustment")
                for a in adjustments):
            problems.append("reasonable_adjustments must be a list of "
                            "entries each naming the adjustment")
    contacts = payload.get("key_contacts")
    if contacts is not None:
        if not isinstance(contacts, list) or not all(
                isinstance(c, Mapping) and c.get("name") and c.get("role")
                and (c.get("email") or c.get("phone"))
                for c in contacts):
            problems.append("key_contacts must be a list of entries each "
                            "with a name, a role and an email or phone")
    return problems


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
        return validate_support_data(payload)
    problems: list[str] = []
    for key in spec.required_keys():
        f = spec.get(key)
        if f is not None and f.sensitivity is Sensitivity.RESTRICTED:
            continue
        if payload.get(key) is None:
            problems.append(f"missing required field {key!r}")
    for key in spec.restricted_keys():
        value = payload.get(key)
        if value is None:
            continue
        # A restricted key exists to carry a *reference* — the opaque
        # identifier a designated lead redeems through the safeguarding
        # channel — and ``build_handover`` puts one there itself. Rejecting
        # every value at the key therefore rejected this module's own
        # output: any handover built with a safeguarding_reference failed
        # the validation of the very spec it was built from.
        #
        # What must never cross is the detail behind the reference, and
        # detail arrives as structure — a disclosure record, a list of
        # concerns, a nested dict. So the test is shape, not presence.
        #
        # This bounds smuggling by shape and not by meaning: a caller that
        # passes a disclosure as the reference *string* still gets it
        # copied. Catching that would mean guessing at prose, which fails
        # in both directions and is a worse bargain than the narrow, honest
        # rule enforced here.
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            problems.append(
                f"restricted field {key!r} must carry only a reference — "
                f"the detail behind it is requested through the "
                f"safeguarding channel, never carried in the payload")
    problems.extend(validate_support_data(payload))
    return problems


__all__ = [
    "Sensitivity",
    "HandoverField",
    "ChecklistItem",
    "HandoverSpec",
    "HandoverError",
    "HandoverAccessError",
    "HandoverResult",
    "DEFAULT_CHECKLIST",
    "checklist_for",
    "sensitivity_of",
    "classify_payload",
    "withhold_sensitive",
    "make_support_plan",
    "make_reasonable_adjustment",
    "make_key_contact",
    "validate_support_data",
    "SIXTH_FORM_TO_FE_COLLEGE",
    "FE_COLLEGE_TO_SIXTH_FORM",
    "NURSERY_TO_PRIMARY",
    "PRIMARY_TO_SECONDARY",
    "SECONDARY_TO_SIXTH_FORM",
    "SIXTH_FORM_TO_UNIVERSITY",
    "SECONDARY_TO_APPRENTICESHIPS",
    "SIXTH_FORM_TO_APPRENTICESHIPS",
    "SECONDARY_TO_FE_COLLEGE",
    "FE_COLLEGE_TO_UNIVERSITY",
    "FE_COLLEGE_TO_APPRENTICESHIPS",
    "UNIVERSITY_TO_APPRENTICESHIPS",
    "APPRENTICESHIPS_TO_UNIVERSITY",
    "HANDOVER_SPECS",
    "get_spec",
    "build_handover",
    "validate_handover",
]
