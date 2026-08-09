"""
Query Builder - A standalone tkinter GUI for visually building and executing SQL queries.

Features: open SQLite databases, visual column selection, WHERE conditions,
ORDER BY, LIMIT, JOINs, SQL preview, execute and view results, CSV export.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import sqlite3
import csv
import os
import re


class ConditionRow:
    """A single WHERE condition row."""

    def __init__(self, parent, columns, on_remove):
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.X, pady=1)

        self.logic_var = tk.StringVar(value="AND")
        logic_cb = ttk.Combobox(self.frame, textvariable=self.logic_var,
                                values=["AND", "OR"], width=5, state="readonly")
        logic_cb.pack(side=tk.LEFT)

        self.column_var = tk.StringVar()
        self.column_cb = ttk.Combobox(self.frame, textvariable=self.column_var,
                                       values=columns, width=18, state="readonly")
        self.column_cb.pack(side=tk.LEFT, padx=4)

        self.operator_var = tk.StringVar(value="=")
        op_cb = ttk.Combobox(self.frame, textvariable=self.operator_var,
                             values=["=", "!=", "<", ">", "<=", ">=", "LIKE",
                                     "NOT LIKE", "IN", "NOT IN", "IS NULL", "IS NOT NULL",
                                     "BETWEEN"],
                             width=10, state="readonly")
        op_cb.pack(side=tk.LEFT, padx=4)

        self.value_var = tk.StringVar()
        self.value_entry = ttk.Entry(self.frame, textvariable=self.value_var, width=20)
        self.value_entry.pack(side=tk.LEFT, padx=4)

        ttk.Button(self.frame, text="X", width=3,
                   command=lambda: on_remove(self)).pack(side=tk.LEFT)

    def update_columns(self, columns):
        self.column_cb.config(values=columns)

    def get_sql(self, is_first=False):
        col = self.column_var.get()
        op = self.operator_var.get()
        val = self.value_var.get()

        if not col:
            return "", []

        if op in ("IS NULL", "IS NOT NULL"):
            clause = f"{col} {op}"
            return clause if is_first else f"{self.logic_var.get()} {clause}", []

        if not val:
            return "", []

        if op in ("IN", "NOT IN"):
            # Expect comma-separated values
            items = [v.strip() for v in val.split(",")]
            placeholders = ", ".join(["?" for _ in items])
            clause = f"{col} {op} ({placeholders})"
            return clause if is_first else f"{self.logic_var.get()} {clause}", items

        if op == "BETWEEN":
            parts = [v.strip() for v in val.split(",")]
            if len(parts) != 2:
                return "", []
            clause = f"{col} BETWEEN ? AND ?"
            return clause if is_first else f"{self.logic_var.get()} {clause}", parts

        clause = f"{col} {op} ?"
        params = [val]
        return clause if is_first else f"{self.logic_var.get()} {clause}", params

    def destroy(self):
        self.frame.destroy()


class QueryBuilderApp:
    """Main Query Builder application."""

    def __init__(self, root):
        self.root = root
        self.root.title("SQL Query Builder")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        self.style.configure("SQL.TLabel", font=("Consolas", 10))
        self.style.configure("Run.TButton", font=("Segoe UI", 10, "bold"))

        self._conn = None
        self._db_path = None
        self._tables = []
        self._table_columns = {}
        self._conditions = []
        self._last_results = []
        self._last_headers = []

        self._build_ui()

    def _build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=6, pady=6)

        ttk.Label(toolbar, text="SQL Query Builder", style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="Open Database", command=self._open_database).pack(side=tk.LEFT)

        self.db_label = ttk.Label(toolbar, text="No database loaded")
        self.db_label.pack(side=tk.LEFT, padx=8)

        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(side=tk.RIGHT)
        ttk.Button(toolbar, text="Execute", style="Run.TButton",
                   command=self._execute_query).pack(side=tk.RIGHT, padx=4)

        # Main pane
        main_pane = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        # Top: builder
        builder_frame = ttk.Frame(main_pane)
        main_pane.add(builder_frame, weight=1)

        builder_pane = ttk.PanedWindow(builder_frame, orient=tk.HORIZONTAL)
        builder_pane.pack(fill=tk.BOTH, expand=True)

        # Left: table and column selection
        left_frame = ttk.Frame(builder_pane)
        builder_pane.add(left_frame, weight=1)
        self._build_table_selector(left_frame)

        # Right: conditions and options
        right_frame = ttk.Frame(builder_pane)
        builder_pane.add(right_frame, weight=2)
        self._build_query_options(right_frame)

        # Bottom: SQL preview and results
        bottom_nb = ttk.Notebook(main_pane)
        main_pane.add(bottom_nb, weight=2)

        # SQL preview tab
        sql_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(sql_frame, text="SQL Preview")

        sql_toolbar = ttk.Frame(sql_frame)
        sql_toolbar.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(sql_toolbar, text="Copy SQL", command=self._copy_sql).pack(side=tk.LEFT)
        ttk.Button(sql_toolbar, text="Edit & Run", command=self._edit_and_run).pack(side=tk.LEFT, padx=4)

        self.sql_text = scrolledtext.ScrolledText(sql_frame, font=("Consolas", 11), height=4,
                                                   wrap=tk.WORD)
        self.sql_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.sql_text.tag_configure("keyword", foreground="#0d47a1", font=("Consolas", 11, "bold"))
        self.sql_text.tag_configure("table", foreground="#2e7d32")
        self.sql_text.tag_configure("string", foreground="#e65100")

        # Results tab
        results_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(results_frame, text="Results")

        self.results_info = ttk.Label(results_frame, text="No results")
        self.results_info.pack(fill=tk.X, padx=4, pady=4)

        results_container = ttk.Frame(results_frame)
        results_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        self.results_tree = ttk.Treeview(results_container, show="headings", selectmode="extended")

        results_scroll_y = ttk.Scrollbar(results_container, orient=tk.VERTICAL,
                                          command=self.results_tree.yview)
        results_scroll_x = ttk.Scrollbar(results_container, orient=tk.HORIZONTAL,
                                          command=self.results_tree.xview)
        self.results_tree.configure(yscrollcommand=results_scroll_y.set,
                                    xscrollcommand=results_scroll_x.set)

        self.results_tree.grid(row=0, column=0, sticky="nsew")
        results_scroll_y.grid(row=0, column=1, sticky="ns")
        results_scroll_x.grid(row=1, column=0, sticky="ew")
        results_container.grid_rowconfigure(0, weight=1)
        results_container.grid_columnconfigure(0, weight=1)

        # Raw SQL tab
        raw_frame = ttk.Frame(bottom_nb)
        bottom_nb.add(raw_frame, text="Raw SQL")

        raw_toolbar = ttk.Frame(raw_frame)
        raw_toolbar.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(raw_toolbar, text="Execute Raw SQL", style="Run.TButton",
                   command=self._execute_raw_sql).pack(side=tk.LEFT)
        ttk.Label(raw_toolbar, text="(Type any SQL query and execute directly)").pack(side=tk.LEFT, padx=8)

        self.raw_sql_text = scrolledtext.ScrolledText(raw_frame, font=("Consolas", 11), height=5)
        self.raw_sql_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

    def _build_table_selector(self, parent):
        # Table selection
        table_frame = ttk.LabelFrame(parent, text="Tables")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        ttk.Label(table_frame, text="Primary Table:").pack(padx=4, pady=(4, 0), anchor="w")
        self.table_var = tk.StringVar()
        self.table_combo = ttk.Combobox(table_frame, textvariable=self.table_var,
                                         state="readonly", width=28)
        self.table_combo.pack(padx=4, pady=4, fill=tk.X)
        self.table_combo.bind("<<ComboboxSelected>>", self._on_table_selected)

        # Columns
        ttk.Label(table_frame, text="Columns:").pack(padx=4, anchor="w")

        col_toolbar = ttk.Frame(table_frame)
        col_toolbar.pack(fill=tk.X, padx=4)
        ttk.Button(col_toolbar, text="Select All", command=self._select_all_columns).pack(side=tk.LEFT)
        ttk.Button(col_toolbar, text="Deselect All",
                   command=self._deselect_all_columns).pack(side=tk.LEFT, padx=4)

        # Scrollable column checkboxes
        col_canvas = tk.Canvas(table_frame, highlightthickness=0)
        col_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=col_canvas.yview)
        self.columns_frame = ttk.Frame(col_canvas)

        self.columns_frame.bind("<Configure>",
                                lambda e: col_canvas.configure(scrollregion=col_canvas.bbox("all")))
        col_canvas.create_window((0, 0), window=self.columns_frame, anchor="nw")
        col_canvas.configure(yscrollcommand=col_scrollbar.set)

        col_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        col_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=4)

        self._column_vars = {}

    def _build_query_options(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # WHERE tab
        where_frame = ttk.Frame(nb)
        nb.add(where_frame, text="WHERE")

        where_toolbar = ttk.Frame(where_frame)
        where_toolbar.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(where_toolbar, text="+ Add Condition",
                   command=self._add_condition).pack(side=tk.LEFT)
        ttk.Button(where_toolbar, text="Clear All",
                   command=self._clear_conditions).pack(side=tk.LEFT, padx=4)

        self.conditions_frame = ttk.Frame(where_frame)
        self.conditions_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        # JOIN tab
        join_frame = ttk.Frame(nb)
        nb.add(join_frame, text="JOIN")
        self._build_join_section(join_frame)

        # ORDER BY / LIMIT tab
        order_frame = ttk.Frame(nb)
        nb.add(order_frame, text="ORDER BY / LIMIT")
        self._build_order_section(order_frame)

        # Aggregate tab
        agg_frame = ttk.Frame(nb)
        nb.add(agg_frame, text="Aggregate")
        self._build_aggregate_section(agg_frame)

    def _build_join_section(self, parent):
        self.join_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, text="Enable JOIN", variable=self.join_enabled_var,
                        command=self._update_sql_preview).pack(padx=8, pady=4, anchor="w")

        join_grid = ttk.Frame(parent)
        join_grid.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(join_grid, text="Join Type:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.join_type_var = tk.StringVar(value="INNER JOIN")
        ttk.Combobox(join_grid, textvariable=self.join_type_var,
                     values=["INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "CROSS JOIN"],
                     state="readonly", width=15).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(join_grid, text="Join Table:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.join_table_var = tk.StringVar()
        self.join_table_combo = ttk.Combobox(join_grid, textvariable=self.join_table_var,
                                              state="readonly", width=20)
        self.join_table_combo.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self.join_table_combo.bind("<<ComboboxSelected>>", self._on_join_table_selected)

        ttk.Label(join_grid, text="On (Left Column):").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.join_left_col_var = tk.StringVar()
        self.join_left_combo = ttk.Combobox(join_grid, textvariable=self.join_left_col_var,
                                             state="readonly", width=20)
        self.join_left_combo.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(join_grid, text="On (Right Column):").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        self.join_right_col_var = tk.StringVar()
        self.join_right_combo = ttk.Combobox(join_grid, textvariable=self.join_right_col_var,
                                              state="readonly", width=20)
        self.join_right_combo.grid(row=3, column=1, sticky="w", padx=4, pady=4)

    def _build_order_section(self, parent):
        order_grid = ttk.Frame(parent)
        order_grid.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(order_grid, text="ORDER BY:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.order_col_var = tk.StringVar()
        self.order_col_combo = ttk.Combobox(order_grid, textvariable=self.order_col_var,
                                             state="readonly", width=20)
        self.order_col_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        self.order_dir_var = tk.StringVar(value="ASC")
        ttk.Combobox(order_grid, textvariable=self.order_dir_var,
                     values=["ASC", "DESC"], state="readonly", width=6).grid(
            row=0, column=2, sticky="w", padx=4, pady=4)

        ttk.Label(order_grid, text="LIMIT:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.limit_var = tk.StringVar()
        ttk.Entry(order_grid, textvariable=self.limit_var, width=10).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(order_grid, text="(leave empty for no limit)").grid(
            row=1, column=2, sticky="w", padx=4, pady=4)

        ttk.Label(order_grid, text="OFFSET:").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.offset_var = tk.StringVar()
        ttk.Entry(order_grid, textvariable=self.offset_var, width=10).grid(
            row=2, column=1, sticky="w", padx=4, pady=4)

    def _build_aggregate_section(self, parent):
        self.agg_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, text="Enable Aggregate Functions",
                        variable=self.agg_enabled_var,
                        command=self._update_sql_preview).pack(padx=8, pady=4, anchor="w")

        agg_grid = ttk.Frame(parent)
        agg_grid.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(agg_grid, text="Function:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.agg_func_var = tk.StringVar(value="COUNT")
        ttk.Combobox(agg_grid, textvariable=self.agg_func_var,
                     values=["COUNT", "SUM", "AVG", "MIN", "MAX"],
                     state="readonly", width=10).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(agg_grid, text="Column:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.agg_col_var = tk.StringVar(value="*")
        self.agg_col_combo = ttk.Combobox(agg_grid, textvariable=self.agg_col_var,
                                           state="readonly", width=18)
        self.agg_col_combo.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(agg_grid, text="GROUP BY:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.group_col_var = tk.StringVar()
        self.group_col_combo = ttk.Combobox(agg_grid, textvariable=self.group_col_var,
                                             state="readonly", width=18)
        self.group_col_combo.grid(row=1, column=1, sticky="w", padx=4, pady=4)

    def _open_database(self):
        path = filedialog.askopenfilename(
            title="Open SQLite Database",
            filetypes=[("SQLite databases", "*.db *.sqlite *.sqlite3"),
                       ("All files", "*.*")]
        )
        if not path:
            return

        try:
            if self._conn:
                self._conn.close()

            self._conn = sqlite3.connect(path)
            self._db_path = path
            self.db_label.config(text=os.path.basename(path))

            # Get tables
            cursor = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            self._tables = [row[0] for row in cursor.fetchall()]

            # Get columns for each table
            self._table_columns.clear()
            for table in self._tables:
                cursor = self._conn.execute(f"PRAGMA table_info([{table}])")
                cols = []
                for row in cursor.fetchall():
                    cols.append({
                        "name": row[1],
                        "type": row[2],
                        "notnull": row[3],
                        "pk": row[5],
                    })
                self._table_columns[table] = cols

            self.table_combo.config(values=self._tables)
            self.join_table_combo.config(values=self._tables)

            if self._tables:
                self.table_combo.set(self._tables[0])
                self._on_table_selected()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open database: {e}")

    def _on_table_selected(self, event=None):
        table = self.table_var.get()
        if not table or table not in self._table_columns:
            return

        # Clear column checkboxes
        for widget in self.columns_frame.winfo_children():
            widget.destroy()
        self._column_vars.clear()

        cols = self._table_columns[table]
        for col_info in cols:
            name = col_info["name"]
            dtype = col_info["type"]
            pk = " (PK)" if col_info["pk"] else ""

            var = tk.BooleanVar(value=True)
            self._column_vars[name] = var
            text = f"{name} [{dtype}]{pk}"
            ttk.Checkbutton(self.columns_frame, text=text, variable=var,
                            command=self._update_sql_preview).pack(anchor="w")

        # Update all column-dependent combos
        col_names = [c["name"] for c in cols]
        for cond in self._conditions:
            cond.update_columns(col_names)

        self.order_col_combo.config(values=[""] + col_names)
        self.join_left_combo.config(values=col_names)

        agg_cols = ["*"] + col_names
        self.agg_col_combo.config(values=agg_cols)
        self.group_col_combo.config(values=[""] + col_names)

        self._update_sql_preview()

    def _on_join_table_selected(self, event=None):
        join_table = self.join_table_var.get()
        if join_table in self._table_columns:
            cols = [c["name"] for c in self._table_columns[join_table]]
            self.join_right_combo.config(values=cols)

    def _select_all_columns(self):
        for var in self._column_vars.values():
            var.set(True)
        self._update_sql_preview()

    def _deselect_all_columns(self):
        for var in self._column_vars.values():
            var.set(False)
        self._update_sql_preview()

    def _add_condition(self):
        table = self.table_var.get()
        cols = [c["name"] for c in self._table_columns.get(table, [])]
        cond = ConditionRow(self.conditions_frame, cols, self._remove_condition)
        self._conditions.append(cond)

    def _remove_condition(self, cond):
        cond.destroy()
        self._conditions.remove(cond)

    def _clear_conditions(self):
        for cond in self._conditions:
            cond.destroy()
        self._conditions.clear()

    def _build_query(self):
        """Build the SQL query from the GUI state. Returns (sql, params)."""
        table = self.table_var.get()
        if not table:
            return "", []

        # SELECT columns
        if self.agg_enabled_var.get():
            func = self.agg_func_var.get()
            col = self.agg_col_var.get() or "*"
            group = self.group_col_var.get()
            if group:
                select_clause = f"{group}, {func}({col})"
            else:
                select_clause = f"{func}({col})"
        else:
            selected = [name for name, var in self._column_vars.items() if var.get()]
            if not selected:
                select_clause = "*"
            else:
                select_clause = ", ".join(f"[{c}]" for c in selected)

        # FROM
        from_clause = f"[{table}]"

        # JOIN
        if self.join_enabled_var.get():
            join_table = self.join_table_var.get()
            join_type = self.join_type_var.get()
            left_col = self.join_left_col_var.get()
            right_col = self.join_right_col_var.get()
            if join_table and left_col and right_col:
                from_clause += (f"\n  {join_type} [{join_table}] "
                                f"ON [{table}].[{left_col}] = [{join_table}].[{right_col}]")

        sql = f"SELECT {select_clause}\nFROM {from_clause}"

        # WHERE
        params = []
        where_parts = []
        for i, cond in enumerate(self._conditions):
            clause, cond_params = cond.get_sql(is_first=(i == 0))
            if clause:
                where_parts.append(clause)
                params.extend(cond_params)

        if where_parts:
            sql += "\nWHERE " + "\n  ".join(where_parts)

        # GROUP BY
        if self.agg_enabled_var.get():
            group = self.group_col_var.get()
            if group:
                sql += f"\nGROUP BY [{group}]"

        # ORDER BY
        order_col = self.order_col_var.get()
        if order_col:
            order_dir = self.order_dir_var.get()
            sql += f"\nORDER BY [{order_col}] {order_dir}"

        # LIMIT
        limit = self.limit_var.get().strip()
        if limit and limit.isdigit():
            sql += f"\nLIMIT {limit}"

            offset = self.offset_var.get().strip()
            if offset and offset.isdigit():
                sql += f" OFFSET {offset}"

        return sql, params

    def _update_sql_preview(self, *_args):
        sql, params = self._build_query()
        self.sql_text.delete("1.0", tk.END)
        self.sql_text.insert("1.0", sql)

        if params:
            self.sql_text.insert(tk.END, f"\n\n-- Parameters: {params}")

        self._highlight_sql()

    def _highlight_sql(self):
        """Apply basic SQL syntax highlighting."""
        for tag in ("keyword", "table", "string"):
            self.sql_text.tag_remove(tag, "1.0", tk.END)

        text = self.sql_text.get("1.0", tk.END)

        keywords = (
            r'\b(SELECT|FROM|WHERE|AND|OR|ORDER BY|GROUP BY|HAVING|LIMIT|OFFSET|'
            r'INNER JOIN|LEFT JOIN|RIGHT JOIN|CROSS JOIN|JOIN|ON|AS|'
            r'INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|IN|NOT|LIKE|BETWEEN|'
            r'IS NULL|IS NOT NULL|ASC|DESC|COUNT|SUM|AVG|MIN|MAX|DISTINCT)\b'
        )
        for m in re.finditer(keywords, text, re.IGNORECASE):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.sql_text.tag_add("keyword", start, end)

        # Highlight quoted strings
        for m in re.finditer(r"'[^']*'", text):
            start = f"1.0+{m.start()}c"
            end = f"1.0+{m.end()}c"
            self.sql_text.tag_add("string", start, end)

    def _execute_query(self):
        sql, params = self._build_query()
        if not sql:
            messagebox.showwarning("No Query", "Build a query first.")
            return
        self._run_sql(sql, params)

    def _execute_raw_sql(self):
        sql = self.raw_sql_text.get("1.0", tk.END).strip()
        if not sql:
            messagebox.showwarning("No SQL", "Enter a SQL query.")
            return
        self._run_sql(sql, [])

    def _run_sql(self, sql, params):
        if not self._conn:
            messagebox.showwarning("No Database", "Open a database first.")
            return

        try:
            cursor = self._conn.execute(sql, params)

            if cursor.description:
                headers = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
            else:
                # Non-SELECT statement
                self._conn.commit()
                self.results_info.config(
                    text=f"Statement executed. {cursor.rowcount} rows affected.")
                return

            self._last_headers = headers
            self._last_results = rows

            self._display_results(headers, rows)

        except sqlite3.Error as e:
            messagebox.showerror("SQL Error", f"Error executing query:\n{e}")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error:\n{type(e).__name__}: {e}")

    def _display_results(self, headers, rows):
        # Clear existing
        self.results_tree.delete(*self.results_tree.get_children())

        # Configure columns
        self.results_tree["columns"] = headers
        for col in headers:
            self.results_tree.heading(col, text=col, command=lambda c=col: self._sort_results(c))
            self.results_tree.column(col, width=120, minwidth=60)

        # Insert rows
        for row in rows:
            display = [str(v) if v is not None else "NULL" for v in row]
            self.results_tree.insert("", "end", values=display)

        self.results_info.config(text=f"{len(rows)} row(s) returned, {len(headers)} column(s)")

    def _sort_results(self, col):
        """Sort results tree by clicking column header."""
        items = [(self.results_tree.set(k, col), k) for k in self.results_tree.get_children()]
        try:
            items.sort(key=lambda t: float(t[0]) if t[0] != "NULL" else float('-inf'))
        except ValueError:
            items.sort(key=lambda t: t[0])

        for index, (_, k) in enumerate(items):
            self.results_tree.move(k, "", index)

    def _copy_sql(self):
        sql, params = self._build_query()
        self.root.clipboard_clear()
        self.root.clipboard_append(sql)
        messagebox.showinfo("Copied", "SQL query copied to clipboard.")

    def _edit_and_run(self):
        """Copy generated SQL to raw SQL tab for editing."""
        sql, params = self._build_query()
        self.raw_sql_text.delete("1.0", tk.END)
        self.raw_sql_text.insert("1.0", sql)

    def _export_csv(self):
        if not self._last_results:
            messagebox.showinfo("Export", "No results to export. Run a query first.")
            return

        path = filedialog.asksaveasfilename(
            title="Export to CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._last_headers)
                for row in self._last_results:
                    writer.writerow(row)
            messagebox.showinfo("Exported",
                                f"Exported {len(self._last_results)} rows to {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def __del__(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    app = QueryBuilderApp(root)
    root.mainloop()
