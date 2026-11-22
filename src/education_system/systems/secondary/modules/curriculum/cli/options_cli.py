"""Year 9 options in the terminal. The old options 1-8 are kept (new round,
view / edit round, manage round subjects, submit pupil choices, view pupil
choices, submission summary, set round status, delete round); 9-17 are added.
Rules live in :mod:`modules.curriculum.domain.options`."""

from __future__ import annotations

from education_system.systems.secondary.modules.curriculum.domain import options as OP
from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.cli.prompts import prompts
from education_system.systems.secondary.ui.cli.prompts.prompts import ask as _ask
from education_system.systems.secondary.ui.cli.prompts.prompts import pause as _pause
from education_system.systems.secondary.ui.cli.prompts.prompts import prompt as _prompt
from education_system.systems.secondary.ui.cli.prompts.prompts import yes as _yes

_ERRORS = (OP.ValidationError, OP.PermissionDenied, OP.NotFound)


_problem = prompts.problem


def _print_rounds(rows: list[OP.Round]) -> None:
    if not rows:
        print("  (no rounds)")
        return
    print(f"  {'ID':<4} {'Name':<32} {'Year':<5} {'Status':<10} {'Opens':<11} {'Closes':<11} "
          "Picks")
    for r in rows:
        print(f"  {r.round_id:<4} {r.name[:32]:<32} {r.year_group:<5} {r.status:<10} "
              f"{(r.opens_on or ''):<11} {(r.closes_on or ''):<11} "
              f"{r.choices_required}+{r.reserves_required}")


def _choose() -> OP.Round | None:
    raw = _prompt("  Round ID: ")
    if not raw.isdigit():
        return None
    try:
        return OP.get_round(int(raw))
    except OP.NotFound:
        print("  No such round.")
        return None


def _pupil(r: OP.Round) -> P.Pupil | None:
    ref = _prompt("  Pupil (admission no, UPN or part of the name): ").lower()
    if not ref:
        return None
    exact = P.find_by_reference(ref)
    if exact:
        return exact
    hits = [p for p in OP.cohort(r.round_id) if ref in p.full_name.lower()
            or ref in p.display_name.lower()]
    if not hits:
        print(f"  Nobody like that in Year {r.year_group}.")
        return None
    if len(hits) > 1:
        for i, p in enumerate(hits[:20], 1):
            print(f"   {i}) {p.display_name} ({p.admission_no})")
        n = _prompt("  Which? ")
        return hits[int(n) - 1] if n.isdigit() and 0 < int(n) <= len(hits[:20]) else None
    return hits[0]


def _codes(r: OP.Round, text: str) -> list[int]:
    offered = {s.code.lower(): s.subject_id for s in OP.list_round_subjects(r.round_id)}
    out = []
    for code in text.replace(",", " ").split():
        if code.lower() not in offered:
            raise OP.ValidationError([f"{code} isn't offered in this round"])
        out.append(offered[code.lower()])
    return out


def menu(principal: Principal) -> None:
    while True:
        activity_log.record("options.view")
        print("\n── Year 9 Options ──")
        _print_rounds(OP.list_rounds())
        print("\n   1) New round\n   2) View / edit round\n   3) Manage round subjects"
              "\n   4) Submit pupil choices\n   5) View pupil choices"
              "\n   6) Submission summary\n   7) Set round status\n   8) Delete round"
              "\n   9) Rules on choices\n  10) Who hasn't chosen (and remind families)"
              "\n  11) Option blocks\n  12) Allocate subjects\n  13) Place a pupil by hand"
              "\n  14) E-mail results to families\n  15) Create Year 10 groups"
              "\n  16) Export choices (CSV)\n  17) History\n   0) Back")
        choice = _prompt("Select: ")
        if choice in {"0", ""}:
            return
        try:
            {"1": lambda: _new(principal), "2": lambda: _view_edit(principal),
             "3": lambda: _subjects(principal), "4": lambda: _submit(principal),
             "5": _view_choices, "6": _summary, "7": lambda: _status(principal),
             "8": lambda: _delete(principal), "9": lambda: _rules(principal),
             "10": lambda: _not_chosen(principal), "11": lambda: _blocks(principal),
             "12": lambda: _allocate(principal), "13": lambda: _place(principal),
             "14": lambda: _results(principal), "15": lambda: _groups(principal),
             "16": lambda: _export(principal), "17": _history,
             }.get(choice, lambda: print("  Invalid selection."))()
        except _ERRORS as e:
            _problem(e)


def _collect(r: OP.Round | None) -> dict:
    data: dict = {}
    for key, label, hint in (("name", "Name", ""), ("year_group", "Year group choosing", "7-10"),
                             ("opens_on", "Opens on", "YYYY-MM-DD"),
                             ("closes_on", "Closes on", "YYYY-MM-DD"),
                             ("choices_required", "Choices", ""),
                             ("reserves_required", "Reserves", ""),
                             ("blocks", "Option blocks", "blank = one per choice"),
                             ("class_size", "Class size", ""), ("notes", "Notes", "")):
        current = getattr(r, key) if r else {"year_group": 9, "choices_required": 4,
                                              "reserves_required": 1,
                                              "class_size": OP.DEFAULT_CLASS_SIZE}.get(key)
        v = _ask(label, None if current is None else str(current), hint=hint,
                 required=key == "name" and r is None)
        if v is not None:
            data[key] = v
        elif r is None and current is not None:
            data[key] = current
    return data


def _new(principal: Principal) -> None:
    print("\n  ── New options round ── (- clears a field)")
    r = OP.create_round(_collect(None), actor=principal)
    print(f"  ✓ Round #{r.round_id} '{r.name}' (Draft) - add subjects next")


def _view_edit(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    s = OP.summary(r.round_id)
    print(f"\n  {r.name} - Year {r.year_group} choosing for Year {r.next_year} - {r.status}")
    print(f"  Opens {r.opens_on or '-'}  Closes {r.closes_on or '-'}  ·  {r.choices_required} "
          f"choices + {r.reserves_required} reserve(s)  ·  {r.blocks} blocks, classes of "
          f"{r.class_size}")
    print(f"  Subjects: {', '.join(x['code'] for x in s['subject_picks']) or 'none'}")
    print(f"  Rules: {'; '.join(x.label for x in OP.list_rules(r.round_id)) or 'none'}")
    print(f"  Chosen: {s['pupils_submitted']} of {s['cohort']}")
    if r.notes:
        print(f"  Notes: {r.notes}")
    if _yes("  Edit it?"):
        print("  Press Enter to keep a value, - to clear it.")
        r = OP.update_round(r.round_id, _collect(r), actor=principal)
        print(f"  ✓ Updated '{r.name}'")


def _subjects(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    while True:
        current = OP.list_round_subjects(r.round_id)
        print(f"\n  ── Subjects in round '{r.name}' ──")
        if not current:
            print("  (none assigned yet)")
        for s in current:
            print(f"  #{s.subject_id:<4} {s.code:<8} {s.name}"
                  + (f"  [{s.ebacc_category}]" if s.ebacc_category else ""))
        print("\n   1) Add subject (from catalogue)\n   2) Remove subject\n   0) Back")
        choice = _prompt("  Select: ")
        if choice in {"0", ""}:
            return
        try:
            if choice == "1":
                for s in OP.available_subjects(r.round_id):
                    print(f"    {s.code:<8} {s.name}")
                code = _prompt("  Subject code: ")
                hit = next((s for s in OP.available_subjects(r.round_id)
                            if s.code.lower() == code.lower()), None)
                if hit is None:
                    print("  Not one of those.")
                    continue
                OP.add_round_subject(r.round_id, hit.subject_id, actor=principal)
                print(f"  ✓ Added {hit.code}")
            elif choice == "2":
                code = _prompt("  Subject code to remove: ")
                hit = next((s for s in current if s.code.lower() == code.lower()), None)
                if hit:
                    OP.remove_round_subject(r.round_id, hit.subject_id, actor=principal)
                    print(f"  ✓ Removed {hit.code}")
        except _ERRORS as e:
            _problem(e)


def _submit(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    p = _pupil(r)
    if not p:
        return
    x = OP.get_choices(r.round_id, p.pupil_id)
    if x:
        print(f"  Now: {x.label}")
    print("  Offered: " + ", ".join(s.code for s in OP.list_round_subjects(r.round_id)))
    for rule in OP.list_rules(r.round_id):
        print(f"  Rule: {rule.label}")
    choices = _codes(r, _prompt(f"  {r.choices_required} choices in order (codes): "))
    reserves = (_codes(r, _prompt(f"  {r.reserves_required} reserve(s) (codes): "))
                if r.reserves_required else [])
    if OP.rule_problems(r.round_id, choices) and OP.is_editor(principal):
        reason = _prompt("  These break a rule - accept them because (Enter = don't): ")
    else:
        reason = None
    x = OP.submit_choices(r.round_id, p.pupil_id, choices, reserves, actor=principal,
                          override_reason=reason or None,
                          notes=_prompt("  Notes (optional): ") or None)
    print(f"  ✓ {p.display_name}: {x.label}")


def _view_choices() -> None:
    r = _choose()
    if not r:
        return
    rows = OP.list_choices(r.round_id)
    if not rows:
        print("  (nobody has chosen yet)")
    for x in rows:
        flag = "  * accepted against the rules" if x.override_reason else ""
        print(f"  {x.pupil_name[:24]:<24} {x.admission_no:<10} {x.label}{flag}")
    _pause()


def _summary() -> None:
    r = _choose()
    if not r:
        return
    s = OP.summary(r.round_id)
    print(f"\n  Pupils submitted: {s['pupils_submitted']} of {s['cohort']}   Complete: "
          f"{s['pupils_complete']}   Partial: {s['pupils_partial']}")
    print(f"  {'Code':<8} {'Name':<24} {'Primary':<8} {'1st':<5} {'Reserve':<8} "
          f"{'Classes':<8} Places")
    for x in s["subject_picks"]:
        print(f"  {x['code']:<8} {x['name'][:24]:<24} {x['primary']:<8} {x['first']:<5} "
              f"{x['reserve']:<8} {x['groups']:<8} {'' if x['places'] is None else x['places']}")
    _pause()


def _status(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    print(f"  Now: {r.status}.  Draft -> Open -> Closed -> Finalised")
    new = _prompt(f"  New status ({'/'.join(OP.STATUSES)}): ")
    if new:
        r = OP.set_status(r.round_id, new, actor=principal)
        print(f"  ✓ '{r.name}' is {r.status}")


def _delete(principal: Principal) -> None:
    r = _choose()
    if r and _yes(f"  Delete '{r.name}' with its subjects and every pupil's choices?"):
        OP.delete_round(r.round_id, actor=principal)
        print("  ✓ Deleted")


def _rules(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    rules = OP.list_rules(r.round_id)
    for i, rule in enumerate(rules, 1):
        print(f"   {i}) {rule.label}")
    if not rules:
        print("  (no rules)")
    what = _prompt("  a = add a rule, r = remove one, Enter = back: ").lower()
    if what == "a":
        print(f"  Categories: {', '.join(S.EBACC_CATEGORIES)}")
        rule = OP.add_rule(r.round_id, _prompt("  From (e.g. Humanities, Languages): "),
                           _prompt("  At least how many? [1]: ") or 1, actor=principal)
        print(f"  ✓ {rule.label}")
    elif what == "r":
        n = _prompt("  Which number? ")
        if n.isdigit() and 0 < int(n) <= len(rules):
            OP.remove_rule(rules[int(n) - 1].rule_id, actor=principal)
            print("  ✓ Removed")


def _not_chosen(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    missing = OP.not_submitted(r.round_id)
    print(f"\n  {len(missing)} pupil(s) haven't chosen:")
    for p in missing:
        print(f"   {p.display_name:<26} {p.admission_no:<10} {p.form_group or ''}")
    if missing and OP.is_editor(principal) and _yes("\n  E-mail their families a reminder?"):
        result = OP.remind_families(r.round_id, actor=principal)
        from education_system.systems.secondary.modules.communication.domain import (
            email_outbox as E,
        )
        report = E.deliver(result.message_id, principal=principal)
        print(f"  ✓ E-mail to {result.recipients} contact(s) ({report.mode}): "
              + ", ".join(f"{k} {v}" for k, v in report.counts.items() if v))
        if result.pupils_without_email:
            print("  No e-mail address for: "
                  + ", ".join(p.display_name for p in result.pupils_without_email))


def _print_blocks(r: OP.Round) -> None:
    st = OP.allocation_status(r.round_id)
    for b in r.block_names:
        here = [c for c in st["classes"] if c["block"] == b]
        print(f"  Block {b}: " + (", ".join(f"{c['code']} {c['pupils']}/{c['capacity']}"
                                            for c in here) or "(empty)"))


def _blocks(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    _print_blocks(r)
    what = _prompt("\n  s = use suggested blocks, e = enter blocks, Enter = back: ").lower()
    if what == "s":
        plan = OP.suggest_blocks(r.round_id)
        for b, items in plan.items():
            print(f"  Block {b}: " + ", ".join(f"{S.get(sid).code} ({size})"
                                               for sid, size in items))
        if _yes("  Save these blocks?"):
            OP.set_blocks(r.round_id, plan, actor=principal)
            print("  ✓ Saved - run Allocate next")
    elif what == "e":
        print("  For each block enter subject codes, with a class size after a colon if not "
              f"{r.class_size} (e.g. HIST GEOG:24 ART).")
        plan: dict[str, list[tuple[int, int | None]]] = {}
        for b in r.block_names:
            items = []
            for part in _prompt(f"  Block {b}: ").split():
                code, _, size = part.partition(":")
                (sid,) = _codes(r, code)
                items.append((sid, int(size) if size.isdigit() else None))
            plan[b] = items
        OP.set_blocks(r.round_id, plan, actor=principal)
        print("  ✓ Saved - run Allocate next")


def _allocate(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    rep = OP.allocate(r.round_id, actor=principal)
    print(f"  ✓ {rep['placed']} placed, {rep['manual']} kept as placed by hand, "
          f"{rep['reserves_used']} reserve(s) used")
    for u in rep["unresolved"]:
        print(f"   • {u['name']}: {u['why']}")
    _print_blocks(r)


def _place(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    p = _pupil(r)
    if not p:
        return
    x = OP.get_choices(r.round_id, p.pupil_id)
    if x is None:
        print("  They haven't chosen.")
        return
    print(f"  Chose: {x.label}")
    _print_blocks(r)
    placements = {}
    for b in r.block_names:
        code = _prompt(f"  Block {b} subject code (Enter = none): ")
        if code:
            (placements[b],) = _codes(r, code)
    _a, warnings = OP.place_by_hand(r.round_id, p.pupil_id, placements, actor=principal)
    print(f"  ✓ Placed {p.display_name}")
    for w in warnings:
        print(f"  ! {w}")


def _results(principal: Principal) -> None:
    r = _choose()
    if not r or not _yes("  E-mail every family their child's subjects?"):
        return
    ids, no_email = OP.email_results(r.round_id, actor=principal)
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    for mid in ids:
        E.deliver(mid, principal=principal)
    print(f"  ✓ {len(ids)} e-mail(s) sent to the outbox ({E.delivery_mode()})")
    if no_email:
        print(f"  No e-mail address for: {', '.join(no_email)}")


def _groups(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    rep = OP.create_groups(r.round_id, actor=principal)
    print(f"  ✓ Created {len(rep['created'])} group(s)"
          + (f": {', '.join(rep['created'])}" if rep["created"] else "")
          + f"; {rep['added']} pupil place(s) added")
    for code, adm, why in rep["refused"]:
        print(f"   • {code}: {adm} - {why}")


def _export(principal: Principal) -> None:
    r = _choose()
    if not r:
        return
    path = _prompt(f"  Save to [options-{r.round_id}.csv]: ") or f"options-{r.round_id}.csv"
    try:
        n = OP.export_choices(r.round_id, path, actor=principal)
    except OSError as e:
        print(f"  Couldn't save: {e}")
        return
    print(f"  ✓ Saved {n} pupil(s) to {path}")


def _history() -> None:
    r = _choose()
    if not r:
        return
    for h in OP.history(r.round_id):
        print(f"  {h['at']}  {h['actor']:<12} {h['action']:<16} "
              + ", ".join(f"{k}={v}" for k, v in h["detail"].items()))
    _pause()
