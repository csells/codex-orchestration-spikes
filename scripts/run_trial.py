#!/usr/bin/env python3
"""Run one frozen local Codex task and preserve publishable execution evidence.

Credentials belong in the separate CODEX_HOME supplied by the operator. This
script neither reads nor publishes authentication material.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone
from telemetry import collect, quota

ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def sanitize(text, workspace, codex_home, private):
    replacements = [(str(workspace), "<WORKSPACE>"),
                    (str(codex_home), "<CODEX_HOME>"),
                    (str(private), "<PRIVATE_RUN_ROOT>"),
                    (str(Path.home()), "<USER_HOME>")]
    for source, target in sorted(replacements, key=lambda pair: -len(pair[0])):
        text = text.replace(source, target)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--policy", choices=["default", "rory", "rory-astra-workers", "rory-long", "rory-long-astra-workers", "sol"], required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--private-root", type=Path, required=True)
    ap.add_argument("--codex-home", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--resume", help="Existing session ID; reuse its workspace")
    ap.add_argument("--workspace", type=Path)
    ap.add_argument("--prompt-file", type=Path)
    args = ap.parse_args()
    private = args.private_root.resolve()
    codex_home = args.codex_home.resolve()
    out = ROOT / "results" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    task = json.loads((ROOT / "tasks" / f"{args.task}.json").read_text())
    original = ROOT / task["fixture"]
    workspace = args.workspace.resolve() if args.workspace else private / args.run_id / "workspace"
    rawdir = private / args.run_id
    rawdir.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        shutil.copytree(original, workspace)
        common = (ROOT / "policies/common.md").read_text()
        if args.policy.endswith("astra-workers"):
            common = common.replace("Luna = gpt-6-luna; Terra = gpt-5.6-terra; Sol = gpt-6-sol", "Luna = gpt-6-astra; Terra = gpt-6-astra; Sol = gpt-6-astra")
        policy_file = "rory-long.md" if args.policy.startswith("rory-long") else "rory-v2.md"
        policy = (ROOT / "policies" / policy_file).read_text() if args.policy.startswith("rory") else ""
        if args.policy.startswith("rory-long"):
            policy = policy.replace("[If inheriting context forces the parent's model, state that here as a fact and what to do about it.]", "In this harness, use fork_turns=none to request a fresh worker with its explicitly selected model.")
        if args.policy.endswith("astra-workers"):
            policy += "\nExperimental control: keep the same assignment and handoff policy, but every worker must use gpt-6-astra at high reasoning. This overrides the routing model names above.\n"
        (workspace / "AGENTS.md").write_text(common + "\n" + policy)
    prompt = args.prompt_file.read_text() if args.prompt_file else task.get("prompt") or (ROOT / task["prompt_file"]).read_text()
    (out / "prompt.txt").write_text(prompt)
    (out / "AGENTS.md.txt").write_text((workspace / "AGENTS.md").read_text())
    model = "gpt-6-sol" if args.policy == "sol" else "gpt-6-astra"
    command = ["codex", "exec", "--ignore-user-config", "--skip-git-repo-check", "--json", "--color", "never", "-m", model,
               "-c", 'model_reasoning_effort="high"', "-c", 'web_search="disabled"',
               "--enable", "multi_agent", "--enable", "multi_agent_v2", "--disable", "apps", "--disable", "plugins",
               "--enable", "skip_host_skill_discovery", "-s", "workspace-write", "-C", str(workspace),
               "-o", str(rawdir / "answer.txt")]
    if args.resume:
        # `resume` takes its own arguments; the workspace is carried by session state.
        command = ["codex", "exec", "--ignore-user-config", "--enable", "multi_agent", "--enable", "multi_agent_v2",
                   "--disable", "apps", "--disable", "plugins", "--enable", "skip_host_skill_discovery",
                   "-c", 'web_search="disabled"', "-c", 'model_reasoning_effort="high"',
                   "resume", args.resume, "--skip-git-repo-check", "--json", "-o", str(rawdir / "answer.txt")]
    command += ["-"]
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    metadata = {"run_id": args.run_id, "task": args.task, "policy": args.policy,
                "model_requested": model, "reasoning_requested": "high", "started_at": now(),
                "command": [sanitize(s, workspace, codex_home, private) for s in command],
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "instructions_sha256": hashlib.sha256((workspace / "AGENTS.md").read_bytes()).hexdigest(),
                "timeout_seconds": args.timeout, "resume": args.resume,
                "account_meter_attribution": "uncontrolled: investigation and other account activity may overlap"}
    (out / "run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"START {args.run_id}: {args.policy} / {args.task}", flush=True)
    try:
        (out / "quota-before.json").write_text(json.dumps(quota(codex_home=codex_home), indent=2)+"\n")
    except (RuntimeError, TimeoutError, OSError) as exc:
        metadata["quota_before_error"] = sanitize(str(exc), workspace, codex_home, private)
    started = time.monotonic()
    events = 0
    last_event = "starting"
    timed_out = False
    with (rawdir / "events.jsonl").open("w") as raw, (rawdir / "stderr.txt").open("w") as err:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, env=env, cwd=workspace, text=True, start_new_session=True)
        proc.stdin.write(prompt)
        proc.stdin.close()
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        last_report = started
        while True:
            for key, _ in selector.select(timeout=1):
                line = key.fileobj.readline()
                if not line:
                    selector.unregister(key.fileobj)
                    continue
                raw.write(line)
                raw.flush()
                events += 1
                try:
                    event = json.loads(line)
                    last_event = event.get("type", "unknown")
                    if last_event == "thread.started": metadata["root_thread_id"] = event["thread_id"]
                    if last_event == "turn.completed": metadata["cli_usage"] = event.get("usage")
                    if last_event in ("turn.failed", "error"): metadata.setdefault("errors", []).append(event)
                except json.JSONDecodeError:
                    metadata.setdefault("unparsed_event_lines", []).append(events)
            elapsed = time.monotonic() - started
            if elapsed > args.timeout and proc.poll() is None:
                timed_out = True
                os.killpg(proc.pid, signal.SIGTERM)
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(proc.pid, signal.SIGKILL)
            if time.monotonic() - last_report >= 20:
                print(f"RUNNING {args.run_id}: {elapsed:.0f}s; {events} events; last={last_event}", flush=True)
                last_report = time.monotonic()
            if proc.poll() is not None and not selector.get_map(): break
        metadata["exit_code"] = proc.wait()
    metadata.update(ended_at=now(), elapsed_seconds=round(time.monotonic()-started, 3), timed_out=timed_out, event_count=events)
    for name in ["events.jsonl", "stderr.txt", "answer.txt"]:
        source = rawdir / name
        if source.exists(): (out / name).write_text(sanitize(source.read_text(), workspace, codex_home, private))
    diffs = []
    paths = {p.relative_to(original) for p in original.rglob("*") if p.is_file()} | {p.relative_to(workspace) for p in workspace.rglob("*") if p.is_file()}
    for relative in sorted(paths):
        if relative == Path("AGENTS.md") or any(x in relative.parts for x in ["node_modules", ".git", "__pycache__"]): continue
        before, after = original / relative, workspace / relative
        try:
            a = before.read_text().splitlines(keepends=True) if before.exists() else []
            b = after.read_text().splitlines(keepends=True) if after.exists() else []
        except UnicodeDecodeError: continue
        if a != b: diffs.extend(difflib.unified_diff(a, b, fromfile="a/"+str(relative), tofile="b/"+str(relative)))
    (out / "changes.patch").write_text(sanitize("".join(diffs), workspace, codex_home, private))
    if metadata.get("root_thread_id"):
        try:
            report = collect(metadata["root_thread_id"], codex_home / "sessions")
            (out / "telemetry.json").write_text(json.dumps(report, indent=2)+"\n")
        except (ValueError, OSError) as exc:
            metadata["telemetry_error"] = sanitize(str(exc), workspace, codex_home, private)
    try:
        (out / "quota-after.json").write_text(json.dumps(quota(codex_home=codex_home), indent=2)+"\n")
    except (RuntimeError, TimeoutError, OSError) as exc:
        metadata["quota_after_error"] = sanitize(str(exc), workspace, codex_home, private)
    (out / "run.json").write_text(json.dumps(metadata, indent=2)+"\n")
    print(f"FINISHED {args.run_id}: exit={metadata['exit_code']} timeout={timed_out} elapsed={metadata['elapsed_seconds']}s root={metadata.get('root_thread_id')}", flush=True)
    return 1 if timed_out or metadata["exit_code"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
