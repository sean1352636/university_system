"""Build PROGRAM_USER_GUIDE.docx — a full operating manual for the platform.

Narrative prose is written here; every menu listing and endpoint table is
generated from inventory.json (extracted from the source tree and the running
API server) so the reference sections cannot drift by hand-editing.

    python build_guide.py <inventory.json> <output.docx>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import docx
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

NAVY = RGBColor(0x2C, 0x3E, 0x50)
GREY = RGBColor(0x55, 0x55, 0x55)
RED = RGBColor(0xC0, 0x39, 0x2B)

SYSTEMS = [
    ("nursery", "Nursery / Early Years", "--nursery", "nursery"),
    ("primary", "Primary School", "--primary", "primary"),
    ("secondary", "Secondary School", "--secondary", "school"),
    ("sixth_form", "Sixth Form College", "--sixthform", "sixthform"),
    ("university", "University", "--university", "university"),
]

shot = {"n": 0}
fignum = {"n": 0}
INK_NAVY = NAVY


class Guide:
    def __init__(self, inv, figdir="docs/assets/guide"):
        self.figdir = Path(figdir)
        self.inv = inv
        self.doc = docx.Document()
        self._page_setup()
        self._styles()
        self.headings: list[tuple[int, str]] = []

    # ── document chrome ────────────────────────────────────────────────
    def _page_setup(self):
        for s in self.doc.sections:
            s.page_width = Inches(8.27)
            s.page_height = Inches(11.69)
            s.left_margin = s.right_margin = Inches(0.9)
            s.top_margin = s.bottom_margin = Inches(0.9)

    def _styles(self):
        st = self.doc.styles
        normal = st["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(10.5)
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.12
        for name, size, colour, before in [
            ("Heading 1", 20, NAVY, 20),
            ("Heading 2", 15, NAVY, 14),
            ("Heading 3", 12, NAVY, 10),
            ("Heading 4", 10.5, NAVY, 8),
        ]:
            s = st[name]
            s.font.name = "Calibri"
            s.font.size = Pt(size)
            s.font.color.rgb = colour
            s.font.bold = True
            s.paragraph_format.space_before = Pt(before)
            s.paragraph_format.space_after = Pt(4)
            s.paragraph_format.keep_with_next = True

    def _footer(self):
        for section in self.doc.sections:
            p = section.footer.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run("Education Management Platform — User Guide     ")
            r.font.size = Pt(8)
            r.font.color.rgb = GREY
            fld = OxmlElement("w:fldSimple")
            fld.set(qn("w:instr"), "PAGE")
            p._p.append(fld)

    # ── primitives ─────────────────────────────────────────────────────
    def p(self, text="", style=None):
        return self.doc.add_paragraph(text, style=style)

    def h(self, text, level):
        para = self.doc.add_paragraph(text, style=f"Heading {level}")
        if level <= 3:
            self.headings.append((level, text))
        return para

    def bullet(self, text):
        return self.doc.add_paragraph(text, style="List Bullet")

    def step(self, n, text, bold_lead=None):
        para = self.p()
        pf = para.paragraph_format
        pf.left_indent = Pt(26)
        pf.first_line_indent = Pt(-14)
        pf.space_after = Pt(4)
        r = para.add_run(f"{n}.  ")
        r.bold = True
        if bold_lead:
            b = para.add_run(bold_lead)
            b.bold = True
        para.add_run(text)
        return para

    def note(self, text, label="Note"):
        para = self.p()
        para.paragraph_format.left_indent = Pt(14)
        para.paragraph_format.space_before = Pt(4)
        r = para.add_run(f"{label}: ")
        r.bold = True
        r.italic = True
        r.font.color.rgb = GREY
        r.font.size = Pt(9.5)
        r2 = para.add_run(text)
        r2.italic = True
        r2.font.color.rgb = GREY
        r2.font.size = Pt(9.5)
        return para

    def warn(self, text):
        para = self.p()
        para.paragraph_format.left_indent = Pt(14)
        r = para.add_run("Important: ")
        r.bold = True
        r.font.color.rgb = RED
        r.font.size = Pt(9.5)
        r2 = para.add_run(text)
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = RED
        return para

    def code(self, lines):
        for line in lines:
            para = self.p()
            para.paragraph_format.space_after = Pt(1)
            para.paragraph_format.left_indent = Pt(20)
            r = para.add_run(line)
            r.font.name = "Consolas"
            r.font.size = Pt(9)
        self.p().paragraph_format.space_after = Pt(4)

    def table(self, headers, rows, widths=None, small=False):
        t = self.doc.add_table(rows=1, cols=len(headers))
        t.style = "Light Grid Accent 1"
        size = Pt(8.5) if small else Pt(9.5)
        for cell, head in zip(t.rows[0].cells, headers):
            para = cell.paragraphs[0]
            para.paragraph_format.space_after = Pt(1)
            r = para.add_run(head)
            r.bold = True
            r.font.size = size
        for row in rows:
            cells = t.add_row().cells
            for cell, value in zip(cells, row):
                para = cell.paragraphs[0]
                para.paragraph_format.space_after = Pt(1)
                r = para.add_run(str(value))
                r.font.size = size
        if widths:
            for row in t.rows:
                for cell, w in zip(row.cells, widths):
                    cell.width = Inches(w)
        self.p().paragraph_format.space_after = Pt(4)
        return t

    def shot_box(self, title, capture, filename, shows):
        shot["n"] += 1
        n = shot["n"]
        para = self.p()
        para.paragraph_format.space_before = Pt(6)
        r = para.add_run(f"Screenshot {n} — {title}")
        r.bold = True
        r.font.size = Pt(9.5)
        r.font.color.rgb = NAVY

        t = self.doc.add_table(rows=1, cols=1)
        t.style = "Table Grid"
        cell = t.rows[0].cells[0]
        q = cell.paragraphs[0]
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = q.add_run(f"[  SCREENSHOT {n} GOES HERE  ]")
        r.bold = True
        r.font.color.rgb = RED
        r.font.size = Pt(10)

        q = cell.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = q.add_run("Capture: ")
        r.bold = True
        r.font.size = Pt(8.5)
        r = q.add_run(capture)
        r.font.size = Pt(8.5)

        q = cell.add_paragraph()
        q.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = q.add_run(f"Save as: assets/guide-{n:02d}-{filename}.png")
        r.font.name = "Consolas"
        r.font.size = Pt(8)
        r.font.color.rgb = GREY

        para = self.p()
        r = para.add_run("What this shows: ")
        r.bold = True
        r.font.size = Pt(8.5)
        r = para.add_run(shows)
        r.font.size = Pt(8.5)
        self.shots = getattr(self, "shots", [])
        self.shots.append((n, title))
        return n

    def shot_line(self, title, capture, filename):
        """Compact one-line placeholder, for the per-page slots in Part 4."""
        shot["n"] += 1
        n = shot["n"]
        t = self.doc.add_table(rows=1, cols=1)
        t.style = "Table Grid"
        cell = t.rows[0].cells[0]
        q = cell.paragraphs[0]
        q.paragraph_format.space_after = Pt(1)
        r = q.add_run(f"[ SCREENSHOT {n} ]  ")
        r.bold = True
        r.font.color.rgb = RED
        r.font.size = Pt(8.5)
        r = q.add_run(title)
        r.bold = True
        r.font.size = Pt(8.5)
        r = q.add_run(f"  —  {capture}")
        r.font.size = Pt(8.5)
        q = cell.add_paragraph()
        q.paragraph_format.space_after = Pt(1)
        r = q.add_run(f"assets/guide-{n:02d}-{filename}.png")
        r.font.name = "Consolas"
        r.font.size = Pt(7.5)
        r.font.color.rgb = GREY
        self.p().paragraph_format.space_after = Pt(2)
        self.shots = getattr(self, "shots", [])
        self.shots.append((n, title))
        return n

    def figure(self, name, caption, width=6.3):
        """Embed a generated chart or diagram, with a numbered caption."""
        path = self.figdir / f"{name}.png"
        if not path.exists():
            self.p(f"[missing figure: {name}]")
            return
        fignum["n"] += 1
        para = self.p()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(8)
        para.paragraph_format.space_after = Pt(2)
        para.add_run().add_picture(str(path), width=Inches(width))

        cap = self.p()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_after = Pt(10)
        r = cap.add_run(f"Figure {fignum['n']}. ")
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = INK_NAVY
        r = cap.add_run(caption)
        r.font.size = Pt(8.5)
        r.font.color.rgb = GREY
        self.figs = getattr(self, "figs", [])
        self.figs.append((fignum["n"], caption))

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ======================================================================
def build(g: Guide):
    inv = g.inv
    menus = inv["menus"]
    api = inv["api"]
    counts = inv["counts"]

    # ── title page ─────────────────────────────────────────────────────
    t = g.doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("Education Management Platform")
    r.bold = True
    r.font.size = Pt(30)
    r.font.color.rgb = NAVY

    t = g.doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("User Guide")
    r.font.size = Pt(20)
    r.font.color.rgb = GREY

    for line, size in [
        ("Nursery · Primary · Secondary · Sixth Form · University", 11),
        ("Command line, desktop application and REST API", 11),
        ("", 8),
        ("Version 9.7.0 — prepared 28 July 2026", 10),
        ("https://github.com/sean1352636/university_system", 10),
    ]:
        para = g.doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = para.add_run(line)
        r.font.size = Pt(size)
        if size == 10:
            r.font.color.rgb = GREY

    para = g.doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(24)
    r = para.add_run(
        "Draft — this guide contains bordered screenshot placeholders marked "
        "“SCREENSHOT n GOES HERE”. Replace each with the captured image before "
        "circulating. Use demonstration data only: this platform holds records "
        "about children."
    )
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RED
    g.page_break()

    # ── about ──────────────────────────────────────────────────────────
    g.h("About this guide", 1)
    g.p(
        "This is the operating manual for the Education Management Platform. It is written for "
        "the people who actually use the software — administrators, office staff, teaching and "
        "pastoral staff, and the technical people responsible for installing and securing it. "
        "It assumes no programming knowledge, except in the API chapter, which necessarily "
        "assumes you can issue an HTTP request."
    )
    g.p(
        "The platform covers five education phases behind one application, and each phase can "
        "be used through three interfaces — a command line, a desktop application and a REST "
        "API. This guide covers all five systems on all three interfaces, and includes a "
        "complete reference to every menu and every published endpoint."
    )
    g.h("How this guide is organised", 2)
    g.table(
        ["Part", "Covers"],
        [
            ["1. Getting started", "Installing, first run, signing in, and how each of the "
                                   "three interfaces is laid out"],
            ["2. Security", "Step-by-step procedures for every security task, from "
                            "bootstrapping a safe installation to responding to an incident"],
            ["3. Using the interfaces", "The desktop application, the command line and the API "
                                        "in detail — conventions that apply everywhere"],
            ["4. The five systems", "One chapter per system: what it covers, its complete menu "
                                    "reference, its endpoints, and worked tasks"],
            ["5. Administration", "User accounts, settings, branding, email, backups and "
                                  "maintenance"],
            ["6. Moving learners between phases", "The progression queue and how a transfer is "
                                                  "made"],
            ["7. Troubleshooting", "Symptoms, causes and fixes"],
            ["Appendices", "The complete endpoint reference for all five systems, the shared "
                           "platform endpoints, a glossary and a screenshot index"],
        ],
        widths=[1.6, 4.9],
    )
    g.figure("fig-platform",
             "One installation carries five systems and three interfaces. Everything "
             "in Part 4 sits behind one of the five boxes on the third row.")
    g.h("How to read the reference tables", 2)
    g.p(
        "The menu listings in Part 4 and the endpoint tables in Appendix A were generated "
        "directly from the software, not transcribed. A menu entry appears in this guide "
        "because it exists in the navigation definition the application reads at startup; an "
        "endpoint appears because the running server publishes it. Where a feature exists in "
        "the source tree but is not reachable, it is not listed."
    )
    g.p(
        "That has one consequence worth stating plainly: if a menu entry in this guide is not "
        "on your screen, the likely reason is that your account's role does not grant it, not "
        "that the guide is wrong."
    )
    g.note(
        "Commands are shown as typed at a terminal, and assume you are in the folder the "
        "software was installed into. Menu paths are written Category → Entry."
    )

    # ── contents placeholder ───────────────────────────────────────────
    g.h("Contents", 1)
    g.p(
        "A contents list is generated at the end of this build from the actual headings. In "
        "Word, replace it with References → Table of Contents → Automatic Table to gain page "
        "numbers; the headings are styled correctly for that to work."
    )
    g.toc_marker = g.doc.add_paragraph()
    g.page_break()

    # ==================================================================
    part_1(g, counts)
    part_2_security(g)
    part_3_interfaces(g, api)
    part_4_systems(g, menus, api, counts, inv)
    part_5_admin(g)
    part_6_progression(g)
    part_7_troubleshooting(g)
    appendices(g, api, inv)


# ======================================================================
def part_1(g, counts):
    g.h("Part 1 — Getting started", 1)

    g.h("1.1 What you need", 2)
    g.p(
        "The platform is deliberately light on prerequisites. There is no database server to "
        "install and no application server to configure; the data lives in ordinary files and "
        "the software runs as a normal program."
    )
    g.table(
        ["Requirement", "Detail"],
        [
            ["Python", "3.11 or newer"],
            ["Database", "None to install — SQLite is file-based"],
            ["Desktop environment", "Only for the desktop application. The command line and "
                                    "API run headless on a server"],
            ["Tk (Linux only)", "The desktop application needs the system Tk package: "
                                "sudo apt-get install python3-tk"],
            ["Outbound email", "SMTP details, configured in the administration area rather "
                               "than in code"],
            ["Display size", "The desktop window opens at 1400×900 and will not shrink below "
                             "1200×800"],
        ],
        widths=[1.7, 4.8],
    )

    g.figure("fig-composition",
             "The five systems are not the same size. The University is two-thirds "
             "of the platform's code on its own, which is why its chapter in Part 4 "
             "is the longest.")
    g.h("1.2 Installing", 2)
    g.code([
        "git clone https://github.com/sean1352636/university_system.git",
        "cd university_system",
        "pip install -r requirements.lock",
    ])
    g.p(
        "That single installation covers all five systems and every interface. Optional extras "
        "exist for the GraphQL layer, real-time features and container monitoring, and are "
        "installed only if wanted."
    )
    g.p(
        "A Docker image and compose configuration are provided for containerised deployment, "
        "including an nginx front end and an optional monitoring stack."
    )

    g.h("1.3 The first run and what it creates", 2)
    g.p(
        "The first launch prepares the installation: it creates the runtime folder, applies "
        "the database schema, and — depending on the choice in §1.4 — creates the first "
        "accounts. It is the only launch that takes noticeably longer than the rest."
    )
    g.table(
        ["Folder", "Holds"],
        [
            ["data", "The databases: the central account database and one per system"],
            ["logs", "Application and audit logs"],
            ["backups", "Backup archives written by the backup tooling"],
            ["secrets", "Encryption keys and credentials"],
        ],
        widths=[1.4, 5.1],
    )
    g.p(
        "Everything the installation accumulates lives in that one folder. Backing it up backs "
        "up the whole installation; it is excluded from the source repository so that real "
        "data cannot be committed by accident."
    )
    g.shot_box(
        "First run in a terminal",
        "In a clean copy of the software, run python -m education_system for the first time and capture "
        "from the command through to the launcher menu appearing.",
        "first-run",
        "the runtime folders being created and the database prepared. Capture this before "
        "anything else exists — once the installation has run, it cannot be captured again "
        "without starting over.",
    )

    g.h("1.4 Deciding which accounts exist", 2)
    g.p(
        "Before the first sign-in you must decide what accounts the installation starts with. "
        "This is the single most important security decision in the whole setup, and it cannot "
        "be undone quietly later — demonstration accounts left enabled on a live system are the "
        "most likely way this platform gets compromised."
    )
    g.table(
        ["If you are…", "Set", "You get"],
        [
            ["Evaluating or demonstrating", "EDU_DEV_SEED=true",
             "The full set of demonstration accounts, covering every role in every system. All "
             "have weak, published passwords"],
            ["Setting up a real installation",
             "EDU_INITIAL_ADMIN_USER and EDU_INITIAL_ADMIN_PASSWORD (12 characters or more)",
             "One strong administrator account and nothing else"],
            ["Unsure", "Nothing",
             "An empty account database. Nobody can sign in until an account is created"],
        ],
        widths=[1.5, 2.1, 2.9],
    )
    g.warn(
        "Never set EDU_DEV_SEED on anything reachable from the internet. The demonstration "
        "accounts are weak by design and their credentials are published in the repository."
    )
    g.p("To add example learners as well as accounts:")
    g.code(["python -m education_system --seed 50            # create 50 demonstration students"])

    g.h("1.5 Starting the platform", 2)
    g.p("Everything starts from one command. With no arguments it asks two questions:")
    g.code(["python -m education_system"])
    g.step(1, "Choose an interface: CLI, GUI, API, Web, or one of the two test options. "
              "0 leaves.")
    g.step(2, "Choose a system: University, Sixth Form College, Secondary School, Primary "
              "School or Nursery. 0 returns to the previous menu.")
    g.step(3, "Sign in.")
    g.p()
    g.p(
        "If you know where you are going, both answers can be given on the command line and "
        "the menus are skipped. This is the form to use in a shortcut, a service definition or "
        "a script."
    )
    g.table(
        ["To open", "Command"],
        [
            ["Nursery, desktop", "python -m education_system --nursery --gui"],
            ["Nursery, command line", "python -m education_system --nursery --cli"],
            ["Primary School, desktop", "python -m education_system --primary --gui"],
            ["Primary School, command line", "python -m education_system --primary --cli"],
            ["Secondary School, desktop", "python -m education_system --secondary --gui"],
            ["Secondary School, command line", "python -m education_system --secondary --cli"],
            ["Sixth Form College, desktop", "python -m education_system --sixthform --gui"],
            ["Sixth Form College, command line", "python -m education_system --sixthform --cli"],
            ["University, desktop", "python -m education_system --university --gui"],
            ["University, command line", "python -m education_system --university --cli"],
            ["The API server (all five systems)", "python -m education_system --university --api"],
            ["The static web portal", "python -m education_system --web"],
        ],
        widths=[2.6, 3.9],
    )
    g.note(
        "--school and --college are accepted as aliases for --secondary and --sixthform. "
        "Add --verbose to see the full startup log on screen."
    )
    g.shot_box(
        "The launcher",
        "Run python -m education_system with no arguments and capture both menus — the interface menu and "
        "the system menu.",
        "launcher",
        "the single entry point. Five systems and four interfaces sit behind one command, "
        "which is what makes this one application rather than five.",
    )

    g.h("1.6 Signing in", 2)
    g.p(
        "The sign-in prompt is shared by all five systems, because there is one account "
        "database behind them. It appears as a window or as a terminal prompt depending on the "
        "interface, but the process is identical."
    )
    g.figure("fig-signin",
             "Signing in. The lockout path on the left is the one worth knowing: five "
             "failures lock the account, not the terminal.")
    g.step(1, "Enter your username and password.")
    g.step(2, "If multi-factor authentication is enabled on the account, provide the second "
              "factor — a six-digit code from an authenticator app, a code sent by email, or a "
              "security key.")
    g.step(3, "If the account is flagged to change its password, or the password has expired, "
              "set a new one before continuing.")
    g.step(4, "You arrive in the system you chose. Superadmin accounts arrive at a dashboard "
              "listing all five systems and choose from there.")
    g.p()
    g.p(
        "Five failed attempts locks the account for fifteen minutes. The lock is on the "
        "account, not the terminal, so trying from elsewhere does not avoid it. An "
        "administrator can clear it early."
    )
    g.shot_box(
        "The sign-in window",
        "Capture the sign-in prompt on the desktop application.",
        "sign-in",
        "the single sign-on shared by all five systems. The same credentials work everywhere "
        "the account holds a role.",
    )
    g.page_break()


# ======================================================================
def part_2_security(g):
    g.h("Part 2 — Security, step by step", 1)
    g.p(
        "This platform holds records about children and young people. Security is therefore "
        "treated as a core requirement rather than a feature, and this part gives the actual "
        "procedures rather than a description of the controls."
    )
    g.p(
        "Work through §2.1 before an installation is used for anything real. The remaining "
        "sections are reference procedures, used as the need arises."
    )

    # 2.1
    g.h("2.1 Bootstrapping a secure installation", 2)
    g.p("Do these in order, before the first person signs in.")
    g.step(1, "Confirm EDU_DEV_SEED is not set. If the installation was evaluated first, the "
              "demonstration accounts already exist — delete every one of them before going "
              "live, or start from a fresh runtime folder.", bold_lead="Remove demo accounts. ")
    g.step(2, "Set EDU_INITIAL_ADMIN_USER and EDU_INITIAL_ADMIN_PASSWORD, using a password of "
              "at least 12 characters that is not used anywhere else. Start the platform once "
              "so the account is created, then unset the variables so the password is not left "
              "in the environment.", bold_lead="Create one strong administrator. ")
    g.step(3, "Sign in as that account and set up multi-factor authentication immediately "
              "(§2.4). An administrator account without a second factor is a single password "
              "away from full access to every record.", bold_lead="Enrol a second factor. ")
    g.step(4, "Generate long random values for API_SECRET_KEY and JWT_SECRET_KEY, and set "
              "API_CORS_ORIGINS to the exact origins allowed to call the API from a browser. "
              "The server refuses to start without all three.", bold_lead="Set the API secrets. ")
    g.step(5, "Confirm the runtime folder is excluded from version control and is not served "
              "by any web server. It holds the databases and the encryption keys.",
           bold_lead="Protect the runtime folder. ")
    g.step(6, "Put the platform behind HTTPS. Nothing in the platform issues certificates; the "
              "supplied nginx configuration is the intended place for this.",
           bold_lead="Terminate TLS in front of it. ")
    g.step(7, "Configure backups (§2.10) and confirm one has actually been written.",
           bold_lead="Turn on backups. ")
    g.step(8, "Create the real user accounts and grant each the narrowest role that lets the "
              "person do their job (§2.2).", bold_lead="Create accounts last. ")
    g.p()
    g.warn(
        "The project's own documentation states that the platform is not recommended for "
        "production use until the measures in its security recommendations are implemented. "
        "Treat this checklist as the minimum, not as sign-off."
    )
    g.code([
        "# generating suitable secrets",
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\"",
    ])

    # 2.2
    g.h("2.2 Accounts, roles and access", 2)
    g.p(
        "An account is one identity in one central database. Access is granted per system: the "
        "same person can be an administrator in Primary, a teacher in Secondary, and have no "
        "access at all to University. Holding a role in more than one system is also what "
        "enables switching between them without signing in again."
    )
    g.table(
        ["Role", "Typical access"],
        [
            ["Administrator", "Full access to their system, including settings and user "
                              "management"],
            ["Staff / Teacher", "Teaching and pastoral features for their own groups"],
            ["Instructor", "Teaching delivery and assessment (University)"],
            ["Student / Pupil", "Their own records, timetable, results and messages"],
            ["Parent", "Their child's information, communications and payments"],
            ["Alumni", "Former-student services (University)"],
            ["Superadmin", "Administrator across all five systems simultaneously"],
        ],
        widths=[1.5, 5.0],
    )
    g.figure("fig-identity",
             "One identity, a separate role in each system. An account with a role in "
             "more than one system can switch between them without signing in again.")
    g.h("Creating an account", 3)
    g.step(1, "Open System → User Management (command line) or the user management area "
              "(desktop).")
    g.step(2, "Choose to add a user, and enter the username and display name.")
    g.step(3, "Set an initial password, and flag the account to change it at next sign-in.")
    g.step(4, "Grant a role in this system. Repeat in each other system the person needs.")
    g.step(5, "Require multi-factor authentication for any account with administrative access.")
    g.p()
    g.h("Removing access", 3)
    g.step(1, "Revoke the role in each system the person held one in.")
    g.step(2, "Invalidate their sessions (§2.6) — revoking a role does not end a session "
              "already open.")
    g.step(3, "Disable or delete the account.")
    g.step(4, "Check whether the person held any API tokens, and rotate the relevant secrets "
              "if so.")
    g.p()
    g.note(
        "Deleting an account does not delete the records it created; audit entries and "
        "learner records survive deliberately, so that history remains intelligible."
    )
    g.shot_box(
        "User management",
        "Open the user-management area with demonstration accounts listed, showing roles per "
        "system.",
        "user-management",
        "how one identity carries a separate role in each system. This is the screen behind "
        "almost every access question.",
    )

    # 2.3
    g.h("2.3 Passwords", 2)
    g.p(
        "Passwords are stored as bcrypt hashes — a deliberately slow algorithm chosen to make "
        "guessing expensive. The original password is never stored and cannot be recovered by "
        "anyone, including an administrator; it can only be replaced."
    )
    g.h("Changing your own password", 3)
    g.step(1, "Open System → Change Password.")
    g.step(2, "Enter the current password, then the new one twice.")
    g.step(3, "Sign in again if prompted.")
    g.p()
    g.h("Resetting someone else's", 3)
    g.step(1, "Open System → User Management and select the account.")
    g.step(2, "Set a new password and flag the account to change it at next sign-in.")
    g.step(3, "Tell the person through a channel other than the platform's own email if the "
              "account's email access is itself in doubt.")
    g.p()
    g.h("Self-service recovery", 3)
    g.p(
        "Users can recover access themselves through an emailed reset link or security "
        "questions, if those are configured. Password history is retained as hashes so a "
        "recent password cannot be immediately reused."
    )

    # 2.4
    g.h("2.4 Multi-factor authentication", 2)
    g.p(
        "Three second factors are supported. An account can be required to use one, and "
        "administrative accounts should be."
    )
    g.h("Authenticator app (time-based codes)", 3)
    g.step(1, "Open System → Multi-Factor Authentication and choose the authenticator-app "
              "method.")
    g.step(2, "Scan the QR code shown, or type the secret into the app by hand.")
    g.step(3, "Enter the six-digit code the app displays to confirm the pairing. Setup is not "
              "complete until a code has been verified.")
    g.step(4, "Store the recovery codes that are issued. They are shown once. Each works a "
              "single time.")
    g.p()
    g.h("Emailed one-time codes", 3)
    g.step(1, "Choose the email method. The account must have a working email address, and the "
              "installation must have SMTP configured (§5.4).")
    g.step(2, "A code is sent on each sign-in and entered at the prompt.")
    g.p()
    g.note(
        "Email is the weakest of the three factors: anyone with access to the mailbox has the "
        "factor. Prefer an authenticator app or a security key for administrators."
    )
    g.h("Security key (WebAuthn)", 3)
    g.step(1, "Choose the security-key method.")
    g.step(2, "Insert or tap the key when prompted, and confirm the registration.")
    g.step(3, "Register a second key if the account is important, since losing the only key "
              "means falling back to recovery codes.")
    g.p()
    g.h("Recovery, and losing a factor", 3)
    g.step(1, "Sign in with a recovery code in place of the usual second factor. Recovery-code "
              "attempts are rate limited.")
    g.step(2, "Enrol a new factor immediately afterwards.")
    g.step(3, "If no recovery code remains, an administrator must disable multi-factor "
              "authentication on the account, after verifying the person's identity by some "
              "means outside the platform.")
    g.p()
    g.warn(
        "That last step is the weakest point in the whole scheme: it lets an administrator "
        "remove someone's second factor. Treat requests to do it as identity-verification "
        "events, and check the audit log afterwards."
    )
    g.shot_box(
        "Multi-factor authentication setup",
        "Capture the enrolment screen showing the QR code and the field for the confirming "
        "code. Use a demonstration account — the secret is a credential.",
        "mfa-setup",
        "enrolment for a second factor. Confirm the QR code and secret belong to a "
        "demonstration account before circulating this image.",
    )

    # 2.5
    g.h("2.5 Lockout and brute-force protection", 2)
    g.table(
        ["Control", "Behaviour"],
        [
            ["Account lockout", "Five consecutive failed sign-ins lock the account for 15 "
                                "minutes"],
            ["Per-account rate limit", "Repeated attempts against one username are throttled "
                                       "independently of where they come from"],
            ["Per-origin rate limit", "Repeated attempts from one origin are throttled, which "
                                      "is what blunts an attack spread across many accounts"],
            ["MFA attempt limits", "Second-factor and recovery-code attempts are capped both "
                                   "per origin and per account"],
        ],
        widths=[1.8, 4.7],
    )
    g.h("Clearing a lockout", 3)
    g.step(1, "Confirm with the person that the failures were theirs. A lockout nobody caused "
              "is a signal, not an inconvenience.")
    g.step(2, "Open System → User Management, select the account and clear the lockout.")
    g.step(3, "If the failures were not theirs, reset the password and review the audit log "
              "(§2.11) for successful sign-ins around the same time.")

    # 2.6
    g.h("2.6 Sessions", 2)
    g.p(
        "Sessions are recorded in the database rather than held only by the client, which is "
        "what makes them reviewable and revocable centrally. A session ends when it expires, "
        "when the user signs out, or when someone invalidates it."
    )
    g.step(1, "Open the session or device area in user management to see active sessions.")
    g.step(2, "Invalidate a single session to sign one device out.")
    g.step(3, "Invalidate all of a user's sessions when an account is compromised, a device is "
              "lost, or someone leaves. Do this after changing the password, not before.")
    g.p()
    g.note(
        "API access uses tokens rather than sessions. Ending a session does not invalidate an "
        "issued access token — see §2.8."
    )

    # 2.7
    g.h("2.7 Single sign-on", 2)
    g.p(
        "Organisations that already run an identity provider can authenticate through it using "
        "OAuth instead of platform-held passwords. Providers are configured centrally; users "
        "link their account once and sign in through the provider thereafter."
    )
    g.step(1, "Configure the provider's client credentials in the administration area.")
    g.step(2, "Have each user link their account from their own security settings.")
    g.step(3, "Decide whether platform passwords remain enabled as a fallback. Leaving both "
              "enabled means the account is only as strong as the weaker path.")

    # 2.8
    g.h("2.8 API security", 2)
    g.p(
        "The API server refuses to start unless three environment variables are set. This is "
        "deliberate — each default it declines to invent would be a real weakness that nobody "
        "would notice."
    )
    g.table(
        ["Variable", "Why it is required"],
        [
            ["API_SECRET_KEY", "A random per-process key would invalidate every session on "
                               "each restart"],
            ["JWT_SECRET_KEY", "Storing the token-signing secret in the database would let "
                               "anyone with file access forge tokens"],
            ["API_CORS_ORIGINS", "A wildcard policy would let any website call the API with a "
                                 "user's credentials"],
        ],
        widths=[1.7, 4.8],
    )
    g.figure("fig-token",
             "The token lifecycle. Sign in once, send the access token with every "
             "request, refresh it rather than signing in again.")
    g.h("Obtaining and using a token", 3)
    g.step(1, "POST credentials to /api/v1/auth/login. The response carries an access token "
              "and a refresh token — or an MFA challenge if the account requires one.")
    g.step(2, "Send the access token as an Authorization: Bearer header on every request.")
    g.step(3, "POST the refresh token to /api/v1/auth/refresh when the access token expires, "
              "rather than storing credentials and signing in repeatedly.")
    g.step(4, "Confirm what a token can reach with GET /api/v1/auth/me. A token grants only "
              "the systems and roles the underlying account holds.")
    g.code([
        "curl -X POST http://localhost:5000/api/v1/auth/login \\",
        "     -H 'Content-Type: application/json' \\",
        "     -d '{\"username\": \"...\", \"password\": \"...\"}'",
        "",
        "curl http://localhost:5000/api/v1/auth/me \\",
        "     -H 'Authorization: Bearer <token>'",
    ])
    g.h("Rotating a compromised secret", 3)
    g.step(1, "Replace JWT_SECRET_KEY and restart. Every issued token stops being accepted "
              "immediately, which will sign out every API client.")
    g.step(2, "Tell integrators in advance where possible, since their next call will fail.")
    g.step(3, "Review the audit log for what the compromised token reached.")
    g.p()
    g.warn(
        "Tokens are bearer credentials: anyone holding one is the user until it expires. Never "
        "put a token in a screenshot, a ticket, a log or a chat message."
    )
    g.shot_box(
        "An API call from start to finish",
        "Capture the login call, the token returned, and one data request using it — with the "
        "token redacted.",
        "api-call",
        "the whole sequence an integrator follows. Redact the token before this image goes "
        "anywhere: it is a working credential for as long as it lives.",
    )

    # 2.9
    g.h("2.9 Protecting data at rest", 2)
    g.table(
        ["Control", "What it does"],
        [
            ["Field-level encryption", "Sensitive values are encrypted individually with "
                                       "Fernet (AES-128-CBC, authenticated with HMAC-SHA256), "
                                       "so the database file alone does not disclose them"],
            ["Secrets outside the codebase", "Encryption keys and credentials live in the "
                                             "runtime folder, excluded from version control"],
            ["Uploaded files", "Documents can be virus scanned with ClamAV before being stored"],
            ["Parameterised queries", "Database access never assembles SQL from user input"],
            ["Email header validation", "Outgoing mail rejects the newline characters used to "
                                        "smuggle extra headers"],
        ],
        widths=[1.8, 4.7],
    )
    g.warn(
        "The encryption keys sit in the same runtime folder as the databases. Anyone who can "
        "copy that folder has both. Protect it at the filesystem level and keep backups "
        "encrypted (§2.10)."
    )

    # 2.10
    g.h("2.10 Backups", 2)
    g.p(
        "Because all live data sits in one runtime folder, a backup is fundamentally a copy of "
        "that folder. The platform also provides its own tooling, which compresses, checksums "
        "and optionally encrypts each archive, and can run on a schedule."
    )
    g.step(1, "Decide where archives are written, and make sure it is not the same disk as the "
              "live data.", bold_lead="Choose a destination. ")
    g.step(2, "Enable encryption and supply a key. An unencrypted backup of this platform is a "
              "complete copy of children's records in a file that is easy to mislay.",
           bold_lead="Encrypt them. ")
    g.step(3, "Set a schedule and a retention period. Old archives are cleaned up "
              "automatically once a retention period is configured.", bold_lead="Schedule it. ")
    g.step(4, "Confirm an archive has actually been written, and verify it — the tooling can "
              "check an archive's checksum.", bold_lead="Verify. ")
    g.step(5, "Store the encryption key somewhere other than the backup destination. A key "
              "kept beside the archive protects nothing.", bold_lead="Keep the key apart. ")
    g.p()
    g.h("Restoring", 3)
    g.p(
        "The tooling includes a restore function and an archive-verification step. What it "
        "does not yet include is a tested, documented end-to-end restore procedure — the "
        "project records this as an open gap."
    )
    g.warn(
        "Do not assume a backup works because it exists. Practise a restore into a scratch "
        "copy before you need one, and write down what you did — that rehearsal is the only "
        "thing that turns an archive into a recovery plan."
    )

    # 2.11
    g.h("2.11 The audit log", 2)
    g.p(
        "Actions are written to an audit log with tamper detection, so an entry cannot be "
        "quietly altered or removed after the fact. Reading sensitive records is recorded as "
        "well as changing them."
    )
    g.table(
        ["Capability", "Use"],
        [
            ["Query by system, user, action or date", "Answering 'who did this, and when'"],
            ["Security-specific entries", "Sign-ins, lockouts, permission changes and other "
                                          "security events are recorded distinctly"],
            ["Integrity verification", "Confirms an individual entry has not been altered "
                                       "since it was written"],
            ["Statistics", "Activity summaries over a period, for routine review"],
        ],
        widths=[2.2, 4.3],
    )
    g.h("Investigating an incident", 3)
    g.step(1, "Fix the date range and the account or system in question, and query the log.")
    g.step(2, "Verify the integrity of any entry you intend to rely on.")
    g.step(3, "Look for the surrounding events, not just the one reported — a suspicious "
              "sign-in matters more than the record that was opened after it.")
    g.step(4, "Export what is relevant before retention removes it, and record what you found "
              "outside the platform.")
    g.shot_box(
        "The audit log",
        "Open the audit log with demonstration activity, filtered to a date range.",
        "audit-log",
        "that the trail is inspectable inside the application, not merely written to a file "
        "somewhere. This is what makes accountability checkable rather than asserted.",
    )

    # 2.12
    g.h("2.12 Data protection and GDPR requests", 2)
    g.p(
        "The platform provides tooling for the requests a data protection regime actually "
        "generates, and — because a learner may have records in more than one phase — it "
        "searches across all five systems rather than one at a time."
    )
    g.table(
        ["Request", "Tooling"],
        [
            ["Subject access request", "Search across all systems, then generate a subject "
                                       "access report and a full data export"],
            ["Data portability", "Export a person's data as JSON or CSV"],
            ["Rectification", "Correct specified fields on a person's record"],
            ["Erasure", "Anonymise a person within a system, preserving aggregate integrity"],
            ["Restriction of processing", "Mark a record restricted, and later unrestrict it"],
            ["Retention review", "Report which records have passed a configured retention "
                                 "period"],
            ["Consent", "Record and check consent, including consent to transfer between "
                        "systems"],
        ],
        widths=[1.9, 4.6],
    )
    g.h("Handling a subject access request", 3)
    g.step(1, "Verify the requester's identity outside the platform first.")
    g.step(2, "Search all systems by name, email or date of birth — a learner who progressed "
              "between phases has records in more than one.")
    g.step(3, "Generate the subject access report and review it before release, checking for "
              "third-party information that must be removed.")
    g.step(4, "Export in the format requested and deliver it through a channel appropriate to "
              "its sensitivity.")
    g.step(5, "Record that the request was fulfilled. The audit log records the export itself.")
    g.p()
    g.h("Handling an erasure request", 3)
    g.step(1, "Establish whether the request must actually be honoured — safeguarding and "
              "statutory retention frequently override it.")
    g.step(2, "Anonymise the record in each system it exists in.")
    g.step(3, "Confirm the person no longer appears in a cross-system search.")
    g.step(4, "Note that anonymisation is irreversible, and that backups taken before it still "
              "contain the original data until they age out.")
    g.p()
    g.note(
        "Default retention periods are not set out of the box. Deciding them, and configuring "
        "the retention report accordingly, is a task for the organisation rather than the "
        "software."
    )

    # 2.13
    g.h("2.13 Safeguarding information", 2)
    g.p(
        "Safeguarding records are the most sensitive data the platform holds, and the ordinary "
        "rules about convenience do not apply to them."
    )
    g.bullet("Grant safeguarding access by named individual, not by job title or department.")
    g.bullet("Review who holds it termly, and revoke immediately when someone changes role.")
    g.bullet("Expect access to be logged, and audit it — the log exists so that access to a "
             "child's records can be accounted for.")
    g.bullet("Never demonstrate the platform using real safeguarding records, and never "
             "screenshot them.")

    # 2.14
    g.h("2.14 Hardening the web and API surface", 2)
    g.p(
        "When the API or web portal is served, protective HTTP headers are applied "
        "automatically: a Content-Security-Policy, X-Frame-Options set to DENY, "
        "X-Content-Type-Options, Referrer-Policy and HSTS. Payloads are validated and requests "
        "are rate limited."
    )
    g.step(1, "Terminate HTTPS in front of the application — the supplied nginx configuration "
              "is the intended place.")
    g.step(2, "Set API_CORS_ORIGINS to the exact origins you serve from. Never a wildcard.")
    g.step(3, "Point monitoring at /api/v1/health, which reports database connectivity as well "
              "as liveness.")
    g.step(4, "Do not expose the API server directly to the internet without a reverse proxy "
              "in front of it.")

    # 2.15
    g.h("2.15 Ongoing assurance", 2)
    g.table(
        ["Check", "What runs"],
        [
            ["Static analysis", "Bandit on every change; GitHub CodeQL weekly"],
            ["Dependency monitoring", "pip-audit against published advisories; Dependabot "
                                      "raises updates"],
            ["Security tests", "The test suite carries a security marker so those tests can be "
                               "run as a set"],
        ],
        widths=[1.8, 4.7],
    )
    g.code([
        "make security-scan      # Bandit",
        "make test               # the suite, excluding slow and GUI tests",
    ])
    g.p(
        "None of this substitutes for keeping the installation itself patched. Apply "
        "dependency updates on a schedule rather than when something breaks."
    )

    # 2.16
    g.h("2.16 Reporting a vulnerability", 2)
    g.p(
        "Security issues should be reported through the repository's security policy rather "
        "than the public issue tracker, so that a fix can be prepared before the problem is "
        "described publicly."
    )
    g.code(["https://github.com/sean1352636/university_system/security/policy"])
    g.page_break()


# ======================================================================
def part_3_interfaces(g, api):
    g.h("Part 3 — Using the interfaces", 1)
    g.p(
        "The three interfaces are written separately against the same underlying rules. What "
        "follows applies in every system; Part 4 covers what differs between them."
    )
    g.figure("fig-layers",
             "Why the three interfaces agree with each other. Each is a different top "
             "layer over the same rules — so a record created on the command line "
             "obeys the same constraints as one created in the window or over the API.")

    # 3.1
    g.h("3.1 The desktop application", 2)
    g.p("The window opens at 1400×900 and has four regions, unchanged across all five systems.")
    g.table(
        ["Region", "Contents"],
        [
            ["Header", "Institution logo and a Dashboard button at the left, with Logout and "
                       "Switch to CLI beside them; the system name centred; Shutdown at the "
                       "right. A Switch System button appears for accounts holding a role in "
                       "more than one system"],
            ["Navigation panel", "The category list down the left. It scrolls, because in most "
                                 "systems the list is longer than the window"],
            ["Content area", "Where the selected feature opens"],
            ["Status bar", "Along the bottom"],
        ],
        widths=[1.6, 4.9],
    )
    g.p(
        "The Dashboard button returns to the home screen from anywhere, which is the quickest "
        "way out of a feature opened by mistake. Closing the window ends the session."
    )
    g.shot_box(
        "The desktop window and its regions",
        "Capture a full desktop window with a feature open, so all four regions are visible at "
        "once.",
        "desktop-regions",
        "the four regions in their normal proportions. Every other desktop screenshot in this "
        "guide is a view of the content area of this same window.",
    )
    g.h("The shape of a feature screen", 3)
    g.p(
        "Once inside a feature the pattern is consistent: a list of records, filters above it, "
        "actions along the top, and a detail form for the selected record. Adding, editing and "
        "searching therefore work the same way whether the records are nursery children, "
        "secondary pupils or university students."
    )
    g.shot_box(
        "A standard record screen",
        "Open any list-and-detail feature with demonstration data, showing the filters, the "
        "list and a selected record's detail together.",
        "record-screen",
        "the pattern every feature follows. Learning it once is enough for the whole platform.",
    )

    # 3.2
    g.h("3.2 The command line", 2)
    g.p(
        "The same categories appear as a numbered menu. Choosing one opens a numbered submenu "
        "of the features within it."
    )
    g.bullet("Type the number of the entry you want and press Enter.")
    g.bullet("0 goes back one level — from a feature to its category, from a category to the "
             "main menu.")
    g.bullet("0 at the main menu leaves the system.")
    g.p(
        "In the four school-phase systems the command line and the desktop application are "
        "built from one shared navigation definition, so they present exactly the same "
        "categories and entries. Choosing between them is a question of environment, not "
        "capability. The University is the exception — see §4.5."
    )
    g.figure("fig-cli-vs-gui",
             "Four systems at parity, one that has diverged. In the University the "
             "desktop application reaches roughly five times as much as the command "
             "line, so the two are not interchangeable there.")
    g.shot_box(
        "A command-line menu and submenu",
        "Capture a main menu and the submenu that opens from one category, so both levels are "
        "visible.",
        "cli-menus",
        "the navigation model. The numbered structure and the 0-to-go-back convention are the "
        "whole of what a new user needs to learn.",
    )

    # 3.3
    g.h("3.3 The REST API", 2)
    g.p(
        "One server process carries all five systems, so it is started once regardless of "
        "which system a caller is interested in."
    )
    g.code([
        "export API_SECRET_KEY='<long random string>'",
        "export JWT_SECRET_KEY='<a different long random string>'",
        "export API_CORS_ORIGINS='https://app.example.com'",
        "",
        "python -m education_system --university --api",
    ])
    g.p(
        "It listens on port 5000 by default; API_HOST and API_PORT change that. Endpoints are "
        "grouped by system:"
    )
    summary = api["summary"]
    rows = []
    for key, label, _flag, prefix in SYSTEMS:
        s = summary.get(prefix, {})
        rows.append([label, f"/api/v1/{prefix}/", str(s.get("groups", 0)),
                     str(s.get("paths", 0)), str(s.get("operations", 0))])
    g.table(["System", "Address prefix", "Groups", "Addresses", "Operations"], rows,
            widths=[1.7, 1.6, 0.8, 1.0, 1.1])
    g.note(
        "Measured from the running server, not from the source tree. An operation is one "
        "method on one address, so an address supporting both a read and a write counts twice. "
        "Appendix A lists every one."
    )
    g.figure("fig-api-surface",
             "The published API surface. Primary is the largest, not the University — "
             "about half the University's route modules are not registered on the "
             "server.")
    g.h("Conventions", 3)
    g.table(
        ["Aspect", "Behaviour"],
        [
            ["Authentication", "Authorization: Bearer <token>, obtained from "
                               "/api/v1/auth/login"],
            ["Versioning", "The version sits in the path: /api/v1/"],
            ["Scope", "A token reaches only the systems and roles its account holds"],
            ["Errors", "A JSON body carrying an error message, with a conventional HTTP status"],
            ["Rate limiting", "Applied to authentication endpoints; exceeded limits return 429"],
            ["Documentation", "/api/v1/docs lists every endpoint the running server publishes"],
            ["Health", "/api/v1/health, with /health/ready and /health/live for probes"],
        ],
        widths=[1.5, 5.0],
    )
    g.h("Beyond REST", 3)
    g.table(
        ["Channel", "Use"],
        [
            ["GraphQL", "Flexible querying where a caller wants specific fields only "
                        "(optional extra)"],
            ["WebSockets", "Live updates pushed as they happen — notifications, chat and "
                           "presence (optional extra; the platform falls back without it)"],
            ["Webhooks", "The platform notifies an external system when events occur"],
            ["LMS connectors", "Course and roster exchange with Canvas, Moodle, Google "
                               "Classroom and Microsoft Teams"],
        ],
        widths=[1.5, 5.0],
    )
    g.shot_box(
        "The API documentation page",
        "Start the API server and open http://localhost:5000/api/v1/docs in a browser.",
        "api-docs",
        "the browsable endpoint reference generated from the running server — the difference "
        "between an API you must ask about and one you can evaluate on the spot.",
    )
    g.page_break()


# ======================================================================
SYSTEM_PROSE = {
    "nursery": (
        "Ages 0–5, run against the Early Years Foundation Stage framework. The system covers "
        "both halves of what the EYFS asks of a setting: the learning and development "
        "requirements, and the statutory welfare requirements alongside them.",
        "A nursery's record is not a set of termly results but a continuous account of a "
        "child's day, and the system is shaped accordingly. Daily care is a first-class area "
        "rather than notes attached to a profile: the register, sign-in and sign-out, "
        "collections, the daily diary, sleep, nappy and toileting logs, meals, bottle feeds, "
        "allergies, medication, and the accident and existing-injury logs. Several exist "
        "because a regulator expects to see them — an existing-injury log is kept so that harm "
        "arriving with a child is recorded separately from harm occurring in the setting.",
        "Staffing has no equivalent in the school systems. Staff-to-child ratios are a legal "
        "requirement that varies by age band, and the system tracks them continuously with "
        "live ratio alerts rather than reporting a breach afterwards. Funding is likewise "
        "phase-specific: the 15- and 30-hour entitlements, two-year-old funding, funding "
        "claims, tax-free childcare and vouchers, sibling discounts, and occupancy against "
        "income.",
    ),
    "primary": (
        "Reception to Year 6, spanning the end of the EYFS, Key Stage 1 and Key Stage 2.",
        "The system is organised around the class rather than the subject, which is how a "
        "primary school runs: pupils belong to a class with a class teacher, and most of what "
        "is recorded about them is recorded there.",
        "Assessment is the area furthest from anything in the later phases — phonics tracking "
        "and the screening check, reading levels and records, the multiplication tables check, "
        "KS1 and KS2 SATs, and the EYFS profile carried forward from Reception — with "
        "intervention tracking and early-warning analytics on top, so that a pupil falling "
        "behind is identified while something can still be done.",
    ),
    "secondary": (
        "Years 7 to 11, covering Key Stage 3, Key Stage 4 and GCSE grading.",
        "The organising unit shifts from the class to the subject and the form group, and the "
        "system changes shape with it: subjects taught across year groups, an options process "
        "at the end of Key Stage 3, a timetable that has to work, and cover arrangements — "
        "including agency cover — when it does not.",
        "Assessment is built around the accountability measures a secondary school is judged "
        "on: the gradebook, target grades and baseline assessment feed Progress 8 and "
        "Attainment 8, alongside mock exams, GCSE entries and results day. Behaviour "
        "management is more formal than in Primary and has its own machinery — a behaviour "
        "log, detentions, and disciplinary and exclusion handling.",
    ),
    "sixth_form": (
        "Ages 16–19. The Sixth Form is the pivot between school and what follows.",
        "Its academic machinery resembles the Secondary system, but a whole category exists "
        "for progression that has no counterpart earlier in the platform: UCAS applications "
        "and the workflow behind them, personal statements, references, university offers and "
        "visits, apprenticeships, careers guidance, and destination tracking after students "
        "leave.",
        "Academically it handles A-levels and T-levels, courses and class groups, the extended "
        "project qualification, work experience, study planning and room booking, with a "
        "timetable optimiser alongside the timetable. Assessment adds predicted grades, "
        "individual learning plans, value-added measures and risk analytics. Finance carries "
        "bursary applications and the ILR census return particular to post-16 funding.",
    ),
    "university": (
        "The largest system by a wide margin — roughly 3,500 of the platform's 5,900 source "
        "files, which is why the repository still carries the name university_system.",
        "It covers the academic core a university needs — courses, modules, enrolments, "
        "assessments, exams, degree classification and progression — and then continues well "
        "beyond it into the business of running a campus: admissions and clearing, student "
        "finance and financial aid, scholarships, accommodation, campus facilities and "
        "navigation, library, dining, parking, printing, health services and counselling, "
        "careers, research administration, alumni relations, student union elections and "
        "clubs, and a set of campus commerce services.",
        "Several platform-wide capabilities are exercised here first and most fully: the AI "
        "study assistant, verifiable credentials and achievement badges, the LMS connectors, "
        "the parent portal, virtual classrooms, and early-warning analytics. Academic "
        "integrity, external examiners and mitigating circumstances have no equivalent in the "
        "school phases.",
    ),
}

WORKED_TASKS = {
    "nursery": ("Taking the daily register", [
        ("Daily Care & Routines → Daily Register", "Choose the room and the date."),
        ("Mark each child", "In or out; Sign In / Sign Out handles arrivals and collections "
                            "through the day, including late pickups."),
        ("Record care as it happens", "Sleep Log, Nappy / Toileting Log, Bottle Feeds and "
                                      "Medication Log are all in the same category."),
        ("Staff & Ratios → Live Ratio Alerts", "Check before finishing: attendance changes the "
                                               "ratio position."),
        ("Parents & Communication → Daily Updates", "Send the day's account to parents."),
    ]),
    "primary": ("Recording an assessment and acting on it", [
        ("Assessment & Progress → Phonics Screening", "Or Multiplication Check, KS1 SATs or "
                                                      "KS2 SATs, depending on the year group."),
        ("Select the class", "The whole class is entered together rather than pupil by pupil."),
        ("Enter the results and save", ""),
        ("Assessment & Progress → Early Warning", "The view now reflects the new data and "
                                                  "flags pupils at risk."),
        ("Pastoral & Wellbeing → Pupil Support", "Record the response for any pupil flagged. "
                                                 "This is the point of recording it."),
    ]),
    "secondary": ("Logging a behaviour incident", [
        ("Pastoral & Wellbeing → Behaviour Log", "Record the incident against the pupil, with "
                                                 "type and severity."),
        ("Pastoral & Wellbeing → Detentions", "Issue and track any sanction that follows."),
        ("Pastoral & Wellbeing → Disciplinary", "Only if the matter escalates."),
        ("Assessment & Grades → Gradebook", "Check whether the concern is academic as well as "
                                            "behavioural."),
        ("Staff & Communication → Parent Contacts", "Record or make the contact home."),
    ]),
    "sixth_form": ("Managing a UCAS application", [
        ("UCAS & Careers → UCAS Applications", "Create the application for the student."),
        ("UCAS & Careers → Personal Statements, References", "Attach supporting material as it "
                                                             "arrives."),
        ("UCAS & Careers → UCAS Workflow", "Move the application through its stages; the view "
                                           "shows every application in the tutor group at once."),
        ("UCAS & Careers → University Offers", "Record what comes back."),
        ("UCAS & Careers → Destinations", "After results, record where the student actually "
                                          "went."),
    ]),
    "university": ("Enrolling a student on a module", [
        ("Learners → Students", "Find or create the student record."),
        ("Academics → Courses / Modules", "Choose the course and the module."),
        ("Academics → Enrolments", "Enrol the student, and confirm the enrolment appears "
                                   "against both the student and the module."),
        ("Academics → Timetable", "Confirm the module's teaching now appears."),
        ("Finance → Student Finance", "Confirm the fee position; enrolment and fees move "
                                      "together."),
    ]),
}


def part_4_systems(g, menus, api, counts, inv):
    g.h("Part 4 — The five systems", 1)
    g.p(
        "One chapter per system. Each gives what the system covers, its complete menu "
        "reference, a worked task, and its endpoint groups. The full endpoint listing is in "
        "Appendix A."
    )
    g.table(
        ["System", "Ages / stage", "Source files", "CLI modules", "Desktop modules"],
        [[label,
          {"nursery": "0–5 (EYFS)", "primary": "Reception – Year 6",
           "secondary": "Years 7–11", "sixth_form": "16–19", "university": "18+"}[key],
          str(counts[key]["total"]), str(counts[key]["cli"]), str(counts[key]["gui"])]
         for key, label, _f, _p in SYSTEMS],
        widths=[1.7, 1.5, 1.1, 1.1, 1.1],
    )

    for idx, (key, label, flag, prefix) in enumerate(SYSTEMS, start=1):
        g.page_break()
        g.h(f"4.{idx} {label}", 2)
        for para in SYSTEM_PROSE[key]:
            g.p(para)

        # ── menus ─────────────────────────────────────────────────
        g.h(f"4.{idx}.1 Menu reference", 3)
        if key == "university":
            g.p(
                "The University does not share a single navigation definition the way the four "
                "school-phase systems do; its desktop application has grown to roughly five "
                "times the size of its command line, and each feature opens its own window "
                "with its own menus. What follows is the feature inventory, organised by the "
                "eleven domain areas the system is built from."
            )
            g.note(
                "Because the two interfaces have diverged, a feature listed under the desktop "
                "inventory may have no command-line equivalent. Anyone evaluating this system "
                "on the command line alone will substantially underestimate it."
            )
            uni = inv["university"]
            g.h("Desktop feature inventory", 4)
            for domain in sorted(uni["gui"]):
                feats = uni["gui"][domain]
                rows = []
                for feature in sorted(feats):
                    subs = feats[feature]
                    rows.append([_pretty(feature),
                                 ", ".join(_pretty(s) for s in subs[:14]) or "—"])
                g.p().add_run(_pretty(domain)).bold = True
                g.table(["Feature", "Includes"], rows, widths=[1.8, 4.7], small=True)
                g.shot_line(
                    f"University desktop — {_pretty(domain)}",
                    f"open a representative feature from the {_pretty(domain).lower()} area "
                    f"with demonstration data",
                    f"university-gui-{domain.replace('_', '-')}",
                )
            g.figure("fig-university-domains",
                     "Where the University's desktop features sit. Academics, "
                     "operations and pastoral carry most of the system.")
            g.h("Command-line module inventory", 4)
            for domain in sorted(uni["cli"]):
                feats = uni["cli"][domain]
                names = ", ".join(_pretty(f) for f in sorted(feats))
                para = g.p()
                r = para.add_run(_pretty(domain) + ": ")
                r.bold = True
                r.font.size = Pt(9.5)
                r2 = para.add_run(names or "—")
                r2.font.size = Pt(9.5)
        else:
            shared = menus.get(key + "_gui_matches_cli", False)
            if shared:
                g.p(
                    "The command line and the desktop application read the same navigation "
                    "definition, so this listing is complete and correct for both. Every "
                    "category below is a menu entry on the command line and a navigation-panel "
                    "entry in the window."
                )
            g.p(
                "Each category below has a screenshot slot for its page in the desktop "
                "application. One image per category is the right granularity: within a "
                "category every entry follows the same list-filter-detail pattern described "
                "in §3.1, so a picture of each individual entry would repeat the same layout "
                "dozens of times."
            )
            g.figure(f"fig-menu-{key}",
                     f"{label} — entries per menu category. The same categories "
                     f"appear on the command line and in the desktop application.")
            for cat in menus[key]:
                g.h(cat["category"], 4)
                items = cat["items"]
                rows = [[items[i], items[i + 1] if i + 1 < len(items) else ""]
                        for i in range(0, len(items), 2)]
                g.table(["Entry", "Entry"], rows, widths=[3.25, 3.25], small=True)
                slug = cat["category"].lower()
                for ch in " /&':":
                    slug = slug.replace(ch, "-")
                slug = "-".join(x for x in slug.split("-") if x)
                g.shot_line(
                    f"{label} — {cat['category']}",
                    f"open {cat['category']} in the navigation panel and capture a "
                    f"representative entry with demonstration data",
                    f"{key}-{slug}",
                )

        # ── worked task ───────────────────────────────────────────
        title, steps = WORKED_TASKS[key]
        g.h(f"4.{idx}.2 Worked task — {title.lower()}", 3)
        g.p(f"Start with python -m education_system {flag} --gui (or --cli; the steps are the same).")
        for n, (where, what) in enumerate(steps, start=1):
            g.step(n, f"{where}. {what}".strip())
        g.p()

        g.shot_box(
            f"{label} — desktop application",
            f"Open {label} with python -m education_system {flag} --gui and capture the dashboard with the "
            f"navigation panel visible.",
            f"{key}-gui",
            f"the home screen for {label}, and the categories listed in §4.{idx}.1 as they "
            f"actually appear.",
        )
        g.shot_box(
            f"{label} — command line",
            f"Run python -m education_system {flag} --cli and capture the main menu together with one "
            f"completed action.",
            f"{key}-cli",
            "the same categories as a numbered menu, and one action carried through to its "
            "result — which is what shows the command line is a full interface rather than a "
            "fallback.",
        )
        g.shot_box(
            f"{label} — worked task",
            f"Capture the screen from the worked task above ({title.lower()}) with "
            f"demonstration data loaded.",
            f"{key}-task",
            "the task in §4.%d.2 at the point it is being carried out." % idx,
        )

        # ── endpoints ─────────────────────────────────────────────
        g.h(f"4.{idx}.3 Endpoint groups", 3)
        groups = api["systems"].get(prefix, {})
        s = api["summary"].get(prefix, {})
        g.p(
            f"Served under /api/v1/{prefix}/ — {s.get('groups', 0)} groups publishing "
            f"{s.get('paths', 0)} addresses and {s.get('operations', 0)} operations. "
            f"Appendix A lists every address and the methods it accepts."
        )
        names = sorted(groups)
        rows = [[names[i], names[i + 1] if i + 1 < len(names) else "",
                 names[i + 2] if i + 2 < len(names) else ""]
                for i in range(0, len(names), 3)]
        g.table(["Group", "Group", "Group"], rows, widths=[2.17, 2.17, 2.17], small=True)
        g.shot_box(
            f"{label} — API",
            f"In /api/v1/docs, expand the {prefix} section and capture the endpoint groups.",
            f"{key}-api",
            f"what an integrator sees when evaluating {label}. The listing is generated from "
            f"the running server, so it cannot drift from what is actually published.",
        )


_METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}


def _merge(records):
    """One row per address, with every method it accepts."""
    merged: dict[str, set] = {}
    for r in records:
        merged.setdefault(r["path"], set()).update(r["methods"])
    return [[path, ", ".join(sorted(ms, key=lambda m: (_METHOD_ORDER.get(m, 9), m)))]
            for path, ms in sorted(merged.items())]


def _pretty(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").strip().title()


# ======================================================================
def part_5_admin(g):
    g.page_break()
    g.h("Part 5 — Administration", 1)
    g.p(
        "These tasks live in the System category on the command line, and in the settings and "
        "user-management areas of the desktop application. They work identically in all five "
        "systems."
    )
    g.h("5.1 Everyday tasks", 2)
    g.table(
        ["Task", "Where", "Notes"],
        [
            ["Create or edit a user account", "System → User Management",
             "One identity, a role granted per system"],
            ["Reset a password", "System → User Management",
             "The old password cannot be recovered, only replaced"],
            ["Clear a lockout", "System → User Management",
             "Otherwise clears itself after 15 minutes"],
            ["Set up multi-factor authentication", "System → Multi-Factor Authentication",
             "See §2.4 for each method"],
            ["Change your own password", "System → Change Password", "Available to every role"],
            ["Change the interface language", "System → Multi-Language",
             "Thirteen languages; coverage is broad but not complete"],
            ["Institution name, logo and colours", "System → Settings",
             "Branding is per installation and appears throughout"],
            ["Email settings", "System → Settings", "SMTP details are set here, not in code"],
            ["Policies, compliance, GDPR", "System (Primary, Secondary, Sixth Form); "
                                           "Compliance & Reports (Nursery)",
             "Nursery keeps these with Ofsted readiness and EYFS compliance instead"],
        ],
        widths=[1.9, 1.9, 2.7],
    )
    g.h("5.2 Branding the installation", 2)
    g.step(1, "Open System → Settings.")
    g.step(2, "Set the institution name, abbreviation and tagline. The tagline becomes the "
              "dashboard heading.")
    g.step(3, "Upload a logo. It appears in the desktop header and on generated documents.")
    g.step(4, "Set the colours, and check the result on a dashboard before telling anyone it "
              "is done.")
    g.shot_box(
        "Administration and branding",
        "Capture the settings screen showing name, tagline, colours and logo.",
        "branding",
        "the settings an administrator controls per institution. The tagline shown here is "
        "what appears as the dashboard heading.",
    )
    g.h("5.3 Languages", 2)
    g.p(
        "The interface carries translations for thirteen languages. Coverage is broad but not "
        "complete: most modules are fully translated and a minority still fall back to "
        "English. Changing the language is per user, from System → Multi-Language."
    )
    g.h("5.4 Email", 2)
    g.step(1, "Open System → Settings and enter the SMTP host, port, credentials and the "
              "address mail should come from.")
    g.step(2, "Send a test message before relying on it.")
    g.step(3, "Note that emailed multi-factor codes and password-reset links both depend on "
              "this working — if SMTP is broken, so is account recovery.")
    g.p()
    g.p(
        "The platform sends from a library of around 450 templates covering admissions, "
        "finance, safeguarding, attendance, library and health. Templates can be edited so "
        "that routine correspondence starts from one rather than a blank page."
    )
    g.h("5.5 Maintenance", 2)
    g.table(
        ["Task", "How"],
        [
            ["Back up", "Copy the runtime folder, or use the scheduled encrypted backup "
                        "tooling (§2.10)"],
            ["Apply database migrations", "Handled automatically at startup; Alembic manages "
                                          "the schema"],
            ["Update dependencies", "pip install -r requirements.lock after pulling changes"],
            ["Check health", "/api/v1/health when the API is running"],
            ["Review the audit log", "§2.11 — worth doing on a schedule, not only after an "
                                     "incident"],
        ],
        widths=[1.9, 4.6],
    )


def part_6_progression(g):
    g.page_break()
    g.h("Part 6 — Moving learners between phases", 1)
    g.p(
        "A learner progressing from one phase to the next — nursery to primary, sixth form to "
        "university — is not re-created as a new person. The transfer goes through a durable "
        "queue rather than a direct copy, so that a transfer interrupted part-way is completed "
        "rather than lost, and so that both sides can be reconciled afterwards."
    )
    g.figure("fig-progression",
             "A transfer goes onto a durable queue and is drained into the receiving "
             "system by a background worker, so an interrupted transfer is completed "
             "rather than lost.")
    g.step(1, "Open the Cross-System category and choose the promotion or transition entry — "
              "Transition to School and Move to Primary School in Nursery, Promote to Next "
              "System elsewhere.")
    g.step(2, "Select the learners to move.")
    g.step(3, "Confirm. The transfer is placed on the queue rather than applied immediately.")
    g.step(4, "A background worker drains the queue into the receiving system. This starts "
              "automatically when a system is launched.")
    g.step(5, "Check the learner appears in the receiving system, and use Student Journey to "
              "see their record across all five phases.")
    g.p()
    g.note(
        "Consent to transfer between systems can be recorded and checked as part of this "
        "process — see §2.12."
    )
    g.shot_box(
        "The student journey across phases",
        "Open Cross-System → Student Journey for a demonstration learner with records in more "
        "than one system.",
        "student-journey",
        "one learner's record spanning several phases. This continuity is the reason the five "
        "systems are one platform rather than five applications.",
    )


def part_7_troubleshooting(g):
    g.page_break()
    g.h("Part 7 — Troubleshooting", 1)
    g.table(
        ["Symptom", "Likely cause", "What to do"],
        [
            ["The desktop interface will not start, but the command line does",
             "The system Tk package is missing",
             "Install it (sudo apt-get install python3-tk on Ubuntu)"],
            ["The window is cut off at the edges", "The display is narrower than 1200 pixels",
             "The window will not shrink below 1200×800. Use a larger display"],
            ["Nobody can sign in on a fresh installation", "No accounts were created",
             "Demonstration accounts exist only with EDU_DEV_SEED set; otherwise bootstrap one "
             "administrator with EDU_INITIAL_ADMIN_USER and EDU_INITIAL_ADMIN_PASSWORD"],
            ["An account is locked out", "Five failed sign-in attempts",
             "Wait 15 minutes, or have an administrator clear it (§2.5)"],
            ["A user lost their authenticator device", "No second factor available",
             "Use a recovery code; failing that an administrator disables MFA after verifying "
             "identity out of band (§2.4)"],
            ["The API server exits immediately", "A required environment variable is not set",
             "API_SECRET_KEY, JWT_SECRET_KEY and API_CORS_ORIGINS must all be set. The error "
             "names the missing one"],
            ["The API server starts but the port is in use", "Something else is on port 5000",
             "Set API_PORT to a free port"],
            ["An endpoint returns 401", "Missing, expired or wrong-scoped token",
             "Refresh the token; check with /api/v1/auth/me that the account holds a role in "
             "the system being called"],
            ["An endpoint returns 429", "Rate limit exceeded",
             "Back off and retry. Authentication endpoints are limited per account and per "
             "origin"],
            ["A browser call is blocked by CORS", "The origin is not in API_CORS_ORIGINS",
             "Add the exact origin. Never use a wildcard"],
            ["A feature is in the desktop application but not the API",
             "Expected, particularly in the University",
             "Check /api/v1/docs before scoping an integration"],
            ["Emailed codes and reset links never arrive", "SMTP is not configured or broken",
             "Fix SMTP (§5.4). Account recovery depends on it"],
            ["Startup is noisy, or something failed silently", "Console logging is kept quiet",
             "Re-run with --verbose for the full startup log"],
        ],
        widths=[2.1, 1.9, 2.5],
        small=True,
    )


# ======================================================================
def appendices(g, api, inv):
    g.page_break()
    g.h("Appendix A — Complete endpoint reference", 1)
    g.p(
        "Every address the running server publishes, grouped by system and then by endpoint "
        "group, with the HTTP methods each accepts. Path segments in angle brackets are "
        "parameters supplied by the caller."
    )
    g.note(
        "Generated from the server's own routing table. If an address is not listed here, the "
        "installation does not publish it."
    )
    for key, label, _flag, prefix in SYSTEMS:
        groups = api["systems"].get(prefix, {})
        if not groups:
            continue
        g.page_break()
        g.h(f"A.{SYSTEMS.index((key, label, _flag, prefix)) + 1} {label} — /api/v1/{prefix}/", 2)
        s = api["summary"].get(prefix, {})
        g.p(f"{s.get('groups', 0)} groups, {s.get('paths', 0)} addresses, "
            f"{s.get('operations', 0)} operations.")
        for group in sorted(groups):
            g.h(f"/{group}", 4)
            g.table(["Address", "Methods"], _merge(groups[group]),
                    widths=[5.1, 1.4], small=True)

    g.page_break()
    g.h("Appendix B — Shared platform endpoints", 1)
    g.p(
        "These are not specific to one system. Authentication is the important one: a token "
        "obtained here is what every per-system call in Appendix A requires."
    )
    for group in sorted(api["shared"]):
        rows = _merge(api["shared"][group])
        if not rows:
            continue
        g.h(f"/{group}", 4)
        g.table(["Address", "Methods"], rows, widths=[5.1, 1.4], small=True)

    g.page_break()
    g.h("Appendix C — Glossary", 1)
    g.table(
        ["Term", "Meaning"],
        [
            ["EYFS", "Early Years Foundation Stage — the statutory framework for children from "
                     "birth to five"],
            ["SEND", "Special Educational Needs and Disabilities"],
            ["EHC plan", "Education, Health and Care plan — a statutory plan of support"],
            ["DSL", "Designated Safeguarding Lead"],
            ["DBS", "Disclosure and Barring Service — the criminal-records check required to "
                    "work with children"],
            ["Prevent duty", "The statutory duty to prevent people being drawn into terrorism"],
            ["SATs", "The national curriculum tests taken at the end of Key Stages 1 and 2"],
            ["Progress 8 / Attainment 8", "Secondary school accountability measures"],
            ["EPQ", "Extended Project Qualification"],
            ["ILR", "Individualised Learner Record — the post-16 funding return"],
            ["UCAS", "Universities and Colleges Admissions Service"],
            ["HESA", "The higher education statistics return"],
            ["Safeguarding", "The duty to protect children and vulnerable people from harm"],
            ["GDPR", "The data protection law governing personal information"],
            ["SAR", "Subject Access Request — a person's request for their own data"],
            ["MFA", "Multi-factor authentication"],
            ["TOTP", "Time-based One-Time Password — the rotating six-digit code from an "
                     "authenticator app"],
            ["WebAuthn", "The standard behind hardware security keys and device biometrics"],
            ["bcrypt", "A deliberately slow password-hashing algorithm"],
            ["Fernet", "The authenticated encryption scheme used for field-level encryption"],
            ["JWT", "JSON Web Token — the bearer token issued by the API"],
            ["CORS", "The browser rule controlling which websites may call an API"],
            ["SQLite", "A self-contained database stored as an ordinary file"],
            ["WAL", "Write-Ahead Logging — a SQLite mode allowing reads and writes at once"],
            ["REST / GraphQL", "Two conventions for letting other software query and update "
                               "the platform"],
            ["Webhook", "An outbound notification sent automatically when something happens"],
            ["LMS", "Learning Management System — Canvas, Moodle, Google Classroom, Teams"],
            ["PWA", "Progressive Web App — a website that behaves like an installed app"],
        ],
        widths=[1.5, 5.0],
    )

    g.page_break()
    g.h("Appendix D — Screenshot index", 1)
    g.p(
        "Every screenshot placeholder in this guide, in order. Capture by interface rather "
        "than by system — all the command lines in one sitting, then all the desktop "
        "applications, then the API documentation page once — or you will start and stop the "
        "application dozens of times."
    )
    g.warn(
        "Use demonstration data only. A screenshot showing a real child's name, date of birth, "
        "medical note or safeguarding concern is a disclosure of personal data, and it travels "
        "further than a database export because it ends up embedded in a document that gets "
        "forwarded and printed."
    )
    rows = [[str(n), title] for n, title in getattr(g, "shots", [])]
    g.table(["#", "Image"], rows, widths=[0.6, 5.9], small=True)

    g.h("Appendix E — Figure index", 1)
    g.p(
        "The charts and diagrams in this guide. All are generated from the same "
        "inventory as the reference tables, so they cannot disagree with them; "
        "rebuild them with the figure script whenever the guide is regenerated."
    )
    rows = [[str(n), cap] for n, cap in getattr(g, "figs", [])]
    g.table(["Figure", "Shows"], rows, widths=[0.7, 5.8], small=True)


# ======================================================================
def write_contents(g):
    """Fill the contents placeholder from the headings actually emitted."""
    anchor = g.toc_marker._p
    for level, text in g.headings:
        p = g.doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Pt({1: 0, 2: 14, 3: 28}[level])
        pf.space_after = Pt(1)
        r = p.add_run(text)
        r.font.size = Pt(10 if level == 1 else 9.5)
        if level == 1:
            r.bold = True
            r.font.color.rgb = NAVY
        elif level == 3:
            r.font.color.rgb = GREY
        anchor.addprevious(p._p)


def main(inv_path, out_path, figdir=None):
    inv = json.loads(open(inv_path).read())
    g = Guide(inv, figdir or str(Path(out_path).parent / "assets" / "guide"))
    build(g)
    write_contents(g)
    g._footer()
    g.doc.save(out_path)
    print("saved", out_path)
    print("screenshots:", shot["n"], " figures:", fignum["n"],
          " headings:", len(g.headings))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
