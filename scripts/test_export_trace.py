#!/usr/bin/env python3
"""Public trace/accounting tests using only synthetic rollouts, without models."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from export_trace import export, redact_opaque
from summarize import estimate
from telemetry import collect


def event(kind, payload):
    return {"timestamp": "2000-01-01T00:00:00Z", "type": kind, "payload": payload}


def meta(thread, source="exec"):
    return event("session_meta", {"id": thread, "source": source,
                                  "base_instructions": "HIDDEN_BASE_SENTINEL"})


def usage_record(thread, response, inputs):
    return {"thread_id": thread, "response_id": response,
            "usage": {"input_tokens": inputs, "cached_input_tokens": 2,
                      "output_tokens": 3, "reasoning_output_tokens": 1,
                      "total_tokens": inputs + 3}}


class PublicTraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orchestration-export-test-")
        self.home = Path(self.temp.name)
        self.sessions = self.home / "sessions"
        self.sessions.mkdir()
        self.addCleanup(self.temp.cleanup)

    def write(self, name, events):
        (self.sessions / f"rollout-{name}.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in events))

    def test_excludes_instruction_envelopes_and_reasoning_but_keeps_evidence(self):
        hidden = []
        for role in ("system", "developer", "user"):
            hidden.append(event("response_item", {"type": "message", "role": role,
                                                   "content": f"HIDDEN_{role.upper()}_SENTINEL"}))
        hidden += [
            event("world_state", {"instructions": "HIDDEN_WORLD_STATE_SENTINEL"}),
            event("response_item", {"type": "reasoning", "summary": "HIDDEN_REASONING_SENTINEL",
                                     "encrypted_content": "HIDDEN_ENCRYPTED_SENTINEL"}),
            event("response_item", {"type": "message", "role": "assistant", "phase": "analysis",
                                     "content": "HIDDEN_ANALYSIS_SENTINEL"}),
        ]
        kept = [
            {"type": "function_call", "name": "exec_command", "arguments": '{"cmd":"pwd"}', "call_id": "tool-1"},
            {"type": "function_call_output", "call_id": "tool-1", "output": "PUBLIC_TOOL_RESULT"},
            {"type": "custom_tool_call", "name": "exec", "input": "PUBLIC_TOOL_CODE", "call_id": "tool-2"},
            {"type": "custom_tool_call_output", "call_id": "tool-2", "output": "PUBLIC_CUSTOM_RESULT"},
            {"type": "agent_message", "author": "/root/worker", "content": "PUBLIC_HANDOFF"},
            {"type": "message", "role": "assistant", "phase": "commentary", "content": "PUBLIC_COMMENTARY"},
            {"type": "message", "role": "assistant", "phase": "final_answer", "content": "PUBLIC_ANSWER"},
        ]
        self.write("root", [meta("root-secret-id"), *hidden,
                            event("turn_context", {"model": "gpt-6-astra", "effort": "high",
                                                   "developer_instructions": "HIDDEN_TURN_SENTINEL"}),
                            *(event("response_item", item) for item in kept),
                            event("token_usage_record", usage_record("root-secret-id", "response-secret-id", 10))])
        rows = export("root-secret-id", self.home)
        serialized = json.dumps(rows)
        self.assertNotIn("HIDDEN_", serialized)
        self.assertNotIn("root-secret-id", serialized)
        self.assertNotIn("response-secret-id", serialized)
        self.assertEqual([row["payload"] for row in rows if row["kind"] == "response_item"], kept)
        tokens = next(row["payload"] for row in rows if row["kind"] == "token_usage_record")
        self.assertEqual(tokens["usage"]["input_tokens"], 10)
        self.assertEqual(tokens["response_hash"], hashlib.sha256(b"response-secret-id").hexdigest()[:16])

    def test_full_history_forks_do_not_republish_parent_evidence(self):
        parent = [meta("r"), event("token_usage_record", usage_record("r", "r1", 10))]
        child_source = {"subagent": {"thread_spawn": {"parent_thread_id": "r"}}}
        self.write("root", parent)
        self.write("child", [*parent, meta("c", child_source),
                            event("token_usage_record", usage_record("r", "r1", 10)),
                            event("token_usage_record", usage_record("c", "c1", 20))])
        rows = export("r", self.home)
        tokens = [row for row in rows if row["kind"] == "token_usage_record"]
        self.assertEqual(len(tokens), 2)
        self.assertEqual(sum(row["payload"]["usage"]["input_tokens"] for row in tokens), 30)
        self.assertEqual({row["thread"] for row in tokens}, {"root", "worker_1"})

    def test_trace_can_reconstruct_compaction_usage_included_by_accountant(self):
        compact_usage = usage_record("r", "compact", 40)
        for also_standalone in (False, True):
            with self.subTest(also_standalone=also_standalone):
                events = [meta("r"), event("turn_context", {"model": "gpt-6-astra"}),
                          event("token_usage_record", usage_record("r", "r1", 10))]
                if also_standalone:
                    events.append(event("token_usage_record", compact_usage))
                events.append(event("compacted", {"latest_token_usage_record": compact_usage,
                                                   "replacement_history": "HIDDEN_COMPACTION_SENTINEL"}))
                self.write("root", events)
                rows = export("r", self.home)
                records = {row["payload"]["response_hash"]: row["payload"]["usage"]
                           for row in rows if row["kind"] == "token_usage_record"}
                report = collect("r", self.sessions)
                self.assertEqual(len(records), 2)
                self.assertEqual(sum(item["input_tokens"] for item in records.values()), report["total_usage"]["input_tokens"])
                self.assertNotIn("HIDDEN_COMPACTION_SENTINEL", json.dumps(rows))

    def test_non_thread_spawn_subagent_metadata_does_not_break_discovery(self):
        self.write("root", [meta("r")])
        self.write("unrelated", [meta("unrelated", {"subagent": "review"})])
        self.assertEqual(len(export("r", self.home)), 1)

    def test_opaque_briefs_embedded_code_and_encrypted_fields_are_hashes_only(self):
        cipher = "gAAAA" + "A" * 95 + "=="  # Synthetic format marker; not real encrypted content.
        digest = hashlib.sha256(cipher.encode()).hexdigest()
        arguments = json.dumps({"model": "gpt-6-luna", "message": cipher})
        self.write("root", [
            meta("r"),
            event("response_item", {"type": "function_call", "name": "spawn_agent", "arguments": arguments}),
            event("response_item", {"type": "custom_tool_call", "name": "exec",
                                     "input": f'run("PUBLIC_COMMAND", "{cipher}")'}),
            event("response_item", {"type": "custom_tool_call_output", "output": [
                {"type": "text", "text": f"PUBLIC_OUTPUT {cipher}"}]}),
            event("response_item", {"type": "agent_message", "content": [
                {"type": "encrypted_text", "encrypted_content": cipher}]}),
        ])
        rows = export("r", self.home)
        encoded = json.dumps(rows)
        self.assertNotIn(cipher, encoded)
        self.assertNotIn("gAAAA", encoded)
        self.assertIn(digest, encoded)
        self.assertIn("PUBLIC_COMMAND", encoded)
        self.assertIn("PUBLIC_OUTPUT", encoded)
        call = next(row["payload"] for row in rows if row["payload"].get("name") == "spawn_agent")
        args = json.loads(call["arguments"])
        self.assertEqual(args["model"], "gpt-6-luna")
        self.assertIn(f"chars={len(cipher)}", args["message"])
        handoff = next(row["payload"] for row in rows if row["payload"].get("type") == "agent_message")
        self.assertEqual(handoff["content"][0]["encrypted_content"], {
            "redacted": "opaque_provider_content", "sha256": digest, "length_chars": len(cipher),
        })
        # Explicitly encrypted fields are omitted even if their provider format changes.
        self.assertEqual(redact_opaque({"encrypted_content": "OTHER_OPAQUE_FORMAT"})["encrypted_content"]["length_chars"], 19)

    def test_completed_execution_events_preserve_behavior_without_hidden_neighbor_items(self):
        workspace = self.home.resolve() / "workspace"
        def completed(thread, item):
            return event("event_msg", {"type": "item_completed", "thread_id": thread, "item": item})
        self.write("root", [
            meta("r"),
            completed("r", {"type": "CommandExecution", "command": ["sh", "-c", "PUBLIC_COMMAND"],
                            "cwd": str(workspace), "stdout": "PUBLIC_STDOUT", "stderr": "PUBLIC_STDERR",
                            "exit_code": 7, "status": "failed", "duration": {"secs": 1, "nanos": 2},
                            "unexpected_hidden_field": "HIDDEN_EXECUTION_SENTINEL"}),
            completed("r", {"type": "FileChange", "changes": {
                str(workspace / "app.py"): {"type": "update", "unified_diff": "+PUBLIC_PATCH"}},
                "status": "completed", "stdout": "PUBLIC_PATCH_RESULT"}),
            completed("r", {"type": "Reasoning", "raw_content": "HIDDEN_REASONING_EVENT_SENTINEL"}),
            completed("r", {"type": "UserMessage", "content": "HIDDEN_USER_EVENT_SENTINEL"}),
            completed("another-thread", {"type": "CommandExecution", "stdout": "WRONG_THREAD_SENTINEL"}),
        ])
        rows = export("r", self.home, workspace)
        executed = [row["payload"] for row in rows if row["kind"] == "execution_event"]
        self.assertEqual(len(executed), 2)
        self.assertEqual(executed[0]["exit_code"], 7)
        self.assertEqual(executed[0]["stdout"], "PUBLIC_STDOUT")
        self.assertEqual(executed[0]["command"], ["sh", "-c", "PUBLIC_COMMAND"])
        self.assertEqual(executed[0]["cwd"], "<private-path>")
        self.assertIn("<private-path>/app.py", executed[1]["changes"])
        serialized = json.dumps(rows)
        for omitted in ("HIDDEN_", "WRONG_THREAD_SENTINEL", str(workspace)):
            self.assertNotIn(omitted, serialized)


class CreditEstimateTests(unittest.TestCase):
    def test_cached_input_is_discounted_and_reasoning_not_added_twice(self):
        result = estimate({"gpt-6-astra": {
            "input_tokens": 1_000_000, "cached_input_tokens": 400_000,
            "output_tokens": 100_000, "reasoning_output_tokens": 50_000,
        }})
        self.assertEqual(result["total"], 285)  # 600k*250 + 400k*25 + 100k*1250, per million.

    def test_unknown_prices_and_invalid_cache_subsets_fail(self):
        with self.assertRaises(KeyError):
            estimate({"unknown-model": {}})
        with self.assertRaises(ValueError):
            estimate({"gpt-6-astra": {"input_tokens": 10, "cached_input_tokens": 11, "output_tokens": 1}})


if __name__ == "__main__":
    unittest.main()
