"""Classification rules as data, tied to the student's regulation version.

A rule set (``classification_rule_sets``) is one scheme with its numbers:

* ``default`` — the built-in rule in :mod:`classification` (Level 5 x1,
  Level 6 x2, UK bands, 2-mark borderline flag). Every student whose
  regulations and programme are unbound gets exactly this, so existing
  results do not change.
* ``ug_honours`` — configurable level weights, bands, a borderline zone and
  the rule applied inside it: ``none`` (flag only, the board decides),
  ``preponderance`` (raised when at least ``preponderance_share`` of the
  final-level credit is in the higher band), ``exit_velocity`` (raised when
  the final-level average is in the higher band) or ``best_of`` (the better
  of the weighted average and the final-level average).
* ``integrated_masters`` — the same, normally weighting Levels 5, 6 and 7.
* ``pgt`` — Distinction / Merit / Pass thresholds on the Level 7 average,
  with credit rules (all credit passed; optionally a named dissertation module
  must itself reach the band).

Exit awards (CertHE, DipHE, Ordinary degree, PGCert, PGDip) are the
programme's own ``course_exit_awards`` when it has any, else the rule set's
list (UK FHEQ norms by default).

A rule set is bound to a regulation version (``programme_versions``) or, for
programmes not under governance, to a programme code
(``classification_rule_bindings``). Resolution: the student's active
regulation assignment, then their programme, then the default.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json

from education_system.systems.university.application.assessment import classification
from education_system.systems.university.infrastructure.database.schemas import (
    progression_classification_schema as schema,
)

BORDERLINE_RULES = ("none", "preponderance", "exit_velocity", "best_of")
UG_EXIT_AWARDS = (
    {"name": "Certificate of Higher Education", "total_credits": 120, "credits_at_level": 120,
     "at_level": 4},
    {"name": "Diploma of Higher Education", "total_credits": 240, "credits_at_level": 120,
     "at_level": 5},
    {"name": "Ordinary Degree", "total_credits": 300, "credits_at_level": 60, "at_level": 6},
)
PG_EXIT_AWARDS = (
    {"name": "Postgraduate Certificate", "total_credits": 60, "credits_at_level": 60,
     "at_level": 7},
    {"name": "Postgraduate Diploma", "total_credits": 120, "credits_at_level": 120,
     "at_level": 7},
)
_UG_BANDS = [[70.0, "First"], [60.0, "2:1"], [50.0, "2:2"], [40.0, "Third"]]
#: Sector-norm starting points, offered in the GUI/CLI (never written unasked).
TEMPLATES = {
    "default": {},
    "ug_honours": {"level_weights": {"5": 1.0, "6": 2.0}, "bands": _UG_BANDS,
                   "pass_mark": 40.0, "borderline_margin": 2.0,
                   "borderline_rule": "preponderance", "preponderance_share": 0.5,
                   "final_level": 6, "max_trailing_credits": 20,
                   "exit_awards": list(UG_EXIT_AWARDS)},
    "integrated_masters": {"level_weights": {"5": 1.0, "6": 2.0, "7": 2.0}, "bands": _UG_BANDS,
                           "pass_mark": 40.0, "borderline_margin": 2.0,
                           "borderline_rule": "preponderance", "preponderance_share": 0.5,
                           "final_level": 7, "max_trailing_credits": 20,
                           "exit_awards": list(UG_EXIT_AWARDS) + [
                               {"name": "Bachelor's Degree with Honours", "total_credits": 360,
                                "credits_at_level": 90, "at_level": 6}]},
    "pgt": {"thresholds": {"Distinction": 70.0, "Merit": 60.0, "Pass": 50.0},
            "pass_mark": 50.0, "borderline_margin": 2.0, "borderline_rule": "none",
            "preponderance_share": 0.5, "require_all_credit_passed": True,
            "dissertation_module": "", "max_trailing_credits": 0,
            "exit_awards": list(PG_EXIT_AWARDS)},
}
DEFAULT_MAX_TRAILING_CREDITS = 20


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


# ── validation ──────────────────────────────────────────────────────────


def _number(value, label, low=0.0, high=100.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number") from None
    if not low <= number <= high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}")
    return number


def _clean_weights(weights) -> dict:
    if not isinstance(weights, dict) or not weights:
        raise ValueError("Give at least one level weight, e.g. {\"5\": 1, \"6\": 2}")
    out = {}
    for level, weight in weights.items():
        lvl = int(_number(level, "Level", 3, 8))
        out[str(lvl)] = _number(weight, f"Level {lvl} weight", 0, 10)
    if not any(out.values()):
        raise ValueError("At least one level must carry weight")
    return out


def _clean_bands(bands) -> list:
    rows = [[_number(floor, "Band floor"), str(label).strip()] for floor, label in bands or []]
    if not rows or any(not label for _f, label in rows):
        raise ValueError("Give the bands as [floor, label] pairs")
    if [f for f, _l in rows] != sorted({f for f, _l in rows}, reverse=True):
        raise ValueError("Band floors must be distinct and listed highest first")
    return rows


def _clean_exit_awards(awards) -> list:
    out = []
    for award in awards or []:
        name = str(award.get("name") or "").strip()
        total = int(_number(award.get("total_credits"), "Exit award credits", 1, 600))
        at = int(_number(award.get("credits_at_level") or 0, "Credits at level", 0, total))
        level = award.get("at_level")
        level = int(_number(level, "Exit award level", 3, 8)) if level not in (None, "") else None
        if not name or (at and level is None):
            raise ValueError("Each exit award needs a name, and a level for credits-at-level")
        out.append({"name": name, "total_credits": total, "credits_at_level": at,
                    "at_level": level})
    return out


def _clean_common(config) -> dict:
    rule = config.get("borderline_rule", "none")
    if rule not in BORDERLINE_RULES:
        raise ValueError(f"Borderline rule must be one of {', '.join(BORDERLINE_RULES)}")
    return {"pass_mark": _number(config.get("pass_mark", 40), "Pass mark"),
            "borderline_margin": _number(config.get("borderline_margin", 2), "Borderline zone",
                                         0, 10),
            "borderline_rule": rule,
            "preponderance_share": _number(config.get("preponderance_share", 0.5),
                                           "Preponderance share", 0, 1),
            "max_trailing_credits": _number(config.get("max_trailing_credits",
                                                       DEFAULT_MAX_TRAILING_CREDITS),
                                            "Maximum trailing credits", 0, 120),
            "exit_awards": _clean_exit_awards(config.get("exit_awards"))}


def clean_config(scheme: str, config: dict | None) -> dict:
    """Validated config for ``scheme``; raises ValueError with a message fit to show."""
    if scheme not in schema.SCHEMES:
        raise ValueError(f"Scheme must be one of {', '.join(schema.SCHEMES)}")
    config = dict(config or {})
    if scheme == "default":
        return {}
    out = _clean_common(config)
    if scheme == "pgt":
        thresholds = config.get("thresholds") or {}
        out["thresholds"] = {k: _number(thresholds.get(k), f"{k} threshold")
                             for k in ("Distinction", "Merit", "Pass")}
        if not out["thresholds"]["Distinction"] > out["thresholds"]["Merit"] \
                > out["thresholds"]["Pass"]:
            raise ValueError("Distinction > Merit > Pass thresholds are required")
        out["require_all_credit_passed"] = bool(config.get("require_all_credit_passed", True))
        out["dissertation_module"] = str(config.get("dissertation_module") or "").strip()
        return out
    out["level_weights"] = _clean_weights(config.get("level_weights"))
    out["bands"] = _clean_bands(config.get("bands"))
    out["final_level"] = int(_number(config.get("final_level") or max(
        int(k) for k in out["level_weights"]), "Final level", 3, 8))
    return out


# ── rule sets and bindings ──────────────────────────────────────────────


def create_rule_set(conn, name, scheme, config, actor, notes="") -> int:
    ensure(conn)
    if not (name or "").strip():
        raise ValueError("Name the rule set")
    clean = clean_config(scheme, config)
    try:
        cur = conn.execute(
            "INSERT INTO classification_rule_sets (name, scheme, config_json, notes, created_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (name.strip(), scheme, json.dumps(clean, sort_keys=True), notes or None, actor))
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError(f"A rule set called {name.strip()!r} already exists") from None
        raise
    return int(cur.lastrowid)


def rule_set(conn, rule_set_id) -> dict:
    ensure(conn)
    rows = _dicts(conn.execute("SELECT * FROM classification_rule_sets WHERE rule_set_id = ?",
                               (rule_set_id,)))
    if not rows:
        raise ValueError(f"No classification rule set {rule_set_id}")
    row = rows[0]
    row["config"] = json.loads(row.pop("config_json") or "{}")
    return row


def list_rule_sets(conn) -> list[dict]:
    ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT r.rule_set_id, r.name, r.scheme, r.retired, r.created_by, r.created_at, "
        "(SELECT COUNT(*) FROM classification_rule_bindings b "
        " WHERE b.rule_set_id = r.rule_set_id) AS bindings "
        "FROM classification_rule_sets r ORDER BY r.name"))
    return rows


def list_bindings(conn) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute(
        "SELECT b.binding_id, b.version_id, b.programme_code, b.rule_set_id, r.name, r.scheme, "
        "b.bound_by, b.bound_at FROM classification_rule_bindings b "
        "JOIN classification_rule_sets r ON r.rule_set_id = b.rule_set_id "
        "ORDER BY COALESCE(b.programme_code, ''), b.version_id"))


def _awards_ratified_under(conn, version_id) -> int:
    if not (_has_table(conn, "student_regulation_assignments")
            and _has_table(conn, "ratified_student_awards")):
        return 0
    return conn.execute(
        "SELECT COUNT(*) FROM ratified_student_awards a JOIN student_regulation_assignments r "
        "ON r.student_id = a.student_id AND r.version_id = ? WHERE a.status = 'ratified'",
        (version_id,)).fetchone()[0]


def _check_version(conn, version_id) -> None:
    if not _has_table(conn, "programme_versions") or conn.execute(
            "SELECT 1 FROM programme_versions WHERE version_id = ?",
            (version_id,)).fetchone() is None:
        raise ValueError(f"No regulation version {version_id}")


def bind(conn, rule_set_id, actor, *, version_id=None, programme_code=None) -> int:
    """Bind a rule set to a regulation version or a programme code (one or the other).

    A regulation version that already has ratified awards cannot be rebound:
    those classifications were made under the rule set it had.
    """
    ensure(conn)
    current = rule_set(conn, rule_set_id)
    if current["retired"]:
        raise ValueError("That rule set is retired")
    if (version_id is None) == (not programme_code):
        raise ValueError("Bind to either a regulation version or a programme code")
    if version_id is not None:
        version_id = int(version_id)
        _check_version(conn, version_id)
        existing = conn.execute("SELECT rule_set_id FROM classification_rule_bindings WHERE "
                                "version_id = ?", (version_id,)).fetchone()
        if existing and existing[0] != current["rule_set_id"] \
                and _awards_ratified_under(conn, version_id):
            raise ValueError("Awards have been ratified under this regulation version's rules; "
                             "approve a new regulation version instead")
        conn.execute("DELETE FROM classification_rule_bindings WHERE version_id = ?",
                     (version_id,))
    else:
        conn.execute("DELETE FROM classification_rule_bindings WHERE programme_code = ?",
                     (programme_code.strip(),))
    cur = conn.execute(
        "INSERT INTO classification_rule_bindings (version_id, programme_code, rule_set_id, "
        "bound_by) VALUES (?, ?, ?, ?)",
        (version_id, (programme_code or "").strip() or None, current["rule_set_id"], actor))
    return int(cur.lastrowid)


def unbind(conn, binding_id) -> bool:
    ensure(conn)
    row = conn.execute("SELECT version_id FROM classification_rule_bindings WHERE binding_id = ?",
                       (binding_id,)).fetchone()
    if row is None:
        return False
    if row[0] is not None and _awards_ratified_under(conn, row[0]):
        raise ValueError("Awards have been ratified under this binding; it cannot be removed")
    conn.execute("DELETE FROM classification_rule_bindings WHERE binding_id = ?", (binding_id,))
    return True


def _student_version(conn, student_id):
    if not _has_table(conn, "student_regulation_assignments"):
        return None
    row = conn.execute("SELECT version_id FROM student_regulation_assignments WHERE "
                       "student_id = ? AND active = 1 ORDER BY assignment_id DESC LIMIT 1",
                       (str(student_id),)).fetchone()
    return row[0] if row else None


def rules_for_student(conn, student_id) -> dict:
    """``{rule_set_id, name, scheme, config, basis}`` for the student (default if unbound)."""
    ensure(conn)
    version_id = _student_version(conn, student_id)
    row = None
    if version_id is not None:
        row = conn.execute("SELECT rule_set_id FROM classification_rule_bindings "
                           "WHERE version_id = ?", (version_id,)).fetchone()
        basis = f"regulation version {version_id}"
    if row is None:
        course = conn.execute("SELECT course FROM students WHERE student_id = ?",
                              (str(student_id),)).fetchone()
        if course and course[0]:
            row = conn.execute("SELECT rule_set_id FROM classification_rule_bindings "
                               "WHERE programme_code = ?", (course[0],)).fetchone()
            basis = f"programme {course[0]}"
    if row is None:
        return {"rule_set_id": None, "name": "University default", "scheme": "default",
                "config": {}, "basis": "no rule set bound (university default)"}
    found = rule_set(conn, row[0])
    return {"rule_set_id": found["rule_set_id"], "name": found["name"],
            "scheme": found["scheme"], "config": found["config"], "basis": basis}


def max_trailing_credits(conn, student_id) -> float:
    rules = rules_for_student(conn, student_id)
    return float(rules["config"].get("max_trailing_credits", DEFAULT_MAX_TRAILING_CREDITS))


# ── classification ──────────────────────────────────────────────────────


def _modules(conn, student_id) -> list[dict]:
    out = []
    for row in classification._module_rows(conn, student_id):
        out.append({"module_code": row[0], "mark": float(row[1]),
                    "level": classification.module_level(row[0], row[5]),
                    "credits": float(row[6] or 0), "complete": bool(row[4])})
    return out


def _weighted(rows) -> float | None:
    """Credit-weighted average (each module counts once when credits are not recorded)."""
    total = sum((r["credits"] or 1.0) for r in rows)
    if not total:
        return None
    return round(sum(r["mark"] * (r["credits"] or 1.0) for r in rows) / total, 2)


def _band(average, bands) -> str:
    for floor, label in bands:
        if average >= floor:
            return label
    return "Fail"


def _next_band(average, bands):
    """``(floor, label)`` of the band just above ``average``, or None at the top."""
    above = [(floor, label) for floor, label in bands if floor > average]
    return min(above) if above else None


def _share_at_or_above(rows, floor) -> float:
    total = sum((r["credits"] or 1.0) for r in rows)
    hit = sum((r["credits"] or 1.0) for r in rows if r["mark"] >= floor)
    return hit / total if total else 0.0


def _apply_borderline(result, rows, config) -> dict:
    """Raise a borderline average under the configured rule; flag it otherwise."""
    upper = _next_band(result["average"], config["bands"])
    if upper is None or upper[0] - result["average"] > config["borderline_margin"]:
        return result
    result["borderline"] = True
    final = [r for r in rows if r["level"] == config["final_level"]]
    rule = config["borderline_rule"]
    raised = False
    if rule == "preponderance":
        raised = _share_at_or_above(final, upper[0]) >= config["preponderance_share"]
    elif rule in ("exit_velocity", "best_of"):
        final_average = _weighted(final)
        raised = final_average is not None and final_average >= upper[0]
    if raised:
        result.update(classification=upper[1], raised=True,
                      note=f"Raised from the borderline under the {rule.replace('_', ' ')} rule.")
    return result


def _weighted_scheme(rows, config) -> dict:
    weights = {int(k): v for k, v in config["level_weights"].items()}
    by_level = {lvl: _weighted([r for r in rows if r["level"] == lvl]) for lvl in weights}
    counted = {lvl: avg for lvl, avg in by_level.items() if avg is not None and weights[lvl]}
    if not counted:
        return {"average": None, "classification": None, "borderline": False, "raised": False,
                "note": "No results at the counting levels yet."}
    weight = sum(weights[lvl] for lvl in counted)
    average = round(sum(avg * weights[lvl] for lvl, avg in counted.items()) / weight, 2)
    result = {"average": average, "classification": _band(average, config["bands"]),
              "borderline": False, "raised": False,
              "note": "" if len(counted) == len([w for w in weights.values() if w])
              else "Provisional: not all counting levels have results."}
    return _apply_borderline(result, rows, config)


def _pgt_band(average, thresholds) -> str:
    for label in ("Distinction", "Merit", "Pass"):
        if average >= thresholds[label]:
            return label
    return "Fail"


def _pgt_scheme(rows, config) -> dict:
    counted = [r for r in rows if r["level"] == 7] or rows
    average = _weighted(counted)
    if average is None:
        return {"average": None, "classification": None, "borderline": False, "raised": False,
                "note": "No Level 7 results yet."}
    label = _pgt_band(average, config["thresholds"])
    notes = []
    failed = [r["module_code"] for r in counted if r["mark"] < config["pass_mark"]]
    if config["require_all_credit_passed"] and failed:
        notes.append("Not all credit passed: " + ", ".join(failed))
        label = "Fail"
    dissertation = config.get("dissertation_module")
    if dissertation and label in ("Distinction", "Merit"):
        diss = next((r for r in counted if r["module_code"] == dissertation), None)
        capped = _pgt_band(diss["mark"], config["thresholds"]) if diss else "Pass"
        order = ("Fail", "Pass", "Merit", "Distinction")
        if order.index(capped) < order.index(label):
            label = max(capped, "Pass", key=order.index)
            notes.append(f"Capped at {label}: the dissertation {dissertation} must reach "
                         "the band.")
    bands = [[v, k] for k, v in sorted(config["thresholds"].items(), key=lambda kv: -kv[1])]
    result = {"average": average, "classification": label, "borderline": False,
              "raised": False, "note": " ".join(notes)}
    if label != "Fail" and not notes:
        result = _apply_borderline(result, counted, dict(config, bands=bands, final_level=7))
    return result


def classify(conn, student_id, rules: dict | None = None) -> dict:
    """The proposed classification under the student's rules (or ``rules``)."""
    rules = rules or rules_for_student(conn, student_id)
    if rules["scheme"] == "default":
        result = classification.degree_classification(conn, student_id)
        result.setdefault("raised", False)
    else:
        rows = _modules(conn, student_id)
        scheme = _pgt_scheme if rules["scheme"] == "pgt" else _weighted_scheme
        result = scheme(rows, rules["config"])
        result["levels"] = classification.level_averages(conn, student_id)
    result.update(rule_set=rules["name"], scheme=rules["scheme"], basis=rules["basis"])
    return result


# ── exit awards ─────────────────────────────────────────────────────────


def _credits(conn, student_id) -> dict:
    from education_system.systems.university.application.programmes import record
    return record.credits_by_level(conn, student_id)


def _meets(credit, award) -> bool:
    at_or_above = sum(v for k, v in credit.items()
                      if k != "total" and k is not None and award.get("at_level")
                      and k >= award["at_level"])
    return credit["total"] >= award["total_credits"] and \
        at_or_above >= (award.get("credits_at_level") or 0)


def _programme_exit_awards(conn, student_id) -> list[dict]:
    if not _has_table(conn, "course_exit_awards"):
        return []
    course = conn.execute("SELECT course FROM students WHERE student_id = ?",
                          (str(student_id),)).fetchone()
    if not course or not course[0]:
        return []
    return [{"name": r[0], "total_credits": r[1], "credits_at_level": r[2], "at_level": r[3]}
            for r in conn.execute(
                "SELECT award_name, total_credits, credits_at_level, at_level FROM "
                "course_exit_awards WHERE course_code = ? AND is_final = 0 "
                "ORDER BY total_credits", (course[0],))]


def exit_award(conn, student_id, rules: dict | None = None) -> dict | None:
    """The highest exit award the student's earned credit meets, or None.

    PGT exit awards carry Distinction / Merit / Pass under the rule set;
    undergraduate exit awards are unclassified.
    """
    rules = rules or rules_for_student(conn, student_id)
    awards = _programme_exit_awards(conn, student_id)
    source = "programme exit awards"
    if not awards:
        awards = rules["config"].get("exit_awards") or list(
            PG_EXIT_AWARDS if rules["scheme"] == "pgt" else UG_EXIT_AWARDS)
        source = f"rule set {rules['name']}"
    credit = _credits(conn, student_id)
    met = [a for a in sorted(awards, key=lambda a: a["total_credits"]) if _meets(credit, a)]
    if not met:
        return None
    best = dict(met[-1], source=source, earned_credits=credit["total"])
    best["classification"] = None
    if rules["scheme"] == "pgt":
        result = _pgt_scheme(_modules(conn, student_id), dict(rules["config"],
                                                                require_all_credit_passed=False,
                                                                dissertation_module=""))
        best["classification"] = result["classification"] if result["average"] else None
    return best


__all__ = ["BORDERLINE_RULES", "TEMPLATES", "bind", "classify", "clean_config",
           "create_rule_set", "exit_award", "list_bindings", "list_rule_sets",
           "max_trailing_credits", "rule_set", "rules_for_student", "unbind"]
