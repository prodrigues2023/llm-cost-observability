# Roadmap

Four milestones. Each ships something usable on its own.

Track these as GitHub Milestones.

---

## Milestone 1 — Design (docs only)

**Goal:** a reader understands why cost must be attributed at the call and measured per outcome,
before any code.

| Issue | Deliverable |
| --- | --- |
| Write context document | Problem, users, scope, explicit non-goals |
| Cost model | What drives cost, and spend versus waste |
| Attribution dimensions | The tags every cost event carries and why |
| Instrumentation diagrams | The single boundary and the attribution flow |
| ADR-0001 | Record architecture decisions in ADRs |
| ADR-0002 | Attribute cost at the call, tagged with dimensions |
| ADR-0003 | The unit is cost per successful outcome |
| ADR-0004 | Instrument at one boundary, not every call site |
| ADR-0005 | Budgets and anomaly alerts are first-class |

**Exit criteria:** a reader can explain why the bill is the wrong instrument and what to measure
instead, and every decision traces to attribution-at-the-source.

---

## Milestone 2 — Contracts

**Goal:** the formats are specified, so a producer and a dashboard integrate consistently.

| Issue | Deliverable | Status |
| --- | --- | --- |
| Cost-event schema | Tokens, price basis, dimensions, timestamp, outcome | Done — [cost-event-schema.md](./docs/contracts/cost-event-schema.md) |
| Outcome contract | What marks a call part of a successful task versus waste | Done — [outcome-contract.md](./docs/contracts/outcome-contract.md) |
| Pricing abstraction | How a token count becomes a cost without hard-coding a provider | Done — [pricing-abstraction.md](./docs/contracts/pricing-abstraction.md) |
| ADR-0006 | Cost-event schema and pricing abstraction | Done — [0006](./docs/adr/0006-cost-event-schema-and-pricing-abstraction.md) |

**Exit criteria met** — the three contracts compose rather than restating each other: the
cost-event schema's `outcome_id` is exactly the outcome contract's correlation key, and its
`price_basis_id` is exactly the pricing abstraction's rate-table reference. A reviewer checks a
Milestone 3 producer against the three documents field by field, the same test named in
[docs/contracts/README.md](./docs/contracts/README.md).

Backed by [ADR-0006](./docs/adr/0006-cost-event-schema-and-pricing-abstraction.md).

---

## Milestone 3 — Reference implementation

**Goal:** `make up` runs a boundary that emits cost events and a dashboard that attributes them.

| Issue | Deliverable |
| --- | --- |
| Instrumentation boundary | Capture tokens and dimensions at one pass-through point |
| Cost event pipeline | Enrich with price, store, aggregate |
| Attribution dashboard | Spend and unit cost by feature, tenant, route |
| Budget and alerting | A budget per dimension and an anomaly alert |
| Local environment | One command, stubbed model, synthetic traffic, no cloud account |

**Exit criteria:** a first-time reader sees spend attributed to a feature and a tenant, and a unit
cost that rises when retries are injected.

---

## Milestone 4 — Validation

**Goal:** prove the alerts and the unit cost catch the failures that a bill hides.

| Issue | Deliverable |
| --- | --- |
| Cost regression drill | Swap in a pricier path; assert the anomaly alert fires |
| Retry storm | Inject failures and retries; assert cost-per-outcome rises while spend looks flat |
| Context bloat | Pad context; show the waste as unit cost, not just total spend |
| Attribution accuracy | Reconcile attributed cost against the total; assert they agree |

**Exit criteria:** a cost regression and a retry storm are both caught by the design in minutes, and
the attributed total reconciles with the bill.
