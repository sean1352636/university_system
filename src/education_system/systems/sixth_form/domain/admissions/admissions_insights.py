"""Admissions conversion, stage timing, reasons and capacity reports.

Complements :mod:`applicant_reports` (funnel, source, time to decision,
weekly volume, subject demand, letters): these break the pipeline down
by feeder school, programme, cycle and source, show how long applicants
spend in each stage, why they withdrew or declined, and offers against
the places set for each programme.

Stages are worked out from the status an applicant is at *and* every
status they passed through (the timeline's ``Status: A → B`` entries),
so an applicant who was offered a place and later withdrew still counts
as offered.

Readable with the ``admissions`` or ``reports`` capability.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import statistics
from dataclasses import dataclass, field
from typing import Any, Iterable

from education_system.systems.sixth_form.domain.admissions import _guard
from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
)

DIMENSIONS: tuple[str, ...] = ("feeder_school", "programme", "cycle",
                               "source")
_OFFERED = {"Offer Made", "Offer Accepted", "Offer Declined", "Deferred",
            "Enrolled"}
_ACCEPTED = {"Offer Accepted", "Deferred", "Enrolled"}
#: Pipeline stages timed by :func:`time_in_stage`, in order.
STAGES: tuple[str, ...] = (
    _adm.ONLINE_UNVERIFIED, "Submitted", "Under Review",
    "Interview Scheduled", "Interviewed", "Waitlisted", "Offer Made",
    "Offer Accepted", "Deferred",
)


def _require() -> None:
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    _guard.require_any((access.ADMISSIONS, access.REPORTS), "admissions reports")


def _norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


# ── Data loading (one pass over the admissions DB) ─────────────────

@dataclass
class _App:
    row: Any
    statuses_seen: set[str]
    history: list[tuple[str, str]]          # (at, status) in order
    choices: list[tuple[str, str]]

    @property
    def id(self) -> str:
        return self.row["applicant_id"]

    @property
    def applied(self) -> bool:
        return self.row["status"] != _adm.ONLINE_UNVERIFIED or len(
            self.statuses_seen) > 1

    @property
    def offered(self) -> bool:
        return bool(self.statuses_seen & _OFFERED) or bool(
            self.row["converted_student_id"])

    @property
    def accepted(self) -> bool:
        return bool(self.statuses_seen & _ACCEPTED) or bool(
            self.row["converted_student_id"])

    @property
    def enrolled(self) -> bool:
        return self.row["status"] == "Enrolled" or bool(
            self.row["converted_student_id"])


def _load(cycle: str | None = None) -> list[_App]:
    _adm.init_db()
    where, args = "WHERE archived_at IS NULL", []
    if cycle:
        where += " AND intake_year = ?"
        args.append(cycle.strip())
    with _adm._connect() as conn:
        apps = conn.execute(f"SELECT * FROM admissions_applicants {where}",  # noqa: S608 — fixed clauses
                            args).fetchall()
        ids = {a["applicant_id"] for a in apps}
        events = conn.execute(
            "SELECT applicant_id, at, detail FROM admissions_events "
            "WHERE detail LIKE 'Status: %' ORDER BY at, id").fetchall()
        choice_rows = conn.execute(
            "SELECT applicant_id, qualification_type, subject FROM "
            "admissions_programme_choices ORDER BY sort_order, id").fetchall()
    hist: dict[str, list[tuple[str, str]]] = {}
    started: dict[str, str] = {}
    for e in events:
        aid = e["applicant_id"]
        if aid not in ids or "→" not in e["detail"]:
            continue
        old, new = e["detail"][len("Status:"):].split("→", 1)
        started.setdefault(aid, old.strip())
        hist.setdefault(aid, []).append((e["at"], new.strip()))
    choices: dict[str, list[tuple[str, str]]] = {}
    for c in choice_rows:
        if c["applicant_id"] in ids:
            choices.setdefault(c["applicant_id"], []).append(
                (c["qualification_type"], c["subject"]))
    out = []
    for a in apps:
        aid = a["applicant_id"]
        # Before its first recorded change an application was in the
        # status that change moved it from; with none, it never moved.
        history = [(a["created_at"] or a["submitted_at"],
                    started.get(aid, a["status"]))] + hist.get(aid, [])
        seen = {st for _at, st in history} | {a["status"]}
        ch = choices.get(aid) or [("A Level", x) for x in (
            a["subject_1"], a["subject_2"], a["subject_3"]) if x]
        out.append(_App(row=a, statuses_seen=seen, history=history,
                        choices=ch))
    return out


# ── Conversion rates ───────────────────────────────────────────────

@dataclass
class ConversionRow:
    group: str
    applied: int = 0
    offered: int = 0
    accepted: int = 0
    enrolled: int = 0
    is_feeder: bool | None = None

    @staticmethod
    def _pct(n: int, d: int) -> float | None:
        return round(100.0 * n / d, 1) if d else None

    @property
    def offer_rate(self) -> float | None:
        return self._pct(self.offered, self.applied)

    @property
    def acceptance_rate(self) -> float | None:
        return self._pct(self.accepted, self.offered)

    @property
    def enrolment_rate(self) -> float | None:
        return self._pct(self.enrolled, self.accepted)

    @property
    def overall_rate(self) -> float | None:
        return self._pct(self.enrolled, self.applied)

    def as_dict(self) -> dict[str, Any]:
        d = {"group": self.group, "applied": self.applied,
             "offered": self.offered, "accepted": self.accepted,
             "enrolled": self.enrolled, "offer_rate": self.offer_rate,
             "acceptance_rate": self.acceptance_rate,
             "enrolment_rate": self.enrolment_rate,
             "overall_rate": self.overall_rate}
        if self.is_feeder is not None:
            d["feeder_school"] = self.is_feeder
        return d


def _groups(app: _App, dimension: str) -> list[str]:
    r = app.row
    if dimension == "feeder_school":
        return [" ".join((r["previous_school"] or "").split()) or "(not recorded)"]
    if dimension == "programme":
        return [f"{q} {s}" for q, s in app.choices] or ["(no programme)"]
    if dimension == "cycle":
        return [r["intake_year"] or "(no intake year)"]
    if dimension == "source":
        return [r["application_source"] or "(not recorded)"]
    raise _adm.ValidationError(
        f"Group by one of: {', '.join(DIMENSIONS)}")


def conversion_by(dimension: str, *, cycle: str | None = None
                  ) -> list[ConversionRow]:
    """Applied → offered → accepted → enrolled counts and rates per
    feeder school, programme, cycle or source. An applicant with several
    programmes counts once in each."""
    _require()
    if dimension not in DIMENSIONS:
        raise _adm.ValidationError(f"Group by one of: {', '.join(DIMENSIONS)}")
    feeders: dict[str, str] = {}
    if dimension == "feeder_school":
        from education_system.systems.sixth_form.domain.admissions import capacity
        feeders = {_norm(f.name): f.name for f in capacity.list_feeder_schools(
            include_inactive=True)}
    rows: dict[str, ConversionRow] = {}
    for app in _load(cycle):
        if not app.applied:
            continue
        groups = _groups(app, dimension)
        if feeders:
            # Spellings of a registered feeder school count as that school.
            groups = [feeders.get(_norm(g), g) for g in groups]
        for g in dict.fromkeys(groups):
            row = rows.setdefault(g, ConversionRow(group=g))
            row.applied += 1
            row.offered += app.offered
            row.accepted += app.accepted
            row.enrolled += app.enrolled
    for row in rows.values():
        if dimension == "feeder_school":
            row.is_feeder = _norm(row.group) in feeders
    return sorted(rows.values(), key=lambda r: (-r.applied, r.group.lower()))


def conversion_totals(*, cycle: str | None = None) -> ConversionRow:
    """The whole pipeline as one row."""
    _require()
    total = ConversionRow(group=cycle or "All cycles")
    for app in _load(cycle):
        if app.applied:
            total.applied += 1
            total.offered += app.offered
            total.accepted += app.accepted
            total.enrolled += app.enrolled
    return total


# ── Time in stage ──────────────────────────────────────────────────

@dataclass
class StageTime:
    stage: str
    applicants: int              # passed through (or are in) the stage
    current: int                 # in it now
    average_days: float | None
    median_days: float | None
    longest_days: float | None
    durations: list[float] = field(default_factory=list, repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "applicants": self.applicants,
                "current": self.current, "average_days": self.average_days,
                "median_days": self.median_days,
                "longest_days": self.longest_days}


def _parse(ts: str | None) -> _dt.datetime | None:
    if not ts:
        return None
    try:
        return _dt.datetime.fromisoformat(ts.replace("T", " ")[:19])
    except ValueError:
        try:
            return _dt.datetime.fromisoformat(ts[:10])
        except ValueError:
            return None


def time_in_stage(*, cycle: str | None = None,
                  now: _dt.datetime | None = None) -> list[StageTime]:
    """How long applicants spend at each stage. Finished stays use the
    time to the next status change; applicants still in a stage count up
    to *now*."""
    _require()
    # Timeline stamps are SQLite datetime('now'), i.e. UTC.
    now = now or _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
    spans: dict[str, list[float]] = {s: [] for s in STAGES}
    current: dict[str, int] = {s: 0 for s in STAGES}
    for app in _load(cycle):
        hist = [(t, s) for t, s in ((_parse(at), st) for at, st in app.history)
                if t is not None]
        for i, (start, stage) in enumerate(hist):
            if stage not in spans:
                continue
            end = hist[i + 1][0] if i + 1 < len(hist) else None
            if end is None:
                if stage != app.row["status"]:
                    continue
                current[stage] += 1
                end = now
            spans[stage].append(max((end - start).total_seconds(), 0) / 86400)
    out = []
    for s in STAGES:
        d = spans[s]
        out.append(StageTime(
            stage=s, applicants=len(d), current=current[s],
            average_days=round(statistics.fmean(d), 1) if d else None,
            median_days=round(statistics.median(d), 1) if d else None,
            longest_days=round(max(d), 1) if d else None, durations=d))
    return out


# ── Withdrawal / decline / rejection reasons ───────────────────────

@dataclass
class ReasonsBreakdown:
    withdrawn: dict[str, int] = field(default_factory=dict)
    declined: dict[str, int] = field(default_factory=dict)
    rejected: dict[str, int] = field(default_factory=dict)

    def rows(self) -> list[dict[str, Any]]:
        out = []
        for outcome, counts in (("Withdrawn", self.withdrawn),
                                ("Offer Declined", self.declined),
                                ("Rejected", self.rejected)):
            total = sum(counts.values())
            for reason, n in sorted(counts.items(), key=lambda kv: -kv[1]):
                out.append({"outcome": outcome, "reason": reason, "count": n,
                            "share": round(100.0 * n / total, 1)
                            if total else None})
        return out


def reasons_breakdown(*, cycle: str | None = None) -> ReasonsBreakdown:
    """Why applicants withdrew, declined offers or were turned down."""
    _require()
    out = ReasonsBreakdown()
    for app in _load(cycle):
        r = app.row
        if r["status"] == "Withdrawn":
            key = r["withdrawal_reason"] or "(no reason recorded)"
            out.withdrawn[key] = out.withdrawn.get(key, 0) + 1
        elif r["status"] == "Offer Declined":
            key = r["withdrawal_reason"] or "(no reason recorded)"
            out.declined[key] = out.declined.get(key, 0) + 1
        elif r["status"] == "Rejected":
            key = r["decision_reason"] or "(no reason recorded)"
            out.rejected[key] = out.rejected.get(key, 0) + 1
    return out


# ── Offers against capacity ────────────────────────────────────────

@dataclass
class CapacityRow:
    programme: str
    places: int | None
    applications: int
    offers_made: int
    accepted: int
    enrolled: int
    places_left: int | None
    oversubscribed: bool

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def offers_vs_capacity(cycle: str) -> list[CapacityRow]:
    """Per programme in *cycle*: places set, applications, offers waiting,
    accepted (incl. deferred in), enrolled and places left."""
    _require()
    from education_system.systems.sixth_form.domain.admissions import capacity
    counts: dict[str, dict[str, int]] = {}
    for app in _load(cycle):
        status = app.row["status"]
        for q, s in app.choices:
            key = f"{_norm(q)}|{_norm(s)}"
            c = counts.setdefault(key, {"applications": 0, "Offer Made": 0,
                                        "accepted": 0, "Enrolled": 0})
            if app.applied:
                c["applications"] += 1
            if status == "Offer Made":
                c["Offer Made"] += 1
            elif status in ("Offer Accepted", "Deferred"):
                c["accepted"] += 1
            elif status == "Enrolled":
                c["Enrolled"] += 1
    out = []
    for p in capacity.programme_places(cycle):
        c = counts.get(f"{_norm(p.qualification_type)}|{_norm(p.subject)}", {})
        out.append(CapacityRow(
            programme=p.label, places=p.places,
            applications=c.get("applications", 0),
            offers_made=c.get("Offer Made", 0), accepted=c.get("accepted", 0),
            enrolled=c.get("Enrolled", 0), places_left=p.places_left,
            oversubscribed=p.oversubscribed))
    return out


# ── CSV ────────────────────────────────────────────────────────────

def to_csv(rows: Iterable[Any]) -> str:
    """CSV text for any of these reports' rows (objects with
    ``as_dict()`` or plain dicts)."""
    dicts = [r.as_dict() if hasattr(r, "as_dict") else dict(r) for r in rows]
    if not dicts:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(dicts[0].keys()))
    w.writeheader()
    for d in dicts:
        w.writerow({k: ("" if v is None else v) for k, v in d.items()})
    return buf.getvalue()
