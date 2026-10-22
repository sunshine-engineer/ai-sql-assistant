"""Trusted OIDC principal -> operator-managed, per-user approved view projection.

File: assistant/access.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import math
import re
import time

from sqlglot import exp

from .config import AppConfig
from .validation import UnsafeSQL


def hosted_config(principal, grants, api_key, model_name):
    """Build a scoped connection configuration from a verified OIDC identity.

    Args:
        principal: Trusted identity claims supplied by the authenticated session.
        grants: Operator-managed mapping from verified email addresses to approved database access.
        api_key: Provider credential supplied at runtime; never include it in logs.
        model_name: Provider model identifier selected for this request.

    Returns:
        AppConfig: Scoped settings for an authenticated hosted session.

    Raises:
        PermissionError: If identity, expiry, grant, projection, TLS, or provider consent is invalid.
    """
    if not principal.get("is_logged_in") or principal.get("email_verified") is not True:
        raise PermissionError("A verified authenticated identity is required.")
    expires = principal.get("exp")
    if type(expires) not in (int, float) or not math.isfinite(expires) or expires <= time.time():
        raise PermissionError("The identity token has expired; sign in again.")
    email = principal.get("email")
    grant = grants.get(email) if isinstance(email, str) else None
    if not isinstance(grant, dict):
        raise PermissionError("No database grant for this identity.")
    columns = grant.get("columns")
    settings = grant.get("connection")
    if (
        not isinstance(columns, dict)
        or not columns
        or any(
            not isinstance(v, list) or not v or any(not isinstance(c, str) for c in v)
            for v in columns.values()
        )
        or not isinstance(settings, dict)
        or not settings.get("tls_ca")
        or grant.get("kind") not in ("postgres", "mysql")
        or grant.get("provider_approved") is not True
    ):
        raise PermissionError(
            "An approved view projection, verified TLS and provider consent are required."
        )
    return AppConfig(
        grant["kind"],
        dict(settings),
        schema=grant.get("schema"),
        api_key=api_key,
        model_name=model_name,
        approved_columns=columns,
        principal=email,
        hosted=True,
    )


def validate_projection(tree, catalog, approved):
    """Reject references outside the operator-approved view columns.

    Args:
        tree: Parsed SQLGlot expression to inspect.
        catalog: Mapping of table names to column metadata.
        approved: Mapping of approved view names to permitted column names.

    Raises:
        UnsafeSQL: If a query bypasses the approved projection or uses unsupported subqueries.
    """
    if len(list(tree.find_all(exp.Select))) > 1 or any(
        isinstance(n, exp.Subquery) for n in tree.walk()
    ):
        raise UnsafeSQL("Restricted view queries do not support subqueries.")
    tables = list(tree.find_all(exp.Table))
    aliases = {t.alias_or_name: t.name for t in tables}
    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            raise UnsafeSQL("Select explicit approved columns.")
    for column in tree.find_all(exp.Column):
        if column.table:
            table = aliases.get(column.table)
            if table not in approved or column.name not in approved[table]:
                raise UnsafeSQL("Column is outside the user projection.")
        else:
            candidates = [
                t.name
                for t in tables
                if any(c["name"] == column.name for c in catalog.get(t.name, []))
            ]
            if not candidates or any(column.name not in approved.get(t, []) for t in candidates):
                raise UnsafeSQL("Column is outside the user projection.")


def provider_question(text):
    # Additional hygiene, not a PII classifier. Approved DB views are the primary
    # boundary; no arbitrary real schemas or private columns go to the provider.
    """Redact recognizable email addresses and credential tokens before provider submission.

    Args:
        text: Question text before limited email/token hygiene checks.

    Returns:
        str: Question text with recognizable email addresses and tokens redacted.
    """
    text = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email redacted]", text, flags=re.I
    )
    return re.sub(r"\b(?:gsk_|sk-)[A-Za-z0-9_-]+", "[credential redacted]", text)
