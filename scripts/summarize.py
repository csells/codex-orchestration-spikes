#!/usr/bin/env python3
"""Recompute credit-equivalent estimates from published full-tree telemetry."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATES = {
    "gpt-6-astra": {"input": 250, "cached": 25, "output": 1250},
    "gpt-6-sol": {"input": 50, "cached": 5, "output": 250},
    "gpt-6-luna": {"input": 2.5, "cached": 0.25, "output": 12.5},
    "gpt-5.6-terra": {"input": 50, "cached": 5, "output": 300},
}


def estimate(usage_by_model):
    result = {}
    for model, usage in usage_by_model.items():
        rate = RATES[model]  # Unknown pricing must fail rather than become free.
        inp, cached = usage["input_tokens"], usage["cached_input_tokens"]
        if not 0 <= cached <= inp: raise ValueError("Invalid cached-input subset")
        result[model] = ((inp-cached)*rate["input"] + cached*rate["cached"] + usage["output_tokens"]*rate["output"])/1_000_000
    return {"by_model": result, "total": sum(result.values())}


def main():
    rows = []
    for path in sorted((ROOT / "results").glob("*/telemetry.json")):
        report = json.loads(path.read_text())
        metadata_path = path.parent / "run.json"
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        root = next(t for t in report["threads"] if t["thread"] == "root")
        validation_path = path.parent / "validation.json"
        validation = json.loads(validation_path.read_text()) if validation_path.exists() else None
        rows.append({
            "run_id": path.parent.name, "task": metadata.get("task"), "policy": metadata.get("policy"),
            "elapsed_seconds": metadata.get("elapsed_seconds"), "resumed_session": bool(metadata.get("resume")),
            "estimate_is_cumulative_for_resumed_session": bool(metadata.get("resume")),
            "usage": report["total_usage"], "model_usage": report["usage_by_model"],
            "credit_estimate": estimate(report["usage_by_model"]),
            "workers": report["thread_count"]-1,
            "root_context_proxy": root["context_proxy"],
            "root_compactions": root["compaction_count"],
            "accounting_warnings": report["warnings"], "validation": validation,
        })
    output = {"rate_source": "https://learn.chatgpt.com/docs/pricing", "rates_checked_date": "2026-09-27",
              "rates_per_million_tokens_standard_speed": RATES,
              "caveat": "Published Standard credit-equivalent estimate, not measured subscription quota or API bill. Input cache is counted at its own rate; reasoning is already included in output. Resumed-session usage is cumulative: never sum successive session snapshots.",
              "runs": rows}
    (ROOT / "results/summary.json").write_text(json.dumps(output, indent=2)+"\n")
    for row in rows:
        print(f"{row['run_id']:32} credits={row['credit_estimate']['total']:.4f} workers={row['workers']} elapsed={row['elapsed_seconds']} quality={row['validation'] and row['validation'].get('passed')}")


if __name__ == "__main__":
    main()
