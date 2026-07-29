"""docs/contracts/cost-event-schema.md, exercised for real."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from costkit.schema import CallStatus, CostEvent


def make_event(**overrides):
    defaults = {
        "outcome_id": "task-1",
        "feature": "checkout-assistant",
        "tenant": "acme",
        "route": "/chat",
        "model_tier": "large",
        "prompt_version": "v3",
        "attempt_number": 1,
        "input_tokens": 1000,
        "output_tokens": 200,
        "cached_input_tokens": 0,
        "price_basis_id": "large-2026-01",
        "computed_cost": Decimal("0.006"),
        "call_status": CallStatus.OK,
        "timestamp": datetime(2026, 6, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return CostEvent(**defaults)


def test_valid_event_constructs():
    event = make_event()
    assert event.event_id
    assert event.call_status == CallStatus.OK


def test_event_id_unique_per_instance():
    a, b = make_event(), make_event()
    assert a.event_id != b.event_id


def test_cached_tokens_cannot_exceed_input_tokens():
    with pytest.raises(ValueError):
        make_event(input_tokens=10, cached_input_tokens=11)


def test_negative_tokens_rejected():
    with pytest.raises(ValueError):
        make_event(input_tokens=-1)


def test_attempt_number_must_be_positive():
    with pytest.raises(ValueError):
        make_event(attempt_number=0)


def test_negative_cost_rejected():
    with pytest.raises(ValueError):
        make_event(computed_cost=Decimal("-0.01"))


@pytest.mark.parametrize("field_name", ["feature", "tenant", "route", "model_tier", "prompt_version", "outcome_id"])
def test_blank_required_dimension_rejected(field_name):
    with pytest.raises(ValueError):
        make_event(**{field_name: ""})
