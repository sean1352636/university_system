"""Guard the placeholder contract between trip-management code and locales.

A translated string whose ``{placeholder}`` names don't match the keyword
arguments the call site passes raises ``KeyError`` inside ``str.format``.
In this package those calls happen *inside* ``safe_db_operation``, so the
KeyError rolled the surrounding transaction back: a trip reported as
"created successfully" was never written, and report generation died with
``Error generating report: 'type'``.

This test fails on any locale string that the code cannot format.
"""

from __future__ import annotations

import ast
import glob
import json
import os
import re

import pytest

KEY_PREFIX = "mobility.trip_management"
SRC_ROOT = "src/education_system"
LOCALE_GLOBS = (
    "var/data/university/locales/*/campus_transport.json",
    "var/data/university/locales/*/campus/campus_transport.json",
)
GET_TEXT_ALIASES = {"get_text", "_", "t"}

# {name}, {name!r}, {name:.2f} — the name is what has to match a kwarg.
PLACEHOLDER = re.compile(r"\{(\w*)((?:![rsa])?(?::[^{}]*)?)\}")


def _repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    while here != "/" and not os.path.isdir(os.path.join(here, ".git")):
        here = os.path.dirname(here)
    return here


def _flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from _flatten(value, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix, obj


def _call_sites(root: str):
    """Yield (key, supplied_kwargs_or_None, path, lineno) for every get_text().

    ``supplied_kwargs`` is ``None`` when the result is used without
    ``.format()`` — such a string must carry no placeholders at all.
    """
    for path in glob.glob(os.path.join(root, SRC_ROOT, "**", "*.py"), recursive=True):
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        if KEY_PREFIX not in source:
            continue
        tree = ast.parse(source)

        formatted = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "format"):
                formatted[id(node.func.value)] = {
                    kw.arg for kw in node.keywords if kw.arg
                }

        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in GET_TEXT_ALIASES
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and node.args[0].value.startswith(KEY_PREFIX)):
                yield (node.args[0].value,
                       formatted.get(id(node)),
                       os.path.relpath(path, root),
                       node.lineno)


def _locale_files(root: str):
    files = []
    for pattern in LOCALE_GLOBS:
        files.extend(sorted(glob.glob(os.path.join(root, pattern))))
    return files


@pytest.mark.unit
def test_trip_management_locale_placeholders_match_call_sites():
    root = _repo_root()
    locale_files = _locale_files(root)
    if not locale_files:
        pytest.skip("no campus_transport locale files installed")

    sites = list(_call_sites(root))
    assert sites, "found no trip-management get_text call sites to check"

    failures = []
    for locale_file in locale_files:
        with open(locale_file, encoding="utf-8") as handle:
            strings = {
                key: value
                for key, value in _flatten(json.load(handle))
                if isinstance(value, str)
            }

        for key, supplied, path, lineno in sites:
            translated = strings.get(key)
            if translated is None:
                continue
            names = {m[0] for m in PLACEHOLDER.findall(translated) if m[0]}
            if not names:
                continue
            if supplied is None:
                failures.append(
                    f"{os.path.basename(locale_file)}: {key!r} has "
                    f"placeholders {sorted(names)} but {path}:{lineno} reads it "
                    f"without .format()"
                )
            elif not names <= supplied:
                failures.append(
                    f"{os.path.basename(locale_file)}: {key!r} needs "
                    f"{sorted(names - supplied)} which {path}:{lineno} does not "
                    f"supply (supplies {sorted(supplied)})"
                )

    assert not failures, "\n".join(failures)
