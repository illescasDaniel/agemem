# Tencent: standalone first, then optional bridges

Implemented and tested:

1. Real MemoryCore standalone gateway, local SQLite + FTS5, embedding disabled.
2. v3 conversation capture/search adapter on the same 18-question corpus, with extraction disabled.
3. One three-message synthetic L1 extraction through a capped local OpenAI gateway; both old Fabric and newer Ansible
   facts were extracted, including the replacement reason. Search for Atlas retrieved the old fact; searching Ansible
   retrieved the replacement, so retrieval coverage still matters even when extraction retained both.

This does not test Panel, Proxy, Wiki, CodeGraph, L2/L3 quality, team authorization or the native Jev persona gate.

## Lightweight source setup

Requires Node >=22.16 and npm; no Tencent Cloud account or managed database. Docker is optional. Full team UI/proxy
setup is a separate, larger deployment. Our actual source install resolved 621 npm packages; "standalone" still has
more operational overhead than markdown or the Python retrieval baselines.

```bash
python scripts/fetch_upstreams.py
# Run from amem root; keep credentials in the environment, not command literals.
export AMEM_ROOT="$PWD"
cd vendor/TencentDB-Agent-Memory/MemoryCore
npm install --ignore-scripts --no-audit --no-fund
export TDAI_GATEWAY_CONFIG="$AMEM_ROOT/experiments/06_tencent/standalone.json"
export TDAI_DATA_DIR="$AMEM_ROOT/.cache/tencent"
export TDAI_GATEWAY_API_KEY="$TENCENT_MEMORY_KEY"
export TDAI_LLM_API_KEY=unused-extraction-disabled
node --import tsx src/gateway/server.ts
```

In another terminal from amem root, with a nonempty TENCENT_MEMORY_KEY matching the gateway token:

```bash
export TENCENT_MEMORY_URL=http://127.0.0.1:18420
python -m amem_lab.cli run --experiment experiments/06_tencent/experiment.json --allow-api
```

v3 requires a Bearer header even when the optional gateway auth gate is disabled. The tested environment had working
FTS5; the adapter checks health and refuses a missing-FTS fallback. A dedicated loopback service is assumed; do not
point the test at a production instance. Each run uses distinct sessions and saves server-ID provenance.

## Generative extraction smoke test

Needs OPENAI_API_KEY, or adapt to a suitable local generative LLM. Jev cannot generate atomic memories by itself.
Run `python -m scripts.budgeted_llm_proxy` in a separate terminal (localhost:18421, max 4 calls/$0.02 reserved).
Use a copy of standalone.json with a DIFFERENT data directory/port, llm.baseUrl set to http://127.0.0.1:18421/v1,
extraction.enabled true, everyNConversations 2, and l1IdleTimeoutSeconds 2. Keep L2/persona timers high. Only capture
synthetic messages for this smoke test; inspect /v3/atomic/search afterward. Stop the core and proxy when finished.
The service already has native `memory.persona.triggerMode: jev` for L3 refresh decisions; this is still untested here.

Integration options: pair Tencent with memory-bank; expose L0 as a source archive to RAG; use its existing Jev gate;
or try the full proxy in a dedicated coding-agent profile. Avoid competing automatic injectors or syncing two
independent "current truth" stores until ownership/deletion/branch semantics are defined.

Upstream: https://github.com/TencentCloud/TencentDB-Agent-Memory
Pinned: 65730e979a5a590c54adc181ba8a375055410b84
