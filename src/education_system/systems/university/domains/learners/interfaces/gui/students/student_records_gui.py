# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
from contextlib import ExitStack
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close

# Import i18n
from education_system.systems.university.infrastructure.i18n import get_text as _t

# Import database connection
from education_system.systems.university.infrastructure.database.db import (
    get_db_connection,
    get_connection,
    reuse_connection,
    transaction,
)
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers — single source of truth for student-row loading and
# column access.
#
# Pre-8.117.16 this file had two near-identical loaders (``view_students``,
# ``view_students_in_window``) and two near-identical double-click handlers.
# The records list also drilled into ``students[0]``..``students[10]``
# positionally, which broke whenever the schema gained a column. Both
# loaders now delegate to ``_load_students_into`` and ``show_student_details``
# uses ``_row_get`` for column access — so adding a column is no longer a
# silent risk.
# ---------------------------------------------------------------------------

def _configure_status_tags(tree) -> None:
    """Give the status tags their colours. Colour is a hint, never the only
    signal — the Status column carries the actual value."""
    try:
        tree.tag_configure("status_inactive", foreground="#a05000")
        tree.tag_configure("status_unknown", foreground="#777777")
    except tk.TclError:
        logger.debug("Could not configure status tags", exc_info=True)


def _status_tag(status) -> str:
    """Row tag for the records list.

    A withdrawn or suspended student used to be indistinguishable from an
    active one in this list, which is precisely where anyone looks first.
    """
    value = (status or "").strip().lower()
    if value == "active":
        return "status_active"
    if not value:
        return "status_unknown"
    return "status_inactive"


# Canonical column list for the records list view. Matches what the tree
# treeview headers expect (id / full_name / email / course / reg_date).
_LIST_COLS_SQL = (
    "student_id, first_name, middle_name, last_name, "
    "email_address, course, status, registration_datetime"
)


def _row_get(row, key, default=None):
    """Read a column from a sqlite3 row by name with a graceful fallback.

    ``sqlite3.Row`` doesn't expose ``.get`` so a missing column raises
    IndexError. This wrapper turns that into the supplied default so
    we can read newer columns without breaking on older databases."""
    try:
        return row[key]
    except (IndexError, KeyError, TypeError):
        return default


#: Columns the free-text filter searches. Kept to what the list displays, so
#: a hit is always visible in the row it matched.
_QUICK_SEARCH_COLUMNS = ("student_id", "first_name", "middle_name", "last_name",
                         "email_address", "course", "status")

#: Rows per page. The list previously issued an unbounded SELECT and rendered
#: every student into the tree; that is fine for a handful and degrades badly
#: as the roll grows, because Tk pays for each row whether or not it is on
#: screen.
DEFAULT_PAGE_SIZE = 100


def _load_students_into(self, tree, *, search_term=None, search_field=None,
                        quick_search=None, limit=None, offset=0):
    """Single canonical loader for the records list treeview.

    Used by ``view_students`` (legacy panel hook used by
    ``student_crud_gui`` after CRUD), ``view_students_in_window`` (the
    Toplevel records window) and the inline search filter. Always
    selects an explicit named column list — never ``SELECT *`` — so
    schema additions can't shift indices.

    *search_term* + *search_field*, when given, narrow the result set
    server-side. Field is validated against an allow-list before being
    interpolated into the SQL because parameter substitution doesn't
    apply to identifiers.

    *quick_search* is the free-text box above the list: it matches any of
    :data:`_QUICK_SEARCH_COLUMNS`. It is applied in SQL rather than by
    filtering the loaded rows, so a search still reaches students on other
    pages — an in-memory filter would silently only ever search the page you
    happen to be looking at.

    *limit* / *offset* page the query. Returns the total number of matching
    rows (ignoring the page window) so a caller can render a pager, or 0 when
    the tree has gone away."""
    if tree is None:
        return 0
    try:
        if not tree.winfo_exists():
            return 0
    except tk.TclError:
        return 0

    # Clear existing rows
    try:
        for item in tree.get_children():
            tree.delete(item)
    except tk.TclError:
        return 0

    conn = None
    try:
        conn = get_db_connection()
        if conn is None:
            messagebox.showerror(
                _t("common.error"),
                _t("student.failed_load_student_data",
                   error="database connection unavailable"),
            )
            return 0

        # Default ordering (by surname, forename); search overrides
        # the WHERE clause but keeps the same SELECT list + ORDER BY.
        params = []
        where = ""
        if self.auth and not self.auth.check_permission('view_any_student'):
            where = "WHERE student_id = ?"
            params.append(self.auth.current_user.get('student_id'))
        elif search_term and search_field:
            allowed = {
                'first_name', 'last_name', 'student_id',
                'course', 'email_address', 'status',
            }
            if search_field in allowed:
                safe = validate_identifier(search_field, "column")
                if search_field == 'student_id':
                    where = f"WHERE [{safe}] = ?"
                    params.append(search_term)
                else:
                    where = f"WHERE LOWER([{safe}]) LIKE LOWER(?)"
                    params.append(f"%{search_term}%")

        # Free-text box: OR across the displayed columns. Column names come
        # from a module constant, never from input, and each is put through
        # validate_identifier as well.
        term = (quick_search or "").strip()
        if term:
            clauses = []
            for column in _QUICK_SEARCH_COLUMNS:
                safe = validate_identifier(column, "column")
                clauses.append(f"LOWER(COALESCE([{safe}], '')) LIKE LOWER(?)")
                params.append(f"%{term}%")
            joined = " OR ".join(clauses)
            where = f"{where} AND ({joined})" if where else f"WHERE ({joined})"

        cursor = conn.cursor()
        # Total before paging, so the pager can say "of N".
        # db-audit: ignore[DBW001] - where is built from validated identifiers
        cursor.execute(f"SELECT COUNT(*) FROM students {where}", params)
        total = cursor.fetchone()[0] or 0

        sql = (
            f"SELECT {_LIST_COLS_SQL} FROM students "
            f"{where} ORDER BY last_name, first_name"
        )
        page_params = list(params)
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            page_params.extend([int(limit), int(offset or 0)])
        cursor.execute(sql, page_params)

        for r in cursor.fetchall():
            # Tuple-positional but bound to our explicit SELECT list,
            # not to the underlying schema — order matches _LIST_COLS_SQL.
            sid, first, middle, last, email, course, status, reg = r
            full_name = " ".join(
                p for p in (first, middle, last) if p
            ).strip() or sid
            tree.insert(
                "", tk.END,
                values=(
                    sid,
                    full_name,
                    email or "",
                    course or "",
                    status or "",
                    (reg[:10] if reg else "N/A"),
                ),
                tags=(_status_tag(status),),
            )
        return total
    except tk.TclError:
        return 0
    except Exception as exc:
        messagebox.showerror(
            _t("common.error"),
            _t("student.failed_load_student_data", error=str(exc)),
        )
        return 0
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

def show_student_records(self):
    """Show student records interface inside the main GUI's content
    area when a workspace is available, or as a Toplevel otherwise.

    Pre-8.117.38 always opened a 1400×800 ``tk.Toplevel(self.root)``.
    User asked for it to fit inside the main content section instead.
    Now goes through ``UnifiedManagementGUI.open_in_workspace``
    (8.117.18 mechanism) when the post-login workspace notebook is
    alive — Library uses Toplevel-style sizing (8.117.34), but the
    Student Records list view fits a tab-frame nicely (less dense
    than Library's notebook-of-notebooks)."""
    # Check if current user is a student - if so, show only their own record
    if self.auth and self.auth.current_user:
        user_role = self.auth.current_user.get('role', '')

        # If student, directly show their own record
        if user_role == 'student':
            student_id = self.auth.current_user.get('student_id') or self.auth.current_user.get('username')
            if student_id:
                print(f"✅ Student user '{student_id}' viewing their own record")
                self.show_student_details(student_id)
                return
            else:
                messagebox.showerror(_t("common.error"), _t("student.unable_retrieve_id"))
                return

    title = _t("student.records_management")

    def _build(host, close_action):
        """Construct the records UI inside *host*. *close_action* is
        a callable supplied by the caller — calls ``nb.forget(host)``
        when ``host`` is a workspace tab frame, ``host.destroy()``
        when it's a Toplevel inner frame."""
        _build_student_records(self, host, close_action)

    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        # Workspace path: tab inside the main GUI's content notebook.
        # ``open_in_workspace`` returns the new tab Frame; the
        # close-action removes that tab.
        nb = getattr(self, "workspace_notebook", None)
        def _close_tab(host=None, _nb=nb):
            # Destroy the tab's widgets too — forget() alone left the whole
            # Student Records screen alive under the notebook.
            from education_system.platform.delivery.gui.portal_dismiss import forget_tab
            if _nb is not None and host is not None:
                forget_tab(_nb, host)
        # Builder receives the tab frame + the close action bound
        # to it.
        opener(title, lambda host: _build(host, lambda: _close_tab(host)))
        return

    # Fallback: classic Toplevel — same shape as pre-8.117.38.
    records_window = tk.Toplevel(self.root)
    _install_clean_close(records_window)
    records_window.title(title)
    records_window.geometry("1400x800")
    records_window.transient(self.root)
    main_outer = ttk.Frame(records_window)
    main_outer.pack(fill=tk.BOTH, expand=True)
    _build(main_outer, lambda: records_window.destroy())


def _build_student_records(self, host, close_action):
    """Internal: build the records list UI inside *host*. Refactored
    out of ``show_student_records`` (8.117.38) so the same widget
    construction works whether *host* is a workspace tab Frame or a
    Toplevel inner frame.

    *close_action* is a no-arg callable that closes the host —
    forgetting the workspace tab or destroying the Toplevel."""
    main_frame = ttk.Frame(host, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(main_frame, text=_t("student.records_management"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Action buttons frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Button(button_frame, text=_t("student.create_student"),
              command=self.create_student_dialog).pack(side=tk.LEFT, padx=5)
    if self.auth and self.auth.check_permission('delete_any_student'):
        ttk.Button(button_frame,
                   text=_t("student.delete_student", default="Delete Student"),
                   command=lambda: self.delete_selected_student(tree)).pack(
            side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("student.export_data"),
              command=self.export_data_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.refresh"),
              command=lambda: self.view_students_in_window(tree)).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.close"),
              command=close_action).pack(side=tk.RIGHT, padx=5)

    # Inline search bar — replaces the modal search dialog. Filters the
    # currently-loaded rows in-memory on KeyRelease so the result set
    # narrows as the user types. The legacy ``search_students_dialog``
    # is still defined for any external caller but the records window
    # no longer surfaces it as a button.
    search_bar = ttk.Frame(main_frame)
    search_bar.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(search_bar, text=_t("student.search_term")).pack(side=tk.LEFT, padx=(0, 6))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_bar, textvariable=search_var, width=40)
    search_entry.pack(side=tk.LEFT)
    status_var = tk.StringVar(value="")
    ttk.Label(search_bar, textvariable=status_var,
              foreground='#555555').pack(side=tk.LEFT, padx=(12, 0))
    ttk.Button(search_bar, text="✕",
               command=lambda: search_var.set(""),
               width=3).pack(side=tk.LEFT, padx=(6, 0))

    # Create student list interface
    records_frame = ttk.LabelFrame(main_frame, text=_t("student.records"), padding="10")
    records_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    # Create treeview in this window
    tree_frame = ttk.Frame(records_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (_t("student.col_id"), _t("student.col_name"), _t("student.col_email"), _t("student.col_course"), _t("student.col_status", default="Status"), _t("student.col_reg_date"))
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=30)

    # Configure columns + bind heading-clicks for ascending/descending
    # sort by column. Standard ttk pattern — store the most-recent
    # sort direction per column so a second click reverses.
    sort_state = {"col": None, "reverse": False}

    def _sort_by(col):
        try:
            data = [
                (tree.set(k, col), k) for k in tree.get_children("")
            ]
            # Numeric-aware sort: try to coerce so "10" sorts after "9"
            def _key(pair):
                v = pair[0]
                try:
                    return (0, float(v))
                except (TypeError, ValueError):
                    return (1, (v or "").lower())
            reverse = sort_state["col"] == col and not sort_state["reverse"]
            data.sort(key=_key, reverse=reverse)
            for index, (_v, k) in enumerate(data):
                tree.move(k, "", index)
            sort_state["col"] = col
            sort_state["reverse"] = reverse
            # Visual marker so the user can see sort state
            for c in columns:
                tree.heading(c, text=c)
            tree.heading(col, text=f"{col}  {'▼' if reverse else '▲'}")
        except tk.TclError:
            pass

    # Per-column widths sized to the actual content. Pre-8.117.40
    # used a uniform 200px on every column = 1000px total, which
    # overflowed the workspace tab's ~900px width — the table got
    # cut off and the horizontal scrollbar never showed (see
    # below). Tighter defaults fit inside the tab; ``stretch=True``
    # (the ttk default) means any extra width gets distributed.
    column_widths = {
        _t("student.col_id"):       90,
        _t("student.col_name"):     220,
        _t("student.col_email"):    240,
        _t("student.col_course"):   80,
        _t("student.col_status"):   110,
        _t("student.col_reg_date"): 100,
    }
    for col in columns:
        tree.heading(col, text=col, command=lambda c=col: _sort_by(c))
        tree.column(col, width=column_widths.get(col, 150),
                    minwidth=60, stretch=True, anchor="w")

    # Tree + scrollbars laid out via grid. Pre-8.117.40 packed them
    # with side=LEFT/RIGHT/BOTTOM in that order — the tree's
    # ``fill=BOTH, expand=True`` consumed the entire tree_frame
    # before either scrollbar got a chance to pack, so both
    # scrollbars rendered at zero width and the user couldn't
    # scroll horizontally to see the cut-off columns. Grid keeps
    # them in their assigned cells regardless of pack order.
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    tree.grid(row=0, column=0, sticky="nsew")
    v_scrollbar.grid(row=0, column=1, sticky="ns")
    h_scrollbar.grid(row=1, column=0, sticky="ew")
    tree_frame.rowconfigure(0, weight=1)
    tree_frame.columnconfigure(0, weight=1)

    # Bind double-click event
    _configure_status_tags(tree)
    tree.bind('<Double-1>', lambda event: self.on_student_double_click_window(event, tree))

    # Right-click cross-jumps to every module keyed by student_id.
    # The student record is the canonical hub — for the first time this
    # tree points outward (Email Manager, Finance, Library, Audit Log,
    # Loyalty / Careers snapshots, Course Mgmt) instead of just being
    # the destination everything else jumps to.
    try:
        from education_system.systems.university.domains.learners.interfaces.gui.students._cross_links import (
            attach_cross_link_menu,
        )
        attach_cross_link_menu(tree, parent=host, app=self)
    except Exception:
        logger.debug("student records cross-link menu unavailable", exc_info=True)

    # Store reference to this window's tree
    self.student_tree = tree

    # Load student data
    self.view_students_in_window(tree)

    # ── Paging + server-side quick search ───────────────────────────
    # The filter runs in SQL, not over the loaded rows: with a page window
    # an in-memory filter would only ever search the page on screen, which
    # looks like "that student doesn't exist".
    state = {"page": 0, "size": DEFAULT_PAGE_SIZE, "total": 0, "after": None}
    self._records_pager = state          # so refreshes can reuse the page

    pager = ttk.Frame(main_frame)
    pager.pack(fill=tk.X, pady=(4, 0))
    prev_btn = ttk.Button(pager, text="◀ Prev", width=9)
    prev_btn.pack(side=tk.LEFT)
    next_btn = ttk.Button(pager, text="Next ▶", width=9)
    next_btn.pack(side=tk.LEFT, padx=(6, 12))
    page_var = tk.StringVar(value="")
    ttk.Label(pager, textvariable=page_var).pack(side=tk.LEFT)

    ttk.Label(pager, text=_t("student.rows_per_page", default="Rows per page:")).pack(
        side=tk.RIGHT, padx=(8, 4))
    size_combo = ttk.Combobox(pager, width=6, state="readonly",
                              values=("50", "100", "250", "500"))
    size_combo.set(str(DEFAULT_PAGE_SIZE))
    size_combo.pack(side=tk.RIGHT)

    def _pages():
        size = max(1, state["size"])
        return max(1, -(-state["total"] // size))   # ceil

    def _load_page():
        # Called as a plain function, like every other use in this module:
        # ``_load_students_into`` is not among the names main_gui patches onto
        # UnifiedManagementGUI, so ``self._load_students_into`` raised
        # AttributeError and the Student Records tab failed to build.
        term = (search_var.get() or "").strip()
        state["total"] = _load_students_into(
            self, tree, quick_search=term or None,
            limit=state["size"], offset=state["page"] * state["size"]) or 0
        # A search (or a deletion) can leave us past the end.
        if state["page"] >= _pages():
            state["page"] = _pages() - 1
            state["total"] = _load_students_into(
                self, tree, quick_search=term or None,
                limit=state["size"], offset=state["page"] * state["size"]) or 0
        shown = len(tree.get_children(""))
        first = state["page"] * state["size"] + 1 if shown else 0
        page_var.set(
            f"Page {state['page'] + 1} of {_pages()}   "
            f"({first}–{first + shown - 1} of {state['total']} students)"
            if shown else
            (f"No students match “{term}”" if term else "No students"))
        prev_btn.state(["!disabled"] if state["page"] > 0 else ["disabled"])
        next_btn.state(["!disabled"] if state["page"] + 1 < _pages() else ["disabled"])
        status_var.set("")

    self._reload_records_page = _load_page

    def _goto(delta):
        state["page"] = max(0, min(_pages() - 1, state["page"] + delta))
        _load_page()

    prev_btn.configure(command=lambda: _goto(-1))
    next_btn.configure(command=lambda: _goto(1))

    def _on_size(_e=None):
        try:
            state["size"] = int(size_combo.get())
        except ValueError:
            state["size"] = DEFAULT_PAGE_SIZE
        state["page"] = 0
        _load_page()

    size_combo.bind("<<ComboboxSelected>>", _on_size)

    def _on_search(*_args):
        # Debounce: each keystroke now costs a query, so wait for a pause
        # rather than hitting the database on every character.
        if state["after"] is not None:
            try:
                main_frame.after_cancel(state["after"])
            except tk.TclError:
                pass
        def _run():
            state["after"] = None
            state["page"] = 0
            _load_page()
        try:
            state["after"] = main_frame.after(250, _run)
        except tk.TclError:
            _run()

    search_var.trace_add("write", _on_search)
    search_entry.bind("<Escape>", lambda _e: search_var.set(""))

    # Refresh re-runs the current page rather than reloading everything.
    refresh_label = _t("gui.refresh")
    for child in button_frame.winfo_children():
        try:
            if isinstance(child, ttk.Button) and child.cget("text") == refresh_label:
                child.configure(command=_load_page)
                break
        except tk.TclError:
            pass

    _load_page()


def create_student_treeview(self, parent):
    """Create treeview widget for displaying student data"""
    tree_frame = ttk.Frame(parent)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (_t("student.col_id"), _t("student.col_name"), _t("student.col_email"), _t("student.col_course"), _t("student.col_status", default="Status"), _t("student.col_reg_date"))
    self.student_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=30)

    # Configure columns
    for col in columns:
        self.student_tree.heading(col, text=col)
        self.student_tree.column(col, width=150)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.student_tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.student_tree.xview)
    self.student_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.student_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Bind events
    _configure_status_tags(self.student_tree)
    self.student_tree.bind('<Double-1>', self.on_student_double_click)
def view_students(self):
    """Refresh the panel-mode student tree (used by ``student_crud_gui``
    after create / update / delete operations). Thin delegate over
    :func:`_load_students_into` — kept as a method for backward compat
    with ``hasattr(self, 'view_students')`` checks elsewhere."""
    tree = getattr(self, 'student_tree', None)
    if tree is None:
        return
    _load_students_into(self, tree)


def view_students_in_window(self, tree):
    """Refresh the records-window tree.

    Routes through the window's pager when one exists so a refresh after a
    create/edit/delete redraws the page the user is on, keeping the search
    term and page number — rather than silently reloading every student and
    leaving the pager describing a result set that is no longer on screen.
    """
    reload_page = getattr(self, "_reload_records_page", None)
    if callable(reload_page):
        try:
            reload_page()
            return
        except tk.TclError:
            # Window has gone; fall through to the plain load.
            self._reload_records_page = None
    _load_students_into(self, tree)


def _selected_student_id(self, tree):
    """The student id of the selected row, or None."""
    try:
        if tree is None or not tree.winfo_exists():
            return None
        selection = tree.selection()
        if not selection:
            return None
        values = tree.item(selection[0]).get('values', []) or []
        return values[0] if values else None
    except tk.TclError:
        return None


def delete_selected_student(self, tree):
    """Delete the student selected in the records list.

    Delete previously lived only on the main navigation panel, so the one
    window devoted to student records could create and edit but not remove —
    the verb was missing exactly where people look for it. The confirmation
    and the actual deletion stay in ``delete_student_dialog``; this only
    resolves the selection and refreshes the list afterwards.
    """
    if not (self.auth and self.auth.check_permission('delete_any_student')):
        messagebox.showerror(
            _t("common.access_denied", default="Access denied"),
            "You don't have permission to delete student records.")
        return
    student_id = self._selected_student_id(tree)
    if not student_id:
        messagebox.showwarning(_t("common.warning", default="Warning"),
                               "Select a student to delete.")
        return
    try:
        self.delete_student_dialog(student_id)
    except Exception as exc:
        logger.exception("delete from records list failed for %s", student_id)
        messagebox.showerror(_t("common.error"), str(exc))
        return
    self.view_students_in_window(tree)


def _double_click_handler(self, tree):
    """Shared double-click handler — drills the selected student into
    the detail window. Used by both the panel-mode and window-mode
    trees; previously had two near-identical copies."""
    try:
        if tree is None or not tree.winfo_exists():
            return
        selection = tree.selection()
        if not selection:
            return
        values = tree.item(selection[0]).get('values', []) or []
        if values:
            self.show_student_details(values[0])
    except (AttributeError, IndexError, tk.TclError):
        messagebox.showerror(_t("common.error"),
                              _t("student.unable_access_details"))
    except Exception as e:
        messagebox.showerror(_t("common.error"),
                              _t("student.error_occurred", error=str(e)))


def on_student_double_click(self, event):
    """Panel-mode double-click handler."""
    _double_click_handler(self, getattr(self, 'student_tree', None))


def on_student_double_click_window(self, event, tree):
    """Window-mode double-click handler."""
    _double_click_handler(self, tree)
def _defer_tab(notebook, tab, builder):
    """Populate *tab* the first time the user selects it.

    ``show_student_details`` used to build every tab up front, so opening
    one record paid for all of them. The Library tab was the worst offender
    by an order of magnitude: importing ``LibrarySummaryFrame`` reaches
    ``finance_integration`` → ``finance_context``, which imports matplotlib,
    seaborn, scipy, sklearn and pandas at module scope — ~9s on the first
    double-click of a session, spent before the window painted anything, for
    a tab most viewers never open.

    The tab is added to the notebook immediately so it stays visible and in
    the same order; only its contents are deferred. ``builder(tab)`` runs at
    most once — a failure is logged and not retried, matching the try/except
    that wrapped each tab when they were built eagerly.
    """
    pending = getattr(notebook, '_deferred_tabs', None)
    if pending is None:
        pending = {}
        notebook._deferred_tabs = pending

        def _on_tab_changed(_event=None):
            try:
                selected = notebook.select()
            except Exception:
                return
            build = pending.pop(selected, None)
            if build is None:
                return
            try:
                widget = notebook.nametowidget(selected)
            except Exception:
                return
            # The builders below can take a moment (the Library import in
            # particular). Paint something first, or the tab just sits
            # blank with no sign that anything is happening.
            placeholder = ttk.Label(
                widget, text=_t("common.loading", default="Loading…"), padding=20)
            placeholder.pack()
            try:
                widget.update_idletasks()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
            try:
                build(widget)
            except Exception:
                logger.exception("Could not build deferred tab %s", selected)
            finally:
                try:
                    placeholder.destroy()
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

        notebook.bind('<<NotebookTabChanged>>', _on_tab_changed, add='+')

    pending[str(tab)] = builder


def _open_early_warning(self, student_id):
    """Open the early-warning module focused on this student."""
    try:
        from education_system.systems.university.domains.learners.interfaces.gui.students._cross_links import (
            _jump,
        )
        _jump("early_warning", {"student_id": student_id})
    except Exception:
        logger.exception("could not open early warning for %s", student_id)


def show_student_details(self, student_id):
    """Enhanced student details viewer with comprehensive information display.

    Writes a GDPR-relevant audit entry naming the viewer + the subject
    student before opening the window, so every read of a student
    record is auditable. The write is best-effort — a transient audit
    DB failure won't block the viewer from rendering, but a sustained
    gap shows up as missing rows in the audit log itself which is a
    different (and detectable) compliance signal."""
    try:
        from education_system.systems.university.domains.learners.interfaces.gui.students._cross_links import (
            audit_student_view,
        )
        viewer = self.auth.current_user if self.auth else None
        if viewer:
            audit_student_view(
                viewer.get('id'),
                viewer.get('username'),
                student_id,
            )
    except Exception:
        logger.debug("student view audit hook failed", exc_info=True)

    detail_window = tk.Toplevel(self.root)
    _install_clean_close(detail_window)
    detail_window.title(_t("student_details.window_title", student_id=student_id))
    detail_window.geometry("900x700")
    detail_window.transient(self.root)

    # student_records.db now carries ~1,800 tables, so SQLite spends ~77ms
    # parsing the schema on each new connection. Building this window opened
    # one per section — the student row here, then another inside
    # _load_academic_data — and paid that over and over. reuse_connection()
    # makes the nested get_db_connection() calls hand back the same
    # connection, so the cost is paid once; the call sites are unchanged, and
    # their conn.close() becomes a no-op until the block exits.
    #
    # ExitStack rather than a `with` so the ~390-line body below keeps its
    # current indentation and stays reviewable as a diff.
    _shared_conn = ExitStack()
    _shared_conn.enter_context(reuse_connection())

    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student_details.error_db_connection"))
            detail_window.destroy()
            return

        # Switch to a Row factory so we can index columns by name
        # (``student['first_name']``) instead of position. Column
        # additions in the schema can no longer shift indices and
        # silently break this view.
        import sqlite3 as _sqlite3
        try:
            conn.row_factory = _sqlite3.Row
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            messagebox.showerror(_t("common.error"), _t("student_details.error_student_not_found"))
            detail_window.destroy()
            return

        # Create notebook for tabbed interface
        notebook = ttk.Notebook(detail_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information Tab
        personal_tab = ttk.Frame(notebook)
        notebook.add(personal_tab, text=_t("student_details.tab_personal_info"))

        # ── Personal info tab: structured cards instead of monospaced blob ──
        na = _t("student_details.na")
        s_id = _row_get(student, 'student_id')
        s_email = _row_get(student, 'email_address')
        s_title = _row_get(student, 'title')
        s_first = _row_get(student, 'first_name')
        s_middle = _row_get(student, 'middle_name')
        s_last = _row_get(student, 'last_name')
        s_gender = _row_get(student, 'gender')
        s_dob = _row_get(student, 'dob')
        s_age = _row_get(student, 'age')
        s_course = _row_get(student, 'course')
        s_reg = _row_get(student, 'registration_datetime')
        s_pronouns = _row_get(student, 'pronouns')
        s_emergency = _row_get(student, 'emergency_contact')

        title = s_title if s_title else na
        first_name = s_first if s_first else na
        middle_name = s_middle if s_middle else ''
        last_name = s_last if s_last else na
        gender = s_gender.title() if s_gender else na
        course = s_course if s_course else na

        name_parts = [p for p in (s_title, s_first, s_middle, s_last) if p]
        full_name = ' '.join(name_parts) if name_parts else na

        # Hero header
        hero = ttk.Frame(personal_tab, padding=(20, 14))
        hero.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(hero, text=full_name, font=('Arial', 18, 'bold')).pack(anchor='w')
        sub_bits = []
        if s_id:
            sub_bits.append(f"ID: {s_id}")
        if course not in (na, ''):
            sub_bits.append(course)
        if s_pronouns:
            sub_bits.append(s_pronouns)
        if s_email:
            sub_bits.append(s_email)
        # Risk badge. Every student carries an early-warning profile scored
        # across academic, attendance, engagement and financial signals; the
        # record used to show none of it. Clicking opens the early-warning
        # module for this student.
        try:
            from education_system.systems.university.domains.learners.interfaces.gui.students._cross_links import (
                RISK_COLOURS, risk_badge_text, risk_component_alert, student_risk,
            )
            _risk = student_risk(student_id)
        except Exception:
            _risk = None
        if _risk:
            _level = str(_risk.get('risk_level') or '').strip().lower()
            _badge = ttk.Label(
                hero, text=risk_badge_text(_risk), font=('Arial', 10, 'bold'),
                foreground=RISK_COLOURS.get(_level, '#555555'), cursor='hand2')
            _badge.pack(anchor='w', pady=(4, 0))
            _badge.bind(
                '<Button-1>',
                lambda _e, u=student_id: self._open_early_warning(u))
            # A high single component is the case the headline level hides,
            # so it gets its own line in warning colour rather than being
            # appended to a line that says "Low".
            _alert = risk_component_alert(_risk)
            if _alert:
                _alert_lbl = ttk.Label(hero, text=_alert, font=('Arial', 9, 'bold'),
                                       foreground='#c2410c', cursor='hand2')
                _alert_lbl.pack(anchor='w')
                _alert_lbl.bind(
                    '<Button-1>',
                    lambda _e, u=student_id: self._open_early_warning(u))
            if _risk.get('last_assessed'):
                ttk.Label(hero,
                          text=f"assessed {str(_risk['last_assessed'])[:10]}"
                               " — click for detail",
                          font=('Arial', 8), foreground='#777777').pack(anchor='w')

        if sub_bits:
            ttk.Label(hero, text=' · '.join(sub_bits),
                      font=('Arial', 10), foreground='#555555').pack(anchor='w', pady=(2, 0))
        ttk.Separator(personal_tab, orient='horizontal').pack(fill=tk.X, padx=10, pady=(8, 4))

        # Scrollable container for the cards (works on small windows)
        canvas = tk.Canvas(personal_tab, borderwidth=0, highlightthickness=0)
        vbar = ttk.Scrollbar(personal_tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side='left', fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        vbar.pack(side='right', fill='y', pady=(0, 10))

        cards = ttk.Frame(canvas)
        cards_window = canvas.create_window((0, 0), window=cards, anchor='nw')

        def _on_inner(_event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas(event):
            canvas.itemconfigure(cards_window, width=event.width)

        cards.bind('<Configure>', _on_inner)
        canvas.bind('<Configure>', _on_canvas)

        def _add_field(parent, row, label, value):
            ttk.Label(parent, text=label, font=('Arial', 10, 'bold'),
                      foreground='#333333').grid(row=row, column=0, sticky='w', padx=(0, 16), pady=3)
            ttk.Label(parent, text=str(value), font=('Arial', 10)).grid(
                row=row, column=1, sticky='w', pady=3,
            )

        # Card 1 — Identity
        identity = ttk.LabelFrame(cards, text=_t("student_details.header_personal_info"),
                                  padding=15)
        identity.pack(fill=tk.X, pady=6)
        identity.columnconfigure(1, weight=1)
        years_text = _t("student_details.label_years")
        _add_field(identity, 0, _t("student_details.label_student_id"), s_id or na)
        _add_field(identity, 1, _t("student_details.label_email_address"), s_email or na)
        _add_field(identity, 2, _t("student_details.label_title"), title)
        _add_field(identity, 3, _t("student_details.label_first_name"), first_name)
        _add_field(identity, 4, _t("student_details.label_middle_name"), middle_name or na)
        _add_field(identity, 5, _t("student_details.label_last_name"), last_name)
        _add_field(identity, 6, _t("student_details.label_full_name"), full_name)

        # Card 2 — Demographics
        demographics = ttk.LabelFrame(cards, text=_t("student_details.header_demographics"),
                                      padding=15)
        demographics.pack(fill=tk.X, pady=6)
        demographics.columnconfigure(1, weight=1)
        age_value = (
            f"{s_age} {years_text}" if s_age not in (None, '') else na
        )
        _add_field(demographics, 0, _t("student_details.label_gender"), gender)
        _add_field(demographics, 1, _t("student_details.label_date_of_birth"), s_dob or na)
        _add_field(demographics, 2, _t("student_details.label_age"), age_value)
        _add_field(demographics, 3,
                   _t("student_details.label_pronouns", default="Pronouns"),
                   s_pronouns or na)

        # Card 3 — Emergency contact. Held on every student record but
        # displayed nowhere until now, which made it useless in the
        # situation it exists for.
        emergency_card = ttk.LabelFrame(
            cards,
            text=_t("student_details.header_emergency_contact",
                    default="Emergency Contact"),
            padding=15)
        emergency_card.pack(fill=tk.X, pady=6)
        emergency_card.columnconfigure(1, weight=1)
        if s_emergency:
            _add_field(emergency_card, 0,
                       _t("student_details.label_emergency_contact",
                          default="Emergency contact"),
                       s_emergency)
        else:
            ttk.Label(emergency_card,
                      text=_t("student_details.no_emergency_contact",
                              default="No emergency contact on record."),
                      font=('Arial', 10, 'italic'),
                      foreground='#a05000').grid(row=0, column=0, sticky='w')

        # Card 4 — Academic info
        academic_info_card = ttk.LabelFrame(cards, text=_t("student_details.header_academic_info"),
                                            padding=15)
        academic_info_card.pack(fill=tk.X, pady=6)
        academic_info_card.columnconfigure(1, weight=1)
        _add_field(academic_info_card, 0, _t("student_details.label_course"), course)
        _add_field(academic_info_card, 1, _t("student_details.label_registration"),
                   s_reg or na)

        # Academic Information Tab
        academic_tab = ttk.Frame(notebook)
        notebook.add(academic_tab, text=_t("student_details.tab_academic_records"))

        # Top bar: summary line on the left, refresh on the right
        top_bar = ttk.Frame(academic_tab)
        top_bar.pack(fill=tk.X, padx=10, pady=(10, 0))
        academic_summary = ttk.Label(top_bar, text="", font=('Arial', 10, 'italic'),
                                     foreground='#555555')
        academic_summary.pack(side=tk.LEFT)
        ttk.Button(
            top_bar,
            text=_t("common.refresh", default="Refresh"),
            command=lambda: self._load_academic_data(
                student_id, modules_tree, grades_tree, attendance_tree,
                academic_summary, na,
            ),
        ).pack(side=tk.RIGHT)

        # Scrollable container — three Treeviews can't all fit when the
        # window is 700px tall, so wrap them in a Canvas + Scrollbar.
        ac_canvas = tk.Canvas(academic_tab, borderwidth=0, highlightthickness=0)
        ac_vbar = ttk.Scrollbar(academic_tab, orient='vertical', command=ac_canvas.yview)
        ac_canvas.configure(yscrollcommand=ac_vbar.set)
        ac_canvas.pack(side='left', fill=tk.BOTH, expand=True, padx=(10, 0), pady=(8, 10))
        ac_vbar.pack(side='right', fill='y', pady=(8, 10))

        ac_inner = ttk.Frame(ac_canvas)
        ac_window = ac_canvas.create_window((0, 0), window=ac_inner, anchor='nw')

        def _on_ac_inner(_event):
            ac_canvas.configure(scrollregion=ac_canvas.bbox('all'))

        def _on_ac_canvas(event):
            ac_canvas.itemconfigure(ac_window, width=event.width)

        ac_inner.bind('<Configure>', _on_ac_inner)
        ac_canvas.bind('<Configure>', _on_ac_canvas)

        # ── Mousewheel scrolling, scoped to the academic-tab canvas ──
        # The previous implementation used ``bind_all`` (process-global)
        # which leaked: closing this detail window did not unbind, so
        # the next Toplevel's wheel events fired callbacks against a
        # destroyed canvas and produced
        # ``TclError: invalid command name ".!toplevel.!canvas"``
        # on stderr. Now bound directly on the canvas + the inner frame
        # + its children via ``bind`` (window-local), so they go away
        # naturally when the detail window is destroyed.
        def _on_ac_wheel(event):
            try:
                delta = -1 if (getattr(event, 'num', None) == 5
                               or getattr(event, 'delta', 0) < 0) else 1
                ac_canvas.yview_scroll(-delta, 'units')
            except tk.TclError:
                # Canvas already destroyed — race with window close.
                pass
            return "break"

        def _bind_wheel_recursive(widget):
            try:
                for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                    widget.bind(seq, _on_ac_wheel, add="+")
                for child in widget.winfo_children():
                    _bind_wheel_recursive(child)
            except tk.TclError:
                pass

        # Bind on the canvas itself + the scrolling inner frame; the
        # children-walk catches the Treeviews and labels added below
        # so wheel events anywhere in the academic tab scroll the
        # outer canvas. Re-bind whenever the inner frame's contents
        # change so newly-added widgets pick up the binding.
        ac_canvas.bind('<MouseWheel>', _on_ac_wheel, add="+")
        ac_canvas.bind('<Button-4>', _on_ac_wheel, add="+")
        ac_canvas.bind('<Button-5>', _on_ac_wheel, add="+")
        ac_inner.bind('<Map>', lambda _e: _bind_wheel_recursive(ac_inner))

        # Three stacked panels with Treeviews (now inside the scrollable inner frame)
        modules_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_enrolled_modules", default="Enrolled Modules"),
            padding=10,
        )
        modules_frame.pack(fill=tk.X, padx=4, pady=(0, 6))
        modules_tree = ttk.Treeview(
            modules_frame, columns=("type", "code", "name"),
            show="headings", height=6,
        )
        modules_tree.heading("type", text=_t('gui.learners.students.student_records.headings.type', default="Type"))
        modules_tree.heading("code", text=_t('gui.learners.students.student_records.headings.code', default="Code"))
        modules_tree.heading("name", text=_t('gui.learners.students.student_records.headings.module_name', default="Module Name"))
        modules_tree.column("type", width=110, anchor="w")
        modules_tree.column("code", width=110, anchor="w")
        modules_tree.column("name", width=400, anchor="w")
        mod_vsb = ttk.Scrollbar(modules_frame, orient="vertical", command=modules_tree.yview)
        modules_tree.configure(yscrollcommand=mod_vsb.set)
        modules_tree.pack(side="left", fill=tk.X, expand=True)
        mod_vsb.pack(side="right", fill="y")
        modules_tree.tag_configure("group", background="#eef2f7", font=('Arial', 10, 'bold'))

        grades_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_grades_assessments", default="Grades & Assessments"),
            padding=10,
        )
        grades_frame.pack(fill=tk.X, padx=4, pady=6)
        grades_tree = ttk.Treeview(
            grades_frame, columns=("module", "assessment", "grade", "date"),
            show="headings", height=6,
        )
        grades_tree.heading("module", text=_t('gui.learners.students.student_records.headings.module', default="Module"))
        grades_tree.heading("assessment", text=_t('gui.learners.students.student_records.headings.assessment', default="Assessment"))
        grades_tree.heading("grade", text=_t('gui.learners.students.student_records.headings.grade', default="Grade"))
        grades_tree.heading("date", text=_t('gui.learners.students.student_records.headings.date', default="Date"))
        grades_tree.column("module", width=110, anchor="w")
        grades_tree.column("assessment", width=300, anchor="w")
        grades_tree.column("grade", width=80, anchor="center")
        grades_tree.column("date", width=160, anchor="w")
        gr_vsb = ttk.Scrollbar(grades_frame, orient="vertical", command=grades_tree.yview)
        grades_tree.configure(yscrollcommand=gr_vsb.set)
        grades_tree.pack(side="left", fill=tk.X, expand=True)
        gr_vsb.pack(side="right", fill="y")
        grades_tree.tag_configure("good", foreground="#1b7f3a")
        grades_tree.tag_configure("warn", foreground="#b87a00")
        grades_tree.tag_configure("fail", foreground="#b00020")

        attendance_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_recent_attendance", default="Recent Attendance"),
            padding=10,
        )
        attendance_frame.pack(fill=tk.X, padx=4, pady=(6, 0))
        attendance_tree = ttk.Treeview(
            attendance_frame, columns=("date", "module", "status", "notes"),
            show="headings", height=6,
        )
        attendance_tree.heading("date", text=_t('gui.learners.students.student_records.headings.date', default="Date"))
        attendance_tree.heading("module", text=_t('gui.learners.students.student_records.headings.module', default="Module"))
        attendance_tree.heading("status", text=_t('gui.learners.students.student_records.headings.status', default="Status"))
        attendance_tree.heading("notes", text=_t('gui.learners.students.student_records.headings.notes', default="Notes"))
        attendance_tree.column("date", width=120, anchor="w")
        attendance_tree.column("module", width=110, anchor="w")
        attendance_tree.column("status", width=100, anchor="center")
        attendance_tree.column("notes", width=320, anchor="w")
        att_vsb = ttk.Scrollbar(attendance_frame, orient="vertical", command=attendance_tree.yview)
        attendance_tree.configure(yscrollcommand=att_vsb.set)
        attendance_tree.pack(side="left", fill=tk.X, expand=True)
        att_vsb.pack(side="right", fill="y")
        attendance_tree.tag_configure("present", foreground="#1b7f3a")
        attendance_tree.tag_configure("late", foreground="#b87a00")
        attendance_tree.tag_configure("absent", foreground="#b00020")

        self._load_academic_data(
            student_id, modules_tree, grades_tree, attendance_tree,
            academic_summary, na,
        )

        # Library activity tab — embedded summary widget driven by the
        # cross-module API. Renders an empty/zero panel when the
        # student has no library records.
        #
        # Deferred: the import below is the single most expensive thing this
        # window does (see _defer_tab). Nothing here touches the DB, so it
        # sits outside the reuse block quite happily.
        library_tab = ttk.Frame(notebook)
        notebook.add(library_tab, text=_t('gui.learners.students.student_records.tabs.library', default="📚 Library"))

        def _build_library_tab(tab):
            from education_system.systems.university.domains.academics.interfaces.gui.library.cross_module_api import (
                LibrarySummaryFrame,
            )
            LibrarySummaryFrame(
                tab,
                user_id=student_id,
                on_open_library=getattr(self, "show_library_management", None),
            ).pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        _defer_tab(notebook, library_tab, _build_library_tab)

        # ── Summary tab ─────────────────────────────────────────
        # Cross-domain at-a-glance metrics: finance / attendance /
        # disciplinary cases. Same shape as the Library tab — small
        # in-process panel that reads bus-side tables directly. Keeps
        # the user from having to drill into 4 separate windows just
        # to see "is this student in trouble".
        summary_tab = ttk.Frame(notebook)
        notebook.add(summary_tab, text=_t('gui.learners.students.student_records.tabs.summary', default="📊 Summary"))

        def _build_summary_tab(tab):
            # Its three counter queries each opened their own connection;
            # share one for the burst.
            with reuse_connection():
                _build_student_summary(
                    tab, student_id, na,
                    on_open_finance=lambda: self.show_student_finance_account()
                        if hasattr(self, 'show_student_finance_account') else None,
                    on_open_attendance=lambda: self.view_student_attendance(
                        student_id, s_email, s_first, s_last)
                        if hasattr(self, 'view_student_attendance') else None,
                )

        _defer_tab(notebook, summary_tab, _build_summary_tab)

        # ── All DB Records tab (admin only) ─────────────────────
        # 8.117.100: surfaces every table in the central DB that
        # references this student. Discovers tables dynamically by
        # querying ``sqlite_master`` for any table with a column named
        # ``student_id``, counts rows per table for the current
        # student, and shows a Treeview with double-click drill-down
        # to a sub-window listing the actual rows.
        #
        # Deferred as well: its opening _refresh() sweeps sqlite_master and
        # runs PRAGMA table_info over all ~1,800 tables to find the ~380 with
        # a student_id column (~265ms), which is wasted on every open for a
        # tab that is an occasional diagnostic.
        try:
            current_role = (self.auth.current_user or {}).get('role', '') if self.auth else ''
            if current_role == 'admin':
                admin_tab = ttk.Frame(notebook)
                notebook.add(admin_tab, text=_t('gui.learners.students.student_records.tabs.all_records_admin', default="🛡 All Records (Admin)"))
                _defer_tab(notebook, admin_tab,
                           lambda tab: _build_student_all_records_tab(tab, student_id))
        except Exception:
            logger.exception("Could not build admin all-records tab")

        # ── Actions tab ─────────────────────────────────────────
        # Reduced from the 8.117.15 footprint: the Edit / Manage Grades
        # / View Attendance / View Timetable / Export / Send Email
        # actions are also exposed on the records-list right-click
        # menu (8.117.16) so the user rarely needs to drill in just to
        # fire one. The tab is kept for the contact pane and as a
        # discoverability surface for users who haven't found the
        # right-click yet.
        actions_tab = ttk.Frame(notebook)
        notebook.add(actions_tab, text=_t("student_details.tab_actions"))

        actions_frame = ttk.LabelFrame(actions_tab, text=_t("student_details.available_actions"), padding=20)
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if self.auth.check_permission('update_any_student'):
            ttk.Button(actions_frame, text=_t("student_details.btn_edit_student"),
                      command=lambda: self.update_student_dialog(student_id),
                      width=30).pack(pady=10)

        # Registration status. Gated with the edit permission: it rewrites
        # the authoritative students row and pauses module enrolments.
        if self.auth.check_permission('update_any_student'):
            ttk.Button(actions_frame,
                      text=_t("student_details.btn_manage_lifecycle",
                              default="Registration Status…"),
                      command=lambda: self.manage_student_lifecycle(
                          student_id, s_first, s_last),
                      width=30).pack(pady=5)

        if self.auth.check_permission('manage_grades'):
            ttk.Button(actions_frame, text=_t("student_details.btn_view_grades",
                                              default="View Grades"),
                      command=lambda: self.manage_student_grades(student_id, s_first, s_last),
                      width=30).pack(pady=5)

        own_record = self.auth.current_user and self.auth.current_user.get('student_id') == student_id
        if self.auth.check_permission('manage_attendance') or own_record:
            ttk.Button(actions_frame, text=_t("student_details.btn_view_attendance"),
                      command=lambda: self.view_student_attendance(student_id, s_email, s_first, s_last),
                      width=30).pack(pady=5)

        ttk.Button(actions_frame, text=_t("student_details.btn_view_timetable"),
                  command=lambda: self.view_student_timetable(student_id, s_first, s_last),
                  width=30).pack(pady=5)

        if self.auth.check_permission('export_data'):
            ttk.Button(actions_frame, text=_t("student_details.btn_export_data"),
                      command=lambda: self.export_individual_student_data(student_id, s_first, s_last),
                      width=30).pack(pady=5)

        contact_frame = ttk.LabelFrame(actions_tab, text=_t("student_details.contact_information"), padding=20)
        contact_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Label(contact_frame, text=f"{_t('student_details.label_email')} {s_email}").pack(anchor=tk.W)
        ttk.Button(contact_frame, text=_t("student_details.btn_send_email"),
                  command=lambda: self.send_email_to_student(s_email, s_first, s_last),
                  width=20).pack(pady=5)

        conn.close()

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student_details.error_load_details", error=str(e)))
        detail_window.destroy()
    finally:
        # Release the shared connection. Deferred tab builders and the
        # window's own callbacks run long after this and open their own —
        # a shared connection held for the window's lifetime would keep a
        # read transaction open and grow the WAL.
        _shared_conn.close()

def _load_academic_data(self, student_id, modules_tree, grades_tree,
                        attendance_tree, summary_label, na):
    """Refresh the three academic Treeviews and the summary line."""
    # Clear
    for tree in (modules_tree, grades_tree, attendance_tree):
        for item in tree.get_children():
            tree.delete(item)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.module_type, sm.module_code, m.module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY m.module_type, sm.module_code
        ''', (student_id,))
        modules = cursor.fetchall()

        cursor.execute('''
            SELECT a.module_code, a.title as assessment_name,
                   s.grade, s.submission_date as grade_date
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE s.student_id = ? AND s.grade IS NOT NULL
            UNION ALL
            SELECT a.module_code, a.assessment_name,
                   g.score as grade, g.submission_date as grade_date
            FROM assessments a
            LEFT JOIN grades g ON a.assessment_id = g.assessment_id
            WHERE g.student_id = ? AND g.score IS NOT NULL
            ORDER BY grade_date DESC
            LIMIT 20
        ''', (student_id, student_id))
        grades = cursor.fetchall()

        cursor.execute('''
            SELECT module_code, date, status, notes
            FROM attendance_records
            WHERE student_id = ?
            ORDER BY date DESC
            LIMIT 10
        ''', (student_id,))
        attendance = cursor.fetchall()

        conn.close()

        # Modules — group by type with a faint header row before each block
        if modules:
            current_type = object()
            for module in modules:
                module_type = (module[0] or _t("student_details.unknown")).strip()
                if module_type != current_type:
                    current_type = module_type
                    modules_tree.insert(
                        "", tk.END,
                        values=(module_type.upper(), "", ""),
                        tags=("group",),
                    )
                modules_tree.insert(
                    "", tk.END,
                    values=(
                        "",
                        module[1] if module[1] else na,
                        module[2] if module[2] else _t("student_details.unknown_module"),
                    ),
                )
        else:
            modules_tree.insert(
                "", tk.END,
                values=("", "", _t("student_details.no_modules_enrolled")),
            )

        # Grades — colour-code by score band
        if grades:
            for grade in grades:
                module_code = grade[0] if grade[0] else na
                assessment_name = grade[1] if grade[1] else _t("student_details.unknown_assessment")
                raw_grade = grade[2]
                grade_value = (
                    raw_grade if raw_grade not in (None, "")
                    else _t("student_details.no_grade")
                )
                grade_date = grade[3] if grade[3] else _t("student_details.unknown_date")

                tag = ()
                try:
                    score = float(raw_grade)
                    if score >= 70:
                        tag = ("good",)
                    elif score >= 40:
                        tag = ("warn",)
                    else:
                        tag = ("fail",)
                except (TypeError, ValueError):
                    pass

                grades_tree.insert(
                    "", tk.END,
                    values=(module_code, assessment_name, grade_value, grade_date),
                    tags=tag,
                )
        else:
            grades_tree.insert(
                "", tk.END,
                values=("", _t("student_details.no_grades_recorded"), "", ""),
            )

        # Attendance — colour-code present/late/absent
        if attendance:
            for att in attendance:
                module_code = att[0] if att[0] else na
                att_date = att[1] if att[1] else _t("student_details.unknown_date")
                status = att[2] if att[2] else _t("student_details.unknown")
                notes = att[3] or ""

                status_lc = (status or "").strip().lower()
                if status_lc == "present":
                    tag = ("present",)
                elif status_lc == "late":
                    tag = ("late",)
                elif status_lc in ("absent", "unauthorised", "unauthorized"):
                    tag = ("absent",)
                else:
                    tag = ()

                attendance_tree.insert(
                    "", tk.END,
                    values=(att_date, module_code, status, notes),
                    tags=tag,
                )
        else:
            attendance_tree.insert(
                "", tk.END,
                values=("", "", _t("student_details.no_attendance_records"), ""),
            )

        summary_label.config(
            text=f"{len(modules)} module(s) · {len(grades)} grade(s) · "
                 f"{len(attendance)} recent attendance entry(ies)"
        )

    except Exception as e:
        summary_label.config(text=f"Error loading academic data: {e}",
                             foreground='#b00020')

def _build_student_all_records_tab(tab, student_id):
    """Render the admin-only "All DB Records" tab.

    Discovers every table in the central DB that has a ``student_id``
    column, counts rows per table for ``student_id``, and shows the
    non-empty ones in a Treeview. Double-click a row to open a
    sub-window with the actual columns/values.
    """
    # Header
    ttk.Label(tab,
              text=f"All database records for {student_id}",
              font=('Arial', 13, 'bold')).pack(anchor='w', padx=15, pady=(15, 4))
    ttk.Label(tab,
              text=(_t('gui.learners.students.student_records.labels.discovered_automatically_from_sqlite_master_every_table_with_a_s', default="Discovered automatically from sqlite_master — "
                    "every table with a 'student_id' column. "
                    "Empty tables are hidden.")),
              foreground='#555').pack(anchor='w', padx=15, pady=(0, 10))

    # Toolbar (Refresh + status)
    toolbar = ttk.Frame(tab)
    toolbar.pack(fill=tk.X, padx=15, pady=(0, 6))
    status_var = tk.StringVar(value="")
    ttk.Label(toolbar, textvariable=status_var, foreground='#555').pack(side=tk.LEFT)

    # Treeview
    cols = ('table', 'rows', 'columns')
    tree_frame = ttk.Frame(tab)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 12))
    tree = ttk.Treeview(tree_frame, columns=cols, show='headings', height=18)
    tree.heading('table',   text=_t('gui.learners.students.student_records.headings.table', default='Table'))
    tree.heading('rows',    text=_t('gui.learners.students.student_records.headings.rows', default='Rows'))
    tree.heading('columns', text=_t('gui.learners.students.student_records.headings.columns', default='Columns'))
    tree.column('table',   width=220)
    tree.column('rows',    width=70, anchor='center')
    tree.column('columns', width=520)
    yscroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=yscroll.set)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    yscroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _refresh():
        for iid in tree.get_children():
            tree.delete(iid)
        try:
            conn = get_db_connection()
        except Exception as e:
            status_var.set(f"DB error: {e}")
            return
        try:
            tables_with_sid = []
            for (name,) in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall():
                try:
                    info = conn.execute(f"PRAGMA table_info({name})").fetchall()
                except Exception:
                    continue
                cols_in_table = [c[1] for c in info]
                if 'student_id' in cols_in_table:
                    tables_with_sid.append((name, cols_in_table))

            non_empty = 0
            for name, cols_in_table in tables_with_sid:
                try:
                    cnt = conn.execute(
                        f"SELECT COUNT(*) FROM {name} WHERE student_id = ?",
                        (student_id,)
                    ).fetchone()[0]
                except Exception:
                    cnt = 0
                if cnt:
                    non_empty += 1
                    tree.insert('', tk.END, values=(
                        name, cnt, ", ".join(cols_in_table[:8]) +
                        (" …" if len(cols_in_table) > 8 else "")))
            status_var.set(
                f"{non_empty} table(s) with rows · "
                f"{len(tables_with_sid)} table(s) referencing student_id")
        finally:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

    ttk.Button(toolbar, text=_t('gui.learners.students.student_records.buttons.refresh', default="Refresh"),
               command=_refresh).pack(side=tk.RIGHT)

    def _open_drilldown(_e=None):
        sel = tree.selection()
        if not sel:
            return
        table = tree.item(sel[0], 'values')[0]
        win = tk.Toplevel(tab.winfo_toplevel())
        _install_clean_close(win)
        win.title(f"{table} — student_id={student_id}")
        win.geometry("1100x500")
        win.transient(tab.winfo_toplevel())

        try:
            conn = get_db_connection()
            info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_names = [c[1] for c in info]
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE student_id = ? "
                "ORDER BY rowid DESC LIMIT 500",
                (student_id,)
            ).fetchall()
            conn.close()
        except Exception as e:
            ttk.Label(win, text=f"Query failed: {e}",
                      foreground='#b00020').pack(padx=20, pady=20)
            return

        ttk.Label(win, text=f"{table} ({len(rows)} row(s), most recent first)",
                  font=('Arial', 12, 'bold')).pack(anchor='w', padx=10, pady=8)
        if not rows:
            ttk.Label(win, text=_t('gui.learners.students.student_records.labels.no_rows', default="No rows.")).pack(padx=20, pady=20)
            return
        inner = ttk.Frame(win)
        inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        rt = ttk.Treeview(inner, columns=col_names, show='headings', height=20)
        for c in col_names:
            rt.heading(c, text=c)
            rt.column(c, width=120, anchor='w')
        ys = ttk.Scrollbar(inner, orient=tk.VERTICAL, command=rt.yview)
        xs = ttk.Scrollbar(inner, orient=tk.HORIZONTAL, command=rt.xview)
        rt.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        rt.grid(row=0, column=0, sticky='nsew')
        ys.grid(row=0, column=1, sticky='ns')
        xs.grid(row=1, column=0, sticky='ew')
        inner.rowconfigure(0, weight=1)
        inner.columnconfigure(0, weight=1)
        for r in rows:
            rt.insert('', tk.END, values=tuple(r))

    tree.bind('<Double-Button-1>', _open_drilldown)
    _refresh()


def _build_student_summary(tab, student_id, na,
                           *, on_open_finance=None, on_open_attendance=None):
    """Render the cross-domain summary tab.

    Pulls one-shot counters for finance (open student_fees, total
    outstanding balance), attendance (recent rate %), and disciplinary
    + academic-misconduct cases (open count). All queries are scoped
    by ``student_id`` and tolerate missing tables — older deployments
    that don't have ``disciplinary_records`` / ``student_fees`` see an
    "n/a" tile rather than a stack trace.

    The three counters go through ``get_db_connection()`` rather than a raw
    ``sqlite3.connect``, so that wrapping the call in ``reuse_connection()``
    actually collapses them onto one connection — a raw connect bypasses the
    sharing entirely and pays the ~77ms schema parse three times over."""
    import sqlite3  # for sqlite3.OperationalError on deployments missing a table

    title_lbl = ttk.Label(tab, text=_t('gui.learners.students.student_records.labels.at_a_glance_summary', default="At-a-glance summary"),
                          font=('Arial', 14, 'bold'))
    title_lbl.pack(anchor='w', padx=14, pady=(14, 6))
    ttk.Label(tab, text=f"Cross-domain status for {student_id} — drawn live "
              "from the finance, attendance, and cases tables.",
              foreground='#555555').pack(anchor='w', padx=14, pady=(0, 12))

    grid = ttk.Frame(tab, padding=10)
    grid.pack(fill='both', expand=True)
    for col in range(3):
        grid.columnconfigure(col, weight=1)

    def _tile(parent, row, col, title, value, sub="", color=None,
              on_click=None):
        card = ttk.LabelFrame(parent, text=title, padding=14)
        card.grid(row=row, column=col, sticky='nsew', padx=8, pady=8)
        big = tk.Label(card, text=str(value),
                       font=('Arial', 22, 'bold'),
                       fg=color or "#222222", anchor='w')
        big.pack(anchor='w')
        if sub:
            tk.Label(card, text=sub, fg='#555555',
                     font=('Arial', 9)).pack(anchor='w', pady=(2, 0))
        if callable(on_click):
            ttk.Button(card, text=_t('gui.learners.students.student_records.buttons.open', default="Open →"),
                       command=on_click).pack(anchor='e', pady=(8, 0))
        return card

    open_fines = "—"
    finance_balance = "—"
    finance_color = None
    try:
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount), 0) "
                "FROM student_fees WHERE student_id = ? "
                "AND status != 'paid'",
                (str(student_id),)
            ).fetchone()
            if row:
                open_fines = int(row[0] or 0)
                bal = float(row[1] or 0.0)
                finance_balance = f"£{bal:,.2f}"
                if bal > 500:
                    finance_color = "#b00020"
                elif bal > 0:
                    finance_color = "#b87a00"
                else:
                    finance_color = "#1b7f3a"
        except sqlite3.OperationalError:
            open_fines = na
        conn.close()
    except Exception:
        logger.debug("finance summary lookup failed", exc_info=True)

    _tile(grid, 0, 0, "💰 Outstanding balance",
          finance_balance,
          sub=f"{open_fines} open fee(s)" if open_fines != "—" else "",
          color=finance_color,
          on_click=on_open_finance if callable(on_open_finance) else None)

    att_rate = "—"
    att_sub = ""
    att_color = None
    try:
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT "
                " SUM(CASE WHEN LOWER(status)='present' THEN 1 ELSE 0 END), "
                " COUNT(*) "
                "FROM attendance_records WHERE student_id = ?",
                (str(student_id),)
            ).fetchone()
            if row and row[1]:
                pct = (float(row[0] or 0) / float(row[1])) * 100
                att_rate = f"{pct:.0f}%"
                att_sub = f"{int(row[0] or 0)} present of {int(row[1])}"
                if pct >= 85:
                    att_color = "#1b7f3a"
                elif pct >= 60:
                    att_color = "#b87a00"
                else:
                    att_color = "#b00020"
            elif row:
                att_rate = na
                att_sub = "no records yet"
        except sqlite3.OperationalError:
            att_rate = na
        conn.close()
    except Exception:
        logger.debug("attendance summary lookup failed", exc_info=True)

    _tile(grid, 0, 1, "✅ Attendance",
          att_rate, sub=att_sub, color=att_color,
          on_click=on_open_attendance if callable(on_open_attendance) else None)

    open_cases = 0
    case_sub = ""
    case_color = None
    case_seen = False
    try:
        conn = get_db_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM disciplinary_records "
                "WHERE user_id = ? AND COALESCE(status, 'Open') != 'Closed'",
                (str(student_id),)
            ).fetchone()
            if row:
                open_cases += int(row[0] or 0)
                case_seen = True
        except sqlite3.OperationalError:
            pass
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM academic_misconduct_cases "
                "WHERE student_id = ? AND COALESCE(status, '') != 'Closed'",
                (str(student_id),)
            ).fetchone()
            if row:
                open_cases += int(row[0] or 0)
                case_seen = True
        except sqlite3.OperationalError:
            pass
        conn.close()
        if case_seen:
            case_sub = "open disciplinary + AM cases"
            if open_cases > 0:
                case_color = "#b00020"
            else:
                case_color = "#1b7f3a"
        else:
            open_cases = na
            case_sub = ""
    except Exception:
        logger.debug("cases summary lookup failed", exc_info=True)

    _tile(grid, 0, 2, "🚨 Open cases",
          open_cases, sub=case_sub, color=case_color)


def search_students_dialog(self):
    """Create search dialog"""
    dialog = self.create_themed_toplevel(_t("student.search_students"), "400x300")
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Search criteria
    ttk.Label(main_frame, text=_t("student.search_by")).grid(row=0, column=0, sticky=tk.W, pady=5)
    search_type = ttk.Combobox(main_frame, values=[
        _t("student.first_name"), _t("student.last_name"), _t("student.student_id"), _t("student.col_course"), _t("common.email")
    ], state='readonly', width=25)
    search_type.grid(row=0, column=1, pady=5, padx=(10, 0))
    search_type.set(_t("student.first_name"))

    ttk.Label(main_frame, text=_t("student.search_term")).grid(row=1, column=0, sticky=tk.W, pady=5)
    search_term = ttk.Entry(main_frame, width=28)
    search_term.grid(row=1, column=1, pady=5, padx=(10, 0))

    def perform_search():
        """Perform search and update treeview"""
        term = search_term.get().strip()
        if not term:
            messagebox.showerror(_t("common.error"), _t("student.enter_search_term"))
            return

        try:
            # Check if student_tree exists
            if not hasattr(self, 'student_tree') or not self.student_tree:
                # Offer to open Student Records window
                if messagebox.askyesno(_t("student.open_records_title"),
                                      _t("student.open_records_msg")):
                    dialog.destroy()
                    self.show_student_records()
                return

            # Clear existing data
            for item in self.student_tree.get_children():
                self.student_tree.delete(item)

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Build query based on search type
                search_field_map = {
                    _t("student.first_name"): 'first_name',
                    _t("student.last_name"): 'last_name',
                    _t("student.student_id"): 'student_id',
                    _t("student.col_course"): 'course',
                    _t("common.email"): 'email_address'
                }

                field = search_field_map.get(search_type.get(), 'first_name')

                safe_field = validate_identifier(field, "column")
                if field == 'student_id':
                    query = 'SELECT * FROM students WHERE [' + safe_field + '] = ?'
                    cursor.execute(query, (term,))
                else:
                    query = 'SELECT * FROM students WHERE LOWER([' + safe_field + ']) LIKE LOWER(?)'
                    cursor.execute(query, (f'%{term}%',))

                results = cursor.fetchall()

                # Populate treeview with results
                for student in results:
                    student_id = student[0]
                    email_address = student[1]
                    first_name = student[3] or ''
                    middle_name = student[4] or ''
                    last_name = student[5] or ''
                    course = student[9]
                    reg_date = student[10]
                    full_name = f"{first_name} {middle_name} {last_name}".replace('  ', ' ').strip()

                    self.student_tree.insert('', tk.END, values=(
                        student_id, full_name, email_address, course, reg_date[:10] if reg_date else 'N/A'
                    ))

                conn.close()

                if not results:
                    messagebox.showinfo(_t("student.search_students"), _t("student.no_results"))
                else:
                    messagebox.showinfo(_t("student.search_students"), _t("student.found_results").replace("{count}", str(len(results))))

                dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Search failed: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=2, column=0, columnspan=2, pady=20)

    def show_all_and_close():
        """Show all students and close search dialog"""
        try:
            if hasattr(self, 'student_tree') and self.student_tree:
                self.view_students()
            dialog.destroy()
        except Exception as e:
            print(f"Error showing all students: {e}")
            dialog.destroy()

    ttk.Button(button_frame, text=_t("common.search"), command=perform_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.show_all"), command=show_all_and_close).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    search_term.focus()
