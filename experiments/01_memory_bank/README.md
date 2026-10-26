# Files first: memory-bank

Hypothesis: current focus/blockers/next steps are best read as small git-tracked files; older decisions can be searched.
`bank` loads current state in file order under the common budget. `bank-search` searches current and historical bank sections.
Neither is a complete autonomous implementation of the memory-bank skill: this tests read policies on an existing snapshot.

```bash
python -m amem_lab.cli run --experiment experiments/01_memory_bank/experiment.json
```

No API key, model download or service. Strengths: handoff, inspectable edits, branch context. Weakness: old decisions and
large state files can swamp the context; document discipline matters as much as retrieval. Review shrunk versus original
state as a separate treatment rather than silently rewriting the source snapshot.

Reference: https://github.com/illescasDaniel/memory-bank
