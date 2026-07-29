"""Synthetic traffic — ROADMAP.md's "stubbed model, synthetic traffic, no
cloud account" for Milestone 3, and the mechanism that makes a retry
storm's cost-per-outcome effect visible on the dashboard without waiting
for real requests.

Generates historical-looking tasks (each one or more correlated calls,
some of which retry and fail) across a time window, using the real
boundary and store -- so what the console shows is aggregated from real
CostEvent/Outcome rows, not a canned chart.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from costkit import context
from costkit.boundary import CallFailedError, InstrumentationBoundary
from costkit.outcome import Outcome, OutcomeStatus
from costkit.pricing import RateTable
from costkit.store import CostStore
from costkit.stub_model import ModelProfile, StubModelClient

FEATURES = ["checkout-assistant", "support-triage", "doc-summarizer"]
TENANTS = ["acme", "globex", "initech"]
ROUTES = {
    "checkout-assistant": "/checkout/chat",
    "support-triage": "/support/triage",
    "doc-summarizer": "/docs/summarize",
}
PROMPT_VERSIONS = ["v1", "v2"]
MODEL_TIERS = ["small", "large"]

RESOLUTION_WINDOW = timedelta(minutes=10)
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class RetryStorm:
    """Injects an elevated failure rate for one feature within a time window
    -- the scenario docs/diagrams/instrumentation.md's sequence describes:
    spend stays roughly flat, cost per outcome rises.
    """

    feature: str
    starts_at: datetime
    ends_at: datetime
    failure_rate: float = 0.6


@dataclass(frozen=True)
class ContextBloat:
    """Multiplies input tokens for one feature within a time window --
    docs/cost-model.md's "context bloat" waste, distinct from a retry
    storm: every call still succeeds first try, so failure-rate-based
    detection would miss it entirely. Only cost-per-outcome catches it,
    because total spend rising from more legitimate-looking traffic reads
    as "a big task", per cost-model.md's waste table.
    """

    feature: str
    starts_at: datetime
    ends_at: datetime
    multiplier: float = 4.0


@dataclass(frozen=True)
class ModelDowngrade:
    """Forces a feature onto one specific model tier within a time window --
    the "cost regression" drill's shape: a deploy that quietly swapped in
    a pricier (or just wrong) tier for a task that didn't need it. Unlike
    ContextBloat this doesn't change token volume, only the price basis.
    """

    feature: str
    starts_at: datetime
    ends_at: datetime
    model_tier: str = "large"


@dataclass
class TrafficConfig:
    start: datetime
    end: datetime
    num_tasks: int = 600
    seed: int = 42
    retry_storm: RetryStorm | None = None
    context_bloat: ContextBloat | None = None
    model_downgrade: ModelDowngrade | None = None
    base_failure_rate: float = 0.03


def _profile_for(model_tier: str, failure_rate: float) -> ModelProfile:
    ranges = {
        "small": ((200, 800), (50, 300)),
        "large": ((400, 1600), (100, 600)),
    }
    input_range, output_range = ranges[model_tier]
    return ModelProfile(
        model_tier=model_tier,
        input_tokens_range=input_range,
        output_tokens_range=output_range,
        cache_hit_rate=0.15,
        failure_rate=failure_rate,
    )


def generate_traffic(store: CostStore, rates: RateTable, config: TrafficConfig) -> dict:
    """Runs `config.num_tasks` synthetic tasks through the real boundary.

    Returns a small summary dict (counts) for the caller to log -- the
    console reads its picture back out of the store afterward, same as a
    real deployment would.
    """
    rng = random.Random(config.seed)
    span_seconds = (config.end - config.start).total_seconds()

    succeeded = failed = 0

    for _ in range(config.num_tasks):
        opened_at = config.start + timedelta(seconds=rng.uniform(0, span_seconds))
        feature = rng.choice(FEATURES)
        tenant = rng.choice(TENANTS)
        route = ROUTES[feature]
        model_tier = rng.choice(MODEL_TIERS)
        prompt_version = rng.choice(PROMPT_VERSIONS)
        outcome_id = f"{feature}-{tenant}-{opened_at.timestamp():.6f}-{rng.randint(0, 999999)}"

        if (
            config.model_downgrade is not None
            and feature == config.model_downgrade.feature
            and config.model_downgrade.starts_at <= opened_at <= config.model_downgrade.ends_at
        ):
            model_tier = config.model_downgrade.model_tier

        failure_rate = config.base_failure_rate
        if (
            config.retry_storm is not None
            and feature == config.retry_storm.feature
            and config.retry_storm.starts_at <= opened_at <= config.retry_storm.ends_at
        ):
            failure_rate = config.retry_storm.failure_rate

        profile = _profile_for(model_tier, failure_rate)
        model = StubModelClient({model_tier: profile}, rng=random.Random(rng.randint(0, 2**31)))
        boundary = InstrumentationBoundary(model, rates, store)

        input_tokens_override = None
        if (
            config.context_bloat is not None
            and feature == config.context_bloat.feature
            and config.context_bloat.starts_at <= opened_at <= config.context_bloat.ends_at
        ):
            baseline_input = rng.randint(*profile.input_tokens_range)
            input_tokens_override = int(baseline_input * config.context_bloat.multiplier)

        store.open_outcome(
            Outcome(
                outcome_id=outcome_id,
                feature=feature,
                tenant=tenant,
                opened_at=opened_at,
                resolution_window=RESOLUTION_WINDOW,
            )
        )

        call_time = opened_at
        task_succeeded = False
        with context.dimensions(
            feature=feature, tenant=tenant, route=route, prompt_version=prompt_version,
            outcome_id=outcome_id,
        ):
            for attempt in range(1, MAX_ATTEMPTS + 1):
                try:
                    boundary.call(
                        model_tier,
                        attempt_number=attempt,
                        at=call_time,
                        input_tokens_override=input_tokens_override,
                    )
                    task_succeeded = True
                    break
                except CallFailedError:
                    call_time = call_time + timedelta(seconds=rng.uniform(0.5, 3.0))
                    continue

        resolved_at = call_time + timedelta(seconds=rng.uniform(0.1, 1.0))
        if task_succeeded:
            store.resolve_outcome(outcome_id, OutcomeStatus.SUCCEEDED, resolved_at)
            succeeded += 1
        else:
            # Exhausted retries within the resolution window -- an
            # explicit failure, not left pending to be swept later.
            store.resolve_outcome(outcome_id, OutcomeStatus.FAILED, resolved_at)
            failed += 1

    return {"succeeded": succeeded, "failed": failed, "total": config.num_tasks}
