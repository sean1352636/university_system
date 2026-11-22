"""Year 6 Transition: Year 7 form allocation for the incoming cohort.

Each child into a Year 7 form (the Form Groups module's open Year 7 forms,
by name). :func:`suggest` balances form size, girls / boys, KS2 band, SEN
and feeder school while honouring every keep-apart and one friendship per
child (groups of at most :data:`year6_transition.MAX_CLUSTER`); manual moves
are kept; :func:`warnings` lists broken keep-aparts, friendless children,
full forms and children not placed; :func:`publish` locks the allocation
and puts each child who already has a pupil record here in their form
through the pupils domain (:func:`unpublish` unlocks it with a reason).

Cohort, permissions and the audit trail are in
:mod:`modules.progression.domain.year6_transition`.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.database import connection as database
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
from education_system.systems.secondary.modules.progression.domain.year6_transition import (
    CohortRow,
    ENTRY_YEAR,
    KS2_BANDS,
    MAX_CLUSTER,
    Suggestion,
    ValidationError,
    _audit,
    _norm,
    _published,
    _raw_rows,
    _require_editor,
    _require_staff,
    _set_form,
    _text,
    _year,
    can_see_needs,
    cohort,
    get,
    ks2_band,
)


def forms() -> list[dict[str, Any]]:
    """The Year 7 forms (from Form Groups): ``{name, capacity, tutor}``."""
    return [{"name": f.name, "capacity": f.capacity, "tutor": f.tutor_name}
            for f in FG.list_forms(ENTRY_YEAR)]


def _require_unlocked(conn, year: str) -> None:
    if _published(conn, year):
        raise ValidationError(["The form allocation is published - unlock it first"])


def form_summary(intake_year: str, *, actor: Principal) -> list[dict[str, Any]]:
    """Per form: size, capacity, girls / boys, KS2 bands, SEN (if permitted), feeders."""
    rows = cohort(intake_year, actor=actor)
    needs = can_see_needs(actor)
    out = []
    for f in [*forms(), {"name": None, "capacity": None, "tutor": None}]:
        mine = [r for r in rows if (r.form_name or None) == f["name"]]
        if f["name"] is None and not mine:
            continue
        out.append({"name": f["name"] or "(not allocated)", "capacity": f["capacity"],
                    "tutor": f["tutor"], "size": len(mine),
                    "female": sum(1 for r in mine if r.gender == "Female"),
                    "male": sum(1 for r in mine if r.gender == "Male"),
                    "other": sum(1 for r in mine if r.gender not in ("Female", "Male")),
                    "bands": {b: sum(1 for r in mine if r.ks2_band == b) for b in KS2_BANDS},
                    "sen": sum(1 for r in mine if r.sen_status in ("K", "E")) if needs else None,
                    "feeders": len({_norm(r.feeder_school) for r in mine}),
                    "enhanced": sum(1 for r in mine if r.enhanced)})
    return out


def _pairs(conn, year: str, kind: str, active: set[int]) -> list[tuple[int, int]]:
    return [(r["cohort_id"], r["other_cohort_id"]) for r in conn.execute(
        "SELECT r.cohort_id, r.other_cohort_id FROM y6_relationships r JOIN y6_cohort c ON "
        "c.cohort_id = r.cohort_id WHERE c.intake_year = ? AND r.kind = ? AND "
        "r.other_cohort_id IS NOT NULL ORDER BY r.rel_id", (year, kind))
        if r["cohort_id"] in active and r["other_cohort_id"] in active]


def suggest(intake_year: str, *, actor: Principal, keep_manual: bool = True) -> Suggestion:
    """A form for every active child. Writes nothing.

    Every keep-apart is honoured; each child is kept with (at least) one
    requested friend where that doesn't break a keep-apart or make a group
    bigger than :data:`MAX_CLUSTER`; then each group goes to the form that
    keeps sizes, girls / boys, KS2 bands, SEN and feeder schools most even,
    within capacity. Manual moves are kept when *keep_manual*."""
    _require_staff(actor, "suggest")
    year = _year(intake_year)
    fl = forms()
    if not fl:
        raise ValidationError(["Set up the Year 7 form groups first (Form Groups)"])
    names = [f["name"] for f in fl]
    cap = {f["name"]: f["capacity"] for f in fl}
    with database.connect() as conn:
        raw = {r["cohort_id"]: r for r in _raw_rows(conn, year, include_inactive=False)}
        active = set(raw)
        apart = {frozenset(p) for p in _pairs(conn, year, "keep_apart", active)}
        friend_pairs = _pairs(conn, year, "friend", active)
    friends: dict[int, list[int]] = {}
    for a, b in friend_pairs:
        friends.setdefault(a, []).append(b)
    fixed = {cid: r["form_name"] for cid, r in raw.items()
             if keep_manual and r.get("form_how") == "manual" and r.get("form_name") in names}
    parent = {cid: cid for cid in raw}

    def root(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def members(r: int) -> list[int]:
        return [c for c in raw if root(c) == r]

    notes: list[str] = []
    for cid in sorted(raw, key=lambda c: (raw[c]["last_name"], raw[c]["first_name"])):
        mine = members(root(cid))
        if any(f in mine for f in friends.get(cid, [])):
            continue
        for f in friends.get(cid, []):
            theirs = members(root(f))
            group = mine + theirs
            if len(group) > MAX_CLUSTER:
                continue
            if any(frozenset((a, b)) in apart for a in mine for b in theirs):
                continue
            if len({fixed[c] for c in group if c in fixed}) > 1:
                continue
            parent[root(f)] = root(cid)
            break
    groups: dict[int, list[int]] = {}
    for cid in raw:
        groups.setdefault(root(cid), []).append(cid)

    size = {n: 0 for n in names}
    gender: dict[str, dict[str, int]] = {n: {} for n in names}
    band: dict[str, dict[str, int]] = {n: {} for n in names}
    sen = {n: 0 for n in names}
    feeder: dict[str, dict[str, int]] = {n: {} for n in names}
    where: dict[int, str] = {}

    def put(cid: int, form: str) -> None:
        r = raw[cid]
        where[cid] = form
        size[form] += 1
        g = r.get("gender") or "?"
        gender[form][g] = gender[form].get(g, 0) + 1
        b = ks2_band(r.get("ks2_reading"), r.get("ks2_maths"))
        band[form][b] = band[form].get(b, 0) + 1
        sen[form] += int(r.get("sen_status") in ("K", "E"))
        fs = _norm(r.get("feeder_school"))
        feeder[form][fs] = feeder[form].get(fs, 0) + 1

    def cost(group: list[int], form: str) -> float:
        c = 6.0 * (size[form] + len(group))
        for cid in group:
            r = raw[cid]
            c += 2.0 * gender[form].get(r.get("gender") or "?", 0)
            c += 2.0 * band[form].get(ks2_band(r.get("ks2_reading"), r.get("ks2_maths")), 0)
            if r.get("sen_status") in ("K", "E"):
                c += 4.0 * sen[form]
            c += 1.5 * feeder[form].get(_norm(r.get("feeder_school")), 0)
        return c

    def fits(group: list[int], form: str) -> bool:
        if cap[form] is not None and size[form] + len(group) > cap[form]:
            return False
        return not any(frozenset((cid, other)) in apart for cid in group
                       for other, f in where.items() if f == form)

    unplaced: list[int] = []
    pinned = [g for g in groups.values() if any(c in fixed for c in g)]
    rest = [g for g in groups.values() if not any(c in fixed for c in g)]
    for g in pinned:
        form = next(fixed[c] for c in g if c in fixed)
        for cid in g:
            put(cid, form)
    hard = {c for p in apart for c in p}
    rest.sort(key=lambda g: (-len(g), -sum(c in hard for c in g),
                             -sum(raw[c].get("sen_status") in ("K", "E") for c in g),
                             min(raw[c]["last_name"] for c in g)))
    for g in rest:
        options = [n for n in names if fits(g, n)]
        if not options and len(g) > 1:
            notes.append(f"A friendship group of {len(g)} couldn't stay together")
            for cid in g:
                one = [n for n in names if fits([cid], n)]
                if one:
                    put(cid, min(one, key=lambda n: (cost([cid], n), n)))
                else:
                    unplaced.append(cid)
            continue
        if not options:
            unplaced.extend(g)
            continue
        best = min(options, key=lambda n: (cost(g, n), n))
        for cid in g:
            put(cid, best)
    if unplaced:
        notes.append(f"{len(unplaced)} child(ren) couldn't be placed (capacity or keep-apart)")
    activity_log.record("year6.suggest", principal=actor, intake=year, placed=len(where),
                        unplaced=len(unplaced) or None)
    return Suggestion(where, unplaced, notes)


def apply_plan(intake_year: str, plan: dict[int, str], *, actor: Principal) -> int:
    """Save a suggestion (replaces earlier auto placements; manual ones stay
    unless the plan moves them)."""
    _require_editor(actor, "allocate")
    year = _year(intake_year)
    names = {f["name"] for f in forms()}
    bad = sorted({f for f in plan.values() if f not in names})
    if bad:
        raise ValidationError([f"No Year 7 form {', '.join(bad)}"])
    with database.connect() as conn:
        _require_unlocked(conn, year)
        ids = {r["cohort_id"] for r in conn.execute("SELECT cohort_id FROM y6_cohort WHERE "
                                                    "intake_year = ?", (year,))}
        conn.execute("DELETE FROM y6_allocation WHERE how = 'auto' AND cohort_id IN (SELECT "
                     "cohort_id FROM y6_cohort WHERE intake_year = ?)", (year,))
        n = 0
        for cid, form in plan.items():
            if int(cid) not in ids:
                continue
            cur = conn.execute("SELECT form_name, how FROM y6_allocation WHERE cohort_id = ?",
                               (int(cid),)).fetchone()
            if cur and cur["form_name"] == form:
                continue
            conn.execute("INSERT OR REPLACE INTO y6_allocation (cohort_id, form_name, how, "
                         "allocated_by) VALUES (?, ?, 'auto', ?)", (int(cid), form,
                                                                    actor.username))
            n += 1
        _audit(conn, "allocate_auto", actor, year, placed=n)
    activity_log.record("year6.allocate_auto", principal=actor, intake=year, placed=n)
    return n


def auto_allocate(intake_year: str, *, actor: Principal, keep_manual: bool = True
                  ) -> Suggestion:
    _require_editor(actor, "allocate")
    s = suggest(intake_year, actor=actor, keep_manual=keep_manual)
    apply_plan(intake_year, s.plan, actor=actor)
    return s


def move(cohort_id: int, form_name: str | None, *, actor: Principal) -> CohortRow:
    """Put a child in a form by hand (None / "" takes them out)."""
    _require_editor(actor, "allocate", cohort_id)
    row = get(cohort_id, actor=actor)
    form = (form_name or "").strip().upper() or None
    if form and form not in {f["name"] for f in forms()}:
        raise ValidationError([f"No Year 7 form {form}"])
    with database.connect() as conn:
        _require_unlocked(conn, row.intake_year)
        if form is None:
            conn.execute("DELETE FROM y6_allocation WHERE cohort_id = ?", (row.cohort_id,))
        else:
            conn.execute("INSERT OR REPLACE INTO y6_allocation (cohort_id, form_name, how, "
                         "allocated_by) VALUES (?, ?, 'manual', ?)", (row.cohort_id, form,
                                                                      actor.username))
        _audit(conn, "allocate", actor, row.intake_year, row.cohort_id, form=form,
               was=row.form_name)
    activity_log.record("year6.allocate", target=row.cohort_id, principal=actor, form=form)
    return get(row.cohort_id, actor=actor)


def clear_allocation(intake_year: str, *, actor: Principal, include_manual: bool = False
                     ) -> int:
    _require_editor(actor, "allocate")
    year = _year(intake_year)
    with database.connect() as conn:
        _require_unlocked(conn, year)
        sql = ("DELETE FROM y6_allocation WHERE cohort_id IN (SELECT cohort_id FROM y6_cohort "
               "WHERE intake_year = ?)")
        if not include_manual:
            sql += " AND how = 'auto'"
        n = conn.execute(sql, (year,)).rowcount or 0
        _audit(conn, "allocate_clear", actor, year, removed=n, manual=include_manual)
    return n


def warnings(intake_year: str, *, actor: Principal) -> list[dict[str, Any]]:
    """Problems with the allocation: ``{level, kind, cohort_id, text}``
    (level "bad" for a broken keep-apart or a full form)."""
    year = _year(intake_year)
    rows = {r.cohort_id: r for r in cohort(year, actor=actor)}
    out: list[dict[str, Any]] = []
    with database.connect() as conn:
        active = set(rows)
        apart = _pairs(conn, year, "keep_apart", active)
        friend = _pairs(conn, year, "friend", active)
        unmatched = conn.execute(
            "SELECT COUNT(*) FROM y6_relationships r JOIN y6_cohort c ON c.cohort_id = "
            "r.cohort_id WHERE c.intake_year = ? AND r.other_cohort_id IS NULL",
            (year,)).fetchone()[0]
    seen: set[frozenset] = set()
    for a, b in apart:
        key = frozenset((a, b))
        if key in seen:
            continue
        seen.add(key)
        if rows[a].form_name and rows[a].form_name == rows[b].form_name:
            out.append({"level": "bad", "kind": "keep_apart", "cohort_id": a,
                        "text": f"{rows[a].name} and {rows[b].name} should be kept apart but "
                                f"are both in {rows[a].form_name}"})
    with_friend: dict[int, bool] = {}
    for a, b in friend:
        if rows[a].form_name and rows[b].form_name:
            with_friend[a] = with_friend.get(a, False) or rows[a].form_name == rows[b].form_name
    for a, ok in with_friend.items():
        if not ok:
            out.append({"level": "warn", "kind": "friendship", "cohort_id": a,
                        "text": f"{rows[a].name} isn't with any requested friend"})
    for f in form_summary(year, actor=actor):
        if f["capacity"] is not None and f["size"] > f["capacity"]:
            out.append({"level": "bad", "kind": "capacity", "cohort_id": None,
                        "text": f"{f['name']} has {f['size']} for {f['capacity']} places"})
    loose = [r for r in rows.values() if not r.form_name]
    if loose:
        out.append({"level": "warn", "kind": "unallocated", "cohort_id": None,
                    "text": f"{len(loose)} child(ren) not in a form yet"})
    if unmatched:
        out.append({"level": "info", "kind": "names", "cohort_id": None,
                    "text": f"{unmatched} friendship / keep-apart name(s) from reports don't "
                            "match a child in the cohort - link them on Friendships"})
    return out


def publish(intake_year: str, *, actor: Principal) -> list[str]:
    """Lock the allocation and put every child who already has a pupil
    record here (on roll, Year 7) in their form via the pupils domain."""
    _require_editor(actor, "publish")
    year = _year(intake_year)
    broken = [w["text"] for w in warnings(year, actor=actor) if w["kind"] == "keep_apart"]
    if broken:
        raise ValidationError(["Fix the broken keep-aparts first", *broken])
    notes: list[str] = []
    with database.connect() as conn:
        if _published(conn, year):
            raise ValidationError(["The allocation is already published"])
        conn.execute("INSERT INTO y6_allocation_publish (intake_year, published_at, "
                     "published_by) VALUES (?, datetime('now'), ?)", (year, actor.username))
        _audit(conn, "publish", actor, year)
    n = 0
    for r in cohort(year, actor=actor):
        if r.pupil_id and r.form_name:
            note = _set_form(r.pupil_id, r.form_name, actor)
            if note is None:
                n += 1
            else:
                notes.append(f"{r.name}: {note}")
    notes.insert(0, f"allocation published; {n} pupil record(s) given their form")
    activity_log.record("year6.publish", principal=actor, intake=year, set=n)
    return notes


def unpublish(intake_year: str, *, actor: Principal, reason: str) -> None:
    """Unlock the allocation to change it (pupil records keep their forms
    until it is published again)."""
    _require_editor(actor, "publish")
    year = _year(intake_year)
    why = _text(reason, 300)
    if not why:
        raise ValidationError(["Say why the allocation is being unlocked"])
    with database.connect() as conn:
        if not _published(conn, year):
            raise ValidationError(["The allocation isn't published"])
        conn.execute("DELETE FROM y6_allocation_publish WHERE intake_year = ?", (year,))
        _audit(conn, "unpublish", actor, year, reason=why)
    activity_log.record("year6.unpublish", principal=actor, intake=year)
