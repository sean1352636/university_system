"""Console helpers shared by the Student Support CLI screens.

Every screen gathers its input first and then calls the support domain
(``student_support.service`` and friends), which checks permissions and
raises ``PermissionError`` / ``ValueError`` with text fit to show. ``call``
prints those messages and returns to the menu, so a refused action never
ends the loop. No SQL here: the screens only call the domain.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional

from education_system.systems.university.domains.student_support.domain.student_support import (
    auth as _auth,
    confidentiality as _tiers,
    routing,
    schema,
)

logger = logging.getLogger(__name__)

PER_PAGE = 20
FAILED = object()


class Leave(Exception):
    """The input ran out (Ctrl-D / end of a script): leave the menus."""


def _t(key: str, default: str, **kwargs: Any) -> str:
    """A translated string (``support_cli.<key>``), ``default`` when missing."""
    try:
        from education_system.systems.university.infrastructure.i18n import get_text
        text = get_text(f"support_cli.{key}", default=default)
    except Exception:
        text = default
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return default.format(**kwargs)


# ── input ────────────────────────────────────────────────────────────────


def ask(prompt: str, default: Optional[str] = None) -> str:
    """One line of input, stripped (``default`` when left empty)."""
    try:
        value = input(prompt).strip()
    except EOFError:
        raise Leave() from None
    return value if value or default is None else default


def ask_text(prompt: str) -> str:
    """Several lines, ended by an empty line."""
    print(prompt + " " + _t('finish_blank', "(finish with an empty line)"))
    lines = []
    while True:
        line = ask("")
        if not line:
            break
        lines.append(line)
    return "\n".join(lines)


def ask_yes(prompt: str, default: bool = False) -> bool:
    answer = ask(f"{prompt} ({'Y/n' if default else 'y/N'}): ").lower()
    if not answer:
        return default
    return answer in ('y', 'yes')


def ask_choice(prompt: str, options: list, label: Callable = str,
               default: Optional[int] = None, allow_none: bool = False):
    """Pick one of ``options`` by number; None when nothing valid is picked."""
    for i, option in enumerate(options, 1):
        print(f"  {i}. {label(option)}")
    hint = f" [{default}]" if default else ""
    raw = ask(f"{prompt}{hint}: ", str(default) if default else None)
    if not raw and allow_none:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    if raw:
        print(_t('invalid_choice', "Invalid choice."))
    return None


def ask_ticket_id(prompt: Optional[str] = None) -> Optional[int]:
    raw = ask(prompt or _t('ticket_number', "Ticket number: ")).lstrip('#')
    if not raw:
        return None
    if not raw.isdigit():
        print(_t('not_a_ticket', "'{value}' is not a ticket number.", value=raw))
        return None
    return int(raw)


def pause() -> None:
    ask(_t('press_enter', "\nPress Enter to continue..."))


# ── calling the domain ───────────────────────────────────────────────────


def call(fn: Callable, *args, **kwargs):
    """``fn(*args, **kwargs)``; on a refusal print its message and return
    :data:`FAILED` (never raises, so the menu loop carries on)."""
    try:
        return fn(*args, **kwargs)
    except Leave:
        raise
    except (PermissionError, ValueError) as exc:
        print(f"❌ {exc}")
    except FileNotFoundError as exc:
        print(f"❌ {exc}")
    except OSError as exc:
        print(f"❌ {_t('io_error', 'The file could not be read or written: {error}', error=exc)}")
    except Exception as exc:
        logger.exception("Student Support CLI action failed")
        print(f"❌ {_t('unexpected', 'Something went wrong: {error}', error=exc)}")
    return FAILED


def failed(result) -> bool:
    return result is FAILED


# ── who is signed in ─────────────────────────────────────────────────────


def actor():
    """The signed-in session the menus act as."""
    return _auth.get_auth_instance()


def user() -> dict:
    return _auth.user_of(actor()) or {}


def is_staff() -> bool:
    """Works tickets (support staff, admins, team members, the health team,
    safeguarding leads)."""
    return _auth.is_case_worker(actor())


def is_admin() -> bool:
    return _auth.is_admin(actor())


# ── showing things ───────────────────────────────────────────────────────


def status_text(status) -> str:
    return schema.status_label(status)


def tier_badge(tier) -> str:
    """'' for standard tickets, else the tier in brackets."""
    tier = _tiers.normalize_tier(tier)
    if tier == _tiers.STANDARD:
        return ''
    return f"[{_tiers.TIER_LABELS[tier].upper()}]"


def team_text(team) -> str:
    return routing.team_label(team) if team else '-'


def category_text(category) -> str:
    return routing.category_label(category) if category else '-'


def heading(title: str) -> None:
    print("\n" + title)
    print("=" * max(40, len(title)))


def show_crisis(support: Optional[dict]) -> None:
    """The crisis contacts, at once, when a result carries them."""
    if not support:
        return
    print("\n" + "!" * 60)
    print(_t('crisis_heading', "You do not have to deal with this alone."))
    for line in support.get('lines') or [support.get('message') or '']:
        print("  " + line)
    if support.get('safeguarding_reference'):
        print(_t('crisis_ref', "A member of the safeguarding team has been told "
                 "(reference {ref}).", ref=support['safeguarding_reference']))
    print("!" * 60)


def page_through(items: list, render: Callable[[Any], str], *, title: str,
                 per_page: int = PER_PAGE, pick: Optional[Callable[[Any], None]] = None,
                 key: Callable[[Any], Any] = lambda i: None) -> None:
    """Show ``items`` 20 to a page; ``pick`` opens the item whose ``key``
    the person types."""
    if not items:
        print(_t('nothing', "Nothing to show."))
        return
    pages = (len(items) + per_page - 1) // per_page
    page = 0
    while True:
        heading(f"{title} ({len(items)})")
        for item in items[page * per_page:(page + 1) * per_page]:
            print(render(item))
        prompt = _t('page_prompt', "Page {page}/{pages} - n next, p previous", page=page + 1,
                    pages=pages)
        if pick:
            prompt += _t('page_open', ", a number to open")
        choice = ask(prompt + _t('page_back', ", Enter to go back: ")).lower()
        if not choice:
            return
        if choice == 'n' and page + 1 < pages:
            page += 1
        elif choice == 'p' and page > 0:
            page -= 1
        elif pick and choice.lstrip('#').isdigit():
            wanted = int(choice.lstrip('#'))
            match = next((i for i in items if key(i) == wanted), None)
            if match is None:
                print(_t('not_listed', "That one is not in this list."))
            else:
                pick(match)


def service_pages(fetch: Callable[[int], dict], render: Callable[[dict], str], *, title: str,
                  pick: Optional[Callable[[dict], None]] = None) -> None:
    """Page through a service listing (``fetch(page)`` returns the
    ``{'tickets', 'total_count', 'total_pages'}`` of that page)."""
    page = 1
    while True:
        result = call(fetch, page)
        if failed(result):
            return
        tickets = result.get('tickets') or []
        total_pages = max(int(result.get('total_pages') or 1), 1)
        heading(f"{title} ({result.get('total_count', len(tickets))})")
        if not tickets:
            print(_t('no_tickets', "No tickets found."))
            return
        for t in tickets:
            print(render(t))
        prompt = _t('page_prompt', "Page {page}/{pages} - n next, p previous", page=page,
                    pages=total_pages)
        if pick:
            prompt += _t('page_open', ", a number to open")
        choice = ask(prompt + _t('page_back', ", Enter to go back: ")).lower()
        if not choice:
            return
        if choice == 'n' and page < total_pages:
            page += 1
        elif choice == 'p' and page > 1:
            page -= 1
        elif pick and choice.lstrip('#').isdigit():
            pick({'ticket_id': int(choice.lstrip('#'))})


def ticket_row(t: dict) -> str:
    """One line of a ticket list."""
    badge = tier_badge(t.get('confidentiality'))
    who = t.get('assigned_to') or _t('unassigned', 'unassigned')
    return (f"  #{t['ticket_id']:<6} {status_text(t.get('status')):<19} "
            f"{str(t.get('priority') or ''):<8} {team_text(t.get('team')):<22} "
            f"{who:<14} {badge} {str(t.get('subject') or '')[:48]}")


def numbers(raw: str) -> Iterable[int]:
    """Ticket numbers from '12, 15 #18'."""
    out = []
    for part in raw.replace(',', ' ').split():
        part = part.lstrip('#')
        if not part.isdigit():
            raise ValueError(f"'{part}' is not a ticket number")
        out.append(int(part))
    return out
