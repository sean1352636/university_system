"""Tkinter window: online learning space (class resources)."""

from __future__ import annotations

import logging
import webbrowser
from pathlib import Path
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox

from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as _cg,
)
from education_system.systems.sixth_form.domain.academics.class_resources import (
    class_resources as data,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as _courses,
)
from education_system.systems.sixth_form.interfaces.gui.operations._ops_ui import (
    Field,
    SummaryTab,
    TableTab,
    form_dialog,
    make_window,
    option_key,
    option_label,
    student_options,
)

logger = logging.getLogger(__name__)

_TAGS = {
    "draft": ("#fff7e6", "#7a5800"),
    "task": ("#e6f0ff", "#1a3f8c"),
    "problem": ("#ffd1d1", "#8c0d0d"),
}


def group_options() -> list[str]:
    codes = {c.course_id: c.course_code for c in _courses.list_courses()}
    return [option_label(g.group_id,
                         f"{codes.get(g.course_id, g.course_id)} "
                         f"{g.group_name}")
            for g in _cg.list_groups()]


def course_options() -> list[str]:
    return [option_label(c.course_id, f"{c.course_code} {c.title}")
            for c in _courses.list_courses()]


def _size(n: int | None) -> str:
    if not n:
        return ""
    return f"{n / 1024:.0f} KB" if n < 1048576 else f"{n / 1048576:.1f} MB"


def _open_target(win, kind: str, where: str) -> None:
    if kind == "file":
        webbrowser.open(Path(where).as_uri())
    elif kind == "url":
        webbrowser.open(where)
    else:
        messagebox.showinfo("Linked task", f"This item points at {where}. "
                            "Open it from Homework & Coursework.",
                            parent=win)


def open_class_resources_window(parent=None) -> None:
    data.init_db()
    win, nb = make_window(parent, "Online Learning Space")
    tabs: list = []

    def refresh_all(_tab=None) -> None:
        for t in tabs:
            t.refresh()

    groups = group_options()
    course_list = course_options()

    def _row(r, *, problem: bool = False):
        task = data.task_info(r.task_kind, r.task_id) if r.task_id else None
        detail = (f"{task.title} (due {task.due_date or '—'})" if task
                  else r.task_ref and f"{r.task_ref} (missing)"
                  or r.url or "")
        tag = ("problem" if problem else "draft" if not r.published
               else "task" if r.kind == data.ONLINE_TASK else "")
        return (r.resource_id,
                (r.resource_id, r.scope_label, r.week or "", r.topic,
                 r.kind, r.title, r.file_name or "", _size(r.file_size),
                 detail, "Yes" if r.published else "No",
                 r.available_from or ""),
                (tag,) if tag else ())

    cols = [("id", "ID", 45), ("scope", "Group / course", 150),
            ("week", "Wk", 40), ("topic", "Topic", 120), ("kind", "Type", 105),
            ("title", "Title", 220), ("file", "File", 150),
            ("size", "Size", 65), ("link", "Link / task", 230),
            ("pub", "Published", 70), ("from", "Available from", 100)]

    def resources_loader(f):
        pub = f.get("published")
        rows = data.list_resources(
            group_id=int(option_key(f["group"])) if f.get("group") else None,
            course_id=(int(option_key(f["course"]))
                       if f.get("course") and not f.get("group") else None),
            kind=f.get("kind"),
            published=None if not pub else pub == "Published",
            search=f.get("search"))
        return [_row(r) for r in rows]

    common = [
        Field("title", "Title", required=True, width=44),
        Field("description", "Description", "text"),
        Field("week", "Teaching week (1-52)"),
        Field("topic", "Topic"),
        Field("sort_order", "Order within week"),
        Field("available_from", "Available from (YYYY-MM-DD)"),
    ]
    scope_fields = [
        Field("group", "Class group (blank = whole course)", "combo",
              [""] + groups, width=40),
        Field("course", "Course (for whole-course items)", "combo",
              [""] + course_list, width=40),
    ]

    def _scope(v: dict) -> None:
        g = option_key(v.pop("group", None))
        c = option_key(v.pop("course", None))
        v["group_id"] = int(g) if g else None
        v["course_id"] = int(c) if c else None

    def _ask_file() -> str | None:
        path = filedialog.askopenfilename(parent=win, title="Choose a file")
        return path or None

    def add_item(kind: str):
        def run(tab):
            v = form_dialog(win, f"Add {kind.lower()}", scope_fields + common
                            + [Field("url", "Link (https://…)", width=44),
                               Field("with_file", "Attach a file now",
                                     "check"),
                               Field("published", "Publish now", "check")],
                            {"sort_order": 0})
            if not v:
                return
            _scope(v)
            v["kind"] = kind
            path = _ask_file() if v.pop("with_file") else None
            data.create_resource(v, source_path=path)
            refresh_all()
        return run

    def add_task(tab):
        g = option_key(tab.filters().get("group"))
        if not g:
            messagebox.showwarning(
                "Choose a group",
                "Pick a class group in the filter first — the homework / "
                "coursework list comes from that group.", parent=win)
            return
        options = [f"{t.kind} #{t.task_id} — {t.title} (due "
                   f"{t.due_date or '—'})"
                   for t in data.task_options(group_id=int(g))]
        if not options:
            messagebox.showwarning("No tasks", "That group has no homework "
                                   "or coursework to link yet.", parent=win)
            return
        v = form_dialog(win, "Add online task", [
            Field("task", "Homework / coursework", "combo", options,
                  required=True, width=60)] + common
            + [Field("published", "Publish now", "check")],
            {"sort_order": 0})
        if v:
            head = v.pop("task").split(" — ")[0]
            kind, _, tid = head.partition(" #")
            v.update({"kind": data.ONLINE_TASK, "group_id": int(g),
                      "task_kind": kind, "task_id": int(tid)})
            data.create_resource(v)
            refresh_all()

    def _sel(tab):
        rid = tab.selected()
        return data.get_resource(int(rid)) if rid else None

    def edit_item(tab):
        r = _sel(tab)
        if not r:
            return
        fields = list(common)
        if r.kind != data.ONLINE_TASK:
            fields.append(Field("url", "Link (https://…)", width=44))
        fields.append(Field("kind", "Type", "combo",
                            (data.RESOURCE, data.LESSON_MATERIAL)
                            if r.kind != data.ONLINE_TASK
                            else (data.ONLINE_TASK,), required=True))
        v = form_dialog(win, f"Edit {r.title}", fields, vars(r))
        if v:
            data.update_resource(r.resource_id, v)
            refresh_all()

    def attach(tab):
        r = _sel(tab)
        if not r:
            return
        path = _ask_file()
        if path:
            data.attach_file(r.resource_id, source_path=path)
            refresh_all()

    def remove_file(tab):
        r = _sel(tab)
        if r and messagebox.askyesno("Remove file",
                                     f"Remove the file from '{r.title}'?",
                                     parent=win):
            data.remove_file(r.resource_id)
            refresh_all()

    def toggle_publish(tab):
        r = _sel(tab)
        if not r:
            return
        (data.unpublish if r.published else data.publish)(r.resource_id)
        refresh_all()

    def open_item(tab):
        r = _sel(tab)
        if r:
            _open_target(win, *data.open_resource(r.resource_id))

    def move(delta: int):
        def run(tab):
            r = _sel(tab)
            if r:
                data.move(r.resource_id, delta)
                refresh_all()
        return run

    def seen(tab):
        r = _sel(tab)
        if not r:
            return
        n, total, missing = data.view_stats(r.resource_id)
        messagebox.showinfo(
            "Who has opened it",
            f"{n} of {total} student(s) have opened '{r.title}'."
            + (f"\n\nNot yet: {', '.join(missing[:40])}"
               + (" …" if len(missing) > 40 else "") if missing else ""),
            parent=win)

    def delete_item(tab):
        r = _sel(tab)
        if r and messagebox.askyesno(
                "Delete", f"Delete '{r.title}' and its stored file? A "
                "linked homework / coursework is not affected.", parent=win):
            data.delete_resource(r.resource_id)
            refresh_all()

    tabs.append(TableTab(
        nb, "Resources", cols, resources_loader,
        filters=[Field("group", "Group", "combo", groups, width=20),
                 Field("course", "Course", "combo", course_list, width=20),
                 Field("kind", "Type", "combo", data.KINDS, width=14),
                 Field("published", "State", "combo",
                       ("Published", "Draft"), width=10),
                 Field("search", "Search", width=14)],
        actions=[("Add resource", add_item(data.RESOURCE)),
                 ("Add lesson material", add_item(data.LESSON_MATERIAL)),
                 ("Add online task", add_task), ("Edit", edit_item),
                 ("Attach file", attach), ("Remove file", remove_file),
                 ("Publish / unpublish", toggle_publish),
                 ("Open", open_item), ("Up", move(-1)), ("Down", move(1)),
                 ("Who has opened it", seen), ("Delete", delete_item)],
        on_double=edit_item, tag_colours=_TAGS))

    # ── Lesson outline ──
    def outline_loader(f):
        g = option_key(f.get("group"))
        c = option_key(f.get("course"))
        if not g and not c:
            return []
        rows = []
        for week, topic, items in data.lesson_outline(
                group_id=int(g) if g else None,
                course_id=int(c) if c and not g else None):
            for r in items:
                rows.append(_row(r))
        return rows

    tabs.append(TableTab(
        nb, "Lesson Outline", cols, outline_loader,
        filters=[Field("group", "Group", "combo", groups, width=24),
                 Field("course", "Course", "combo", course_list, width=24)],
        actions=[("Open", open_item), ("Up", move(-1)), ("Down", move(1))],
        tag_colours=_TAGS))

    # ── What a student sees ──
    def student_loader(f):
        sid = option_key(f.get("student"))
        if not sid:
            return []
        out = []
        for s in data.resources_for_student(sid):
            r = s.resource
            out.append((r.resource_id,
                        (r.resource_id, r.scope_label, r.week or "",
                         r.topic, r.kind, r.title,
                         f"{s.task.title} (due {s.task.due_date or '—'})"
                         if s.task else (r.file_name or r.url or ""),
                         "Yes" if s.seen else "No"),
                        ("task",) if s.task else ()))
        return out

    tabs.append(TableTab(
        nb, "Student View",
        [("id", "ID", 45), ("scope", "Group / course", 160),
         ("week", "Wk", 40), ("topic", "Topic", 130), ("kind", "Type", 110),
         ("title", "Title", 240), ("what", "File / link / task", 300),
         ("seen", "Opened", 60)],
        student_loader,
        filters=[Field("student", "Student", "combo", student_options(),
                       width=40)],
        actions=[("Open", open_item)], tag_colours=_TAGS))

    tabs.append(TableTab(
        nb, "Problems", cols,
        lambda _f: [_row(r, problem=True) for r in data.orphaned_resources()],
        actions=[("Edit", edit_item), ("Delete", delete_item)],
        tag_colours=_TAGS))

    def render():
        s = data.summary()
        lines = ["Online learning space", "",
                 f"  Items:            {s.total}",
                 f"  Published:        {s.published}",
                 f"  Drafts:           {s.drafts}",
                 f"  With a file:      {s.files}  ({_size(s.store_bytes)})",
                 f"  With a link:      {s.links}",
                 f"  Online tasks:     {s.tasks}",
                 f"  Problems:         {s.orphaned}", "", "  By type:"]
        lines += [f"    {k:<18} {v}" for k, v in s.by_kind.items()]
        lines += ["", "  By course:"]
        lines += [f"    {k:<18} {v}" for k, v in sorted(s.by_course.items())]
        return lines

    tabs.append(SummaryTab(nb, render))
