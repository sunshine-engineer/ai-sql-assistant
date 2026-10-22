"""Conservative admission budgets; no provider retries or work after exhaustion.

File: assistant/budgets.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import json
import time
from dataclasses import dataclass, field

from groq import APIConnectionError

from .config import (
    DEFAULT_OUTPUT_TOKENS,
    DEFAULT_PROVIDER_TIMEOUT_SECONDS,
    DEFAULT_REQUEST_SECONDS,
    DEFAULT_REQUEST_TOKENS,
)


class BudgetExceeded(RuntimeError):
    """Signal that a request cannot admit more work within its time or token budget."""

    pass


@dataclass
class RequestBudget:
    """Account for one request deadline and conservative model token reservations.

    Attributes:
        seconds: Request deadline duration in seconds.
        tokens: Cumulative token admission cap.
        output_tokens: Maximum output tokens per call.
        clock: Injectable monotonic clock.
        spent: Measured or reserved cumulative token usage.
        _started: Initial monotonic timestamp.
    """

    seconds: float = DEFAULT_REQUEST_SECONDS
    tokens: int = DEFAULT_REQUEST_TOKENS
    output_tokens: int = DEFAULT_OUTPUT_TOKENS
    clock: object = field(default=time.monotonic, repr=False)
    spent: int = 0
    _started: float = field(init=False, repr=False)

    def __post_init__(self):
        """Validate positive request budgets and record the initial monotonic time.

        Raises:
            ValueError: If any configured budget is not positive.
        """
        if self.seconds <= 0 or self.tokens <= 0 or self.output_tokens <= 0:
            raise ValueError("Budgets must be positive.")
        self._started = self.clock()

    def remaining_seconds(self):
        """Return the request time remaining or stop work after its deadline.

        Returns:
            float: Positive wall-clock seconds remaining.

        Raises:
            BudgetExceeded: If the request deadline has elapsed.
        """
        remaining = self.seconds - (self.clock() - self._started)
        if remaining <= 0:
            raise BudgetExceeded("time_budget")
        return remaining

    def admit(self, messages, tools):
        # UTF-8 bytes conservatively bound content tokens; reserve protocol/tool
        # overhead too. This is admission accounting, not measured provider usage.
        """Reserve model input and output capacity before a provider call.

        Args:
            messages: Conversation messages supplied to the workflow or model.
            tools: Tool schemas sent to or bound on the provider model.

        Returns:
            tuple: Provider timeout/output arguments and reserved token charge.

        Raises:
            BudgetExceeded: If time or remaining output-token capacity is exhausted.
        """
        content = [m.model_dump() for m in messages]
        estimate = (
            len(json.dumps({"messages": content, "tools": tools}, default=str).encode()) + 2048
        )
        output = min(self.output_tokens, self.tokens - self.spent - estimate)
        if output < 64:
            raise BudgetExceeded("token_budget")
        return {
            "timeout": min(DEFAULT_PROVIDER_TIMEOUT_SECONDS, self.remaining_seconds()),
            "max_tokens": output,
        }, estimate + output

    def charge(self, reply, reserved):
        """Charge reported token usage, or the reservation when usage is unavailable.

        Args:
            reply: Provider reply with optional usage_metadata.
            reserved: Conservative token reservation for this provider invocation.

        Raises:
            BudgetExceeded: If the deadline or cumulative token limit has been exceeded.
        """
        usage = getattr(reply, "usage_metadata", None)
        actual = usage.get("total_tokens") if isinstance(usage, dict) else None
        self.spent += actual if type(actual) is int and actual >= 0 else reserved
        self.remaining_seconds()
        if self.spent > self.tokens:
            raise BudgetExceeded("token_budget")

    def summary(self):
        """Export request limits, elapsed time, and token accounting method.

        Returns:
            dict: Sanitized operational metadata.
        """
        return {
            "seconds_limit": self.seconds,
            "tokens_limit": self.tokens,
            "accounted_tokens": self.spent,
            "elapsed_ms": round((self.clock() - self._started) * 1000, 2),
            "accounting": "provider_usage_when_available_otherwise_reserved_bytes",
        }


def provider_error(exc):
    """Map a provider exception to a sanitized operational error category.

    Args:
        exc: Raised exception to classify without exposing its private message.

    Returns:
        str: Sanitized provider error category.
    """
    status = getattr(exc, "status_code", None)
    if status == 429:
        return "rate_limit"
    if status in (401, 403):
        return "authentication"
    if status in (400, 404, 422):
        return "model_or_request"
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower():
        return "provider_timeout"
    if isinstance(exc, (ConnectionError, APIConnectionError)):
        return "provider_connection"
    if status and isinstance(status, int) and status >= 500:
        return "provider_unavailable"
    return "provider_error"
