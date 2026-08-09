"""Archive extraction and path containment (task 20).

Backup/restore now routes zip extraction through safe_extract instead of
ZipFile.extractall / .extract, which are vulnerable to zip-slip.
"""

from __future__ import annotations

import os
import zipfile

import pytest

from education_system.platform.kernel.core.safe_paths import (
    PathSecurityError,
    resolve_under,
    safe_extract,
)

pytestmark = pytest.mark.security


def test_safe_extract_rejects_traversal_member(tmp_path):
    mal = tmp_path / "mal.zip"
    with zipfile.ZipFile(mal, "w") as z:
        z.writestr("../escape.txt", "pwned")
    dest = tmp_path / "out"
    with pytest.raises(PathSecurityError):
        safe_extract(zipfile.ZipFile(mal), dest)
    assert not (tmp_path / "escape.txt").exists()


def test_safe_extract_writes_contained_member(tmp_path):
    ok = tmp_path / "ok.zip"
    with zipfile.ZipFile(ok, "w") as z:
        z.writestr("database/student_records.db", "data")
    dest = tmp_path / "out"
    written = safe_extract(
        zipfile.ZipFile(ok), dest, members=["database/student_records.db"]
    )
    assert written and os.path.exists(written[0])
    assert os.path.abspath(str(written[0])).startswith(os.path.abspath(str(dest)))


def test_resolve_under_blocks_escape(tmp_path):
    with pytest.raises(PathSecurityError):
        resolve_under(tmp_path, "../../etc/passwd")
    # A normal relative path resolves inside the root.
    inside = resolve_under(tmp_path, "sub/file.txt")
    assert os.path.abspath(str(inside)).startswith(os.path.abspath(str(tmp_path)))
