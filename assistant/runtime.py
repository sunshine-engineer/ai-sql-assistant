"""Construct request-scoped resources and close them on success or failure."""
from contextlib import contextmanager

import langchain_groq

from .config import AppConfig
from .connections import open_engine
from .execution import QueryService


@contextmanager
def application_session(config: AppConfig):
    engine = open_engine(config.kind, **config.settings)
    try:
        service = QueryService(engine, schema=config.schema)
        model = langchain_groq.ChatGroq(
            api_key=config.api_key, model=config.model_name, temperature=0,
            streaming=False, timeout=20, max_retries=0, max_tokens=1500,
        )
        yield service, model
    finally:
        engine.dispose()
