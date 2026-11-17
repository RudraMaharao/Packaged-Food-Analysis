# Workflow and automation

The source snapshot is versioned with the project. A GitHub Actions workflow rebuilds MongoDB collections and all six exports on every push or pull request, then runs the consistency checks. Power BI refresh and publication remain owner-controlled in the workspace.

```mermaid
flowchart LR
    A[PackSense / Open Food Facts<br/>India snapshot · 25,209 rows] --> B[Source checksum<br/>and unique barcode check]
    B --> C[Python cleaning<br/>unit conversion · missingness flags]
    C --> D[(MongoDB<br/>raw_products + products)]
    D --> E{Six aggregation pipelines}
    E --> E1[Quality overview]
    E --> E2[Category profile]
    E --> E3[Brand scorecard]
    E --> E4[Screening drivers]
    E --> E5[Nutri-Score comparison]
    E --> E6[Review queue]
    C --> F[Power BI-ready product CSV]
    E1 & E2 & E3 & E4 & E5 & E6 --> G[Aggregate CSV exports]
    F --> H[Power Query + DAX model]
    G --> H
    H --> I[3-page interactive report<br/>Overview · Data gaps · Read the label]
    D --> J[verify.py<br/>source / export / Mongo parity]
    F --> J
    G --> J
    K[GitHub Actions<br/>push · pull request · manual] --> C
    K --> J
    J --> L{Pass?}
    L -->|yes| M[Verified analysis artifacts]
    L -->|no| N[Fail CI and inspect data]
```

## Rebuild sequence

1. `build.py` checks barcode uniqueness, cleans fields, and replaces the two MongoDB collections.
2. `aggregations.py` runs six named pipelines and writes aggregate CSVs.
3. `build.py` writes the full product export and computed metrics.
4. `verify.py` checks the source hash, row and barcode parity, screen invariants, MongoDB counts, and aggregation totals.
5. Power BI uses `power_query.m` and the DAX measures for interactive exploration. The dashboard includes visible caveats because total sugar and total fat only approximate the added values required by the cited guidelines.
