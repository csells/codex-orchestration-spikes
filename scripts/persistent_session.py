#!/usr/bin/env python3
"""Deterministic persistent Codex app-server driver (CLI 0.156.1).

Keep one instance alive across root user turns so native workers can be reused.
Raw protocol envelopes are written ONLY to the caller's private rawdir. This
module does not copy credentials, export raw envelopes, alter model context
limits, compact automatically, or invoke a supervising/grading model.

Launch outside an enclosing OS sandbox when Codex must establish its own shell
sandbox. Codex itself uses workspace-write with approvalPolicy=never.
"""

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

from telemetry import _quota_snapshot


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class PersistentSession:
    def __init__(self, codex_home, workspace, rawdir, *, effort="high", codex="codex"):
        self.codex_home = Path(codex_home).resolve()
        self.workspace = Path(workspace).resolve()
        self.rawdir = Path(rawdir).resolve()
        self.effort = effort
        self.codex = codex
        self.thread_id = None
        self.process = None
        self._next_id = 0
        self._messages = queue.Queue()
        self._pending = deque()
        self._write_lock = threading.Lock()
        self._stdin_lock = threading.Lock()

    def start(self):
        if self.process is not None:
            raise RuntimeError("Session transport already started")
        self.rawdir.mkdir(parents=True, exist_ok=True)
        self._protocol = (self.rawdir / "app-server.jsonl").open("a", buffering=1)
        self._stderr = (self.rawdir / "app-server.stderr.txt").open("a", buffering=1)
        os.chmod(self.rawdir / "app-server.jsonl", 0o600)
        os.chmod(self.rawdir / "app-server.stderr.txt", 0o600)
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.codex_home)
        command = [self.codex, "app-server", "--stdio", "--enable", "multi_agent",
                   "--enable", "multi_agent_v2", "--disable", "apps", "--disable", "plugins",
                   "--enable", "skip_host_skill_discovery", "-c", 'web_search="disabled"']
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self._stderr, text=True, bufsize=1, env=env,
                                        cwd=self.workspace, start_new_session=True)
        self._reader = threading.Thread(target=self._read_messages, daemon=True)
        self._reader.start()
        self._rpc("initialize", {
            "clientInfo": {"name": "orchestration-spikes-persistent", "version": "0.1.0"},
            "capabilities": {"experimentalApi": True},
        })
        self._send({"jsonrpc": "2.0", "method": "initialized"})
        return self

    def _record(self, direction, message):
        with self._write_lock:
            self._protocol.write(json.dumps({"observed_at": utc_now(), "direction": direction,
                                             "message": message}) + "\n")

    def _read_messages(self):
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    self._record("unparsed_stdout", {"line": line})
                    continue
                self._record("received", message)
                # Refuse unexpected interactive requests; never silently approve
                # actions or supply fabricated answers to model questions.
                if "method" in message and "id" in message:
                    self._send({"jsonrpc": "2.0", "id": message["id"], "error": {
                        "code": -32601, "message": "Interactive requests are unsupported in this deterministic experiment"}})
                self._messages.put(message)
        finally:
            self._messages.put(None)

    def _send(self, message):
        with self._stdin_lock:
            self._record("sent", message)
            self.process.stdin.write(json.dumps(message) + "\n")
            self.process.stdin.flush()

    def _rpc(self, method, params=None, timeout=30):
        self._next_id += 1
        request_id = self._next_id
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"RPC timed out: {method}")
            try:
                message = self._messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError(f"RPC timed out: {method}") from exc
            if message is None:
                raise RuntimeError("Codex app-server exited; inspect private stderr")
            if message.get("id") != request_id or "method" in message:
                self._pending.append(message)
                continue
            if "error" in message:
                raise RuntimeError(f"RPC {method} failed: {message['error']}")
            return message.get("result", {})

    def start_thread(self, model="gpt-6-astra", config=None):
        settings = {"model_reasoning_effort": self.effort, "web_search": "disabled"}
        settings.update(config or {})
        result = self._rpc("thread/start", {
            "model": model, "cwd": str(self.workspace), "sandbox": "workspace-write",
            "approvalPolicy": "never", "config": settings, "ephemeral": False,
            "serviceTier": "default",
        })
        self.thread_id = result["thread"]["id"]
        return self.thread_id

    def resume_thread(self, thread_id, config=None):
        """Explicit recovery operation; ordinary turns keep the live transport."""
        result = self._rpc("thread/resume", {"threadId": thread_id,
            "cwd": str(self.workspace), "sandbox": "workspace-write", "approvalPolicy": "never",
            "config": config or {}, "excludeTurns": True})
        self.thread_id = result["thread"]["id"]
        return self.thread_id

    def _notification(self, wait_seconds):
        if self._pending:
            return self._pending.popleft()
        try:
            message = self._messages.get(timeout=wait_seconds)
        except queue.Empty:
            return {}
        if message is None:
            raise RuntimeError("Codex app-server exited during a turn; inspect private stderr")
        return message

    def run_turn(self, prompt, timeout=900):
        if not self.thread_id:
            raise RuntimeError("Call start_thread or resume_thread first")
        started_at = utc_now()
        started = time.monotonic()
        result = self._rpc("turn/start", {"threadId": self.thread_id,
            "input": [{"type": "text", "text": prompt}], "effort": self.effort,
            "serviceTierForTurn": "default"})
        turn_id = result["turn"]["id"]
        answer = ""
        fallback_answer = ""
        event_count = 0
        last_heartbeat = started
        root_usage = None
        errors = []
        while True:
            elapsed = time.monotonic() - started
            if elapsed >= timeout:
                try:
                    self._rpc("turn/interrupt", {"threadId": self.thread_id, "turnId": turn_id}, timeout=10)
                except (RuntimeError, TimeoutError, BrokenPipeError):
                    pass
                return {"thread_id": self.thread_id, "turn_id": turn_id, "status": "interrupted",
                        "answer": answer or fallback_answer, "started_at": started_at,
                        "ended_at": utc_now(), "elapsed_seconds": round(time.monotonic()-started, 3),
                        "timed_out": True, "error": "Turn exceeded its declared time limit",
                        "event_count": event_count}
            message = self._notification(min(1, timeout - elapsed))
            if message:
                event_count += 1
            method = message.get("method")
            params = message.get("params") or {}
            if params.get("threadId") == self.thread_id:
                if method == "item/completed" and params.get("turnId") == turn_id:
                    item = params.get("item") or {}
                    if item.get("type") == "agentMessage":
                        fallback_answer = item.get("text", fallback_answer)
                        if item.get("phase") == "final_answer":
                            answer = item.get("text", answer)
                elif method == "thread/tokenUsage/updated":
                    root_usage = params.get("tokenUsage")
                elif method == "error":
                    errors.append(params.get("error"))
                elif method == "turn/completed" and params.get("turn", {}).get("id") == turn_id:
                    turn = params["turn"]
                    for item in turn.get("items", []):
                        if item.get("type") == "agentMessage" and item.get("phase") == "final_answer":
                            answer = item.get("text", answer)
                    record = {"thread_id": self.thread_id, "turn_id": turn_id,
                              "status": turn["status"], "answer": answer or fallback_answer,
                              "started_at": started_at, "ended_at": utc_now(),
                              "elapsed_seconds": round(time.monotonic()-started, 3), "timed_out": False,
                              "event_count": event_count, "root_token_usage": root_usage}
                    if turn.get("error") or errors:
                        record["error"] = turn.get("error") or errors
                    return record
            if time.monotonic() - last_heartbeat >= 20:
                print(f"RUNNING persistent turn: {elapsed:.0f}s; {event_count} events", flush=True)
                last_heartbeat = time.monotonic()

    def rate_limits(self):
        raw = self._rpc("account/rateLimits/read", {})
        buckets = raw.get("rateLimitsByLimitId") or {"default": raw.get("rateLimits", {})}
        return {"observed_at": utc_now(),
                "buckets": {key: _quota_snapshot(value) for key, value in buckets.items()},
                "caveat": "Account-wide percentages; this reader does not establish exclusive activity or update latency."}

    def compact(self, thread_id=None):
        """Request explicit compaction; never called automatically by this driver.

        Returns the start acknowledgement. Observe the subsequent native
        compaction event before treating the operation as completed.
        """
        while True:
            try:
                self._pending.append(self._messages.get_nowait())
            except queue.Empty:
                break
        self._compaction_skip = len(self._pending)
        self._compaction_thread = thread_id or self.thread_id
        self._compaction_started_at = utc_now()
        self._compaction_started = time.monotonic()
        return self._rpc("thread/compact/start", {"threadId": self._compaction_thread})

    def wait_for_compaction(self, timeout=180):
        """Wait for native completion after compact(); return timed_out on timeout.

        Unrelated notifications remain available to run_turn. Callers that need
        durable evidence should additionally verify the persisted compacted row.
        """
        if not hasattr(self, "_compaction_started"):
            raise RuntimeError("Call compact before wait_for_compaction")
        deferred = []
        deadline = time.monotonic() + timeout
        completion = None
        heartbeat = time.monotonic()
        try:
            while time.monotonic() < deadline:
                message = self._notification(min(1, max(0, deadline-time.monotonic())))
                if time.monotonic()-heartbeat >= 20:
                    print("RUNNING explicit compaction; waiting for native completion", flush=True)
                    heartbeat = time.monotonic()
                if not message:
                    continue
                if self._compaction_skip:
                    self._compaction_skip -= 1
                    deferred.append(message)
                    continue
                params = message.get("params") or {}
                if params.get("threadId") == self._compaction_thread and (
                    message.get("method") == "thread/compacted" or
                    (message.get("method") == "item/completed" and
                     (params.get("item") or {}).get("type") == "contextCompaction")
                ):
                    completion = message["method"]
                    break
                deferred.append(message)
        finally:
            self._pending.extendleft(reversed(deferred))
        return {"thread_id": self._compaction_thread, "started_at": self._compaction_started_at,
                "ended_at": utc_now(), "elapsed_seconds": round(time.monotonic()-self._compaction_started, 3),
                "status": "completed" if completion else "timeout", "timed_out": completion is None,
                "completion_notification": completion}

    def close(self):
        if self.process is None:
            return
        try:
            self.process.stdin.close()
            self.process.wait(timeout=5)
        except (subprocess.TimeoutExpired, BrokenPipeError):
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self._reader.join(timeout=2)
        self._protocol.close()
        self._stderr.close()
        self.process = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--rawdir", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path, help="JSON array of prompt strings")
    args = parser.parse_args()
    with PersistentSession(args.codex_home, args.workspace, args.rawdir) as session:
        session.start_thread()
        for i, prompt in enumerate(json.loads(args.prompts.read_text()), 1):
            record = session.run_turn(prompt)
            (args.rawdir / f"turn-{i}.json").write_text(json.dumps(record, indent=2)+"\n")
            print(f"FINISHED turn {i}: {record['status']}; {record['elapsed_seconds']}s", flush=True)
            if record["status"] != "completed":
                break
