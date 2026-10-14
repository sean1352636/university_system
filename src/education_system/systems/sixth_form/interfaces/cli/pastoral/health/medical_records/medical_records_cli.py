"""CLI flows for Medical Records."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
    medical_records as data,
)
from education_system.systems.sixth_form.domain.pastoral.health.medical_records.medical_records import (
    ALLERGY_SEVERITIES,
    Allergy,
    BLOOD_GROUPS,
    CONDITION_SEVERITIES,
    Condition,
    DEFAULT_ALLERGY_SEVERITY,
    DEFAULT_CONDITION_SEVERITY,
    DEFAULT_MEDICATION_ROUTE,
    MEDICATION_ROUTES,
    Medication,
    ValidationError,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as _students,
)

logger = logging.getLogger(__name__)


class _UserAbort(Exception):
    pass


def _input(prompt: str, *, default: str = "",
            allow_empty: bool = True) -> str:
    suffix = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{suffix}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    s = raw.strip()
    if s.lower() == "cancel":
        raise _UserAbort
    if not s:
        if default:
            return default
        if not allow_empty:
            print("    Value is required.")
            return _input(prompt, default=default, allow_empty=False)
        return ""
    return s


def _pause() -> None:
    try:
        input("\n  Press Enter to continue...")
    except (EOFError, KeyboardInterrupt):
        pass


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    raw = _input(f"{prompt} (y/n)",
                  default="y" if default else "n").strip().lower()
    return raw in ("y", "yes")


def _multiline(prompt: str, *, default: str = "") -> str:
    print(f"\n  {prompt} (end with '.'; ENTER for default)")
    if default:
        for line in default.splitlines():
            print(f"    | {line}")
    lines: list[str] = []
    try:
        while True:
            ln = input("  > ")
            if ln.strip() == ".":
                break
            if not lines and not ln:
                return default
            lines.append(ln)
    except (EOFError, KeyboardInterrupt):
        print()
        raise _UserAbort
    return "\n".join(lines)


def _pick_from(label: str, options: list[str],
                default: str | None = None,
                allow_blank: bool = False) -> str:
    print(f"\n  {label}:")
    opts = ([""] + options) if allow_blank else options
    for i, opt in enumerate(opts, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(opts)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(opts)):
            print("    Out of range.")
            continue
        return opts[n - 1]


def _pick_student() -> str:
    rows = _students.list_students()
    if not rows:
        print("    No students.")
        raise _UserAbort
    print("\n  Students:")
    for i, s in enumerate(rows, 1):
        full = f"{getattr(s, 'first_name', '')} " \
               f"{getattr(s, 'last_name', '')}".strip()
        print(f"    {i:>3}) {s.student_id:<12}  {full}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1].student_id
        match = next((s for s in rows if s.student_id == raw), None)
        if match:
            return match.student_id
        print("    No matching student.")


# ── Rendering ────────────────────────────────────────────────────

def _print_profile_full(student_id: str) -> None:
    s = _students.get_student(student_id)
    name = getattr(s, "full_name", None) or "(unknown)"
    print(f"\n  Student: {student_id}  ({name})")

    p = data.get_profile(student_id)
    if p is None:
        print("    (no medical profile)")
    else:
        print(f"\n    NHS number       : {p.nhs_number or '—'}")
        print(f"    Blood group      : {p.blood_group or '—'}")
        print(f"    GP               : {p.gp_name or '—'}  "
              f"({p.gp_practice or '—'})  {p.gp_phone or ''}")
        print(f"    Emergency contact: {p.emergency_contact_name or '—'}"
              f"  ({p.emergency_contact_rel or '—'})"
              f"  {p.emergency_contact_phone or ''}")
        print(f"    Last reviewed    : {p.last_reviewed or '—'}")
        if p.notes:
            print("\n    Profile notes:")
            for line in p.notes.splitlines():
                print(f"      {line}")

    conds = data.list_conditions(student_id=student_id)
    print(f"\n    Conditions ({len(conds)}):")
    if not conds:
        print("      (none)")
    for c in conds:
        flag = " " if c.active else "i"
        print(f"      {flag}#{c.condition_id:<3}  "
              f"{c.severity:<9}  {c.name[:30]:<30}  "
              f"diagnosed {c.diagnosed_date or '—'}")

    today_meds = data.list_medications(student_id=student_id,
                                         active_on=None)
    print(f"\n    Medications ({len(today_meds)}):")
    if not today_meds:
        print("      (none)")
    for m in today_meds:
        flag = "!" if m.is_emergency else " "
        print(f"      {flag}#{m.medication_id:<3}  {m.name[:24]:<24}  "
              f"{m.dose or '—':<14}  {m.frequency or '—':<14}  "
              f"{m.route:<10}  "
              f"{m.start_date or '—'}–{m.end_date or '—'}")

    algs = data.list_allergies(student_id=student_id)
    print(f"\n    Allergies ({len(algs)}):")
    if not algs:
        print("      (none)")
    for a in algs:
        flag = "!" if a.severity in ("Severe",
                                       "Life-threatening") else " "
        epi = " [EpiPen]" if a.has_epipen else ""
        print(f"      {flag}#{a.allergy_id:<3}  {a.severity:<16}  "
              f"{a.allergen[:24]:<24}  → "
              f"{(a.reaction or '—')[:30]}{epi}")


def _print_student_table(rows: list[data.StudentMedicalSummary]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'Student':<12} {'Name':<24}  "
          f"{'Cond':>5}  {'SevC':>5}  "
          f"{'Meds':>5}  {'Emrg':>5}  "
          f"{'Alrg':>5}  {'SevA':>5}  Profile")
    print("  " + "-" * 110)
    for r in rows:
        prof = "yes" if r.profile else "—"
        print(f"  {r.student_id:<12} {r.student_name[:24]:<24}  "
              f"{r.active_conditions:>5}  {r.severe_conditions:>5}  "
              f"{r.current_medications:>5}  "
              f"{r.emergency_medications:>5}  "
              f"{r.allergies:>5}  {r.severe_allergies:>5}  {prof}")
    print(f"\n  {len(rows)} student(s).")


# ── Profile flows ────────────────────────────────────────────────

def view_student() -> None:
    try:
        sid = _pick_student()
        _print_profile_full(sid)
        _pause()
    except _UserAbort:
        return


def save_profile_flow() -> None:
    print("\n═══ Save / Update Medical Profile ═══")
    try:
        sid = _pick_student()
        existing = data.get_profile(sid)
        if existing is not None:
            print(f"  (Existing profile for {sid} — editing.)")
        nhs = _input("NHS number",
                       default=(existing.nhs_number if existing
                                 else "") or "")
        bg = _pick_from("Blood group", list(BLOOD_GROUPS),
                          allow_blank=True,
                          default=(existing.blood_group if existing
                                    else ""))
        gp_name = _input("GP name",
                            default=(existing.gp_name if existing
                                      else "") or "")
        gp_practice = _input("GP practice",
                               default=(existing.gp_practice if existing
                                         else "") or "")
        gp_phone = _input("GP phone",
                            default=(existing.gp_phone if existing
                                      else "") or "")
        ec_name = _input("Emergency contact name",
                            default=(existing.emergency_contact_name
                                      if existing else "") or "")
        ec_phone = _input("Emergency contact phone",
                            default=(existing.emergency_contact_phone
                                      if existing else "") or "")
        ec_rel = _input("Relationship to student",
                          default=(existing.emergency_contact_rel
                                    if existing else "") or "")
        last_rev = _input("Last reviewed (YYYY-MM-DD)",
                            default=(existing.last_reviewed
                                      if existing else "") or "")
        notes = _multiline("Notes",
                            default=(existing.notes if existing
                                      else "") or "")
        p = data.save_profile({
            "student_id": sid, "nhs_number": nhs,
            "blood_group": bg, "gp_name": gp_name,
            "gp_practice": gp_practice, "gp_phone": gp_phone,
            "emergency_contact_name": ec_name,
            "emergency_contact_phone": ec_phone,
            "emergency_contact_rel": ec_rel,
            "last_reviewed": last_rev, "notes": notes,
        })
        print(f"\n  ✓ Saved profile for {p.student_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("save_profile_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Condition flows ──────────────────────────────────────────────

def add_condition() -> None:
    print("\n═══ Add Condition ═══")
    try:
        sid = _pick_student()
        name = _input("Condition (e.g. Asthma, Type-1 diabetes)",
                        allow_empty=False)
        sev = _pick_from("Severity", list(CONDITION_SEVERITIES),
                           default=DEFAULT_CONDITION_SEVERITY)
        diag = _input("Diagnosed date (YYYY-MM-DD)")
        care_plan = _input("Care plan reference (optional)")
        active = _yes_no("Active?", default=True)
        notes = _multiline("Notes (optional)")
        c = data.create_condition({
            "student_id": sid, "name": name, "severity": sev,
            "diagnosed_date": diag, "care_plan_ref": care_plan,
            "active": active, "notes": notes,
        })
        print(f"\n  ✓ Added condition #{c.condition_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_condition failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_condition() -> None:
    print("\n═══ Edit Condition ═══")
    try:
        sid = _pick_student()
        conds = data.list_conditions(student_id=sid)
        if not conds:
            print("  (no conditions for this student)")
            _pause()
            return
        for i, c in enumerate(conds, 1):
            flag = " " if c.active else "i"
            print(f"   {flag}{i:>2}) #{c.condition_id:<3} "
                  f"{c.name[:32]:<32}  {c.severity}")
        idx = int(_input("Pick #", allow_empty=False)) - 1
        if idx < 0 or idx >= len(conds):
            print("  Out of range.")
            return
        c = conds[idx]
        name = _input("Condition", default=c.name, allow_empty=False)
        sev = _pick_from("Severity", list(CONDITION_SEVERITIES),
                           default=c.severity)
        diag = _input("Diagnosed date", default=c.diagnosed_date or "")
        care_plan = _input("Care plan reference",
                              default=c.care_plan_ref or "")
        active = _yes_no("Active?", default=c.active)
        notes = _multiline("Notes", default=c.notes or "")
        out = data.update_condition(c.condition_id, {
            "name": name, "severity": sev,
            "diagnosed_date": diag, "care_plan_ref": care_plan,
            "active": active, "notes": notes,
        })
        print(f"\n  ✓ Updated condition #{out.condition_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValueError:
        print("\n  ✗ Invalid selection.")
        _pause()
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_condition failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_condition_flow() -> None:
    print("\n═══ Delete Condition ═══")
    try:
        cid = int(_input("Condition id", allow_empty=False))
        if not data.get_condition(cid):
            print("  No such condition.")
            return
        if not _yes_no(f"Delete condition #{cid}?"):
            print("  (cancelled)")
            return
        data.delete_condition(cid)
        print(f"\n  ✓ Deleted condition #{cid}.")
        _pause()
    except _UserAbort:
        return
    except ValueError:
        print("\n  ✗ Condition id must be a number.")
        _pause()
    except Exception as e:
        logger.exception("delete_condition_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Medication flows ─────────────────────────────────────────────

def add_medication() -> None:
    print("\n═══ Add Medication ═══")
    try:
        sid = _pick_student()
        name = _input("Medication name", allow_empty=False)
        dose = _input("Dose (e.g. 100mg)")
        freq = _input("Frequency (e.g. Twice daily)")
        route = _pick_from("Route", list(MEDICATION_ROUTES),
                             default=DEFAULT_MEDICATION_ROUTE)
        start = _input("Start date (YYYY-MM-DD)")
        end = _input("End date (YYYY-MM-DD)")
        prescribed = _input("Prescribed by")
        emergency = _yes_no("Emergency medication?")
        notes = _multiline("Notes (optional)")
        m = data.create_medication({
            "student_id": sid, "name": name, "dose": dose,
            "frequency": freq, "route": route,
            "start_date": start, "end_date": end,
            "prescribed_by": prescribed,
            "is_emergency": emergency, "notes": notes,
        })
        print(f"\n  ✓ Added medication #{m.medication_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_medication failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_medication() -> None:
    print("\n═══ Edit Medication ═══")
    try:
        sid = _pick_student()
        meds = data.list_medications(student_id=sid)
        if not meds:
            print("  (no medications for this student)")
            _pause()
            return
        for i, m in enumerate(meds, 1):
            flag = "!" if m.is_emergency else " "
            print(f"   {flag}{i:>2}) #{m.medication_id:<3} "
                  f"{m.name[:24]:<24}  {m.dose or '—':<12}  "
                  f"{m.route}")
        idx = int(_input("Pick #", allow_empty=False)) - 1
        if idx < 0 or idx >= len(meds):
            print("  Out of range.")
            return
        m = meds[idx]
        name = _input("Name", default=m.name, allow_empty=False)
        dose = _input("Dose", default=m.dose or "")
        freq = _input("Frequency", default=m.frequency or "")
        route = _pick_from("Route", list(MEDICATION_ROUTES),
                             default=m.route)
        start = _input("Start date", default=m.start_date or "")
        end = _input("End date", default=m.end_date or "")
        prescribed = _input("Prescribed by",
                                default=m.prescribed_by or "")
        emergency = _yes_no("Emergency medication?",
                               default=m.is_emergency)
        notes = _multiline("Notes", default=m.notes or "")
        out = data.update_medication(m.medication_id, {
            "name": name, "dose": dose, "frequency": freq,
            "route": route, "start_date": start, "end_date": end,
            "prescribed_by": prescribed,
            "is_emergency": emergency, "notes": notes,
        })
        print(f"\n  ✓ Updated medication #{out.medication_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValueError:
        print("\n  ✗ Invalid selection.")
        _pause()
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_medication failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_medication_flow() -> None:
    print("\n═══ Delete Medication ═══")
    try:
        mid = int(_input("Medication id", allow_empty=False))
        if not data.get_medication(mid):
            print("  No such medication.")
            return
        if not _yes_no(f"Delete medication #{mid}?"):
            print("  (cancelled)")
            return
        data.delete_medication(mid)
        print(f"\n  ✓ Deleted medication #{mid}.")
        _pause()
    except _UserAbort:
        return
    except ValueError:
        print("\n  ✗ Medication id must be a number.")
        _pause()
    except Exception as e:
        logger.exception("delete_medication_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Allergy flows ────────────────────────────────────────────────

def add_allergy() -> None:
    print("\n═══ Add Allergy ═══")
    try:
        sid = _pick_student()
        allergen = _input("Allergen (e.g. Peanuts)", allow_empty=False)
        sev = _pick_from("Severity", list(ALLERGY_SEVERITIES),
                           default=DEFAULT_ALLERGY_SEVERITY)
        reaction = _input("Reaction (e.g. anaphylaxis)")
        epipen = _yes_no("EpiPen / adrenaline auto-injector held?")
        notes = _multiline("Notes (optional)")
        a = data.create_allergy({
            "student_id": sid, "allergen": allergen,
            "severity": sev, "reaction": reaction,
            "has_epipen": epipen, "notes": notes,
        })
        print(f"\n  ✓ Added allergy #{a.allergy_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("add_allergy failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def edit_allergy() -> None:
    print("\n═══ Edit Allergy ═══")
    try:
        sid = _pick_student()
        algs = data.list_allergies(student_id=sid)
        if not algs:
            print("  (no allergies for this student)")
            _pause()
            return
        for i, a in enumerate(algs, 1):
            flag = "!" if a.severity in ("Severe",
                                            "Life-threatening") else " "
            print(f"   {flag}{i:>2}) #{a.allergy_id:<3} "
                  f"{a.allergen[:24]:<24}  {a.severity}")
        idx = int(_input("Pick #", allow_empty=False)) - 1
        if idx < 0 or idx >= len(algs):
            print("  Out of range.")
            return
        a = algs[idx]
        allergen = _input("Allergen", default=a.allergen,
                            allow_empty=False)
        sev = _pick_from("Severity", list(ALLERGY_SEVERITIES),
                           default=a.severity)
        reaction = _input("Reaction", default=a.reaction or "")
        epipen = _yes_no("EpiPen held?", default=a.has_epipen)
        notes = _multiline("Notes", default=a.notes or "")
        out = data.update_allergy(a.allergy_id, {
            "allergen": allergen, "severity": sev,
            "reaction": reaction, "has_epipen": epipen,
            "notes": notes,
        })
        print(f"\n  ✓ Updated allergy #{out.allergy_id}.")
        _pause()
    except _UserAbort:
        print("\n  (cancelled)")
    except ValueError:
        print("\n  ✗ Invalid selection.")
        _pause()
    except ValidationError as e:
        print(f"\n  ✗ {e}")
        _pause()
    except Exception as e:
        logger.exception("edit_allergy failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def delete_allergy_flow() -> None:
    print("\n═══ Delete Allergy ═══")
    try:
        aid = int(_input("Allergy id", allow_empty=False))
        if not data.get_allergy(aid):
            print("  No such allergy.")
            return
        if not _yes_no(f"Delete allergy #{aid}?"):
            print("  (cancelled)")
            return
        data.delete_allergy(aid)
        print(f"\n  ✓ Deleted allergy #{aid}.")
        _pause()
    except _UserAbort:
        return
    except ValueError:
        print("\n  ✗ Allergy id must be a number.")
        _pause()
    except Exception as e:
        logger.exception("delete_allergy_flow failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── List / summary flows ─────────────────────────────────────────

def list_students() -> None:
    print("\n═══ All Students — Medical Overview ═══")
    try:
        _print_student_table(data.all_student_summaries())
        _pause()
    except Exception as e:
        logger.exception("list_students failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def list_flagged() -> None:
    print("\n═══ Students With Severe Flags ═══")
    try:
        rows = [s for s in data.all_student_summaries()
                 if s.severe_conditions or s.severe_allergies
                 or s.emergency_medications]
        _print_student_table(rows)
        _pause()
    except Exception as e:
        logger.exception("list_flagged failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def list_epipens() -> None:
    print("\n═══ EpiPen Holders ═══")
    try:
        rows = data.list_allergies(epipen_only=True)
        if not rows:
            print("  (none)")
        else:
            names = {s.student_id: s.full_name
                      for s in _students.list_students()}
            for a in rows:
                print(f"    #{a.allergy_id:<3}  "
                      f"{a.student_id:<12}  "
                      f"{names.get(a.student_id, '(unknown)')[:22]:<22}  "
                      f"{a.severity:<16}  "
                      f"{a.allergen[:24]:<24}")
        _pause()
    except Exception as e:
        logger.exception("list_epipens failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


def show_summary() -> None:
    print("\n═══ Medical Records Summary ═══")
    try:
        s = data.summary()
        print(f"\n  Profiles                 : {s.total_profiles}")
        print(f"  Conditions (total)       : {s.total_conditions}")
        print(f"  Severe active conditions : {s.severe_conditions}")
        print(f"  Medications (total)      : {s.total_medications}")
        print(f"  Emergency medications    : {s.emergency_medications}")
        print(f"  Allergies (total)        : {s.total_allergies}")
        print(f"  Severe / life-threat alg : {s.severe_allergies}")
        print(f"  Students with EpiPen     : {s.epipen_holders}")
        print(f"  Students flagged overall : {s.students_with_flag}")
        _pause()
    except Exception as e:
        logger.exception("show_summary failed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()


# ── Menu ─────────────────────────────────────────────────────────

_MENU: list[tuple[str, Callable[[], None]]] = [
    ("View student record",       view_student),
    ("Save/update profile",       save_profile_flow),
    ("Add condition",             add_condition),
    ("Edit condition",            edit_condition),
    ("Delete condition",          delete_condition_flow),
    ("Add medication",            add_medication),
    ("Edit medication",           edit_medication),
    ("Delete medication",         delete_medication_flow),
    ("Add allergy",               add_allergy),
    ("Edit allergy",              edit_allergy),
    ("Delete allergy",            delete_allergy_flow),
    ("All students — overview",   list_students),
    ("Flagged students",          list_flagged),
    ("EpiPen holders",            list_epipens),
    ("Summary report",            show_summary),
]


def run() -> None:
    while True:
        print("\n══════ Medical Records ══════")
        for i, (label, _fn) in enumerate(_MENU, 1):
            print(f"  {i:>2}) {label}")
        print("   0) Back")
        try:
            choice = input("  Select: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(_MENU)):
            print("  Invalid selection.")
            continue
        _label, fn = _MENU[int(choice) - 1]
        try:
            fn()
        except _UserAbort:
            print("\n  (cancelled)")
        except Exception as e:
            logger.exception("Medical records CLI flow crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Medical Records":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Medical records CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
