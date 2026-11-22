"""Structured UCAS offer conditions, and checking results against them.

One shape for "what an offer asks for", used by both ends of the
sixth form → university link: the university records it when it issues an
offer (``university...admissions.domain.ucas.offer_terms``) and evaluates
it on results day (``...ucas.results_day``); the sixth form records the
same shape for offers from universities outside this platform and checks
its learners' released results against it (``sixth_form.domain.progression.
university.offers``). Neither system imports the other — both import this.

A condition is a dict:

``kind``
    ``grade_profile`` — "ABB", "D*DD", "BB + DM", "Distinction";
    ``subject_grade`` — "B in Mathematics" (``subject`` may list
    alternatives with "/" or " or ", ``count`` how many of them);
    ``tariff_points`` — "112 UCAS points" (``count`` = best N results);
    ``qualification_grade`` — a whole qualification, e.g. EPQ at B;
    ``gcse_requirement`` — GCSE English / maths at a grade;
    ``other_text`` — anything else, which a person always checks.
``qualification_type``, ``subject``, ``min_grade``, ``min_points``,
``count``, ``text`` — as the kind needs.

Results are dicts with ``subject``, ``grade``, ``qualification_type``,
``released`` and ``release_at`` — the sixth form adapter's
``exam_results_for_admissions`` shape.

:func:`conditions_from_text` reads the free-text condition the offer forms
have always had ("ABB including B in Mathematics", "112 UCAS points",
"BB + DM", "plus B in the EPQ", "GCSE English and Maths at grade 4"). What
it cannot account for word by word becomes an ``other_text`` condition, so
genuinely unparseable prose still goes to a person and nothing is guessed.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from education_system.platform.cross_system import qualification_grades as qg

__all__ = [
    "CONDITION_KINDS",
    "MET", "MISSED", "REVIEW", "PENDING",
    "ConditionOutcome",
    "Evaluation",
    "conditions_from_text",
    "describe",
    "evaluate",
    "is_released",
    "validate_condition",
    "validate_conditions",
]

MET = "Met"
MISSED = "Missed"
REVIEW = "Review"
PENDING = "Pending"

CONDITION_KINDS: tuple[str, ...] = (
    "grade_profile", "subject_grade", "tariff_points",
    "qualification_grade", "gcse_requirement", "other_text",
)

KIND_LABELS: dict[str, str] = {
    "grade_profile": "Grade profile",
    "subject_grade": "Subject grade",
    "tariff_points": "UCAS Tariff points",
    "qualification_grade": "Qualification grade",
    "gcse_requirement": "GCSE requirement",
    "other_text": "Other (checked by hand)",
}

_FIELDS = ("kind", "qualification_type", "subject", "min_grade",
           "min_points", "count", "text")

#: Ofqual's anchor points between legacy GCSE letters and 9-1 numbers
#: (bottom of 7 = bottom of A, bottom of 4 = bottom of C, bottom of 1 =
#: bottom of G). Other letters have no defined equivalent and are refused.
_LEGACY_GCSE = {"A": "7", "C": "4", "G": "1"}


# ── Validation ─────────────────────────────────────────────────────

def _clean(value: Any) -> str | None:
    s = str(value).strip() if value is not None else ""
    return s or None


def _int(value: Any, label: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        raise ValueError(f"{label} must be a whole number") from None
    if n <= 0:
        raise ValueError(f"{label} must be more than 0")
    return n


def _profile_segments(profile: str,
                      qualification_type: str | None = None
                      ) -> list[tuple[str, list[str]]] | None:
    """``"BB + DM"`` -> ``[("A Level", ["B", "B"]), ("BTEC Diploma", ["DM"])]``.

    ``None`` if any part is not a grade profile.
    """
    parts = [p.strip() for p in re.split(r"\s*(?:\+|,|\bplus\b|\band\b)\s*",
                                         profile.strip()) if p.strip()]
    if not parts:
        return None
    explicit = qg.canonical_type(qualification_type) if qualification_type else None
    out: list[tuple[str, list[str]]] = []
    for part in parts:
        token = part.replace(" ", "")
        if explicit and len(parts) == 1:
            ladder = qg.ladder_for(explicit)
            if ladder is None:
                return None
            if qg.scale_key(explicit) in ("btec_single", "btec_double",
                                          "btec_triple", "t_level"):
                g = ladder.normalise(token)
                if g is None:
                    return None
                out.append((explicit, [g]))
                continue
            letters = re.findall(r"A\*|[A-E]", token.upper())
            if not letters or "".join(letters) != token.upper():
                return None
            if any(ladder.normalise(x) is None for x in letters):
                return None
            out.append((explicit, [ladder.normalise(x) for x in letters]))
            continue
        tl = qg.LADDERS["t_level"].normalise(part)
        if tl and not re.fullmatch(r"(?:A\*|[A-E])+", part):
            out.append(("T Level", [tl]))
            continue
        up = token.upper()
        if re.fullmatch(r"(?:A\*|[A-E])+", up):
            out.append(("A Level", re.findall(r"A\*|[A-E]", up)))
            continue
        inferred = qg.infer_type(up)
        if inferred and inferred.startswith(("BTEC", "Applied")):
            g = qg.normalise_grade(up, inferred)
            if g is None:
                return None
            out.append((inferred, [g]))
            continue
        return None
    return out


def validate_condition(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise one condition, or raise ``ValueError`` saying what is wrong."""
    kind = _clean(data.get("kind"))
    if kind not in CONDITION_KINDS:
        raise ValueError(
            f"Condition kind must be one of: {', '.join(CONDITION_KINDS)}")
    out: dict[str, Any] = {f: None for f in _FIELDS}
    out["kind"] = kind
    qtype_raw = _clean(data.get("qualification_type"))
    qtype = qg.canonical_type(qtype_raw) if qtype_raw else None
    if qtype_raw and qtype is None:
        raise ValueError(f"Unknown qualification type {qtype_raw!r}")
    out["qualification_type"] = qtype
    out["subject"] = _clean(data.get("subject"))
    out["text"] = _clean(data.get("text"))
    out["count"] = _int(data.get("count"), "Count")
    out["min_points"] = _int(data.get("min_points"), "Minimum points")
    grade = _clean(data.get("min_grade"))

    if kind == "grade_profile":
        if not grade:
            raise ValueError("A grade profile needs the grades, e.g. ABB or BB + DM")
        if _profile_segments(grade, qtype) is None:
            raise ValueError(f"{grade!r} is not a grade profile")
        out["min_grade"] = grade
    elif kind in ("subject_grade", "qualification_grade"):
        if kind == "subject_grade" and not out["subject"]:
            raise ValueError("A subject grade needs the subject")
        if kind == "qualification_grade" and not qtype:
            raise ValueError("A qualification grade needs the qualification type")
        if not grade:
            raise ValueError("The minimum grade is required")
        check_type = qtype or qg.infer_type(grade) or "A Level"
        g = qg.normalise_grade(grade, check_type)
        if g is None:
            ladder = qg.ladder_for(check_type)
            raise ValueError(
                f"{grade!r} is not a {check_type} grade"
                + (f" ({', '.join(ladder.grades)})" if ladder else ""))
        out["min_grade"] = g
        out["qualification_type"] = qtype or check_type
    elif kind == "gcse_requirement":
        if not out["subject"]:
            raise ValueError("A GCSE requirement needs the subject(s)")
        if not grade:
            raise ValueError("A GCSE requirement needs the grade")
        g = grade.upper()
        g = _LEGACY_GCSE.get(g, g)
        if qg.normalise_grade(g, "GCSE") is None:
            raise ValueError(
                "GCSE grade must be 9-1 (legacy letters A, C and G are "
                "accepted as 7, 4 and 1)")
        out["min_grade"] = g
        out["qualification_type"] = "GCSE"
    elif kind == "tariff_points":
        if out["min_points"] is None:
            raise ValueError("A tariff condition needs the minimum points")
    elif kind == "other_text":
        if not out["text"]:
            raise ValueError("Describe the condition in the text field")
    return out


def validate_conditions(rows: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Every condition normalised, numbered in the error if one is wrong."""
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows or (), 1):
        if not any(_clean(row.get(f)) for f in _FIELDS if f != "kind"):
            continue  # an empty row in a form
        try:
            out.append(validate_condition(row))
        except ValueError as e:
            raise ValueError(f"Condition {i}: {e}") from None
    return out


def describe(c: dict[str, Any]) -> str:
    """One line a person reads, e.g. ``B in Mathematics (A Level)``."""
    kind = c.get("kind")
    qt = c.get("qualification_type")
    if kind == "grade_profile":
        return f"{c.get('min_grade')}" + (f" ({qt})" if qt else "")
    if kind == "subject_grade":
        n = c.get("count")
        lead = f"{n} of " if n and n > 1 else ""
        return (f"{c.get('min_grade')} in {lead}{c.get('subject')}"
                + (f" ({qt})" if qt and qt != "A Level" else ""))
    if kind == "tariff_points":
        out = f"{c.get('min_points')} UCAS Tariff points"
        if c.get("count"):
            out += f" from best {c['count']}"
        if qt:
            out += f" ({qt} only)"
        return out
    if kind == "qualification_grade":
        return (f"{qt} at {c.get('min_grade')}"
                + (f" in {c['subject']}" if c.get("subject") else ""))
    if kind == "gcse_requirement":
        return f"GCSE {c.get('subject')} at grade {c.get('min_grade')}"
    return c.get("text") or "—"


# ── Reading the free-text condition ────────────────────────────────

_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_GRADE = r"(A\*|[A-E])"
_STOP = r"(?=\s*(?:,|;|\.(?:\s|$)|\band\b|\bplus\b|\bwith\b|\bincluding\b|\+|\(|$))"
_SUBJECT_GRADE_RE = re.compile(
    rf"(?<![A-Za-z*]){_GRADE}\s+(?:grade\s+)?in\s+(?:A[\s-]?level\s+)?"
    rf"(?P<subject>[A-Za-z][A-Za-z /&]*?){_STOP}")
_EPQ_NAME = r"(?:the\s+)?(?:EPQ|Extended\s+Project(?:\s+Qualification)?)"
_EPQ_A_RE = re.compile(rf"(?<![A-Za-z*]){_GRADE}\s+(?:grade\s+)?in\s+{_EPQ_NAME}", re.I)
_EPQ_B_RE = re.compile(rf"{_EPQ_NAME}\s+(?:at\s+)?(?:grade\s+)?{_GRADE}(?![A-Za-z])", re.I)
_TARIFF_RE = re.compile(
    r"(?P<pts>\d{2,3})\s*(?:ucas\s*)?(?:tariff\s*)?(?:points|pts)\b"
    r"(?:\s+from\s+(?:a\s+maximum\s+of\s+|the\s+best\s+|best\s+)?"
    r"(?P<n>\d|one|two|three|four|five)\s+"
    r"(?P<what>a[\s-]?levels?|qualifications?|subjects?))?", re.I)
_TARIFF_B_RE = re.compile(r"ucas\s+tariff\s+(?:score\s+)?of\s+(?P<pts>\d{2,3})", re.I)
_GCSE_SUBJ = r"(?:English(?:\s+Language|\s+Literature)?|Maths|Mathematics|Science|Double\s+Science)"
_GCSE_LIST = rf"{_GCSE_SUBJ}(?:\s*(?:,|and|&)\s*{_GCSE_SUBJ})*"
_GCSE_G = r"([1-9]|[ACG])"
_GCSE_A_RE = re.compile(
    rf"GCSEs?\s+(?:in\s+)?(?P<subj>{_GCSE_LIST})\s+(?:at\s+)?(?:grade\s+)?"
    rf"(?P<g>{_GCSE_G[1:-1]})(?:\s*/\s*[A-G])?(?:\s*\(\s*[A-G]\s*\))?"
    r"(?:\s+or\s+(?:above|higher|better))?(?![A-Za-z0-9])", re.I)
_GCSE_B_RE = re.compile(
    rf"(?:grade\s+)?(?P<g>{_GCSE_G[1:-1]})(?:\s*/\s*[A-G])?(?:\s*\(\s*[A-G]\s*\))?"
    r"(?:\s+or\s+(?:above|higher|better))?\s+in\s+GCSEs?\s+"
    rf"(?P<subj>{_GCSE_LIST})", re.I)
_PROFILE_TOKEN = r"(?:A\*|D\*|[A-EMP])+"
_PROFILE_RE = re.compile(
    rf"(?<![A-Za-z*]){_PROFILE_TOKEN}(?:\s*(?:\+|\bplus\b)\s*{_PROFILE_TOKEN})*(?![A-Za-z*])")
_TLEVEL_RE = re.compile(r"\b(Distinction\*?|Merit|Pass)(?![A-Za-z])")
_QUAL_AFTER_RE = re.compile(
    r"^\s*(?:in|at|from)?\s*(?:an?\s+|the\s+)?(?:Pearson\s+)?"
    r"(?P<q>BTEC(?:\s+National)?\s+(?:Extended\s+Diploma|Diploma|Extended\s+Certificate)"
    r"|Extended\s+Diploma|T[\s-]?Level|A[\s-]?levels?|AS[\s-]?levels?)", re.I)
_FILLER = re.compile(
    r"\b(?:and|or|above|higher|better|at|grades?|including|incl|with|plus|a|an|"
    r"the|in|minimum|min|of|from|required|requirement|overall|a[\s-]?levels?|"
    r"ucas|tariff|points|achieve|achieving|to|be|offer|conditional|level|"
    r"also|equivalent|qualifications?|subjects?)\b", re.I)


def _subjects_in(text: str) -> list[str]:
    parts = re.split(r"\s*(?:,|\band\b|&)\s*", text.strip())
    return [p.strip() for p in parts if p.strip()]


def conditions_from_text(text: str | None) -> list[dict[str, Any]]:
    """Structured conditions read from an offer's free-text condition.

    Whatever is left once every recognised piece is taken out — other than
    connecting words — is returned as one ``other_text`` condition holding
    the whole original text, so an offer with a clause nobody could check
    automatically is never treated as checked.
    """
    raw = str(text or "").strip()
    if not raw:
        return []
    s = raw
    out: list[dict[str, Any]] = []

    def take(m: re.Match) -> None:
        nonlocal s
        s = s[:m.start()] + " " + s[m.end():]

    for rx in (_GCSE_A_RE, _GCSE_B_RE):
        while (m := rx.search(s)) is not None:
            g = m.group("g").upper()
            g = _LEGACY_GCSE.get(g, g)
            for subject in _subjects_in(m.group("subj")):
                out.append({"kind": "gcse_requirement", "subject": subject,
                            "min_grade": g, "qualification_type": "GCSE"})
            take(m)
    for rx in (_EPQ_A_RE, _EPQ_B_RE):
        while (m := rx.search(s)) is not None:
            out.append({"kind": "qualification_grade", "qualification_type": "EPQ",
                        "min_grade": m.group(1).upper()})
            take(m)
    for rx in (_TARIFF_RE, _TARIFF_B_RE):
        while (m := rx.search(s)) is not None:
            cond: dict[str, Any] = {"kind": "tariff_points",
                                    "min_points": int(m.group("pts"))}
            n = m.groupdict().get("n")
            if n:
                cond["count"] = int(_NUM_WORDS.get(n.lower(), n))
                what = (m.group("what") or "").lower()
                if what.startswith("a"):
                    cond["qualification_type"] = "A Level"
            out.append(cond)
            take(m)
    while (m := _SUBJECT_GRADE_RE.search(s)) is not None:
        subject = m.group("subject").strip()
        if re.search(r"\b(?:EPQ|GCSE)\b", subject, re.I):
            break
        out.append({"kind": "subject_grade", "subject": subject,
                    "min_grade": m.group(1), "qualification_type": "A Level"})
        take(m)

    # "A level(s)" names the default qualification; its lone "A" would
    # otherwise read as a one-grade profile.
    s = re.sub(r"\b(?:GCE\s+)?A[\s-]?levels?\b", " ", s, flags=re.I)
    profiles: list[dict[str, Any]] = []
    while (m := _PROFILE_RE.search(s)) is not None:
        token = m.group(0)
        single = len(re.findall(r"A\*|D\*|[A-EMP]", token.replace(" ", ""))) == 1
        # A lone letter is an article or an initial far more often than a
        # one-grade offer; only a starred grade or the whole text counts.
        if single and "*" not in token and s.strip() != token:
            s = s[:m.start()] + " \x00 " + s[m.end():]
            continue
        rest = s[m.end():]
        qtype = None
        qm = _QUAL_AFTER_RE.match(rest)
        consumed = 0
        if qm:
            qtype = qg.canonical_type(qm.group("q"))
            consumed = qm.end()
        if _profile_segments(token, qtype) is None:
            s = s[:m.start()] + " \x00 " + s[m.end():]
            continue
        profiles.append({"kind": "grade_profile", "min_grade": token.strip(),
                         "qualification_type": qtype})
        s = s[:m.start()] + " " + s[m.end() + consumed:]
    if "T Level" in raw or "T-Level" in raw or re.fullmatch(
            r"\s*(?:Distinction\*?|Merit|Pass)\s*", raw):
        while (m := _TLEVEL_RE.search(s)) is not None:
            profiles.append({"kind": "grade_profile", "min_grade": m.group(1),
                             "qualification_type": "T Level"})
            take(m)
        s = re.sub(r"\bT[\s-]?Levels?\b", " ", s, flags=re.I)

    leftover = _FILLER.sub(" ", s.replace("\x00", "?"))
    leftover = re.sub(r"[\s,;:.+()/&\-]+", " ", leftover).strip()
    # Two profiles side by side without a "+" are alternatives ("ABB or
    # BBB with an A in the EPQ") — not something to require both of.
    alternatives = len(profiles) > 1 and re.search(r"\bor\b", raw, re.I)
    if leftover or alternatives:
        return [{"kind": "other_text", "text": raw}]
    return validate_conditions(out + profiles)


# ── Evaluation ─────────────────────────────────────────────────────

def is_released(result: dict[str, Any], now: _dt.datetime | None = None) -> bool:
    """Has this result been published?

    The source system's ``released`` flag is authoritative when present —
    it applies the source's own embargo rule at read time, and a past
    ``release_at`` (e.g. an old recorded release time on a result since
    withdrawn) must not override a False. ``release_at`` decides only
    when no flag was supplied.
    """
    if "released" in result and result["released"] is not None:
        return bool(result["released"])
    at = result.get("release_at")
    if not at:
        return False
    try:
        when = _dt.datetime.fromisoformat(str(at).strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            when = _dt.datetime.strptime(str(at).strip()[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            return False
    if now is None:
        now = _dt.datetime.now(when.tzinfo) if when.tzinfo else _dt.datetime.now()
    elif when.tzinfo and now.tzinfo is None:
        when = when.astimezone().replace(tzinfo=None)
    elif now.tzinfo and when.tzinfo is None:
        now = now.astimezone().replace(tzinfo=None)
    return when <= now


_SUBJECT_ALIASES = {
    "maths": "mathematics", "math": "mathematics",
    "further maths": "further mathematics", "further math": "further mathematics",
    "english lit": "english literature", "english lang": "english language",
    "comp sci": "computer science", "computing": "computer science",
    "double science": "combined science", "science": "combined science",
    "chem": "chemistry", "bio": "biology", "phys": "physics",
}


def _norm_subject(s: str | None) -> str:
    t = re.sub(r"\(.*?\)", " ", str(s or "")).lower()
    t = re.sub(r"\b(?:gce|gcse|a[\s-]?level|as[\s-]?level)\b", " ", t)
    t = re.sub(r"[^a-z ]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _SUBJECT_ALIASES.get(t, t)


def _subject_matches(wanted: str, have: str, *, loose_english: bool = False) -> bool:
    w, h = _norm_subject(wanted), _norm_subject(have)
    if not w or not h:
        return False
    if w == h:
        return True
    if loose_english and w == "english" and h.startswith("english"):
        return True
    if w == "combined science" and h in ("combined science", "science",
                                         "biology", "chemistry", "physics"):
        return loose_english
    return False


@dataclass
class _Result:
    subject: str
    grade: str
    qtype: str
    raw: dict[str, Any]


def _prepare(results: Iterable[dict[str, Any]]) -> list[_Result]:
    """Typed, normalised results; the best grade per subject and type."""
    best: dict[tuple[str, str], _Result] = {}
    for r in results or ():
        grade = _clean(r.get("grade"))
        if not grade:
            continue
        qtype = qg.canonical_type(r.get("qualification_type")) or qg.infer_type(grade)
        if not qtype:
            continue
        g = qg.normalise_grade(grade, qtype)
        if g is None:
            continue
        subject = _clean(r.get("subject")) or qtype
        key = (_norm_subject(subject), qtype)
        current = best.get(key)
        if current is None or (qg.rank(g, qtype) or 99) < (qg.rank(current.grade, qtype) or 99):
            best[key] = _Result(subject, g, qtype, dict(r))
    return list(best.values())


@dataclass
class ConditionOutcome:
    condition: dict[str, Any]
    verdict: str
    reason: str
    relied: list[dict[str, Any]] = field(default_factory=list)

    @property
    def label(self) -> str:
        return describe(self.condition)


@dataclass
class Evaluation:
    verdict: str
    outcomes: list[ConditionOutcome]
    relied: list[dict[str, Any]]
    unreleased: list[dict[str, Any]]

    @property
    def reason(self) -> str:
        return "; ".join(f"{o.label}: {o.reason}" for o in self.outcomes) or "—"

    @property
    def all_released(self) -> bool:
        return not self.unreleased

    @property
    def release_at(self) -> str | None:
        """When the last relied-on embargoed result is published, if known."""
        times = [str(r.get("release_at")) for r in self.unreleased if r.get("release_at")]
        if len(times) < len(self.unreleased):
            return None
        return max(times) if times else None


def _sorted(pool: list[_Result]) -> list[_Result]:
    return sorted(pool, key=lambda r: qg.rank(r.grade, r.qtype) or 99)


def _eval_profile(c: dict[str, Any], results: list[_Result]) -> ConditionOutcome:
    segments = _profile_segments(c["min_grade"], c.get("qualification_type")) or []
    wanted: dict[str, list[str]] = {}
    for qtype, grades in segments:
        wanted.setdefault(qtype, []).extend(grades)
    relied: list[dict[str, Any]] = []
    pending: list[str] = []
    missed: list[str] = []
    achieved: list[str] = []
    for qtype, grades in wanted.items():
        pool = _sorted([r for r in results if r.qtype == qtype])
        relied.extend(r.raw for r in pool)
        if len(pool) < len(grades):
            pending.append(f"{len(pool)} of {len(grades)} {qtype} result(s) in")
            continue
        want = sorted(grades, key=lambda g: qg.rank(g, qtype) or 99)
        got = [r.grade for r in pool]
        achieved.append(f"{''.join(got)} {qtype}")
        if not all((qg.rank(got[i], qtype) or 99) <= (qg.rank(want[i], qtype) or 99)
                   for i in range(len(want))):
            missed.append(f"{''.join(want)} {qtype} required")
    if missed:
        return ConditionOutcome(c, MISSED, ", ".join(missed) + f" — achieved {', '.join(achieved)}.", relied)
    if pending:
        return ConditionOutcome(c, PENDING, "; ".join(pending) + ".", relied)
    return ConditionOutcome(c, MET, f"achieved {', '.join(achieved)}.", relied)


def _alternatives(subject: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s*(?:/|\bor\b)\s*", subject) if p.strip()]


def _eval_subject(c: dict[str, Any], results: list[_Result]) -> ConditionOutcome:
    qtype = c.get("qualification_type") or "A Level"
    options = _alternatives(c.get("subject") or "")
    need = c.get("count") or 1
    relied: list[dict[str, Any]] = []
    met, missing, below = [], [], []
    for subject in options:
        hits = [r for r in results if r.qtype == qtype and _subject_matches(subject, r.subject)]
        if not hits:
            missing.append(subject)
            continue
        best = _sorted(hits)[0]
        relied.append(best.raw)
        if qg.meets(best.grade, c["min_grade"], qtype):
            met.append(f"{best.subject} {best.grade}")
        else:
            below.append(f"{best.subject} {best.grade}")
    if len(met) >= need:
        return ConditionOutcome(c, MET, ", ".join(met) + ".", relied)
    if len(met) + len(missing) >= need and missing:
        return ConditionOutcome(c, PENDING, f"no {qtype} result in {', '.join(missing)} yet.", relied)
    return ConditionOutcome(c, MISSED, (", ".join(below) or "not taken") + ".", relied)


def _eval_qualification(c: dict[str, Any], results: list[_Result]) -> ConditionOutcome:
    qtype = c["qualification_type"]
    pool = [r for r in results if r.qtype == qtype
            and (not c.get("subject") or _subject_matches(c["subject"], r.subject))]
    if not pool:
        return ConditionOutcome(c, PENDING, f"no {qtype} result yet.", [])
    best = _sorted(pool)[0]
    ok = qg.meets(best.grade, c["min_grade"], qtype)
    return ConditionOutcome(c, MET if ok else MISSED, f"{qtype} {best.grade}.", [r.raw for r in pool])


def _eval_gcse(c: dict[str, Any], results: list[_Result]) -> ConditionOutcome:
    subjects = _subjects_in(c.get("subject") or "")
    relied: list[dict[str, Any]] = []
    unknown, below, ok = [], [], []
    for subject in subjects:
        hits = [r for r in results if r.qtype == "GCSE"
                and _subject_matches(subject, r.subject, loose_english=True)]
        if not hits:
            unknown.append(subject)
            continue
        best = _sorted(hits)[0]
        relied.append(best.raw)
        (ok if qg.meets(best.grade, c["min_grade"], "GCSE") else below).append(
            f"{best.subject} {best.grade}")
    if below:
        return ConditionOutcome(c, MISSED, ", ".join(below) + ".", relied)
    if unknown:
        # GCSEs are usually sat before the sixth form and need not be on
        # its record — a missing one is checked against the certificate.
        return ConditionOutcome(c, REVIEW, f"no GCSE {', '.join(unknown)} on record — check the certificate.", relied)
    return ConditionOutcome(c, MET, ", ".join(ok) + ".", relied)


def _eval_tariff(c: dict[str, Any], results: list[_Result]) -> ConditionOutcome:
    restrict = c.get("qualification_type")
    pool = [r for r in results if qg.is_tariff_bearing(r.qtype)
            and (not restrict or r.qtype == restrict)]
    if not pool:
        return ConditionOutcome(c, PENDING, "no tariff-bearing results yet.", [])
    known: list[int] = []
    unknown: list[str] = []
    for r in pool:
        pts = qg.tariff_points(r.qtype, r.grade)
        if pts is None:
            unknown.append(f"{r.subject} {r.grade}")
        else:
            known.append(pts)
    count = c.get("count")
    if count and len(pool) < count:
        return ConditionOutcome(c, PENDING, f"{len(pool)} of {count} results in.", [r.raw for r in pool])
    known.sort(reverse=True)
    total = sum(known[:count] if count else known)
    need = c["min_points"]
    relied = [r.raw for r in pool]
    if total >= need:
        return ConditionOutcome(c, MET, f"{total} points (need {need}).", relied)
    if unknown:
        return ConditionOutcome(c, REVIEW, f"{total} known points (need {need}); no tariff value here for {', '.join(unknown)}.", relied)
    return ConditionOutcome(c, MISSED, f"{total} points (need {need}).", relied)


_EVALUATORS = {
    "grade_profile": _eval_profile,
    "subject_grade": _eval_subject,
    "qualification_grade": _eval_qualification,
    "gcse_requirement": _eval_gcse,
    "tariff_points": _eval_tariff,
}


def evaluate(conditions: Iterable[dict[str, Any]],
             results: Iterable[dict[str, Any]], *,
             now: _dt.datetime | None = None) -> Evaluation:
    """Check *results* against every condition.

    The overall verdict: :data:`MISSED` if any condition is missed,
    otherwise :data:`PENDING` if any is still waiting for a result,
    otherwise :data:`REVIEW` if any needs a person, otherwise :data:`MET`.
    No conditions at all is :data:`REVIEW` — there is nothing to check.

    ``unreleased`` lists the results the verdict relied on that are not
    yet published, so a caller can hold any action until they are.
    """
    results = list(results or ())
    conds = list(conditions or ())
    typed = _prepare(results)
    outcomes: list[ConditionOutcome] = []
    if not typed and any(c.get("kind") != "other_text" for c in conds):
        outcomes = [ConditionOutcome(c, PENDING if c.get("kind") != "other_text" else REVIEW,
                                     "no results yet." if c.get("kind") != "other_text"
                                     else "checked by hand.")
                    for c in conds]
    else:
        for c in conds:
            fn = _EVALUATORS.get(c.get("kind"))
            if fn is None:
                outcomes.append(ConditionOutcome(c, REVIEW, "checked by hand."))
                continue
            try:
                outcomes.append(fn(c, typed))
            except Exception as exc:  # a malformed stored row is a person's job
                outcomes.append(ConditionOutcome(c, REVIEW, f"could not be checked ({exc})."))
    verdicts = {o.verdict for o in outcomes}
    if not outcomes:
        verdict = REVIEW
    elif MISSED in verdicts:
        verdict = MISSED
    elif PENDING in verdicts:
        verdict = PENDING
    elif REVIEW in verdicts:
        verdict = REVIEW
    else:
        verdict = MET
    relied: list[dict[str, Any]] = []
    seen: set[int] = set()
    for o in outcomes:
        for r in o.relied:
            if id(r) not in seen:
                seen.add(id(r))
                relied.append(r)
    unreleased = [r for r in relied if not is_released(r, now)]
    return Evaluation(verdict, outcomes, relied, unreleased)
