"""Abuse and cost protection for a publicly reachable deployment.

Everything here is in-process (one worker). It protects the single shared model credential
and the Zhihu session from being used up; it is not an authentication system.

Environment (all optional, integers; 0 disables that limit):
  RATE_LIMIT_MODEL_PER_HOUR   model-backed requests per client per hour (default 40)
  RATE_LIMIT_CREATE_PER_HOUR  rooms created per client per hour (default 20)
  MODEL_DAILY_BUDGET          model calls per UTC day across all clients (default 1500)
  MODEL_MIN_GAP_SECONDS       minimum spacing between model calls, all clients (default 25)
  MODEL_MAX_QUEUE_SECONDS     longest a call may wait for its slot before "busy" (default 90)
  TRUST_PROXY                 set to 1 behind a reverse proxy, to key clients by X-Forwarded-For
"""
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import HTTPException, Request


class ModelBusy(Exception):
    """The shared model credential is saturated or out of budget; callers show this message as is."""


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def client_key(request: Request) -> str:
    if os.getenv('TRUST_PROXY') == '1':
        forwarded = request.headers.get('x-forwarded-for', '')
        if forwarded.strip():
            return forwarded.split(',')[0].strip()
    return request.client.host if request.client else 'unknown'


class WindowLimiter:
    """Sliding-window counter per key. Returns seconds to wait when the key is over its limit."""

    def __init__(self):
        self.hits = defaultdict(deque)
        self._checks = 0

    def check(self, key, limit, window=3600.0, now=None):
        if limit <= 0:
            return None
        now = time.monotonic() if now is None else now
        q = self.hits[key]
        while q and now - q[0] >= window:
            q.popleft()
        if len(q) >= limit:
            return max(1, int(window - (now - q[0])) + 1)
        q.append(now)
        self._checks += 1
        if self._checks % 500 == 0:  # drop idle keys so memory stays bounded
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] >= window]:
                self.hits.pop(k, None)
        return None

    def reset(self):
        self.hits.clear()


limiter = WindowLimiter()


def rate_limit(bucket: str, env: str, default: int):
    """FastAPI dependency factory: 429 with Retry-After once a client exceeds its hourly allowance."""

    async def dependency(request: Request):
        wait = limiter.check(f'{bucket}:{client_key(request)}', _int(env, default))
        if wait is not None:
            raise HTTPException(
                429,
                f'请求太频繁，请约 {max(1, wait // 60)} 分钟后再试。',
                headers={'Retry-After': str(wait)},
            )

    return dependency


limit_model = rate_limit('model', 'RATE_LIMIT_MODEL_PER_HOUR', 40)
limit_create = rate_limit('create', 'RATE_LIMIT_CREATE_PER_HOUR', 20)

# ---- shared model credential -------------------------------------------------

_next_slot = 0.0
_budget_day = None
_budget_used = 0


def reserve_model_slot(now=None):
    """Reserve the next call slot for the whole process and return how long to wait for it.

    Spacing is global (not per request), so concurrent users cannot exceed the upstream rate.
    Raises ModelBusy instead of queueing for longer than MODEL_MAX_QUEUE_SECONDS.
    """
    global _next_slot, _budget_day, _budget_used
    now = time.monotonic() if now is None else now
    gap = _int('MODEL_MIN_GAP_SECONDS', 25)
    max_wait = _int('MODEL_MAX_QUEUE_SECONDS', 90)
    budget = _int('MODEL_DAILY_BUDGET', 1500)
    today = datetime.now(timezone.utc).date()
    if _budget_day != today:
        _budget_day, _budget_used = today, 0
    if budget > 0 and _budget_used >= budget:
        raise ModelBusy('今日模型调用额度已用完，请明天再来。')
    slot = max(now, _next_slot)
    wait = slot - now
    if max_wait > 0 and wait > max_wait:
        raise ModelBusy('现在使用的人比较多，请稍后再试。已有的对话不会丢失。')
    _next_slot = slot + gap
    _budget_used += 1
    return wait


def reset_model_state():
    global _next_slot, _budget_day, _budget_used
    _next_slot, _budget_day, _budget_used = 0.0, None, 0
