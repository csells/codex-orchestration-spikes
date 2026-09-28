#!/usr/bin/env python3
"""Read Codex 0.156.1 rollout telemetry without publishing conversation content.

Usage: telemetry.py collect ROOT_THREAD_ID ROLLOUT_DIRECTORY [MORE_DIRECTORIES]
       telemetry.py quota [--codex-home PRIVATE_DIRECTORY]

Response usage is deduplicated across the full descendant tree. Historical
records copied into forks are excluded by their actual thread_id. Context
figures are provider input-token footprints, not measurements of the next
request or exact live context occupancy. No prompts, outputs, account IDs,
response IDs, raw thread IDs, or local paths appear in the returned report.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
from typing import Any


TOKEN_FIELDS = (
    "input_tokens", "cached_input_tokens", "cache_write_input_tokens",
    "output_tokens", "reasoning_output_tokens", "total_tokens",
)


def _usage(values: dict[str, Any] | None) -> dict[str, int]:
    values = values or {}
    return {key: int(values.get(key, 0) or 0) for key in TOKEN_FIELDS}


def _add(target: dict[str, int], values: dict[str, int]) -> None:
    for key in TOKEN_FIELDS:
        target[key] = target.get(key, 0) + values.get(key, 0)


def _event_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def sanitize(value: Any, private_prefixes: tuple[str, ...] = ()) -> Any:
    """Defense in depth for public text; structured telemetry uses allowlists.

    This is not a general secret scanner. Do not pass raw authentication files,
    environment dumps, prompts, or model transcripts to this function.
    """
    if isinstance(value, dict):
        return {key: sanitize(item, private_prefixes) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item, private_prefixes) for item in value]
    if isinstance(value, str):
        for prefix in sorted(private_prefixes, key=len, reverse=True):
            if prefix:
                value = value.replace(prefix, "<private-path>")
        value = re.sub(r"/Users/[^/\s\"']+", "<user-home>", value)
        value = re.sub(r"/home/[^/\s\"']+", "<user-home>", value)
    return value


def _quota_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    """Only public experimental observations, never account/reset-credit IDs."""
    def field(obj: dict[str, Any], camel: str, snake: str) -> Any:
        return obj.get(camel, obj.get(snake))

    result: dict[str, Any] = {}
    for name in ("primary", "secondary"):
        window = raw.get(name)
        if isinstance(window, dict):
            result[name] = {
                "used_percent": field(window, "usedPercent", "used_percent"),
                "window_minutes": field(window, "windowDurationMins", "window_minutes"),
                "resets_at": field(window, "resetsAt", "resets_at"),
            }
    result["limit_id"] = field(raw, "limitId", "limit_id")
    result["spend_control_reached"] = field(raw, "spendControlReached", "spend_control_reached")
    return result


def quota(codex_home: str | Path | None = None, timeout: float = 30,
          codex: str = "codex") -> dict[str, Any]:
    """Read subscription percentages through app-server; no model request.

    App-server still needs writable local state. Use a private, writable
    CODEX_HOME or execute with normal Codex-home filesystem permissions.
    """
    env = os.environ.copy()
    if codex_home is not None:
        env["CODEX_HOME"] = str(codex_home)
    process = subprocess.Popen(
        [codex, "app-server", "--stdio", "-c", "features.plugins=false",
         "-c", "features.apps=false"], env=env, text=True, bufsize=1,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    messages: queue.Queue[Any] = queue.Queue()

    def read() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except json.JSONDecodeError:
                continue
        messages.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def rpc(request_id: int, method: str, params: Any = None) -> Any:
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        assert process.stdin is not None
        try:
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
        except BrokenPipeError as exc:
            raise RuntimeError("Codex app-server exited before responding; check writable state directory") from exc
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Codex app-server timed out: {method}")
            try:
                message = messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f"Codex app-server timed out: {method}") from exc
            if message is None:
                raise RuntimeError("Codex app-server exited; check writable state directory")
            if message.get("id") != request_id:
                continue
            if "error" in message:
                # Error strings may contain private local paths. Report only code.
                raise RuntimeError(f"Codex RPC {method} failed with code {message['error'].get('code')}")
            return message.get("result", {})

    try:
        rpc(1, "initialize", {
            "clientInfo": {"name": "orchestration-spikes", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True},
        })
        result = rpc(2, "account/rateLimits/read", {})
        buckets = result.get("rateLimitsByLimitId") or {}
        if not buckets and isinstance(result.get("rateLimits"), dict):
            buckets = {"default": result["rateLimits"]}
        return {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "buckets": {key: _quota_snapshot(value) for key, value in buckets.items()},
            "caveat": "Account-wide, potentially rounded/delayed percentages; concurrent activity prevents per-run attribution.",
        }
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=1)


def _read_rollout(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]], int]:
    events = []
    malformed = 0
    with path.open() as stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1  # An active transcript can have an unfinished final line.
                continue
            if isinstance(event, dict):
                events.append(event)
    metas = [event["payload"] for event in events if event.get("type") == "session_meta"]
    return (metas[-1] if metas else None), events, malformed


def collect(root_id: str, rollout_roots: str | Path | list[str | Path],
            private_prefixes: tuple[str, ...] = ()) -> dict[str, Any]:
    """Return public-safe usage/model evidence for a root and its descendants.

    Paths may be directories or individual rollout JSONL files. Do not collect
    with --ephemeral: persisted descendant rollouts are required for accounting.
    """
    if isinstance(rollout_roots, (str, Path)):
        rollout_roots = [rollout_roots]
    paths: set[Path] = set()
    for source in rollout_roots:
        path = Path(source)
        paths.update(path.rglob("rollout*.jsonl") if path.is_dir() else [path])
    sessions: dict[str, dict[str, Any]] = {}
    for path in sorted(paths):
        meta, events, malformed = _read_rollout(path)
        if not meta or not meta.get("id"):
            continue
        source = meta.get("source")
        subagent = source.get("subagent") if isinstance(source, dict) else None
        spawn = subagent.get("thread_spawn", {}) if isinstance(subagent, dict) else {}
        if not isinstance(spawn, dict):
            spawn = {}
        session_id = meta["id"]
        # Prefer the most complete copy if callers supplied duplicate stores.
        if session_id in sessions and len(sessions[session_id]["events"]) >= len(events):
            continue
        sessions[session_id] = {
            "meta": meta, "events": events, "malformed": malformed,
            "parent": spawn.get("parent_thread_id"), "agent_path": spawn.get("agent_path"),
            # The outer timestamp records rollout persistence, which may occur
            # after spawn_agent returns. Use the thread's actual creation time.
            "created_at": next((entry["payload"].get("timestamp") or entry.get("timestamp") for entry in events
                                if entry.get("type") == "session_meta"
                                and entry.get("payload", {}).get("id") == session_id), None),
        }
    if root_id not in sessions:
        raise ValueError("Root rollout was not found in supplied locations")
    members = {root_id}
    while True:
        expanded = members | {sid for sid, session in sessions.items() if session["parent"] in members}
        if expanded == members:
            break
        members = expanded
    ordered = [root_id] + sorted(members - {root_id}, key=lambda sid: (
        str(sessions[sid]["meta"].get("timestamp", "")), sid))
    labels = {sid: ("root" if i == 0 else f"worker_{i}") for i, sid in enumerate(ordered)}
    children_by_path: dict[tuple[str, str], list[str]] = defaultdict(list)
    for sid in ordered:
        if sessions[sid]["agent_path"]:
            children_by_path[(sessions[sid]["parent"], sessions[sid]["agent_path"])].append(sid)
    total = _usage({})
    model_usage: dict[str, dict[str, int]] = defaultdict(lambda: _usage({}))
    seen_responses: set[str] = set()
    threads = []
    warnings = []
    for sid in ordered:
        session = sessions[sid]
        model = "unknown"
        effort = None
        models = set()
        efforts = set()
        counters: Counter[str] = Counter()
        compaction_markers: Counter[str] = Counter()
        thread_usage = _usage({})
        by_model: dict[str, dict[str, int]] = defaultdict(lambda: _usage({}))
        footprints: list[int] = []
        responses = 0
        foreign_records = 0
        duplicates = 0
        context_window = None
        last_quota = None
        started_own_history = False
        pending_spawns: dict[str, dict[str, Any]] = {}
        observed_spawns = []

        def add_record(record: dict[str, Any]) -> None:
            nonlocal responses, foreign_records, duplicates
            if record.get("thread_id") != sid:
                foreign_records += 1
                return
            response_id = record.get("response_id")
            if not response_id:
                warnings.append(f"{labels[sid]} has a usage record without response_id; excluded")
                return
            if response_id in seen_responses:
                duplicates += 1
                return
            seen_responses.add(response_id)
            usage = _usage(record.get("usage"))
            for target in (total, thread_usage, by_model[model], model_usage[model]):
                _add(target, usage)
            footprints.append(usage["input_tokens"])
            models.add(model)
            if effort is not None:
                efforts.add(effort)
            responses += 1

        for event in session["events"]:
            kind = event.get("type")
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            if kind == "session_meta" and payload.get("id") == sid:
                started_own_history = True
            # Fork files can contain earlier parent history before their own meta.
            if not started_own_history:
                continue
            if kind == "turn_context":
                model = payload.get("model", model)
                effort = payload.get("effort", payload.get("reasoning_effort", effort))
            elif kind == "token_usage_record":
                add_record(payload)
            elif kind == "compacted":
                compaction_markers["compacted"] += 1
                nested = payload.get("latest_token_usage_record")
                if isinstance(nested, dict):
                    add_record(nested)
            elif kind == "event_msg":
                event_type = payload.get("type")
                if event_type == "context_compacted":
                    compaction_markers["context_compacted"] += 1
                elif event_type == "token_count":
                    info = payload.get("info") or {}
                    context_window = info.get("model_context_window", context_window)
                    if isinstance(payload.get("rate_limits"), dict):
                        last_quota = _quota_snapshot(payload["rate_limits"])
            elif kind == "response_item" and payload.get("type") in ("function_call", "custom_tool_call"):
                name = payload.get("name", "unknown")
                counters[name] += 1
                if name.rsplit(".", 1)[-1] == "spawn_agent":
                    try:
                        arguments = json.loads(payload.get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        arguments = {}
                    if isinstance(arguments, dict):
                        pending_spawns[payload.get("call_id", "")] = {
                            "arguments": arguments, "started_at": event.get("timestamp"),
                        }
            elif kind == "response_item" and payload.get("type") == "function_call_output":
                pending_spawn = pending_spawns.get(payload.get("call_id", ""))
                if pending_spawn is not None:
                    arguments = pending_spawn["arguments"]
                    try:
                        output = json.loads(payload.get("output", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        output = {}
                    if isinstance(output, dict) and output.get("task_name"):
                        candidates = children_by_path.get((sid, output["task_name"]), [])
                        start = _event_time(pending_spawn["started_at"])
                        end = _event_time(event.get("timestamp"))
                        matches = candidates
                        if start is not None and end is not None:
                            created = {candidate: _event_time(sessions[candidate]["created_at"])
                                       for candidate in candidates}
                            # Missing timestamps permit only an unambiguous single
                            # parent/path match. Never attach an earlier spawn to a
                            # later, timestamped child when names are reused.
                            matches = [candidate for candidate, when in created.items()
                                       if when is None or start <= when <= end]
                        child = labels[matches[0]] if len(matches) == 1 else None
                        observed_spawns.append({
                            "requested_model": arguments.get("model"),
                            "requested_reasoning_effort": arguments.get("reasoning_effort"),
                            "fork_turns": arguments.get("fork_turns", "all"),
                            "observed_child": child,
                        })
                        if len(matches) > 1:
                            warnings.append(f"{labels[sid]} has ambiguous child routing for a reused agent path; model attribution for that spawn is unresolved")
                        elif child is None:
                            warnings.append(f"{labels[sid]} has a successful spawn without a descendant rollout; accounting is incomplete")
        if not responses:
            warnings.append(f"{labels[sid]} has no attributable per-response usage records")
        if "unknown" in models:
            warnings.append(f"{labels[sid]} has usage without an observed model in turn_context")
        threads.append({
            "thread": labels[sid], "parent": labels.get(session["parent"]),
            "actual_models": sorted(models), "reasoning_efforts": sorted(efforts),
            "response_count": responses, "usage": thread_usage,
            "usage_by_model": dict(by_model), "tool_call_counts": dict(counters),
            "successful_spawn_requests": observed_spawns,
            "context_proxy": {
                "definition": "Provider input_tokens for each observed response; not exact live occupancy",
                "peak_request_input_tokens": max(footprints) if footprints else None,
                "last_request_input_tokens": footprints[-1] if footprints else None,
                "reported_model_context_window": context_window,
            },
            # A single compaction writes both marker types. Never add them.
            "compaction_count": max(compaction_markers.values(), default=0),
            "compaction_markers": dict(compaction_markers),
            "last_observed_quota": last_quota,
            "excluded_foreign_usage_records": foreign_records,
            "deduplicated_usage_records": duplicates,
            "malformed_lines": session["malformed"],
        })
    return sanitize({
        "schema_version": 1, "thread_count": len(threads), "threads": threads,
        "total_usage": total, "usage_by_model": dict(model_usage),
        "accounting": "Sum unique token_usage_record.usage by response_id, restricted to actual thread_id; includes nested compaction records once",
        "limitations": [
            "Only descendants with persisted rollouts in supplied directories are observable",
            "Cached input is a subset of input; reasoning output is a subset of output",
            "Input-token footprint is a proxy for context, not exact next-request occupancy",
            "Quota snapshots are account-wide, rounded or delayed, and may include concurrent work",
        ],
        "warnings": sorted(set(warnings)),
    }, private_prefixes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect_parser = commands.add_parser("collect")
    collect_parser.add_argument("root_id")
    collect_parser.add_argument("rollout_roots", nargs="+")
    quota_parser = commands.add_parser("quota")
    quota_parser.add_argument("--codex-home")
    args = parser.parse_args()
    if args.command == "collect":
        report = collect(args.root_id, args.rollout_roots)
    else:
        report = quota(args.codex_home)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
