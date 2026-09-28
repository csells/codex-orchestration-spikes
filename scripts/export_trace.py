#!/usr/bin/env python3
"""Export task evidence, excluding instruction envelopes and reasoning content.

Opaque encrypted_content fields and observed gAAAA-prefixed provider ciphertext
are replaced by SHA-256/character-count markers, without decoding. Plaintext
CommandExecution and FileChange completion events preserve what actually ran
and its recorded result per thread, even when a delegation brief is opaque.

Limits: omitted encrypted briefs cannot be reviewed or reconstructed here.
This covers the observed provider format, not arbitrary secret detection.
Execution events and tool outputs can overlap, and output can be truncated at
the source. They are behavioral evidence, not additional usage charges. Usage
records must be deduplicated by response_hash, including compaction records.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from telemetry import _read_rollout, sanitize


OPAQUE_PROVIDER_TOKEN = re.compile(r"gAAAA[A-Za-z0-9_-]{80,}={0,2}")
EXECUTION_FIELDS = {
    "CommandExecution": ("type", "id", "command", "cwd", "source", "status",
                         "stdout", "stderr", "aggregated_output", "exit_code", "duration"),
    "FileChange": ("type", "id", "changes", "status", "stdout", "stderr"),
}


def _opaque_marker(value):
    return {"redacted": "opaque_provider_content", "sha256": hashlib.sha256(value.encode()).hexdigest(),
            "length_chars": len(value)}


def redact_opaque(value):
    """Remove known opaque provider strings while retaining identity and length."""
    if isinstance(value, dict):
        return {key: (_opaque_marker(item) if key == "encrypted_content" and isinstance(item, str)
                      else redact_opaque(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_opaque(item) for item in value]
    if isinstance(value, str):
        def replace(match):
            marker = _opaque_marker(match.group(0))
            return f"<opaque-provider-content sha256={marker['sha256']} chars={marker['length_chars']}>"
        return OPAQUE_PROVIDER_TOKEN.sub(replace, value)
    return value


def _sanitize_paths(value, prefixes):
    # FileChange.changes uses absolute filenames as dictionary keys.
    if isinstance(value, dict):
        return {sanitize(key, prefixes): _sanitize_paths(item, prefixes) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_paths(item, prefixes) for item in value]
    return sanitize(value, prefixes)


def export(root_id, home, workspace=None):
    sessions = {}
    for path in Path(home, "sessions").rglob("rollout*.jsonl"):
        meta, events, malformed = _read_rollout(path)
        if meta:
            source = meta.get("source")
            subagent = source.get("subagent") if isinstance(source, dict) else None
            spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
            parent = spawn.get("parent_thread_id") if isinstance(spawn, dict) else None
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
            elif kind == "event_msg" and payload.get("type") == "item_completed":
                item = payload.get("item")
                if not isinstance(item, dict) or item.get("type") not in EXECUTION_FIELDS:
                    continue
                if payload.get("thread_id") not in (None, sid):
                    continue
                fields = EXECUTION_FIELDS[item["type"]]
                data = {key: item[key] for key in fields if key in item}
                kind = "execution_event"
            elif kind == "compacted":
                nested = payload.get("latest_token_usage_record")
                if isinstance(nested, dict) and nested.get("thread_id") == sid and nested.get("response_id"):
                    # Compaction usage can exist only here. Preserve its response
                    # hash so readers can deduplicate it against a standalone record.
                    result.append({"timestamp": event.get("timestamp"), "thread": labels[sid],
                                   "kind": "token_usage_record", "payload": {
                                       "response_hash": hashlib.sha256(nested["response_id"].encode()).hexdigest()[:16],
                                       "usage": nested["usage"],
                                   }})
                data = {"compaction_marker": True}
            else: continue
            result.append({"timestamp": event.get("timestamp"), "thread": labels[sid], "kind": kind, "payload": data})
    prefixes = tuple(str(Path(x).resolve()) for x in [workspace, home, Path(__file__).resolve().parents[2]] if x)
    return _sanitize_paths(redact_opaque(result), prefixes)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("root_id")
    p.add_argument("home", type=Path)
    p.add_argument("--workspace", type=Path)
    a = p.parse_args()
    for row in export(a.root_id, a.home, a.workspace): print(json.dumps(row))
