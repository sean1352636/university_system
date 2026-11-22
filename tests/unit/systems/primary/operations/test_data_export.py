"""Bulk Data Export (systems.primary.domain.operations.reporting.data_export.data_export).

The button tests check every preset writes its files; these check preset
CRUD, the per-dataset results, manifest, archive, job history and the
overview figures. Everything is written under tmp_path.
"""

from __future__ import annotations

import csv
import json
import zipfile

import pytest

from education_system.systems.primary.domain.learners.pupils import pupils as P
from education_system.systems.primary.domain.operations.reporting.custom_export import (
    custom_export as CE,
)
from education_system.systems.primary.domain.operations.reporting.data_export import (
    data_export as DE,
)
from education_system.systems.primary.domain.staff import staff as ST

BUILTIN_KEYS = ["full_backup", "pupils_core", "academics", "assessment", "pastoral",
                "finance", "staff"]


def _staff(n=2):
    return [ST.create_staff({"first_name": f"S{i}", "last_name": "Teacher"}) for i in range(n)]


def _pupils(n=3):
    return [P.create_pupil({"first_name": f"P{i}", "last_name": "Pupil", "year_group": "2",
                            "date_of_birth": "2019-01-01"}) for i in range(n)]


def _preset(key="mine", name="My preset", datasets=("pupils", "staff"), **extra):
    return DE.create_preset({"key": key, "name": name, "datasets": list(datasets), **extra})


def _boom(*_a, **_k):
    raise RuntimeError("dataset offline")


# ── presets ──

def test_builtin_presets_listed_first_then_user_presets_by_name():
    _preset("zz", "beta")
    _preset("aa", "Alpha")
    presets = DE.list_presets()
    assert [p.key for p in presets] == BUILTIN_KEYS + ["aa", "zz"]
    assert all(p.is_builtin and p.preset_id is None for p in presets[:7])
    full = presets[0]
    assert full.datasets == sorted(CE.DATASETS().keys())
    assert DE.get_preset("staff").datasets == ["staff"]


def test_create_preset_stores_and_dedupes_datasets():
    p = DE.create_preset({"key": " term-1_end ", "name": "  End of term ",
                          "description": " d ", "created_by": " admin3 ",
                          "datasets": ["staff", "pupils", "staff"]})
    assert (p.key, p.name, p.description, p.datasets, p.created_by, p.is_builtin) == \
        ("term-1_end", "End of term", "d", ["staff", "pupils"], "admin3", False)
    assert DE.get_preset(p.preset_id) == p
    assert DE.get_preset("term-1_end") == p
    assert DE.get_preset("nothing") is None
    assert DE.get_preset(999) is None


@pytest.mark.parametrize("payload,message", [
    ({"key": "", "name": "n", "datasets": ["staff"]}, "Preset key is required"),
    ({"key": "has space", "name": "n", "datasets": ["staff"]},
     "only letters, digits, '_' or '-'"),
    ({"key": "finance", "name": "n", "datasets": ["staff"]}, "'finance' is a built-in preset"),
    ({"key": "k", "name": " ", "datasets": ["staff"]}, "Name is required"),
    ({"key": "k", "name": "n", "datasets": []}, "Pick at least one dataset"),
    ({"key": "k", "name": "n", "datasets": ["staff", "unicorns"]},
     "Unknown dataset\\(s\\): unicorns"),
])
def test_create_preset_validation(payload, message):
    with pytest.raises(DE.ValidationError, match=message):
        DE.create_preset(payload)


def test_create_preset_duplicate_key():
    _preset("dup")
    with pytest.raises(DE.ValidationError, match="A preset with key 'dup' already exists"):
        _preset("dup", "Other")


def test_update_preset():
    p = _preset("orig", datasets=["pupils"])
    out = DE.update_preset(p.preset_id, {"name": "Renamed", "datasets": ["staff", "send"]})
    assert (out.key, out.name, out.datasets) == ("orig", "Renamed", ["staff", "send"])
    moved = DE.update_preset(p.preset_id, {"key": "new-key"})
    assert moved.key == "new-key" and DE.get_preset("orig") is None
    _preset("taken")
    with pytest.raises(DE.ValidationError, match="A preset with key 'taken' already exists"):
        DE.update_preset(p.preset_id, {"key": "taken"})
    with pytest.raises(DE.ValidationError, match="is a built-in preset"):
        DE.update_preset(p.preset_id, {"key": "staff"})
    with pytest.raises(DE.ValidationError, match="Name is required"):
        DE.update_preset(p.preset_id, {"name": ""})
    with pytest.raises(DE.ValidationError, match="No editable preset #404"):
        DE.update_preset(404, {"name": "x"})


def test_delete_preset():
    p = _preset()
    assert DE.delete_preset(p.preset_id) is True
    assert DE.delete_preset(p.preset_id) is False
    assert DE.get_preset("mine") is None


# ── run_export ──

def test_run_export_writes_files_manifest_and_job(tmp_path):
    staff = _staff(2)
    _pupils(3)
    p = _preset(datasets=("pupils", "staff"))
    out = tmp_path / "export"
    job = DE.run_export("mine", out, run_by=" admin3 ", notes=" termly ")
    assert (job.preset_key, job.preset_name, job.fmt, job.status) == \
        ("mine", "My preset", "csv", "succeeded")
    assert (job.files_total, job.rows_total, job.zipped, job.archive_path) == (2, 5, False, None)
    assert (job.run_by, job.notes, job.output_dir) == ("admin3", "termly", str(out))
    assert job.finished_at and job.started_at <= job.finished_at
    by_key = {f.dataset_key: f for f in job.files}
    assert (by_key["pupils"].row_count, by_key["pupils"].label, by_key["pupils"].error) == \
        (3, "Pupils", None)
    assert by_key["staff"].file_path == str(out / "staff.csv")
    assert job.bytes_total == sum(f.bytes_written for f in job.files)
    with (out / "staff.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert sorted(r["Staff ID"] for r in rows) == sorted(s.staff_id for s in staff)

    manifest = json.loads((out / "_manifest.json").read_text(encoding="utf-8"))
    assert (manifest["job_id"], manifest["preset_key"], manifest["fmt"]) == \
        (job.job_id, "mine", "csv")
    assert manifest["files"] == [
        {"dataset": "pupils", "file": "pupils.csv", "rows": 3,
         "bytes": by_key["pupils"].bytes_written, "error": None},
        {"dataset": "staff", "file": "staff.csv", "rows": 2,
         "bytes": by_key["staff"].bytes_written, "error": None}]
    assert manifest["totals"] == {"rows": 5, "bytes": job.bytes_total}
    assert DE.get_job(job.job_id) == job
    assert p.preset_id is not None


@pytest.mark.parametrize("fmt,ext", [("markdown", "md"), ("JSON", "json"), ("tsv", "tsv")])
def test_run_export_format_sets_extension(tmp_path, fmt, ext):
    _staff(1)
    job = DE.run_export("staff", tmp_path / "out", fmt=fmt)
    assert job.files[0].file_path == str(tmp_path / "out" / f"staff.{ext}")
    assert job.fmt == fmt.lower() and job.rows_total == 1


def test_run_export_by_preset_id(tmp_path):
    p = _preset(datasets=["staff"])
    assert DE.run_export(p.preset_id, tmp_path / "o").preset_key == "mine"


def test_run_export_refusals(tmp_path):
    with pytest.raises(DE.ValidationError, match="No preset 'nope'"):
        DE.run_export("nope", tmp_path / "o")
    with pytest.raises(DE.ValidationError, match="Format must be one of"):
        DE.run_export("staff", tmp_path / "o", fmt="xlsx")
    assert DE.list_jobs() == []


def test_run_export_partial_and_failed(tmp_path, monkeypatch):
    _pupils(2)
    monkeypatch.setattr(CE.get_dataset("staff"), "list_fn", _boom)
    _preset(datasets=["pupils", "staff"])
    job = DE.run_export("mine", tmp_path / "partial")
    assert (job.status, job.files_total, job.rows_total) == ("partial", 2, 2)
    bad = next(f for f in job.files if f.dataset_key == "staff")
    assert (bad.error, bad.file_path, bad.row_count) == ("dataset offline", "", 0)
    manifest = json.loads((tmp_path / "partial" / "_manifest.json").read_text("utf-8"))
    assert {"dataset": "staff", "file": None, "rows": 0, "bytes": 0,
            "error": "dataset offline"} in manifest["files"]

    failed = DE.run_export("staff", tmp_path / "failed")
    assert (failed.status, failed.rows_total) == ("failed", 0)


def test_run_export_zip_contains_data_files_and_manifest(tmp_path):
    _staff(1)
    _pupils(1)
    _preset(datasets=["pupils", "staff"])
    out = tmp_path / "zipme"
    job = DE.run_export("mine", out, zip_output=True)
    assert job.zipped and job.status == "succeeded"
    assert job.archive_path.startswith(str(tmp_path / "export_mine_"))
    with zipfile.ZipFile(job.archive_path) as zf:
        names = set(zf.namelist())
    assert {"pupils.csv", "staff.csv"} <= names
    assert "_manifest.json" in names


# ── jobs ──

def test_list_jobs_filters_newest_first(tmp_path, monkeypatch):
    _staff(1)
    j1 = DE.run_export("staff", tmp_path / "a")
    j2 = DE.run_export("pupils_core", tmp_path / "b")
    monkeypatch.setattr(CE.get_dataset("staff"), "list_fn", _boom)
    j3 = DE.run_export("staff", tmp_path / "c")
    assert [j.job_id for j in DE.list_jobs()] == [j3.job_id, j2.job_id, j1.job_id]
    assert [j.job_id for j in DE.list_jobs(preset_key="staff")] == [j3.job_id, j1.job_id]
    assert [j.job_id for j in DE.list_jobs(status="failed")] == [j3.job_id]
    assert len(DE.list_jobs(limit=1)) == 1
    with pytest.raises(DE.ValidationError, match="Status must be one of"):
        DE.list_jobs(status="done")


def test_delete_job_keeps_or_removes_files(tmp_path):
    _staff(1)
    keep = DE.run_export("staff", tmp_path / "keep")
    assert DE.delete_job(keep.job_id) is True
    assert (tmp_path / "keep" / "staff.csv").exists()
    assert DE.get_job(keep.job_id) is None

    wipe = DE.run_export("staff", tmp_path / "wipe", zip_output=True)
    assert DE.delete_job(wipe.job_id, remove_files=True) is True
    assert not (tmp_path / "wipe").exists()
    assert not (tmp_path / wipe.archive_path).exists()
    assert DE.delete_job(wipe.job_id) is False


# ── overview ──

def test_overview_totals(tmp_path, monkeypatch):
    _staff(2)
    _preset("u1", "User one", datasets=["staff"])
    ok = DE.run_export("staff", tmp_path / "ok")
    monkeypatch.setattr(CE.get_dataset("staff"), "list_fn", _boom)
    bad = DE.run_export("staff", tmp_path / "bad")
    ov = DE.overview()
    assert (ov.total_jobs, ov.succeeded, ov.partial, ov.failed) == (2, 1, 0, 1)
    assert (ov.total_files_written, ov.total_rows_written) == (2, 2)
    assert ov.total_bytes_written == ok.bytes_total
    assert ov.last_job.job_id == bad.job_id
    assert (ov.builtin_preset_count, ov.user_preset_count) == (7, 1)


def test_overview_empty():
    ov = DE.overview()
    assert (ov.total_jobs, ov.succeeded, ov.total_rows_written, ov.last_job) == (0, 0, 0, None)


def test_available_datasets_match_custom_export():
    assert DE.available_datasets() == [(d.key, d.label) for d in CE.list_datasets()]
