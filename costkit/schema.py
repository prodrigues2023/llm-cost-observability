"""The cost-event schema — docs/contracts/cost-event-schema.md, implemented.

CostEvent is exactly the record the instrumentation boundary emits. Every
required field from the contract is a required constructor argument here;
there is no default that would let a producer skip one silently.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

UNKNOWN = "unknown"
UNATTRIBUTED_OUTCOME = "unattributed"


class CallStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


@dataclass(frozen=True)
class CostEvent:
    outcome_id: str
    feature: str
    tenant: str
    route: str
    model_tier: str
    prompt_version: str
    attempt_number: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    price_basis_id: str
    computed_cost: Decimal
    call_status: CallStatus
    timestamp: datetime
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        # docs/contracts/cost-event-schema.md's validity rules.
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")
        if self.input_tokens < 0 or self.output_tokens < 0 or self.cached_input_tokens < 0:
            raise ValueError("token counts must be >= 0")
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached_input_tokens must be <= input_tokens")
        if self.computed_cost < 0:
            raise ValueError("computed_cost must be >= 0")
        for required in (
            self.feature,
            self.tenant,
            self.route,
            self.model_tier,
            self.prompt_version,
            self.outcome_id,
        ):
            if not required:
                raise ValueError("required attribution dimension must be non-empty (use UNKNOWN/UNATTRIBUTED_OUTCOME explicitly, never blank)")
