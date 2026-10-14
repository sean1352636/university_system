"""Student Journey panel — the Learner 360, as a tabbed Tkinter frame.

A read-only GUI over
:func:`education_system.platform.cross_system.learner_360.build_learner_360`:
look a learner up by canonical ``journey_id`` or by any system's local
student id, and see their whole record across every system — one tab per
Learner 360 section (overview, current education, records, timeline,
qualifications, attendance, achievements, progression, transfers,
documents, support, system access, lineage).

The view is filtered for the signed-in user's role, so a tab a viewer may
not see says so rather than disappearing. Follows the shared-frame
convention used by the analytics / GDPR / admin panels: a ``tk.Frame``
subclass taking ``(parent, db_path=None, auth=None)`` that the host packs
with ``fill='both', expand=True`` — existing embeds keep working unchanged.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from education_system.platform.cross_system import (
    identity_service,
    journey_cli,
    learner_360,
    progression,
)
from education_system.paths import SYSTEM_LABELS, SYSTEM_ORDER

_HEADER_BG = "#1a5276"
_BODY_BG = "#ecf0f1"
_CARD_BG = "white"

# Lookup modes for the selector: label -> system key (None = canonical id).
_LOOKUP_MODES = [("Journey ID", None)] + [
    (SYSTEM_LABELS.get(s, s.title()) + " student ID", s) for s in SYSTEM_ORDER
]

# Tab -> (columns, row -> values) for the sections that are lists of rows.
_TABLES: dict[str, tuple[tuple[str, ...], object]] = {
    "records": (("System", "Local ID", "Status", "Year / course",
                 "Attendance", "Results"),
                lambda r: (r.get("label"), r.get("student_id"),
                           (r.get("record") or {}).get("status")
                           or ", ".join(r.get("statuses") or []),
                           (r.get("record") or {}).get("year_group")
                           or (r.get("record") or {}).get("course") or "",
                           f"{(r.get('attendance') or {}).get('present_pct', '')}%"
                           if r.get("attendance") else "",
                           len(r.get("results") or []))),
    "timeline": (("Date", "System", "Event", "Detail", "Source"),
                 lambda e: (e.get("date") or "", e.get("label"), e.get("kind"),
                            e.get("detail"), e.get("source"))),
    "qualifications": (("Title", "Level", "Grade", "Awarded", "System",
                        "Origin", "Source ref"),
                       lambda q: (q.get("title"), q.get("level") or "",
                                  q.get("grade") or "", q.get("awarded_on") or "",
                                  q.get("source_system"), q.get("origin"),
                                  q.get("source_ref") or "")),
    "attendance": (("System", "Local ID", "Sessions", "Present %", "By mark"),
                   lambda a: (a.get("label"), a.get("student_id"), a.get("total"),
                              a.get("present_pct"),
                              "  ".join(f"{m}={n}" for m, n in
                                        (a.get("by_mark") or {}).items()))),
    "achievements": (("System", "Kind", "Count", "Points", "Most recent"),
                     lambda a: (a.get("label"), a.get("kind"), a.get("count"),
                                a.get("total_points"),
                                "; ".join(str(x.get("title") or x.get("reason") or "")
                                          for x in (a.get("recent") or [])[:3]))),
    "transfers": (("Date", "From", "To", "Kind", "Reason"),
                  lambda t: (t.get("date") or "", t.get("from_system") or "",
                             t.get("to_system") or "", t.get("kind"),
                             t.get("reason") or "")),
    "documents": (("System", "Title", "Category", "Added", "Link"),
                  lambda d: (d.get("system"), d.get("title"), d.get("category"),
                             d.get("created_at") or "", d.get("link"))),
    "system_access": (("Username", "Name", "Active", "Last login", "Systems"),
                      lambda u: (u.get("username"), u.get("display_name") or "",
                                 "yes" if u.get("is_active") else "no",
                                 u.get("last_login") or "",
                                 ", ".join(f"{s['system_key']} ({s['role']})"
                                           for s in u.get("systems") or []))),
    "lineage": (("Section", "System", "Written by", "Source", "Local ID"),
                lambda li: (li.get("section"), li.get("system") or "",
                            li.get("source_system") or "", li.get("source"),
                            li.get("local_student_id") or li.get("origin") or "")),
}


class StudentJourneyFrame(tk.Frame):
    """Cross-system Learner 360 (the single student view)."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._auth = auth
        self._db_path = db_path
        self._view: dict | None = None
        self._tabs: dict[str, tk.Frame] = {}
        self._build_ui()
        self._prefill_from_auth()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg=_BODY_BG)

        header = tk.Frame(self, bg=_HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="Learner 360", font=("Helvetica", 15, "bold"),
            bg=_HEADER_BG, fg="white",
        ).pack(side="left", padx=20, pady=10)

        # ── Lookup bar ────────────────────────────────────────────────
        bar = tk.Frame(self, bg=_BODY_BG)
        bar.pack(fill="x", padx=15, pady=(10, 4))

        tk.Label(bar, text="Look up by:", bg=_BODY_BG).pack(side="left")
        self._mode_var = tk.StringVar(value=_LOOKUP_MODES[-1][0])  # university
        self._mode_box = ttk.Combobox(
            bar, textvariable=self._mode_var, state="readonly", width=24,
            values=[label for label, _ in _LOOKUP_MODES])
        self._mode_box.pack(side="left", padx=(6, 12))

        self._id_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self._id_var, width=38)
        entry.pack(side="left")
        entry.bind("<Return>", lambda _e: self._lookup())

        ttk.Button(bar, text="View", command=self._lookup).pack(
            side="left", padx=8)

        self._status = tk.Label(self, text="", bg=_BODY_BG, fg="#7b241c",
                                font=("Helvetica", 9, "italic"))
        self._status.pack(fill="x", padx=18, anchor="w")

        # ── Person card + section tabs ────────────────────────────────
        self._card = tk.Frame(self, bg=_CARD_BG, bd=1, relief="groove",
                              padx=16, pady=10)
        self._card.pack(fill="x", padx=15, pady=(4, 6))
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        for key, title in learner_360.SECTION_TITLES:
            frame = tk.Frame(self._notebook, bg=_BODY_BG)
            self._notebook.add(frame, text=title)
            self._tabs[key] = frame

    def _viewer(self) -> tuple[str | None, str | None]:
        try:
            cu = getattr(self._auth, "current_user", None) or {}
            role = cu.get("role") or next(iter(cu.get("roles") or []), None)
            return role, cu.get("system") or cu.get("system_key")
        except Exception:
            return None, None

    def _prefill_from_auth(self):
        """If a learner is logged in, pre-load their own record."""
        try:
            cu = getattr(self._auth, "current_user", None) or {}
            sid = cu.get("student_id")
            if sid:
                self._mode_var.set(_LOOKUP_MODES[-1][0])  # university
                self._id_var.set(str(sid))
                self._lookup()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Lookup + render
    # ------------------------------------------------------------------

    def _selected_system(self):
        label = self._mode_var.get()
        for lbl, sys in _LOOKUP_MODES:
            if lbl == label:
                return sys
        return None

    def _lookup(self):
        key = (self._id_var.get() or "").strip()
        self._clear()
        if not key:
            self._status.config(text="Enter an ID to look up.")
            return
        system = self._selected_system()
        role, viewer_system = self._viewer()
        try:
            if system is None:
                view = learner_360.build_learner_360(
                    key, viewer_role=role, viewer_system=viewer_system)
            else:
                row = identity_service.find_by_student(system, key)
                view = (learner_360.build_learner_360(
                    row["journey_id"], viewer_role=role,
                    viewer_system=viewer_system)
                    if row else {"found": False})
        except Exception as exc:  # defensive; the service is best-effort
            self._status.config(text=f"Lookup failed: {exc}")
            return
        if not view.get("found"):
            self._status.config(text="No journey found for that identifier.")
            return
        self._status.config(text="")
        self._render(view)

    def _clear(self):
        for w in self._card.winfo_children():
            w.destroy()
        for frame in self._tabs.values():
            for w in frame.winfo_children():
                w.destroy()

    def _render(self, view: dict):
        self._view = view
        o = view.get("overview") or {}
        tk.Label(self._card, text=o.get("full_name", "?"), bg=_CARD_BG,
                 font=("Helvetica", 16, "bold")).pack(anchor="w")
        meta = [f"DOB: {o.get('date_of_birth') or '—'}"]
        if "upn" in o:
            meta += [f"UPN: {o.get('upn') or '—'}", f"NHS: {o.get('nhs_number') or '—'}"]
        tk.Label(self._card, text="     ".join(meta), bg=_CARD_BG,
                 font=("Helvetica", 10)).pack(anchor="w", pady=(2, 0))
        tk.Label(
            self._card,
            text=f"Currently: {o.get('current_label') or '—'} "
                 f"({o.get('status') or '—'})     Journey {view.get('journey_id', '')}",
            bg=_CARD_BG, fg="#555", font=("Helvetica", 9)).pack(anchor="w")
        self._maybe_add_promote(self._card, view)

        restricted = set(view.get("restricted_sections") or [])
        for key, _title in learner_360.SECTION_TITLES:
            frame = self._tabs[key]
            if key in restricted or view.get(key) is None:
                tk.Label(frame, text="Not available for your role.",
                         bg=_BODY_BG, fg="#7b241c",
                         font=("Helvetica", 10, "italic")).pack(
                    anchor="w", padx=12, pady=12)
                continue
            renderer = getattr(self, f"_render_{key}", None)
            if renderer is not None:
                renderer(frame, view[key])
            elif key in _TABLES:
                self._table(frame, key, view[key])

    # ── Section renderers ─────────────────────────────────────────────

    def _pairs(self, parent, pairs):
        grid = tk.Frame(parent, bg=_BODY_BG)
        grid.pack(fill="x", padx=12, pady=10)
        for i, (k, v) in enumerate(pairs):
            tk.Label(grid, text=f"{k}:", bg=_BODY_BG,
                     font=("Helvetica", 9, "bold")).grid(
                row=i, column=0, sticky="w", padx=(0, 10), pady=2)
            tk.Label(grid, text=str(v if v not in (None, "") else "—"),
                     bg=_BODY_BG, font=("Helvetica", 9), wraplength=700,
                     justify="left").grid(row=i, column=1, sticky="w", pady=2)

    def _table(self, parent, key, rows, columns=None, values=None):
        cols, fn = _TABLES[key] if key in _TABLES else (columns, values)
        if not rows:
            tk.Label(parent, text="Nothing recorded.", bg=_BODY_BG,
                     font=("Helvetica", 9, "italic")).pack(anchor="w", padx=12,
                                                           pady=10)
            return
        frame = tk.Frame(parent, bg=_BODY_BG)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        tree = ttk.Treeview(frame, columns=cols, show="headings",
                            height=min(max(len(rows), 3), 18))
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=140, anchor="w")
        for row in rows:
            tree.insert("", tk.END, values=[
                "" if v is None else v for v in fn(row)])
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

    def _render_overview(self, frame, o):
        pairs = [("Name", o.get("full_name")),
                 ("Date of birth", o.get("date_of_birth")),
                 ("Current system", o.get("current_label")),
                 ("Status", o.get("status")),
                 ("Systems", ", ".join(o.get("system_labels") or []))]
        if "upn" in o:
            pairs += [("UPN", o.get("upn")), ("NHS number", o.get("nhs_number")),
                      ("Registered", o.get("created_at")),
                      ("Merged from", ", ".join(o.get("merged_from") or []))]
        self._pairs(frame, pairs)

    def _render_current_education(self, frame, ce):
        rows = (ce.get("active") or []) + (ce.get("pending") or [])
        self._table(frame, "current", rows,
                    ("System", "Local ID", "Status", "Programme", "Year",
                     "Institution", "Started", "Written by"),
                    lambda a: (a.get("label"), a.get("local_student_id"),
                               a.get("status"), a.get("programme") or "",
                               a.get("year_group") or "", a.get("institution"),
                               a.get("start_date") or "", a.get("source_system")))

    def _render_progression(self, frame, p):
        self._pairs(frame, [
            ("Current", p.get("current_label")),
            ("Recommended next", p.get("recommended_label")),
            ("Open transitions", len(p.get("open_transitions") or [])),
            ("Completed", len(p.get("completed") or [])),
            ("Cancelled", len(p.get("cancelled") or []))])
        rows = ((p.get("open_transitions") or []) + (p.get("completed") or [])
                + (p.get("cancelled") or []))
        self._table(frame, "progression", rows,
                    ("From", "To", "Status", "Started", "Completed", "Reference"),
                    lambda t: (t.get("source_system") or "(entry)",
                               t.get("destination_system"), t.get("status"),
                               t.get("initiated_at") or "",
                               t.get("completed_at") or "",
                               t.get("application_reference") or ""))

    def _render_support(self, frame, s):
        pairs = [("Flags", ", ".join(f"{f['flag']} ({f['system']})"
                                     for f in s.get("flags") or []) or "None"),
                 ("Counts", ", ".join(f"{k}: {v}" for k, v in
                                      (s.get("counts") or {}).items()) or "None")]
        sg = s.get("safeguarding") or {}
        if sg.get("visible"):
            pairs.append(("Open safeguarding alerts", sg.get("open_alerts")))
            if s.get("documents_withheld"):
                pairs.append(("Sensitive documents withheld",
                              s["documents_withheld"]))
        else:
            pairs.append(("Safeguarding", sg.get("note") or "Not shown."))
        pairs.append(("Detail", "Support, safeguarding and welfare detail is "
                                "never shown here — use the owning system."))
        self._pairs(frame, pairs)

    # ── Promote ───────────────────────────────────────────────────────

    def _promote_source(self, view: dict):
        """The (system, local_id) a learner would be promoted *from* — their
        current phase — or None if promotion isn't possible from here.

        Accepts a Learner 360 or the legacy ``build_overview`` dict.
        """
        current = ((view.get("overview") or view.get("person") or {})
                   .get("current_system"))
        if not current or progression.next_phase(current) is None:
            return None
        if journey_cli.promote_kind(current) is None:
            return None
        for row in ((view.get("current_education") or {}).get("active") or []):
            if row.get("system") == current and row.get("local_student_id"):
                return current, row["local_student_id"]
        for phase in view.get("phases") or view.get("records") or []:
            if phase.get("system") == current and phase.get("student_id"):
                return current, phase["student_id"]
        return None

    def _maybe_add_promote(self, card, view: dict):
        role, _sys = self._viewer()
        if role and learner_360.viewer_tier(role) not in ("staff", "internal"):
            return
        src = self._promote_source(view)
        if not src:
            return
        system, sid = src
        nxt = progression.next_phase(system)
        label = SYSTEM_LABELS.get(nxt, nxt.title())
        ttk.Button(
            card, text=f"Promote to {label} ▶",
            command=lambda: self._promote(system, sid, nxt, label)
        ).pack(anchor="w", pady=(8, 0))

    def _promote(self, system: str, student_id: str, nxt: str, label: str):
        if not messagebox.askyesno(
                "Promote learner",
                f"Promote {student_id} from {SYSTEM_LABELS.get(system, system)} "
                f"to {label}?\n\nThis creates their record in the next system "
                "and is hard to undo.", parent=self):
            return
        extra = {}
        if journey_cli.promote_kind(system) == "subjects":
            for i in (1, 2, 3):
                val = simpledialog.askstring(
                    "A-Level subjects", f"A-Level subject {i}:", parent=self)
                if not val:
                    messagebox.showinfo("Cancelled",
                                        "Three subjects are required.",
                                        parent=self)
                    return
                extra[f"subject_{i}"] = val.strip()
        if journey_cli.promote_accepts_consent(system):
            # Same rules as the CLI: nursery -> primary requires medical
            # alerts, which cross only with consent, so refuse up front.
            medical = messagebox.askyesno(
                "Consent to share", journey_cli.MEDICAL_CONSENT_QUESTION,
                parent=self)
            support = messagebox.askyesno(
                "Consent to share", journey_cli.SUPPORT_CONSENT_QUESTION,
                parent=self)
            consent = journey_cli.build_consent(system, medical=medical,
                                                support=support)
            missing = journey_cli.missing_consent(system, consent)
            if missing:
                messagebox.showwarning(
                    "Consent needed",
                    f"The handover to {label} requires {', '.join(missing)}, "
                    "which may only be shared with the parent's consent.",
                    parent=self)
                return
            extra["consent"] = consent
            reference = simpledialog.askstring(
                "Safeguarding reference", journey_cli.REFERENCE_QUESTION + ":",
                parent=self)
            if reference and reference.strip():
                extra["safeguarding_reference"] = reference.strip()
        try:
            journey_cli.promote(system, student_id, **extra)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Promotion failed", str(exc), parent=self)
            return
        messagebox.showinfo("Promoted",
                            f"{student_id} promoted to {label}.", parent=self)
        # Refresh the view so the new phase shows immediately.
        self._lookup()


__all__ = ["StudentJourneyFrame"]
