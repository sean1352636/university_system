"""Tests for university_system.modules.shared.utils.templates."""
import json

import pytest

from education_system.post_18.university_system.modules.shared.utils import templates


@pytest.fixture(autouse=True)
def restore_templates():
    """Snapshot DEFAULT_TEMPLATES so tests don't leak global mutations."""
    snapshot = json.loads(json.dumps(templates.DEFAULT_TEMPLATES))
    yield
    templates.DEFAULT_TEMPLATES.clear()
    templates.DEFAULT_TEMPLATES.update(snapshot)


class TestBasicAccessors:
    def test_get_default_templates_returns_dict(self):
        t = templates.get_default_templates()
        assert "email" in t
        assert "report" in t

    def test_load_template_existing(self):
        assert templates.load_template("email", "welcome") == "Welcome to the university system!"

    def test_load_template_missing_returns_empty(self):
        assert templates.load_template("nope", "x") == ""
        assert templates.load_template("email", "nope") == ""

    def test_list_templates(self):
        names = templates.list_templates()
        assert "email" in names
        assert "report" in names

    def test_template_exists(self):
        assert templates.template_exists("email") is True
        assert templates.template_exists("nope_xyz") is False

    def test_get_template_categories(self):
        cats = templates.get_template_categories()
        assert "email" in cats


class TestFormatTemplate:
    def test_formats_with_vars(self):
        assert templates.format_template("hi {name}", name="alice") == "hi alice"

    def test_missing_key_returns_original(self):
        result = templates.format_template("hi {name}")
        # Missing-key path returns the original template
        assert result == "hi {name}"


class TestCRUD:
    def test_create_template(self):
        templates.create_template("custom", "value")
        assert templates.template_exists("custom")

    def test_update_template_existing(self):
        templates.create_template("x", "v1")
        assert templates.update_template("x", "v2") is True
        assert templates.DEFAULT_TEMPLATES["x"] == "v2"

    def test_update_template_missing_returns_false(self):
        assert templates.update_template("nope_x", "v") is False

    def test_delete_template_existing(self):
        templates.create_template("x", "v")
        assert templates.delete_template("x") is True
        assert not templates.template_exists("x")

    def test_delete_template_missing_returns_false(self):
        assert templates.delete_template("nope_x") is False


class TestRenderTemplate:
    def test_nested_render(self):
        out = templates.render_template("email.welcome")
        assert "Welcome" in out

    def test_render_with_vars(self):
        templates.create_template("greeting", "hi {name}")
        assert templates.render_template("greeting", {"name": "alice"}) == "hi alice"

    def test_missing_template_returns_error_string(self):
        out = templates.render_template("nope_xyz")
        # Falls back to a translated error key; we just assert it returns a string
        assert isinstance(out, str)


class TestInitializeAnalytics:
    def test_adds_analytics_section(self):
        templates.initialize_analytics_templates()
        assert "analytics" in templates.DEFAULT_TEMPLATES
        assert "report_header" in templates.DEFAULT_TEMPLATES["analytics"]


class TestEnsureTemplatesDirectory:
    def test_returns_path(self):
        result = templates.ensure_templates_directory()
        assert isinstance(result, str)


class TestImportTemplatesFromPath:
    def test_no_path_returns_none(self):
        assert templates.import_templates_from_path() is None

    def test_missing_file_returns_none(self, tmp_path):
        assert templates.import_templates_from_path(source_path=str(tmp_path / "nope.json")) is None

    def test_imports_dict(self, tmp_path):
        f = tmp_path / "t.json"
        f.write_text(json.dumps({"new_cat": {"k": "v"}}))
        result = templates.import_templates_from_path(source_path=str(f))
        assert result == {"new_cat": {"k": "v"}}
        assert templates.template_exists("new_cat")

    def test_invalid_json_returns_none(self, tmp_path):
        f = tmp_path / "t.json"
        f.write_text("not json{")
        assert templates.import_templates_from_path(source_path=str(f)) is None

    def test_imports_list_with_named_templates(self, tmp_path):
        f = tmp_path / "t.json"
        f.write_text(json.dumps([{"name": "from_list", "body": "x"}]))
        templates.import_templates_from_path(source_path=str(f))
        assert templates.template_exists("from_list")
