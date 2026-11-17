# Validation record · 17 November 2026

The local build and `verify.py` passed against MongoDB. A Power BI DAX query independently returned the same counts from the live semantic model.

| Metric | Python / MongoDB | Power BI DAX |
|---|---:|---:|
| Products | 25,209 | 25,209 |
| Raw usable | 10,391 | 10,391 |
| Usable after validation | 10,388 | 10,388 |
| Screen eligible | 6,455 | 6,455 |
| Flagged among eligible | 6,185 | 6,185 |
| Within proxy thresholds | 270 | 270 |
| Insufficient screen data | 18,754 | 18,754 |

Source SHA-256: `9007b7a48fe9bc129e6a90a6fc7dfb4dfdcb6a72f53b3a3aabc74eda0d5d1951`.

Checks cover all 25,209 unique barcodes, source/export row parity, screen eligibility and flag invariants, MongoDB collection counts, and the `quality_overview` aggregate. The verified raw usable share is **41.2%**. The screen is a consumer awareness proxy and does not establish legal HFSS compliance.

The DAX check used:

```dax
EVALUATE ROW(
  "Products", [Total Products],
  "Raw usable", [Raw Usable Products],
  "Normalized usable", [Normalized Usable Products],
  "Screen eligible", [Screen Eligible Products],
  "Flagged", [Flagged Products],
  "Within thresholds", [Within Proxy Thresholds],
  "Insufficient", [Insufficient Data Products]
)
```
