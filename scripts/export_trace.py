#!/usr/bin/env python3
"""Export task evidence, excluding instruction envelopes and reasoning content."""
import argparse
import hashlib
import json
from pathlib import Path
from telemetry import _read_rollout, sanitize


def export(root_id, home, workspace=None):
    sessions = {}
    for path in Path(home, "sessions").rglob("rollout*.jsonl"):
        meta, events, malformed = _read_rollout(path)
        if meta:
            source = meta.get("source")
            parent = source.get("subagent", {}).get("thread_spawn", {}).get("parent_thread_id") if isinstance(source, dict) else None
            sessions[meta["id"]] = (meta, parent, events)
    members = {root_id}
    while True:
        expanded = members | {sid for sid, (_, parent, _) in sessions.items() if parent in members}
        if members == expanded: break
        members = expanded
    if root_id not in sessions: raise ValueError("Missing root")
    ordered = [root_id] + sorted(members-{root_id}, key=lambda sid: (sessions[sid][0].get("timestamp", ""), sid))
    labels = {sid: "root" if i == 0 else f"worker_{i}" for i, sid in enumerate(ordered)}
    result = []
    keep = {"function_call", "function_call_output", "custom_tool_call", "custom_tool_call_output", "agent_message"}
    for sid in ordered:
        meta, parent, events = sessions[sid]
        active = False
        for event in events:
            kind, payload = event.get("type"), event.get("payload", {})
            if kind == "session_meta" and payload.get("id") == sid:
                active = True
                data = {"parent": labels.get(parent)}
            elif not active: continue
            elif kind == "turn_context":
                data = {"model": payload.get("model"), "effort": payload.get("effort")}
            elif kind == "token_usage_record" and payload.get("thread_id") == sid:
                data = {"response_hash": hashlib.sha256(payload["response_id"].encode()).hexdigest()[:16], "usage": payload["usage"]}
            elif kind == "response_item" and (payload.get("type") in keep or (payload.get("type") == "message" and payload.get("role") == "assistant" and payload.get("phase") in ["commentary", "final_answer"])):
                data = payload
            elif kind == "compacted":
                data = {"compaction_marker": True}
            else: continue
            result.append({"timestamp": event.get("timestamp"), "thread": labels[sid], "kind": kind, "payload": data})
    prefixes = tuple(str(Path(x).resolve()) for x in [workspace, home, Path(__file__).resolve().parents[2]] if x)
    return sanitize(result, prefixes)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root_id")
    p.add_argument("home", type=Path)
    p.add_argument("--workspace", type=Path)
    a = p.parse_args()
    for row in export(a.root_id, a.home, a.workspace): print(json.dumps(row))
