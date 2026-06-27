"""Token + cost metering for a Harvey eval run.

Harness-only: it wraps the Anthropic SDK boundary (`client.messages.stream`) on a
provider instance so we can read `usage` off each streamed completion. It does NOT
touch any backend file — the provider keeps all its retry/JSON logic; we only proxy
`get_final_message()` to accumulate token counts.

Cost uses public per-MTok pricing (USD), keyed by model id. Opus 4.8: $5 in / $25 out;
prompt-cache write 1.25x input (5-min TTL), cache read 0.1x input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# USD per 1,000,000 tokens. input/output are list prices; cache_write is the 5-min-TTL
# write premium (1.25x input), cache_read is the read price (~0.1x input).
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-8": {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_read": 0.50},
    "claude-opus-4-7": {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_read": 0.50},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.30},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.10},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.10},
}


@dataclass
class UsageTracker:
    """Accumulates token usage across every LLM call in one task evaluation."""

    model: str = ""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    def add(self, usage: object) -> None:
        self.calls += 1
        self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        self.cache_read_tokens += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        self.cache_creation_tokens += int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

    def cost_usd(self) -> float:
        p = PRICING.get(self.model)
        if not p:
            return 0.0
        return (
            self.input_tokens * p["input"]
            + self.output_tokens * p["output"]
            + self.cache_creation_tokens * p["cache_write"]
            + self.cache_read_tokens * p["cache_read"]
        ) / 1_000_000

    def summary(self) -> dict:
        total_in = self.input_tokens + self.cache_read_tokens + self.cache_creation_tokens
        return {
            "model": self.model,
            "llm_calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "total_input_tokens": total_in,
            "total_tokens": total_in + self.output_tokens,
            "cost_usd": round(self.cost_usd(), 6),
        }


class _MeteredStream:
    """Proxies a MessageStream, recording usage when the final message is pulled."""

    def __init__(self, real, tracker: UsageTracker) -> None:
        self._real = real
        self._tracker = tracker

    def get_final_message(self):
        msg = self._real.get_final_message()
        self._tracker.add(getattr(msg, "usage", None))
        return msg

    def __getattr__(self, name):
        return getattr(self._real, name)


class _MeteredManager:
    """Proxies the stream context manager so __enter__ yields a metered stream."""

    def __init__(self, real_mgr, tracker: UsageTracker) -> None:
        self._real_mgr = real_mgr
        self._tracker = tracker

    def __enter__(self):
        return _MeteredStream(self._real_mgr.__enter__(), self._tracker)

    def __exit__(self, *exc):
        return self._real_mgr.__exit__(*exc)


def install_metering(provider: object, tracker: UsageTracker) -> bool:
    """Wrap `provider._client.messages.stream` to record usage into `tracker`.

    Returns True if metering was installed (real provider with an Anthropic client),
    False otherwise (e.g. the mock provider, which makes no metered API calls)."""
    client = getattr(provider, "_client", None)
    if client is None:
        return False
    tracker.model = getattr(provider, "_model", "") or tracker.model
    real_stream = client.messages.stream

    def metered_stream(*args, **kwargs):
        return _MeteredManager(real_stream(*args, **kwargs), tracker)

    client.messages.stream = metered_stream
    return True
