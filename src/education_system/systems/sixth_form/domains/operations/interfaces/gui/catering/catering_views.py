"""Tkinter views for Sixth Form Catering menus and allergens."""

from __future__ import annotations

import datetime as _dt
import logging
from education_system.platform.delivery.gui.parented_dialogs import messagebox, simpledialog

from education_system.systems.sixth_form.domains.operations.domain.catering import (
    catering as data,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    option_key,
    option_label,
)

logger = logging.getLogger(__name__)

_ITEM_TAGS = {"inactive": ("#eeeeee", "#444444")}
_MENU_TAGS = {"draft": ("#fff7e6", "#7a5800")}
_MATCH_TAGS = {
    "severe": ("#ffd1d1", "#8c0d0d"),
    "may":    ("#fff7e6", "#7a5800"),
}


def open_catering_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Catering")
    tabs: list = []

    def refresh_all(_tab=None) -> None:
        for t in tabs:
            t.refresh()

    item_fields = [
        Field("name", "Dish", required=True),
        Field("description", "Description"),
        Field("course", "Course", "combo", data.COURSES, required=True),
        Field("vegetarian", "Vegetarian", "check"),
        Field("vegan", "Vegan", "check"),
        Field("halal", "Halal", "check"),
        Field("gluten_free", "Gluten-free", "check"),
        Field("allergens", "Contains", "multi", data.ALLERGENS),
        Field("may_contain", "May contain (traces)", "multi",
              data.ALLERGENS),
        Field("active", "Active", "check"),
        Field("notes", "Notes", "text"),
    ]

    # ── Dishes ──
    def items_loader(f):
        free = [f["free_from"]] if f.get("free_from") else None
        return [(i.item_id,
                 (i.item_id, i.name, i.course, i.dietary_label,
                  ", ".join(i.allergens), ", ".join(i.may_contain),
                  "Yes" if i.active else "No"),
                 () if i.active else ("inactive",))
                for i in data.list_items(course=f.get("course"),
                                         name_like=f.get("name"),
                                         free_from=free,
                                         active_only=bool(f.get("active")))]

    def new_item(tab):
        v = form_dialog(win, "New dish", item_fields, {"active": True})
        if v:
            data.create_item(v)
            refresh_all()

    def edit_item(tab):
        iid = tab.selected()
        if not iid:
            return
        item = data.get_item(int(iid))
        v = form_dialog(win, f"Edit {item.name}", item_fields, vars(item))
        if v:
            data.update_item(item.item_id, v)
            refresh_all()

    def delete_item(tab):
        iid = tab.selected()
        if iid and messagebox.askyesno("Delete", "Delete this dish?",
                                       parent=win):
            data.delete_item(int(iid))
            refresh_all()

    tabs.append(TableTab(
        nb, "Dishes",
        [("id", "ID", 50), ("name", "Dish", 220), ("course", "Course", 110),
         ("diet", "Dietary", 90), ("contains", "Contains", 330),
         ("may", "May contain", 220), ("active", "Active", 60)],
        items_loader,
        filters=[Field("course", "Course", "combo", data.COURSES, width=14),
                 Field("name", "Name", width=14),
                 Field("free_from", "Free from", "combo", data.ALLERGENS,
                       width=22),
                 Field("active", "Active only", "check")],
        actions=[("New dish", new_item), ("Edit", edit_item),
                 ("Delete", delete_item)],
        on_double=edit_item, tag_colours=_ITEM_TAGS))

    # ── Menus ──
    def menus_loader(f):
        start = f.get("from") or _dt.date.today().isoformat()
        rows = []
        for m in data.list_menus(date_from=start, date_to=f.get("to"),
                                 service=f.get("service")):
            rows.append((m.menu_id,
                         (m.menu_id, m.menu_date,
                          _dt.date.fromisoformat(m.menu_date)
                          .strftime("%a"), m.service,
                          "Yes" if m.published else "Draft",
                          "; ".join(f"{i.name}"
                                    + (f" ({i.dietary_label})"
                                       if i.dietary_label else "")
                                    for i in m.items),
                          ", ".join(m.allergens), m.notes),
                         () if m.published else ("draft",)))
        return rows

    def _menu(tab):
        mid = tab.selected()
        return data.get_menu(int(mid)) if mid else None

    def new_menu(tab):
        v = form_dialog(win, "New menu", [
            Field("menu_date", "Date (YYYY-MM-DD)", required=True),
            Field("service", "Service", "combo", data.SERVICES,
                  required=True),
            Field("notes", "Notes", "text"),
        ], {"menu_date": _dt.date.today().isoformat(), "service": "Lunch"})
        if v:
            data.create_menu(v["menu_date"], v["service"], notes=v["notes"])
            refresh_all()

    def add_dish(tab):
        m = _menu(tab)
        if not m:
            return
        on = {i.item_id for i in m.items}
        options = [option_label(i.item_id, i.name)
                   for i in data.list_items(active_only=True)
                   if i.item_id not in on]
        if not options:
            messagebox.showinfo("Dishes", "No more active dishes to add.",
                                parent=win)
            return
        v = form_dialog(win, f"Add dish to {m.label}", [
            Field("item", "Dish", "combo", options, required=True,
                  width=44)])
        if v:
            data.add_item_to_menu(m.menu_id, int(option_key(v["item"])))
            refresh_all()

    def remove_dish(tab):
        m = _menu(tab)
        if not m or not m.items:
            return
        v = form_dialog(win, f"Remove dish from {m.label}", [
            Field("item", "Dish", "combo",
                  [option_label(i.item_id, i.name) for i in m.items],
                  required=True, width=44)])
        if v:
            data.remove_item_from_menu(m.menu_id,
                                       int(option_key(v["item"])))
            refresh_all()

    def publish(tab):
        m = _menu(tab)
        if m:
            data.publish_menu(m.menu_id, not m.published)
            refresh_all()

    def copy(tab):
        m = _menu(tab)
        if not m:
            return
        to = simpledialog.askstring("Copy menu", "Copy to date "
                                    "(YYYY-MM-DD):", parent=win)
        if to:
            data.copy_menu(m.menu_id, to.strip())
            refresh_all()

    def edit_notes(tab):
        m = _menu(tab)
        if not m:
            return
        v = form_dialog(win, f"Notes for {m.label}",
                        [Field("notes", "Notes", "text")], vars(m))
        if v is not None:
            data.update_menu(m.menu_id, notes=v["notes"])
            refresh_all()

    def delete_menu(tab):
        m = _menu(tab)
        if m and messagebox.askyesno("Delete", f"Delete {m.label} menu?",
                                     parent=win):
            data.delete_menu(m.menu_id)
            refresh_all()

    tabs.append(TableTab(
        nb, "Menus",
        [("id", "ID", 45), ("date", "Date", 90), ("dow", "Day", 45),
         ("svc", "Service", 80), ("pub", "Published", 75),
         ("items", "Dishes", 480), ("alg", "Allergens", 300),
         ("notes", "Notes", 150)],
        menus_loader,
        filters=[Field("from", "From (today)", width=11),
                 Field("to", "To", width=11),
                 Field("service", "Service", "combo", data.SERVICES,
                       width=10)],
        actions=[("New menu", new_menu), ("Add dish", add_dish),
                 ("Remove dish", remove_dish),
                 ("Publish / unpublish", publish), ("Copy to date", copy),
                 ("Notes", edit_notes), ("Delete", delete_menu)],
        tag_colours=_MENU_TAGS))

    # ── Allergen check (medical data: MEDICAL capability) ──
    def check_loader(f):
        day = f.get("date")
        if not day:
            return []
        rows = []
        for n, m in enumerate(data.allergen_check(day, f.get("service"))):
            tag = ("severe" if m.severity in ("Severe",
                                              "Life-threatening")
                   or m.has_epipen else "may" if m.may_contain_only else "")
            rows.append((n, (m.student_id, m.student_name, m.allergy,
                             m.severity, "Yes" if m.has_epipen else "",
                             m.menu_label, ", ".join(m.matched_allergens),
                             ", ".join(m.items),
                             "Trace only" if m.may_contain_only
                             else "Contains"),
                         (tag,) if tag else ()))
        return rows

    tabs.append(TableTab(
        nb, "Allergen Check",
        [("sid", "Student ID", 90), ("name", "Student", 160),
         ("allergy", "Recorded allergy", 150), ("sev", "Severity", 90),
         ("pen", "EpiPen", 60), ("menu", "Menu", 130),
         ("match", "Matched", 180), ("items", "Dishes", 300),
         ("kind", "Risk", 90)],
        check_loader,
        filters=[Field("date", "Menu date (YYYY-MM-DD)", width=11),
                 Field("service", "Service", "combo", data.SERVICES,
                       width=10)],
        actions=[], tag_colours=_MATCH_TAGS))

    def render():
        s = data.summary()
        lines = ["Catering summary", "",
                 f"  Dishes:            {s.items} ({s.active_items} active)",
                 f"  Vegetarian:        {s.vegetarian}",
                 f"  Vegan:             {s.vegan}",
                 f"  Halal:             {s.halal}",
                 f"  Gluten-free:       {s.gluten_free}", "",
                 f"  Menus on file:     {s.menus}",
                 f"  Next 7 days:       {s.menus_next_7_days} "
                 f"({s.unpublished_upcoming} not published)", "",
                 "  Active dishes by course:"]
        lines += [f"    {k:<16} {v}" for k, v in s.by_course.items() if v]
        lines += ["", "  Active dishes containing each allergen:"]
        lines += [f"    {k:<28} {v}" for k, v in s.by_allergen.items()]
        return lines

    tabs.append(SummaryTab(nb, render))
