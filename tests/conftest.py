"""Shared real SQLite retail fixture; no live model or external database needed."""
import pytest
from assistant.connections import open_engine
from assistant.demo import build_demo, TABLES
from assistant.execution import QueryService


@pytest.fixture
def retail(tmp_path):
    path = build_demo(tmp_path / 'retail.db')
    engine = open_engine('sqlite', path=path)
    service = QueryService(engine, tables=TABLES)
    service.retail = True
    yield service
    engine.dispose()
