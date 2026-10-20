"""Resource lifecycle contracts independent of Streamlit and live providers."""
from unittest.mock import Mock

import pytest

from assistant.config import AppConfig, DEFAULT_DATABASE
from assistant.runtime import application_session


def test_config_redacts_credentials():
    config = AppConfig('postgres', {'password': 'db-secret'}, api_key='api-secret')
    assert 'db-secret' not in repr(config)
    assert 'api-secret' not in repr(config)
    assert config.database_identity == ['postgres', {'password': 'db-secret'}, None]


def test_config_requires_complete_connection_and_key():
    config = AppConfig('sqlite', {'path': str(DEFAULT_DATABASE)})
    assert not config.ready
    config.api_key = 'offline-key'
    assert config.ready
    config.settings['path'] = ''
    assert not config.ready


@pytest.mark.parametrize('failure', [None, 'schema', 'model', 'request'])
def test_resources_close_on_success_and_failure(monkeypatch, failure):
    engine, service, model = Mock(), Mock(), Mock()
    monkeypatch.setattr('assistant.runtime.open_engine', lambda *a, **kw: engine)
    service_factory = Mock(return_value=service)
    model_factory = Mock(return_value=model)
    monkeypatch.setattr('assistant.runtime.QueryService', service_factory)
    monkeypatch.setattr('langchain_groq.ChatGroq', model_factory)
    config = AppConfig('sqlite', {'path': str(DEFAULT_DATABASE)}, api_key='offline-key')
    if failure == 'schema':
        service_factory.side_effect = RuntimeError('schema failure')
    elif failure == 'model':
        model_factory.side_effect = RuntimeError('model failure')

    def request():
        with application_session(config) as resources:
            assert resources == (service, model)
            engine.dispose.assert_not_called()
            if failure == 'request':
                raise RuntimeError('request failure')

    if failure:
        with pytest.raises(RuntimeError):
            request()
    else:
        request()
    engine.dispose.assert_called_once()
