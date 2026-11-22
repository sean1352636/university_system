"""CLI flows: online learning space (class resources)."""

from __future__ import annotations

import logging
from typing import Callable

from education_system.systems.sixth_form.domain.academics.class_groups import (
    class_groups as _cg,
)
from education_system.systems.sixth_form.domain.academics.class_resources import (
    class_resources as data,
)
from education_system.systems.sixth_form.domain.academics.courses import (
    courses as _courses,
)
from education_system.systems.sixth_form.interfaces.cli.operations._ops_cli import (
    ask,
    choose,
    pause,
    pick_student,
    run_menu,
    table,
    yes_no,
)

logger = logging.getLogger(__name__)


def _pick_group(allow_course_wide: bool = False) -> tuple[int | None, int]:
    """(group_id or None, course_id)."""
    codes = {c.course_id: c.course_code for c in _courses.list_courses()}
    options = [f"{g.group_id} — {codes.get(g.course_id, g.course_id)} "
               f"{g.group_name}" for g in _cg.list_groups()]
    if allow_course_wide:
        options += [f"C{c.course_id} — {c.course_code} (all groups)"
                    for c in _courses.list_courses()]
    label = choose("Group / course", options)
    if label is None:
        raise ValueError("Create a course and class group first")
    head = label.split(" — ")[0]
    if head.startswith("C"):
        return None, int(head[1:])
    g = _cg.get_group(int(head))
    return g.group_id, g.course_id


def _show(rows) -> None:
    table(["ID", "Group / course", "Wk", "Topic", "Type", "Title", "File",
           "Link / task", "Pub"],
          [(r.resource_id, r.scope_label, r.week or "", r.topic, r.kind,
            r.title, r.file_name, r.url or r.task_ref,
            "Y" if r.published else "N") for r in rows])


def list_resources() -> None:
    gid, cid = _pick_group(allow_course_wide=True)
    _show(data.list_resources(group_id=gid,
                              course_id=None if gid else cid))
    pause()


def _common(r=None) -> dict:
    return {
        "title": ask("Title", default=r.title if r else "", required=True),
        "description": ask("Description",
                           default=(r.description or "") if r else ""),
        "week": ask("Teaching week (1-52, blank = none)",
                    default=str(r.week or "") if r else ""),
        "topic": ask("Topic", default=(r.topic or "") if r else ""),
        "sort_order": ask("Order within week",
                          default=str(r.sort_order) if r else "0"),
        "available_from": ask("Available from (YYYY-MM-DD, blank = now)",
                              default=(r.available_from or "") if r else ""),
    }


def add_resource() -> None:
    gid, cid = _pick_group(allow_course_wide=True)
    kind = choose("Type", (data.RESOURCE, data.LESSON_MATERIAL),
                  default=data.RESOURCE)
    payload = {"group_id": gid, "course_id": cid, "kind": kind, **_common(),
               "url": ask("Link (https://…, blank = none)")}
    path = ask("File to attach (path, blank = none)")
    payload["published"] = yes_no("Publish now?")
    r = data.create_resource(payload, source_path=path or None)
    print(f"\n  ✓ Added #{r.resource_id} {r.title}")
    pause()


def add_task() -> None:
    gid, cid = _pick_group()
    tasks = data.task_options(group_id=gid)
    label = choose("Homework / coursework",
                   [f"{t.kind} #{t.task_id} — {t.title} (due "
                    f"{t.due_date or '—'})" for t in tasks])
    if label is None:
        raise ValueError("That group has no homework or coursework yet")
    kind, _, tid = label.split(" — ")[0].partition(" #")
    r = data.create_resource({"group_id": gid, "kind": data.ONLINE_TASK,
                              "task_kind": kind, "task_id": int(tid),
                              **_common(),
                              "published": yes_no("Publish now?")})
    print(f"\n  ✓ Linked #{r.resource_id} to {r.task_ref}")
    pause()


def _pick_resource():
    gid, cid = _pick_group(allow_course_wide=True)
    rows = data.list_resources(group_id=gid, course_id=None if gid else cid)
    label = choose("Item", [f"{r.resource_id} — {r.title} ({r.kind}, "
                            f"{'published' if r.published else 'draft'})"
                            for r in rows])
    if label is None:
        raise ValueError("Nothing here yet")
    return data.get_resource(int(label.split(" — ")[0]))


def edit_resource() -> None:
    r = _pick_resource()
    payload = _common(r)
    if r.kind != data.ONLINE_TASK:
        payload["url"] = ask("Link", default=r.url or "")
    data.update_resource(r.resource_id, payload)
    print("\n  ✓ Updated")
    pause()


def attach_file() -> None:
    r = _pick_resource()
    path = ask("File path", required=True)
    data.attach_file(r.resource_id, source_path=path)
    print("\n  ✓ File attached")
    pause()


def remove_file() -> None:
    r = _pick_resource()
    if yes_no(f"Remove the file from '{r.title}'?"):
        data.remove_file(r.resource_id)
        print("\n  ✓ Removed")
    pause()


def toggle_publish() -> None:
    r = _pick_resource()
    out = (data.unpublish if r.published else data.publish)(r.resource_id)
    print(f"\n  ✓ {'Published' if out.published else 'Unpublished'}")
    pause()


def reorder() -> None:
    r = _pick_resource()
    data.move(r.resource_id, -1 if choose("Move", ("Up", "Down")) == "Up"
              else 1)
    print("\n  ✓ Moved")
    pause()


def delete_resource() -> None:
    r = _pick_resource()
    if yes_no(f"Delete '{r.title}' and its file?"):
        data.delete_resource(r.resource_id)
        print("\n  ✓ Deleted")
    pause()


def who_opened() -> None:
    r = _pick_resource()
    n, total, missing = data.view_stats(r.resource_id)
    print(f"\n  {n} of {total} student(s) have opened it.")
    if missing:
        print("  Not yet: " + ", ".join(missing))
    pause()


def outline() -> None:
    gid, cid = _pick_group(allow_course_wide=True)
    for week, topic, items in data.lesson_outline(
            group_id=gid, course_id=None if gid else cid):
        print(f"\n  Week {week or '—'}: {topic or '(no topic)'}")
        for r in items:
            print(f"     · {r.title}{'' if r.published else '  [draft]'}")
    pause()


def student_view() -> None:
    sid = pick_student()
    rows = data.resources_for_student(sid)
    table(["ID", "Group / course", "Wk", "Type", "Title", "Task / link",
           "Opened"],
          [(s.resource.resource_id, s.resource.scope_label,
            s.resource.week or "", s.resource.kind, s.resource.title,
            f"{s.task.title} due {s.task.due_date or '—'}" if s.task
            else s.resource.file_name or s.resource.url,
            "Y" if s.seen else "N") for s in rows])
    pause()


def problems() -> None:
    _show(data.orphaned_resources())
    pause()


def summary_flow() -> None:
    s = data.summary()
    print("\n═══ Online Learning Space ═══")
    print(f"  Items: {s.total}  published {s.published}  drafts {s.drafts}")
    print(f"  Files: {s.files}  links: {s.links}  tasks: {s.tasks}")
    print(f"  Problems: {s.orphaned}")
    for k, v in sorted(s.by_course.items()):
        print(f"    {k:<16} {v}")
    pause()


_MENU: list[tuple[str, Callable[[], None]]] = [
    ("List resources",        list_resources),
    ("Lesson outline",        outline),
    ("What a student sees",   student_view),
    ("Who has opened an item", who_opened),
    ("─" * 6,                 lambda: None),
    ("Add resource / lesson material", add_resource),
    ("Add online task (link homework / coursework)", add_task),
    ("Edit item",             edit_resource),
    ("Attach / replace file", attach_file),
    ("Remove file",           remove_file),
    ("Publish / unpublish",   toggle_publish),
    ("Reorder",               reorder),
    ("Delete item",           delete_resource),
    ("─" * 6,                 lambda: None),
    ("Problems (missing group / task)", problems),
    ("Summary",               summary_flow),
]


def run() -> None:
    run_menu("Online Learning Space", _MENU)


def class_resources_menu() -> None:
    """Entry point for the main CLI menu."""
    run()
