"""A stubbed model client — no real provider, no API key, no network call.

Returns token counts and a synthetic failure per a configurable profile,
per ROADMAP.md's Milestone 3 "stubbed model, synthetic traffic, no cloud
account" requirement. This is what the instrumentation boundary wraps;
swapping this for a real provider client is the only change a real
deployment needs to make.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


class ModelCallError(Exception):
    """A simulated call failure -- the stub's analogue of a provider error.

    Carries the input tokens the provider had already processed, and
    (usually) a partial output the provider had already generated before
    failing -- a stream that errors mid-way still bills what it produced.
    This is what makes retry waste (cost-model.md) show up as real,
    substantial cost on a failed attempt, not a rounding error.
    """

    def __init__(self, message: str, input_tokens: int, partial_output_tokens: int = 0) -> None:
        super().__init__(message)
        self.input_tokens = input_tokens
        self.partial_output_tokens = partial_output_tokens


@dataclass(frozen=True)
class ModelProfile:
    """Per-tier behaviour: token ranges, cache hit rate, failure rate."""

    model_tier: str
    input_tokens_range: tuple[int, int]
    output_tokens_range: tuple[int, int]
    cache_hit_rate: float = 0.0
    failure_rate: float = 0.0


@dataclass(frozen=True)
class ModelResponse:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int


class StubModelClient:
    """A deterministic-if-seeded stand-in for a real LLM API client."""

    def __init__(self, profiles: dict[str, ModelProfile], rng: random.Random | None = None) -> None:
        self._profiles = profiles
        self._rng = rng or random.Random()

    def call(self, model_tier: str, input_tokens_override: int | None = None) -> ModelResponse:
        try:
            profile = self._profiles[model_tier]
        except KeyError as exc:
            raise ValueError(f"no stub profile for model_tier={model_tier!r}") from exc

        input_tokens = (
            input_tokens_override
            if input_tokens_override is not None
            else self._rng.randint(*profile.input_tokens_range)
        )

        if self._rng.random() < profile.failure_rate:
            # Most failures happen partway through generation, not before
            # it starts -- bill for a random fraction of the normal output
            # range, the same way a real streaming failure would.
            max_partial = max(profile.output_tokens_range[1] // 2, 1)
            partial_output_tokens = self._rng.randint(0, max_partial)
            raise ModelCallError(
                f"simulated failure for model_tier={model_tier!r}",
                input_tokens=input_tokens,
                partial_output_tokens=partial_output_tokens,
            )

        output_tokens = self._rng.randint(*profile.output_tokens_range)
        cached_input_tokens = (
            input_tokens if self._rng.random() < profile.cache_hit_rate else 0
        )
        return ModelResponse(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
        )


DEFAULT_PROFILES: dict[str, ModelProfile] = {
    "small": ModelProfile(
        model_tier="small",
        input_tokens_range=(200, 800),
        output_tokens_range=(50, 300),
        cache_hit_rate=0.1,
        failure_rate=0.02,
    ),
    "large": ModelProfile(
        model_tier="large",
        input_tokens_range=(200, 800),
        output_tokens_range=(50, 300),
        cache_hit_rate=0.1,
        failure_rate=0.01,
    ),
}
