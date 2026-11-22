"""Behaviour Report: positive and negative behaviour, detentions and
suspensions / exclusions over any date range (default: this school year to
date).

Read-only. The figures come from the Behaviour & Rewards log
(:mod:`modules.behaviour.domain.behaviour`; withdrawn entries never count), the
detentions register (:mod:`modules.behaviour.domain.detentions`; rescheduled
ones are counted once, at their new date) and suspension / exclusion cases
(:mod:`modules.behaviour.domain.exclusions`; withdrawn and overturned cases
left out).

* Positive vs negative counts and points, broken down by type, year, form,
  subject, member of staff, weekday and hour.
* Rates per 100 pupils (on roll at some point in the range): positive and
  negative entries, suspensions and permanent exclusions - the DfE
  "suspension rate" is suspensions / pupils x 100.
* Week-by-week trend.
* Pupils of concern: most negative points in the range, with their negative
  entries, missed detentions and suspension days.
* Detentions set / attended / missed / excused / cancelled with the
  attendance rate, by type.
* Suspensions and exclusions: cases, pupils, school days, by type and
  census reason category.
* CSV export of any table.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log

ValidationError = RC.ValidationError
PermissionDenied = RC.PermissionDenied
NotFound = RC.NotFound

#: Breakdowns of the behaviour log.
BREAKDOWNS: dict[str, str] = {
    "type": "Type", "year": "Year group", "form": "Form", "subject": "Subject",
    "staff": "Member of staff", "weekday": "Day of week", "hour": "Hour",
    "severity": "Severity", "location": "Location",
}
SECTIONS: dict[str, str] = {
    "summary": "Summary",
    "breakdown": "Breakdown",
    "weeks": "Trend by week",
    "concern": "Pupils of concern",
    "detentions": "Detentions",
    "exclusions": "Suspensions & exclusions",
    "pupils": "All pupils",
}


def _key(by: str, e: BH.Entry) -> str:
    if by == "type":
        return e.incident_type
    if by == "year":
        return f"Year {e.pupil_year}"
    if by == "form":
        return f"{e.pupil_year} {e.form_group or '(no form)'}"
    if by == "subject":
        return e.subject_code or "(no subject)"
    if by == "staff":
        return e.raised_by or e.raised_by_username or "(unknown)"
    if by == "weekday":
        return RC.weekday_name(e.entry_date)
    if by == "hour":
        return f"{e.entry_time[:2]}:00" if e.entry_time else "(no time)"
    if by == "severity":
        return e.severity
    if by == "location":
        return e.location or "(not recorded)"
    raise ValidationError([f"Break down by one of {', '.join(BREAKDOWNS)}"])


@dataclass(frozen=True)
class Report:
    start: str
    end: str
    scope: str
    pupils_on_roll: int
    entries: list[BH.Entry]
    detentions: list[DT.Detention]
    cases: list[EX.Case]
    pupils: list[P.Pupil]

    # ── Behaviour ────────────────────────────────────────────────────

    @property
    def positive(self) -> list[BH.Entry]:
        return [e for e in self.entries if e.polarity == "positive"]

    @property
    def negative(self) -> list[BH.Entry]:
        return [e for e in self.entries if e.polarity == "negative"]

    def totals(self) -> dict[str, Any]:
        pos, neg = self.positive, self.negative
        susp = [c for c in self.cases if c.case_type == EX.SUSPENSION]
        perm = [c for c in self.cases if c.case_type == EX.PERMANENT]
        n = self.pupils_on_roll
        d = self.detention_summary()
        return {
            "pupils_on_roll": n, "entries": len(self.entries),
            "positive": len(pos), "negative": len(neg),
            "positive_points": sum(e.points for e in pos),
            "negative_points": sum(e.points for e in neg),
            "net_points": sum(e.points for e in self.entries),
            "ratio": round(len(pos) / len(neg), 2) if neg else None,
            "pupils_with_negative": len({e.pupil_id for e in neg}),
            "pupils_with_positive": len({e.pupil_id for e in pos}),
            "positive_per_100": RC.per_100(len(pos), n),
            "negative_per_100": RC.per_100(len(neg), n),
            "detentions_set": d["set"], "detentions_attended": d["Attended"],
            "detentions_missed": d["Missed"], "detention_attendance_pct": d["attendance_pct"],
            "suspensions": len(susp), "suspension_days": sum(c.days or 0 for c in susp),
            "pupils_suspended": len({c.pupil_id for c in susp}),
            "suspension_rate": RC.per_100(len(susp), n),
            "permanent_exclusions": len(perm),
            "permanent_exclusion_rate": RC.per_100(len(perm), n),
            "internal_exclusions": sum(1 for c in self.cases
                                       if c.case_type == "Internal exclusion"),
        }

    def breakdown(self, by: str = "type") -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for e in self.entries:
            k = _key(by, e)
            g = groups.setdefault(k, {"group": k, "positive": 0, "negative": 0,
                                      "positive_points": 0, "negative_points": 0,
                                      "points": 0, "pupils": set()})
            g[e.polarity] += 1
            g[f"{e.polarity}_points"] += e.points
            g["points"] += e.points
            g["pupils"].add(e.pupil_id)
        order = {d: i for i, d in enumerate(RC.WEEKDAYS)}
        rows = [{**g, "pupils": len(g["pupils"])} for g in groups.values()]
        if by in ("weekday", "hour"):
            return sorted(rows, key=lambda g: (order.get(g["group"], 99), g["group"]))
        return sorted(rows, key=lambda g: (-(g["positive"] + g["negative"]), g["group"]))

    def weeks(self) -> list[dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in self.entries:
            w = out.setdefault(RC.week_start(e.entry_date),
                               {"week": RC.week_start(e.entry_date), "positive": 0,
                                "negative": 0, "points": 0, "detentions": 0,
                                "suspensions": 0})
            w[e.polarity] += 1
            w["points"] += e.points
        for d in self.detentions:
            out.setdefault(RC.week_start(d.detention_date),
                           {"week": RC.week_start(d.detention_date), "positive": 0,
                            "negative": 0, "points": 0, "detentions": 0,
                            "suspensions": 0})["detentions"] += 1
        for c in self.cases:
            if c.case_type in EX.FORMAL:
                out.setdefault(RC.week_start(c.start_date),
                               {"week": RC.week_start(c.start_date), "positive": 0,
                                "negative": 0, "points": 0, "detentions": 0,
                                "suspensions": 0})["suspensions"] += 1
        return [out[k] for k in sorted(out)]

    def per_pupil(self) -> list[dict[str, Any]]:
        by: dict[int, dict[str, Any]] = {}

        def row(pid: int) -> dict[str, Any]:
            p = self._pupil(pid)
            return by.setdefault(pid, {
                "pupil_id": pid, "admission_no": p.admission_no if p else "",
                "pupil_name": RC.name(p) if p else f"#{pid}",
                "year_group": p.year_group if p else "", "form_group": p.form_group if p else "",
                "positive": 0, "negative": 0, "positive_points": 0, "negative_points": 0,
                "net": 0, "detentions": 0, "missed": 0, "suspensions": 0,
                "suspension_days": 0, "permanent": 0})
        for e in self.entries:
            r = row(e.pupil_id)
            r[e.polarity] += 1
            r[f"{e.polarity}_points"] += e.points
            r["net"] += e.points
        for d in self.detentions:
            r = row(d.pupil_id)
            r["detentions"] += 1
            r["missed"] += d.status == "Missed"
        for c in self.cases:
            r = row(c.pupil_id)
            if c.case_type == EX.SUSPENSION:
                r["suspensions"] += 1
                r["suspension_days"] += c.days or 0
            elif c.case_type == EX.PERMANENT:
                r["permanent"] += 1
        return sorted(by.values(), key=lambda r: (r["net"], -r["negative"], r["pupil_name"]))

    def concern(self, limit: int = 25) -> list[dict[str, Any]]:
        """Pupils of concern: negative entries, missed detentions or a
        suspension, worst first (negative points, then counts)."""
        rows = [r for r in self.per_pupil()
                if r["negative"] or r["missed"] or r["suspensions"] or r["permanent"]]
        rows.sort(key=lambda r: (-r["permanent"], r["negative_points"] - 5 * r["missed"]
                                 - 10 * r["suspensions"], -r["negative"], r["pupil_name"]))
        return rows[:limit]

    def _pupil(self, pid: int) -> P.Pupil | None:
        if not hasattr(self, "_pmap"):
            object.__setattr__(self, "_pmap", {p.pupil_id: p for p in self.pupils})
        p = self._pmap.get(pid)  # type: ignore[attr-defined]
        return p if p is not None else P.get_pupil(pid)

    # ── Detentions and exclusions ────────────────────────────────────

    def detention_summary(self) -> dict[str, Any]:
        c = Counter(d.status for d in self.detentions)
        done = c["Attended"] + c["Missed"]
        return {"set": len(self.detentions), **{s: c.get(s, 0) for s in DT.DETENTION_STATUSES},
                "attendance_pct": RC.pct(c["Attended"], done, 0),
                "minutes_served": sum(d.duration_min for d in self.detentions
                                      if d.status == "Attended"),
                "pupils": len({d.pupil_id for d in self.detentions}),
                "by_type": dict(Counter(d.detention_type for d in self.detentions))}

    def detention_rows(self) -> list[list[Any]]:
        types = sorted({d.detention_type for d in self.detentions})
        out = []
        for t in [None, *types]:
            ds = [d for d in self.detentions if t is None or d.detention_type == t]
            c = Counter(d.status for d in ds)
            done = c["Attended"] + c["Missed"]
            out.append([t or "All types", len(ds), c["Scheduled"], c["Attended"], c["Missed"],
                        c["Excused"], c["Cancelled"], RC.pct(c["Attended"], done, 0),
                        len({d.pupil_id for d in ds})])
        return out

    def exclusion_rows(self) -> list[list[Any]]:
        out = []
        for label, keyf in (("Type", lambda c: c.case_type),
                            ("Reason", lambda c: c.reason_category or "(no category)"),
                            ("Year", lambda c: f"Year {c.pupil_year}")):
            groups: dict[str, list[EX.Case]] = {}
            for c in self.cases:
                groups.setdefault(keyf(c), []).append(c)
            for k in sorted(groups):
                cs = groups[k]
                out.append([label, k, len(cs), len({c.pupil_id for c in cs}),
                            sum(c.days or 0 for c in cs),
                            RC.per_100(len(cs), self.pupils_on_roll)])
        return out


# ── Building ─────────────────────────────────────────────────────────

def build(actor: Principal, start: Any = None, end: Any = None, *, year_group: Any = None,
          form: str | None = None, pupil_id: Any = None) -> Report:
    RC.require_staff(actor, "behaviour_report.run")
    s, e = RC.date_range(start, end, cap_today=False)
    si, ei = s.isoformat(), e.isoformat()
    yg, pid = RC.int_or_none(year_group), RC.int_or_none(pupil_id)
    pupils = RC.cohort(si, ei, year_group=yg, form=form, pupil_id=pid)
    entries = BH.list_entries(date_from=si, date_to=ei, year_group=yg,
                              form_group=form or None, pupil_id=pid, include_withdrawn=False)
    dets = [d for d in DT.list_detentions(date_from=si, date_to=ei, year_group=yg,
                                          form_group=form or None, pupil_id=pid)
            if d.status != "Rescheduled"]
    cases = [c for c in EX.list_cases(date_from=si, date_to=ei, year_group=yg, pupil_id=pid)
             if c.counts and (not form or (c.form_group or "").lower() == form.lower())]
    scope = ("Pupil " + (RC.name(pupils[0]) if pupils else f"#{pid}")) if pid else \
        (f"Form {form}" if form else (f"Year {yg}" if yg else "Whole school"))
    report = Report(start=si, end=ei, scope=scope, pupils_on_roll=len(pupils),
                    entries=entries, detentions=dets, cases=cases, pupils=pupils)
    activity_log.record("behaviour_report.run", principal=actor, entries=len(entries),
                        year=yg or "", form=form or "")
    return report


def pupil_text(report: Report, pupil_id: int) -> str:
    """One pupil's lines in the range (drill down)."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    es = [e for e in report.entries if e.pupil_id == p.pupil_id]
    ds = [d for d in report.detentions if d.pupil_id == p.pupil_id]
    cs = [c for c in report.cases if c.pupil_id == p.pupil_id]
    lines = [f"{p.display_name} ({p.admission_no}) - Year {p.year_group} {p.form_group or ''}",
             f"{report.start} to {report.end}", "",
             f"Positive {sum(1 for e in es if e.polarity == 'positive')} "
             f"({sum(e.points for e in es if e.points > 0)} pts), negative "
             f"{sum(1 for e in es if e.polarity == 'negative')} "
             f"({sum(e.points for e in es if e.points < 0)} pts), net "
             f"{sum(e.points for e in es)}", "", "Entries:"]
    lines += [f"  {e.entry_date} {e.entry_time or '':5} {e.points:+d}  {e.incident_type:<18} "
              f"{e.subject_code or '':6} {e.raised_by or ''}" for e in es] or ["  (none)"]
    lines += ["", "Detentions:"]
    lines += [f"  {d.detention_date} {d.detention_type:<12} {d.status}" for d in ds] \
        or ["  (none)"]
    lines += ["", "Suspensions & exclusions:"]
    lines += [f"  {c.period:<28} {c.case_type:<22} {c.days or 0} day(s)  {c.status}"
              for c in cs] or ["  (none)"]
    return "\n".join(lines)


# ── Tables and export ────────────────────────────────────────────────

_PUPIL_HEAD = ["Admission no", "Pupil", "Year", "Form", "Positive", "Negative",
               "Positive points", "Negative points", "Net", "Detentions", "Missed",
               "Suspensions", "Suspension days", "Permanent"]


def _pupil_cells(r: dict[str, Any]) -> list[Any]:
    return [r["admission_no"], r["pupil_name"], r["year_group"], r["form_group"],
            r["positive"], r["negative"], r["positive_points"], r["negative_points"], r["net"],
            r["detentions"], r["missed"], r["suspensions"], r["suspension_days"],
            r["permanent"]]


_TOTAL_LABELS = {
    "pupils_on_roll": "Pupils on roll (in the range)", "entries": "Behaviour entries",
    "positive": "Positive entries", "negative": "Negative entries",
    "positive_points": "Positive points", "negative_points": "Negative points",
    "net_points": "Net points", "ratio": "Positive : negative ratio",
    "pupils_with_positive": "Pupils with a positive entry",
    "pupils_with_negative": "Pupils with a negative entry",
    "positive_per_100": "Positive entries per 100 pupils",
    "negative_per_100": "Negative entries per 100 pupils",
    "detentions_set": "Detentions set", "detentions_attended": "Detentions attended",
    "detentions_missed": "Detentions missed",
    "detention_attendance_pct": "Detention attendance %",
    "suspensions": "Suspensions", "suspension_days": "Suspension days (school days)",
    "pupils_suspended": "Pupils suspended", "suspension_rate": "Suspension rate (per 100)",
    "permanent_exclusions": "Permanent exclusions",
    "permanent_exclusion_rate": "Permanent exclusion rate (per 100)",
    "internal_exclusions": "Internal exclusions",
}


def table(report: Report, section: str, by: str = "type") -> tuple[list[str], list[list[Any]]]:
    if section == "summary":
        t = report.totals()
        return ["Measure", "Value"], [["Period", f"{report.start} to {report.end}"],
                                      ["Covering", report.scope],
                                      *([lab, t[k]] for k, lab in _TOTAL_LABELS.items())]
    if section == "breakdown":
        return ([BREAKDOWNS.get(by, by), "Positive", "Negative", "Positive points",
                 "Negative points", "Net points", "Pupils"],
                [[g["group"], g["positive"], g["negative"], g["positive_points"],
                  g["negative_points"], g["points"], g["pupils"]] for g in report.breakdown(by)])
    if section == "weeks":
        return (["Week of", "Positive", "Negative", "Net points", "Detentions", "Suspensions"],
                [[w["week"], w["positive"], w["negative"], w["points"], w["detentions"],
                  w["suspensions"]] for w in report.weeks()])
    if section == "concern":
        return _PUPIL_HEAD, [_pupil_cells(r) for r in report.concern()]
    if section == "pupils":
        return _PUPIL_HEAD, [_pupil_cells(r) for r in report.per_pupil()]
    if section == "detentions":
        return (["Type", "Set", "Scheduled", "Attended", "Missed", "Excused", "Cancelled",
                 "Attendance %", "Pupils"], report.detention_rows())
    if section == "exclusions":
        return (["By", "Group", "Cases", "Pupils", "School days", "Per 100 pupils"],
                report.exclusion_rows())
    raise ValidationError([f"Section must be one of {', '.join(SECTIONS)}"])


def export_csv(path: str | Path, report: Report, section: str = "summary", *,
               actor: Principal, by: str = "type") -> int:
    RC.require_staff(actor, "behaviour_report.export")
    head, rows = table(report, section, by)
    return RC.write_csv(path, head, rows, actor=actor, action="behaviour_report.export",
                        section=section)
