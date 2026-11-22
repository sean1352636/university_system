"""Letters screen: the template library, mail merge, sent letters and replies.

The old Letter Templates window's tabs keep their place: **Active**,
**Drafts**, **Archived**, **All** (Category, Recipient and Format filters,
Apply; columns ID, Name, Category, Recipient, Format, Status, Uses; the
Preview and Merge fields panes; New, Edit, Activate, Archive, Retire, Change
status, Duplicate, Render, Record use, Delete, Refresh) and **Summary**. Added
to each list: a search box, Send…, and History.

New tabs:

* **Send** - choose an active template and the pupils (chosen pupils, a form
  or a year group), fill the custom fields and the reply-by date, preview one
  pupil's letter, then send; families without e-mail get a print copy.
* **Sent letters** - each mail merge with its letters, e-mails and replies;
  View letters (record replies), Print copies…, Export CSV…, Chase replies,
  Pupil's letters…
* **Replies** - every reply slip still waiting, to record or chase.

The rules are in :mod:`modules.communication.domain.letters`.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.secondary.modules.communication.domain import letters as L
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.ui.gui.components import widgets as W

logger = logging.getLogger(__name__)
_ERRORS = W.ERRORS
_problems = W.problems
_text_window = W.text_window
_form = W.form_dialog
_SCOPES = {"Active": "active", "Drafts": "drafts", "Archived": "archived", "All": "all"}
_AUDIENCES = ("Chosen pupils", "Form", "Year group")


def _fields(t: L.Template | None) -> list:
    return [
        ("name", "Name", t.name if t else "", None),
        ("description", "Description", t.description if t else "", None),
        ("category", "Category", t.category if t else L.DEFAULT_CATEGORY, list(L.CATEGORIES)),
        ("recipient_type", "Recipient", t.recipient_type if t else L.DEFAULT_RECIPIENT,
         list(L.RECIPIENT_TYPES)),
        ("format", "Format", t.format if t else L.DEFAULT_FORMAT, list(L.FORMATS)),
        ("subject_line", "Subject line", t.subject_line if t else "", None),
        ("body", "Body ({pupil_name}, {parent_name}…)", t.body if t else "", "text"),
        ("letterhead", "Letterhead", t.letterhead if t else "", "text"),
        ("signature", "Signature", t.signature if t else "", "text"),
        ("footer", "Footer", t.footer if t else "", "text"),
        ("sender_role", "Sender role", t.sender_role if t else "", None),
        ("merge_fields", "Custom fields (e.g. trip, cost)", t.merge_fields if t else "", None),
        ("attachments_ref", "Attachments note", t.attachments_ref if t else "", None),
        ("reply_slip", "Reply slip (yes / no)", t.reply_slip if t else False, "check"),
        ("reply_question", "Reply slip question", t.reply_question if t else "", None),
        ("notes", "Notes", t.notes if t else "", "text"),
    ]


class LettersPage:
    TABS = ("Active", "Drafts", "Archived", "All", "Summary", "Send", "Sent letters",
            "Replies")

    def __init__(self, parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> None:
        self.parent, self.principal, self.state = parent, principal, state
        self.open_pupil = open_pupil
        self.editor = L.is_editor(principal)
        activity_log.record("letters.view")
        ttk.Label(parent, text="Letters", font=("", 16, "bold")).pack(anchor="w")
        self.summary_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.summary_var, foreground="#666").pack(
            anchor="w", pady=(0, 6))
        self.book = ttk.Notebook(parent)
        self.book.pack(fill="both", expand=True)
        self.tabs = {n: ttk.Frame(self.book, padding=8) for n in self.TABS}
        for n, f in self.tabs.items():
            self.book.add(f, text=n)
        self.lists: dict[str, dict[str, Any]] = {}
        self._built: set[str] = set()
        start = state.get("tab") if state.get("tab") in self.TABS else "Active"
        self.book.select(self.TABS.index(start))
        self.book.bind("<<NotebookTabChanged>>", self._on_tab)
        self._on_tab()

    # ── helpers ──────────────────────────────────────────────────────

    def _top(self):
        return self.parent.winfo_toplevel()

    def _err(self, title: str, e: Exception) -> None:
        messagebox.showerror(title, _problems(e), parent=self._top())

    def _info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text, parent=self._top())

    def _run(self, title: str, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except _ERRORS as e:
            self._err(title, e)
            return None

    def _button(self, bar, text: str, command, enabled: bool = True) -> None:
        b = ttk.Button(bar, text=text, command=command)
        if not enabled:
            b.state(["disabled"])
        b.pack(side="left", padx=2)

    def _current(self) -> str:
        return self.TABS[self.book.index(self.book.select())]

    def _on_tab(self, _e=None) -> None:
        name = self._current()
        self.state["tab"] = name
        if name not in self._built:
            self._built.add(name)
            {"Summary": self._build_summary, "Send": self._build_send,
             "Sent letters": self._build_sent, "Replies": self._build_replies}.get(
                name, lambda tab: self._build_list(name, tab))(self.tabs[name])
        self._refresh(name)

    def _refresh(self, name: str) -> None:
        {"Summary": self.refresh_summary, "Send": self.refresh_send,
         "Sent letters": self.refresh_sent, "Replies": self.refresh_replies}.get(
            name, lambda: self.refresh_list(name))()

    def _refresh_all(self) -> None:
        for name in list(self._built):
            self._refresh(name)
        self._update_summary()

    def _update_summary(self) -> None:
        s = L.summary()
        self.summary_var.set(f"Templates: {s.total} ({s.active} active)    Mail merges: "
                             f"{s.sends}    Letters sent: {s.letters_sent}    Awaiting "
                             f"replies: {s.awaiting_replies}")

    # ── the library (the old tabs) ───────────────────────────────────

    def _build_list(self, name: str, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        v = {"cat": tk.StringVar(), "rec": tk.StringVar(), "fmt": tk.StringVar(),
             "search": tk.StringVar()}
        for label, var, values, width in (("Category:", v["cat"], ["", *L.CATEGORIES], 18),
                                          ("Recipient:", v["rec"], ["", *L.RECIPIENT_TYPES],
                                           14),
                                          ("Format:", v["fmt"], ["", *L.FORMATS], 16)):
            ttk.Label(bar, text=label).pack(side="left", padx=(0, 2))
            ttk.Combobox(bar, textvariable=var, values=values, state="readonly",
                         width=width).pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="Search:").pack(side="left")
        ent = ttk.Entry(bar, textvariable=v["search"], width=14)
        ent.pack(side="left", padx=(2, 4))
        ent.bind("<Return>", lambda _e: self.refresh_list(name))
        self._button(bar, "Apply", lambda: self.refresh_list(name))
        pane = ttk.Panedwindow(tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left, right = ttk.Frame(pane), ttk.Frame(pane, padding=(8, 0, 0, 0))
        pane.add(left, weight=3)
        pane.add(right, weight=2)
        tree = W.tree(left, [("id", "ID", 45), ("name", "Name", 200),
                             ("category", "Category", 120), ("recipient", "Recipient", 110),
                             ("format", "Format", 120), ("status", "Status", 70),
                             ("uses", "Uses", 50)], height=14, stretch={"name"},
                      tags=W.STANDARD_TAGS)
        tree.bind("<<TreeviewSelect>>", lambda _e: self._preview_selected(name))
        tree.bind("<Double-1>", lambda _e: self.edit())
        ttk.Label(right, text="Preview", font=("", 10, "bold")).pack(anchor="w")
        prev = tk.Text(right, wrap="word", height=14, width=48, state="disabled")
        prev.pack(fill="both", expand=True)
        ttk.Label(right, text="Merge fields", font=("", 10, "bold")).pack(anchor="w",
                                                                         pady=(6, 0))
        fields_var = tk.StringVar(value="(this template has no placeholders)")
        ttk.Label(right, textvariable=fields_var, wraplength=360, justify="left").pack(
            anchor="w")
        bar2 = ttk.Frame(tab)
        bar2.pack(fill="x", pady=(4, 0))
        ed = self.editor
        for text, cmd, ok in (("New", self.new, True), ("Edit", self.edit, True),
                              ("Activate", lambda: self._status("Active"), ed),
                              ("Archive", lambda: self._status("Archived"), ed),
                              ("Retire", lambda: self._status("Retired"), ed),
                              ("Change status", self.set_status, ed),
                              ("Duplicate", self.duplicate, True), ("Render", self.render, True),
                              ("Record use", self.record_use, True),
                              ("Delete", self.delete, True),
                              ("Refresh", lambda: self.refresh_list(name), True)):
            self._button(bar2, text, cmd, ok)
        bar3 = ttk.Frame(tab)
        bar3.pack(fill="x", pady=(4, 0))
        self._button(bar3, "Send…", self.send_selected)
        self._button(bar3, "History", self.history)
        self.lists[name] = {"tree": tree, "vars": v, "rows": {}, "preview": prev,
                            "fields": fields_var}

    def refresh_list(self, name: str) -> None:
        x = self.lists.get(name)
        if x is None:
            return
        v = x["vars"]
        rows = L.list_templates(scope=_SCOPES[name], category=v["cat"].get() or None,
                                recipient_type=v["rec"].get() or None,
                                format=v["fmt"].get() or None,
                                search=v["search"].get() or None)
        tree = x["tree"]
        tree.delete(*tree.get_children())
        x["rows"] = {}
        for t in rows:
            x["rows"][str(t.template_id)] = t
            tree.insert("", "end", iid=str(t.template_id),
                        tags=("muted",) if t.status in ("Archived", "Retired") else (),
                        values=(t.template_id, t.name, t.category, t.recipient_type, t.format,
                                t.status, t.use_count))
        if not self.summary_var.get():
            self._update_summary()

    def _preview_selected(self, name: str) -> None:
        x = self.lists[name]
        sel = x["tree"].selection()
        if not sel:
            return
        t = x["rows"][sel[0]]
        r = L.preview(t)
        x["preview"].configure(state="normal")
        x["preview"].delete("1.0", "end")
        x["preview"].insert("1.0", f"Subject: {r.subject}\n\n{r.body}"
                            + (f"\n\n[Reply slip] {t.reply_question}" if t.reply_slip else ""))
        x["preview"].configure(state="disabled")
        fields = t.detected_placeholders
        x["fields"].set(", ".join("{" + f + "}" + (" (custom)" if f in t.custom_fields else "")
                                  for f in fields) or "(this template has no placeholders)")

    def _selected(self, title: str) -> L.Template | None:
        x = self.lists.get(self._current())
        sel = x["tree"].selection() if x else ()
        if not sel:
            self._info(title, "Select a template first.")
            return None
        return x["rows"][sel[0]]

    def new(self) -> None:
        def save(v):
            if not self.editor:
                v["status"] = "Draft"
            else:
                v.setdefault("status", "Draft")
            L.create_template(v, actor=self.principal)
            self._refresh_all()
        fields = _fields(None)
        if self.editor:
            fields.insert(5, ("status", "Status", "Draft", list(L.STATUSES)))
        _form(self.parent, "New template", fields, save,
              note="Merge fields: " + ", ".join("{" + f + "}" for f in L.STANDARD_FIELDS)
              + ". List any others as custom fields; they are filled in when sending.")

    def edit(self) -> None:
        t = self._selected("Edit")
        if t is None:
            return

        def save(v):
            L.update_template(t.template_id, v, actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Edit template #{t.template_id}", _fields(t), save)

    def _status(self, status: str) -> None:
        t = self._selected(status)
        if t and self._run(status, lambda: L.set_status(t.template_id, status,
                                                        actor=self.principal)):
            self._refresh_all()

    def set_status(self) -> None:
        t = self._selected("Change status")
        if t is None:
            return

        def save(v):
            L.set_status(t.template_id, v["status"], actor=self.principal)
            self._refresh_all()
        _form(self.parent, f"Status - {t.name}",
              [("status", "Status", t.status, list(L.STATUSES))], save)

    def duplicate(self) -> None:
        t = self._selected("Duplicate")
        if t and self._run("Duplicate", lambda: L.duplicate(t.template_id,
                                                            actor=self.principal)):
            self._refresh_all()

    def render(self) -> None:
        """The old Render: type a value for each field and see the result."""
        t = self._selected("Render")
        if t is None:
            return
        fields = t.detected_placeholders
        if not fields:
            r = L.render(t, {})
            _text_window(self.parent, "Output", f"Subject: {r.subject}\n\n{r.body}")
            return

        def save(v):
            r = L.render(t, v)
            _text_window(self.parent, "Output", f"Subject: {r.subject}\n\n{r.body}"
                         + (f"\n\n(Not filled in: {', '.join(r.missing)})" if r.missing else ""))
        _form(self.parent, f"Render - {t.name}", [(f, "{" + f + "}", "", None) for f in fields],
              save)

    def record_use(self) -> None:
        t = self._selected("Record use")
        if t and self._run("Record use", lambda: L.record_use(t.template_id,
                                                              actor=self.principal)):
            self._refresh_all()

    def delete(self) -> None:
        t = self._selected("Delete")
        if t and messagebox.askyesno("Delete", f"Delete template '{t.name}'? Letters already "
                                     "sent keep their copy.", parent=self._top()):
            if self._run("Delete", lambda: L.delete_template(t.template_id,
                                                             actor=self.principal)):
                self._refresh_all()

    def history(self) -> None:
        t = self._selected("History")
        if t:
            _text_window(self.parent, "History", "\n".join(
                f"{h['at']}  {h['actor']:<14} {h['action']:<16} "
                + ", ".join(f"{k}={v}" for k, v in h["detail"].items())
                for h in L.history(template_id=t.template_id)) or "No changes recorded.")

    def send_selected(self) -> None:
        t = self._selected("Send")
        if t is None:
            return
        if t.status != "Active":
            self._info("Send", "Only active templates are sent - activate it first.")
            return
        self.state["send_template"] = t.template_id
        self.book.select(self.TABS.index("Send"))

    # ── Summary (the old Summary tab) ────────────────────────────────

    def _build_summary(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self._button(bar, "Refresh", self.refresh_summary)
        self.text = tk.Text(tab, wrap="word", font=("TkFixedFont", 10), state="disabled")
        self.text.pack(fill="both", expand=True)

    def refresh_summary(self) -> None:
        s = L.summary()
        lines = ["Templates", "---------"]
        for label, n in (("Total", s.total), ("Active", s.active), ("Drafts", s.drafts),
                         ("Archived", s.archived), ("Retired", s.retired),
                         ("Total uses", s.total_uses), ("With reply slip", s.with_reply_slip)):
            lines.append(f"  {label:<18}: {n}")
        if s.most_used:
            lines += ["", "Most used", "---------"]
            lines += [f"  {n:<36} {c}" for n, c in s.most_used]
        for title, d in (("By category", s.by_category), ("By recipient", s.by_recipient),
                         ("By format", s.by_format)):
            lines += ["", title, "-" * len(title)]
            lines += [f"  {k:<24}: {v}" for k, v in sorted(d.items())]
        lines += ["", "Sending", "-------", f"  Mail merges       : {s.sends}",
                  f"  Letters sent      : {s.letters_sent}",
                  f"  Awaiting replies  : {s.awaiting_replies}"]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")

    # ── Send ─────────────────────────────────────────────────────────

    def _build_send(self, tab) -> None:
        top = ttk.Frame(tab)
        top.pack(fill="x")
        self.s_template = tk.StringVar()
        self.s_kind = tk.StringVar(value=_AUDIENCES[0])
        self.s_pupils = tk.StringVar()
        self.s_form = tk.StringVar()
        self.s_year = tk.StringVar()
        self.s_reply_by = tk.StringVar()
        self.s_preview_pupil = tk.StringVar()
        rows = (("Template:", ttk.Combobox(top, textvariable=self.s_template, state="readonly",
                                           width=50)),
                ("Send to:", ttk.Combobox(top, textvariable=self.s_kind, values=_AUDIENCES,
                                          state="readonly", width=16)),
                ("Pupils (admission nos.):", ttk.Entry(top, textvariable=self.s_pupils,
                                                       width=52)),
                ("Form:", ttk.Combobox(top, textvariable=self.s_form, state="readonly",
                                       values=["", *P.form_groups_in_use()], width=10)),
                ("Year group:", ttk.Combobox(top, textvariable=self.s_year, state="readonly",
                                             values=["", *(str(y) for y in P.YEAR_GROUPS)],
                                             width=5)),
                ("Reply by (date):", ttk.Entry(top, textvariable=self.s_reply_by, width=14)))
        for i, (label, w) in enumerate(rows):
            ttk.Label(top, text=label).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 6))
            w.grid(row=i, column=1, sticky="w")
        self.s_tcb = rows[0][1]
        self.s_tcb.bind("<<ComboboxSelected>>", lambda _e: self._template_chosen())
        if not self.editor:
            for w in (rows[3][1], rows[4][1]):
                w.state(["disabled"])
            rows[1][1].configure(values=_AUDIENCES[:1])
        self.s_custom = ttk.LabelFrame(tab, text="Custom fields", padding=6)
        self.s_custom.pack(fill="x", pady=(6, 0))
        self.s_custom_vars: dict[str, tk.StringVar] = {}
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="Preview for pupil:").pack(side="left")
        ttk.Entry(bar, textvariable=self.s_preview_pupil, width=12).pack(side="left", padx=4)
        self._button(bar, "Preview", self.send_preview)
        self._button(bar, "Check", self.send_check)
        self._button(bar, "Send…", self.send_now)
        if not self.editor:
            ttk.Label(bar, text="You can send to pupils you choose; the school office sends "
                                "to a form or year.", foreground="#777").pack(side="left",
                                                                               padx=8)
        self.s_out = tk.Text(tab, wrap="word", height=14, state="disabled")
        self.s_out.pack(fill="both", expand=True)
        self._s_templates: dict[str, int] = {}

    def refresh_send(self) -> None:
        if not hasattr(self, "s_tcb"):
            return
        self._s_templates = {f"{t.name} ({t.category})": t.template_id
                             for t in L.list_templates(scope="active")}
        self.s_tcb.configure(values=list(self._s_templates))
        want = self.state.get("send_template")
        pick = next((k for k, v in self._s_templates.items() if v == want), None)
        if pick:
            self.s_template.set(pick)
        elif self.s_template.get() not in self._s_templates:
            self.s_template.set("")
        self._template_chosen()

    def _template_chosen(self) -> None:
        tid = self._s_templates.get(self.s_template.get())
        self.state["send_template"] = tid
        for w in self.s_custom.winfo_children():
            w.destroy()
        old = {k: v.get() for k, v in self.s_custom_vars.items()}
        self.s_custom_vars = {}
        t = L.get_template(tid) if tid else None
        fields = [f for f in (t.custom_fields if t else []) if f in t.detected_placeholders]
        if not fields:
            ttk.Label(self.s_custom, text="(none for this template)" if t else
                      "Choose a template.", foreground="#777").pack(anchor="w")
        for i, f in enumerate(fields):
            ttk.Label(self.s_custom, text="{" + f + "}").grid(row=i, column=0, sticky="w")
            var = tk.StringVar(value=old.get(f, ""))
            ttk.Entry(self.s_custom, textvariable=var, width=40).grid(row=i, column=1,
                                                                      sticky="w", pady=1)
            self.s_custom_vars[f] = var
        if t and t.reply_slip:
            self._show(f"Reply slip: {t.reply_question}\nGive a reply-by date.")

    def _show(self, text: str) -> None:
        self.s_out.configure(state="normal")
        self.s_out.delete("1.0", "end")
        self.s_out.insert("1.0", text)
        self.s_out.configure(state="disabled")

    def _send_args(self) -> dict[str, Any]:
        tid = self._s_templates.get(self.s_template.get())
        if not tid:
            raise L.ValidationError(["Choose a template"])
        kind = self.s_kind.get()
        args: dict[str, Any] = {"custom": {k: v.get() for k, v in self.s_custom_vars.items()},
                                "reply_by": self.s_reply_by.get().strip() or None}
        if kind == "Form":
            args["form"] = self.s_form.get() or None
        elif kind == "Year group":
            args["year"] = self.s_year.get() or None
        else:
            args["pupil_ids"] = L.parse_pupil_refs(self.s_pupils.get())
        return {"template_id": tid, **args}

    def send_preview(self) -> None:
        try:
            a = self._send_args()
            ref = self.s_preview_pupil.get().strip() or (a.get("pupil_ids") or [None])[0]
            if ref is None:
                _k, _l, pupils = L.audience_pupils(pupil_ids=a.get("pupil_ids"),
                                                   form=a.get("form"), year=a.get("year"))
                ref = pupils[0].pupil_id if pupils else None
            r = L.preview(a["template_id"], ref, a["custom"], reply_by=a["reply_by"])
        except _ERRORS as e:
            self._err("Preview", e)
            return
        self._show(f"Subject: {r.subject}\n\n{r.body}")

    def send_check(self) -> dict[str, Any] | None:
        try:
            a = self._send_args()
            c = L.check_send(a.pop("template_id"), actor=self.principal, **a)
        except _ERRORS as e:
            self._err("Check", e)
            return None
        lines = [f"{c['template'].name} to {c['label']}: {len(c['pupils'])} letter(s).",
                 f"{c['with_email']} pupil(s) have a contact with e-mail ({c['emails']} "
                 "address(es)).",
                 f"{len(c['no_email'])} need a printed copy."]
        lines += [f"  {p.admission_no:<10} {p.display_name}" for p in c["no_email"][:30]]
        self._show("\n".join(lines))
        return c

    def send_now(self) -> None:
        c = self.send_check()
        if c is None or not messagebox.askyesno(
                "Send", f"Send {len(c['pupils'])} letter(s) ('{c['template'].name}' to "
                f"{c['label']})?", parent=self._top()):
            return
        try:
            a = self._send_args()
            res = L.send(a.pop("template_id"), actor=self.principal, **a)
        except _ERRORS as e:
            self._err("Send", e)
            return
        self._refresh_all()
        text = (f"Mail merge #{res['send_id']}: {res['letters']} letter(s), "
                f"{res['emails']} e-mail(s).")
        if res["no_email"]:
            text += (f"\n\n{len(res['no_email'])} family(ies) have no e-mail - print their "
                     "copies from Sent letters (Print copies…).")
        if not res["message_id"]:
            self._info("Send", text)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info("Send", text + (f"\n\nQueued - delivery failed: {error}" if error
                                           else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    # ── Sent letters ─────────────────────────────────────────────────

    def _build_sent(self, tab) -> None:
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 4))
        self.sent_mine = tk.BooleanVar(value=not self.editor)
        ttk.Checkbutton(bar, text="Mine only", variable=self.sent_mine,
                        command=self.refresh_sent).pack(side="left")
        for text, cmd in (("View letters", self.view_letters),
                          ("Print copies…", lambda: self.print_copies(True)),
                          ("Print all…", lambda: self.print_copies(False)),
                          ("Export CSV…", self.export), ("Chase replies", self.chase),
                          ("Pupil's letters…", self.pupil_letters),
                          ("Refresh", self.refresh_sent)):
            self._button(bar, text, cmd)
        self.sent_tree = W.tree(tab, [("id", "#", 45), ("sent", "Sent", 120),
                                      ("template", "Letter", 200), ("to", "To", 150),
                                      ("letters", "Letters", 60), ("emails", "E-mails", 60),
                                      ("replies", "Replies", 140), ("by", "By", 90)],
                                height=16, stretch={"template"}, tags=W.STANDARD_TAGS)
        self.sent_tree.bind("<Double-1>", lambda _e: self.view_letters())
        self.sent_rows: dict[str, L.Send] = {}

    def refresh_sent(self) -> None:
        if not hasattr(self, "sent_tree"):
            return
        self.sent_tree.delete(*self.sent_tree.get_children())
        self.sent_rows = {}
        for s in L.list_sends(sent_by=self.principal.username if self.sent_mine.get()
                              else None):
            self.sent_rows[str(s.send_id)] = s
            rep = ""
            tag: tuple = ()
            if s.reply_question:
                r = L.reply_summary(s.send_id)
                rep = f"{r['yes']} yes, {r['no']} no, {r['no_reply']} waiting"
                tag = ("warn",) if r["no_reply"] else ("good",)
            self.sent_tree.insert("", "end", iid=str(s.send_id), tags=tag, values=(
                s.send_id, s.sent_at[:16], s.template_name, s.audience_label, s.letters,
                s.emails, rep, s.sent_by))

    def _send_selected(self, title: str) -> L.Send | None:
        sel = self.sent_tree.selection()
        if not sel:
            self._info(title, "Select a mail merge first.")
            return None
        return self.sent_rows[sel[0]]

    def view_letters(self) -> None:
        s = self._send_selected("View letters")
        if s is None:
            return
        win, frm = W.dialog(self.parent, f"Letters - #{s.send_id} {s.template_name}",
                            size="860x460")
        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(0, 6))
        if s.reply_question:
            ttk.Label(frm, text=f"Reply slip: {s.reply_question}"
                      + (f" (by {s.reply_by})" if s.reply_by else ""),
                      foreground="#555").pack(anchor="w")
        tree = W.tree(frm, [("pupil", "Pupil", 200), ("form", "Form", 60),
                            ("parent", "Parent", 180), ("emails", "E-mails", 60),
                            ("printed", "Printed", 90), ("reply", "Reply", 60),
                            ("note", "Note", 200)], height=14, stretch={"note"},
                      tags=W.STANDARD_TAGS)
        rows: dict[str, L.Recipient] = {}

        def refresh() -> None:
            tree.delete(*tree.get_children())
            rows.clear()
            for r in L.recipients(s.send_id):
                rows[str(r.recipient_id)] = r
                tree.insert("", "end", iid=str(r.recipient_id),
                            tags=("bad",) if not r.emails and not r.printed_at else (),
                            values=(r.pupil_name, r.form_group or "", r.parent_name or "",
                                    r.emails, (r.printed_at or "")[:10], r.reply or "",
                                    r.reply_note or ""))

        def pick() -> L.Recipient | None:
            sel = tree.selection()
            return rows[sel[0]] if sel else None

        def reply(value: str | None) -> None:
            r = pick()
            if r is None:
                return
            try:
                if value is None:
                    L.clear_reply(r.recipient_id, actor=self.principal)
                else:
                    L.record_reply(r.recipient_id, value, actor=self.principal)
            except _ERRORS as e:
                messagebox.showerror("Reply", _problems(e), parent=win)
                return
            refresh()
            self._refresh_all()

        def show() -> None:
            r = pick()
            if r:
                _text_window(win, r.pupil_name, f"Subject: {r.subject}\n\n{r.body}",
                             save_name="letter.txt")

        def open_pupil() -> None:
            r = pick()
            if r and self.open_pupil:
                self.open_pupil(r.pupil_id)
        for text, cmd, ok in (("View letter", show, True),
                              ("Reply: Yes", lambda: reply("Yes"), bool(s.reply_question)),
                              ("Reply: No", lambda: reply("No"), bool(s.reply_question)),
                              ("Clear reply", lambda: reply(None), bool(s.reply_question)),
                              ("Open pupil", open_pupil, self.open_pupil is not None),
                              ("Refresh", refresh, True)):
            b = ttk.Button(bar, text=text, command=cmd)
            if not ok:
                b.state(["disabled"])
            b.pack(side="left", padx=2)
        tree.bind("<Double-1>", lambda _e: show())
        refresh()

    def print_copies(self, only_no_email: bool) -> None:
        s = self._send_selected("Print copies")
        if s is None:
            return
        text = self._run("Print copies", lambda: L.print_copies(
            s.send_id, actor=self.principal, only_no_email=only_no_email))
        if text is None:
            return
        if not text:
            self._info("Print copies", "Every family was e-mailed - nothing to print.")
            return
        self.refresh_sent()
        _text_window(self.parent, "Print copies", text.replace("\f", "\n" + "=" * 70 + "\n"),
                     save_name=f"letters-{s.send_id}.txt")

    def export(self) -> None:
        s = self._send_selected("Export")
        if s is None:
            return
        path = filedialog.asksaveasfilename(parent=self._top(), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            initialfile=f"letters-{s.send_id}.csv")
        if path:
            n = self._run("Export", lambda: L.export_csv(s.send_id, path,
                                                         actor=self.principal))
            if n is not None:
                self._info("Export", f"Exported {n} letter(s).")

    def chase(self, send_id: int | None = None) -> None:
        s = L.get_send(send_id) if send_id else self._send_selected("Chase replies")
        if s is None:
            return
        n = len(L.chase_list(s.send_id))
        if not messagebox.askyesno("Chase replies", f"E-mail a reminder to the families of "
                                   f"{n} pupil(s) who haven't replied?", parent=self._top()):
            return
        res = self._run("Chase replies", lambda: L.chase(s.send_id, actor=self.principal))
        if not res:
            return
        self._refresh_all()
        text = f"{res['emails']} reminder(s) prepared." + (
            f"\n\n{len(res['no_email'])} family(ies) have no e-mail - phone them."
            if res["no_email"] else "")
        if not res["message_id"]:
            self._info("Chase replies", text)
            return
        from education_system.systems.secondary.modules.communication.gui import email_views

        def done(_report, error) -> None:
            try:
                self._info("Chase replies", text + (f"\n\nQueued - delivery failed: {error}"
                                                    if error else "\n\nSent."))
            except tk.TclError:
                pass
        email_views.deliver_in_background(self.parent, res["message_id"], self.principal, done)

    def pupil_letters(self) -> None:
        def save(v):
            p = L._pupil(v["pupil"])
            if p is None:
                raise L.ValidationError([f"No pupil {v['pupil']}"])
            rows = L.for_pupil(p.pupil_id)
            _text_window(self.parent, f"Letters - {p.display_name}", "\n".join(
                [f"{len(rows)} letter(s) sent home about {p.display_name}", ""] +
                [f"{r.sent_at[:10]}  {r.template_name:<32} "
                 + (f"reply: {r.reply or 'waiting'}" if r.reply_question else "")
                 + (" (printed)" if r.printed_at else "") for r in rows]))
        _form(self.parent, "Pupil's letters", [("pupil", "Pupil (admission no. or ID)", "",
                                                None)], save)

    # ── Replies ──────────────────────────────────────────────────────

    def _build_replies(self, tab) -> None:
        ttk.Label(tab, text="Reply slips still waiting, soonest reply-by date first.",
                  foreground="#555").pack(anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(4, 4))
        for text, cmd in (("Record Yes", lambda: self._reply("Yes")),
                          ("Record No", lambda: self._reply("No")),
                          ("Chase this letter", self._chase_from_replies),
                          ("Open pupil", self._open_reply_pupil),
                          ("Refresh", self.refresh_replies)):
            self._button(bar, text, cmd)
        self.rep_tree = W.tree(tab, [("by", "Reply by", 90), ("letter", "Letter", 200),
                                     ("pupil", "Pupil", 200), ("form", "Form", 60),
                                     ("question", "Question", 260), ("chased", "Chased", 60)],
                               height=16, stretch={"question"}, tags=W.STANDARD_TAGS)
        self.rep_rows: dict[str, L.Recipient] = {}

    def refresh_replies(self) -> None:
        if not hasattr(self, "rep_tree"):
            return
        self.rep_tree.delete(*self.rep_tree.get_children())
        self.rep_rows = {}
        today = L._today().isoformat()
        for r in L.chase_list():
            self.rep_rows[str(r.recipient_id)] = r
            late = bool(r.reply_by and r.reply_by < today)
            self.rep_tree.insert("", "end", iid=str(r.recipient_id),
                                 tags=("bad",) if late else (),
                                 values=(r.reply_by or "", r.template_name, r.pupil_name,
                                         r.form_group or "", r.reply_question or "",
                                         r.chase_count))

    def _reply_selected(self, title: str) -> L.Recipient | None:
        sel = self.rep_tree.selection()
        if not sel:
            self._info(title, "Select a letter first.")
            return None
        return self.rep_rows[sel[0]]

    def _reply(self, value: str) -> None:
        r = self._reply_selected("Reply")
        if r and self._run("Reply", lambda: L.record_reply(r.recipient_id, value,
                                                           actor=self.principal)):
            self._refresh_all()

    def _chase_from_replies(self) -> None:
        r = self._reply_selected("Chase")
        if r:
            self.chase(r.send_id)

    def _open_reply_pupil(self) -> None:
        r = self._reply_selected("Open pupil")
        if r and self.open_pupil:
            self.open_pupil(r.pupil_id)


def draw_letters(parent: ttk.Frame, *, principal: Principal, state: dict,
                 open_pupil: Callable[[int], None] | None = None) -> LettersPage:
    return LettersPage(parent, principal=principal, state=state, open_pupil=open_pupil)
