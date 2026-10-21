"""Operational trace allowlist: no prompts, SQL literals, results or credentials."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import re
from time import perf_counter
from uuid import uuid4

import sqlglot
from sqlglot import exp

PROMPT_VERSION = 'retail-analyst-v4-terminal-plans'


def query_fingerprint(sql, dialect):
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
        # Strip literals before hashing; neither sensitive values nor identifiers are exported.
        tree = tree.transform(lambda node: exp.Placeholder() if isinstance(node, exp.Literal) else node)
        return hashlib.sha256(tree.sql().encode()).hexdigest()[:20]
    except Exception:
        return 'unparseable'


def model_identifier(model):
    name = getattr(model, 'model_name', None)
    if not isinstance(name, str):
        return type(model).__name__
    if not re.fullmatch(r'[\w./:-]{1,100}', name) or re.search(r'gsk_|sk-|gh[pou]_|[A-Za-z0-9]{40}', name):
        return '[redacted]'
    return name


@dataclass
class Trace:
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
        self.stages.append({'stage': name, 'elapsed_ms': round((perf_counter()-self._started)*1000, 2)})

    def usage(self, reply):
        usage = getattr(reply, 'usage_metadata', None)
        if not isinstance(usage, dict):
            return
        values = {key: usage[key] for key in ('input_tokens', 'output_tokens', 'total_tokens')
                  if isinstance(usage.get(key), int) and 0 <= usage[key] <= 10000000}
        if len(values) == 3:
            self._complete_usage_calls += 1
        if values:
            self.tokens = self.tokens or {}
            for key, value in values.items():
                self.tokens[key] = self.tokens.get(key, 0) + value

    def export(self, outcome):
        return {'request_id': self.request_id, 'started_at': self.started_at,
                'prompt_version': PROMPT_VERSION, 'model': self.model,
                'outcome': outcome, 'duration_ms': round((perf_counter()-self._started)*1000, 2),
                'stages': self.stages, 'tool_calls': self.calls, 'model_calls': self.model_calls,
                'retries': self.retries, 'token_usage': self.tokens,
                'token_usage_complete': bool(self.model_calls) and self._complete_usage_calls == len(self.model_calls)}
