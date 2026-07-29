"""The instrumentation boundary — ADR-0004, implemented.

The one place every call passes through. It reads dimensions from context
(costkit.context), calls the stub model, applies the price basis, and
writes exactly one CostEvent. Call sites never compute cost or touch the
store directly -- this module is the only thing that does.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from costkit import context
from costkit.pricing import RateTable
from costkit.schema import CallStatus, CostEvent
from costkit.store import CostStore
from costkit.stub_model import ModelCallError, StubModelClient


class CallFailedError(Exception):
    """Raised to the call site after the failed call's cost event was recorded."""


@dataclass(frozen=True)
class BoundaryResult:
    event: CostEvent
    output_tokens: int


class InstrumentationBoundary:
    def __init__(self, model: StubModelClient, rates: RateTable, store: CostStore) -> None:
        self._model = model
        self._rates = rates
        self._store = store

    def call(
        self, model_tier: str, attempt_number: int = 1, at: datetime | None = None
    ) -> BoundaryResult:
        """Makes one model call and emits exactly one cost event for it.

        Dimensions come from costkit.context, per ADR-0004: the call site's
        only job is to have set them, not to pass them here. `at` defaults
        to now; it is overridable so synthetic/historical traffic can be
        generated with realistic timestamps instead of wall-clock time.
        """
        dims = context.current()
        now = at or datetime.now(timezone.utc)
        basis = self._rates.lookup(model_tier, now)

        try:
            response = self._model.call(model_tier)
        except ModelCallError as exc:
            # Billed for the input and whatever partial output the
            # provider already processed, per stub_model.py's
            # ModelCallError -- a failed call is not free.
            cost = basis.compute_cost(exc.input_tokens, exc.partial_output_tokens, 0)
            event = CostEvent(
                outcome_id=dims.outcome_id,
                feature=dims.feature,
                tenant=dims.tenant,
                route=dims.route,
                model_tier=model_tier,
                prompt_version=dims.prompt_version,
                attempt_number=attempt_number,
                input_tokens=exc.input_tokens,
                output_tokens=exc.partial_output_tokens,
                cached_input_tokens=0,
                price_basis_id=basis.price_basis_id,
                computed_cost=cost,
                call_status=CallStatus.ERROR,
                timestamp=now,
            )
            self._store.insert_cost_event(event)
            raise CallFailedError(str(exc)) from exc

        cost = basis.compute_cost(
            response.input_tokens, response.output_tokens, response.cached_input_tokens
        )
        event = CostEvent(
            outcome_id=dims.outcome_id,
            feature=dims.feature,
            tenant=dims.tenant,
            route=dims.route,
            model_tier=model_tier,
            prompt_version=dims.prompt_version,
            attempt_number=attempt_number,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cached_input_tokens=response.cached_input_tokens,
            price_basis_id=basis.price_basis_id,
            computed_cost=cost,
            call_status=CallStatus.OK,
            timestamp=now,
        )
        self._store.insert_cost_event(event)
        return BoundaryResult(event=event, output_tokens=response.output_tokens)
