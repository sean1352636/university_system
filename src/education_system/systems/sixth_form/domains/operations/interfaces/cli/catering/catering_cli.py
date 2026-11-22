"""CLI flows for Sixth Form Catering menus and allergens."""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable

from education_system.systems.sixth_form.domains.operations.domain.catering import (
    catering as data,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    choose,
    choose_many,
    pause,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _pick_item(active_only: bool = False) -> int:
    q = ask("Dish name (blank = list all)")
    rows = data.list_items(name_like=q or None, active_only=active_only)
    label = choose("Dish", [f"{i.item_id} — {i.name}" for i in rows])
    if label is None:
        raise ValueError("No matching dishes")
    return int(label.split(" — ")[0])


def _pick_menu() -> int:
    start = ask("From date", default=_dt.date.today().isoformat())
    rows = data.list_menus(date_from=start)
    label = choose("Menu", [f"{m.menu_id} — {m.label}"
                            + ("" if m.published else " (draft)")
                            for m in rows])
    if label is None:
        raise ValueError("No menus from that date")
    return int(label.split(" — ")[0])


def _item_form(existing: data.MenuItem | None = None) -> dict:
    e = existing
    return {
        "name": ask("Dish", default=e.name if e else "", required=True),
        "description": ask("Description",
                           default=(e.description or "") if e else ""),
        "course": choose("Course", data.COURSES,
                         default=e.course if e else data.DEFAULT_COURSE),
        "vegetarian": yes_no("Vegetarian", default=bool(e and e.vegetarian)),
        "vegan": yes_no("Vegan", default=bool(e and e.vegan)),
        "halal": yes_no("Halal", default=bool(e and e.halal)),
        "gluten_free": yes_no("Gluten-free",
                              default=bool(e and e.gluten_free)),
        "allergens": choose_many("Contains", data.ALLERGENS,
                                 e.allergens if e else ()),
        "may_contain": choose_many("May contain (traces)", data.ALLERGENS,
                                   e.may_contain if e else ()),
        "notes": ask("Notes", default=(e.notes or "") if e else ""),
    }


# ── Dishes ──────────────────────────────────────────────────────────

def list_items() -> None:
    free = choose("Free from (blank = any)", data.ALLERGENS,
                  allow_blank=True)
    rows = data.list_items(free_from=[free] if free else None)
    table(["ID", "Dish", "Course", "Diet", "Contains", "May contain",
           "Active"],
          [(i.item_id, i.name, i.course, i.dietary_label,
            ", ".join(i.allergens), ", ".join(i.may_contain),
            "Y" if i.active else "N") for i in rows])
    pause()


def new_item() -> None:
    i = data.create_item(_item_form())
    print(f"\n  ✓ Created dish #{i.item_id} {i.name}")
    pause()


def edit_item() -> None:
    i = data.get_item(_pick_item())
    payload = _item_form(i)
    payload["active"] = yes_no("Active", default=i.active)
    out = data.update_item(i.item_id, payload)
    print(f"\n  ✓ Updated {out.name}")
    pause()


def delete_item() -> None:
    iid = _pick_item()
    if yes_no("Delete this dish?"):
        data.delete_item(iid)
        print("\n  ✓ Deleted")
    pause()


# ── Menus ───────────────────────────────────────────────────────────

def _print_menu(m: data.Menu) -> None:
    print(f"\n  {m.label}" + ("" if m.published else "  (draft)"))
    for i in m.items:
        diet = f" [{i.dietary_label}]" if i.dietary_label else ""
        alg = f"  — contains: {', '.join(i.allergens)}" if i.allergens \
            else ""
        print(f"    • {i.name}{diet}{alg}")
    if m.allergens:
        print(f"    Allergens on this menu: {', '.join(m.allergens)}")


def week_menus() -> None:
    start = ask("From date", default=_dt.date.today().isoformat())
    end = (_dt.date.fromisoformat(start)
           + _dt.timedelta(days=6)).isoformat()
    rows = data.list_menus(date_from=start, date_to=end)
    if not rows:
        print("\n  (no menus)")
    for m in rows:
        _print_menu(m)
    pause()


def new_menu() -> None:
    m = data.create_menu(
        ask("Date", default=_dt.date.today().isoformat()),
        choose("Service", data.SERVICES, default=data.DEFAULT_SERVICE),
        notes=ask("Notes"))
    print(f"\n  ✓ Created {m.label} menu")
    while yes_no("Add a dish?", default=True):
        m = data.add_item_to_menu(m.menu_id, _pick_item(active_only=True))
    _print_menu(m)
    pause()


def add_dish() -> None:
    mid = _pick_menu()
    m = data.add_item_to_menu(mid, _pick_item(active_only=True))
    _print_menu(m)
    pause()


def remove_dish() -> None:
    m = data.get_menu(_pick_menu())
    label = choose("Remove", [f"{i.item_id} — {i.name}" for i in m.items])
    if label:
        m = data.remove_item_from_menu(m.menu_id,
                                       int(label.split(" — ")[0]))
    _print_menu(m)
    pause()


def publish() -> None:
    m = data.get_menu(_pick_menu())
    out = data.publish_menu(m.menu_id, not m.published)
    print(f"\n  ✓ {out.label} {'published' if out.published else 'unpublished'}")
    pause()


def copy_menu() -> None:
    mid = _pick_menu()
    out = data.copy_menu(mid, ask("Copy to date", required=True))
    print(f"\n  ✓ Created {out.label}")
    pause()


def delete_menu() -> None:
    mid = _pick_menu()
    if yes_no("Delete this menu?"):
        data.delete_menu(mid)
        print("\n  ✓ Deleted")
    pause()


def allergen_check() -> None:
    day = ask("Menu date", default=_dt.date.today().isoformat())
    svc = choose("Service (blank = all)", data.SERVICES, allow_blank=True)
    rows = data.allergen_check(day, svc)
    table(["Student", "Name", "Allergy", "Severity", "EpiPen", "Menu",
           "Matched", "Dishes", "Risk"],
          [(m.student_id, m.student_name, m.allergy, m.severity,
            "Y" if m.has_epipen else "", m.menu_label,
            ", ".join(m.matched_allergens), ", ".join(m.items),
            "Trace" if m.may_contain_only else "Contains") for m in rows])
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n═══ Catering Summary ═══")
    print(f"  Dishes:        {s.items} ({s.active_items} active)")
    print(f"  Vegetarian {s.vegetarian} · Vegan {s.vegan} · Halal "
          f"{s.halal} · Gluten-free {s.gluten_free}")
    print(f"  Menus:         {s.menus}; next 7 days {s.menus_next_7_days} "
          f"({s.unpublished_upcoming} unpublished)")
    print("\n  Active dishes containing each allergen:")
    for k, v in s.by_allergen.items():
        print(f"    {k:<28} {v}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("Menus for a week",        week_menus),
    ("Allergen check (medical)", allergen_check),
    ("─" * 6,                   lambda: None),
    ("New menu",                new_menu),
    ("Add dish to menu",        add_dish),
    ("Remove dish from menu",   remove_dish),
    ("Publish / unpublish menu", publish),
    ("Copy menu to date",       copy_menu),
    ("Delete menu",             delete_menu),
    ("─" * 6,                   lambda: None),
    ("List dishes",             list_items),
    ("New dish",                new_item),
    ("Edit dish",               edit_item),
    ("Delete dish",             delete_item),
    ("─" * 6,                   lambda: None),
    ("Summary",                 summary_flow),
]


def run() -> None:
    run_menu("Catering", _MENU)


def catering_menu() -> None:
    """Entry point for the main CLI menu."""
    run()


def dispatch(label: str) -> bool:
    if label != "Catering":
        return False
    try:
        run()
    except Exception as e:
        logger.exception("Catering CLI submenu crashed")
        print(f"\n  ✗ Unexpected error: {e}")
        pause()
    return True
