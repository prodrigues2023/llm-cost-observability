# The console

Milestone 3's reference implementation: `costkit/` is the instrumentation boundary, pricing
abstraction, and outcome state machine from [docs/contracts](../docs/contracts), implemented and
tested for real; `console/` is the attribution dashboard over it.

| Piece | File | Implements |
| --- | --- | --- |
| Cost-event schema | [costkit/schema.py](../costkit/schema.py) | [cost-event-schema.md](../docs/contracts/cost-event-schema.md) |
| Outcome state machine | [costkit/outcome.py](../costkit/outcome.py) | [outcome-contract.md](../docs/contracts/outcome-contract.md) |
| Pricing abstraction | [costkit/pricing.py](../costkit/pricing.py) | [pricing-abstraction.md](../docs/contracts/pricing-abstraction.md) |
| Instrumentation boundary | [costkit/boundary.py](../costkit/boundary.py) | [ADR-0004](../docs/adr/0004-instrument-at-the-boundary.md) |
| Budgets + anomaly detection | [costkit/budgets.py](../costkit/budgets.py) | [ADR-0005](../docs/adr/0005-budgets-and-alerts.md) |
| Stubbed model + synthetic traffic | [costkit/stub_model.py](../costkit/stub_model.py), [costkit/traffic.py](../costkit/traffic.py) | ROADMAP.md's "no cloud account" requirement |
| Dashboard | [console/app.py](./app.py), [console/static/index.html](./static/index.html) | Attribution + budgets + anomalies over the real store |

## Running it

```bash
make up      # docker compose up --build; console at http://localhost:8000
make down
make console # runs it directly with Python, no Docker
make test    # pytest — schema/outcome/pricing/boundary/traffic/budgets, all real
```

No API key, no cloud account, no network call: `costkit.stub_model.StubModelClient` stands in for
a provider, and `costkit.traffic.generate_traffic` seeds 24 hours of synthetic tasks through the
real boundary on startup — everything the console shows is aggregated from cost events the stub
model actually produced, not canned sample data.

## What "stubbed" means here, precisely

- Token counts, cache hits, and failures are drawn from a configurable `ModelProfile` — random but
  bounded, not scripted to produce a specific chart.
- A failed call still bills for the input (and often partial output) tokens the stub says a
  provider had already processed before erroring, per
  [cost-event-schema.md](../docs/contracts/cost-event-schema.md)'s note that a failed call is not
  free — this is what makes retry waste show up as real cost in the numbers, not an assumption.
- The **"Trigger retry-storm demo"** button on the console calls `POST /api/demo/retry-storm`,
  which reseeds the last 24 hours with an elevated failure rate for `checkout-assistant` in the
  final hour — reproducing ROADMAP.md's Milestone 3 exit criterion ("a unit cost that rises when
  retries are injected") on demand, the same mechanism
  [k8s-observability-stack](https://github.com/prodrigues2023/k8s-observability-stack)'s `make demo`
  uses to force a fault.

## What Milestone 3 does and does not claim

- **Real:** the schema, outcome state machine, pricing formula, boundary, and budget/anomaly
  detectors are genuine, tested implementations — 36 tests, including one that proves a retried
  task's cost per outcome is measurably higher than a clean task's, not asserted from a fixture.
- **Stubbed:** the model itself. No real LLM provider is called; swapping `StubModelClient` for a
  real provider client is the only change described in
  [pricing-abstraction.md](../docs/contracts/pricing-abstraction.md) and
  [ADR-0004](../docs/adr/0004-instrument-at-the-boundary.md) a real deployment would need to make.
- **Simplified anomaly detection.** `costkit.budgets.detect_anomalies` is a ratio-over-a-rolling-
  baseline check, not a statistical model — [ADR-0005](../docs/adr/0005-budgets-and-alerts.md)
  and [budgets.py](../costkit/budgets.py)'s docstring both flag this: distinguishing a legitimate
  traffic swing from a regression is explicitly out of scope for this reference implementation.
- **No persistence.** The console reseeds fresh on every restart (SQLite in-memory); set
  `COST_DB_PATH` to a file path to keep data across restarts instead.
