"""SQLite-backed storage for cost events and outcomes.

No cloud account, no external database -- ROADMAP.md's Milestone 3 local-
environment requirement. The schema mirrors docs/contracts/cost-event-schema.md
and docs/contracts/outcome-contract.md field for field; this module is
persistence only, it computes nothing the contracts didn't already define.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal

from costkit.outcome import Outcome, OutcomeStatus
from costkit.schema import CostEvent

_ATTRIBUTION_DIMENSIONS = {"feature", "tenant", "route", "model_tier", "prompt_version"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cost_events (
    event_id TEXT PRIMARY KEY,
    outcome_id TEXT NOT NULL,
    feature TEXT NOT NULL,
    tenant TEXT NOT NULL,
    route TEXT NOT NULL,
    model_tier TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_input_tokens INTEGER NOT NULL,
    price_basis_id TEXT NOT NULL,
    computed_cost TEXT NOT NULL,
    call_status TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cost_events_outcome ON cost_events(outcome_id);
CREATE INDEX IF NOT EXISTS idx_cost_events_timestamp ON cost_events(timestamp);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id TEXT PRIMARY KEY,
    feature TEXT NOT NULL,
    tenant TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    resolution_window_seconds REAL NOT NULL,
    status TEXT NOT NULL,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_outcomes_status ON outcomes(status);
"""


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _dt_or_none(value: str | None) -> datetime | None:
    return _dt(value) if value else None


class CostStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- writes -----------------------------------------------------

    def open_outcome(self, outcome: Outcome) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO outcomes
                (outcome_id, feature, tenant, opened_at, resolution_window_seconds, status, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                outcome.outcome_id,
                outcome.feature,
                outcome.tenant,
                outcome.opened_at.isoformat(),
                outcome.resolution_window.total_seconds(),
                outcome.status.value,
                outcome.resolved_at.isoformat() if outcome.resolved_at else None,
            ),
        )
        self._conn.commit()

    def resolve_outcome(self, outcome_id: str, status: OutcomeStatus, at: datetime) -> None:
        outcome = self.get_outcome(outcome_id)
        outcome.resolve(status, at)
        self._conn.execute(
            "UPDATE outcomes SET status = ?, resolved_at = ? WHERE outcome_id = ?",
            (outcome.status.value, at.isoformat(), outcome_id),
        )
        self._conn.commit()

    def sweep_abandoned(self, at: datetime) -> int:
        rows = self._conn.execute(
            "SELECT outcome_id, feature, tenant, opened_at, resolution_window_seconds, status, resolved_at "
            "FROM outcomes WHERE status = ?",
            (OutcomeStatus.PENDING.value,),
        ).fetchall()
        swept = 0
        for row in rows:
            outcome = self._row_to_outcome(row)
            if outcome.sweep_abandoned(at):
                self._conn.execute(
                    "UPDATE outcomes SET status = ?, resolved_at = ? WHERE outcome_id = ?",
                    (outcome.status.value, at.isoformat(), outcome.outcome_id),
                )
                swept += 1
        self._conn.commit()
        return swept

    def insert_cost_event(self, event: CostEvent) -> None:
        self._conn.execute(
            """
            INSERT INTO cost_events
                (event_id, outcome_id, feature, tenant, route, model_tier, prompt_version,
                 attempt_number, input_tokens, output_tokens, cached_input_tokens,
                 price_basis_id, computed_cost, call_status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.outcome_id,
                event.feature,
                event.tenant,
                event.route,
                event.model_tier,
                event.prompt_version,
                event.attempt_number,
                event.input_tokens,
                event.output_tokens,
                event.cached_input_tokens,
                event.price_basis_id,
                str(event.computed_cost),
                event.call_status.value,
                event.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    # --- reads --------------------------------------------------------

    def get_outcome(self, outcome_id: str) -> Outcome:
        row = self._conn.execute(
            "SELECT outcome_id, feature, tenant, opened_at, resolution_window_seconds, status, resolved_at "
            "FROM outcomes WHERE outcome_id = ?",
            (outcome_id,),
        ).fetchone()
        if row is None:
            raise KeyError(outcome_id)
        return self._row_to_outcome(row)

    @staticmethod
    def _row_to_outcome(row: tuple) -> Outcome:
        outcome_id, feature, tenant, opened_at, window_seconds, status, resolved_at = row
        return Outcome(
            outcome_id=outcome_id,
            feature=feature,
            tenant=tenant,
            opened_at=_dt(opened_at),
            resolution_window=timedelta(seconds=window_seconds),
            status=OutcomeStatus(status),
            resolved_at=_dt_or_none(resolved_at),
        )

    def total_spend(self, since: datetime | None = None) -> Decimal:
        query = "SELECT COALESCE(SUM(CAST(computed_cost AS REAL)), 0) FROM cost_events"
        params: tuple = ()
        if since is not None:
            query += " WHERE timestamp >= ?"
            params = (since.isoformat(),)
        (total,) = self._conn.execute(query, params).fetchone()
        return Decimal(str(total))

    def spend_and_unit_cost_by(
        self, dimension: str, since: datetime | None = None, until: datetime | None = None
    ) -> list[dict]:
        """Spend and cost-per-outcome, grouped by an attribution dimension.

        cost per outcome = attributed cost across every event whose outcome
        resolved `succeeded`, divided by the count of those outcomes --
        outcome-contract.md's formula, computed exactly, not approximated.

        `since`/`until` bound the window on either side -- both are needed
        to compute a baseline window that does not overlap a "recent"
        window being compared against it (see costkit.budgets.detect_anomalies).
        """
        if dimension not in _ATTRIBUTION_DIMENSIONS:
            raise ValueError(f"unknown dimension {dimension!r}, must be one of {_ATTRIBUTION_DIMENSIONS}")

        clauses = []
        params: list = []
        if since is not None:
            clauses.append("ce.timestamp >= ?")
            params.append(since.isoformat())
        if until is not None:
            clauses.append("ce.timestamp < ?")
            params.append(until.isoformat())
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        rows = self._conn.execute(
            f"""
            SELECT
                ce.{dimension} AS dim,
                SUM(CAST(ce.computed_cost AS REAL)) AS total_spend,
                COALESCE(SUM(CASE WHEN o.status = 'succeeded' THEN CAST(ce.computed_cost AS REAL) ELSE 0 END), 0)
                    AS attributed_to_succeeded,
                COUNT(DISTINCT CASE WHEN o.status = 'succeeded' THEN ce.outcome_id END) AS succeeded_outcomes,
                COUNT(DISTINCT ce.outcome_id) AS total_outcomes
            FROM cost_events ce
            LEFT JOIN outcomes o ON o.outcome_id = ce.outcome_id
            {where}
            GROUP BY dim
            ORDER BY total_spend DESC
            """,
            params,
        ).fetchall()

        results = []
        for dim, total_spend, attributed_to_succeeded, succeeded_outcomes, total_outcomes in rows:
            cost_per_outcome = (
                attributed_to_succeeded / succeeded_outcomes if succeeded_outcomes else None
            )
            results.append(
                {
                    dimension: dim,
                    "total_spend": round(total_spend, 6),
                    "succeeded_outcomes": succeeded_outcomes,
                    "total_outcomes": total_outcomes,
                    "cost_per_outcome": round(cost_per_outcome, 6) if cost_per_outcome is not None else None,
                }
            )
        return results

    def cost_per_outcome_timeseries(self, dimension: str, dim_value: str, bucket_seconds: int, since: datetime) -> list[dict]:
        """Bucketed cost-per-outcome for one slice -- what an anomaly detector watches."""
        if dimension not in _ATTRIBUTION_DIMENSIONS:
            raise ValueError(f"unknown dimension {dimension!r}")

        rows = self._conn.execute(
            f"""
            SELECT
                CAST((julianday(ce.timestamp) - julianday(?)) * 86400 / ? AS INTEGER) AS bucket,
                SUM(CASE WHEN o.status = 'succeeded' THEN CAST(ce.computed_cost AS REAL) ELSE 0 END) AS attributed_cost,
                COUNT(DISTINCT CASE WHEN o.status = 'succeeded' THEN ce.outcome_id END) AS succeeded_outcomes
            FROM cost_events ce
            LEFT JOIN outcomes o ON o.outcome_id = ce.outcome_id
            WHERE ce.{dimension} = ? AND ce.timestamp >= ?
            GROUP BY bucket
            ORDER BY bucket
            """,
            (since.isoformat(), bucket_seconds, dim_value, since.isoformat()),
        ).fetchall()

        out = []
        for bucket, attributed_cost, succeeded_outcomes in rows:
            bucket_start = since + timedelta(seconds=bucket * bucket_seconds)
            cost_per_outcome = attributed_cost / succeeded_outcomes if succeeded_outcomes else None
            out.append(
                {
                    "bucket_start": bucket_start.isoformat(),
                    "cost_per_outcome": round(cost_per_outcome, 6) if cost_per_outcome is not None else None,
                    "succeeded_outcomes": succeeded_outcomes,
                }
            )
        return out

    def unattributed_event_count(self, since: datetime | None = None) -> int:
        from costkit.schema import UNATTRIBUTED_OUTCOME, UNKNOWN

        query = (
            "SELECT COUNT(*) FROM cost_events WHERE "
            "feature = ? OR tenant = ? OR route = ? OR model_tier = ? OR prompt_version = ? OR outcome_id = ?"
        )
        params: list = [UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN, UNKNOWN, UNATTRIBUTED_OUTCOME]
        if since is not None:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        (count,) = self._conn.execute(query, params).fetchone()
        return count

    def recent_events(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT event_id, outcome_id, feature, tenant, route, model_tier, prompt_version, "
            "attempt_number, input_tokens, output_tokens, cached_input_tokens, computed_cost, "
            "call_status, timestamp FROM cost_events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        columns = [
            "event_id", "outcome_id", "feature", "tenant", "route", "model_tier", "prompt_version",
            "attempt_number", "input_tokens", "output_tokens", "cached_input_tokens", "computed_cost",
            "call_status", "timestamp",
        ]
        return [dict(zip(columns, row)) for row in rows]

    def outcome_status_counts(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT status, COUNT(*) FROM outcomes GROUP BY status").fetchall()
        return {status: count for status, count in rows}
