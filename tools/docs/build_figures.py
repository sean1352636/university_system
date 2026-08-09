"""Generate the charts and diagrams used by PROGRAM_USER_GUIDE.docx.

Every figure is drawn from inventory.json (extracted from the source tree and
the running API server), so the numbers in the charts cannot drift from the
numbers in the reference tables.

Colour follows the validated palette in the dataviz reference:
  categorical  slot1 #2a78d6 blue, slot2 #eb6834 orange, slot3 #1baf7a aqua,
               slot4 #eda100 yellow, slot5 #e87ba4 magenta
  sequential   blue, single hue
Slots 3-5 sit below 3:1 against the light surface, so every mark drawn in them
carries a visible direct label (the palette's relief rule).

    python build_figures.py inventory.json out_dir/
"""
from __future__ import annotations

import json
import textwrap
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from matplotlib.patches import FancyBboxPatch, PathPatch, Wedge  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

# ── palette ────────────────────────────────────────────────────────────
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
BLUE = "#2a78d6"
BLUE_SOFT = "#cde2fb"
DPI = 200

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": BASELINE,
    "text.color": INK,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
})


def _frame(ax, keep=("left", "bottom")):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)
        if side in keep:
            ax.spines[side].set_linewidth(0.8)
            ax.spines[side].set_color(BASELINE)
    ax.tick_params(length=0, pad=4)


def _title(ax, title, subtitle=None, wrap=88):
    """Title and subtitle stacked above the plot area.

    Drawn as axes-relative text rather than set_title so the two never collide,
    and the subtitle is wrapped so a long line doesn't stretch the saved image
    far wider than the chart itself.
    """
    lines = textwrap.wrap(subtitle, wrap) if subtitle else []
    step = 11.5   # points between subtitle lines — fixed, not axes-relative,
    base = 7      # so tall charts don't get a huge title gap
    for i, line in enumerate(lines):
        ax.annotate(line, xy=(0, 1), xycoords="axes fraction",
                    xytext=(0, base + step * (len(lines) - 1 - i)),
                    textcoords="offset points", fontsize=8, color=INK2,
                    va="bottom", ha="left", annotation_clip=False)
    ax.annotate(title, xy=(0, 1), xycoords="axes fraction",
                xytext=(0, base + step * len(lines) + 4),
                textcoords="offset points", fontsize=10, fontweight="bold",
                color=INK, va="bottom", ha="left", annotation_clip=False)


def _px_in_data(ax, px):
    """Convert a pixel distance into data units on each axis.

    The corner radius has to be computed per axis: a bar 0.3 x-units wide and
    1600 y-units tall needs wildly different numbers to look like one radius.
    Call this only after the axis limits are set.
    """
    inv = ax.transData.inverted()
    x0, y0 = inv.transform((0, 0))
    x1, y1 = inv.transform((px, px))
    return abs(x1 - x0), abs(y1 - y0)


def _rounded_bar(ax, x, y, w, h, colour, horizontal=False, radius_px=4):
    """A bar with its data-end rounded and its baseline end square."""
    rx, ry = _px_in_data(ax, radius_px)
    if horizontal:
        rx, ry = min(rx, w), min(ry, h / 2)
        verts = [(x, y), (x + w - rx, y), (x + w, y), (x + w, y + ry),
                 (x + w, y + h - ry), (x + w, y + h), (x + w - rx, y + h),
                 (x, y + h), (x, y)]
    else:
        rx, ry = min(rx, w / 2), min(ry, h)
        verts = [(x, y), (x, y + h - ry), (x, y + h), (x + rx, y + h),
                 (x + w - rx, y + h), (x + w, y + h), (x + w, y + h - ry),
                 (x + w, y), (x, y)]
    codes = [MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3,
             MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO,
             MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=colour,
                           edgecolor="none", zorder=3))


def save(fig, out: Path, name):
    fig.savefig(out / f"{name}.png", dpi=DPI, bbox_inches="tight",
                pad_inches=0.12)
    plt.close(fig)
    print("  ", name)


# ═══════════════════════════════════════════════════════════════════════
# Charts
# ═══════════════════════════════════════════════════════════════════════
LABELS = {
    "nursery": "Nursery",
    "primary": "Primary",
    "secondary": "Secondary",
    "sixth_form": "Sixth Form",
    "university": "University",
}
PREFIX = {"nursery": "nursery", "primary": "primary", "secondary": "school",
          "sixth_form": "sixthform", "university": "university"}
ORDER = ["nursery", "primary", "secondary", "sixth_form", "university"]


def chart_composition(inv, out):
    """Part-to-whole: where the platform's code sits. Five segments, values far
    apart — the case a pie is actually good at."""
    counts = inv["counts"]
    vals = [counts[k]["total"] for k in ORDER]
    total = sum(vals)

    fig, ax = plt.subplots(figsize=(6.4, 3.5))
    start = 90.0
    for i, (key, v) in enumerate(zip(ORDER, vals)):
        extent = v / total * 360
        ax.add_patch(Wedge((0, 0), 1.0, start - extent, start, width=0.42,
                           facecolor=CAT[i], edgecolor=SURFACE, linewidth=2))
        start -= extent
    ax.set_xlim(-1.30, 3.75)
    ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.text(0, 0.10, f"{total:,}", ha="center", va="center", fontsize=19,
            fontweight="bold", color=INK)
    ax.text(0, -0.20, "source files", ha="center", va="center", fontsize=8.5,
            color=INK2)

    # every segment direct-labelled: three of these hues sit below 3:1
    y = 1.02
    for i, (key, v) in enumerate(zip(ORDER, vals)):
        ax.add_patch(FancyBboxPatch((1.34, y - 0.05), 0.09, 0.09,
                                    boxstyle="round,pad=0.005,rounding_size=0.03",
                                    facecolor=CAT[i], edgecolor="none"))
        ax.text(1.56, y, LABELS[key], fontsize=8.5, color=INK, va="center")
        ax.text(2.90, y, f"{v:,}", fontsize=8.5, color=INK2, va="center",
                ha="right")
        ax.text(3.70, y, f"{v / total * 100:.1f}%", fontsize=8.5, color=INK2,
                va="center", ha="right")
        y -= 0.30

    _title(ax, "Where the platform's code sits",
           "Python source files by system. The University is two-thirds of the "
           "platform on its own.")
    save(fig, out, "fig-composition")


def chart_cli_vs_gui(inv, out):
    """One series, magnitude — how far the two interfaces have diverged.

    Plotted as a ratio rather than as absolute counts on a shared scale: the
    University has ~16x the modules of any school system, so on a shared axis
    the four systems the chart is partly about become unreadable slivers. The
    absolute counts are in the Part 4 table and the composition chart.
    """
    counts = inv["counts"]
    ratios = [counts[k]["gui"] / counts[k]["cli"] for k in ORDER]

    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    ax.set_xlim(-0.6, len(ORDER) - 0.4)
    ax.set_ylim(0, max(ratios) * 1.24)
    bar = 0.42
    for i, r in enumerate(ratios):
        colour = CAT[1] if r > 1.5 else BLUE
        _rounded_bar(ax, i - bar / 2, 0, bar, r, colour)
        k = ORDER[i]
        ax.text(i, r + max(ratios) * 0.045,
                f"{r:.2f}×", ha="center", fontsize=8, color=INK,
                fontweight="bold" if r > 1.5 else "normal")
        ax.text(i, r + max(ratios) * 0.115 if r > 1.5 else r + max(ratios) * 0.115,
                f"{counts[k]['cli']} → {counts[k]['gui']}", ha="center",
                fontsize=7, color=MUTED)

    ax.axhline(1.0, color=BASELINE, linewidth=0.9, zorder=1)
    ax.text(len(ORDER) - 0.45, 1.06, "parity", ha="right", fontsize=7.5,
            color=MUTED)
    ax.set_xticks(range(len(ORDER)))
    ax.set_xticklabels([LABELS[k] for k in ORDER], fontsize=8.5, color=INK)
    ax.set_ylabel("desktop modules per\ncommand-line module", fontsize=8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)
    _frame(ax)

    _title(ax, "How far the two staff interfaces have diverged",
           "The four school systems sit at parity — both are generated from one "
           "navigation definition. The University's desktop app is five times its "
           "command line.")
    save(fig, out, "fig-cli-vs-gui")


def chart_api_surface(inv, out):
    summary = inv["api"]["summary"]
    paths = [summary[PREFIX[k]]["paths"] for k in ORDER]
    ops = [summary[PREFIX[k]]["operations"] for k in ORDER]

    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    ax.set_xlim(-0.55, len(ORDER) - 0.45)
    ax.set_ylim(0, max(ops) * 1.18)
    slot, bar = 1.0, 0.30
    for i in range(len(ORDER)):
        _rounded_bar(ax, i * slot - bar - 0.02, 0, bar, paths[i], CAT[0])
        _rounded_bar(ax, i * slot + 0.02, 0, bar, ops[i], CAT[1])
        ax.text(i * slot - bar / 2 - 0.02, paths[i] + 18, f"{paths[i]:,}",
                ha="center", fontsize=7.5, color=INK2)
        ax.text(i * slot + bar / 2 + 0.02, ops[i] + 18, f"{ops[i]:,}",
                ha="center", fontsize=7.5, color=INK2)

    ax.set_xticks([i * slot for i in range(len(ORDER))])
    ax.set_xticklabels([LABELS[k] for k in ORDER], fontsize=8.5, color=INK)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _frame(ax)

    handles = [plt.Line2D([], [], marker="s", linestyle="none", markersize=7,
                          markerfacecolor=CAT[0], markeredgecolor="none",
                          label="Addresses"),
               plt.Line2D([], [], marker="s", linestyle="none", markersize=7,
                          markerfacecolor=CAT[1], markeredgecolor="none",
                          label="Operations")]
    leg = ax.legend(handles=handles, frameon=False, fontsize=8, ncol=2,
                    loc="upper left")
    for t in leg.get_texts():
        t.set_color(INK2)

    _title(ax, "The API surface, system by system",
           "Published by the running server. An operation is one method on one "
           "address, so an address that reads and writes counts twice.")
    save(fig, out, "fig-api-surface")


def chart_menu_sizes(inv, out, key):
    """Single series, magnitude — one hue, no legend."""
    cats = inv["menus"][key]
    pairs = sorted(((c["category"], len(c["items"])) for c in cats),
                   key=lambda t: t[1])
    names = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=(6.4, 0.34 * len(names) + 1.3))
    ax.set_ylim(-0.7, len(names) - 0.3)
    ax.set_xlim(0, max(vals) * 1.12)
    for i, v in enumerate(vals):
        _rounded_bar(ax, 0, i - 0.19, v, 0.38, BLUE, horizontal=True)
        ax.text(v + max(vals) * 0.015, i, str(v), va="center", fontsize=7.5,
                color=INK2)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8.5, color=INK)
    ax.set_xlabel("menu entries", fontsize=8)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _frame(ax)
    _title(ax, f"{LABELS[key]} — where the menu's weight sits",
           "Entries per category. The same categories appear on the command line "
           "and in the desktop application.")
    save(fig, out, f"fig-menu-{key}")


def chart_university_domains(inv, out):
    gui = inv["university"]["gui"]
    pairs = sorted(((d, sum(1 + len(v) for v in feats.values()))
                    for d, feats in gui.items()), key=lambda t: t[1])
    names = [p[0].replace("_", " ").title() for p in pairs]
    vals = [p[1] for p in pairs]

    fig, ax = plt.subplots(figsize=(6.4, 0.34 * len(names) + 1.4))
    ax.set_ylim(-0.7, len(names) - 0.3)
    ax.set_xlim(0, max(vals) * 1.12)
    for i, v in enumerate(vals):
        _rounded_bar(ax, 0, i - 0.19, v, 0.38, BLUE, horizontal=True)
        ax.text(v + max(vals) * 0.015, i, str(v), va="center", fontsize=7.5,
                color=INK2)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8.5, color=INK)
    ax.set_xlabel("desktop features and sub-features", fontsize=8)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    _frame(ax)
    _title(ax, "University — desktop features by domain area",
           "Academics, operations and pastoral carry most of the system; "
           "Shell is the application frame rather than a domain.")
    save(fig, out, "fig-university-domains")


# ═══════════════════════════════════════════════════════════════════════
# Diagrams
# ═══════════════════════════════════════════════════════════════════════
def _box(ax, x, y, w, h, text, fill=SURFACE, edge=BASELINE, bold=False,
         fontsize=8.5, colour=INK, lw=1.0):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06",
        facecolor=fill, edgecolor=edge, linewidth=lw, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=colour, zorder=3,
            fontweight="bold" if bold else "normal", linespacing=1.4)


def _arrow(ax, xy_from, xy_to, text=None, colour=MUTED, rad=0.0):
    ax.annotate("", xy=xy_to, xytext=xy_from,
                arrowprops=dict(arrowstyle="-|>", color=colour, linewidth=1.2,
                                shrinkA=2, shrinkB=2,
                                connectionstyle=f"arc3,rad={rad}"), zorder=1)
    if text:
        mx = (xy_from[0] + xy_to[0]) / 2
        my = (xy_from[1] + xy_to[1]) / 2
        ax.text(mx, my + 0.10, text, ha="center", va="bottom", fontsize=7.5,
                color=INK2, zorder=4,
                bbox=dict(boxstyle="round,pad=0.18", facecolor=SURFACE,
                          edgecolor="none"))


def _canvas(w, h, xlim, ylim):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def diagram_platform(out):
    fig, ax = _canvas(6.8, 3.9, (0, 10), (0, 6.2))
    _title(ax, "The platform at a glance",
           "One installation, one account database, five systems, three ways in.")

    for i, label in enumerate(["Command line", "Desktop application", "REST API"]):
        _box(ax, 0.4 + i * 3.15, 5.0, 2.9, 0.75, label, fill=BLUE_SOFT,
             edge=BLUE, bold=True)

    _box(ax, 0.4, 3.5, 9.25, 0.95,
         "Launcher  —  choose a system, sign in once", bold=True)

    names = ["Nursery", "Primary", "Secondary", "Sixth Form", "University"]
    for i, n in enumerate(names):
        _box(ax, 0.4 + i * 1.87, 1.95, 1.72, 0.95, n, fontsize=8)

    _box(ax, 0.4, 0.4, 9.25, 1.05,
         "Shared platform  —  identity and roles · audit · GDPR · email ·\n"
         "backup · progression queue · the unified API server",
         fill="#f4f4f1", bold=False, fontsize=8, colour=INK2)

    for i in range(3):
        _arrow(ax, (1.85 + i * 3.15, 5.0), (1.85 + i * 3.15, 4.45))
    for i in range(5):
        _arrow(ax, (1.26 + i * 1.87, 3.5), (1.26 + i * 1.87, 2.9))
        _arrow(ax, (1.26 + i * 1.87, 1.95), (1.26 + i * 1.87, 1.45))
    save(fig, out, "fig-platform")


def diagram_layers(out):
    fig, ax = _canvas(6.6, 3.4, (0, 10), (0, 5.6))
    _title(ax, "The four layers",
           "Each layer talks only to the one beneath it.")
    rows = [
        ("Interface", "CLI menus · desktop windows · REST endpoints · web pages"),
        ("Domain / Service", "The education rules — what may happen, and when"),
        ("Infrastructure", "Databases · email · authentication · validation · file paths"),
        ("Data", "SQLite databases in write-ahead-logging mode"),
    ]
    for i, (name, detail) in enumerate(rows):
        y = 4.1 - i * 1.08
        _box(ax, 0.4, y, 2.5, 0.85, name, fill=BLUE_SOFT, edge=BLUE, bold=True)
        _box(ax, 3.1, y, 6.5, 0.85, detail, fontsize=8)
        if i < 3:
            _arrow(ax, (1.65, y), (1.65, y - 0.23))
    save(fig, out, "fig-layers")


def diagram_signin(out):
    fig, ax = _canvas(6.8, 4.3, (0, 10), (0, 7.0))
    _title(ax, "Signing in", "The same sequence on every interface, in every system.")
    _box(ax, 3.1, 6.0, 3.8, 0.72, "Username and password", bold=True)
    _box(ax, 3.1, 4.9, 3.8, 0.72, "Correct?")
    _box(ax, 0.3, 3.8, 2.5, 0.72, "No — failed attempt\ncounted", fill="#fdecec",
         edge="#d03b3b", fontsize=7.5)
    _box(ax, 0.3, 2.6, 2.5, 0.72, "5 failures →\nlocked 15 minutes",
         fill="#fdecec", edge="#d03b3b", fontsize=7.5)
    _box(ax, 3.1, 3.8, 3.8, 0.72, "Second factor required?")
    _box(ax, 7.2, 3.8, 2.5, 0.72, "Yes — code, email code\nor security key", fontsize=7.5)
    _box(ax, 3.1, 2.6, 3.8, 0.72, "Password change forced?")
    _box(ax, 7.2, 2.6, 2.5, 0.72, "Yes — set a new one", fontsize=8)
    _box(ax, 3.1, 1.4, 3.8, 0.72, "Signed in", fill=BLUE_SOFT, edge=BLUE, bold=True)
    _box(ax, 3.1, 0.3, 3.8, 0.72,
         "Superadmin → dashboard listing all five systems", fontsize=7.5)

    _arrow(ax, (5.0, 6.0), (5.0, 5.62))
    _arrow(ax, (3.1, 5.26), (2.8, 4.52))
    _arrow(ax, (1.55, 3.8), (1.55, 3.32))
    _arrow(ax, (5.0, 4.9), (5.0, 4.52))
    _arrow(ax, (6.9, 4.16), (7.2, 4.16))
    _arrow(ax, (5.0, 3.8), (5.0, 3.32))
    _arrow(ax, (6.9, 2.96), (7.2, 2.96))
    _arrow(ax, (5.0, 2.6), (5.0, 2.12))
    _arrow(ax, (5.0, 1.4), (5.0, 1.02))
    save(fig, out, "fig-signin")


def diagram_token(out):
    fig, ax = _canvas(6.8, 3.6, (0, 10), (0, 5.6))
    _title(ax, "How an API caller stays signed in",
           "A token is a bearer credential — anyone holding it is the user until it "
           "expires.")
    _box(ax, 0.3, 4.3, 2.6, 0.8, "POST /auth/login", fill=BLUE_SOFT, edge=BLUE,
         bold=True, fontsize=8)
    _box(ax, 3.6, 4.3, 2.9, 0.8, "MFA challenge?", fontsize=8)
    _box(ax, 7.1, 4.3, 2.6, 0.8, "Yes —\nPOST /auth/mfa/verify", fontsize=7.5)
    _box(ax, 3.6, 3.0, 2.9, 0.8, "Access + refresh token", fill=BLUE_SOFT,
         edge=BLUE, bold=True, fontsize=8)
    _box(ax, 3.6, 1.7, 2.9, 0.8, "Authorization: Bearer …\non every request",
         fontsize=7.5)
    _box(ax, 7.1, 1.7, 2.6, 0.8, "POST /auth/refresh\nwhen it expires",
         fontsize=7.5)
    _box(ax, 0.3, 1.7, 2.6, 0.8, "GET /auth/me\nwhat can this reach?", fontsize=7.5)
    _box(ax, 0.3, 0.4, 9.4, 0.8,
         "A token reaches only the systems and roles its account holds.\n"
         "Authenticating does not open all five.",
         fill="#f4f4f1", fontsize=7.5, colour=INK2)

    _arrow(ax, (2.9, 4.7), (3.6, 4.7))
    _arrow(ax, (6.5, 4.7), (7.1, 4.7))
    _arrow(ax, (8.4, 4.3), (6.5, 3.75), rad=-0.25)
    _arrow(ax, (5.05, 4.3), (5.05, 3.82), "no")
    _arrow(ax, (5.05, 3.0), (5.05, 2.52))
    _arrow(ax, (6.5, 2.1), (7.1, 2.1))
    _arrow(ax, (3.6, 2.1), (2.9, 2.1))
    save(fig, out, "fig-token")


def diagram_progression(out):
    fig, ax = _canvas(6.8, 3.2, (0, 10), (0, 4.8))
    _title(ax, "Moving a learner to the next phase",
           "A durable queue, not a direct copy — an interrupted transfer is "
           "completed, not lost.")
    _box(ax, 0.3, 3.2, 2.3, 0.85, "Sending system\nselect learners",
         fill=BLUE_SOFT, edge=BLUE, fontsize=8)
    _box(ax, 3.1, 3.2, 2.3, 0.85, "Consent checked", fontsize=8)
    _box(ax, 5.9, 3.2, 3.8, 0.85, "Transfer queue\n(durable — survives a restart)",
         fontsize=8)
    _box(ax, 5.9, 1.8, 3.8, 0.85, "Background drainer\nstarted with each system",
         fontsize=8)
    _box(ax, 3.1, 1.8, 2.3, 0.85, "Receiving system", fill=BLUE_SOFT, edge=BLUE,
         fontsize=8)
    _box(ax, 0.3, 1.8, 2.3, 0.85, "Same person,\nsame journey", fontsize=8)
    _box(ax, 0.3, 0.4, 9.4, 0.8,
         "Cross-System → Student Journey shows one learner's record\n"
         "across all five phases.", fill="#f4f4f1", fontsize=7.5, colour=INK2)
    _arrow(ax, (2.6, 3.62), (3.1, 3.62))
    _arrow(ax, (5.4, 3.62), (5.9, 3.62))
    _arrow(ax, (7.8, 3.2), (7.8, 2.72))
    _arrow(ax, (5.9, 2.22), (5.4, 2.22))
    _arrow(ax, (3.1, 2.22), (2.6, 2.22))
    save(fig, out, "fig-progression")


def diagram_identity(out):
    fig, ax = _canvas(6.8, 3.4, (0, 10), (0, 5.2))
    _title(ax, "One account, a role in each system",
           "Access is granted per system, so the same person can hold different "
           "roles — or none.")
    _box(ax, 3.3, 4.1, 3.4, 0.85, "One account\nin the central database",
         fill=BLUE_SOFT, edge=BLUE, bold=True, fontsize=8.5)
    roles = [("Nursery", "—"), ("Primary", "Administrator"),
             ("Secondary", "Teacher"), ("Sixth Form", "—"),
             ("University", "—")]
    for i, (sysname, role) in enumerate(roles):
        x = 0.25 + i * 1.95
        granted = role != "—"
        _box(ax, x, 2.2, 1.75, 0.95,
             f"{sysname}\n{role}", fontsize=7.5,
             fill=BLUE_SOFT if granted else SURFACE,
             edge=BLUE if granted else GRID,
             colour=INK if granted else MUTED)
        _arrow(ax, (5.0, 4.1), (x + 0.87, 3.2), rad=0.0,
               colour=MUTED if granted else GRID)
    _box(ax, 0.25, 0.9, 9.45, 0.85,
         "Holding a role in more than one system is what enables Switch System,\n"
         "and what an API token can reach.",
         fill="#f4f4f1", fontsize=7.5, colour=INK2)
    save(fig, out, "fig-identity")


# ═══════════════════════════════════════════════════════════════════════
def main(inv_path, out_dir):
    inv = json.loads(Path(inv_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print("charts:")
    chart_composition(inv, out)
    chart_cli_vs_gui(inv, out)
    chart_api_surface(inv, out)
    chart_university_domains(inv, out)
    for key in ["nursery", "primary", "secondary", "sixth_form"]:
        chart_menu_sizes(inv, out, key)
    print("diagrams:")
    diagram_platform(out)
    diagram_layers(out)
    diagram_signin(out)
    diagram_token(out)
    diagram_progression(out)
    diagram_identity(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
