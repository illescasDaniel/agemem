"""Compose cached real Jev recall + bank + RAW-RAG, without repeating any API calls."""
import argparse
import json
import statistics
from pathlib import Path

from amem_lab.core import Hit, Retrieved, TOKEN, digest, load_data, pack, render, score, serialize


def read(path, method):
    run = json.loads(Path(path).read_text())
    if run["methods"][method]["status"] != "completed":
        raise ValueError(f"{method} did not complete")
    return run, {r["question_id"]: r for r in run["rows"] if r["method"] == method}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", default="reports/lexical.json")
    parser.add_argument("--memory", default="reports/jev-pilot.json")
    parser.add_argument("--raw", default="reports/raw-upstream.json")
    parser.add_argument("--data", default="data/coding_memory.json")
    parser.add_argument("--output", default="reports/composed-pilot.json")
    args = parser.parse_args()
    data, _ = load_data(args.data)
    bank_run, bank = read(args.bank, "bank")
    memory_run, memory = read(args.memory, "jevmem")
    raw_run, raw = read(args.raw, "raw-upstream")
    if any(r["dataset_sha256"] != digest(data) for r in (bank_run, memory_run, raw_run)):
        raise ValueError("Dataset hash mismatch")
    if len({r["budget_units"] for r in (bank_run, memory_run, raw_run)}) != 1:
        raise ValueError("Context budgets differ")
    budget = bank_run["budget_units"]
    questions = {q["id"]: q for q in data["questions"]}
    rows = []
    for qid in sorted(set(bank) & set(memory) & set(raw)):
        def hits(source):
            return [Hit(**h) for h in source[qid]["retrieved"]["hits"]]
        state = pack(hits(bank), budget // 4)
        notes = pack(hits(memory), budget // 4)
        used = sum(len(TOKEN.findall(render(h))) for h in [*state, *notes])
        evidence = [*state, *notes, *pack(hits(raw), budget - used)]
        result = Retrieved(evidence, metadata={"composition": "25% bank cap, 25% Jev cap, remaining raw",
                           "api_calls": 0, "mode": "cached replay; not a live routed implementation"})
        rows.append({"method": "bank-jev-raw", "question_id": qid, "kind": questions[qid]["kind"],
                     "project": questions[qid]["project"], **score(questions[qid], result),
                     "retrieved": serialize(result)})
    answerable = [r for r in rows if r["evidence_coverage"] is not None]
    result = {"schema_version": 1, "dataset_sha256": digest(data), "budget_units": budget,
              "manifest": data["manifest"], "methods": {"bank-jev-raw": {"status": "completed", "questions": len(rows),
              "evidence_coverage": statistics.mean(r["evidence_coverage"] for r in answerable),
              "all_evidence_rate": statistics.mean(r["all_evidence"] for r in answerable)}}, "rows": rows}
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["methods"]))


if __name__ == "__main__":
    main()
