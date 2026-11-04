"""Construct request-scoped resources and close them on success or failure.

File: assistant/runtime.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from contextlib import contextmanager

import langchain_groq

from .budgets import RequestBudget
from .config import (
    DEFAULT_DATABASE,
    DEFAULT_OUTPUT_TOKENS,
    DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    AppConfig,
)
from .connections import open_engine
from .demo import TABLES, build_demo
from .deployment import enforce_deployment
from .execution import QueryService


@contextmanager
def application_session(config: AppConfig):
    """Yield request-scoped database and model resources, disposing the engine on exit.

    Args:
        config: Application configuration containing connection and deployment settings.

    Yields:
        tuple: Controlled query service and configured model; engine disposal is guaranteed.

    Raises:
        PermissionError: If deployment policy or hosted view authorization fails.
        BudgetExceeded: If setup exceeds the shared request deadline.
        SQLAlchemyError: If connection or schema discovery fails.
        Exception: Model-construction and caller errors propagate after engine disposal.
    """
    budget = RequestBudget()
    enforce_deployment(config)
    demo = config.kind == "sqlite" and config.settings.get("path") == str(DEFAULT_DATABASE)
    if demo:
        build_demo(DEFAULT_DATABASE)
    budget.remaining_seconds()
    engine = open_engine(config.kind, **config.settings)
    try:
        if config.hosted:
            from sqlalchemy import inspect

            if not set(config.approved_columns).issubset(
                inspect(engine).get_view_names(schema=config.schema)
            ):
                raise PermissionError("Hosted mode permits operator-approved views only.")
        budget.remaining_seconds()
        service = QueryService(
            engine,
            schema=config.schema,
            budget=budget,
            tables=list(config.approved_columns)
            if config.approved_columns
            else TABLES
            if demo
            else None,
            **({"approved_columns": config.approved_columns} if config.approved_columns else {}),
        )
        service.request_budget = budget
        service.hosted = config.hosted
        service.retail = demo
        model = langchain_groq.ChatGroq(
            api_key=config.api_key,
            model=config.model_name,
            temperature=0,
            streaming=False,
            timeout=DEFAULT_PROVIDER_TIMEOUT_SECONDS,
            max_retries=0,
            max_tokens=DEFAULT_OUTPUT_TOKENS,
            **({"reasoning_effort": "none"} if config.model_name.startswith("qwen/") else {}),
        )
        budget.remaining_seconds()
        yield service, model
    finally:
        engine.dispose()
