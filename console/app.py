"""The attribution console — Milestone 3's dashboard.

Serves the UI and a small JSON API over the real CostStore: everything the
page shows is aggregated from cost events and outcomes the boundary
actually wrote, via costkit.traffic's synthetic generator on startup (and
on demand, for the retry-storm demo button) -- not canned sample data.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from costkit.budgets import Budget, BudgetMetric, check_budgets, detect_anomalies
from costkit.pricing import PriceBasis, RateTable
from costkit.store import CostStore
from costkit.traffic import FEATURES, RetryStorm, TrafficConfig, generate_traffic

# In-memory by default: the console reseeds 24h of synthetic traffic on
# every start, so there is nothing to persist across restarts. Set
# COST_DB_PATH to a file path to keep data between restarts instead.
DB_PATH = os.environ.get("COST_DB_PATH", ":memory:")
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="LLM Cost Observability Console")

_rates = RateTable()
_store = CostStore(DB_PATH)


def _seed_rates() -> None:
    epoch = datetime(2020, 1, 1, tzinfo=timezone.utc)
    _rates.add(
        PriceBasis(
            price_basis_id="small-2026",
            model_tier="small",
            currency="USD",
            rate_input=Decimal("0.0000005"),
            rate_output=Decimal("0.0000015"),
            rate_cached_input=Decimal("0.00000025"),
            effective_from=epoch,
            effective_to=None,
            source="reference rate table, docs/contracts/pricing-abstraction.md example",
        )
    )
    _rates.add(
        PriceBasis(
            price_basis_id="large-2026",
            model_tier="large",
            currency="USD",
            rate_input=Decimal("0.000003"),
            rate_output=Decimal("0.000015"),
            rate_cached_input=Decimal("0.0000015"),
            effective_from=epoch,
            effective_to=None,
            source="reference rate table, docs/contracts/pricing-abstraction.md example",
        )
    )


BUDGETS = [
    Budget(dimension="feature", value="checkout-assistant", metric=BudgetMetric.COST_PER_OUTCOME,
           threshold=Decimal("0.0045"), window=timedelta(hours=24)),
    Budget(dimension="feature", value="support-triage", metric=BudgetMetric.COST_PER_OUTCOME,
           threshold=Decimal("0.015"), window=timedelta(hours=24)),
    Budget(dimension="feature", value="doc-summarizer", metric=BudgetMetric.COST_PER_OUTCOME,
           threshold=Decimal("0.03"), window=timedelta(hours=24)),
    Budget(dimension="tenant", value="acme", metric=BudgetMetric.SPEND,
           threshold=Decimal("5.00"), window=timedelta(hours=24)),
]


def _seed_traffic(with_storm: bool = True) -> dict:
    now = datetime.now(timezone.utc)
    storm = (
        RetryStorm(feature="checkout-assistant", starts_at=now - timedelta(hours=1), ends_at=now, failure_rate=0.85)
        if with_storm
        else None
    )
    config = TrafficConfig(
        start=now - timedelta(hours=24), end=now, num_tasks=2400, seed=42, retry_storm=storm,
    )
    return generate_traffic(_store, _rates, config)


@app.on_event("startup")
def on_startup() -> None:
    _seed_rates()
    _seed_traffic(with_storm=True)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/summary")
def api_summary() -> JSONResponse:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    total_spend = _store.total_spend(since=since)
    status_counts = _store.outcome_status_counts()
    unattributed = _store.unattributed_event_count(since=since)

    rows = _store.spend_and_unit_cost_by("feature", since=since)
    succeeded = sum(r["succeeded_outcomes"] for r in rows)
    attributed_to_succeeded = sum(
        (r["cost_per_outcome"] or 0) * r["succeeded_outcomes"] for r in rows
    )
    blended_cost_per_outcome = attributed_to_succeeded / succeeded if succeeded else None

    return JSONResponse(
        {
            "total_spend_24h": float(total_spend),
            "blended_cost_per_outcome_24h": blended_cost_per_outcome,
            "outcome_status_counts": status_counts,
            "unattributed_events_24h": unattributed,
        }
    )


@app.get("/api/attribution")
def api_attribution(dimension: str = "feature", hours: int = 24, until_hours_ago: int = 0) -> JSONResponse:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)
    until = now - timedelta(hours=until_hours_ago) if until_hours_ago else None
    rows = _store.spend_and_unit_cost_by(dimension, since=since, until=until)
    return JSONResponse(rows)


@app.get("/api/timeseries")
def api_timeseries(dimension: str = "feature", value: str = "checkout-assistant", hours: int = 8, bucket_minutes: int = 15) -> JSONResponse:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = _store.cost_per_outcome_timeseries(dimension, value, bucket_minutes * 60, since)
    return JSONResponse(rows)


@app.get("/api/budgets")
def api_budgets() -> JSONResponse:
    now = datetime.now(timezone.utc)
    breaches = check_budgets(_store, BUDGETS, now)
    return JSONResponse(
        [
            {
                "dimension": b.budget.dimension,
                "value": b.budget.value,
                "metric": b.budget.metric.value,
                "threshold": float(b.budget.threshold),
                "actual": float(b.actual),
            }
            for b in breaches
        ]
    )


@app.get("/api/anomalies")
def api_anomalies() -> JSONResponse:
    now = datetime.now(timezone.utc)
    anomalies = detect_anomalies(_store, "feature", FEATURES, now, ratio_threshold=1.3)
    return JSONResponse(
        [
            {
                "dimension": a.dimension,
                "value": a.value,
                "baseline_cost_per_outcome": a.baseline_cost_per_outcome,
                "recent_cost_per_outcome": a.recent_cost_per_outcome,
                "ratio": a.ratio,
            }
            for a in anomalies
        ]
    )


@app.post("/api/demo/retry-storm")
def api_trigger_retry_storm() -> JSONResponse:
    """Regenerates the last 24h of traffic with a fresh retry storm in the
    final hour -- the Makefile's `make demo` target hits this."""
    summary = _seed_traffic(with_storm=True)
    return JSONResponse(summary)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
