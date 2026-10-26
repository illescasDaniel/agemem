# Actual jev-mem

Hypothesis: typed relevance, graph relations, consolidation and sufficiency reduce context while retaining useful facts.
Use the real installed jev-mem Writer, Consolidator and Retriever; no FakeDecider or heuristic substitute is scored.

```bash
python -m amem_lab.cli run --methods jevmem --project controlled --questions controlled-current,controlled-historical,controlled-rename-chain,controlled-handoff,controlled-unknown --allow-api --output reports/jev-pilot.json
```

Requires TYPESAFE_API_KEY or JEV_API_KEY, or a compatible JEVMEM_BASE_URL. API values are never stored. Default session caps
are 32 calls and 80k input tokens, with retries disabled. See docs/EVALUATION.md for the bounded configuration. Do not
run the complete srxy corpus through this profile without a new cost estimate and source-data egress permission.

SQLite is in RAM, source notes retain IDs and dates, and rejected evidence remains in the denominator. Original current
state and quoted injection are deliberately sent in the synthetic pilot to exercise actual write rejection. The service
is allowed to say insufficient; real results are reported without a degraded fallback. Branch visibility is supplied
by the harness and must not be interpreted as proof of native branch behavior.
