"""Tests for scripts.generate_openapi_spec."""
import json
from unittest.mock import patch

from education_system.systems.university.scripts import generate_openapi_spec as script


class TestModuleSurface:
    def test_callables_and_builders(self):
        for name in ("_build_university", "_build_college", "_build_secondary",
                     "_build_primary", "_build_unified", "_write_spec",
                     "_run_one", "main"):
            assert callable(getattr(script, name))

    def test_builders_registry_complete(self):
        assert set(script.BUILDERS.keys()) == {"university", "college", "secondary", "primary", "unified"}
        for _, (builder, filename) in script.BUILDERS.items():
            assert callable(builder)
            assert filename.endswith(".json")


class TestWriteSpec:
    def test_creates_file_and_returns_true(self, tmp_path):
        out = tmp_path / "sub" / "spec.json"
        spec = {"openapi": "3.0.3", "info": {"title": "t"}}
        assert script._write_spec(spec, out) is True
        assert out.exists()
        # Trailing newline
        assert out.read_text().endswith("\n")
        # Sorted, valid JSON
        loaded = json.loads(out.read_text())
        assert loaded == spec

    def test_no_change_when_identical(self, tmp_path):
        out = tmp_path / "spec.json"
        spec = {"a": 1, "b": 2}
        script._write_spec(spec, out)
        # Second write with same content -> False (no change)
        assert script._write_spec(spec, out) is False

    def test_detects_change(self, tmp_path):
        out = tmp_path / "spec.json"
        script._write_spec({"a": 1}, out)
        assert script._write_spec({"a": 2}, out) is True


class TestRunOne:
    def test_returns_change_flag_from_builder(self, tmp_path):
        spec = {"openapi": "3.0.3", "info": {"title": "x"}, "paths": {"/foo": {"get": {}}}}
        with patch.object(script, "DOCS_API_DIR", tmp_path), \
             patch.object(script, "REPO_ROOT", tmp_path), \
             patch.dict(script.BUILDERS,
                        {"university": (lambda: spec, "openapi-university.json")}):
            changed, count = script._run_one("university")
        assert changed is True
        assert count == 1

    def test_builder_exception_returns_false_zero(self, tmp_path):
        def boom():
            raise RuntimeError("nope")
        with patch.object(script, "DOCS_API_DIR", tmp_path), \
             patch.object(script, "REPO_ROOT", tmp_path), \
             patch.dict(script.BUILDERS,
                        {"university": (boom, "openapi-university.json")}):
            changed, count = script._run_one("university")
        assert changed is False
        assert count == 0
