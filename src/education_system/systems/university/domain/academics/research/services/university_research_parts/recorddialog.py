"""Extracted class implementation."""

from .. import university_research_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class RecordDialog(tk.Toplevel):
    """Generic edit/create dialog driven by a list of FieldSpec."""

    def __init__(self, parent, title, fields, record=None, people_lookup=None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PALETTE["bg"])
        self.transient(parent)
        # A transient Toplevel isn't mapped synchronously, so an immediate
        # grab_set() raises "grab failed: window not viewable". Defer the grab
        # until the window is actually viewable.
        self._grab_when_viewable()
        self.resizable(False, False)

        self.fields = fields
        self.record = record or {}
        self.people_lookup = people_lookup or {}
        self.vars = {}
        self.result = None

        frame = ttk.Frame(self, style="Panel.TFrame")
        frame.pack(fill="both", expand=True, padx=2, pady=2)

        header = ttk.Frame(frame, style="Header.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=title, style="Header.TLabel").pack(
            anchor="w", padx=18, pady=12)

        body = ttk.Frame(frame, style="Panel.TFrame")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        for i, f in enumerate(fields):
            ttk.Label(body, text=f.label + (" *" if f.required else ""),
                      style="Panel.TLabel", font=("Segoe UI", 10)).grid(
                row=i, column=0, sticky="nw", pady=6, padx=(0, 12))

            val = self.record.get(f.key, f.default)
            if val is None:
                val = ""

            if f.kind == "multiline":
                text = tk.Text(body, width=42, height=4, font=("Segoe UI", 10),
                               relief="solid", borderwidth=1)
                text.insert("1.0", str(val))
                text.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = text
            elif f.kind == "combo":
                var = tk.StringVar(value=str(val))
                cb = ttk.Combobox(body, textvariable=var, values=f.choices,
                                  width=40, state="readonly")
                cb.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
            elif f.kind == "people":
                # choices is a list of (id, display) tuples
                display_map = {d: i for i, d in f.choices}
                self.vars[f.key + "_map"] = display_map
                inverse = {i: d for i, d in f.choices}
                current = inverse.get(val, "")
                var = tk.StringVar(value=current)
                cb = ttk.Combobox(body, textvariable=var,
                                  values=[""] + [d for _, d in f.choices],
                                  width=40, state="readonly")
                cb.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
            elif f.kind == "bool":
                var = tk.BooleanVar(value=bool(val))
                cb = ttk.Checkbutton(body, variable=var, style="TCheckbutton")
                cb.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
            else:
                var = tk.StringVar(value=str(val))
                entry = ttk.Entry(body, textvariable=var, width=44)
                entry.grid(row=i, column=1, sticky="w", pady=6)
                self.vars[f.key] = var
                if f.hint:
                    ttk.Label(body, text=f.hint, style="Muted.TLabel").grid(
                        row=i, column=2, sticky="w", padx=8)

        btn_row = ttk.Frame(frame, style="Panel.TFrame")
        btn_row.pack(fill="x", padx=20, pady=(0, 18))
        ttk.Button(btn_row, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(btn_row, text="Save", style="Accent.TButton",
                   command=self._save).pack(side="right", padx=(0, 8))

        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"+{max(px, 0)}+{max(py, 0)}")

    def _grab_when_viewable(self):
        """Set the modal grab once the window is viewable, retrying until then.

        grab_set() raises TclError if the window isn't yet mapped; a transient
        Toplevel maps asynchronously, so retry on the event loop.
        """
        try:
            if self.winfo_viewable():
                self.grab_set()
            else:
                self.after(10, self._grab_when_viewable)
        except tk.TclError:
            # Window was destroyed before it became viewable — nothing to grab.
            pass

    def _save(self):
        out = {}
        for f in self.fields:
            widget = self.vars[f.key]
            if f.kind == "multiline":
                v = widget.get("1.0", "end").strip()
            elif f.kind == "bool":
                v = 1 if widget.get() else 0
            elif f.kind == "people":
                display = widget.get()
                mapping = self.vars[f.key + "_map"]
                v = mapping.get(display)
            else:
                v = widget.get().strip()

            if f.required and (v is None or v == ""):
                messagebox.showerror("Missing field",
                                     f"Please provide: {f.label}", parent=self)
                return

            if f.kind == "date" and v:
                try:
                    v = parse_date(v)
                except ValueError as e:
                    messagebox.showerror("Invalid date", str(e), parent=self)
                    return
            elif f.kind == "int" and v != "":
                try:
                    v = int(v)
                except ValueError:
                    messagebox.showerror("Invalid number",
                                         f"{f.label} must be a whole number.",
                                         parent=self)
                    return
            elif f.kind == "float" and v != "":
                try:
                    v = float(v)
                except ValueError:
                    messagebox.showerror("Invalid number",
                                         f"{f.label} must be a number.",
                                         parent=self)
                    return

            out[f.key] = v if v != "" else None

        self.result = out
        self.destroy()
