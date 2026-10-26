# Exploratory retrieval run

Dataset SHA256: `9da7e11f73415d480bab7ad28766267bd7f2b9e06e6d4c1c66dd94da52ab64b0`
Context budget: 1800 regex units; not model tokens.

These scores measure presence of annotated passages after truncation, not answer correctness.

| Method | Status | Evidence coverage | All evidence | Mean context units |
|---|---|---:|---:|---:|
| bank | completed | 0.188 | 0.188 | 1208 |
| bank-search | completed | 0.438 | 0.438 | 1205 |

Unknown questions have no coverage score. Nonempty context is not automatically an incorrect answer.
Project/branch/time visibility is enforced by the shared harness, not credited to a backend.
First-query timings include model loading/building and cannot be read as steady-state latency.
