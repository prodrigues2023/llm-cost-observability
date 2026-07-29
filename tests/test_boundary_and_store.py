"""Exercises the boundary + store together: a call site sets dimensions,
the boundary emits real cost events, the store aggregates them per
docs/contracts/outcome-contract.md's formula -- including the retry-waste
scenario the whole repository exists to make visible.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from costkit import context
from costkit.boundary import CallFailedError, InstrumentationBoundary
from costkit.outcome import Outcome, OutcomeStatus
from costkit.pricing import PriceBasis, RateTable
from costkit.schema import UNATTRIBUTED_OUTCOME, UNKNOWN
from costkit.store import CostStore
from costkit.stub_model import DEFAULT_PROFILES, StubModelClient


@pytest.fixture
def rates():
    table = RateTable()
    table.add(
        PriceBasis(
            price_basis_id="large-test",
            model_tier="large",
            currency="USD",
            rate_input=Decimal("0.000003"),
            rate_output=Decimal("0.000015"),
            rate_cached_input=Decimal("0.0000015"),
            effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
            effective_to=None,
            source="test",
        )
    )
    return table


@pytest.fixture
def store():
    s = CostStore(":memory:")
    yield s
    s.close()


def test_call_without_context_writes_unknown_and_unattributed(rates, store):
    model = StubModelClient(DEFAULT_PROFILES, rng=random.Random(1))
    boundary = InstrumentationBoundary(model, rates, store)

    boundary.call("large")

    events = store.recent_events(limit=1)
    assert events[0]["feature"] == UNKNOWN
    assert events[0]["outcome_id"] == UNATTRIBUTED_OUTCOME
    assert store.unattributed_event_count() == 1


def test_call_with_context_attributes_correctly(rates, store):
    model = StubModelClient(DEFAULT_PROFILES, rng=random.Random(1))
    boundary = InstrumentationBoundary(model, rates, store)

    with context.dimensions(feature="checkout", tenant="acme", route="/chat", prompt_version="v1", outcome_id="task-1"):
        result = boundary.call("large")

    assert result.event.feature == "checkout"
    assert result.event.tenant == "acme"
    assert result.event.outcome_id == "task-1"
    assert result.event.computed_cost > 0


def test_successful_task_cost_per_outcome(rates, store):
    """One call, one success: cost per outcome equals that call's cost."""
    model = StubModelClient(DEFAULT_PROFILES, rng=random.Random(42))
    boundary = InstrumentationBoundary(model, rates, store)
    now = datetime.now(timezone.utc)

    outcome = Outcome(
        outcome_id="task-A", feature="checkout", tenant="acme",
        opened_at=now, resolution_window=timedelta(minutes=10),
    )
    store.open_outcome(outcome)

    with context.dimensions(feature="checkout", tenant="acme", route="/chat", prompt_version="v1", outcome_id="task-A"):
        result = boundary.call("large")

    store.resolve_outcome("task-A", OutcomeStatus.SUCCEEDED, now + timedelta(seconds=1))

    rows = store.spend_and_unit_cost_by("feature")
    checkout_row = next(r for r in rows if r["feature"] == "checkout")
    assert checkout_row["succeeded_outcomes"] == 1
    assert checkout_row["cost_per_outcome"] == pytest.approx(float(result.event.computed_cost), rel=1e-6)


def test_retry_waste_raises_cost_per_outcome_while_spend_looks_flat():
    """The headline scenario: a retried task costs more per outcome than a
    clean one, even though both tasks did 'the same' successful work.
    """
    rates = RateTable()
    rates.add(
        PriceBasis(
            price_basis_id="large-test", model_tier="large", currency="USD",
            rate_input=Decimal("0.000003"), rate_output=Decimal("0.000015"),
            rate_cached_input=Decimal("0.0000015"),
            effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc), effective_to=None, source="test",
        )
    )
    store = CostStore(":memory:")
    # A model that always fails on attempt 1 to force a deterministic retry.
    from costkit.stub_model import ModelProfile

    always_fails_once = ModelProfile(
        model_tier="large", input_tokens_range=(500, 500), output_tokens_range=(100, 100),
        cache_hit_rate=0.0, failure_rate=1.0,
    )
    reliable = ModelProfile(
        model_tier="large", input_tokens_range=(500, 500), output_tokens_range=(100, 100),
        cache_hit_rate=0.0, failure_rate=0.0,
    )

    now = datetime.now(timezone.utc)

    # Clean task: one call, succeeds.
    clean_model = StubModelClient({"large": reliable})
    clean_boundary = InstrumentationBoundary(clean_model, rates, store)
    store.open_outcome(Outcome("clean-task", "checkout", "acme", now, timedelta(minutes=10)))
    with context.dimensions(feature="checkout", tenant="acme", route="/chat", prompt_version="v1", outcome_id="clean-task"):
        clean_boundary.call("large", attempt_number=1)
    store.resolve_outcome("clean-task", OutcomeStatus.SUCCEEDED, now)

    # Retried task: attempt 1 fails (billed for input), attempt 2 succeeds.
    flaky_model = StubModelClient({"large": always_fails_once})
    flaky_boundary = InstrumentationBoundary(flaky_model, rates, store)
    store.open_outcome(Outcome("retried-task", "checkout", "acme", now, timedelta(minutes=10)))
    with context.dimensions(feature="checkout", tenant="acme", route="/chat", prompt_version="v1", outcome_id="retried-task"):
        with pytest.raises(CallFailedError):
            flaky_boundary.call("large", attempt_number=1)
        # Retry with a reliable client standing in for "the second attempt worked."
        reliable_retry_model = StubModelClient({"large": reliable})
        flaky_boundary_retry = InstrumentationBoundary(reliable_retry_model, rates, store)
        flaky_boundary_retry.call("large", attempt_number=2)
    store.resolve_outcome("retried-task", OutcomeStatus.SUCCEEDED, now)

    rows = store.spend_and_unit_cost_by("feature")
    row = next(r for r in rows if r["feature"] == "checkout")
    # Two succeeded outcomes; the retried one paid for its failed attempt
    # too, so total spend / 2 outcomes must exceed what either single call
    # cost alone -- the unit-cost-rises-with-waste effect ADR-0003 exists
    # to surface.
    events = store.recent_events(limit=10)
    clean_cost = sum(float(e["computed_cost"]) for e in events if e["outcome_id"] == "clean-task")
    retried_cost = sum(float(e["computed_cost"]) for e in events if e["outcome_id"] == "retried-task")

    assert retried_cost > clean_cost  # the failed attempt added real cost
    assert row["succeeded_outcomes"] == 2
    assert row["cost_per_outcome"] == pytest.approx((clean_cost + retried_cost) / 2, abs=1e-6)
    assert row["cost_per_outcome"] > clean_cost  # unit cost pulled up by the retry

    store.close()


def test_sweep_abandoned_excludes_from_denominator():
    rates = RateTable()
    rates.add(
        PriceBasis(
            price_basis_id="large-test", model_tier="large", currency="USD",
            rate_input=Decimal("0.000003"), rate_output=Decimal("0.000015"),
            rate_cached_input=Decimal("0.0000015"),
            effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc), effective_to=None, source="test",
        )
    )
    store = CostStore(":memory:")
    model = StubModelClient(DEFAULT_PROFILES, rng=random.Random(7))
    boundary = InstrumentationBoundary(model, rates, store)

    now = datetime.now(timezone.utc)
    store.open_outcome(Outcome("abandoned-task", "checkout", "acme", now, timedelta(minutes=1)))
    with context.dimensions(feature="checkout", tenant="acme", route="/chat", prompt_version="v1", outcome_id="abandoned-task"):
        boundary.call("large")
    # never resolved -- simulate time passing past the resolution window
    swept = store.sweep_abandoned(now + timedelta(minutes=5))
    assert swept == 1

    rows = store.spend_and_unit_cost_by("feature")
    row = next(r for r in rows if r["feature"] == "checkout")
    assert row["succeeded_outcomes"] == 0
    assert row["total_spend"] > 0  # cost was real even though nothing succeeded
    assert row["cost_per_outcome"] is None

    store.close()
