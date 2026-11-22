"""Reports & Analytics buttons of the Primary School main menu (GUI + CLI).

Every button in the category opens on an empty sandbox school without an
error or the "not yet implemented" stub, in the GUI (``NAV_CATEGORIES``) and
the terminal (``CATEGORIES`` via ``_submenu``). Behind the buttons the
rebuilt reporting layer is checked with real data: every KPI tile and Data
Dashboard panel computes on an empty school and after seeding a pupil, the
Mobile Dashboard feeds pick up the seeded data, every Custom Export dataset
returns rows carrying its declared columns, and every Data Export preset
writes its files into ``tmp_path``. Audit Reports, Data Export and Custom
Export are admin-only: a teacher is refused them in both front ends.

All data lives in the ``primary_sandbox`` temp directories (see conftest).
"""

from __future__ import annotations

import csv
import datetime as dt
import importlib
import io
import json
import zipfile
from contextlib import redirect_stdout

import pytest

from education_system.systems.primary import cli_main, gui_main
from education_system.systems.primary.domain import access

CATEGORY = "Reports & Analytics"

#: label -> GUI handler, in sidebar order.
EXPECTED = {
    "Attendance Report": "open_report_attendance",
    "Progress Report": "open_report_progress",
    "KPI Dashboard": "open_kpi_dashboard",
    "Data Dashboard": "open_data_dashboard",
    "Mobile Dashboard": "open_mobile_dashboard",
    "Audit Reports": "open_audit_reports",
    "Data Export": "open_data_export",
    "Custom Export": "open_export",
}
LABELS = list(EXPECTED)
ADMIN_ONLY_LABELS = ["Audit Reports", "Data Export", "Custom Export"]
STAFF_LABELS = [lb for lb in LABELS if lb not in ADMIN_ONLY_LABELS]

#: The page heading each GUI button draws in the main window's content frame
#: (the title passed to ``kit.show_page``). Every report is a page now - none
#: opens a Toplevel.
GUI_PAGE_TITLES = {label: label for label in LABELS}

#: The first line each terminal screen prints.
CLI_HEADERS = {
    "Attendance Report": "-- Attendance Report --",
    "Progress Report": "-- Progress Report --",
    "KPI Dashboard": "═══ KPI Dashboard ═══",
    "Data Dashboard": "═══ Data Dashboard ═══",
    "Mobile Dashboard": "── Mobile Dashboard ──",
    "Audit Reports": "── Audit Reports ──",
    "Data Export": "── Data Export ──",
    "Custom Export": "── Custom Export ──",
}

#: Strings that mean a screen failed rather than opened.
CLI_FAILURES = ("[stub]", "Traceback", "Error:", "Error opening", "✗")

DATASET_KEYS = [
    "pupils", "staff", "attendance", "behaviour", "safeguarding", "subjects",
    "homework", "parent_contacts", "trips", "send", "reading_levels",
    "phonics_screening", "mtc", "ks1_sats", "ks2_sats", "progress_reviews",
    "dinner_money", "pupil_premium", "receipts",
]
PRESET_DATASETS = {
    "full_backup": None,  # every registered dataset
    "pupils_core": ["pupils", "parent_contacts", "send", "pupil_premium"],
    "academics": ["subjects", "attendance", "homework"],
    "assessment": ["reading_levels", "phonics_screening", "mtc", "ks1_sats",
                   "ks2_sats", "progress_reviews"],
    "pastoral": ["behaviour", "safeguarding", "send", "progress_reviews"],
    "finance": ["dinner_money", "trips", "receipts", "pupil_premium"],
    "staff": ["staff"],
}

_DOMAIN = "education_system.systems.primary.domain."
_REPORTING = _DOMAIN + "operations.reporting."


def _domain(name: str):
    return importlib.import_module(_DOMAIN + name)


def _kpi():
    return importlib.import_module(_REPORTING + "kpi_dashboard.kpi_dashboard")


def _data_dashboard():
    return importlib.import_module(_REPORTING + "data_dashboard.data_dashboard")


def _mobile():
    return importlib.import_module(_REPORTING + "mobile_dashboard.mobile_dashboard")


def _custom_export():
    return importlib.import_module(_REPORTING + "custom_export.custom_export")


def _data_export():
    return importlib.import_module(_REPORTING + "data_export.data_export")


# ── Seeding ──────────────────────────────────────────────────────────

def _seed_school() -> str:
    """One Year 4 pupil with one record in every dataset the reports read.
    Returns the pupil id."""
    today = dt.date.today().isoformat()
    pupils = _domain("learners.pupils.pupils")
    pid = pupils.create_pupil({
        "first_name": "Ada", "last_name": "Lovelace", "year_group": "4",
        "date_of_birth": "2017-03-01", "send_status": "yes",
    }).pupil_id

    subjects = _domain("academics.subjects.subjects")
    subjects.create({"code": "MA", "name": "Maths", "key_stage": "KS2"})
    _domain("academics.classes.classes").create({"name": "Oak", "year_group": "4"})
    _domain("staff.staff").create_staff({
        "first_name": "Grace", "last_name": "Hopper", "email": "grace@example.test"})
    _domain("academics.attendance.attendance").record_mark(pid, today, "AM", "/")

    reading = _domain("assessment.reading_levels.reading_levels")
    reading.record_assessment(pid, {"band": reading.BANDS[0], "status": "working",
                                    "assessed_on": today})
    _domain("assessment.phonics_screening.phonics_screening").create({
        "pupil_id": pid, "academic_year": "2025-26", "attempt": 1, "score": 35,
        "assessed_on": today})
    _domain("assessment.mtc.mtc").create({
        "pupil_id": pid, "academic_year": "2025-26", "score": 22, "assessed_on": today})
    _domain("assessment.ks1_sats.ks1_sats").create({
        "pupil_id": pid, "academic_year": "2025-26", "subject": "Reading",
        "scaled_score": 104, "outcome": "EXS", "assessed_on": today})
    _domain("assessment.ks2_sats.ks2_sats").create({
        "pupil_id": pid, "academic_year": "2025-26", "subject": "Maths",
        "scaled_score": 104, "outcome": "EXS", "assessed_on": today})
    _domain("assessment.progress.progress").create_review({
        "student_id": pid, "review_date": today, "risk_level": "High"})

    _domain("finance.dinner_money.dinner_money").charge_meal(
        pid, entry_date=today, amount_pence=250)
    _domain("finance.pupil_premium.pupil_premium").upsert(
        {"pupil_id": pid, "academic_year": "2025/26"})
    _domain("pastoral.send.send").upsert({"pupil_id": pid, "academic_year": "2025/26"})
    _domain("finance.receipts.receipts").create_receipt(
        {"payer_name": "Parent", "student_id": pid, "issued_date": today},
        [{"description": "Trip", "amount": 5}])

    behaviour = _domain("pastoral.behaviour.behaviour")
    behaviour.log_incident({
        "pupil_id": pid, "incident_date": today,
        "incident_type": next(iter(behaviour.INCIDENT_TYPES)),
        "description": "Helped a friend"})
    _domain("academics.homework.homework").create_assignment({
        "title": "Spellings", "subject_id": subjects.list_all()[0].subject_id,
        "year_group": "4", "due_date": today})
    _domain("finance.trips.trips").create_trip({"name": "Zoo", "start_date": today})
    _domain("operations.communications.parent_contacts.parent_contacts").create_contact({
        "student_id": pid, "first_name": "Ann", "last_name": "Lovelace",
        "primary_phone": "01234 567890", "email": "ann@example.test"})
    _domain("safeguarding.safeguarding").raise_concern({
        "pupil_id": pid, "description": "Test concern", "incident_date": today})
    return pid


@pytest.fixture
def seeded_pupil():
    return _seed_school()


# ── 1. The menus list the buttons ────────────────────────────────────

def _gui_items() -> list[tuple[str, str]]:
    return dict(gui_main.NAV_CATEGORIES)[CATEGORY]


def test_gui_category_lists_every_button():
    assert _gui_items() == list(EXPECTED.items())


def test_cli_category_lists_every_button():
    assert dict(cli_main.CATEGORIES)[CATEGORY] == LABELS


@pytest.mark.parametrize("label", LABELS)
def test_gui_handler_is_a_real_method(label):
    handler = EXPECTED[label]
    method = getattr(gui_main.PrimarySchoolMainGUI, handler, None)
    assert callable(method), f"{handler} missing - {label} would show the stub"
    assert method.__qualname__ == f"PrimarySchoolMainGUI.{handler}"


def test_admin_only_labels_match_the_access_policy():
    assert {lb for lb in LABELS if lb in access.ADMIN_ONLY} == set(ADMIN_ONLY_LABELS)


# ── 2. GUI: every button opens ───────────────────────────────────────

def _frame_text(widget) -> str:
    import tkinter as tk

    seen: list[str] = []

    def walk(w):
        try:
            text = w.cget("text")
            if text:
                seen.append(str(text))
        except (tk.TclError, AttributeError):
            pass
        for child in w.winfo_children():
            walk(child)

    walk(widget)
    return "\n".join(seen)


def _open(gui, label, toplevels):
    before = set(toplevels(gui))
    getattr(gui, EXPECTED[label])()
    gui.root.update_idletasks()
    return [w for w in toplevels(gui) if w not in before]


@pytest.mark.gui
@pytest.mark.parametrize("label", LABELS)
def test_gui_button_opens_its_screen(label, primary_gui, content_text, toplevels):
    new = _open(primary_gui, label, toplevels)

    text = content_text(primary_gui)
    assert "not yet implemented" not in text
    assert primary_gui.principal.denied_message(label) not in text
    errors = [m for m in primary_gui.messages if m[0] == "showerror"]
    assert not errors, errors
    assert new == [], f"{label} opened a window: {[w.title() for w in new]}"
    title = GUI_PAGE_TITLES[label]
    assert primary_gui._current_page and primary_gui._current_page[0] == title
    assert title in _frame_text(primary_gui.content_frame).splitlines(), \
        f"{label}: no {title!r} heading in the content area"


@pytest.mark.gui
def test_gui_kpi_dashboard_draws_every_tile(primary_gui):
    primary_gui.open_kpi_dashboard()
    primary_gui.root.update_idletasks()
    shown = _frame_text(primary_gui.content_frame)
    for tile in _kpi().snapshot().tiles:
        assert tile.label in shown


@pytest.mark.gui
def test_gui_data_dashboard_shows_every_panel(primary_gui):
    primary_gui.open_data_dashboard()
    primary_gui.root.update_idletasks()
    import tkinter.ttk as ttk

    notebooks = []

    def walk(w):
        if isinstance(w, ttk.Notebook):
            notebooks.append(w)
        for child in w.winfo_children():
            walk(child)

    walk(primary_gui.content_frame)
    assert notebooks, "Data Dashboard drew no panel notebook"
    tabs = [notebooks[0].tab(t, "text") for t in notebooks[0].tabs()]
    assert len(tabs) == len(_data_dashboard().build_panels().panels)


# ── 3. CLI: every button opens ───────────────────────────────────────

def _run_submenu(label, auth, scripted_input) -> str:
    items = dict(cli_main.CATEGORIES)[CATEGORY]
    choice = str(items.index(label) + 1)
    # pick the item, leave the screen, leave the category
    scripted_input([choice, "0", "0"] + ["0", ""] * 20)
    out = io.StringIO()
    with redirect_stdout(out):
        try:
            cli_main._submenu(CATEGORY, items, auth=auth)
        except BaseException as exc:  # conftest's OutOfInput (not importable: no package)
            if type(exc).__name__ != "OutOfInput":
                raise
            pytest.fail(f"{label} kept asking for input:\n{out.getvalue()[-2000:]}")
    return out.getvalue()


@pytest.mark.parametrize("label", LABELS)
def test_cli_button_opens_its_screen(label, fake_auth, admin_principal, scripted_input):
    out = _run_submenu(label, fake_auth, scripted_input)

    for bad in CLI_FAILURES:
        assert bad not in out, f"{bad!r} in {label} output:\n{out[-2000:]}"
    assert admin_principal.denied_message(label) not in out
    assert CLI_HEADERS[label] in out


def test_cli_kpi_dashboard_prints_every_tile(fake_auth, admin_principal, scripted_input):
    out = _run_submenu("KPI Dashboard", fake_auth, scripted_input)
    for tile in _kpi().snapshot().tiles:
        assert tile.label in out


def test_cli_data_dashboard_lists_every_panel(fake_auth, admin_principal, scripted_input):
    out = _run_submenu("Data Dashboard", fake_auth, scripted_input)
    for panel in _data_dashboard().build_panels().panels:
        assert panel.name in out


# ── 4a. KPI Dashboard tiles ──────────────────────────────────────────

KPI_TILES = ["kpi_student_count", "kpi_staff_count", "kpi_subject_count",
             "kpi_classes", "kpi_dinner_money_owed", "kpi_pupil_premium",
             "kpi_send_pupils"]

#: tile function -> (value on an empty school, value after _seed_school)
KPI_VALUES = {
    "kpi_student_count": ("0", "1"),
    "kpi_staff_count": ("0", "1"),
    "kpi_subject_count": ("0", "1"),
    "kpi_classes": ("0", "1"),
    "kpi_dinner_money_owed": ("£0.00", "£2.50"),
    "kpi_pupil_premium": ("0", "1"),
    "kpi_send_pupils": ("0", "1"),
}


@pytest.mark.parametrize("name", KPI_TILES)
def test_kpi_tile_computes_on_empty_school(name):
    tile = getattr(_kpi(), name)()
    # "—" means the metric raised and was swallowed
    assert tile.value == KPI_VALUES[name][0], tile


@pytest.mark.parametrize("name", KPI_TILES)
def test_kpi_tile_counts_seeded_pupil(name, seeded_pupil):
    tile = getattr(_kpi(), name)()
    assert tile.value == KPI_VALUES[name][1], tile


def test_kpi_dinner_money_hint_counts_debtors(seeded_pupil):
    assert _kpi().kpi_dinner_money_owed().hint == "1 pupil(s) in debt"


def test_kpi_send_hint_counts_ehcps(seeded_pupil):
    assert _kpi().kpi_send_pupils().hint == "0 with an EHCP"


def test_kpi_attendance_tiles_use_todays_marks(seeded_pupil):
    kpi = _kpi()
    assert kpi.kpi_today_attendance().value == "100%"
    assert kpi.kpi_window_attendance(30).value == "100%"
    assert kpi.kpi_attendance_at_risk(30, 90.0).value == "0"
    assert kpi.kpi_recent_behaviour(30).value == "1"


def test_kpi_attendance_tiles_empty_school():
    kpi = _kpi()
    assert kpi.kpi_today_attendance().value == "—"
    assert kpi.kpi_today_attendance().hint == "No marks recorded today"
    assert kpi.kpi_attendance_at_risk(30, 90.0).value == "0"
    assert kpi.kpi_recent_behaviour(30).value == "0"


def test_kpi_snapshot_has_no_secondary_or_post16_tiles():
    kpi = _kpi()
    names = [n for n in vars(kpi) if n.startswith("kpi_")]
    for gone in ("ucas", "apprentice", "exam_entr"):
        assert not [n for n in names if gone in n], names
    labels = [t.label.lower() for t in kpi.snapshot().tiles]
    for gone in ("ucas", "apprentice", "exam entr"):
        assert not [lb for lb in labels if gone in lb], labels


def test_kpi_snapshot_every_tile_computes(seeded_pupil):
    tiles = _kpi().snapshot().tiles
    assert len(tiles) == 11
    assert all(t.value != "—" for t in tiles), [t for t in tiles if t.value == "—"]


# ── 4b. Data Dashboard panels ────────────────────────────────────────

PANELS = {
    "panel_pupils_by_year_group": "Pupils by year group",
    "panel_dinner_money": "Dinner money balances",
    "panel_pupil_premium": "Pupil Premium by category",
    "panel_send_by_stage": "SEND register by stage",
}
PANEL_EMPTY_NOTES = {
    "panel_pupils_by_year_group": "No pupils on roll.",
    "panel_dinner_money": "No dinner money accounts.",
    "panel_pupil_premium": "No Pupil Premium records.",
    "panel_send_by_stage": "No pupils on the SEND register.",
}
PANEL_SEEDED_ROW = {
    "panel_pupils_by_year_group": ("Year 4", 1),
    "panel_dinner_money": ("In debt", 1),
    "panel_pupil_premium": ("Ever 6 FSM", 1),
    "panel_send_by_stage": ("Monitoring", 1),
}


@pytest.mark.parametrize("name", list(PANELS))
def test_data_panel_empty_school(name):
    panel = getattr(_data_dashboard(), name)()
    assert panel.name == PANELS[name]
    # "... unavailable." means the collector raised
    assert panel.note == PANEL_EMPTY_NOTES[name]
    assert panel.rows == [] and panel.total is None


@pytest.mark.parametrize("name", list(PANELS))
def test_data_panel_counts_seeded_pupil(name, seeded_pupil):
    panel = getattr(_data_dashboard(), name)()
    assert panel.note == ""
    assert panel.total == 1
    assert [(r.label, r.count) for r in panel.rows] == [PANEL_SEEDED_ROW[name]]


def test_data_panel_year_group_counts_send(seeded_pupil):
    row = _data_dashboard().panel_pupils_by_year_group().rows[0]
    assert row.extra == "1"


@pytest.mark.parametrize("seed", [False, True], ids=["empty", "seeded"])
def test_data_dashboard_build_panels(seed):
    if seed:
        _seed_school()
    snap = _data_dashboard().build_panels()
    names = [p.name for p in snap.panels]
    for wanted in PANELS.values():
        assert wanted in names
    assert not [p for p in snap.panels if "unavailable" in p.note]
    attendance = next(p for p in snap.panels if p.name.startswith("Attendance status"))
    assert attendance.total == (1 if seed else None)


# ── 4c. Mobile Dashboard ─────────────────────────────────────────────

def test_mobile_feeds_empty_school():
    mobile = _mobile()
    assert mobile._high_risk_feed() == []
    assert mobile._today_attendance() == (0, 0, None)


def test_mobile_feeds_seeded(seeded_pupil):
    mobile = _mobile()
    assert mobile._today_attendance() == (1, 1, 100.0)
    feed = mobile._high_risk_feed()
    assert len(feed) == 1
    assert feed[0].title == f"Ada Lovelace ({seeded_pupil})"
    assert feed[0].severity == "warn"


@pytest.mark.parametrize("seed", [False, True], ids=["empty", "seeded"])
def test_mobile_build_dashboard_tiles(seed):
    if seed:
        _seed_school()
    d = _mobile().build_dashboard()
    tiles = {t.key: t.value for t in d.tiles}
    assert set(tiles) == {"students", "attendance", "open_targets", "high_risk",
                          "today_events"}
    assert tiles["students"] == ("1" if seed else "0")
    assert tiles["high_risk"] == ("1" if seed else "0")
    assert tiles["attendance"] == ("100.0%" if seed else "—")


# ── 4d. Custom Export datasets ───────────────────────────────────────

def test_custom_export_registers_every_dataset():
    assert sorted(_custom_export().DATASETS()) == sorted(DATASET_KEYS)


@pytest.mark.parametrize("key", DATASET_KEYS)
def test_custom_export_dataset_empty_school(key):
    ce = _custom_export()
    spec = ce.get_dataset(key)
    assert ce.fetch(key) == []
    header = next(csv.reader(io.StringIO(ce.render(key, fmt="csv"))))
    assert header == [h for _k, h in spec.columns]


@pytest.mark.parametrize("key", DATASET_KEYS)
def test_custom_export_dataset_rows_carry_declared_columns(key, seeded_pupil):
    ce = _custom_export()
    spec = ce.get_dataset(key)
    rows = ce.fetch(key)
    assert len(rows) == 1, f"{key} returned {len(rows)} row(s) after seeding"
    row = rows[0]
    for col, _header in spec.columns:
        present = col in row if isinstance(row, dict) else hasattr(row, col)
        assert present, f"{key} column {col!r} is not a field of {type(row).__name__}"
    for pupil_col in ("pupil_id", "student_id"):
        if pupil_col in dict(spec.columns):
            assert ce._get(row, pupil_col) == seeded_pupil

    table = list(csv.reader(io.StringIO(ce.render(key, fmt="csv"))))
    assert len(table) == 2 and len(table[1]) == len(spec.columns)


def test_custom_export_writes_into_tmp(tmp_path, seeded_pupil):
    ce = _custom_export()
    target = tmp_path / "exports" / "pupils.json"
    res = ce.export("pupils", target)
    assert res.fmt == "json" and res.row_count == 1
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data[0]["Pupil ID"] == seeded_pupil


def test_custom_export_attendance_uses_list_records(seeded_pupil):
    ce = _custom_export()
    today = dt.date.today().isoformat()
    rows = ce.fetch("attendance", filters={"pupil_id": seeded_pupil,
                                           "date_from": today, "date_to": today})
    assert [(r.pupil_id, r.date, r.session) for r in rows] == [(seeded_pupil, today, "AM")]
    assert ce.fetch("attendance", filters={"date_from": "2000-01-01",
                                           "date_to": "2000-01-02"}) == []


# ── 4e. Data Export presets ──────────────────────────────────────────

def test_data_export_builtin_presets():
    presets = {p.key: p for p in _data_export().list_presets() if p.is_builtin}
    assert sorted(presets) == sorted(PRESET_DATASETS)
    for key, datasets in PRESET_DATASETS.items():
        expected = sorted(DATASET_KEYS) if datasets is None else datasets
        assert sorted(presets[key].datasets) == sorted(expected), key


def _check_job(job, out_dir, rows_per_file):
    assert job.status == "succeeded", [(f.dataset_key, f.error) for f in job.files]
    assert (out_dir / "_manifest.json").is_file()
    for f in job.files:
        assert f.error is None
        path = out_dir / f"{f.dataset_key}.csv"
        assert f.file_path == str(path) and path.is_file()
        assert f.row_count == rows_per_file, (f.dataset_key, f.row_count)


@pytest.mark.parametrize("preset", list(PRESET_DATASETS))
def test_data_export_preset_writes_files_empty_school(preset, tmp_path):
    out_dir = tmp_path / "export" / preset
    job = _data_export().run_export(preset, out_dir, fmt="csv")
    _check_job(job, out_dir, 0)
    manifest = json.loads((out_dir / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["preset_key"] == preset
    assert len(manifest["files"]) == len(job.files)


@pytest.mark.parametrize("preset", list(PRESET_DATASETS))
def test_data_export_preset_writes_seeded_rows(preset, tmp_path, seeded_pupil):
    out_dir = tmp_path / "export" / preset
    job = _data_export().run_export(preset, out_dir, fmt="csv")
    _check_job(job, out_dir, 1)
    assert job.rows_total == len(job.files)


def test_data_export_zip_and_job_history(tmp_path, seeded_pupil):
    de = _data_export()
    out_dir = tmp_path / "export" / "finance"
    job = de.run_export("finance", out_dir, fmt="jsonl", zip_output=True, run_by="admin3")
    assert job.status == "succeeded" and job.zipped
    assert job.archive_path and job.archive_path.startswith(str(tmp_path))
    with zipfile.ZipFile(job.archive_path) as zf:
        names = set(zf.namelist())
    assert {f"{k}.jsonl" for k in PRESET_DATASETS["finance"]} <= names
    assert [j.job_id for j in de.list_jobs(preset_key="finance")] == [job.job_id]


def test_data_export_unknown_preset_refused(tmp_path):
    de = _data_export()
    with pytest.raises(de.ValidationError):
        de.run_export("no_such_preset", tmp_path / "x")


# ── 5. Access: admin-only buttons ────────────────────────────────────

@pytest.mark.parametrize("label", ADMIN_ONLY_LABELS)
def test_teacher_refused_admin_only_policy(label, staff_principal, admin_principal):
    assert not staff_principal.can_open(label)
    assert admin_principal.can_open(label)


@pytest.mark.parametrize("label", STAFF_LABELS)
def test_teacher_allowed_staff_reports_policy(label, staff_principal):
    assert staff_principal.can_open(label)


@pytest.mark.parametrize("label", ADMIN_ONLY_LABELS)
def test_cli_teacher_refused_admin_only(label, staff_auth, staff_principal, scripted_input):
    out = _run_submenu(label, staff_auth, scripted_input)
    assert staff_principal.denied_message(label) in out
    assert CLI_HEADERS[label] not in out


@pytest.mark.parametrize("label", STAFF_LABELS)
def test_cli_teacher_opens_staff_reports(label, staff_auth, staff_principal, scripted_input):
    out = _run_submenu(label, staff_auth, scripted_input)
    assert staff_principal.denied_message(label) not in out
    for bad in CLI_FAILURES:
        assert bad not in out, f"{bad!r} in {label} output:\n{out[-2000:]}"
    assert CLI_HEADERS[label] in out


@pytest.mark.gui
@pytest.mark.parametrize("label", ADMIN_ONLY_LABELS)
def test_gui_teacher_refused_admin_only(label, primary_gui, staff_principal, toplevels):
    primary_gui.principal = staff_principal
    new = _open(primary_gui, label, toplevels)
    assert new == []
    assert staff_principal.denied_message(label) in _frame_text(primary_gui.content_frame)


@pytest.mark.gui
@pytest.mark.parametrize("label", STAFF_LABELS)
def test_gui_teacher_opens_staff_reports(label, primary_gui, staff_principal, toplevels):
    primary_gui.principal = staff_principal
    new = _open(primary_gui, label, toplevels)
    assert staff_principal.denied_message(label) not in _frame_text(primary_gui.content_frame)
    assert new == [], f"{label} opened a window: {[w.title() for w in new]}"
    assert GUI_PAGE_TITLES[label] in _frame_text(primary_gui.content_frame).splitlines()
