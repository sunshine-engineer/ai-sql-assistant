"""Operational trace allowlist: no prompts, SQL literals, results or credentials.

File: assistant/tracing.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4

import sqlglot
from sqlglot import exp

PROMPT_VERSION = "retail-analyst-v4-terminal-plans"


def query_fingerprint(sql, dialect):
    """Hash normalized SQL after stripping literals without exporting SQL text.

    Args:
        sql: Untrusted SQL text to validate before any execution.
        dialect: SQLGlot dialect name: sqlite, postgres, or mysql.

    Returns:
        str: Truncated digest or unparseable sentinel.
    """
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
        # Strip literals before hashing; neither sensitive values nor identifiers are exported.
        tree = tree.transform(
            lambda node: exp.Placeholder() if isinstance(node, exp.Literal) else node
        )
        return hashlib.sha256(tree.sql().encode()).hexdigest()[:20]
    except Exception:
        return "unparseable"


def model_identifier(model):
    """Return an allowlisted model identifier or a redacted placeholder.

    Args:
        model: Model adapter supporting invoke and, for workflows, tool binding.

    Returns:
        str: Safe model identifier or redacted placeholder.
    """
    name = getattr(model, "model_name", None)
    if not isinstance(name, str):
        return type(model).__name__
    if not re.fullmatch(r"[\w./:-]{1,100}", name) or re.search(
        r"gsk_|sk-|gh[pou]_|[A-Za-z0-9]{40}", name
    ):
        return "[redacted]"
    return name


@dataclass
class Trace:
    """Collect allowlisted request stages, calls, timings, and provider token usage.

    Attributes:
        model: Sanitized model identifier.
        request_id: Opaque request UUID.
        started_at: UTC start timestamp.
        stages: Stage names and elapsed timings.
        calls: Allowlisted tool-call outcomes.
        model_calls: Allowlisted provider-call outcomes.
        tokens: Accumulated provider usage when reported.
        retries: SQL repair count.
        _complete_usage_calls: Calls reporting all token usage fields.
        _started: Initial performance-counter value.
    """

    model: str
    request_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stages: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    model_calls: list = field(default_factory=list)
    tokens: dict | None = None
    retries: int = 0
    _complete_usage_calls: int = field(default=0, repr=False)
    _started: float = field(default_factory=perf_counter, repr=False)

    def stage(self, name):
        """Record a named workflow stage and elapsed time.

        Args:
            name: Instance name, stage name, or other identifier required by the caller.
        """
        self.stages.append(
            {"stage": name, "elapsed_ms": round((perf_counter() - self._started) * 1000, 2)}
        )

    def usage(self, reply):
        """Accumulate valid provider token counts and track complete usage reporting.

        Args:
            reply: Provider reply with optional usage_metadata.
        """
        usage = getattr(reply, "usage_metadata", None)
        if not isinstance(usage, dict):
            return
        values = {
            key: usage[key]
            for key in ("input_tokens", "output_tokens", "total_tokens")
            if isinstance(usage.get(key), int) and 0 <= usage[key] <= 10000000
        }
        if len(values) == 3:
            self._complete_usage_calls += 1
        if values:
            self.tokens = self.tokens or {}
            for key, value in values.items():
                self.tokens[key] = self.tokens.get(key, 0) + value

    def export(self, outcome):
        """Export allowlisted request evidence with the supplied terminal outcome.

        Args:
            outcome: Sanitized terminal workflow outcome.

        Returns:
            dict: Sanitized operational metadata.
        """
        return {
            "request_id": self.request_id,
            "started_at": self.started_at,
            "prompt_version": PROMPT_VERSION,
            "model": self.model,
            "outcome": outcome,
            "duration_ms": round((perf_counter() - self._started) * 1000, 2),
            "stages": self.stages,
            "tool_calls": self.calls,
            "model_calls": self.model_calls,
            "retries": self.retries,
            "token_usage": self.tokens,
            "token_usage_complete": bool(self.model_calls)
            and self._complete_usage_calls == len(self.model_calls),
        }
