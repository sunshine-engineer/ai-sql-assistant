"""Shared real SQLite retail fixture; no live model or external database needed.

File: tests/conftest.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import pytest

from assistant.connections import open_engine
from assistant.demo import TABLES, build_demo
from assistant.execution import QueryService


@pytest.fixture
def retail(tmp_path):
    """Yield a real, temporary retail QueryService and dispose its engine afterward.

    Args:
        tmp_path: Pytest-managed temporary directory.

    Yields:
        Temporary test resource, disposed when the fixture scope exits.
    """
    path = build_demo(tmp_path / "retail.db")
    engine = open_engine("sqlite", path=path)
    service = QueryService(engine, tables=TABLES)
    service.retail = True
    yield service
    engine.dispose()
