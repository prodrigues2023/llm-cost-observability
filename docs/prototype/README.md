# UI prototype

A self-contained, static **design mockup** of the cost-observability console — the interface the
concept implies, built as a docs-first design artifact, not the Milestone 3 application.

- **File:** [`index.html`](./index.html) — open it in a browser (no build, no dependencies).
- **What it shows:** cost attributed by feature/tenant/route, the headline unit **cost per successful
  outcome** beside total spend, an anomaly alert (a retry storm where unit cost climbs while spend
  stays flat), and a per-feature breakdown.
- **Design system:** the [shadcn/ui](https://ui.shadcn.com/) token system (zinc base), theme-aware
  (light/dark), with a chart palette validated for colour-vision accessibility.
- **Data is synthetic** and illustrative. This is a prototype, not a live product.

It exists to make the repository's thesis legible at a glance: a total-spend view hides a cost
regression that a cost-per-outcome view surfaces. See [the cost model](../cost-model.md) and
[the ADRs](../adr) for the reasoning behind what the screen shows.
