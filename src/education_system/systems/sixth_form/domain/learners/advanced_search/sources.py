"""Relative/group/UCAS/clash/similar-student lookups and the per-scope
``_search_<scope>`` readers (``_ADAPTERS``) for Advanced Search.

Split out of ``advanced_search.py`` (2026-10-22); that module is now a
facade re-exporting every name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only — avoids import cycles
    from .models import QueryOptions
    from .query import ParsedQuery

import re
from dataclasses import field
from typing import Any, Callable

from .models import (  # noqa: F401
    Clash,
    GroupRollup,
    Hit,
    Relative,
    SimilarStudent,
    UcasCluster,
    UcasPeer,
    ValidationError,
)
from ._db import (  # noqa: F401
    logger,
)
from .matching import (  # noqa: F401
    _emit,
    _filter_match,
    _first_attr,
    _trim,
)


def _norm_phone(p: str | None) -> str:
    return re.sub(r"\D", "", p or "")


# ── 13. Family / sibling linkage ──────────────────────────────────

def _home_key(s: Any) -> tuple[str, str] | None:
    """Postcode plus first address line, normalised, or None when either is
    missing: a postcode alone covers a whole street."""
    postcode = re.sub(r"\s", "", (getattr(s, "postcode", "") or "").upper())
    first = (getattr(s, "address", "") or "").strip().splitlines()
    line = re.sub(r"[^a-z0-9]", "", first[0].lower()) if first else ""
    return (postcode, line) if postcode and line else None


def find_relatives(student_id: str) -> list[Relative]:
    """Students likely related to ``student_id`` — shared emergency-contact
    phone or name, a shared home address/postcode, or a shared surname with
    a shared contact."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as m,
    )
    target = m.get_student(student_id)
    if target is None:
        raise ValidationError(f"No student {student_id!r}")
    t_phone = _norm_phone(getattr(target, "emergency_contact_phone", ""))
    t_name = (getattr(target, "emergency_contact_name", "") or "").strip().lower()
    t_last = (getattr(target, "last_name", "") or "").strip().lower()
    t_home = _home_key(target)
    out: list[Relative] = []
    for s in m.list_students():
        if s.student_id == target.student_id:
            continue
        reasons: list[str] = []
        if t_home and _home_key(s) == t_home:
            reasons.append("same home address")
        if t_phone and _norm_phone(
                getattr(s, "emergency_contact_phone", "")) == t_phone:
            reasons.append("shared emergency contact phone")
        s_name = (getattr(s, "emergency_contact_name", "") or "").strip().lower()
        if t_name and s_name == t_name:
            reasons.append("shared emergency contact name")
        # Shared surname is corroborating evidence, not a link on its own.
        s_last = (getattr(s, "last_name", "") or "").strip().lower()
        if reasons and t_last and s_last == t_last:
            reasons.append("shared surname")
        if reasons:
            out.append(Relative(
                student_id=s.student_id, full_name=s.full_name,
                basis=", ".join(dict.fromkeys(reasons))))
    return out


# ── 14. Teaching-group rollups ────────────────────────────────────

def group_rollup(group_id: int) -> GroupRollup:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as cg,
    )
    grp = cg.get_group(group_id)
    if grp is None:
        raise ValidationError(f"No class group #{group_id}")
    members = list(cg.list_members(group_id))
    att_vals: list[float] = []
    points = 0
    bcount = 0
    open_concerns = 0
    try:
        from education_system.systems.sixth_form.domain.operations.reporting.progress import (
            progress as pr,
        )
        for sid in members:
            revs = pr.reviews_for_student(sid)
            latest = next((r for r in revs
                           if getattr(r, "attendance_pct", None) is not None),
                          None)
            if latest is not None and latest.attendance_pct is not None:
                att_vals.append(float(latest.attendance_pct))
    except Exception:
        logger.debug("group_rollup: progress unavailable")
    try:
        from education_system.systems.sixth_form.domain.pastoral.behaviour import (
            behaviour as bh,
        )
        for sid in members:
            for e in bh.entries_for_student(sid):
                points += int(getattr(e, "points", 0) or 0)
                bcount += 1
    except Exception:
        logger.debug("group_rollup: behaviour unavailable")
    try:
        from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import (
            attendance_concerns as ac,
        )
        for sid in members:
            for c in ac.concerns_for_student(sid):
                if (c.status or "").strip().lower() not in (
                        "closed", "resolved"):
                    open_concerns += 1
    except Exception:
        logger.debug("group_rollup: concerns unavailable")
    avg_att = round(sum(att_vals) / len(att_vals), 1) if att_vals else None
    return GroupRollup(
        group_id=group_id,
        group_name=getattr(grp, "group_name", f"Group #{group_id}"),
        member_count=len(members), avg_attendance=avg_att,
        behaviour_points=points, behaviour_count=bcount,
        open_concerns=open_concerns, members=members)


# ── 15. UCAS choice matching ──────────────────────────────────────

def ucas_peers(university: str,
               course_code: str | None = None) -> list[UcasPeer]:
    """Students with a UCAS choice at ``university`` (substring, case-
    insensitive), optionally narrowed to a course code."""
    uni = (university or "").strip().lower()
    if not uni:
        raise ValidationError("university is required")
    cc = (course_code or "").strip().lower() or None
    out: list[UcasPeer] = []
    from education_system.systems.sixth_form.domain.progression.university import ucas as u
    for app in u.list_applications():
        for ch in u.list_choices(app.application_id):
            if uni not in (ch.university or "").lower():
                continue
            if cc and cc != (ch.course_code or "").lower():
                continue
            out.append(UcasPeer(
                student_id=app.student_id, university=ch.university,
                course_code=ch.course_code, course_name=ch.course_name,
                status=ch.decision_status or app.status or ""))
    return out


def ucas_choice_clusters(*, by_course: bool = False,
                         min_size: int = 2) -> list[UcasCluster]:
    """Group students by shared UCAS university (and optionally course)."""
    from education_system.systems.sixth_form.domain.progression.university import ucas as u
    buckets: dict[tuple[str, str | None], list[str]] = {}
    for app in u.list_applications():
        for ch in u.list_choices(app.application_id):
            uni = (ch.university or "").strip()
            if not uni:
                continue
            key = (uni, (ch.course_code or None) if by_course else None)
            ids = buckets.setdefault(key, [])
            if app.student_id not in ids:
                ids.append(app.student_id)
    out = [UcasCluster(university=k[0], course_code=k[1], student_ids=v)
           for k, v in buckets.items() if len(v) >= min_size]
    out.sort(key=lambda c: (-len(c.student_ids), c.university))
    return out


# ── 16. Timetable clashes ─────────────────────────────────────────

def timetable_clashes() -> list[Clash]:
    """Detect room double-bookings and per-student timetable conflicts."""
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as tt,
    )
    slots = tt.list_slots()
    out: list[Clash] = []
    # Room clashes: same (day, period, room) used by >1 distinct group.
    by_room: dict[tuple[int, int, str], list[int]] = {}
    for s in slots:
        if not s.room:
            continue
        key = (s.day, s.period, s.room)
        ids = by_room.setdefault(key, [])
        if s.group_id not in ids:
            ids.append(s.group_id)
    for (day, period, room), gids in by_room.items():
        if len(gids) > 1:
            out.append(Clash("room", day, period, room, sorted(gids)))
    # Student clashes: a student whose groups meet at the same (day, period).
    try:
        from education_system.systems.sixth_form.domain.academics.class_groups import (
            class_groups as cg,
        )
        slots_by_group: dict[int, list] = {}
        for s in slots:
            slots_by_group.setdefault(s.group_id, []).append(s)
        student_groups: dict[str, list[int]] = {}
        for g in cg.list_groups():
            for sid in cg.list_members(g.group_id):
                student_groups.setdefault(sid, []).append(g.group_id)
        for sid, gids in student_groups.items():
            seen: dict[tuple[int, int], list[int]] = {}
            for gid in gids:
                for s in slots_by_group.get(gid, []):
                    seen.setdefault((s.day, s.period), [])
                    if gid not in seen[(s.day, s.period)]:
                        seen[(s.day, s.period)].append(gid)
            for (day, period), clash_gids in seen.items():
                if len(clash_gids) > 1:
                    out.append(Clash("student", day, period, sid,
                                     sorted(clash_gids)))
    except Exception:
        logger.debug("timetable_clashes: student pass unavailable")
    return out


# ── 17. Similar students ──────────────────────────────────────────

def similar_students(student_id: str, *,
                     limit: int = 10) -> list[SimilarStudent]:
    """Rank other students by overlap of subjects and tutor group/year."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students as m,
    )
    target = m.get_student(student_id)
    if target is None:
        raise ValidationError(f"No student {student_id!r}")
    t_subjects = {s.strip().lower() for s in (target.subjects or []) if s}
    groups = student_group_index()
    t_year, t_tg = groups.get(target.student_id, (None, None))
    ranked: list[SimilarStudent] = []
    for s in m.list_students():
        if s.student_id == target.student_id:
            continue
        shared: list[str] = []
        score = 0.0
        subj = {x.strip().lower() for x in (s.subjects or []) if x}
        common = t_subjects & subj
        if common:
            score += 2.0 * len(common)
            shared.append(f"subjects: {', '.join(sorted(common))}")
        year, tg = groups.get(s.student_id, (None, None))
        if t_tg and tg == t_tg:
            score += 1.5
            shared.append(f"tutor group {tg}")
        elif t_year is not None and year == t_year:
            score += 0.5
            shared.append(f"year {t_year}")
        if score > 0:
            ranked.append(SimilarStudent(
                student_id=s.student_id, full_name=s.full_name,
                score=round(score, 2), shared=shared))
    ranked.sort(key=lambda x: (-x.score, x.student_id))
    return ranked[:limit]


def student_group_index() -> dict[str, tuple[int | None, str | None]]:
    """Map every student id → (year_group, tutor_group_name) in one pass.

    Used by the GUI to group results by year/tutor without an O(N) query
    per row. Students with no tutor group are absent from the map."""
    out: dict[str, tuple[int | None, str | None]] = {}
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups as tg,
        )
        for g in tg.list_groups():
            for sid in tg.list_members(g.tutor_group_id):
                out[sid] = (g.year_group, g.name)
    except Exception:
        logger.debug("student_group_index unavailable")
    return out


def _search_students(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as m,
    )
    rows = m.list_students()
    groups = student_group_index()
    upns = m.upns_by_student()
    out: list[Hit] = []
    for s in rows:
        subjects = ", ".join(getattr(s, "subjects", []) or [])
        year, tutor_group = groups.get(s.student_id, (None, None))
        doc = _student_doc(s, subjects, year, tutor_group,
                           upns.get(s.student_id))
        if not _filter_match(parsed, opts, doc):
            continue
        where = "  ·  ".join(x for x in (
            f"Y{year}" if year else "", tutor_group or "", s.status) if x)
        _emit(out, doc, Hit(
            scope="students",
            entity_id=s.student_id,
            label=f"{s.student_id} — {s.full_name}",
            sublabel=_trim(f"{s.email or '—'}  ·  {subjects}  ·  {where}", 110),
        ))
    return out


def _student_doc(s: Any, subjects: str, year: int | None,
                 tutor_group: str | None, upn: str | None) -> dict[str, Any]:
    """The searchable form of a student record: every field the profile
    holds, so ``postcode:``, ``upn:``, ``status:``, ``dob:`` and the rest
    can be queried, and ``status`` drives the archived filter."""
    return {
        "id":              s.student_id,
        "name":            s.full_name,
        "preferred":       s.preferred_name or "",
        "email":           s.email or "",
        "personal_email":  s.personal_email or "",
        "phone":           s.phone or "",
        "subject":         subjects,
        "status":          s.status or "",
        "dob":             s.date_of_birth or "",
        "gender":          s.gender or "",
        "pronouns":        s.pronouns or "",
        "address":         s.address or "",
        "postcode":        s.postcode or "",
        "previous_school": s.previous_school or "",
        "ethnicity":       s.ethnicity_label or "",
        "nationality":     s.nationality or "",
        "language":        s.first_language or "",
        "start":           s.start_date or "",
        "left":            s.leaving_date or "",
        "leaving_reason":  s.leaving_reason or "",
        "upn":             upn or "",
        "uln":             s.uln or "",
        "uci":             s.uci or "",
        "candidate":       s.candidate_number or "",
        "year":            str(year) if year else "",
        "tutor_group":     tutor_group or "",
        "contact":         " ".join(x for x in (
            s.emergency_contact_name, s.emergency_contact_phone,
            s.emergency_contact_relation) if x),
        "_sid":            s.student_id,
        "_date":           s.start_date or "",
    }


def _search_staff(parsed: ParsedQuery,
                  opts: QueryOptions,
                  _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.staff import (
        staff as m,
    )
    rows = m.list_staff()
    out: list[Hit] = []
    for s in rows:
        full = f"{s.first_name} {s.last_name}".strip()
        doc = {
            "id":         s.staff_id,
            "name":       full,
            "email":      getattr(s, "email", "") or "",
            "role":       getattr(s, "role", "") or "",
            "department": getattr(s, "department", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="staff",
            entity_id=s.staff_id,
            label=f"{s.staff_id} — {full}",
            sublabel=_trim(
                f"{doc['role'] or '—'}  ·  {doc['email'] or '—'}", 100),
        ))
    return out


def _search_courses(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as m,
    )
    rows = m.list_courses()
    out: list[Hit] = []
    for c in rows:
        doc = {
            "code":        getattr(c, "course_code", "") or "",
            "title":       getattr(c, "title", "") or "",
            "level":       getattr(c, "level", "") or "",
            "description": getattr(c, "description", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="courses",
            entity_id=str(c.course_id),
            label=f"{doc['code']} — {doc['title']}",
            sublabel=_trim(doc["level"], 80),
        ))
    return out


def _search_subjects(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.subjects import (
        subjects as m,
    )
    rows = m.list_subjects()
    out: list[Hit] = []
    for s in rows:
        doc = {
            "name":     s.name,
            "subject":  s.name,
            "category": getattr(s, "qualification", "") or "",
            "code":     getattr(s, "exam_board", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="subjects",
            entity_id=str(s.subject_id),
            label=s.name,
            sublabel=_trim(
                f"{doc['category'] or '—'}  ·  {doc['code'] or '—'}", 80),
        ))
    return out


def _search_class_groups(parsed: ParsedQuery,
                         opts: QueryOptions,
                         _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as m,
    )
    rows = m.list_groups()
    out: list[Hit] = []
    for g in rows:
        bits = []
        for fld in ("code", "name", "label", "group_code"):
            v = getattr(g, fld, None)
            if v:
                bits.append(str(v))
        title = " · ".join(bits) or f"Group #{g.group_id}"
        doc = {
            "id":    str(g.group_id),
            "code":  _first_attr(g, "code", "group_code"),
            "name":  _first_attr(g, "name", "label"),
            "title": title,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="class_groups",
            entity_id=str(g.group_id),
            label=title,
            sublabel=_trim(f"course_id={getattr(g, 'course_id', '—')}", 60),
        ))
    return out


def _search_behaviour(parsed: ParsedQuery,
                      opts: QueryOptions,
                      _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour as m,
    )
    rows = m.list_entries()
    out: list[Hit] = []
    for e in rows:
        doc = {
            "id":          str(e.entry_id),
            "name":        e.student_id or "",
            "type":        e.entry_type or "",
            "category":    e.category or "",
            "description": e.description or "",
            "location":    e.location or "",
            "action":      e.action_taken or "",
            "_date":       getattr(e, "entry_date", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="behaviour",
            entity_id=str(e.entry_id),
            label=f"#{e.entry_id} {e.student_id} · {e.entry_type}"
                  f" · {e.category}",
            sublabel=_trim(
                f"{e.entry_date}  ·  {e.description or ''}", 110),
        ))
    return out


def _search_absence_requests(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.absence_requests import (
        absence_requests as m,
    )
    rows = m.list_requests()
    out: list[Hit] = []
    for r in rows:
        doc = {
            "id":          str(r.request_id),
            "name":        r.student_id or "",
            "reason":      r.reason or "",
            "description": r.description or "",
            "status":      r.status or "",
            "author":      r.submitted_by or "",
            "notes":       r.notes or "",
            "_date":       getattr(r, "start_date", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="absence_requests",
            entity_id=str(r.request_id),
            label=f"#{r.request_id} {r.student_id} · {r.reason}"
                  f" · {r.status}",
            sublabel=_trim(
                f"{r.start_date} → {r.end_date}  ·  "
                f"{r.description or ''}", 110),
        ))
    return out


def _search_attendance_concerns(parsed: ParsedQuery,
                                opts: QueryOptions,
                                _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.attendance_concerns import (
        attendance_concerns as m,
    )
    rows = m.list_concerns()
    out: list[Hit] = []
    for c in rows:
        att = getattr(c, "attendance_pct", None)
        doc = {
            "id":          str(c.concern_id),
            "name":        c.student_id or "",
            "level":       c.level or "",
            "status":      c.status or "",
            "reason":      c.reason or "",
            "description": c.description or "",
            "action":      c.action_taken or "",
            "notes":       c.notes or "",
            "author":      c.raised_by or "",
            "_date":       getattr(c, "raised_date", "") or "",
            "_attendance": att,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="attendance_concerns",
            entity_id=str(c.concern_id),
            label=f"#{c.concern_id} {c.student_id} · "
                  f"{c.level} · {c.status}",
            sublabel=_trim(
                f"{c.raised_date}  ·  {c.reason}  ·  "
                f"{c.description or ''}", 110),
        ))
    return out


def _search_accommodations(parsed: ParsedQuery,
                           opts: QueryOptions,
                           _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.accessibility import (
        accessibility as m,
    )
    rows = m.list_accommodations()
    out: list[Hit] = []
    for a in rows:
        doc = {
            "id":          str(a.accommodation_id),
            "_sid":        a.student_id or "",
            "name":        a.name or "",
            "description": a.description or "",
            "category":    a.category or "",
            "status":      a.status or "",
            "author":      a.approved_by or "",
            "notes":       a.notes or "",
            "_date":       getattr(a, "start_date", "")
                          or getattr(a, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="accommodations",
            entity_id=str(a.accommodation_id),
            label=f"#{a.accommodation_id} {a.student_id} · {a.name}",
            sublabel=_trim(
                f"{a.category}  ·  {a.status}  ·  "
                f"{a.description or ''}", 110),
        ))
    return out


def _search_safeguarding(parsed: ParsedQuery,
                         opts: QueryOptions,
                         _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.safeguarding import (
        safeguarding as m,
    )
    rows = m.list_concerns()
    out: list[Hit] = []
    for c in rows:
        sid = getattr(c, "student_id", "") or ""
        doc = {
            "id":          str(getattr(c, "concern_id", "")),
            "name":        sid,
            "summary":     getattr(c, "summary", "") or "",
            "description": getattr(c, "description", "") or "",
            "category":    getattr(c, "category", "") or "",
            "status":      getattr(c, "status", "") or "",
            "author":      getattr(c, "raised_by", "") or "",
            "notes":       getattr(c, "notes", "") or "",
            "_date":       getattr(c, "raised_date", "")
                          or getattr(c, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        label_bits = [
            f"#{getattr(c, 'concern_id', '?')}",
            sid or "—",
            doc["category"], doc["status"],
        ]
        _emit(out, doc, Hit(
            scope="safeguarding",
            entity_id=str(getattr(c, "concern_id", "")),
            label=" · ".join(b for b in label_bits if b),
            sublabel=_trim(doc["summary"] or doc["description"], 110),
        ))
    return out


def _search_notices(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domains.communications.domain.notices import (
        notices as m,
    )
    rows = m.list_notices()
    out: list[Hit] = []
    for n in rows:
        doc = {
            "id":     str(n.notice_id),
            "title":  getattr(n, "title", "") or "",
            "body":   getattr(n, "body", "") or "",
            "author": getattr(n, "author", "")
                      or getattr(n, "posted_by", "") or "",
            "_date":  getattr(n, "posted_at", "")
                     or getattr(n, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="notices",
            entity_id=str(n.notice_id),
            label=f"#{n.notice_id} {doc['title']}",
            sublabel=_trim(doc["body"], 110),
        ))
    return out


def _search_messages(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domains.communications.domain.messages import (
        messages as m,
    )
    rows = m.list_messages()
    out: list[Hit] = []
    for msg in rows:
        when = (msg.sent_at or msg.received_at or msg.created_at or "")
        doc = {
            "id":        str(msg.message_id),
            "direction": msg.direction or "",
            "title":     msg.subject or "",
            "body":      msg.body or "",
            "email":     msg.to_address or "",
            "name":      msg.to_name or "",
            "_date":     when,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="messages",
            entity_id=str(msg.message_id),
            label=f"#{msg.message_id} {msg.direction or '—'} · "
                  f"{msg.subject}",
            sublabel=_trim(
                f"{when}  ·  to {msg.to_address or msg.to_name or '—'}"
                f"  ·  {msg.body or ''}", 110),
        ))
    return out


def _search_predicted_grades(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.assessment.predicted_grades import (
        predicted_grades as m,
    )
    rows = m.list_predictions()
    # Best-effort map of (student, subject) → target grades so relative
    # comparisons like ``predicted<target`` (item 14) have something to
    # compare against. Missing module ⇒ empty map (relative cmp ⇒ no match).
    targets: dict[tuple[str, str], Any] = {}
    try:
        from education_system.systems.sixth_form.domain.assessment.target_setting import (
            target_setting as _ts,
        )
        for t in _ts.list_targets():
            targets[(t.student_id, t.subject_name)] = t
    except Exception:
        logger.debug("target_setting unavailable for predicted_grades adapter")
    out: list[Hit] = []
    for p in rows:
        tgt = targets.get((p.student_id or "", p.subject or ""))
        doc = {
            "id":          str(p.prediction_id),
            "name":        p.student_id or "",
            "subject":     p.subject or "",
            "category":    p.confidence or "",
            "notes":       p.notes or "",
            "author":      p.predicted_by or "",
            "_date":       getattr(p, "predicted_at", "") or "",
            "_grade":      p.grade or "",
            "_target":      (getattr(tgt, "mte_grade", "") or "") if tgt else "",
            "_aspirational": (getattr(tgt, "aspirational_grade", "") or "")
                             if tgt else "",
            "_current":     (getattr(tgt, "current_grade", "") or "") if tgt else "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="predicted_grades",
            entity_id=str(p.prediction_id),
            label=f"#{p.prediction_id} {p.student_id} · {p.subject} "
                  f"· {p.grade}",
            sublabel=_trim(
                f"{p.confidence or '—'}  ·  {p.notes or ''}", 110),
        ))
    return out


def _search_homework(parsed: ParsedQuery,
                     opts: QueryOptions,
                     _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.homework import (
        homework as m,
    )
    rows = m.list_assignments()
    out: list[Hit] = []
    for a in rows:
        doc = {
            "id":          str(a.assignment_id),
            "title":       a.title or "",
            "type":        a.type or "",
            "description": a.description or "",
            "notes":       a.notes or "",
            "code":        f"group:{a.group_id}",
            "_date":       a.due_date or a.set_date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="homework",
            entity_id=str(a.assignment_id),
            label=f"#{a.assignment_id} {a.title} · {a.type}",
            sublabel=_trim(
                f"group {a.group_id}  ·  set {a.set_date}  ·  "
                f"due {a.due_date}", 110),
        ))
    return out


def _search_timetable(parsed: ParsedQuery,
                      opts: QueryOptions,
                      _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.timetable import (
        timetable as m,
    )
    rows = m.list_slots()
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    out: list[Hit] = []
    for s in rows:
        day_lbl = days[s.day - 1] if 1 <= s.day <= 7 else f"day{s.day}"
        doc = {
            "id":       str(s.slot_id),
            "code":     f"group:{s.group_id}",
            "location": s.room or "",
            "notes":    s.notes or "",
            "type":     day_lbl,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="timetable",
            entity_id=str(s.slot_id),
            label=f"#{s.slot_id} {day_lbl} P{s.period} · group {s.group_id}"
                  f" · {s.room or '—'}",
            sublabel=_trim(
                f"{s.start_time or '—'}–{s.end_time or '—'}  ·  "
                f"{s.notes or ''}", 110),
        ))
    return out


def _search_parents_evenings(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domains.communications.domain.parents_evenings import (
        parents_evenings as m,
    )
    rows = m.list_events()
    out: list[Hit] = []
    for e in rows:
        doc = {
            "id":       str(e.event_id),
            "name":     e.name or "",
            "title":    e.name or "",
            "level":    e.year_group or "",
            "location": e.location or "",
            "status":   e.status or "",
            "notes":    e.notes or "",
            "_date":    e.event_date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="parents_evenings",
            entity_id=str(e.event_id),
            label=f"#{e.event_id} {e.name} · {e.event_date} · "
                  f"{e.year_group}",
            sublabel=_trim(
                f"{e.start_time}–{e.end_time}  ·  "
                f"{e.location or '—'}  ·  {e.status}", 110),
        ))
    return out


def _search_progress_reviews(parsed: ParsedQuery,
                             opts: QueryOptions,
                             _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.operations.reporting.progress import (
        progress as m,
    )
    rows = m.list_reviews()
    out: list[Hit] = []
    for r in rows:
        doc = {
            "id":          str(r.review_id),
            "name":        r.student_id or "",
            "type":        r.period or "",
            "level":       r.risk_level or "",
            "status":      r.status or "",
            "description": (r.academic_summary or "")
                           + " " + (r.behaviour_summary or ""),
            "notes":       (r.next_steps or "")
                           + " " + (r.notes or ""),
            "author":      r.reviewer_staff_id or "",
            "_date":       r.review_date or "",
            "_attendance": r.attendance_pct,
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="progress_reviews",
            entity_id=str(r.review_id),
            label=f"#{r.review_id} {r.student_id} · {r.period} · "
                  f"{r.status}",
            sublabel=_trim(
                f"{r.review_date}  ·  risk {r.risk_level}  ·  "
                f"{(r.academic_summary or r.behaviour_summary or '')}", 110),
        ))
    return out


def _search_surveys(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.pastoral.surveys import (
        surveys as m,
    )
    rows = m.list_surveys()
    out: list[Hit] = []
    for s in rows:
        prompts = " ".join(q.prompt for q in (s.questions or [])
                           if getattr(q, "prompt", None))
        doc = {
            "id":          str(s.survey_id),
            "name":        s.name or "",
            "title":       s.name or "",
            "description": s.description or "",
            "level":       s.audience or "",
            "status":      s.status or "",
            "notes":       s.notes or "",
            "author":      s.created_by or "",
            "body":        prompts,
            "_date":       s.open_on or s.created_on or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="surveys",
            entity_id=str(s.survey_id),
            label=f"#{s.survey_id} {s.name} · {s.audience} · {s.status}",
            sublabel=_trim(
                f"{len(s.questions or [])} questions  ·  "
                f"{s.description or ''}", 110),
        ))
    return out


def _search_ucas(parsed: ParsedQuery,
                 opts: QueryOptions,
                 _filters: dict) -> list[Hit]:
    out: list[Hit] = []
    try:
        from education_system.systems.sixth_form.domain.progression.university import ucas as u
        for a in u.list_applications():
            choices_text = ""
            try:
                ch = u.list_choices(a.application_id)
                choices_text = " ".join(
                    f"{c.university} {c.course_code or ''} {c.course_name or ''}"
                    for c in ch)
            except Exception:
                pass
            doc = {
                "id":          f"app:{a.application_id}",
                "name":        a.student_id or "",
                "code":        a.ucas_id or "",
                "status":      a.status or "",
                "description": choices_text,
                "body":        a.personal_statement or "",
                "notes":       a.notes or "",
                "_date":       a.submitted_at or a.created_at or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            _emit(out, doc, Hit(
                scope="ucas",
                entity_id=f"app:{a.application_id}",
                label=f"App #{a.application_id} {a.student_id} · "
                      f"cycle {a.cycle_year} · {a.status}",
                sublabel=_trim(choices_text or a.notes or "", 110),
            ))
    except Exception:
        logger.exception("UCAS adapter (applications) failed")
    try:
        from education_system.systems.sixth_form.domain.progression.university import references as r
        for ref in r.list_references():
            doc = {
                "id":          f"ref:{ref.reference_id}",
                "name":        ref.student_id or "",
                "author":      ref.referee or "",
                "role":        ref.referee_role or "",
                "title":       ref.title or "",
                "status":      ref.status or "",
                "body":        ref.body or "",
                "notes":       ref.notes or "",
                "_date":       ref.submitted_at or ref.requested_at
                                or ref.created_at or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            _emit(out, doc, Hit(
                scope="ucas",
                entity_id=f"ref:{ref.reference_id}",
                label=f"Ref #{ref.reference_id} {ref.student_id} · "
                      f"{ref.referee} · {ref.status}",
                sublabel=_trim(
                    f"{ref.title or '—'}  ·  {ref.word_count}w  ·  "
                    f"{ref.body or ''}", 110),
            ))
    except Exception:
        logger.exception("UCAS adapter (references) failed")
    return out


def _search_alumni(parsed: ParsedQuery,
                   opts: QueryOptions,
                   _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.learners.alumni import records as alumni_records
    rows = alumni_records.list_alumni()
    out: list[Hit] = []
    for a in rows:
        full = a.full_name
        doc = {
            "id":          str(a.alumni_id),
            "name":        full,
            "email":       a.email or "",
            "phone":       a.phone or "",
            "role":        a.current_role or "",
            "department":  a.current_employer or "",
            "category":    a.current_sector or "",
            "location":    a.current_location
                           or a.country or a.region or "",
            "level":       a.leaving_year or "",
            "status":      a.status or "",
            "description": a.bio or "",
            "notes":       a.notes or "",
            "_date":       a.leaving_date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        bits = [full]
        if a.leaving_year:
            bits.append(f"leaver {a.leaving_year}")
        if a.current_role:
            bits.append(a.current_role)
        if a.current_employer:
            bits.append(f"@ {a.current_employer}")
        _emit(out, doc, Hit(
            scope="alumni",
            entity_id=str(a.alumni_id),
            label=f"#{a.alumni_id} {full}",
            sublabel=_trim(" · ".join(bits[1:]) or (a.bio or ""), 110),
        ))
    return out


def _search_finance(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    out: list[Hit] = []
    try:
        from education_system.systems.sixth_form.domains.finance.domain.fees import (
            fees as f,
        )
        for it in f.list_items():
            doc = {
                "id":          f"fee:{it.fee_id}",
                "name":        it.student_id or "",
                "title":       it.description or "",
                "category":    it.category or "",
                "status":      it.stored_status or "",
                "level":       it.academic_year or "",
                "notes":       it.notes or "",
                "_date":       it.issued_date or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            _emit(out, doc, Hit(
                scope="finance",
                entity_id=f"fee:{it.fee_id}",
                label=f"Fee #{it.fee_id} {it.student_id} · "
                      f"{it.category} · £{it.amount:.2f}",
                sublabel=_trim(
                    f"{it.description}  ·  due {it.due_date or '—'}  ·  "
                    f"{it.stored_status or '—'}", 110),
            ))
    except Exception:
        logger.exception("Finance adapter (fees) failed")
    try:
        from education_system.systems.sixth_form.domains.finance.domain.bursaries import (
            bursaries as b,
        )
        for app in b.list_applications():
            doc = {
                "id":          f"burs:{app.application_id}",
                "name":        app.student_id or "",
                "category":    app.bursary_type or "",
                "status":      app.status or "",
                "reason":      app.reason or "",
                "level":       app.academic_year or "",
                "notes":       (app.decision_note or "")
                               + " " + (app.notes or ""),
                "author":      app.assessed_by or "",
                "_date":       app.application_date or "",
            }
            if not _filter_match(parsed, opts, doc):
                continue
            awarded = (f"£{app.amount_awarded:.2f}"
                        if app.amount_awarded is not None else "—")
            _emit(out, doc, Hit(
                scope="finance",
                entity_id=f"burs:{app.application_id}",
                label=f"Burs #{app.application_id} {app.student_id} · "
                      f"{app.bursary_type} · {app.status}",
                sublabel=_trim(
                    f"awarded {awarded}  ·  {app.reason or ''}", 110),
            ))
    except Exception:
        logger.exception("Finance adapter (bursaries) failed")
    return out


def _search_library(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.academics.library import (
        library as m,
    )
    rows = m.list_books()
    out: list[Hit] = []
    for b in rows:
        doc = {
            "id":          str(b.book_id),
            "title":       b.title or "",
            "author":      b.author or "",
            "code":        b.isbn or "",
            "subject":     b.subject_area or "",
            "category":    b.item_type or "",
            "status":      b.status or "",
            "location":    b.location or "",
            "description": b.description or "",
            "notes":       (b.keywords or "")
                           + " " + (b.notes or ""),
            "_date":       getattr(b, "created_at", "") or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="library",
            entity_id=str(b.book_id),
            label=f"#{b.book_id} {b.title}"
                  + (f" — {b.author}" if b.author else ""),
            sublabel=_trim(
                f"{b.item_type}  ·  {b.copies_available}/{b.copies_total}"
                f"  ·  {b.location or '—'}", 110),
        ))
    return out


def _search_documents(parsed: ParsedQuery,
                      opts: QueryOptions,
                      _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domains.communications.domain.document_hub import (
        document_hub as m,
    )
    rows = m.list_documents()
    out: list[Hit] = []
    for d in rows:
        doc = {
            "id":          str(d.document_id),
            "title":       d.title or "",
            "description": d.description or "",
            "category":    d.category or "",
            "level":       d.audience or "",
            "status":      d.status or "",
            "code":        d.version or "",
            "author":      d.author or "",
            "department":  d.owner_department or "",
            "notes":       (d.keywords or "")
                           + " " + (d.notes or ""),
            "_date":       d.issued_on or d.created_on or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="documents",
            entity_id=str(d.document_id),
            label=f"#{d.document_id} {d.title} · v{d.version}",
            sublabel=_trim(
                f"{d.category}  ·  {d.audience}  ·  {d.status}  ·  "
                f"{d.description or ''}", 110),
        ))
    return out


def _search_audit_logs(parsed: ParsedQuery,
                       opts: QueryOptions,
                       _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.infrastructure import log_store as m
    rows = m.list_logs(limit=500)
    out: list[Hit] = []
    for r in rows:
        doc = {
            "id":          str(r.log_id),
            "level":       r.level or "",
            "name":        r.student_id or "",
            "code":        r.logger_name or "",
            "title":       (r.module or "") + " · " + (r.func_name or ""),
            "body":        r.message or "",
            "description": r.exc_text or "",
            "notes":       r.extra_json or "",
            "_date":       r.ts or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="audit_logs",
            entity_id=str(r.log_id),
            label=f"[{r.level}] #{r.log_id} {r.logger_name}",
            sublabel=_trim(
                f"{r.ts}  ·  {r.message}", 130),
        ))
    return out


def _search_attendance(parsed: ParsedQuery,
                       opts: QueryOptions,
                       _filters: dict) -> list[Hit]:
    """Register marks for the last year (older marks are in reports)."""
    import datetime as _dt
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance as m,
    )
    since = ((opts.today or _dt.date.today())
             - _dt.timedelta(days=365)).isoformat()
    out: list[Hit] = []
    for r in m.list_records(date_from=since):
        doc = {
            "id":          str(r.record_id),
            "_sid":        r.student_id,
            "name":        r.student_id,
            "status":      r.status or "",
            "code":        r.code or "",
            "type":        r.session or "",
            "location":    r.offsite_location or "",
            "author":      r.authorised_by or "",
            "notes":       " ".join(x for x in (
                r.notes, r.authorisation_note) if x),
            "_date":       r.date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        late = f" ({r.minutes_late} min)" if r.minutes_late else ""
        _emit(out, doc, Hit(
            scope="attendance",
            entity_id=str(r.record_id),
            label=f"{r.student_id} · {r.date} {r.session or ''} · "
                  f"{r.status}{late}",
            sublabel=_trim(f"code {r.code or '—'}  ·  slot {r.slot_id}  ·  "
                           f"{r.notes or ''}", 110),
        ))
    return out


def _search_exam_results(parsed: ParsedQuery,
                         opts: QueryOptions,
                         _filters: dict) -> list[Hit]:
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as m,
    )
    out: list[Hit] = []
    for row in m.list_results():
        res = row.result
        doc = {
            "id":          str(res.result_id),
            "_sid":        row.student_id,
            "name":        row.student_id,
            "title":       row.student_name or "",
            "subject":     row.subject or "",
            "code":        row.paper_code or "",
            "category":    row.exam_board or "",
            "type":        f"{row.season} {row.year}",
            "status":      "released" if res.released else "embargoed",
            "notes":       res.notes or "",
            "_grade":      res.grade or "",
            "_date":       res.released_at or res.recorded_at or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="exam_results",
            entity_id=str(res.result_id),
            label=f"{row.student_id} {row.student_name} · {row.subject} "
                  f"{res.grade}",
            sublabel=_trim(f"{row.exam_board} {row.paper_code}  ·  "
                           f"{row.season} {row.year}  ·  "
                           f"{'released' if res.released else 'embargoed'}",
                           110),
        ))
    return out


def _search_enrolments(parsed: ParsedQuery,
                       opts: QueryOptions,
                       _filters: dict) -> list[Hit]:
    """Learning aims — what each learner is enrolled on, every status."""
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims as m,
    )
    out: list[Hit] = []
    for a in m.list_all_aims(status=None):
        doc = {
            "id":          str(a.aim_id),
            "_sid":        a.student_id,
            "name":        a.student_id,
            "subject":     a.subject or "",
            "type":        a.qualification_type or "",
            "code":        a.aim_code or "",
            "category":    a.awarding_body or "",
            "status":      a.status or "",
            "reason":      a.withdrawal_reason or "",
            "notes":       a.notes or "",
            "_date":       a.start_date or "",
        }
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="enrolments",
            entity_id=str(a.aim_id),
            label=f"{a.student_id} · {a.label}",
            sublabel=_trim(f"{a.academic_year or '—'}  ·  {a.status}  ·  "
                           f"{a.aim_code or ''}", 110),
        ))
    return out


def _search_medical(parsed: ParsedQuery,
                    opts: QueryOptions,
                    _filters: dict) -> list[Hit]:
    """Medical conditions, medications and allergies. Entity ids carry the
    record kind (``condition:12``) because the three tables share ids."""
    from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
        medical_records as m,
    )
    out: list[Hit] = []
    rows: list[tuple[str, Any, dict[str, Any], str, str]] = []
    for c in m.list_conditions():
        rows.append(("condition", c.condition_id, {
            "title": c.name, "level": c.severity,
            "status": "active" if c.active else "resolved",
            "code": c.care_plan_ref or "", "notes": c.notes or "",
            "_date": c.diagnosed_date or c.created_at or "",
        }, c.student_id, f"condition {c.name} ({c.severity})"))
    for md in m.list_medications():
        rows.append(("medication", md.medication_id, {
            "title": md.name, "type": md.route or "",
            "level": "emergency" if md.is_emergency else "",
            "description": " ".join(x for x in (md.dose, md.frequency) if x),
            "author": md.prescribed_by or "", "notes": md.notes or "",
            "_date": md.start_date or md.created_at or "",
        }, md.student_id, f"medication {md.name}"))
    for al in m.list_allergies():
        rows.append(("allergy", al.allergy_id, {
            "title": al.allergen, "level": al.severity,
            "description": al.reaction or "",
            "type": "epipen" if al.has_epipen else "",
            "notes": al.notes or "", "_date": al.created_at or "",
        }, al.student_id, f"allergy {al.allergen} ({al.severity})"))
    for kind, rid, fields, sid, label in rows:
        doc = {"id": f"{kind}:{rid}", "_sid": sid, "name": sid,
               "category": kind, **fields}
        if not _filter_match(parsed, opts, doc):
            continue
        _emit(out, doc, Hit(
            scope="medical",
            entity_id=f"{kind}:{rid}",
            label=f"{sid} · {label}",
            sublabel=_trim(str(fields.get("notes") or ""), 110),
        ))
    return out


_ADAPTERS: dict[str, Callable[
    [ParsedQuery, QueryOptions, dict], list[Hit]]] = {
    "students":             _search_students,
    "staff":                _search_staff,
    "courses":              _search_courses,
    "subjects":             _search_subjects,
    "class_groups":         _search_class_groups,
    "behaviour":            _search_behaviour,
    "absence_requests":     _search_absence_requests,
    "attendance_concerns":  _search_attendance_concerns,
    "accommodations":       _search_accommodations,
    "safeguarding":         _search_safeguarding,
    "notices":              _search_notices,
    "messages":             _search_messages,
    "predicted_grades":     _search_predicted_grades,
    "homework":             _search_homework,
    "timetable":            _search_timetable,
    "parents_evenings":     _search_parents_evenings,
    "progress_reviews":     _search_progress_reviews,
    "surveys":              _search_surveys,
    "ucas":                 _search_ucas,
    "alumni":               _search_alumni,
    "finance":              _search_finance,
    "library":              _search_library,
    "documents":            _search_documents,
    "audit_logs":           _search_audit_logs,
    "attendance":           _search_attendance,
    "exam_results":         _search_exam_results,
    "enrolments":           _search_enrolments,
    "medical":              _search_medical,
}
