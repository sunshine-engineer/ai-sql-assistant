"""Construct request-scoped resources and close them on success or failure."""
from contextlib import contextmanager

import langchain_groq

from .config import AppConfig, DEFAULT_DATABASE
from .demo import build_demo, TABLES
from .connections import open_engine
from .execution import QueryService
from .deployment import enforce_deployment
from .budgets import RequestBudget


@contextmanager
def application_session(config: AppConfig):
    budget = RequestBudget()
    enforce_deployment(config)
    demo = config.kind == 'sqlite' and config.settings.get('path') == str(DEFAULT_DATABASE)
    if demo:
        build_demo(DEFAULT_DATABASE)
    budget.remaining_seconds()
    engine = open_engine(config.kind, **config.settings)
    try:
        if config.hosted:
            from sqlalchemy import inspect
            if not set(config.approved_columns).issubset(inspect(engine).get_view_names(schema=config.schema)):
                raise PermissionError('Hosted mode permits operator-approved views only.')
        budget.remaining_seconds()
        service = QueryService(engine, schema=config.schema, budget=budget,
                               tables=list(config.approved_columns) if config.approved_columns else TABLES if demo else None,
                               **({'approved_columns':config.approved_columns} if config.approved_columns else {}))
        service.request_budget = budget
        service.hosted = config.hosted
        service.retail = demo
        model = langchain_groq.ChatGroq(
            api_key=config.api_key, model=config.model_name, temperature=0,
            streaming=False, timeout=20, max_retries=0, max_tokens=1500,
            **({'reasoning_effort':'none'} if config.model_name.startswith('qwen/') else {}),
        )
        budget.remaining_seconds()
        yield service, model
    finally:
        engine.dispose()
