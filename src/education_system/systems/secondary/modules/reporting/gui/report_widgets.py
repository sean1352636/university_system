"""Building blocks shared by the report screens.

* :class:`FilterBar` - From / To dates, year group and form, with Run.
* :class:`TableBox` - a table whose columns change with what it shows.
* :func:`run_in_background` - run a slow report off the Tk thread
  (``tk_threads``) and hand the result, or the refusal, back on it.
* :func:`save_csv` - ask for a file name and write a CSV.
* :func:`bar_chart` - a simple bar / line chart in a pop-up (matplotlib is
  imported only when a chart is opened).
* :class:`ReportPage` - a notebook of tables over one report object, each
  tab with Export CSV (and Open pupil where rows are pupils).
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui import tk_threads
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
ERRORS = W.ERRORS
YEARS = ("", *(str(y) for y in P.YEAR_GROUPS))


def run_in_background(widget: tk.Misc, work: Callable[[], Any],
                      done: Callable[[Any], None], failed: Callable[[Exception], None],
                      name: str = "secondary-report") -> None:
    """``done(work())`` on the Tk thread; ``failed(e)`` if *work* raises."""
    def run() -> None:
        try:
            result = work()
        except Exception as e:  # noqa: BLE001 - handed to the screen
            if not isinstance(e, ERRORS):
                logger.exception("Report failed")
            tk_threads.ui(widget, failed, e)
            return
        tk_threads.ui(widget, done, result)

    tk_threads.start_thread(widget, run, name=name)


def save_csv(owner: tk.Misc, initial: str, write: Callable[[str], int],
             title: str = "Export") -> None:
    path = filedialog.asksaveasfilename(parent=owner.winfo_toplevel(), defaultextension=".csv",
                                        filetypes=[("CSV", "*.csv")], initialfile=initial)
    if not path:
        return
    try:
        n = write(path)
    except ERRORS as e:
        messagebox.showerror(title, W.problems(e), parent=owner.winfo_toplevel())
        return
    except OSError as e:
        messagebox.showerror(title, f"Couldn't write the file:\n{e}",
                             parent=owner.winfo_toplevel())
        return
    messagebox.showinfo(title, f"Exported {n} row(s).", parent=owner.winfo_toplevel())


def bar_chart(owner: tk.Misc, title: str, labels: list[str], series: dict[str, list[Any]],
              *, line: bool = False, ylabel: str = "") -> None:
    """A pop-up chart. Imports matplotlib only now."""
    try:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
    except ImportError:
        messagebox.showinfo(title, "Charts need matplotlib, which isn't installed.",
                            parent=owner.winfo_toplevel())
        return
    win, frm = W.dialog(owner, title, size="820x480")
    fig = Figure(figsize=(8, 4.2), dpi=96)
    ax = fig.add_subplot(111)
    xs = list(range(len(labels)))
    n = max(1, len(series))
    for i, (name, vals) in enumerate(series.items()):
        ys = [v if isinstance(v, (int, float)) else 0 for v in vals]
        if line:
            ax.plot(xs, ys, marker="o", label=name)
        else:
            w = 0.8 / n
            ax.bar([x + i * w - 0.4 + w / 2 for x in xs], ys, width=w, label=name)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=45 if len(labels) > 6 else 0, ha="right"
                       if len(labels) > 6 else "center", fontsize=8)
    ax.set_title(title)
    if ylabel:
        ax.set_ylabel(ylabel)
    if len(series) > 1:
        ax.legend()
    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=frm)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)
    ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(6, 0))


class TableBox:
    """A frame holding a table that is rebuilt for each set of headings."""

    def __init__(self, parent: tk.Misc, height: int = 16) -> None:
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="both", expand=True)
        self.height = height
        self.tree: ttk.Treeview | None = None
        self.rows: list[list[Any]] = []
        self.headings: list[str] = []

    def show(self, headings: list[str], rows: list[list[Any]], *,
             tags: Callable[[list[Any]], tuple[str, ...]] | None = None) -> None:
        if self.tree is not None and list(headings) == self.headings:
            self.tree.delete(*self.tree.get_children())
        else:
            for w in self.frame.winfo_children():
                w.destroy()
            cols = [(f"c{i}", h, max(50, min(260, 9 * len(h) + 20)))
                    for i, h in enumerate(headings)]
            self.tree = W.tree(self.frame, cols, height=self.height, tags=W.STANDARD_TAGS,
                               xscroll=len(headings) > 10, minwidth=40)
            self.headings = list(headings)
        self.rows = rows
        for i, r in enumerate(rows):
            self.tree.insert("", "end", iid=str(i), values=[RC.show(v) for v in r],
                             tags=tags(r) if tags else ())

    def selected(self) -> list[Any] | None:
        if self.tree is None:
            return None
        sel = self.tree.selection()
        return self.rows[int(sel[0])] if sel else None


class FilterBar:
    """From / To / Year / Form and Run, remembered in *state*."""

    def __init__(self, parent: tk.Misc, state: dict, on_run: Callable[[], None], *,
                 dates: bool = True, year: bool = True, form: bool = True,
                 default_from: str = "", default_to: str = "") -> None:
        self.state = state
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 6))
        self.bar = bar
        self.vars: dict[str, tk.StringVar] = {}
        if dates:
            for key, label, default in (("from", "From:", default_from),
                                        ("to", "To:", default_to)):
                ttk.Label(bar, text=label).pack(side="left")
                v = tk.StringVar(value=state.get(key, default))
                ttk.Entry(bar, textvariable=v, width=11).pack(side="left", padx=(2, 8))
                self.vars[key] = v
        if year:
            ttk.Label(bar, text="Year:").pack(side="left")
            v = tk.StringVar(value=state.get("year", ""))
            cb = ttk.Combobox(bar, textvariable=v, values=YEARS, state="readonly", width=4)
            cb.pack(side="left", padx=(2, 8))
            self.vars["year"] = v
        if form:
            ttk.Label(bar, text="Form:").pack(side="left")
            v = tk.StringVar(value=state.get("form", ""))
            try:
                forms = ["", *P.form_groups_in_use()]
            except Exception:  # noqa: BLE001 - an empty list still works
                forms = [""]
            ttk.Combobox(bar, textvariable=v, values=forms, width=7).pack(side="left",
                                                                           padx=(2, 8))
            self.vars["form"] = v
        self.run_button = ttk.Button(bar, text="Run", command=on_run)
        self.run_button.pack(side="left", padx=2)

    def get(self) -> dict[str, str]:
        out = {k: v.get().strip() for k, v in self.vars.items()}
        self.state.update(out)
        return out

    def busy(self, on: bool) -> None:
        self.run_button.state(["disabled"] if on else ["!disabled"])


class ReportPage:
    """A titled page: filter bar, a status line and a notebook of tables.

    Subclasses set TITLE, TABS (tab -> section), PUPIL_TABS and implement
    :meth:`compute` (runs off the Tk thread), :meth:`table` and
    :meth:`export`."""

    TITLE = ""
    TABS: dict[str, str] = {}
    PUPIL_TABS: frozenset[str] = frozenset()
    LOG = ""

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.report: Any = None
        ttk.Label(parent, text=self.TITLE, font=("", 16, "bold")).pack(anchor="w")
        self.status = tk.StringVar(value="Choose the filters and press Run.")
        ttk.Label(parent, textvariable=self.status, foreground="#666").pack(anchor="w",
                                                                            pady=(0, 6))
        self.build_filters(parent)
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.names = list(self.TABS)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.names}
        for n in self.names:
            self.book.add(self.tabs[n], text=n)
        self.boxes: dict[str, TableBox] = {}
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.names else self.names[0]
        self.book.select(self.names.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()
        self.run()

    # ── to override ──────────────────────────────────────────────────

    def build_filters(self, parent: ttk.Frame) -> None:
        self.filters = FilterBar(parent, self.state, self.run)

    def gather(self) -> dict[str, str]:
        """Read the filters (on the Tk thread; compute() runs off it)."""
        return self.filters.get()

    def compute(self, f: dict[str, str]) -> Any:
        """Build the report from *f*. Runs off the Tk thread: no Tk calls."""
        raise NotImplementedError

    def table(self, section: str) -> tuple[list[str], list[list[Any]]]:
        raise NotImplementedError

    def export(self, path: str, section: str) -> int:
        raise NotImplementedError

    def describe(self) -> str:
        return ""

    def extra_buttons(self, name: str, bar: ttk.Frame) -> None:
        """Add buttons to a tab's toolbar."""

    def row_tags(self, name: str, row: list[Any]) -> tuple[str, ...]:
        return ()

    def pupil_text(self, pupil_id: int) -> str | None:
        """Text for "Pupil detail" (drill down), or None to open the profile only."""
        return None

    # ── machinery ────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        if isinstance(e, ERRORS):
            messagebox.showerror(title, W.problems(e), parent=self._top())
        else:
            messagebox.showerror(title, f"Something went wrong: {e}", parent=self._top())

    def _on_tab(self, _e=None) -> None:
        name = self.names[self.book.index(self.book.select())]
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            self._build_tab(name)
        self._fill(name)

    def _build_tab(self, name: str) -> None:
        tab = self.tabs[name]
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Export CSV…", command=lambda: self._export(name)).pack(
            side="left", padx=2)
        if name in self.PUPIL_TABS:
            ttk.Button(bar, text="Open pupil", command=lambda: self._open(name)).pack(
                side="left", padx=2)
            ttk.Button(bar, text="Pupil detail", command=lambda: self._detail(name)).pack(
                side="left", padx=2)
        self.extra_buttons(name, bar)
        self.boxes[name] = TableBox(tab)

    def _fill(self, name: str) -> None:
        if self.report is None or name not in self.boxes:
            return
        try:
            head, rows = self.table(self.TABS[name])
        except ERRORS as e:
            self.status.set(W.problems(e).replace("\n", " "))
            return
        box = self.boxes[name]
        box.show(head, rows, tags=lambda r: self.row_tags(name, r))
        if name in self.PUPIL_TABS and box.tree is not None:
            box.tree.bind("<Double-1>", lambda _e: self._open(name))

    def refresh_tabs(self) -> None:
        for name in self._built:
            self._fill(name)

    def run(self) -> None:
        f = self.gather()
        self.filters.busy(True)
        self.status.set("Working…")

        def done(report: Any) -> None:
            self.filters.busy(False)
            self.report = report
            self.status.set(self.describe())
            self.refresh_tabs()

        def failed(e: Exception) -> None:
            self.filters.busy(False)
            self.status.set("Not run - " + W.problems(e).replace("\n", " "))
            self._err(self.TITLE, e)

        run_in_background(self.parent, lambda: self.compute(f), done, failed,
                          name=f"secondary-{self.LOG or 'report'}")

    def _export(self, name: str) -> None:
        if self.report is None:
            messagebox.showinfo(self.TITLE, "Run the report first.", parent=self._top())
            return
        section = self.TABS[name]
        save_csv(self.parent, f"{self.LOG or 'report'}_{section}.csv",
                 lambda path: self.export(path, section), self.TITLE)

    def _pupil_id(self, name: str) -> int | None:
        row = self.boxes[name].selected() if name in self.boxes else None
        if not row:
            messagebox.showinfo(self.TITLE, "Select a pupil first.", parent=self._top())
            return None
        p = P.find_by_reference(str(row[0]))
        return p.pupil_id if p else None

    def _open(self, name: str) -> None:
        pid = self._pupil_id(name)
        if pid is not None and self.open_pupil:
            self.open_pupil(pid)

    def _detail(self, name: str) -> None:
        pid = self._pupil_id(name)
        if pid is None:
            return
        try:
            text = self.pupil_text(pid)
        except ERRORS as e:
            self._err(self.TITLE, e)
            return
        if text:
            W.text_window(self.parent, f"{self.TITLE} - pupil", text)
        elif self.open_pupil:
            self.open_pupil(pid)
