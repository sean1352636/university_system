"""Building blocks shared by every Primary School screen.

The screens were written with a free-text box for every field - dates,
pupil ids, staff ids, year groups, times - so every form was a typing
exercise and a format error waiting to happen. These widgets replace those
boxes **in place**: each one takes the same ``textvariable`` (a
``tk.StringVar``) the old ``ttk.Entry`` used and keeps it holding exactly the
value the domain expects (``YYYY-MM-DD``, ``HH:MM``, a pupil id, "R"/"1".."6",
…), so a screen's save code does not change.

Pickers
    :class:`DateField`      day / month / year drop-downs (+ Today, Clear)
    :class:`TimeField`      hour / minute drop-downs
    :class:`ChoiceField`    a read-only drop-down of fixed values
    :class:`PupilPicker`    pupils by name (type to filter); holds the pupil id
    :class:`StaffPicker`    staff by name; holds the staff id (or the name)
    :class:`ClassPicker`    class names, optionally for one year group
    :class:`YearGroupPicker` Reception / Year 1 … Year 6; holds "R" / "1".."6"
    :class:`SubjectPicker`  subjects; holds the subject id (or code / name)
    :class:`AcademicYearPicker` "2026-27" style years
    :class:`NumberField`    a spinbox for whole numbers / amounts
    :class:`MultiPicker`    a list to tick several from

Layout (as the Secondary School screens)
    :func:`show_page`  draw a screen in the main window's content area, with
                       its heading and the "Open in new window" button
    :func:`page_heading` the bold title a page starts with
    :func:`close_page` what an old "Close" button does on a page
    :func:`tree`       a table with a scrollbar and row colour tags
    :func:`dialog`     a parented pop-up with a padded frame
    :func:`scrolled_form` a pop-up body that scrolls while its buttons stay put
    :func:`form_dialog` a whole pop-up form from a list of fields

Systems never import each other, so this mirrors (does not import) the
Secondary School's ``ui/gui/components/widgets.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable, Mapping, Sequence

from education_system.platform.delivery.gui.date_picker import (
    DatePicker,
    birth_years,
    recent_years,
)
from education_system.platform.delivery.gui.parented_dialogs import make_toplevel, messagebox

logger = logging.getLogger(__name__)

__all__ = [
    "AcademicYearPicker", "ChoiceField", "ClassPicker", "close_page", "DateField", "MultiPicker",
    "NumberField", "PupilPicker", "StaffPicker", "SubjectPicker", "TimeField",
    "YearGroupPicker", "academic_years", "birth_years", "dialog", "form_dialog",
    "page_heading", "pupil_birth_years", "recent_years", "scrolled_form", "show_page",
    "staff_birth_years", "tree", "STANDARD_TAGS",
]

YEAR_GROUP_LABELS: dict[str, str] = {
    "R": "Reception", "1": "Year 1", "2": "Year 2", "3": "Year 3",
    "4": "Year 4", "5": "Year 5", "6": "Year 6",
}


# ── Year ranges for date pickers ────────────────────────────────────

def pupil_birth_years() -> list[str]:
    """Birth years for a primary pupil (nursery-age to secondary transfer)."""
    return birth_years(youngest=2, oldest=13)


def staff_birth_years() -> list[str]:
    return birth_years(youngest=16, oldest=80)


def academic_years(*, back: int = 4, ahead: int = 1) -> list[str]:
    """"2026-27" style years around now (newest first), plus any the
    Academic Year screen holds."""
    today = _dt.date.today()
    start = today.year if today.month >= 9 else today.year - 1
    years = [f"{y}-{str(y + 1)[-2:]}" for y in range(start + ahead, start - back - 1, -1)]
    try:
        from education_system.systems.primary.domain.academics.academic_year import (
            academic_year as ay,
        )
        for y in ay.list_years():
            if y.name not in years:
                years.append(y.name)
    except Exception:  # noqa: BLE001 - extra years are a nicety
        logger.debug("academic years lookup failed", exc_info=True)
    return years


# ── Value-holding drop-downs ─────────────────────────────────────────

class _Bound(ttk.Frame):
    """A frame that keeps ``textvariable`` (the value the screen saves) in
    step with what is shown. Subclasses implement ``_show(value)`` and call
    ``_store(value)`` when the user picks something."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None,
                 **kw: Any) -> None:
        super().__init__(master, **kw)
        self.var = textvariable if textvariable is not None else tk.StringVar()
        self._syncing = False
        self._trace = self.var.trace_add("write", self._on_var)

    def _on_var(self, *_a: Any) -> None:
        if not self._syncing:
            self._syncing = True
            try:
                self._show(self.var.get())
            finally:
                self._syncing = False

    def _store(self, value: str) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            self.var.set(value)
        finally:
            self._syncing = False

    def _show(self, value: str) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str | None) -> None:
        self.var.set(value or "")

    def destroy(self) -> None:
        try:
            self.var.trace_remove("write", self._trace)
        except (tk.TclError, ValueError):
            pass
        super().destroy()


class DateField(_Bound):
    """Day / month / year drop-downs bound to a ``YYYY-MM-DD`` StringVar
    ("" when not set). *years* defaults to a window around now; pass
    :func:`pupil_birth_years` or :func:`staff_birth_years` for a date of
    birth. ``clear=False`` hides the Clear button for required dates."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 years: Sequence[str] | None = None, today: bool = True,
                 **kw: Any) -> None:
        super().__init__(master, textvariable, **kw)
        current = self.var.get().strip()
        yrs = list(years) if years is not None else recent_years(ahead=2, back=10)
        if current[:4].isdigit() and current[:4] not in yrs:
            yrs.append(current[:4])
            yrs.sort(reverse=True)
        self.picker = DatePicker(self, value=current or None, years=yrs)
        self.picker.pack(side="left")
        if not today:
            for child in self.picker.winfo_children():
                if isinstance(child, ttk.Button) and child.cget("text") == "Today":
                    child.destroy()
        for box in (self.picker.cb_day, self.picker.cb_month, self.picker.cb_year):
            box.bind("<<ComboboxSelected>>", lambda _e: self._picked(), add="+")
        for child in self.picker.winfo_children():
            if isinstance(child, ttk.Button):
                cmd = child.cget("command")
                child.configure(command=lambda c=cmd: (self.tk.call(c), self._picked()))

    def _picked(self) -> None:
        self._store(self.picker.get())

    def _show(self, value: str) -> None:
        value = (value or "").strip()
        if value:
            self.picker.set(value[:10])
        else:
            self.picker.clear()

    def state_disabled(self, disabled: bool = True) -> None:
        for box in (self.picker.cb_day, self.picker.cb_month, self.picker.cb_year):
            box.configure(state="disabled" if disabled else "readonly")


class TimeField(_Bound):
    """Hour / minute drop-downs bound to an ``HH:MM`` StringVar ("" = not set).
    *hours* defaults to 07–19 (a school day plus clubs); minutes step by
    *step* (5)."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 hours: Iterable[int] = range(7, 20), step: int = 5, **kw: Any) -> None:
        super().__init__(master, textvariable, **kw)
        hrs = [""] + [f"{h:02d}" for h in hours]
        mins = [""] + [f"{m:02d}" for m in range(0, 60, step)]
        self.cb_h = ttk.Combobox(self, values=hrs, width=4, state="readonly")
        self.cb_m = ttk.Combobox(self, values=mins, width=4, state="readonly")
        self.cb_h.pack(side="left")
        ttk.Label(self, text=":").pack(side="left")
        self.cb_m.pack(side="left")
        for box in (self.cb_h, self.cb_m):
            box.bind("<<ComboboxSelected>>", lambda _e: self._picked(), add="+")
        self._show(self.var.get())

    def _picked(self) -> None:
        h, m = self.cb_h.get(), self.cb_m.get()
        if h and not m:
            m = "00"
            self.cb_m.set(m)
        self._store(f"{h}:{m}" if h else "")

    def _show(self, value: str) -> None:
        value = (value or "").strip()
        if ":" in value:
            h, m = value.split(":", 1)
            h, m = h.zfill(2)[-2:], m[:2].zfill(2)
            for box, v in ((self.cb_h, h), (self.cb_m, m)):
                if v not in box.cget("values"):
                    box.configure(values=list(box.cget("values")) + [v])
                box.set(v)
        else:
            self.cb_h.set("")
            self.cb_m.set("")


class ChoiceField(_Bound):
    """A drop-down of *choices*: plain strings, or ``(value, label)`` pairs
    when what is shown differs from what is saved. ``blank=True`` offers an
    empty first entry ("any" in a filter, "not set" in a form); ``editable``
    lets the user type a value that is not in the list."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 choices: Iterable[Any] = (), blank: bool = False, editable: bool = False,
                 width: int = 28, on_change: Callable[[str], None] | None = None,
                 **kw: Any) -> None:
        super().__init__(master, textvariable, **kw)
        self._blank, self._editable, self._on_change = blank, editable, on_change
        self.box = ttk.Combobox(self, width=width,
                                state="normal" if editable else "readonly")
        self.box.pack(side="left", fill="x", expand=True)
        self.box.bind("<<ComboboxSelected>>", lambda _e: self._picked(), add="+")
        if editable:
            self.box.bind("<KeyRelease>", lambda _e: self._picked(), add="+")
            self.box.bind("<FocusOut>", lambda _e: self._picked(), add="+")
        self.set_choices(choices)

    def set_choices(self, choices: Iterable[Any]) -> None:
        pairs: list[tuple[str, str]] = []
        for c in choices:
            if isinstance(c, (tuple, list)) and len(c) == 2:
                pairs.append((str(c[0]), str(c[1])))
            else:
                pairs.append((str(c), str(c)))
        if self._blank:
            pairs.insert(0, ("", ""))
        self._by_label = {lbl: val for val, lbl in pairs}
        self._by_value = {val: lbl for val, lbl in pairs}
        self.box.configure(values=[lbl for _v, lbl in pairs])
        self._show(self.var.get())

    def _picked(self) -> None:
        shown = self.box.get()
        value = self._by_label.get(shown, shown if self._editable else "")
        self._store(value)
        if self._on_change:
            self._on_change(value)

    def _show(self, value: str) -> None:
        value = value or ""
        label = self._by_value.get(value)
        if label is None and value:
            # A stored value the list no longer offers (an old record): keep it
            # visible and selectable rather than silently blanking it.
            label = value
            self._by_label[label] = value
            self._by_value[value] = label
            self.box.configure(values=list(self.box.cget("values")) + [label])
        self.box.set(label or "")

    def bind_change(self, fn: Callable[[str], None]) -> None:
        self._on_change = fn


class _SearchPicker(ChoiceField):
    """A ChoiceField you can type into to narrow the list; only a listed
    entry is accepted (typed text that matches nothing leaves the value
    blank)."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 choices: Iterable[Any] = (), blank: bool = True, width: int = 36,
                 allow_other: bool = False, **kw: Any) -> None:
        super().__init__(master, textvariable, choices=choices, blank=blank,
                         editable=False, width=width, **kw)
        self._allow_other = allow_other
        self.box.configure(state="normal")
        self._all = list(self.box.cget("values"))
        self.box.bind("<KeyRelease>", self._filter, add="+")
        self.box.bind("<FocusOut>", lambda _e: self._commit(), add="+")
        self.box.bind("<Return>", lambda _e: self._commit(), add="+")

    def set_choices(self, choices: Iterable[Any]) -> None:
        super().set_choices(choices)
        self._all = list(self.box.cget("values"))

    def _filter(self, event: tk.Event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        q = self.box.get().strip().lower()
        self.box.configure(values=[v for v in self._all if q in v.lower()] if q else self._all)

    def _commit(self) -> None:
        shown = self.box.get()
        if shown in self._by_label:
            self._picked()
            return
        q = shown.strip().lower()
        hits = [v for v in self._all if q and q in v.lower()]
        if len(hits) == 1:
            self.box.set(hits[0])
            self._picked()
        elif not q:
            self._store("")
        elif self._allow_other:
            self._store(shown.strip())  # a name not on the list (e.g. "Headteacher")
        else:
            self._show(self.var.get())  # put back the last valid choice
        self.box.configure(values=self._all)


def _pupil_choices(year_group: str | None = None, include_off_roll: bool = False
                   ) -> list[tuple[str, str]]:
    try:
        from education_system.systems.primary.domain.learners.pupils import pupils
        rows = pupils.list_pupils(include_off_roll=include_off_roll)
    except Exception:  # noqa: BLE001 - an empty list beats a broken form
        logger.exception("pupil list for picker failed")
        return []
    if year_group:
        rows = [p for p in rows if p.year_group == year_group]
    rows.sort(key=lambda p: (p.last_name.lower(), p.first_name.lower()))
    out = []
    for p in rows:
        year = YEAR_GROUP_LABELS.get(p.year_group, p.year_group)
        cls = f" {p.class_name}" if getattr(p, "class_name", None) else ""
        out.append((p.pupil_id, f"{p.last_name}, {p.first_name} ({p.pupil_id}) · {year}{cls}"))
    return out


class PupilPicker(_SearchPicker):
    """Pupils on roll by name (type part of a name or id to narrow the
    list). Holds the pupil id. *year_group* limits the list."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 year_group: str | None = None, include_off_roll: bool = False,
                 blank: bool = True, width: int = 44, **kw: Any) -> None:
        super().__init__(master, textvariable,
                         choices=_pupil_choices(year_group, include_off_roll),
                         blank=blank, width=width, **kw)


def _staff_choices(*, by: str, active_only: bool, role: str | None,
                   dsl_only: bool) -> list[tuple[str, str]]:
    try:
        from education_system.systems.primary.domain.staff import staff
        rows = staff.list_staff(active_only=active_only, role=role,
                                is_dsl=True if dsl_only else None)
    except Exception:  # noqa: BLE001
        logger.exception("staff list for picker failed")
        return []
    rows.sort(key=lambda s: (s.last_name.lower(), s.first_name.lower()))
    out = []
    for s in rows:
        value = s.staff_id if by == "id" else s.full_name
        role_txt = f" · {s.role}" if getattr(s, "role", None) else ""
        out.append((value, f"{s.full_name} ({s.staff_id}){role_txt}"))
    return out


class StaffPicker(_SearchPicker):
    """Staff by name. Holds the staff id, or the full name with
    ``by="name"`` (for fields that store a name, e.g. "recorded by").
    A ``by="name"`` field also accepts a typed name that is not on the staff
    list (a role such as "Headteacher", or an outside person), as the old
    typed box did; pass ``allow_other=False`` to refuse that."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 by: str = "id", active_only: bool = True, role: str | None = None,
                 dsl_only: bool = False, blank: bool = True, width: int = 40,
                 allow_other: bool | None = None, **kw: Any) -> None:
        if allow_other is None:
            allow_other = by == "name"
        super().__init__(master, textvariable, allow_other=allow_other,
                         choices=_staff_choices(by=by, active_only=active_only, role=role,
                                                dsl_only=dsl_only),
                         blank=blank, width=width, **kw)


def _class_choices(year_group: str | None) -> list[str]:
    try:
        from education_system.systems.primary.domain.academics.classes import classes
        rows = classes.list_all(year_group=year_group) if year_group else classes.list_all()
    except Exception:  # noqa: BLE001
        logger.exception("class list for picker failed")
        return []
    return sorted({c.name for c in rows if getattr(c, "is_active", True)})


class ClassPicker(ChoiceField):
    """Class names (e.g. "3A"). Editable by default so a class not yet set
    up in Classes can still be entered."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 year_group: str | None = None, blank: bool = True, editable: bool = True,
                 width: int = 12, **kw: Any) -> None:
        super().__init__(master, textvariable, choices=_class_choices(year_group),
                         blank=blank, editable=editable, width=width, **kw)

    def for_year(self, year_group: str | None) -> None:
        self.set_choices(_class_choices(year_group))


class YearGroupPicker(ChoiceField):
    """Reception / Year 1 … Year 6, holding "R" / "1".."6". Use
    ``labels=True`` for fields that store the label itself ("Year 3")."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 blank: bool = False, labels: bool = False, extra: Iterable[str] = (),
                 width: int = 12, **kw: Any) -> None:
        if labels:
            choices: list[Any] = [*extra, *YEAR_GROUP_LABELS.values()]
        else:
            choices = [*((e, e) for e in extra), *YEAR_GROUP_LABELS.items()]
        super().__init__(master, textvariable, choices=choices, blank=blank, width=width,
                         **kw)


def _subject_choices(by: str) -> list[tuple[str, str]]:
    try:
        from education_system.systems.primary.domain.academics.subjects import subjects
        rows = subjects.list_all()
    except Exception:  # noqa: BLE001
        logger.exception("subject list for picker failed")
        return []
    out = []
    for s in rows:
        value = {"id": str(s.subject_id), "code": s.code, "name": s.name}[by]
        out.append((value, f"{s.name} ({s.code})"))
    return out


class SubjectPicker(ChoiceField):
    """Subjects; holds the subject id (``by="code"`` or ``"name"`` for
    fields that store those)."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 by: str = "id", blank: bool = True, width: int = 30, **kw: Any) -> None:
        super().__init__(master, textvariable, choices=_subject_choices(by), blank=blank,
                         width=width, **kw)


class AcademicYearPicker(ChoiceField):
    """"2026-27" style academic years (editable for an older year)."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 blank: bool = False, width: int = 10, **kw: Any) -> None:
        super().__init__(master, textvariable, choices=academic_years(), blank=blank,
                         editable=True, width=width, **kw)
        if not self.var.get() and not blank:
            values = self.box.cget("values")
            current = academic_years(back=0, ahead=0)
            if current:
                self.set(current[0])
            elif values:
                self.set(values[0])


class NumberField(ttk.Spinbox):
    """A spinbox bound to a StringVar: whole numbers by default,
    ``increment=0.01`` for money. Typing is still allowed."""

    def __init__(self, master: tk.Misc, textvariable: tk.StringVar | None = None, *,
                 from_: float = 0, to: float = 9999, increment: float = 1,
                 width: int = 8, **kw: Any) -> None:
        fmt = "%.2f" if increment < 1 else "%.0f"
        super().__init__(master, textvariable=textvariable, from_=from_, to=to,
                         increment=increment, width=width, format=fmt, **kw)


class MultiPicker(ttk.Frame):
    """A list to tick several from. *choices* are ``(value, label)``;
    :meth:`get` gives the chosen values."""

    def __init__(self, master: tk.Misc, choices: Iterable[tuple[str, str]], *,
                 selected: Iterable[str] = (), height: int = 8, width: int = 44,
                 **kw: Any) -> None:
        super().__init__(master, **kw)
        self._values = []
        self.box = tk.Listbox(self, selectmode="multiple", height=height, width=width,
                              exportselection=False)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.box.yview)
        self.box.configure(yscrollcommand=sb.set)
        chosen = set(selected)
        for i, (value, label) in enumerate(choices):
            self._values.append(value)
            self.box.insert("end", label)
            if value in chosen:
                self.box.selection_set(i)
        self.box.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def get(self) -> list[str]:
        return [self._values[i] for i in self.box.curselection()]


# ── Layout ───────────────────────────────────────────────────────────

STANDARD_TAGS: dict[str, dict[str, str]] = {
    "good": {"background": "#e7f6ea"},
    "bad": {"background": "#fde2e2"},
    "warn": {"background": "#fff4d6"},
    "muted": {"foreground": "#777"},
}


def page_heading(parent: tk.Misc, title: str, subtitle: str | None = None) -> ttk.Frame:
    """The bold heading a page starts with (as the Secondary School pages)."""
    head = ttk.Frame(parent)
    head.pack(fill="x", pady=(0, 8))
    ttk.Label(head, text=title, font=("", 16, "bold")).pack(anchor="w")
    if subtitle:
        ttk.Label(head, text=subtitle, foreground="#666", wraplength=900,
                  justify="left").pack(anchor="w", pady=(2, 0))
    return head


def show_page(host: Any, title: str, draw: Callable[[ttk.Frame], None]) -> None:
    """Show a screen in the main window's content area (with the "Open in
    new window" button), or - when *host* is not the main window (a pop-out,
    a test double) - in a window of its own. *draw(parent)* builds the
    screen into *parent*, so the same function serves both."""
    shower = getattr(host, "show_page", None)
    if callable(shower):
        shower(title, draw)
        return
    root = getattr(host, "root", host)
    win = make_toplevel(root)
    win.title(title)
    frame = ttk.Frame(win, padding=10)
    frame.pack(fill="both", expand=True)
    draw(frame)


def close_page(host: Any, parent: tk.Misc) -> None:
    """What a page's old "Close" button now does: back to the dashboard in
    the main window, or close the window when the page was popped out."""
    top = parent.winfo_toplevel()
    root = getattr(host, "root", None)
    if root is not None and top is root and callable(getattr(host, "_show_welcome", None)):
        host._show_welcome()
    else:
        top.destroy()


def tree(parent: tk.Misc, columns: Iterable[tuple[str, str, int]], *, height: int = 12,
         select: str = "browse", stretch: Iterable[str] = (),
         tags: Mapping[str, str | Mapping[str, str]] | None = None) -> ttk.Treeview:
    """A headings-only table packed into *parent* with a vertical scrollbar.
    *columns* are ``(key, heading, width)``."""
    columns = list(columns)
    wide = set(stretch)
    frame = ttk.Frame(parent)
    frame.pack(fill="both", expand=True)
    t = ttk.Treeview(frame, columns=[c for c, _h, _w in columns], show="headings",
                     selectmode=select, height=height)
    for col, heading, width in columns:
        t.heading(col, text=heading)
        t.column(col, width=width, anchor="w", stretch=col in wide)
    sb = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sb.set)
    t.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    for tag, style in {**STANDARD_TAGS, **(tags or {})}.items():
        if isinstance(style, str):
            t.tag_configure(tag, background=style)
        else:
            t.tag_configure(tag, **style)
    return t


def dialog(owner: tk.Misc, title: str, *, size: str | None = None,
           padding: int = 12) -> tuple[tk.Toplevel, ttk.Frame]:
    """A pop-up over *owner*'s window: ``(window, padded frame)``."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(title)
    if size:
        win.geometry(size)
    frm = ttk.Frame(win, padding=padding)
    frm.pack(fill="both", expand=True)
    return win, frm


def scrolled_form(win: tk.Toplevel, padding: int = 12) -> tuple[ttk.Frame, ttk.Frame]:
    """``(body, footer)`` packed into *win*: fields go in *body*, which
    scrolls on a small screen; buttons go in *footer*, which stays visible."""
    footer = ttk.Frame(win, padding=(padding, 6, padding, padding))
    footer.pack(side="bottom", fill="x")
    ttk.Separator(win, orient="horizontal").pack(side="bottom", fill="x")
    holder = ttk.Frame(win)
    holder.pack(side="top", fill="both", expand=True)
    canvas = tk.Canvas(holder, highlightthickness=0, borderwidth=0)
    bar = ttk.Scrollbar(holder, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = ttk.Frame(canvas, padding=padding)
    item = canvas.create_window(0, 0, window=body, anchor="nw")
    body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>",
                lambda e: canvas.itemconfigure(item, width=max(e.width, body.winfo_reqwidth())))

    def wheel(e: tk.Event) -> str | None:
        if isinstance(e.widget, (tk.Text, tk.Listbox)):
            return None
        if body.winfo_reqheight() <= canvas.winfo_height():
            return None
        canvas.yview_scroll(-1 if (getattr(e, "num", None) == 4
                                   or getattr(e, "delta", 0) > 0) else 1, "units")
        return "break"

    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        win.bind(seq, wheel, add="+")
    return body, footer


def form_dialog(owner: tk.Misc, title: str, fields: list[tuple[str, str, Any, Any]],
                on_save: Callable[[dict[str, Any]], None], note: str | None = None, *,
                errors: tuple[type[BaseException], ...] = (ValueError,)) -> tk.Toplevel:
    """A pop-up form. Each field is ``(key, label, initial, kind)``; *kind*:

    * ``None`` - one-line entry;  ``"text"`` - several lines;  ``"check"``;
    * ``"date"`` / ``"dob"`` (pupil) / ``"staff_dob"`` - date drop-downs;
    * ``"time"``;  ``"pupil"``;  ``"staff"`` (id) / ``"staff_name"``;
    * ``"class"``;  ``"year_group"``;  ``"subject"``;  ``"academic_year"``;
    * ``"number"`` / ``"money"``;
    * a list - a read-only drop-down;  ``("edit", list)`` - one you can type in;
    * ``("multi", [(value, label)])`` - tick several (gives a list).

    Save calls ``on_save({key: value})``; if it raises one of *errors* the
    message is shown and the form stays open."""
    win = make_toplevel(owner.winfo_toplevel())
    win.title(title)
    body, footer = scrolled_form(win)
    if note:
        ttk.Label(body, text=note, foreground="#555", wraplength=460, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
    getters: dict[str, Callable[[], Any]] = {}
    for i, (key, label, initial, kind) in enumerate(fields, start=1):
        ttk.Label(body, text=label).grid(row=i, column=0, sticky="nw", padx=(0, 8), pady=3)
        init = "" if initial is None else str(initial)
        var = tk.StringVar(value=init)
        widget: tk.Misc
        if kind == "text":
            t = tk.Text(body, width=50, height=3, wrap="word")
            t.insert("1.0", init)
            widget = t
            getters[key] = lambda t=t: t.get("1.0", "end").strip()
        elif kind == "check":
            bv = tk.BooleanVar(value=bool(initial))
            widget = ttk.Checkbutton(body, variable=bv)
            getters[key] = bv.get
        elif isinstance(kind, tuple) and kind and kind[0] == "multi":
            widget = MultiPicker(body, kind[1], selected=initial or ())
            getters[key] = widget.get
        else:
            simple: dict[str, Callable[[], tk.Misc]] = {
                "date": lambda: DateField(body, var),
                "dob": lambda: DateField(body, var, years=pupil_birth_years(), today=False),
                "staff_dob": lambda: DateField(body, var, years=staff_birth_years(),
                                               today=False),
                "time": lambda: TimeField(body, var),
                "pupil": lambda: PupilPicker(body, var),
                "staff": lambda: StaffPicker(body, var),
                "staff_name": lambda: StaffPicker(body, var, by="name"),
                "class": lambda: ClassPicker(body, var),
                "year_group": lambda: YearGroupPicker(body, var),
                "subject": lambda: SubjectPicker(body, var),
                "academic_year": lambda: AcademicYearPicker(body, var),
                "number": lambda: NumberField(body, var),
                "money": lambda: NumberField(body, var, increment=0.01, to=99999),
            }
            if isinstance(kind, str) and kind in simple:
                widget = simple[kind]()
            elif isinstance(kind, tuple) and kind and kind[0] == "edit":
                widget = ChoiceField(body, var, choices=kind[1], editable=True, width=40)
            elif kind:
                widget = ChoiceField(body, var, choices=kind)
            else:
                widget = ttk.Entry(body, textvariable=var, width=42)
            getters[key] = var.get
        widget.grid(row=i, column=1, sticky="w", pady=3)

    def save() -> None:
        try:
            on_save({k: g() for k, g in getters.items()})
        except errors as e:
            messagebox.showerror(title, str(e), parent=win)
            return
        win.destroy()

    ttk.Button(footer, text="Cancel", command=win.destroy).pack(side="right", padx=(6, 0))
    ttk.Button(footer, text="Save", command=save).pack(side="right")
    return win
