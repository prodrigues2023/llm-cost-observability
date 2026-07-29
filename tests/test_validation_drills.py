"""Milestone 4: prove the alerts and the unit cost catch what a bill hides.

Each test here is one of ROADMAP.md's four validation drills, enforced as
a real assertion against data costkit itself generated -- not a fixture
shaped to make the claim look true. `make test` runs these on every push,
so the milestone's claims stay true rather than becoming stale prose.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from costkit.budgets import detect_anomalies
from costkit.pricing import PriceBasis, RateTable
from costkit.store import CostStore
from costkit.traffic import (
    FEATURES,
    ContextBloat,
    ModelDowngrade,
    RetryStorm,
    TrafficConfig,
    generate_traffic,
)


def make_rates() -> RateTable:
    table = RateTable()
    for tier, rate_in, rate_out in (("small", "0.0000005", "0.0000015"), ("large", "0.000003", "0.000015")):
        table.add(
            PriceBasis(
                price_basis_id=f"{tier}-test",
                model_tier=tier,
                currency="USD",
                rate_input=Decimal(rate_in),
                rate_output=Decimal(rate_out),
                rate_cached_input=Decimal(rate_in) / 2,
                effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
                effective_to=None,
                source="test",
            )
        )
    return table


# --- Drill 1: cost regression -------------------------------------------


def test_cost_regression_drill_anomaly_fires():
    """A deploy quietly swaps a feature onto a pricier model tier. Token
    volume and failure rate are unchanged -- only the price basis is
    different -- and the anomaly detector must still catch it.
    """
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=8)

    downgrade = ModelDowngrade(
        feature="support-triage", starts_at=now - timedelta(hours=1), ends_at=now, model_tier="large",
    )
    config = TrafficConfig(start=start, end=now, num_tasks=1000, seed=101, model_downgrade=downgrade)
    generate_traffic(store, rates, config)

    anomalies = detect_anomalies(store, "feature", FEATURES, now, ratio_threshold=1.3)
    flagged = {a.value for a in anomalies}
    assert "support-triage" in flagged, f"expected support-triage flagged, got {flagged}"

    anomaly = next(a for a in anomalies if a.value == "support-triage")
    assert anomaly.ratio > 1.3
    store.close()


# --- Drill 2: retry storm -------------------------------------------------


def test_retry_storm_cost_per_outcome_rises_while_spend_stays_comparatively_flat():
    """The headline claim: a retry storm raises cost per outcome far more
    than it raises total spend, because failed attempts are billed but
    contribute nothing to the denominator.
    """
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=8)

    storm = RetryStorm(feature="checkout-assistant", starts_at=now - timedelta(hours=1), ends_at=now, failure_rate=0.85)
    config = TrafficConfig(start=start, end=now, num_tasks=1200, seed=102, retry_storm=storm, base_failure_rate=0.02)
    generate_traffic(store, rates, config)

    baseline = next(
        r for r in store.spend_and_unit_cost_by("feature", since=start, until=now - timedelta(hours=1))
        if r["feature"] == "checkout-assistant"
    )
    recent = next(
        r for r in store.spend_and_unit_cost_by("feature", since=now - timedelta(hours=1))
        if r["feature"] == "checkout-assistant"
    )

    # Normalize spend to a per-hour rate so a 1h recent window is
    # comparable to a 7h baseline window.
    baseline_hourly_spend = baseline["total_spend"] / 7
    recent_hourly_spend = recent["total_spend"] / 1

    spend_ratio = recent_hourly_spend / baseline_hourly_spend
    cost_per_outcome_ratio = recent["cost_per_outcome"] / baseline["cost_per_outcome"]

    # The unit-cost signal must rise meaningfully more than spend does --
    # this is the exact gap a total-spend-only dashboard sleeps through.
    assert cost_per_outcome_ratio > 1.3
    assert cost_per_outcome_ratio > spend_ratio + 0.1, (
        f"cost_per_outcome_ratio={cost_per_outcome_ratio:.2f} did not exceed "
        f"spend_ratio={spend_ratio:.2f} by a meaningful margin"
    )
    # And the failure signature is real: fewer of the storm window's
    # outcomes succeeded than attempted.
    assert recent["succeeded_outcomes"] < recent["total_outcomes"]
    store.close()


# --- Drill 3: context bloat ------------------------------------------------


def test_context_bloat_raises_unit_cost_via_tokens_not_failures():
    """Padding input tokens raises cost per outcome even though every call
    still succeeds first try -- proving the effect is real waste (excess
    tokens), not disguised retry waste.
    """
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=8)

    bloat = ContextBloat(feature="doc-summarizer", starts_at=now - timedelta(hours=1), ends_at=now, multiplier=5.0)
    config = TrafficConfig(start=start, end=now, num_tasks=1000, seed=103, context_bloat=bloat, base_failure_rate=0.01)
    generate_traffic(store, rates, config)

    baseline = next(
        r for r in store.spend_and_unit_cost_by("feature", since=start, until=now - timedelta(hours=1))
        if r["feature"] == "doc-summarizer"
    )
    recent = next(
        r for r in store.spend_and_unit_cost_by("feature", since=now - timedelta(hours=1))
        if r["feature"] == "doc-summarizer"
    )

    assert recent["cost_per_outcome"] > baseline["cost_per_outcome"] * 1.5

    # The bloat drill's signature, distinct from a retry storm: nearly
    # every task still succeeds first try.
    recent_success_rate = recent["succeeded_outcomes"] / recent["total_outcomes"]
    assert recent_success_rate > 0.95, (
        f"expected context bloat to leave success rate high, got {recent_success_rate:.2%}"
    )
    store.close()


# --- Drill 4: attribution reconciliation -----------------------------------


def test_attribution_reconciles_with_the_independently_recomputed_total():
    """Attributed cost must equal an amount recomputed from the stored
    token counts and price basis independently of the store's own
    running total -- the "attributed total reconciles with the bill"
    exit criterion, checked the only way possible without a real bill:
    the formula must reproduce every stored number exactly.
    """
    store = CostStore(":memory:")
    rates = make_rates()
    now = datetime.now(timezone.utc)
    config = TrafficConfig(start=now - timedelta(hours=6), end=now, num_tasks=500, seed=104)
    generate_traffic(store, rates, config)

    events = store.recent_events(limit=10_000)
    assert len(events) > 0

    recomputed_total = Decimal(0)
    for event in events:
        basis = rates.get(event["price_basis_id"])
        recomputed = basis.compute_cost(
            event["input_tokens"], event["output_tokens"], event["cached_input_tokens"]
        )
        stored = Decimal(str(event["computed_cost"]))
        assert abs(recomputed - stored) < Decimal("0.0000001"), (
            f"event {event['event_id']}: stored={stored} recomputed={recomputed}"
        )
        recomputed_total += recomputed

    stored_total = store.total_spend()
    assert abs(recomputed_total - stored_total) < Decimal("0.000001"), (
        f"recomputed_total={recomputed_total} stored_total={stored_total}"
    )

    # Every event was attributed -- no event fell into the unknown/
    # unattributed bucket, since generate_traffic always sets context.
    assert store.unattributed_event_count() == 0
    store.close()
