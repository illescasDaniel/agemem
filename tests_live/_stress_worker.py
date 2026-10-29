"""Worker for test_concurrency: hammers one shared .agemem/local through the real Engine API."""
import json
import sys
import time
import uuid
from pathlib import Path

from agemem.engine import Engine
from agemem.notes.decider import FakeDecider

root, index, rounds, go = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
while not go.exists():            # start together, including the first open of both databases
    time.sleep(0.005)
engine = Engine(root, offline=True, decider=FakeDecider(
    lambda state, key, q: 0 if key in ("injection", "status", "multi_hop", "temporal", "missing_evidence") else 0.9))
sources, notes, started = [], [], time.time()
engine.index()
for n in range(rounds):
    token = uuid.uuid4().hex
    sources.append(engine.capture(f"worker {index} event {n} {token}", label=f"w{index}", shared=n % 2 == 0)["source_id"])
    result = engine.remember(f"Worker {index} fact {n} about topic-{token[:8]} {token[8:]}", sources[-1], shared=n % 2 == 0)
    if not result["rejected"]:
        notes.append(result["node_id"])
    engine.recall(f"worker {index} fact {n}")
engine.maintain()
engine.close()
print(json.dumps({"sources": sources, "notes": notes, "seconds": time.time() - started}))
