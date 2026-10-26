# Layered state + notes + original evidence

Hypothesis: current state, concise notes and original evidence have complementary roles.
The local `layered` treatment reserves up to 25% state and 25% manually written synthetic notes, then uses BM25 evidence.

```bash
python -m amem_lab.cli run --experiment experiments/05_layered_memory/experiment.json
python -m scripts.compose_pilot
```

`compose_pilot.py` separately combines cached outputs from the real bank, Jev and RAW-RAG pilots, with the same fixed
allocation. No paid calls are repeated. This is an implemented replay experiment, not a live agent memory service.
The remainder after state/notes is given to raw evidence. No question-type labels or gold inform selection.

Potential later product: memory-bank owns current git state; jev-mem owns durable notes and uncertainty; a source archive
supplies missing reasoning links. Host agents can promote validated repeated workflows into skills with evidence links.
Test a live bridge and conditional retrieval only after a broader evaluation; a false sufficient signal can otherwise
prevent necessary source retrieval.
