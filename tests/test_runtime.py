"""Resource lifecycle contracts independent of Streamlit and live providers.

File: tests/test_runtime.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from unittest.mock import Mock

import pytest

from assistant.config import DEFAULT_DATABASE, AppConfig
from assistant.runtime import application_session


def test_config_redacts_credentials():
    """Verify config redacts credentials."""
    config = AppConfig("postgres", {"password": "db-secret"}, api_key="api-secret")
    assert "db-secret" not in repr(config)
    assert "api-secret" not in repr(config)
    assert config.database_identity == ["postgres", {"password": "db-secret"}, None]


def test_config_requires_complete_connection_and_key():
    """Verify config requires complete connection and key."""
    config = AppConfig("sqlite", {"path": str(DEFAULT_DATABASE)})
    assert not config.ready
    config.api_key = "offline-key"
    assert config.ready
    config.settings["path"] = ""
    assert not config.ready


@pytest.mark.parametrize("failure", [None, "schema", "model", "request"])
def test_resources_close_on_success_and_failure(monkeypatch, failure):
    """Verify resources close on success and failure.

    Args:
        monkeypatch: Pytest helper for reversible runtime substitutions.
        failure: Parametrized failure for this regression case.
    """
    engine, service, model = Mock(), Mock(), Mock()
    monkeypatch.setattr("assistant.runtime.open_engine", lambda *a, **kw: engine)
    service_factory = Mock(return_value=service)
    model_factory = Mock(return_value=model)
    monkeypatch.setattr("assistant.runtime.QueryService", service_factory)
    monkeypatch.setattr("langchain_groq.ChatGroq", model_factory)
    config = AppConfig("sqlite", {"path": str(DEFAULT_DATABASE)}, api_key="offline-key")
    if failure == "schema":
        service_factory.side_effect = RuntimeError("schema failure")
    elif failure == "model":
        model_factory.side_effect = RuntimeError("model failure")

    def request():
        """Exercise a request-scoped application session for cleanup assertions."""
        with application_session(config) as resources:
            assert resources == (service, model)
            engine.dispose.assert_not_called()
            if failure == "request":
                raise RuntimeError("request failure")

    if failure:
        with pytest.raises(RuntimeError):
            request()
    else:
        request()
    engine.dispose.assert_called_once()
