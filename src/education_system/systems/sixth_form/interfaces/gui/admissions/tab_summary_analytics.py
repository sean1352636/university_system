"""Summary and Analytics tabs of the Sixth Form Admissions window.

Split out of ``admissions_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.platform import branding
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    applicant_reports as reports,
)
from education_system.systems.sixth_form.domain.admissions.admissions import (
    Applicant,
    STATUSES,
)
from ._common import _today
from ._sidecar import _forecast_enrolment

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # string annotation on SummaryTab.__init__
    from .tab_applicants import ApplicantsTab


# ══ Summary tab ════════════════════════════════════════════════════

class SummaryTab:
    def __init__(self, nb: ttk.Notebook, *,
                 notebook: ttk.Notebook | None = None,
                 drill_tab: "ApplicantsTab | None" = None) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._notebook = notebook
        self._drill_tab = drill_tab
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Upcoming interview window (days):").pack(
            side="left")
        self.window_e = ttk.Entry(bar, width=6)
        self.window_e.insert(0, "14")
        self.window_e.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left")

        # Drill-down jump buttons (item 46).
        drill = ttk.Frame(self.frame)
        drill.pack(fill="x", padx=8, pady=(0, 4))
        if self._drill_tab is not None:
            ttk.Label(drill, text="Jump to:").pack(side="left")
            for label, status in (("Awaiting interview", "Under Review"),
                                    ("Interviewed", "Interviewed"),
                                    ("Offers made", "Offer Made"),
                                    ("Accepted", "Offer Accepted"),
                                    ("Enrolled", "Enrolled")):
                ttk.Button(drill, text=label,
                            command=lambda s=status: self._drill(s)).pack(
                    side="left", padx=2)

        self.text = tk.Text(self.frame, wrap="none", height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.text.configure(state="disabled")

    def _drill(self, status: str) -> None:
        tab = self._drill_tab
        if tab is None:
            return
        tab._preset = None
        tab._reset_filters()
        tab.f_status.set(status)
        tab.refresh()
        if self._notebook is not None:
            self._notebook.select(tab.frame)

    def refresh(self) -> None:
        try:
            win = int(self.window_e.get().strip() or "14")
        except ValueError:
            messagebox.showerror("Summary", "Window must be a number.")
            return
        summ = reports.summary(upcoming_window_days=win)
        lines = [
            f"Total applicants     : {summ.total}",
            f"Open                 : {summ.open_count}",
            f"Awaiting decision    : {summ.awaiting_decision}",
            f"Pending offers       : {summ.pending_offers}",
            f"Converted to student : {summ.converted}",
            f"Rejected             : {summ.rejected}",
            f"Upcoming interviews  : {summ.upcoming_interviews}  "
            f"(next {win} days)",
        ]
        expiring = data.list_expiring_offers(within_days=win)
        if expiring:
            lines.append(f"⚠ Offers expiring ≤{win}d : {len(expiring)}  "
                         + ", ".join(f"{a.applicant_id}({a.offer_expiry})"
                                     for a in expiring[:6]))
        lines += [
            "",
            "═ Conversion funnel ═══════════════════ (item 41)",
        ]
        fn = reports.funnel()
        top = fn[0][1] if fn else 0
        for stage, n in fn:
            bar_w = int(round(40 * n / top)) if top else 0
            pct = f"{round(100 * n / top)}%" if top else "—"
            lines.append(f"  {stage:<20} {n:>4}  {pct:>4} "
                         f"{'█' * bar_w}")

        lines += ["", "═ Source effectiveness ════════════════ (item 42)",
                  f"  {'Source':<18}{'Total':>6}{'Offers':>8}"
                  f"{'Enrolled':>10}{'Conv%':>8}"]
        for d in reports.source_effectiveness():
            lines.append(f"  {d['source']:<18}{d['total']:>6}"
                         f"{d['offers']:>8}{d['enrolled']:>10}"
                         f"{d['conversion']:>7}%")

        ttd = reports.time_to_decision_stats()
        lines += ["", "═ Time to decision (days) ═════════════ (item 43)"]
        if ttd["count"]:
            lines.append(f"  n={ttd['count']}  avg={ttd['avg']}  "
                         f"median={ttd['median']}  min={ttd['min']}  "
                         f"max={ttd['max']}")
        else:
            lines.append("  (no decisions recorded yet)")

        lines += ["", "═ Applications by week ════════════════ (item 44)"]
        weeks = reports.applications_by_week()[-10:]
        wmax = max((n for _, n in weeks), default=0)
        for wk, n in weeks:
            bar_w = int(round(30 * n / wmax)) if wmax else 0
            lines.append(f"  {wk:<10} {n:>4} {'█' * bar_w}")
        if not weeks:
            lines.append("  (no applications)")

        lines += ["", "═ Subject demand ═════════════════════ (item 45)"]
        for subj, n in reports.subject_demand()[:15]:
            lines.append(f"  {subj:<28} {n:>4}")
        if not reports.subject_demand():
            lines.append("  (no subject choices recorded)")

        lines += ["", "═ By status ═══════════════════════════"]
        for s in STATUSES:
            lines.append(f"  {s:<22} : {summ.by_status.get(s, 0)}")

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(lines))
        self.text.configure(state="disabled")


# ══ Analytics tab ══════════════════════════════════════════════════

class AnalyticsTab:
    """Visual dashboard — KPI tiles plus canvas charts (items 26–35)."""

    def __init__(self, nb: ttk.Notebook | None, *,
                 frame: ttk.Frame | None = None) -> None:
        # ``frame`` = draw into that frame (a new window) instead of a tab;
        # the charts are drawn larger there.
        self.popped = frame is not None
        self.frame = frame if frame is not None else ttk.Frame(nb)
        if frame is None:
            nb.add(self.frame, text="Analytics")
        self._auto_job: str | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.v_auto = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Auto-refresh (30s)",
                         variable=self.v_auto,
                         command=self._refresh_auto).pack(side="left", padx=8)
        ttk.Button(bar, text="Cohort compare…",
                    command=self._cohort_compare).pack(side="left", padx=4)
        ttk.Button(bar, text="Export summary PDF…",
                    command=self._export_summary_pdf).pack(side="left", padx=4)
        if not self.popped:
            from ..popout import add_button
            add_button(bar, "Admissions analytics",
                       lambda f: AnalyticsTab(None, frame=f))

        # KPI tile row (items 30, 31, 34).
        kpi = ttk.Frame(self.frame)
        kpi.pack(fill="x", padx=8, pady=(2, 6))
        self.kpi_vars: dict[str, tk.StringVar] = {}
        for key, title in (("conversion", "Offer→Enrol conversion"),
                            ("ttd", "Time to decision"),
                            ("forecast", "Projected enrolment")):
            lf = ttk.LabelFrame(kpi, text=title)
            lf.pack(side="left", fill="x", expand=True, padx=4)
            var = tk.StringVar(value="—")
            self.kpi_vars[key] = var
            ttk.Label(lf, textvariable=var, justify="center",
                       font=("TkDefaultFont", 11, "bold")).pack(
                padx=10, pady=8)

        grid = ttk.Frame(self.frame)
        grid.pack(fill="both", expand=True, padx=8, pady=4)
        self.canvases: dict[str, tk.Canvas] = {}
        specs = (("funnel", "Conversion funnel", 0, 0),
                 ("source", "Source conversion %", 0, 1),
                 ("weekly", "Applications by week", 1, 0),
                 ("subjects", "Subject demand", 1, 1))
        for key, title, r, c in specs:
            cell = ttk.LabelFrame(grid, text=title)
            cell.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            cv = tk.Canvas(cell, width=640 if self.popped else 380,
                           height=330 if self.popped else 210,
                           highlightthickness=0, background="white")
            cv.pack(fill="both", expand=True, padx=4, pady=4)
            self.canvases[key] = cv
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

    # ── refresh + KPIs ──────────────────────────────────────────

    def refresh(self) -> None:
        apps = data.list_applicants()
        self._conversion_kpi(apps)
        self._time_to_decision_card()
        self._forecast_card(apps)
        self._funnel_chart()
        self._source_chart()
        self._weekly_trend()
        self._subject_demand_chart()

    def _conversion_kpi(self, apps: list[Applicant]) -> None:
        enrolled = sum(1 for a in apps if a.status == "Enrolled")
        offers = sum(1 for a in apps
                     if a.offer_type and a.offer_type != "Not Offered")
        pct = round(100 * enrolled / offers) if offers else 0
        self.kpi_vars["conversion"].set(
            f"{pct}%\n{enrolled} enrolled / {offers} offers")

    def _time_to_decision_card(self) -> None:
        ttd = reports.time_to_decision_stats()
        if ttd["count"]:
            self.kpi_vars["ttd"].set(
                f"avg {ttd['avg']}d · median {ttd['median']}d\n"
                f"n={ttd['count']} (min {ttd['min']} / max {ttd['max']})")
        else:
            self.kpi_vars["ttd"].set("no decisions yet")

    def _forecast_card(self, apps: list[Applicant]) -> None:
        f = _forecast_enrolment(apps)
        self.kpi_vars["forecast"].set(
            f"~{f['projected_total']}\n{f['enrolled']} now "
            f"+ {f['expected_additional']} expected")

    # ── charts (items 26–29) ────────────────────────────────────

    def _funnel_chart(self) -> None:
        self._hbars(self.canvases["funnel"], reports.funnel(), color="#2f6fb0")

    def _source_chart(self) -> None:
        pairs = [(d["source"], d["conversion"])
                 for d in reports.source_effectiveness()]
        self._hbars(self.canvases["source"], pairs, color="#2e8b57",
                    suffix="%")

    def _weekly_trend(self) -> None:
        self._line(self.canvases["weekly"],
                   reports.applications_by_week()[-12:], color="#b0562f")

    def _subject_demand_chart(self) -> None:
        self._hbars(self.canvases["subjects"], reports.subject_demand()[:8],
                    color="#6a4fb0")

    @staticmethod
    def _hbars(cv: tk.Canvas, pairs: list, *, color: str,
               suffix: str = "") -> None:
        cv.delete("all")
        w = int(cv["width"])
        h = int(cv["height"])
        if not pairs:
            cv.create_text(w // 2, h // 2, text="(no data)", fill="#999")
            return
        rows = list(pairs)[:8]
        top = max((v for _, v in rows), default=0) or 1
        rh = (h - 8) / len(rows)
        label_w = 108
        for i, (k, v) in enumerate(rows):
            y = 4 + i * rh
            cv.create_text(4, y + rh / 2, text=str(k)[:16], anchor="w",
                           font=("TkDefaultFont", 8))
            bw = (w - label_w - 46) * v / top
            cv.create_rectangle(label_w, y + 2, label_w + bw, y + rh - 2,
                                fill=color, outline="")
            cv.create_text(label_w + bw + 4, y + rh / 2,
                           text=f"{v}{suffix}", anchor="w",
                           font=("TkDefaultFont", 8))

    @staticmethod
    def _line(cv: tk.Canvas, pairs: list, *, color: str) -> None:
        cv.delete("all")
        w = int(cv["width"])
        h = int(cv["height"])
        if len(pairs) < 2:
            cv.create_text(w // 2, h // 2, text="(not enough data)",
                           fill="#999")
            return
        vals = [v for _, v in pairs]
        top = max(vals) or 1
        pad_l, pad_r, pad_t, pad_b = 24, 10, 12, 26
        span = (w - pad_l - pad_r)
        base = h - pad_b
        n = len(pairs)
        pts = []
        for i, (_, v) in enumerate(pairs):
            x = pad_l + span * i / (n - 1)
            y = pad_t + (base - pad_t) * (1 - v / top)
            pts.append((x, y))
        cv.create_line(pad_l, base, w - pad_r, base, fill="#ccc")
        for i in range(len(pts) - 1):
            cv.create_line(*pts[i], *pts[i + 1], fill=color, width=2)
        for (x, y), (lbl, v) in zip(pts, pairs):
            cv.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color,
                           outline="")
        # First / mid / last x-axis labels.
        for idx in {0, n // 2, n - 1}:
            lbl = str(pairs[idx][0])[-5:]
            cv.create_text(pts[idx][0], base + 10, text=lbl,
                           font=("TkDefaultFont", 7), fill="#666")
        cv.create_text(pad_l - 4, pad_t, text=str(top), anchor="e",
                       font=("TkDefaultFont", 7), fill="#666")

    # ── cohort compare / auto-refresh (items 32, 35) ────────────

    def _cohort_compare(self) -> None:
        by_year: dict[str, dict[str, int]] = {}
        for a in data.list_applicants():
            year = (a.submitted_at or "????")[:4]
            d = by_year.setdefault(year, {"total": 0, "offers": 0,
                                          "enrolled": 0})
            d["total"] += 1
            if a.offer_type and a.offer_type != "Not Offered":
                d["offers"] += 1
            if a.status == "Enrolled":
                d["enrolled"] += 1
        lines = ["Cohort comparison by application year", "=" * 52, "",
                 f"  {'Year':<6}{'Total':>7}{'Offers':>8}"
                 f"{'Enrolled':>10}{'Conv%':>8}"]
        for year in sorted(by_year):
            d = by_year[year]
            conv = round(100 * d["enrolled"] / d["offers"]) if d["offers"] \
                else 0
            lines.append(f"  {year:<6}{d['total']:>7}{d['offers']:>8}"
                         f"{d['enrolled']:>10}{conv:>7}%")
        if not by_year:
            lines.append("  (no applicants)")
        TextViewerDialog(self.frame.winfo_toplevel(),
                          "Cohort comparison", "\n".join(lines),
                          save_name="cohort_comparison.txt")

    def _refresh_auto(self) -> None:
        if self._auto_job is not None:
            self.frame.after_cancel(self._auto_job)
            self._auto_job = None
        if self.v_auto.get():
            def tick() -> None:
                if not self.v_auto.get() or not self.frame.winfo_exists():
                    return
                self.refresh()
                self._auto_job = self.frame.after(30_000, tick)
            self._auto_job = self.frame.after(30_000, tick)

    # ── management PDF (item 33) ─────────────────────────────────

    def _export_summary_pdf(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.frame.winfo_toplevel(), defaultextension=".pdf",
            initialfile="admissions_summary.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            self._write_summary_pdf(path)
        except Exception as e:  # noqa: BLE001 — surface, don't crash the GUI
            messagebox.showerror("Export summary PDF",
                                  f"Could not create PDF:\n{e}")
            return
        messagebox.showinfo("Export summary PDF", f"Saved to {path}")

    @staticmethod
    def _write_summary_pdf(path: str) -> None:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
        styles = getSampleStyleSheet()
        summ = reports.summary()
        elems = [
            Paragraph(f"{branding.SYSTEM_NAME} — Admissions summary",
                      styles["Title"]),
            Paragraph(f"Generated {_today()}", styles["Normal"]),
            Spacer(1, 10),
            Paragraph("Headline", styles["Heading2"]),
        ]
        head = [["Total", summ.total], ["Open", summ.open_count],
                ["Awaiting decision", summ.awaiting_decision],
                ["Pending offers", summ.pending_offers],
                ["Converted", summ.converted], ["Rejected", summ.rejected]]
        t1 = Table(head, colWidths=[6 * cm, 3 * cm])
        t1.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        elems += [t1, Spacer(1, 10),
                  Paragraph("Conversion funnel", styles["Heading2"])]
        funnel_rows = [["Stage", "Count"]] + [[s, n] for s, n in reports.funnel()]
        t2 = Table(funnel_rows, colWidths=[7 * cm, 3 * cm], repeatRows=1)
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        elems += [t2, Spacer(1, 10),
                  Paragraph("Source effectiveness", styles["Heading2"])]
        src_rows = [["Source", "Total", "Offers", "Enrolled", "Conv%"]]
        for d in reports.source_effectiveness():
            src_rows.append([d["source"], d["total"], d["offers"],
                             d["enrolled"], f"{d['conversion']}%"])
        t3 = Table(src_rows, repeatRows=1,
                   colWidths=[5 * cm, 2 * cm, 2 * cm, 2.5 * cm, 2 * cm])
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
        elems.append(t3)
        SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm,
                          rightMargin=2 * cm, topMargin=2 * cm,
                          bottomMargin=2 * cm).build(elems)


# Sibling names used only at call time; imported last so any import order works.
from .dialogs_actions import TextViewerDialog  # noqa: E402
