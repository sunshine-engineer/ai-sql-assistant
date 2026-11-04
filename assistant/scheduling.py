"""Sequential benchmark quota admission, shared by both approaches and tool bindings."""
from collections import deque
from dataclasses import dataclass
import math
import time
from .budgets import BudgetExceeded


@dataclass
class Ticket:
    at: float
    tokens: int


class QuotaScheduler:
    def __init__(self, requests_per_minute=30, tokens_per_minute=8000,
                 interval=0, clock=time.monotonic, sleeper=time.sleep, window=60):
        if (type(requests_per_minute) is not int or requests_per_minute < 1 or
                type(tokens_per_minute) is not int or tokens_per_minute < 1 or
                not math.isfinite(interval) or interval < 0 or not math.isfinite(window) or window <= 0):
            raise ValueError('Use positive quota limits and a nonnegative finite interval.')
        self.rpm, self.tpm, self.interval = requests_per_minute, tokens_per_minute, interval
        self.clock, self.sleeper, self.window = clock, sleeper, window
        self.tickets = deque()
        self.last_dispatch = None
        self.cooldown = 0
        self.wait_seconds = 0
        self.denials = 0
        self.rate_limits = 0

    def acquire(self, tokens, budget):
        if type(tokens) is not int or tokens < 1:
            raise ValueError('Token reservation must be a positive integer.')
        if tokens > self.tpm:
            self.denials += 1
            raise BudgetExceeded('quota_request_too_large')
        while True:
            budget.remaining_seconds()
            now = self.clock()
            while self.tickets and self.tickets[0].at + self.window <= now:
                self.tickets.popleft()
            delay = max(0, self.cooldown-now)
            if self.last_dispatch is not None:
                delay = max(delay, self.last_dispatch+self.interval-now)
            if len(self.tickets) >= self.rpm:
                delay = max(delay, self.tickets[0].at+self.window-now)
            total = sum(t.tokens for t in self.tickets)
            if total + tokens > self.tpm:
                for ticket in self.tickets:
                    total -= ticket.tokens
                    if total + tokens <= self.tpm:
                        delay = max(delay, ticket.at+self.window-now)
                        break
            if delay <= 0:
                ticket = Ticket(now, tokens)
                self.tickets.append(ticket)
                self.last_dispatch = now
                return ticket
            # Reserve headroom for HTTP. Queue waits are charged to this request,
            # but do not consume the separate 20-second HTTP timeout.
            if delay + 2 >= budget.remaining_seconds():
                self.denials += 1
                raise BudgetExceeded('quota_wait_budget')
            step = min(delay, 1)
            self.sleeper(step)
            self.wait_seconds += step

    def cancel(self, ticket):
        self.tickets = deque(t for t in self.tickets if t is not ticket)
        self.last_dispatch = self.tickets[-1].at if self.tickets else None

    def complete(self, ticket, reply):
        usage = getattr(reply, 'usage_metadata', None)
        actual = usage.get('total_tokens') if isinstance(usage, dict) else None
        if type(actual) is int and actual >= 0:
            ticket.tokens = actual

    def failed(self, ticket, exc):
        status = getattr(exc, 'status_code', None)
        if status in (401, 403, 429):
            ticket.tokens = 0
        if status == 429:
            self.rate_limits += 1
            response = getattr(exc, 'response', None)
            headers = getattr(response, 'headers', {})
            try:
                delay = float(headers.get('retry-after', 60))
                if not math.isfinite(delay) or delay < 0:
                    delay = 60
            except (TypeError, ValueError):
                delay = 60
            self.cooldown = max(self.cooldown, self.clock()+min(delay, 86400))

    def summary(self):
        return {'requests_per_minute':self.rpm,'tokens_per_minute':self.tpm,
                'minimum_interval_seconds':self.interval,'queue_wait_ms':round(self.wait_seconds*1000,2),
                'budget_denials':self.denials,'provider_rate_limits':self.rate_limits,
                'token_estimate':'reserved input bytes / 3 plus output cap; replaced by usage when reported',
                'scope':'Sequential local quota estimate; shared account traffic and tokenizer differences can still cause 429.'}


class ScheduledModel:
    budget_scheduling = True

    def __init__(self, model, interval=0, scheduler=None):
        self.model = model
        self.scheduler = scheduler or QuotaScheduler(interval=interval)
        self.model_name = getattr(model, 'model_name', 'bound')
        self.pending = None

    def bind_tools(self, tools):
        bound = ScheduledModel(self.model.bind_tools(tools), scheduler=self.scheduler)
        bound.model_name = self.model_name
        return bound

    def prepare(self, budget, reserved, output):
        estimate = max(1, math.ceil((reserved-output)/3)+output)
        self.pending = self.scheduler.acquire(estimate, budget)

    def cancel_pending(self):
        if self.pending is not None:
            self.scheduler.cancel(self.pending)
            self.pending = None

    def invoke(self, messages, **kwargs):
        if self.pending is None:
            raise RuntimeError('Prepare quota admission using the request budget before invocation.')
        ticket, self.pending = self.pending, None
        try:
            reply = self.model.invoke(messages, **kwargs)
        except Exception as exc:
            self.scheduler.failed(ticket, exc)
            raise
        self.scheduler.complete(ticket, reply)
        return reply


def prepare_call(model, budget, messages, tools):
    kwargs, reserved = budget.admit(messages, tools)
    if getattr(model, 'budget_scheduling', False) is True:
        model.prepare(budget, reserved, kwargs['max_tokens'])
        # Admission may have waited. Recompute HTTP timeout from actual time left.
        try:
            kwargs, reserved = budget.admit(messages, tools)
        except BudgetExceeded:
            model.cancel_pending()
            raise
    return kwargs, reserved
