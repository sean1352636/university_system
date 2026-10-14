"""CLI flows for Sixth Form Surveys."""

from __future__ import annotations

import logging
from datetime import date as _date
from typing import Any, Callable
from education_system.systems.sixth_form.domain.pastoral.surveys import (
    surveys as data,
)
from education_system.systems.sixth_form.domain.pastoral.surveys.surveys import (
    AUDIENCES,
    DEFAULT_AUDIENCE,
    DEFAULT_STATUS,
    QUESTION_TYPES,
    Question,
    Response,
    STATUSES,
    Survey,
    ValidationError,
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
            return _input(prompt, default=default,
                            allow_empty=False)
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
                default: str | None = None) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        marker = " *" if opt == default else "  "
        print(f"    {marker}{i:>2}) {opt or '(none)'}")
    while True:
        raw = _input(f"  Pick #1..{len(options)}",
                      default=default or "")
        if default and raw == default:
            return default
        if not raw.isdigit():
            print("    Enter a number.")
            continue
        n = int(raw)
        if not (1 <= n <= len(options)):
            print("    Out of range.")
            continue
        return options[n - 1]


def _pick_survey() -> Survey:
    rows = data.list_surveys()
    if not rows:
        print("    No surveys yet.")
        raise _UserAbort
    print("\n  Surveys:")
    for i, s in enumerate(rows, 1):
        rc = data.response_count(s.survey_id)
        print(f"    {i:>3}) #{s.survey_id}  {s.name[:36]:<36}  "
              f"{s.audience[:14]:<14}  "
              f"[{s.status}]  {rc} response(s)")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.survey_id == n), None)
            if match:
                return match
        print("    No matching survey.")


def _pick_response(survey_id: int) -> Response:
    rows = data.list_responses(survey_id)
    if not rows:
        print("    No responses yet.")
        raise _UserAbort
    print("\n  Responses:")
    for i, r in enumerate(rows, 1):
        name = (r.respondent_name
                  if r.respondent_name else "anonymous")
        print(f"    {i:>3}) #{r.response_id}  "
              f"{r.submitted_on}  {name}")
    while True:
        raw = _input(f"  Pick #1..{len(rows)} (or id)",
                      allow_empty=False)
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(rows):
                return rows[n - 1]
            match = next((r for r in rows
                            if r.response_id == n), None)
            if match:
                return match
        print("    No matching response.")


# ── Print helpers ─────────────────────────────────────────────

def _print_table(rows: list[Survey]) -> None:
    if not rows:
        print("\n  (none)")
        return
    print()
    print(f"  {'#':>4}  {'Name':<32}  {'Audience':<16}  "
          f"{'Status':<10}  Open       Close      "
          f"Qs  Resp")
    print("  " + "-" * 110)
    for s in rows:
        rc = data.response_count(s.survey_id)
        print(f"  {s.survey_id:>4}  {s.name[:32]:<32}  "
              f"{s.audience[:16]:<16}  "
              f"{s.status:<10}  "
              f"{(s.open_on or '—'):<10}  "
              f"{(s.close_on or '—'):<10}  "
              f"{len(s.questions):>2}  {rc:>4}")
    print(f"\n  {len(rows)} survey(s).")


def _print_full(s: Survey) -> None:
    print()
    print(f"    #{s.survey_id}  {s.name}")
    print(f"    Audience       : {s.audience}")
    print(f"    Status         : {s.status}")
    print(f"    Anonymous      : "
          f"{'yes' if s.anonymous else 'no'}")
    print(f"    Open / close   : "
          f"{s.open_on or '—'}  →  {s.close_on or '—'}")
    print(f"    Created by     : {s.created_by or '—'}")
    print(f"    Responses      : "
          f"{data.response_count(s.survey_id)}")
    if s.description:
        print()
        print("    Description:")
        for line in s.description.splitlines():
            print(f"      {line}")
    print()
    print("    Questions:")
    for i, q in enumerate(s.questions, 1):
        marker = "*" if q.required else " "
        print(f"      {i:>2}.{marker} [{q.type}] {q.prompt}")
        if q.choices:
            for c in q.choices:
                print(f"           - {c}")
    if s.notes:
        print()
        print("    Notes:")
        for line in s.notes.splitlines():
            print(f"      {line}")


def _print_response(s: Survey, r: Response) -> None:
    name = (r.respondent_name
              if r.respondent_name else "anonymous")
    print(f"\n    Response #{r.response_id}  "
          f"{r.submitted_on}  by {name}")
    if r.respondent_role:
        print(f"    Role: {r.respondent_role}")
    for idx, q in enumerate(s.questions):
        v = r.answers.get(idx)
        if v is None:
            display = "(skipped)"
        elif isinstance(v, list):
            display = ", ".join(str(x) for x in v)
        else:
            display = str(v)
        print(f"      {idx+1}. {q.prompt}")
        print(f"         → {display}")
    if r.notes:
        print(f"    Notes: {r.notes}")


# ── Question editor (within survey form) ──────────────────────

def _collect_question(existing: Question | None = None) -> Question:
    prompt = _input(
        "Prompt",
        default=(existing.prompt if existing else ""),
        allow_empty=False)
    qtype = _pick_from(
        "Type", list(QUESTION_TYPES),
        default=(existing.type if existing else "Text"))
    choices: list[str] = []
    if qtype in ("Single Choice", "Multi Choice"):
        print("\n  Enter choices one per line "
              "(end with '.'):")
        if existing:
            for c in existing.choices:
                print(f"    | {c}")
        try:
            while True:
                ln = input("  > ").strip()
                if ln == ".":
                    break
                if ln:
                    choices.append(ln)
        except (EOFError, KeyboardInterrupt):
            print()
            raise _UserAbort
        if not choices and existing:
            choices = list(existing.choices)
    required = _yes_no(
        "Required?",
        default=(existing.required if existing else False))
    return Question(prompt=prompt, type=qtype,
                       choices=choices, required=required)


def _edit_questions(
        existing: list[Question] | None = None) -> list[Question]:
    qs: list[Question] = list(existing or [])
    while True:
        print("\n  Current questions:")
        if not qs:
            print("    (none)")
        for i, q in enumerate(qs, 1):
            mark = "*" if q.required else " "
            print(f"    {i:>2}.{mark} [{q.type}] {q.prompt}")
        print("\n  Actions: a=add  e=edit  d=delete  "
              "m=move  q=done")
        try:
            choice = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            raise _UserAbort
        if choice in ("q", ""):
            break
        if choice == "a":
            try:
                qs.append(_collect_question())
            except _UserAbort:
                continue
        elif choice == "e":
            idx_raw = _input("  Edit #")
            if not idx_raw.isdigit():
                continue
            idx = int(idx_raw) - 1
            if not (0 <= idx < len(qs)):
                continue
            try:
                qs[idx] = _collect_question(qs[idx])
            except _UserAbort:
                continue
        elif choice == "d":
            idx_raw = _input("  Delete #")
            if not idx_raw.isdigit():
                continue
            idx = int(idx_raw) - 1
            if 0 <= idx < len(qs):
                del qs[idx]
        elif choice == "m":
            src_raw = _input("  Move # from")
            dst_raw = _input("  To #")
            if (src_raw.isdigit() and dst_raw.isdigit()):
                src = int(src_raw) - 1
                dst = int(dst_raw) - 1
                if (0 <= src < len(qs) and 0 <= dst < len(qs)):
                    qs.insert(dst, qs.pop(src))
    return qs


# ── Survey flows ─────────────────────────────────────────────

def list_all() -> None:
    print("\n═══ All Surveys ═══")
    _print_table(data.list_surveys())
    _pause()


def list_open() -> None:
    print("\n═══ Open Surveys ═══")
    _print_table(data.list_surveys(open_only=True))
    _pause()


def filter_flow() -> None:
    print("\n═══ Filter ═══")
    try:
        aud = _input(
            f"Audience ({'/'.join(AUDIENCES[:2])}…)") or None
        status = _input(f"Status ({'/'.join(STATUSES)})") or None
        name = _input("Name contains") or None
        creator = _input("Created by contains") or None
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_surveys(
        audience=aud, status=status,
        name_like=name, created_by_like=creator)
    _print_table(rows)
    _pause()


def view_flow() -> None:
    print("\n═══ View Survey ═══")
    try:
        s = _pick_survey()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_full(s)
    _pause()


def _collect_survey_form(
        existing: Survey | None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    is_edit = existing is not None
    payload["name"] = _input(
        "Name",
        default=(existing.name if is_edit else ""),
        allow_empty=False)
    payload["audience"] = _pick_from(
        "Audience", list(AUDIENCES),
        default=(existing.audience if is_edit
                  else DEFAULT_AUDIENCE))
    payload["anonymous"] = _yes_no(
        "Anonymous responses?",
        default=(existing.anonymous if is_edit else True))
    payload["open_on"] = _input(
        "Open on (YYYY-MM-DD)",
        default=(existing.open_on or "") if is_edit else "")
    payload["close_on"] = _input(
        "Close on (YYYY-MM-DD)",
        default=(existing.close_on or "") if is_edit else "")
    payload["created_by"] = _input(
        "Created by",
        default=(existing.created_by or "")
        if is_edit else "")
    payload["status"] = _pick_from(
        "Status", list(STATUSES),
        default=(existing.status if is_edit else DEFAULT_STATUS))
    try:
        payload["description"] = _multiline(
            "Description",
            default=(existing.description or "")
            if is_edit else "")
        payload["notes"] = _multiline(
            "Notes",
            default=(existing.notes or "")
            if is_edit else "")
    except _UserAbort:
        raise
    locked = is_edit and not existing.is_editable
    if locked:
        print("\n  Survey is past Draft — questions are locked.")
        payload["questions"] = existing.questions
    else:
        print("\n  ── Edit questions ──")
        payload["questions"] = _edit_questions(
            existing.questions if is_edit else None)
    return payload


def new_survey() -> None:
    print("\n═══ New Survey ═══")
    try:
        payload = _collect_survey_form(None)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        s = data.create_survey(payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Created survey #{s.survey_id}")
    _pause()


def edit_survey() -> None:
    print("\n═══ Edit Survey ═══")
    try:
        s = _pick_survey()
        payload = _collect_survey_form(s)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.update_survey(s.survey_id, payload)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Updated #{s.survey_id}")
    _pause()


def publish_flow() -> None:
    print("\n═══ Publish ═══")
    try:
        s = _pick_survey()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.publish(s.survey_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{s.survey_id} → Open")
    _pause()


def close_flow() -> None:
    print("\n═══ Close ═══")
    try:
        s = _pick_survey()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.close_survey(s.survey_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{s.survey_id} → Closed")
    _pause()


def archive_flow() -> None:
    print("\n═══ Archive ═══")
    try:
        s = _pick_survey()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.archive(s.survey_id)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{s.survey_id} → Archived")
    _pause()


def set_status_flow() -> None:
    print("\n═══ Change Status ═══")
    try:
        s = _pick_survey()
        new_status = _pick_from("New status", list(STATUSES),
                                  default=s.status)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        data.set_status(s.survey_id, new_status)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ #{s.survey_id} → {new_status}")
    _pause()


def delete_survey_flow() -> None:
    print("\n═══ Delete Survey ═══")
    try:
        s = _pick_survey()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(
            f"Delete survey #{s.survey_id} and all responses? "
            "Type 'yes'",
            default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_survey(s.survey_id):
        print(f"\n  ✓ Deleted #{s.survey_id}")
    _pause()


# ── Response flows ────────────────────────────────────────────

def _collect_answers(s: Survey) -> dict[int, Any]:
    answers: dict[int, Any] = {}
    for idx, q in enumerate(s.questions):
        marker = " (required)" if q.required else ""
        print(f"\n  Q{idx+1}{marker} [{q.type}]: {q.prompt}")
        if q.choices:
            for i, c in enumerate(q.choices, 1):
                print(f"      {i}) {c}")
        if q.type == "Multi Choice":
            print("  (enter numbers comma-separated, "
                  "or blank to skip)")
            raw = _input("Answer")
            if raw:
                picks: list[str] = []
                for tok in raw.split(","):
                    tok = tok.strip()
                    if tok.isdigit():
                        n = int(tok)
                        if 1 <= n <= len(q.choices):
                            picks.append(q.choices[n - 1])
                    elif tok in q.choices:
                        picks.append(tok)
                if picks:
                    answers[idx] = picks
        elif q.type == "Single Choice":
            raw = _input("Answer (number)")
            if raw.isdigit():
                n = int(raw)
                if 1 <= n <= len(q.choices):
                    answers[idx] = q.choices[n - 1]
            elif raw in q.choices:
                answers[idx] = raw
        elif q.type == "Likert":
            raw = _input("Answer (1-5)")
            if raw:
                answers[idx] = raw
        elif q.type == "Yes/No":
            raw = _input("Answer (Yes/No)")
            if raw:
                answers[idx] = raw
        elif q.type == "Number":
            raw = _input("Answer (number)")
            if raw:
                answers[idx] = raw
        else:  # Text
            raw = _input("Answer")
            if raw:
                answers[idx] = raw
    return answers


def submit_response_flow() -> None:
    print("\n═══ Submit Response ═══")
    try:
        s = _pick_survey()
        if s.status != "Open":
            print(f"  Survey is {s.status}, not Open.")
            _pause()
            return
        anon = (True if s.anonymous
                  else _yes_no("Anonymous?", default=False))
        name = ""
        role = ""
        if not anon:
            name = _input("Respondent name", allow_empty=False)
            role = _input("Respondent role")
        answers = _collect_answers(s)
        notes = _multiline("Notes")
    except _UserAbort:
        print("\n  Cancelled.")
        return
    try:
        r = data.submit_response(
            s.survey_id, answers=answers,
            respondent_name=name or None,
            respondent_role=role or None,
            anonymous=anon, notes=notes or None)
    except ValidationError as exc:
        print(f"\n  ✗ {exc}")
        _pause()
        return
    print(f"\n  ✓ Submitted response #{r.response_id}")
    _pause()


def list_responses_flow() -> None:
    print("\n═══ List Responses ═══")
    try:
        s = _pick_survey()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    rows = data.list_responses(s.survey_id)
    print(f"\n  {len(rows)} response(s) for "
          f"{s.name!r}:")
    for r in rows:
        name = r.respondent_name or "anonymous"
        print(f"    #{r.response_id}  {r.submitted_on}  {name}")
    _pause()


def view_response_flow() -> None:
    print("\n═══ View Response ═══")
    try:
        s = _pick_survey()
        r = _pick_response(s.survey_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    _print_response(s, r)
    _pause()


def delete_response_flow() -> None:
    print("\n═══ Delete Response ═══")
    try:
        s = _pick_survey()
        r = _pick_response(s.survey_id)
    except _UserAbort:
        print("\n  Cancelled.")
        return
    if _input(f"Delete response #{r.response_id}? Type 'yes'",
              default="no").lower() != "yes":
        print("\n  Cancelled.")
        return
    if data.delete_response(r.response_id):
        print(f"\n  ✓ Deleted #{r.response_id}")
    _pause()


def stats_flow() -> None:
    print("\n═══ Question Statistics ═══")
    try:
        s = _pick_survey()
    except _UserAbort:
        print("\n  Cancelled.")
        return
    stats = data.question_stats(s.survey_id)
    print(f"\n  Survey: {s.name!r}  "
          f"({data.response_count(s.survey_id)} responses)\n")
    for st in stats:
        print(f"  Q{st.index+1}. [{st.type}] {st.prompt}")
        print(f"      answered: {st.answered}  "
              f"skipped: {st.skipped}")
        if st.mean is not None:
            print(f"      mean: {st.mean}")
        if st.counts:
            print("      counts:")
            for k, v in sorted(st.counts.items(),
                                  key=lambda kv: -kv[1]):
                print(f"        {k:<24} : {v}")
        if st.text_samples:
            print("      samples:")
            for sample in st.text_samples:
                print(f"        - {sample[:60]}")
        print()
    _pause()


def summary_flow() -> None:
    print("\n═══ Surveys Summary ═══")
    s = data.summary()
    print(f"\n  Total surveys       : {s.total}")
    print(f"  Drafts              : {s.drafts}")
    print(f"  Open                : {s.open_count}")
    print(f"  Closed              : {s.closed}")
    print(f"  Archived            : {s.archived}")
    print(f"  Total responses     : {s.total_responses}")
    print("\n  By audience:")
    for k in AUDIENCES:
        n = s.by_audience.get(k, 0)
        if n:
            print(f"    {k:<22}: {n}")
    print("\n  By status:")
    for k in STATUSES:
        n = s.by_status.get(k, 0)
        if n:
            print(f"    {k:<14}: {n}")
    _pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List all",         list_all),
    ("List open",        list_open),
    ("Filter",           filter_flow),
    ("View",             view_flow),
    ("─" * 6,            lambda: None),
    ("New survey",       new_survey),
    ("Edit survey",      edit_survey),
    ("Publish",          publish_flow),
    ("Close",            close_flow),
    ("Archive",          archive_flow),
    ("Change status",    set_status_flow),
    ("Delete survey",    delete_survey_flow),
    ("─" * 6,            lambda: None),
    ("Submit response",  submit_response_flow),
    ("List responses",   list_responses_flow),
    ("View response",    view_response_flow),
    ("Delete response",  delete_response_flow),
    ("─" * 6,            lambda: None),
    ("Question stats",   stats_flow),
    ("Summary",          summary_flow),
]


def run() -> None:
    while True:
        print("\n── Surveys ──")
        for i, (label, _) in enumerate(_MENU, 1):
            if label.startswith("─"):
                print(f"      {label * 3}")
            else:
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
        label, handler = _MENU[int(choice) - 1]
        if label.startswith("─"):
            continue
        try:
            handler()
        except _UserAbort:
            print("\n  Cancelled.")
        except Exception as e:
            logger.exception("Surveys CLI crashed")
            print(f"\n  ✗ Unexpected error: {e}")
            _pause()


def dispatch(label: str) -> bool:
    if label != "Surveys":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Surveys CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        _pause()
    return True
