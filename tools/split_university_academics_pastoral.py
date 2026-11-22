#!/usr/bin/env python3
"""Split the university's Academics and Pastoral slices into business areas.

Academics (~350k lines) and Pastoral (~220k lines) were catch-alls. Every file
in them moves to the area it serves, keeping its path below the slice
(``domains/academics/<rest>`` -> ``domains/<area>/<rest>``) except that
``domain/services/<pkg>`` flattens to ``domain/<pkg>`` in every slice but
Admissions, whose own layout keeps ``domain/services/``:

* new slices: ``curriculum``, ``teaching``, ``integrity``, ``research``,
  ``library``, ``quality``, ``health``, ``student_support``, ``student_life``;
* existing slices that take a part: ``assessment`` (assignments, exams, grade
  tracking), ``progression`` (degree audit, graduation, credentials),
  ``learners`` (parent portal), ``admissions`` (admissions selection);
* three shared Academics GUI helpers go to ``infrastructure/ui``; the
  ``_report_presentation`` alias is replaced by the platform module it aliased.

There are no shims: every import, quoted or written module name and path in
``src/`` (migrations included), ``tests/``, ``tools/`` and the path-bearing
config (pyproject, Makefile, classification, layout baseline) is rewritten.
Relative imports that would resolve differently after the move are first made
absolute. Module classifications are preserved exactly (the run refuses
otherwise). The Academics and Pastoral boundary tests are replaced by one per
receiving slice, carrying every allow-list entry (mapped) plus the reaches the
split makes visible.

Usage::

    python tools/split_university_academics_pastoral.py            # dry run
    python tools/split_university_academics_pastoral.py --apply
"""

from __future__ import annotations

import argparse
import ast
import collections
import fnmatch
import importlib.util
import json
import re
import shutil
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import move_university_ai as base  # noqa: E402

ROOT, SRC = base.ROOT, base.SRC
U = base.U
D = U / "domains"
PKG_U = "education_system.systems.university"
CLASSIFICATION = base.CLASSIFICATION
BOUNDARY_TESTS = ROOT / "tests/unit/systems/university/domains"
MAP_FILE = ROOT / "var/backups/maintenance/university-academics-pastoral-split-map.json"
PATH_CONFIGS = [ROOT / "pyproject.toml", ROOT / "Makefile", ROOT / "tools/layout_baseline.json"]
REMOVE = ROOT / "remove"

# ── the plan: (old path under domains/, new path under systems/university/) ──

PLAN: list[tuple[str, str]] = []


def put(area: str, top: str, layer: str, names: str, new_layer: str | None = None) -> None:
    new_layer = layer if new_layer is None else new_layer
    for name in names.split():
        old = f"{top}/{layer}/{name}" if layer else f"{top}/{name}"
        new = f"{new_layer}/{name}" if new_layer else name
        PLAN.append((old, f"domains/{area}/{new}"))


A, P = "academics", "pastoral"
# Academics — domain/services (flattened to domain/ except for Admissions)
put("teaching", A, "domain/services", "attendance module_scheduling academic_calendar office_hours "
    "virtual_classroom timetable section_meeting_calendar.py timetable_bridge.py timetable_ics.py",
    "domain")
put("assessment", A, "domain/services", "assignments exam_management ai_grading assessment_service.py",
    "domain")
put("integrity", A, "domain/services", "plagiarism", "domain")
put("library", A, "domain/services", "library", "domain")
put("curriculum", A, "domain/services", "course_management modules.py", "domain")
put("quality", A, "domain/services", "evaluation", "domain")
put("progression", A, "domain/services", "degree_audit", "domain")
put("learners", A, "domain/services", "parent_portal", "domain")
put("admissions", A, "domain/services", "admissions_selection")
# Academics — domain
put("curriculum", A, "domain", "course_planning curriculum_specification programme_governance "
    "collaborative_provision student_mobility")
put("student_life", A, "domain", "study_hub ai_study")
put("research", A, "domain", "research")
PLAN.append((f"{A}/domain/research/external_quality_assurance",
             "domains/quality/domain/external_quality_assurance"))
# Academics — application
put("teaching", A, "application", "timetabling.py")
# Academics — GUI
put("curriculum", A, "interfaces/gui", "course_management_gui course_management module_management "
    "course_catalog student_registration curriculum_specification collaborative_provision "
    "programme_governance student_mobility _section_picker.py student_outcomes_gui.py")
put("teaching", A, "interfaces/gui", "module_scheduling attendance_tracker academic_calendar "
    "office_hours timetabling course_forums course_messaging roster_viewer attendance_grade "
    "_cross_dialogs _cross_launchers.py _cross_services.py student_timetable_gui.py "
    "timetable_management.py virtual_classroom_gui.py")
put("assessment", A, "interfaces/gui", "assignment_system grade_tracking grade_tracking_management_gui "
    "exam_management student_grades bulk_grade_import _absence_to_deferred.py "
    "_attendance_eligibility.py _exam_attendance_writer.py")
put("integrity", A, "interfaces/gui", "ai_detector ai_detector_gui.py plagiarism_main_gui")
put("library", A, "interfaces/gui", "library")
put("research", A, "interfaces/gui", "research")
put("quality", A, "interfaces/gui", "course_health semester_analytics")
put("progression", A, "interfaces/gui", "blockchain_credentials_gui.py")
put("learners", A, "interfaces/gui", "parent_portal")
put("student_life", A, "interfaces/gui", "study_hub ai_study")
PLAN += [
    (f"{A}/interfaces/gui/_field_pickers.py", "infrastructure/ui/field_pickers.py"),
    (f"{A}/interfaces/gui/report_widgets.py", "infrastructure/ui/report_widgets.py"),
    (f"{A}/interfaces/gui/_module_dialog.py", "infrastructure/ui/module_dialog.py"),
]
# Academics — CLI
put("curriculum", A, "interfaces/cli", "course_planning curriculum_specification programme_governance "
    "collaborative_provision student_mobility course_catalog_cli.py transfer_credits_cli.py")
put("teaching", A, "interfaces/cli", "services timetabling office_hours_cli.py office_hours_extra_cli.py")
put("assessment", A, "interfaces/cli", "exam_management_cli.py exam_office_cli.py exam_seating_cli.py")
put("integrity", A, "interfaces/cli", "integrity")
put("research", A, "interfaces/cli", "research")
put("quality", A, "interfaces/cli", "accreditation_cli.py")
put("progression", A, "interfaces/cli", "graduation graduation_ceremony_cli.py")
put("student_life", A, "interfaces/cli", "study_hub ai_study")
# Pastoral — domain
put("health", P, "domain", "health")
put("student_support", P, "domain", "disability wellbeing advising equality_diversity")
put("student_life", P, "domain", "student_life social_matching student_jobs student_app achievement_badges")
put("student_support", P, "domain/services", "student_support helpdesk early_warning mental_health "
    "accessibility_tools.py", "domain")
put("student_life", P, "domain/services", "career_services internship_management.py", "domain")
# Pastoral — application / infrastructure
put("health", P, "application", "health")
put("health", P, "infrastructure", "health")
# Pastoral — GUI
put("health", P, "interfaces/gui", "health")
put("student_support", P, "interfaces/gui", "student_support helpdesk wellbeing disability "
    "equality_diversity advising accessibility_tools_gui.py counselling_panel.py")
put("student_life", P, "interfaces/gui", "student_union_gui student_life internship_management "
    "student_jobs social_matching career_services student_app achievement_badges document_center "
    "account_security notification_prefs student_profile student_union_management_gui.py")
# Pastoral — CLI
put("health", P, "interfaces/cli", "health_portal health")
put("student_support", P, "interfaces/cli", "wellbeing student_support disability equality_diversity advising")
put("student_life", P, "interfaces/cli", "student_union_events student_jobs social_matching student_life "
    "student_app achievement_badges")

#: Aliases replaced by the module they re-export (the file goes to remove/).
ALIASES = {f"{A}/interfaces/gui/_report_presentation.py":
           "education_system.platform.delivery.gui.report_presentation"}
#: Package __init__ files of the packages being split up (re-exports nobody imports).
SPLIT_INITS = [f"{t}/{p}__init__.py" for t in (A, P) for p in (
    "", "domain/", "domain/services/", "interfaces/", "interfaces/gui/", "interfaces/cli/",
    "application/", "infrastructure/")]

NEW_SLICES = {
    "curriculum": "Curriculum: programmes, modules and the academic offering.\n\nOwns course "
                  "and module management, the catalogue, course planning, curriculum\n"
                  "specification, programme governance, collaborative provision, student\n"
                  "mobility, student module registration and learning outcomes.",
    "teaching": "Teaching: delivering the timetable.\n\nOwns attendance, module scheduling, "
                "the academic calendar, timetabling,\noffice hours, virtual classrooms, "
                "rosters, course forums and course messaging.",
    "integrity": "Academic integrity: plagiarism checking and the AI content detector "
                 "(screens and\nconsole). The case rules are in ``application/integrity``.",
    "research": "Research: the research office, postgraduate research (PGR) and their screens.",
    "library": "Library: circulation, catalogue and library services, and their screens.",
    "quality": "Quality: module, course and lecturer evaluation, external quality assurance,\n"
               "accreditation, course health and semester comparisons.",
    "health": "Health: the health portal, appointments, records, dentist, first aid and\n"
              "vaccinations.\n\n**Medical data stays private to this slice.** Safeguarding "
              "referrals cross the\nboundary through an explicit port or event, never a table "
              "import.",
    "student_support": "Student support: the support and helpdesk tickets, early warning, advising,\n"
                       "disability and accessibility, wellbeing and mental health, and equality\n"
                       "and diversity.",
    "student_life": "Student life: the student union, clubs and events, jobs and internships,\n"
                    "careers, social matching, badges, the student app, student self-service\n"
                    "(profile, documents, security, notification preferences) and Study Hub.",
}
LAYER_DOCS = {
    "domain": "Business rules for this slice.",
    "domain/services": "Domain services for this slice.",
    "interfaces": "Thin inbound adapters for this slice (cli, gui).",
    "interfaces/gui": "Tk screens for this slice.",
    "interfaces/cli": "Console menus for this slice.",
    "application": "Use cases for this slice.",
    "infrastructure": "Adapters to storage and services for this slice.",
}


# ── plan resolution ──────────────────────────────────────────────────────────

def _dotted_rel(rel: str) -> str:
    """'domains/x/y.py' (under systems/university) -> dotted module."""
    rel = rel[:-3] if rel.endswith(".py") else rel
    rel = rel[:-9] if rel.endswith("/__init__") else rel
    return f"{PKG_U}." + rel.replace("/", ".")


def plan_files():
    """(moves [(old Path, new Path)], data moves, prefixes old->new dotted, problems)."""
    entries = sorted(PLAN, key=lambda e: -len(e[0]))
    problems: list[str] = []
    moves, data = [], []
    owned = set(ALIASES) | set(SPLIT_INITS)
    for top in (A, P):
        for path in sorted((D / top).rglob("*")):
            if "__pycache__" in path.parts or path.is_dir():
                continue
            rel = path.relative_to(D).as_posix()
            if rel in owned:
                continue
            hit = next(((o, n) for o, n in entries if rel == o or rel.startswith(o + "/")), None)
            if hit is None:
                problems.append(f"not in the plan: {rel}")
                continue
            dest = U / (hit[1] + rel[len(hit[0]):])
            (moves if path.suffix == ".py" else data).append((path, dest))
    prefixes = {_dotted_rel("domains/" + o): _dotted_rel(n) for o, n in PLAN}
    prefixes.update({_dotted_rel("domains/" + o): new for o, new in ALIASES.items()})
    for o, _ in PLAN:
        if not (D / o).exists():
            problems.append(f"planned path missing: {o}")
    return moves, data, prefixes, problems


def area_of(path: Path, moves_by_old: dict[Path, Path]) -> str | None:
    dest = moves_by_old.get(path, path)
    try:
        rel = dest.relative_to(D).parts
    except ValueError:
        return None
    return rel[0]


# ── relative imports ─────────────────────────────────────────────────────────

def _pkg_of(path: Path) -> list[str]:
    return list(path.parent.relative_to(SRC).parts)


def _module_exists_old(dotted: str) -> bool:
    p = SRC / Path(*dotted.split("."))
    return p.with_suffix(".py").exists() or (p / "__init__.py").exists()


def relative_fixes(moves, prefixes):
    """{old file: new text} making relative imports absolute where the move would
    change what they resolve to."""
    new_of = {o: n for o, n in moves}
    fixes = {}
    for old, new in moves:
        text = old.read_text(encoding="utf-8", errors="replace")
        if "from ." not in text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        lines = text.split("\n")
        changed = False
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ImportFrom) and node.level):
                continue
            old_base = _pkg_of(old)[: len(_pkg_of(old)) - node.level + 1]
            new_base = _pkg_of(new)[: len(_pkg_of(new)) - node.level + 1]
            mod = node.module or ""
            old_target = ".".join(old_base + ([mod] if mod else []))
            new_resolved = ".".join(new_base + ([mod] if mod else []))
            expected = base._map_name(old_target, prefixes) or old_target
            ok = expected == new_resolved
            if ok:
                for alias in node.names:
                    child = f"{old_target}.{alias.name}"
                    if _module_exists_old(child):
                        exp_child = base._map_name(child, prefixes) or child
                        if exp_child != f"{new_resolved}.{alias.name}":
                            ok = False
            if ok:
                continue
            first = lines[node.lineno - 1]
            head = re.compile(r"from\s+\.+[\w.]*\s+import")
            m = head.search(first, node.col_offset)
            if not m:
                raise SystemExit(f"cannot rewrite relative import at {old}:{node.lineno}")
            lines[node.lineno - 1] = first[:m.start()] + f"from {old_target} import" + first[m.end():]
            changed = True
        if changed:
            fixes[old] = "\n".join(lines)
    return fixes


# ── module names split over adjacent string literals ─────────────────────────

_LITERALS = re.compile(r"""^\s*(?:(['"])[^'"\n]*\1\s*)+$""")


def join_split_strings(text: str, prefixes) -> tuple[str, int]:
    """Rewrite module names written as implicitly concatenated literals
    (``"a.domains.academics."`` ``"b.c"``), which the token pass cannot see."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, 0
    lines = text.split("\n")
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    edits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and node.end_lineno != node.lineno):
            continue
        value = node.value
        if ".domains.academics." not in value and ".domains.pastoral." not in value:
            continue
        mapped = base._TOKEN.sub(lambda m: base._map_name(m.group(0), prefixes) or m.group(0), value)
        if mapped == value:
            continue
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[node.end_lineno - 1] + node.end_col_offset
        segment = text[start:end]
        if not _LITERALS.match(segment) or segment.lstrip()[0] not in "'\"":
            continue
        quote = segment.lstrip()[0]
        second = lines[node.lineno]
        indent = second[: len(second) - len(second.lstrip())]
        lead = len(lines[node.lineno - 1][: node.col_offset])
        if lead + len(mapped) + 2 <= 99:
            new = f"{quote}{mapped}{quote}"
        else:
            first_len = len(segment.split("\n")[0].strip()) - 2
            cut = mapped.rfind(".", 0, max(first_len, 20)) + 1 or len(mapped) // 2
            new = f"{quote}{mapped[:cut]}{quote}\n{indent}{quote}{mapped[cut:]}{quote}"
        edits.append((start, end, new))
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text, len(edits)


# ── rewriting text that is not Python source ─────────────────────────────────

_BARE = re.compile(r"[\w./$(){}*-]*domains/(?:academics|pastoral)/[\w/.*-]*")


def _bare_slash_map():
    pairs = [("domains/" + o, n) for o, n in PLAN]
    pairs += [("domains/" + o, "REMOVED:" + n) for o, n in ALIASES.items()]
    return sorted(pairs, key=lambda p: -len(p[0]))


def rewrite_bare_paths(text: str) -> tuple[str, int]:
    pairs = _bare_slash_map()
    count = 0

    def swap(m):
        nonlocal count
        token = m.group(0)
        if "tests/" in token:
            return token
        i = token.find("domains/")
        rest = token[i:]
        for old, new in pairs:
            if new.startswith("REMOVED:"):
                continue
            if rest == old or rest.startswith(old + "/") or rest.startswith(old + "*"):
                count += 1
                return token[:i] + new + rest[len(old):]
        return token

    return _BARE.sub(swap, text), count


def rewrite_text_file(path: Path, prefixes, apply: bool) -> int:
    text = path.read_text(encoding="utf-8")
    new, n = base._TOKEN.subn(lambda m: base._map_name(m.group(0), prefixes) or m.group(0), text)
    new, k = rewrite_bare_paths(new)
    if apply and new != text:
        path.write_text(new, encoding="utf-8")
    return n + k


# ── classification ───────────────────────────────────────────────────────────

def _classify(rel: str, rules) -> str:
    return next(r["classification"] for r in rules if fnmatch.fnmatch(rel, r["glob"]))


def new_classification(moves):
    catalogue = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    rules = catalogue["rules"]
    old_of = {}
    for old, new in moves:
        old_of[new.relative_to(U).as_posix()] = _classify(old.relative_to(U).as_posix(), rules)
    whole_core = ["curriculum", "teaching", "integrity", "research", "library", "quality"]
    new_rules = []
    for r in rules:
        if r["glob"] == "domains/academics/**":
            new_rules += [{"glob": f"domains/{s}/**", "classification": r["classification"]}
                          for s in whole_core]
        elif r["glob"] == "domains/pastoral/domain/health/**":
            new_rules.append({"glob": "domains/health/domain/health/**",
                              "classification": r["classification"]})
        else:
            new_rules.append(r)
    extra: dict[str, str] = {}
    for new_rel, cls in sorted(old_of.items()):
        if _classify(new_rel, new_rules) == cls:
            continue
        entry = next(n for o, n in sorted(PLAN, key=lambda e: -len(e[1]))
                     if new_rel == n or new_rel.startswith(n + "/"))
        glob = entry if entry.endswith(".py") else entry + "/**"
        extra[glob] = cls
    at = next(i for i, r in enumerate(new_rules) if r["glob"] == "**")
    new_rules[at:at] = [{"glob": g, "classification": c} for g, c in sorted(extra.items())]
    changed = [n for n, c in old_of.items() if _classify(n, new_rules) != c]
    catalogue["rules"] = new_rules
    return catalogue, changed, extra


# ── boundary tests ───────────────────────────────────────────────────────────

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def carried_entries(prefixes, moves_by_old):
    """Academics/Pastoral allow-list entries, mapped: {slice: [(rel, module, origin)]}."""
    out = collections.defaultdict(list)
    for top in (A, P):
        test = _load(f"bt_{top}", BOUNDARY_TESTS / top / f"test_{top}_boundaries.py")
        groups = {name: val for name, val in vars(test).items()
                  if isinstance(val, (set, frozenset, dict)) and name.isupper()}
        for rel, module in sorted(test.KNOWN_VIOLATIONS):
            origin = next((n for n, v in groups.items()
                           if n != "KNOWN_VIOLATIONS" and isinstance(v, (set, frozenset))
                           and (rel, module) in v), "KNOWN_VIOLATIONS")
            old_file = D / top / rel
            new_file = moves_by_old.get(old_file)
            if new_file is None:
                continue
            slice_ = new_file.relative_to(D).parts[0] if D in new_file.parents else None
            if slice_ is None:
                continue
            new_rel = new_file.relative_to(D / slice_).as_posix()
            out[slice_].append((new_rel, base._map_name(module, prefixes) or module, f"{top}.{origin}"))
    return out


def write_boundary_test(slice_: str, actual: set, carried: list) -> str:
    carried_set = {(r, m) for r, m, _ in carried}
    by_origin = collections.defaultdict(list)
    for r, m, o in carried:
        if (r, m) in actual:
            by_origin[o].append((r, m))
    new = sorted(actual - carried_set)
    lines = [
        f'"""Import-boundary tests for the {slice_.replace("_", " ").title()} vertical slice.',
        "",
        "The rules live in ``tests/unit/systems/university/domains/conftest.py``; this",
        "module supplies only what the slice currently violates. The allow-list is a",
        "ratchet — see ``_assert_ratchet`` — so it can only shrink.",
        "",
        "Generated by ``tools/split_university_academics_pastoral.py`` when Academics and",
        "Pastoral were split into areas (2026-10-24). Carried entries keep the group",
        "they had in the old Academics/Pastoral allow-list.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        f'SLICE = "{slice_}"',
        "",
        "KNOWN_VIOLATIONS: set[tuple[str, str]] = {",
    ]
    for origin in sorted(by_origin):
        lines.append(f"    # Carried from {origin}.")
        lines += [f"    ({r!r}, {m!r})," for r, m in sorted(by_origin[origin])]
    if new:
        lines.append("    # Reaches the split made visible: these were inside one slice before.")
        lines += [f"    ({r!r}, {m!r})," for r, m in new]
    lines += [
        "}",
        "",
        "",
        "def test_slice_is_in_place(slice_violations) -> None:",
        "    # Fails loudly if the slice directory has gone missing.",
        "    slice_violations(SLICE)",
        "",
        "",
        "def test_boundary_ratchet(assert_slice_ratchet) -> None:",
        "    assert_slice_ratchet(SLICE, KNOWN_VIOLATIONS)",
        "",
    ]
    return "\n".join(lines)


EXTRA_TESTS = {
    "teaching": '''

def test_timetabling_moved_with_the_slice() -> None:
    """application/timetabling.py came across, per the document."""
    from pathlib import Path
    uni = Path(__file__).resolve().parents[5] / "src/education_system/systems/university"
    assert (uni / "domains/teaching/application/timetabling.py").is_file()
    assert not (uni / "application/timetabling.py").exists()
''',
}


# ── main ─────────────────────────────────────────────────────────────────────

def coupling(moves, prefixes):
    moves_by_old = dict(moves)
    edges = collections.Counter()
    for old, new in moves:
        a = area_of(old, moves_by_old)
        text = old.read_text(encoding="utf-8", errors="replace")
        for m in set(base._TOKEN.findall(text)):
            if ".domains.academics." not in m and ".domains.pastoral." not in m:
                continue
            mapped = base._map_name(m, prefixes)
            if mapped and ".domains." in mapped:
                b = mapped.split(".domains.")[1].split(".")[0]
                if b != a:
                    edges[(a, b)] += 1
    return edges


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    moves, data, prefixes, problems = plan_files()
    collisions = [str(n) for _, n in moves + data if n.exists()]
    dup = [n for n, c in collections.Counter(n for _, n in moves + data).items() if c > 1]
    print(f"modules to move: {len(moves)} | data files: {len(data)} | plan entries: {len(PLAN)} "
          f"| prefixes: {len(prefixes)}")
    if problems or collisions or dup:
        print("Refusing:", *(problems + collisions + [str(d) for d in dup])[:40], sep="\n  ")
        return 1
    fixes = relative_fixes(moves, prefixes)
    print(f"relative imports made absolute in {len(fixes)} files")
    catalogue, changed, extra = new_classification(moves)
    print(f"classification: {len(extra)} entry-level rules added; files changing class: {len(changed)}")
    if changed:
        print("Refusing: classification would change for", changed[:10])
        return 1
    edges = coupling(moves, prefixes)
    print(f"cross-slice mentions created by the split: {sum(edges.values())}")
    for (a, b), n in edges.most_common(12):
        print(f"   {n:4} {a} -> {b}")

    sources = {o for o, _ in moves}
    py_paths = [p for root in (SRC / "education_system", ROOT / "tests", ROOT / "tools")
                for p in root.rglob("*.py")
                if "__pycache__" not in p.parts and p not in sources
                and not p.name.startswith(("move_", "split_"))
                and not (p.name.endswith("_boundaries.py") and p.parent.name in (A, P))]
    joined = {}
    for p in py_paths + sorted(sources):
        text = p.read_text(encoding="utf-8", errors="replace")
        if "domains.academics." in text or "domains.pastoral." in text:
            new, k = join_split_strings(text, prefixes)
            if k:
                joined[p] = new
    print(f"split string module names rewritten in {len(joined)} files")
    files, refs, hand = base.rewrite(prefixes, apply=False, paths=py_paths + sorted(sources))
    hand = sorted(set(hand))
    print(f"python files to rewrite: {files} | references: {refs} | to fix by hand: {len(hand)}")
    for line in hand:
        print("  hand:", line)
    cfg = sum(rewrite_text_file(p, prefixes, apply=False) for p in PATH_CONFIGS)
    print(f"path/config references to rewrite: {cfg}")
    if not args.apply:
        print("\nDry run. Re-run with --apply.")
        return 0

    # backup
    from education_system import paths as edu_paths
    dest = edu_paths.maintenance_backup_dir("university-academics-pastoral-split", create=True)
    archive = dest / "sources.tar.gz"
    needles = ("domains.academics", "domains.pastoral", "domains/academics", "domains/pastoral")
    with tarfile.open(archive, "w:gz") as tar:
        for top in (A, P):
            tar.add(D / top, arcname=str((D / top).relative_to(ROOT)),
                    filter=lambda t: None if "__pycache__" in t.name else t)
            tar.add(BOUNDARY_TESTS / top / f"test_{top}_boundaries.py",
                    arcname=f"tests/unit/systems/university/domains/{top}/test_{top}_boundaries.py")
        for p in py_paths + PATH_CONFIGS + [CLASSIFICATION]:
            if p.exists() and any(n in p.read_text(encoding="utf-8", errors="replace") for n in needles):
                tar.add(p, arcname=str(p.relative_to(ROOT)))
    print("backup:", archive)

    carried = carried_entries(prefixes, dict(moves))
    for p, text in joined.items():
        p.write_text(text, encoding="utf-8")
    fixes = relative_fixes(moves, prefixes)
    for old, text in fixes.items():
        old.write_text(text, encoding="utf-8")
    created = []
    for old, new in moves + data:
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(new))
    for s, doc in NEW_SLICES.items():
        init = D / s / "__init__.py"
        if not init.exists():
            init.write_text(f'"""{doc}\n"""\n', encoding="utf-8")
            created.append(init)
    for _, new in moves:
        d = new.parent
        while D in d.parents:
            init = d / "__init__.py"
            if not init.exists():
                layer = d.relative_to(D).as_posix().split("/", 1)
                doc = LAYER_DOCS.get(layer[1] if len(layer) > 1 else "", "")
                init.write_text(f'"""{doc}"""\n' if doc else "", encoding="utf-8")
                created.append(init)
            d = d.parent
    for rel in list(ALIASES) + SPLIT_INITS:
        src_path = D / rel
        if src_path.exists():
            target = REMOVE / src_path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(target))
    for top in (A, P):
        leftovers = [p for p in (D / top).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
        if leftovers:
            raise SystemExit(f"{top} still holds files: {leftovers[:5]}")
        shutil.rmtree(D / top)
        old_test = BOUNDARY_TESTS / top / f"test_{top}_boundaries.py"
        target = REMOVE / old_test.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_test), str(target))
    CLASSIFICATION.write_text(json.dumps(catalogue, indent=2) + "\n", encoding="utf-8")
    files, refs, hand = base.rewrite(prefixes, apply=True, paths=py_paths + [n for _, n in moves])
    hand = sorted(set(hand))
    cfg = sum(rewrite_text_file(p, prefixes, apply=True) for p in PATH_CONFIGS)
    # bare domains/<old>/... paths inside python sources (tools pins, tests, docstrings)
    bare = 0
    for p in py_paths + [n for _, n in moves]:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if "domains/academics" in text or "domains/pastoral" in text:
            new, k = rewrite_bare_paths(text)
            if k:
                p.write_text(new, encoding="utf-8")
                bare += k

    # boundary tests for every slice that received code
    conf = _load("bconf", BOUNDARY_TESTS / "conftest.py")
    receiving = sorted({n.relative_to(D).parts[0] for _, n in moves if D in n.parents})
    written = []
    for s in receiving:
        target = BOUNDARY_TESTS / s / f"test_{s}_boundaries.py"
        if target.exists():
            continue  # an existing slice keeps its curated test; adjusted by hand
        target.parent.mkdir(parents=True, exist_ok=True)
        actual = conf._violations(s)
        target.write_text(write_boundary_test(s, actual, carried.get(s, [])) + EXTRA_TESTS.get(s, ""),
                          encoding="utf-8")
        written.append(target)
    path_map = {o.relative_to(SRC / "education_system").as_posix():
                n.relative_to(SRC / "education_system").as_posix() for o, n in moves}
    MAP_FILE.write_text(json.dumps({"files": path_map, "prefixes": prefixes}, indent=1,
                                   sort_keys=True) + "\n", encoding="utf-8")
    print(f"moved {len(moves)} modules + {len(data)} data files; created {len(created)} __init__.py; "
          f"rewrote {refs} python references in {files} files, {cfg} config references, "
          f"{bare} bare paths; {len(hand)} to fix by hand; wrote {len(written)} boundary tests; "
          f"map: {MAP_FILE}")
    for line in hand:
        print("  hand:", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
