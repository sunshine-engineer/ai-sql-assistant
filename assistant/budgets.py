"""Conservative admission budgets; no provider retries or work after exhaustion."""
from dataclasses import dataclass, field
import json
import time
from groq import APIConnectionError


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class RequestBudget:
    seconds: float = 60
    tokens: int = 60000
    output_tokens: int = 1500
    clock: object = field(default=time.monotonic, repr=False)
    spent: int = 0
    _started: float = field(init=False, repr=False)

    def __post_init__(self):
        if self.seconds <= 0 or self.tokens <= 0 or self.output_tokens <= 0:
            raise ValueError('Budgets must be positive.')
        self._started = self.clock()

    def remaining_seconds(self):
        remaining = self.seconds - (self.clock() - self._started)
        if remaining <= 0:
            raise BudgetExceeded('time_budget')
        return remaining

    def admit(self, messages, tools):
        # UTF-8 bytes conservatively bound content tokens; reserve protocol/tool
        # overhead too. This is admission accounting, not measured provider usage.
        content = [m.model_dump() for m in messages]
        estimate = len(json.dumps({'messages': content, 'tools': tools}, default=str).encode()) + 2048
        output = min(self.output_tokens, self.tokens - self.spent - estimate)
        if output < 64:
            raise BudgetExceeded('token_budget')
        return {'timeout': min(20, self.remaining_seconds()), 'max_tokens': output}, estimate + output

    def charge(self, reply, reserved):
        usage = getattr(reply, 'usage_metadata', None)
        actual = usage.get('total_tokens') if isinstance(usage, dict) else None
        self.spent += actual if type(actual) is int and actual >= 0 else reserved
        self.remaining_seconds()
        if self.spent > self.tokens:
            raise BudgetExceeded('token_budget')

    def summary(self):
        return {'seconds_limit': self.seconds, 'tokens_limit': self.tokens,
                'accounted_tokens': self.spent, 'elapsed_ms':round((self.clock()-self._started)*1000,2),
                'accounting': 'provider_usage_when_available_otherwise_reserved_bytes'}


def provider_error(exc):
    status = getattr(exc, 'status_code', None)
    if status == 429:
        return 'rate_limit'
    if status in (401, 403):
        return 'authentication'
    if status in (400, 404, 422):
        return 'model_or_request'
    if isinstance(exc, TimeoutError) or 'timeout' in type(exc).__name__.lower():
        return 'provider_timeout'
    if isinstance(exc, (ConnectionError, APIConnectionError)):
        return 'provider_connection'
    if status and isinstance(status, int) and status >= 500:
        return 'provider_unavailable'
    return 'provider_error'
