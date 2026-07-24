# Instrumentation and attribution flow

Two diagrams: where cost is captured, and how a tagged call becomes an attributed, alertable metric.

## The single boundary

Every model call passes through one instrumentation boundary
([ADR-0004](../adr/0004-instrument-at-the-boundary.md)). Call sites propagate dimensions; the boundary
turns a call into a cost event. Nothing computes cost at a call site.

```mermaid
graph TB
    fa["Feature A call site"] -->|"propagate feature, tenant, route, prompt version"| b
    fb["Feature B call site"] -->|"propagate dimensions"| b
    fc["Feature C call site"] -->|"propagate dimensions"| b

    b["Instrumentation boundary<br/><i>one place every call passes through</i>"]
    b --> model["Model provider"]
    model -->|"token counts"| b
    b -->|"tokens × price basis + dimensions"| ev["Cost event<br/><i>tagged, at the call</i>"]

    ev --> store["Cost store"]
    store --> dash["Dashboard<br/><i>spend + unit cost, sliced</i>"]
    store --> alert["Budgets + anomaly alerts"]

    classDef site fill:#438dd5,stroke:#2e6295,color:#fff
    classDef boundary fill:#e9a13b,stroke:#b87a26,color:#000
    classDef data fill:#08427b,stroke:#052e56,color:#fff
    class fa,fb,fc,model site
    class b boundary
    class ev,store,dash,alert data
```

The boundary is the load-bearing element: capture is complete and uniform because every call goes
through it ([ADR-0004](../adr/0004-instrument-at-the-boundary.md)), and attribution is exact because
the dimensions are read from the propagated context at that moment
([ADR-0002](../adr/0002-attribute-at-the-call.md)), never reconstructed later.

## From a call to an alertable regression

The sequence that catches a retry storm a total-spend chart would sleep through.

```mermaid
sequenceDiagram
    participant App as Call site
    participant B as Boundary
    participant S as Cost store
    participant A as Alerting

    App->>B: model call, with feature and tenant in context
    B->>B: capture tokens, apply price basis, attach dimensions
    B->>S: cost event, tagged, outcome pending
    Note over S: task later marked succeeded or failed
    S->>S: cost per outcome = attributed cost over successful outcomes
    S->>A: per-outcome metric per dimension
    alt unit cost within budget and baseline
        A-->>A: no alert
    else unit cost breaches budget or spikes vs baseline
        A-->>App: page — cost regression on this feature and route
        Note over A: total spend may look flat while unit cost has doubled
    end
```

The point the sequence makes: the alert fires on **cost per outcome**
([ADR-0003](../adr/0003-cost-per-outcome.md)), so a wave of retries — which leaves total spend
looking roughly flat while the successful-outcome denominator shrinks — pushes the unit cost up and
pages someone ([ADR-0005](../adr/0005-budgets-and-alerts.md)). A dashboard watching only the total
would show nothing worth looking at.
