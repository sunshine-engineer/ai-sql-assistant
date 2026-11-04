"""Verify relocated maintenance commands preserve legacy fixture behavior.

File: tests/test_maintenance.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from scripts.build_student import STUDENT_ROWS

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("command", [("sqlite.py",), ("-m", "scripts.build_student")])
def test_student_builder_compatibility_and_existing_table_protection(tmp_path, command):
    """Verify both commands produce identical rows and reject an existing fixture table.

    Args:
        tmp_path: Pytest-managed temporary output directory.
        command: Legacy script or relocated module invocation under test.
    """
    path = tmp_path / "student.db"
    result = subprocess.run(
        [sys.executable, *command, "--output", str(path)], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT * FROM STUDENT").fetchall() == list(STUDENT_ROWS)
    repeated = subprocess.run(
        [sys.executable, *command, "--output", str(path)], cwd=ROOT, capture_output=True, text=True
    )
    assert repeated.returncode != 0
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT * FROM STUDENT").fetchall() == list(STUDENT_ROWS)


def test_maintenance_imports_do_not_create_database(tmp_path):
    """Verify importing the legacy shim and maintenance modules creates no local fixture.

    Args:
        tmp_path: Empty working directory used to detect import-time file writes.
    """
    code = (
        "import runpy, sys; "
        f"sys.path.insert(0, {str(ROOT)!r}); "
        f"runpy.run_path({str(ROOT / 'sqlite.py')!r}, run_name='imported_shim'); "
        "import scripts.build_student, scripts.check_consistency"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())
