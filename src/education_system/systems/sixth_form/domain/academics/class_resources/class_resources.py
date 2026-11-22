"""Online learning space: class resources for the Sixth Form System.

One table, ``class_resources``, holds what a teacher puts in front of a
class group (or every group on a course):

* **Resources** — a link (http/https) and/or an uploaded file;
* **Lesson materials** — the same, ordered by teaching week and topic so
  the group sees the course unfold week by week;
* **Online tasks** — a pointer to an existing Homework (``assignments``)
  or Coursework (``coursework_assignments``) record. The task itself is
  never copied: its title, due date and status are read from the owning
  record each time.

Scope: ``course_id`` is always set; ``group_id`` set means *that group
only*, NULL means every group on the course. Students see a resource
only when it is **published**, its ``available_from`` date has come, and
they are a member of the group (or of a group on the course). Coursework
tasks also stay hidden while the coursework itself is still a Draft.

Files are copied into ``<sixth form data dir>/class_resources/`` (the
same runtime area, layout and filename rules as the coursework store),
named ``course_<id>/[group_<id>/]<resource id>_<name>`` and content
hashed. ``class_resource_views`` records which students opened what.

Group and course references are soft (checked on write) so deleting a
course or group in Class Groups is not blocked; resources left pointing
at a removed group are listed by :func:`orphaned_resources`.

Write permission: the teacher of the group (group teacher, else the
course teacher), the course teacher for course-wide items, or staff with
``students.manage`` / admin.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import logging
import mimetypes
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB
STORE_DIRNAME = "class_resources"

RESOURCE = "Resource"
LESSON_MATERIAL = "Lesson Material"
ONLINE_TASK = "Online Task"
KINDS: tuple[str, ...] = (RESOURCE, LESSON_MATERIAL, ONLINE_TASK)

HOMEWORK = "Homework"
COURSEWORK = "Coursework"
TASK_KINDS: tuple[str, ...] = (HOMEWORK, COURSEWORK)

#: Coursework is shown to students only once it has been set.
VISIBLE_COURSEWORK_STATUSES: tuple[str, ...] = ("Set", "Closed", "Graded")

MAX_FILE_BYTES = 50 * 1024 * 1024
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS class_resources (
    resource_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id       INTEGER NOT NULL,
    group_id        INTEGER,
    kind            TEXT NOT NULL DEFAULT 'Resource',
    title           TEXT NOT NULL,
    description     TEXT,
    url             TEXT,
    stored_path     TEXT,
    file_name       TEXT,
    file_size       INTEGER,
    mime_type       TEXT,
    sha256          TEXT,
    week            INTEGER,
    topic           TEXT,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    task_kind       TEXT,
    task_id         INTEGER,
    published       INTEGER NOT NULL DEFAULT 0,
    published_at    TEXT,
    available_from  TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS class_resource_views (
    view_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id  INTEGER NOT NULL,
    student_id   TEXT NOT NULL,
    first_seen   TEXT DEFAULT (datetime('now')),
    last_seen    TEXT DEFAULT (datetime('now')),
    times        INTEGER NOT NULL DEFAULT 1,
    UNIQUE (resource_id, student_id),
    FOREIGN KEY (resource_id) REFERENCES class_resources(resource_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id)  REFERENCES students(student_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cres_course ON class_resources(course_id);
CREATE INDEX IF NOT EXISTS idx_cres_group  ON class_resources(group_id);
CREATE INDEX IF NOT EXISTS idx_cres_task   ON class_resources(task_kind, task_id);
CREATE INDEX IF NOT EXISTS idx_crv_student ON class_resource_views(student_id);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Resource:
    resource_id: int
    course_id: int
    group_id: int | None
    kind: str
    title: str
    description: str | None
    url: str | None
    stored_path: str | None
    file_name: str | None
    file_size: int | None
    mime_type: str | None
    sha256: str | None
    week: int | None
    topic: str | None
    sort_order: int
    task_kind: str | None
    task_id: int | None
    published: bool
    published_at: str | None
    available_from: str | None
    created_by: str | None
    created_at: str
    updated_at: str
    course_code: str | None = None
    group_name: str | None = None

    @property
    def scope_label(self) -> str:
        code = self.course_code or f"course #{self.course_id}"
        if self.group_id is None:
            return f"{code} (all groups)"
        return f"{code} {self.group_name or f'group #{self.group_id}'}"

    @property
    def has_file(self) -> bool:
        return bool(self.stored_path)

    @property
    def task_ref(self) -> str | None:
        if self.task_kind and self.task_id:
            return f"{self.task_kind} #{self.task_id}"
        return None


@dataclass
class TaskInfo:
    """The live state of a linked Homework / Coursework record."""
    kind: str
    task_id: int
    title: str
    due_date: str | None
    status: str | None
    visible_to_students: bool


@dataclass
class StudentResource:
    resource: Resource
    task: TaskInfo | None = None
    seen: bool = False


@dataclass
class ResourceSummary:
    total: int = 0
    published: int = 0
    drafts: int = 0
    files: int = 0
    links: int = 0
    tasks: int = 0
    orphaned: int = 0
    by_kind: dict[str, int] = field(default_factory=dict)
    by_course: dict[str, int] = field(default_factory=dict)
    store_bytes: int = 0


# ── Plumbing ────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    _cg.init_db()          # courses, students, class groups
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def store_root() -> Path:
    """Read from ``paths`` at call time so a redirected data dir wins."""
    root = Path(paths.SIXTH_FORM_DATA_DIR) / STORE_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


_SELECT = (
    "SELECT r.*, c.course_code, g.group_name FROM class_resources r "
    "LEFT JOIN courses c ON c.course_id = r.course_id "
    "LEFT JOIN class_groups g ON g.group_id = r.group_id")


def _row(r: _sql.Row) -> Resource:
    return Resource(
        resource_id=r["resource_id"], course_id=r["course_id"],
        group_id=r["group_id"], kind=r["kind"], title=r["title"],
        description=r["description"], url=r["url"],
        stored_path=r["stored_path"], file_name=r["file_name"],
        file_size=r["file_size"], mime_type=r["mime_type"],
        sha256=r["sha256"], week=r["week"], topic=r["topic"],
        sort_order=r["sort_order"], task_kind=r["task_kind"],
        task_id=r["task_id"], published=bool(r["published"]),
        published_at=r["published_at"], available_from=r["available_from"],
        created_by=r["created_by"], created_at=r["created_at"],
        updated_at=r["updated_at"], course_code=r["course_code"],
        group_name=r["group_name"])


# ── Validation helpers ──────────────────────────────────────────────

def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _require(v: Any, label: str) -> str:
    s = _text(v)
    if not s:
        raise ValidationError(f"{label} is required")
    return s


def _date(v: Any, label: str) -> str | None:
    s = _text(v)
    if not s:
        return None
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _opt_int(v: Any, label: str, lo: int, hi: int) -> int | None:
    if v in (None, ""):
        return None
    try:
        n = int(str(v).strip())
    except ValueError:
        raise ValidationError(f"{label} must be a whole number") from None
    if not lo <= n <= hi:
        raise ValidationError(f"{label} must be between {lo} and {hi}")
    return n


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def validate_url(v: Any) -> str | None:
    s = _text(v)
    if not s:
        return None
    u = urlparse(s)
    if u.scheme.lower() not in ("http", "https") or not u.netloc:
        raise ValidationError("Link must be a full http:// or https:// URL")
    if len(s) > 2000:
        raise ValidationError("Link is too long")
    return s


def _course(course_id: int) -> Any:
    from education_system.systems.sixth_form.domain.academics.courses import (
        courses as _crs,
    )
    return _crs.get_course(int(course_id))


def _group(group_id: int) -> Any:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    return _cg.get_group(int(group_id))


def _resolve_scope(course_id: Any, group_id: Any) -> tuple[int, int | None]:
    gid = _opt_int(group_id, "Class group", 1, 10**9)
    if gid is not None:
        g = _group(gid)
        if g is None:
            raise ValidationError(f"No class group #{gid}")
        if course_id not in (None, "") and int(course_id) != g.course_id:
            raise ValidationError(
                f"Group {g.group_name} is not on course #{course_id}")
        return g.course_id, gid
    cid = _opt_int(course_id, "Course", 1, 10**9)
    if cid is None:
        raise ValidationError("Choose a course or a class group")
    if _course(cid) is None:
        raise ValidationError(f"No course #{cid}")
    return cid, None


# ── Linked tasks ────────────────────────────────────────────────────

def task_info(task_kind: str | None, task_id: int | None) -> TaskInfo | None:
    """Live title / due date / status of a linked task; None if gone."""
    if not task_kind or not task_id:
        return None
    today = _dt.date.today().isoformat()
    if task_kind == HOMEWORK:
        from education_system.systems.sixth_form.domain.academics.homework import (
            homework as _hw,
        )
        a = _hw.get_assignment(int(task_id))
        if a is None:
            return None
        return TaskInfo(HOMEWORK, a.assignment_id, a.title, a.due_date,
                        a.type, (a.set_date or "") <= today)
    from education_system.systems.sixth_form.domain.academics.assignments import (
        store as _cw,
    )
    a = _cw.get_assignment(int(task_id))
    if a is None:
        return None
    return TaskInfo(COURSEWORK, a.assignment_id, a.title, a.due_date,
                    a.status, a.status in VISIBLE_COURSEWORK_STATUSES)


def _task_scope(task_kind: str, task_id: int) -> tuple[int | None, int | None]:
    """(course_id, group_id) the task belongs to."""
    if task_kind == HOMEWORK:
        from education_system.systems.sixth_form.domain.academics.homework import (
            homework as _hw,
        )
        a = _hw.get_assignment(task_id)
        if a is None:
            raise ValidationError(f"No homework #{task_id}")
        g = _group(a.group_id)
        return (g.course_id if g else None), a.group_id
    from education_system.systems.sixth_form.domain.academics.assignments import (
        store as _cw,
    )
    a = _cw.get_assignment(task_id)
    if a is None:
        raise ValidationError(f"No coursework #{task_id}")
    cid = a.course_id
    if cid is None and a.class_group_id:
        g = _group(a.class_group_id)
        cid = g.course_id if g else None
    return cid, a.class_group_id


def _validate_task(task_kind: Any, task_id: Any, course_id: int,
                   group_id: int | None) -> tuple[str, int]:
    kind = _choice(task_kind, TASK_KINDS, "Task type")
    tid = _opt_int(task_id, "Task", 1, 10**9)
    if tid is None:
        raise ValidationError("Choose the homework or coursework to link")
    t_course, t_group = _task_scope(kind, tid)
    if group_id is not None:
        ok = t_group == group_id or (t_group is None and t_course == course_id)
    else:
        ok = t_course == course_id
    if not ok:
        raise ValidationError(
            f"{kind} #{tid} is not set for this group / course")
    return kind, tid


def task_options(*, course_id: int | None = None,
                 group_id: int | None = None) -> list[TaskInfo]:
    """Homework and coursework that may be linked into this scope."""
    cid, gid = _resolve_scope(course_id, group_id)
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    from education_system.systems.sixth_form.domain.academics.homework import (
        homework as _hw,
    )
    from education_system.systems.sixth_form.domain.academics.assignments import (
        store as _cw,
    )
    groups = [gid] if gid is not None else [
        g.group_id for g in _cg.list_groups(course_id=cid)]
    out: list[TaskInfo] = []
    for g in groups:
        for a in _hw.list_assignments(group_id=g):
            out.append(task_info(HOMEWORK, a.assignment_id))
    seen: set[int] = set()
    for a in _cw.list_assignments(course_id=cid) + (
            _cw.list_assignments(class_group_id=gid) if gid else []):
        if a.assignment_id in seen:
            continue
        if gid is not None and a.class_group_id not in (None, gid):
            continue
        seen.add(a.assignment_id)
        out.append(task_info(COURSEWORK, a.assignment_id))
    return [t for t in out if t is not None]


# ── Permissions ─────────────────────────────────────────────────────

def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _norm(s: str | None) -> str:
    return " ".join((s or "").split()).lower()


def _principal_aliases(p: Any) -> set[str]:
    out = {_norm(v) for v in (p.staff_id, p.staff_name, p.username) if v}
    if p.staff_id:
        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
        from education_system.systems.sixth_form.domain.academics.cover.cover import (
            staff_aliases,
        )
        st = _staff.get_staff(p.staff_id)
        if st is not None:
            out |= staff_aliases(st)
    return out


def teaches(course_id: int, group_id: int | None, principal: Any = None
            ) -> bool:
    """Is the principal the teacher of the group (or course)?"""
    p = principal or _access().current()
    mine = _principal_aliases(p)
    if not mine:
        return False
    course = _course(course_id)
    course_teacher = _norm(course.teacher) if course else ""
    if group_id is not None:
        g = _group(group_id)
        eff = _norm(g.teacher) if g and _norm(g.teacher) else course_teacher
        return bool(eff) and eff in mine
    if course_teacher and course_teacher in mine:
        return True
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    return any(_norm(g.teacher) in mine for g in
               _cg.list_groups(course_id=course_id) if _norm(g.teacher))


def can_edit(course_id: int, group_id: int | None,
             principal: Any = None) -> bool:
    access = _access()
    p = principal or access.current()
    if p.is_admin or p.can(access.STUDENTS_MANAGE):
        return True
    return p.is_staff and teaches(course_id, group_id, p)


def _require_edit(course_id: int, group_id: int | None, action: str) -> Any:
    access = _access()
    p = access.current()
    if not can_edit(course_id, group_id, p):
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not {action} — only the "
            "group's teacher (or Sixth Form leaders) can.")
    return p


def _require_staff_reader() -> None:
    access = _access()
    access.current().require(access.TEACHING, "class resources")


# ── Files ───────────────────────────────────────────────────────────

def _safe_filename(name: Any) -> str:
    from education_system.systems.sixth_form.domain.academics.assignments.models import (
        _UNSAFE_FILENAME_RE,
    )
    stem = Path(str(name or "")).name.strip()
    cleaned = _UNSAFE_FILENAME_RE.sub("_", stem).strip("._-")
    return cleaned[:120] or "file"


def _check_name(filename: str) -> None:
    from education_system.systems.sixth_form.domain.academics.assignments.models import (
        BLOCKED_ATTACHMENT_SUFFIXES,
    )
    suffix = Path(filename).suffix.lower()
    if suffix in BLOCKED_ATTACHMENT_SUFFIXES:
        raise ValidationError(f"{suffix} files cannot be shared with a class")


def _store_file(resource: Resource, *, source_path: Any = None,
                data: bytes | None = None, filename: str | None = None
                ) -> dict[str, Any]:
    if (source_path is None) == (data is None):
        raise ValidationError("Provide exactly one of a file path or data")
    if source_path is not None:
        src = Path(str(source_path)).expanduser()
        if not src.is_file():
            raise ValidationError(f"No such file: {src}")
        size = src.stat().st_size
        name = filename or src.name
    else:
        if not filename:
            raise ValidationError("A file name is required")
        size = len(data or b"")
        name = filename
    if size == 0:
        raise ValidationError("File is empty")
    if size > MAX_FILE_BYTES:
        raise ValidationError(
            f"File is {size / 1048576:.1f} MB — the limit is "
            f"{MAX_FILE_BYTES // 1048576} MB")
    safe = _safe_filename(name)
    _check_name(safe)
    rel_dir = Path(f"course_{resource.course_id}")
    if resource.group_id is not None:
        rel_dir /= f"group_{resource.group_id}"
    rel = rel_dir / f"{resource.resource_id}_{safe}"
    root = store_root()
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if source_path is not None:
        shutil.copyfile(src, target)
    else:
        target.write_bytes(data or b"")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {"stored_path": rel.as_posix(), "file_name": safe,
            "file_size": size, "sha256": digest,
            "mime_type": mimetypes.guess_type(safe)[0]}


def _unlink(rel: str | None) -> None:
    if not rel:
        return
    root = store_root()
    target = root / rel
    if root not in target.resolve().parents:
        logger.warning("Refused to remove %s outside the store", target)
        return
    try:
        target.unlink(missing_ok=True)
        node = target.parent
        while node != root and root in node.parents:
            node.rmdir()
            node = node.parent
    except OSError:
        pass


def file_path(resource: Resource) -> Path | None:
    """Absolute path of the stored copy (None for a link-only item)."""
    if not resource.stored_path:
        return None
    path = store_root() / resource.stored_path
    return path if path.is_file() else None


# ── CRUD ────────────────────────────────────────────────────────────

def _values(payload: dict[str, Any], existing: Resource | None
            ) -> dict[str, Any]:
    def g(k: str, dflt: Any = None) -> Any:
        return payload.get(k, getattr(existing, k) if existing else dflt)

    if existing is not None and "course_id" not in payload \
            and "group_id" not in payload:
        cid, gid = existing.course_id, existing.group_id
    else:
        cid, gid = _resolve_scope(g("course_id"), g("group_id"))
    kind = _choice(g("kind", RESOURCE), KINDS, "Type", RESOURCE)
    out = {
        "course_id": cid, "group_id": gid, "kind": kind,
        "title": _require(g("title"), "Title"),
        "description": _text(g("description")),
        "url": validate_url(g("url")),
        "week": _opt_int(g("week"), "Week", 1, 52),
        "topic": _text(g("topic")),
        "sort_order": _opt_int(g("sort_order", 0), "Order", -9999, 9999) or 0,
        "available_from": _date(g("available_from"), "Available from"),
        "task_kind": None, "task_id": None,
    }
    if kind == ONLINE_TASK:
        out["task_kind"], out["task_id"] = _validate_task(
            g("task_kind"), g("task_id"), cid, gid)
    elif payload.get("task_kind") or payload.get("task_id"):
        raise ValidationError("Only an Online Task links to homework or "
                              "coursework")
    return out


def create_resource(payload: dict[str, Any], *, source_path: Any = None,
                    data: bytes | None = None,
                    filename: str | None = None) -> Resource:
    """Add an item. A Resource / Lesson Material needs a link or a file;
    an Online Task needs ``task_kind`` + ``task_id``. New items start
    unpublished unless ``published`` is true."""
    init_db()
    v = _values(payload, None)
    p = _require_edit(v["course_id"], v["group_id"], "add class resources")
    has_file = source_path is not None or data is not None
    if v["kind"] != ONLINE_TASK and not v["url"] and not has_file:
        raise ValidationError("Give a link or attach a file")
    publish_now = bool(payload.get("published"))
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO class_resources (course_id, group_id, kind, title, "
            "description, url, week, topic, sort_order, task_kind, task_id, "
            "available_from, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (v["course_id"], v["group_id"], v["kind"], v["title"],
             v["description"], v["url"], v["week"], v["topic"],
             v["sort_order"], v["task_kind"], v["task_id"],
             v["available_from"], p.staff_name or p.username or None))
        new_id = cur.lastrowid
    if has_file:
        try:
            attach_file(new_id, source_path=source_path, data=data,
                        filename=filename)
        except Exception:
            with _connect() as conn:
                conn.execute("DELETE FROM class_resources WHERE resource_id=?",
                             (new_id,))
            raise
    if publish_now:
        publish(new_id)
    logger.info("Class resource #%d added (%s, course %s group %s)", new_id,
                v["kind"], v["course_id"], v["group_id"])
    return _require_resource(new_id)


def update_resource(resource_id: int, payload: dict[str, Any]) -> Resource:
    r = _require_resource(resource_id)
    _require_edit(r.course_id, r.group_id, "change this resource")
    v = _values(payload, r)
    if (v["course_id"], v["group_id"]) != (r.course_id, r.group_id):
        _require_edit(v["course_id"], v["group_id"],
                      "move a resource to that group")
    if v["kind"] != ONLINE_TASK and not v["url"] and not r.stored_path:
        raise ValidationError("Give a link or attach a file")
    with _connect() as conn:
        conn.execute(
            "UPDATE class_resources SET course_id=?, group_id=?, kind=?, "
            "title=?, description=?, url=?, week=?, topic=?, sort_order=?, "
            "task_kind=?, task_id=?, available_from=?, "
            "updated_at=datetime('now') WHERE resource_id=?",
            (v["course_id"], v["group_id"], v["kind"], v["title"],
             v["description"], v["url"], v["week"], v["topic"],
             v["sort_order"], v["task_kind"], v["task_id"],
             v["available_from"], resource_id))
    return _require_resource(resource_id)


def attach_file(resource_id: int, *, source_path: Any = None,
                data: bytes | None = None,
                filename: str | None = None) -> Resource:
    """Attach (or replace) the file on an item."""
    r = _require_resource(resource_id)
    _require_edit(r.course_id, r.group_id, "attach files")
    if r.kind == ONLINE_TASK:
        raise ValidationError("Attach files to the homework / coursework "
                              "itself, not to the online-task link")
    meta = _store_file(r, source_path=source_path, data=data,
                       filename=filename)
    with _connect() as conn:
        conn.execute(
            "UPDATE class_resources SET stored_path=?, file_name=?, "
            "file_size=?, mime_type=?, sha256=?, updated_at=datetime('now') "
            "WHERE resource_id=?",
            (meta["stored_path"], meta["file_name"], meta["file_size"],
             meta["mime_type"], meta["sha256"], resource_id))
    if r.stored_path and r.stored_path != meta["stored_path"]:
        _unlink(r.stored_path)
    return _require_resource(resource_id)


def remove_file(resource_id: int) -> Resource:
    r = _require_resource(resource_id)
    _require_edit(r.course_id, r.group_id, "remove files")
    if not r.stored_path:
        raise ValidationError("This item has no file")
    if not r.url and r.kind != ONLINE_TASK:
        raise ValidationError("Add a link first — an item needs a link or "
                              "a file")
    with _connect() as conn:
        conn.execute(
            "UPDATE class_resources SET stored_path=NULL, file_name=NULL, "
            "file_size=NULL, mime_type=NULL, sha256=NULL, "
            "updated_at=datetime('now') WHERE resource_id=?", (resource_id,))
    _unlink(r.stored_path)
    return _require_resource(resource_id)


def publish(resource_id: int) -> Resource:
    r = _require_resource(resource_id)
    _require_edit(r.course_id, r.group_id, "publish resources")
    if r.kind == ONLINE_TASK and task_info(r.task_kind, r.task_id) is None:
        raise ValidationError("The linked task no longer exists")
    with _connect() as conn:
        conn.execute(
            "UPDATE class_resources SET published=1, "
            "published_at=COALESCE(published_at, datetime('now')), "
            "updated_at=datetime('now') WHERE resource_id=?", (resource_id,))
    return _require_resource(resource_id)


def unpublish(resource_id: int) -> Resource:
    r = _require_resource(resource_id)
    _require_edit(r.course_id, r.group_id, "unpublish resources")
    with _connect() as conn:
        conn.execute(
            "UPDATE class_resources SET published=0, published_at=NULL, "
            "updated_at=datetime('now') WHERE resource_id=?", (resource_id,))
    return _require_resource(resource_id)


def delete_resource(resource_id: int) -> bool:
    """Remove the item and its stored file. The linked homework or
    coursework is untouched."""
    r = _require_resource(resource_id)
    _require_edit(r.course_id, r.group_id, "delete resources")
    with _connect() as conn:
        cur = conn.execute("DELETE FROM class_resources WHERE resource_id=?",
                           (resource_id,))
    _unlink(r.stored_path)
    return bool(cur.rowcount)


def move(resource_id: int, delta: int) -> Resource:
    """Nudge an item up (-1) or down (+1) within its week."""
    r = _require_resource(resource_id)
    _require_edit(r.course_id, r.group_id, "reorder resources")
    with _connect() as conn:
        conn.execute(
            "UPDATE class_resources SET sort_order=sort_order+?, "
            "updated_at=datetime('now') WHERE resource_id=?",
            (int(delta), resource_id))
    return _require_resource(resource_id)


def get_resource(resource_id: int) -> Resource | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(f"{_SELECT} WHERE r.resource_id=?",
                         (int(resource_id),)).fetchone()
    return _row(r) if r else None


def _require_resource(resource_id: int) -> Resource:
    r = get_resource(resource_id)
    if r is None:
        raise ValidationError(f"No class resource #{resource_id}")
    return r


_ORDER = (" ORDER BY c.course_code, r.group_id IS NOT NULL, g.group_name, "
          "COALESCE(r.week, 999), r.topic COLLATE NOCASE, r.sort_order, "
          "r.resource_id")


def list_resources(*, course_id: int | None = None,
                   group_id: int | None = None,
                   include_course_wide: bool = True,
                   kind: str | None = None,
                   published: bool | None = None,
                   week: int | None = None,
                   search: str | None = None) -> list[Resource]:
    """Staff view, in teaching order (week, topic, order). With
    ``group_id`` the course-wide items for that group's course are
    included unless ``include_course_wide`` is false."""
    _require_staff_reader()
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if group_id is not None:
        g = _group(group_id)
        if g is None:
            raise ValidationError(f"No class group #{group_id}")
        if include_course_wide:
            clauses.append("(r.group_id = ? OR (r.group_id IS NULL AND "
                           "r.course_id = ?))")
            args += [g.group_id, g.course_id]
        else:
            clauses.append("r.group_id = ?")
            args.append(g.group_id)
    elif course_id is not None:
        clauses.append("r.course_id = ?")
        args.append(int(course_id))
    if kind:
        clauses.append("r.kind = ?")
        args.append(_choice(kind, KINDS, "Type"))
    if published is not None:
        clauses.append("r.published = ?")
        args.append(1 if published else 0)
    if week is not None:
        clauses.append("r.week = ?")
        args.append(int(week))
    if search:
        like = f"%{search.strip()}%"
        clauses.append("(r.title LIKE ? OR r.topic LIKE ? OR "
                       "r.description LIKE ?)")
        args += [like, like, like]
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row(r) for r in conn.execute(_SELECT + where + _ORDER,
                                              args).fetchall()]


def lesson_outline(*, course_id: int | None = None,
                   group_id: int | None = None
                   ) -> list[tuple[int | None, str | None, list[Resource]]]:
    """Lesson materials grouped as ``[(week, topic, [items])]``."""
    rows = list_resources(course_id=course_id, group_id=group_id,
                          kind=LESSON_MATERIAL)
    rows.sort(key=lambda r: (r.week or 999, (r.topic or "").lower(),
                             r.sort_order, r.resource_id))
    out: list[tuple[int | None, str | None, list[Resource]]] = []
    for r in rows:
        if out and out[-1][0] == r.week and \
                (out[-1][1] or "").lower() == (r.topic or "").lower():
            out[-1][2].append(r)
        else:
            out.append((r.week, r.topic, [r]))
    return out


def resources_for_task(task_kind: str, task_id: int) -> list[Resource]:
    _require_staff_reader()
    init_db()
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            f"{_SELECT} WHERE r.task_kind=? AND r.task_id=?" + _ORDER,
            (task_kind, int(task_id))).fetchall()]


def orphaned_resources() -> list[Resource]:
    """Items whose group or course has since been removed, or whose
    linked task no longer exists."""
    _require_staff_reader()
    init_db()
    with _connect() as conn:
        rows = [_row(r) for r in conn.execute(
            f"{_SELECT} WHERE c.course_id IS NULL OR "
            "(r.group_id IS NOT NULL AND g.group_id IS NULL) OR "
            "r.task_id IS NOT NULL" + _ORDER).fetchall()]
    return [r for r in rows if r.course_code is None
            or (r.group_id is not None and r.group_name is None)
            or (r.task_id and task_info(r.task_kind, r.task_id) is None)]


# ── Student side ────────────────────────────────────────────────────

def _check_student_access(student_id: str) -> str:
    access = _access()
    p = access.current()
    sid = _require(student_id, "Student")
    if not access.can_see_student(p, sid):
        raise access.AccessDenied(
            f"{p.username or 'This account'} may not see another "
            "student's class resources.")
    return sid


def _student_groups(student_id: str) -> list[Any]:
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    return _cg.groups_for_student(student_id)


def resources_for_student(student_id: str, *,
                          group_id: int | None = None
                          ) -> list[StudentResource]:
    """What a student can see: published items for their class groups
    (and course-wide items for those courses) whose ``available_from``
    has come, in teaching order. Online tasks carry the live task (title,
    due date); a task the student may not see yet is left out.

    The signed-in user must be the student, or staff who may see them.
    """
    sid = _check_student_access(student_id)
    init_db()
    groups = _student_groups(sid)
    if group_id is not None:
        groups = [g for g in groups if g.group_id == int(group_id)]
    if not groups:
        return []
    gids = [g.group_id for g in groups]
    cids = sorted({g.course_id for g in groups})
    today = _dt.date.today().isoformat()
    gm = ",".join("?" * len(gids))
    cm = ",".join("?" * len(cids))
    sql = (f"{_SELECT} WHERE r.published = 1 AND "
           "(r.available_from IS NULL OR r.available_from <= ?) AND "
           f"(r.group_id IN ({gm}) OR (r.group_id IS NULL AND "  # DBW001: only placeholders are interpolated
           f"r.course_id IN ({cm})))" + _ORDER)
    with _connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, [today, *gids, *cids])]
        seen = {r[0] for r in conn.execute(
            "SELECT resource_id FROM class_resource_views WHERE "
            "student_id=?", (sid,))}
    out: list[StudentResource] = []
    for r in rows:
        task = None
        if r.kind == ONLINE_TASK:
            task = task_info(r.task_kind, r.task_id)
            if task is None or not task.visible_to_students:
                continue
        out.append(StudentResource(resource=r, task=task,
                                   seen=r.resource_id in seen))
    return out


def open_resource(resource_id: int, *, student_id: str | None = None
                  ) -> tuple[str, str]:
    """``("file", absolute path)`` or ``("url", link)`` for an item.

    With ``student_id`` the item must be visible to that student and the
    view is recorded; without it the caller must be staff.
    """
    r = _require_resource(resource_id)
    if student_id:
        visible = {s.resource.resource_id
                   for s in resources_for_student(student_id)}
        if r.resource_id not in visible:
            raise ValidationError("That resource is not available to you")
        with _connect() as conn:
            conn.execute(
                "INSERT INTO class_resource_views (resource_id, student_id) "
                "VALUES (?, ?) ON CONFLICT(resource_id, student_id) DO "
                "UPDATE SET last_seen=datetime('now'), times=times+1",
                (r.resource_id, student_id.strip()))
    else:
        _require_staff_reader()
    path = file_path(r)
    if path is not None:
        return "file", str(path)
    if r.url:
        return "url", r.url
    if r.task_kind:
        return "task", f"{r.task_kind} #{r.task_id}"
    raise ValidationError("This item's file is missing from the store")


def view_stats(resource_id: int) -> tuple[int, int, list[str]]:
    """``(seen, audience, not_seen_student_ids)`` for one item."""
    _require_staff_reader()
    r = _require_resource(resource_id)
    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )
    gids = [r.group_id] if r.group_id is not None else [
        g.group_id for g in _cg.list_groups(course_id=r.course_id)]
    audience: set[str] = set()
    for gid in gids:
        audience |= set(_cg.list_members(gid))
    with _connect() as conn:
        seen = {row[0] for row in conn.execute(
            "SELECT student_id FROM class_resource_views WHERE "
            "resource_id=?", (r.resource_id,))}
    return (len(seen & audience), len(audience),
            sorted(audience - seen))


def summary() -> ResourceSummary:
    _require_staff_reader()
    out = ResourceSummary(by_kind={k: 0 for k in KINDS})
    for r in list_resources():
        out.total += 1
        out.published += r.published
        out.drafts += not r.published
        out.files += r.has_file
        out.links += bool(r.url)
        out.tasks += r.kind == ONLINE_TASK
        out.by_kind[r.kind] = out.by_kind.get(r.kind, 0) + 1
        key = r.course_code or f"#{r.course_id}"
        out.by_course[key] = out.by_course.get(key, 0) + 1
        out.store_bytes += r.file_size or 0
    out.orphaned = len(orphaned_resources())
    return out
