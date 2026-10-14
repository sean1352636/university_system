"""Documents — the files behind an apprentice's record, for everyone involved.

One screen for every role. What each actor sees is decided by the
service, not here: an apprentice their own documents, an employer their
apprentices' and their organisation's, a tutor their caseload's, an
administrator everything, and the end-point assessor the EPA category
only. The buttons follow the same permissions, so nobody is offered an
action that would only be refused.

Documents are grouped by category. Each row is the latest version;
earlier versions are kept and reachable through Version history, because
"which version did the employer sign?" gets asked at audit. Expired and
expiring documents are coloured, and agreements show how far through
their three signatures they are.
"""

from __future__ import annotations

import logging
import tkinter as tk
import webbrowser
from collections.abc import Callable
from datetime import date
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records.documents import (
    Document,
    format_size,
)
from education_system.systems.apprenticeships.domain.records.signatures import SignOff
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.interfaces.gui.windows.shared import (
    signatures as signature_window,
)
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    document_service,
    signature_service,
)

logger = logging.getLogger(__name__)

# (key, heading, width[, anchor]); "#0" is the tree column holding the
# category group and the document title.
DOCUMENT_COLUMNS = (
    ("owner", "Apprentice / employer", 210),
    ("version", "Version", 70, "e"),
    ("approval", "Approval", 90),
    ("expires", "Expires", 100),
    ("flag", "Expiry", 110),
    ("signatures", "Signatures", 190),
    ("uploaded", "Uploaded", 140),
    ("by", "By", 110),
    ("size", "Size", 80, "e"),
)

VERSION_COLUMNS = (
    ("version", "Version", 70, "e"),
    ("file", "File uploaded", 260),
    ("uploaded", "Uploaded", 150),
    ("by", "By", 120),
    ("approval", "Approval", 100),
    ("size", "Size", 90, "e"),
    ("current", "Current", 80),
)

_CHECKLIST_LABELS = dict(config.COMPLIANCE_DOCUMENTS)
_CHECKLIST_KEYS = {label: key for key, label in config.COMPLIANCE_DOCUMENTS}


def render(gui: Any) -> None:
    frame = gui.clear()
    epao = gui.actor.role == config.END_POINT_ASSESSOR
    widgets.heading(
        frame,
        "EPA Documents" if epao else "Documents",
        subtitle=(
            "The assessment paperwork for the apprentices you assess."
            if epao else
            "Uploaded files, grouped by category. Every version is kept; expired and "
            "expiring documents are coloured."
        ),
    )
    ok, counts = widgets.guard(lambda: document_service.document_counts(gui.actor))
    if not ok:
        return
    widgets.kpi_row(frame, [
        ("Documents", counts["total"]),
        ("Awaiting approval", counts["pending"]),
        (f"Expiring within {config.DOCUMENT_EXPIRY_WARNING_DAYS} days", counts["expiring"]),
        ("Expired", counts["expired"]),
    ])
    _Browser(gui, frame)


class _Browser:
    """The filter bar, the grouped list and the actions on it."""

    def __init__(self, gui: Any, parent: Any) -> None:
        self.gui = gui
        self.actor = gui.actor
        self.documents: dict[int, Document] = {}
        self.people = self._apprentice_names()

        specs: list[tuple] = [
            ("category", "Category", "combo", document_service.categories_for(self.actor)),
        ]
        if self.people:
            specs.append(("apprentice", "Apprentice", "combo", list(self.people)))
        specs += [
            ("approval_status", "Approval", "combo", config.DOCUMENT_APPROVAL_STATUSES),
            ("search", "Search", "entry"),
            ("expiring_only", "Expiring only", "check"),
            ("history", "Old versions too", "check"),
        ]
        self.filters = widgets.FilterBar(parent, specs, self.reload)
        widgets.button_bar(parent, self._buttons())
        self.tree = _grouped_tree(parent)
        self.tree.bind("<Double-1>", lambda _e: self.open())
        self.count_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.count_var, foreground=config.MUTED_FG).pack(
            anchor="w", pady=(4, 0)
        )
        self.reload()

    # ── Loading ─────────────────────────────────────────────────────

    def reload(self) -> None:
        values = self.filters.values()
        apprentice_id = self.people.get(values.pop("apprentice", ""), None)
        history = values.pop("history", False)
        ok, rows = widgets.guard(lambda: document_service.list_documents(
            self.actor, apprentice_id=apprentice_id, current_only=not history, **values,
        ))
        rows = rows if ok and rows else []
        signoffs: dict[int, SignOff] = {}
        if rows:
            _, signoffs = widgets.guard(
                lambda: signature_service.signoffs_for_documents(self.actor, rows)
            )
        self.documents = {d.document_id: d for d in rows}
        _fill(self.tree, rows, signoffs or {})
        plural = "document" if len(rows) == 1 else "documents"
        self.count_var.set(f"{len(rows)} {plural}")

    def _apprentice_names(self) -> dict[str, int]:
        """Apprentice filter options; none for an apprentice, who has only themselves."""
        if self.actor.role == config.APPRENTICE:
            return {}
        try:
            people = apprentice_service.list_apprentices(self.actor)
        except Exception:
            logger.debug("No apprentice filter for %s", self.actor.username, exc_info=True)
            return {}
        return {s.full_name: s.apprentice.apprentice_id for s in people}

    # ── Actions ─────────────────────────────────────────────────────

    def _buttons(self) -> list[tuple[str, Callable[[], None]]]:
        can = self.actor.can
        buttons: list[tuple[str, Callable[[], None]]] = []
        if can("document.upload"):
            buttons.append(("Upload…", self.upload))
        buttons += [("Open", self.open), ("Save a copy…", self.save_copy)]
        if can("document.upload"):
            buttons.append(("New version…", self.new_version))
        buttons += [("Version history", self.versions), ("Signatures…", self.signatures)]
        if can("document.approve"):
            buttons += [("Approve", self.approve), ("Reject…", self.reject),
                        ("Edit details…", self.edit)]
        return buttons

    def selected(self, action: str) -> Document | None:
        chosen = self.tree.selection()
        ident = chosen[0] if chosen else ""
        if not ident.isdigit():
            widgets.inform(f"Select a document first to {action}.", title="Nothing selected")
            return None
        return self.documents.get(int(ident))

    def upload(self) -> None:
        ok, owners = widgets.guard(lambda: document_service.upload_owners(self.actor))
        if not ok:
            return
        if not owners:
            widgets.warn("There is no record you can file a document against yet.")
            return
        path = _ask_file(self.gui, "Choose a file to upload")
        if path is None:
            return
        by_label = {o["label"]: o for o in owners}
        fields: list[dict[str, Any]] = [
            {"key": "owner", "label": "Belongs to", "kind": "combo", "required": True,
             "options": list(by_label), "value": next(iter(by_label))},
            {"key": "category", "label": "Category", "kind": "combo", "required": True,
             "options": config.DOCUMENT_CATEGORIES, "value": "Other"},
            {"key": "title", "label": "Title", "value": path.stem},
            {"key": "expiry_date", "label": "Expires",
             "help": "YYYY-MM-DD, for anything that lapses — right-to-work evidence, say."},
        ]
        if self.actor.is_provider:
            fields.append({
                "key": "checklist", "label": "Evidences checklist item", "kind": "combo",
                "options": ["", *_CHECKLIST_KEYS],
                "help": "Links the file to an item on the compliance checklist.",
            })

        def save(values: dict[str, Any]) -> object:
            owner = by_label[values["owner"]]
            return document_service.upload_document(
                self.actor, path,
                category=values["category"],
                apprentice_id=owner["apprentice_id"],
                employer_id=owner["employer_id"],
                title=values.get("title"),
                expiry_date=values.get("expiry_date"),
                checklist_key=_CHECKLIST_KEYS.get(values.get("checklist") or ""),
            )

        dialog = widgets.FormDialog(
            self.gui.root, "Upload a document", fields, save, save_label="Upload",
            intro=f"{path.name} — {format_size(path.stat().st_size)}. A copy is kept in the "
                  "document store; the original stays where it is."
                  + ("" if self.actor.is_provider else
                     " Your provider will check it before it is approved."),
        )
        if dialog.saved:
            self._refresh()

    def new_version(self) -> None:
        document = self.selected("add a new version")
        if document is None:
            return
        path = _ask_file(self.gui, f"New version of “{document.title}”")
        if path is None:
            return
        fields = [
            {"key": "title", "label": "Title", "value": document.title},
            {"key": "expiry_date", "label": "Expires", "value": document.expiry_date or "",
             "help": "YYYY-MM-DD; clear it if the new version does not lapse."},
        ]

        def save(values: dict[str, Any]) -> object:
            return document_service.upload_new_version(
                self.actor, document.document_id, path,
                title=values.get("title"), expiry_date=values.get("expiry_date") or "",
            )

        dialog = widgets.FormDialog(
            self.gui.root, "Upload a new version", fields, save, save_label="Upload",
            intro=f"Version {document.version + 1} of “{document.title}”, from {path.name}. "
                  "Earlier versions are kept, and any signatures on this one stay with it — "
                  "the new version needs signing afresh.",
        )
        if dialog.saved:
            self._refresh()

    def open(self) -> None:
        document = self.selected("open it")
        if document is not None:
            _open_document(self.gui, document)

    def save_copy(self) -> None:
        document = self.selected("save a copy")
        if document is not None:
            _save_copy(self.gui, document)

    def versions(self) -> None:
        document = self.selected("see its versions")
        if document is not None:
            _version_window(self.gui, document)

    def signatures(self) -> None:
        document = self.selected("see its signatures")
        if document is None:
            return
        ok, state = widgets.guard(
            lambda: signature_service.signoff(self.actor, "document", document.document_id)
        )
        if not ok:
            return
        if not state.required:
            widgets.inform(
                f"{document.category} documents do not need signing. Learning agreements "
                "and commitment statements do.", title="No signatures needed",
            )
            return
        signature_window.show_signoff(self.gui, state, on_signed=self._refresh)

    def approve(self) -> None:
        document = self.selected("approve it")
        if document is None or not widgets.confirm(f"Approve “{document.title}”?"):
            return
        ok, _ = widgets.guard(
            lambda: document_service.approve_document(self.actor, document.document_id)
        )
        if ok:
            self._refresh()

    def reject(self) -> None:
        document = self.selected("reject it")
        if document is None:
            return
        reason = widgets.ask_reason(
            f"Why is “{document.title}” being rejected? The uploader sees this, so say what "
            "needs to change."
        )
        if not reason:
            return
        ok, _ = widgets.guard(lambda: document_service.reject_document(
            self.actor, document.document_id, reason=reason
        ))
        if ok:
            self._refresh()

    def edit(self) -> None:
        document = self.selected("edit its details")
        if document is None:
            return
        fields: list[dict[str, Any]] = [
            {"key": "title", "label": "Title", "required": True, "value": document.title},
            {"key": "expiry_date", "label": "Expires", "value": document.expiry_date or "",
             "help": "YYYY-MM-DD, or blank if it does not lapse."},
        ]
        if document.apprentice_id is not None:
            fields.append({
                "key": "checklist", "label": "Evidences checklist item", "kind": "combo",
                "options": ["", *_CHECKLIST_KEYS],
                "value": _CHECKLIST_LABELS.get(document.checklist_key or "", ""),
            })

        def save(values: dict[str, Any]) -> object:
            payload = {"title": values.get("title"), "expiry_date": values.get("expiry_date")}
            if "checklist" in values:
                payload["checklist_key"] = _CHECKLIST_KEYS.get(values.get("checklist") or "")
            return document_service.update_details(self.actor, document.document_id, payload)

        if widgets.FormDialog(self.gui.root, "Edit document details", fields, save).saved:
            self._refresh()

    def _refresh(self) -> None:
        # The KPI tiles above the list count what just changed too.
        render(self.gui)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _grouped_tree(parent: Any) -> ttk.Treeview:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    tree = ttk.Treeview(
        holder, columns=[c[0] for c in DOCUMENT_COLUMNS], show="tree headings",
        selectmode="browse",
    )
    tree.heading("#0", text="Document")
    tree.column("#0", width=300, stretch=True)
    for spec in DOCUMENT_COLUMNS:
        tree.heading(spec[0], text=spec[1])
        tree.column(spec[0], width=spec[2], anchor=spec[3] if len(spec) > 3 else "w")
    for name, colour in config.RAG_COLOURS.items():
        tree.tag_configure(name, background=colour)
    tree.tag_configure("group", font=("", 10, "bold"))
    tree.tag_configure("old", foreground=config.MUTED_FG)
    bar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=bar.set)
    tree.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    return tree


def _fill(tree: ttk.Treeview, rows: list[Document], signoffs: dict[int, SignOff]) -> None:
    tree.delete(*tree.get_children())
    today = date.today()
    groups: dict[str, list[Document]] = {}
    for document in rows:
        groups.setdefault(document.category, []).append(document)
    order = {c: i for i, c in enumerate(config.DOCUMENT_CATEGORIES)}
    for category in sorted(groups, key=lambda c: order.get(c, len(order))):
        members = groups[category]
        node = tree.insert(
            "", "end", iid=f"group:{category}", text=f"{category} ({len(members)})",
            open=True, tags=("group",),
        )
        for d in members:
            state = signoffs.get(d.document_id)
            tags = [t for t in (d.rag(today),) if t]
            if d.is_superseded:
                tags.append("old")
            tree.insert(node, "end", iid=str(d.document_id), text=d.title, tags=tuple(tags),
                        values=[_cell(v) for v in (
                            d.owner_label + (" (organisation)" if d.is_employer_document else ""),
                            f"v{d.version}" + ("" if d.is_current else " (old)"),
                            d.approval_status, d.expiry_date, d.expiry_flag(today),
                            state.summary if state and state.required else None,
                            d.uploaded_at, d.uploaded_by, d.size_label,
                        )])


def _cell(value: Any) -> str:
    return config.EMPTY_CELL if value in (None, "") else str(value)


def _ask_file(gui: Any, title: str) -> Path | None:
    patterns = " ".join(f"*{e}" for e in config.DOCUMENT_EXTENSIONS)
    chosen = filedialog.askopenfilename(
        parent=gui.root, title=title,
        filetypes=[("Documents and images", patterns), ("All files", "*")],
    )
    return Path(chosen) if chosen else None


def _open_document(gui: Any, document: Document) -> None:
    """Open the stored file with whatever the desktop uses for it.

    The platform has no shared open-file helper, so this goes through the
    browser, which hands the file to the registered viewer. Where nothing
    is registered — a bare Linux box — the user is pointed at Save a copy.
    """
    ok, path = widgets.guard(lambda: document_service.file_path(gui.actor, document.document_id))
    if not ok:
        return
    try:
        opened = webbrowser.open(path.as_uri())
    except Exception:
        logger.debug("Could not open %s", path, exc_info=True)
        opened = False
    if not opened:
        widgets.warn(
            "Nothing on this computer is set up to open it. Use Save a copy… and open the "
            "copy instead.", title="Could not open",
        )


def _save_copy(gui: Any, document: Document) -> None:
    destination = filedialog.asksaveasfilename(
        parent=gui.root, title=f"Save a copy of “{document.title}”",
        initialfile=document.original_filename, defaultextension=document.extension,
    )
    if not destination:
        return
    # The dialog has already asked about replacing an existing file.
    ok, saved = widgets.guard(lambda: document_service.save_copy(
        gui.actor, document.document_id, destination, overwrite=True
    ))
    if ok:
        widgets.inform(f"Saved to {saved}.", title="Copy saved")


def _version_window(gui: Any, document: Document) -> None:
    ok, versions = widgets.guard(
        lambda: document_service.version_history(gui.actor, document.document_id)
    )
    if not ok:
        return
    win = widgets.open_window(gui, f"Versions — {document.title}", geometry="1000x420")
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    widgets.heading(
        body, document.title,
        subtitle=f"{document.category} · {document.owner_label}. Newest first; every version "
                 "is kept.",
    )
    by_id = {v.document_id: v for v in versions}
    table: widgets.DataTable | None = None

    def chosen(action: str) -> Document | None:
        ident = table.require_selection_int(action) if table else None
        return by_id.get(ident) if ident is not None else None

    def open_version() -> None:
        version = chosen("open it")
        if version is not None:
            _open_document(gui, version)

    def save_version() -> None:
        version = chosen("save a copy")
        if version is not None:
            _save_copy(gui, version)

    widgets.button_bar(body, [
        ("Open", open_version), ("Save a copy…", save_version), ("Close", win.destroy),
    ])
    table = widgets.DataTable(body, VERSION_COLUMNS, on_activate=lambda _i: open_version())
    table.populate(
        versions,
        lambda v: (v.version, v.original_filename, v.uploaded_at, v.uploaded_by,
                   v.approval_status, v.size_label, v.is_current),
        identity=lambda v: v.document_id,
        tag=lambda v: None if v.is_current else "muted",
        noun="version",
    )
