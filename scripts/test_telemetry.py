#!/usr/bin/env python3
"""Deterministic accounting checks; no credentials, network, or real transcripts.

Run: python3 -m unittest discover -s scripts -p 'test_telemetry.py' -v
"""

import json
from pathlib import Path
import tempfile
import unittest

from telemetry import _quota_snapshot, collect, sanitize


def event(kind, payload):
    return {"type": kind, "payload": payload}


def meta(thread, parent=None, path=None):
    source = "exec" if parent is None else {
        "subagent": {"thread_spawn": {"parent_thread_id": parent, "agent_path": path}}
    }
    return event("session_meta", {"id": thread, "source": source})


def context(model, effort="high"):
    return event("turn_context", {"model": model, "effort": effort})


def record(thread, response, inputs, cached=0, outputs=2, reasoning=1):
    return {
        "thread_id": thread, "response_id": response,
        "usage": {"input_tokens": inputs, "cached_input_tokens": cached,
                  "output_tokens": outputs, "reasoning_output_tokens": reasoning,
                  "total_tokens": inputs + outputs},
    }


def usage(thread, response, inputs, **kwargs):
    return event("token_usage_record", record(thread, response, inputs, **kwargs))


def spawn(task="/root/search", call="spawn-1"):
    return [
        event("response_item", {
            "type": "function_call", "name": "spawn_agent", "call_id": call,
            "arguments": json.dumps({"model": "gpt-6-luna", "reasoning_effort": "medium",
                                     "fork_turns": "none", "task_name": "search"}),
        }),
        event("response_item", {
            "type": "function_call_output", "call_id": call,
            "output": json.dumps({"task_name": task}),
        }),
    ]


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orchestration-telemetry-test-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def write(self, name, events, trailing=""):
        path = self.root / f"rollout-{name}.jsonl"
        path.write_text("".join(json.dumps(item) + "\n" for item in events) + trailing)
        return path

    def test_full_tree_excludes_inherited_history_and_preserves_model_evidence(self):
        parent = [meta("parent"), context("gpt-6-astra"),
                  usage("parent", "parent-response", 10, cached=4), *spawn()]
        self.write("parent", parent)
        self.write("child", [
            *parent,  # Full-history fork copies earlier parent events.
            meta("child", "parent", "/root/search"), context("gpt-6-luna", "medium"),
            usage("parent", "parent-response", 10, cached=4),  # Defensive ownership check.
            usage("child", "child-response", 20, cached=12),
        ])
        result = collect("parent", self.root)
        self.assertEqual(result["thread_count"], 2)
        self.assertEqual(result["total_usage"]["input_tokens"], 30)
        self.assertEqual(result["total_usage"]["cached_input_tokens"], 16)
        self.assertEqual(result["total_usage"]["output_tokens"], 4)
        self.assertEqual(result["total_usage"]["reasoning_output_tokens"], 2)
        # Cached input and reasoning output are subsets, never extra billed tokens.
        self.assertEqual(result["total_usage"]["total_tokens"], 34)
        self.assertEqual(result["usage_by_model"]["gpt-6-astra"]["input_tokens"], 10)
        self.assertEqual(result["usage_by_model"]["gpt-6-luna"]["input_tokens"], 20)
        child = result["threads"][1]
        self.assertEqual(child["actual_models"], ["gpt-6-luna"])
        self.assertEqual(child["reasoning_efforts"], ["medium"])
        self.assertEqual(child["parent"], "root")
        self.assertEqual(child["excluded_foreign_usage_records"], 1)
        self.assertEqual(result["threads"][0]["successful_spawn_requests"], [{
            "requested_model": "gpt-6-luna", "requested_reasoning_effort": "medium",
            "fork_turns": "none", "observed_child": "worker_1",
        }])
        self.assertFalse(result["warnings"])

    def test_deduplicates_compaction_response_and_paired_markers(self):
        compact = record("root-id", "compact-response", 40)
        self.write("root", [
            meta("root-id"), context("gpt-6-astra"), usage("root-id", "answer", 10),
            event("token_usage_record", compact),
            event("compacted", {"latest_token_usage_record": compact}),
            event("event_msg", {"type": "context_compacted"}),
        ])
        result = collect("root-id", self.root)
        self.assertEqual(result["total_usage"]["input_tokens"], 50)
        self.assertEqual(result["threads"][0]["response_count"], 2)
        self.assertEqual(result["threads"][0]["compaction_count"], 1)
        self.assertEqual(result["threads"][0]["deduplicated_usage_records"], 1)

    def test_includes_compaction_usage_when_available_only_in_compacted_record(self):
        self.write("root", [meta("r"), context("gpt-6-astra"),
                            event("compacted", {"latest_token_usage_record": record("r", "c", 40)})])
        result = collect("r", self.root)
        self.assertEqual(result["total_usage"]["input_tokens"], 40)
        self.assertEqual(result["threads"][0]["response_count"], 1)

    def test_descendants_are_recursive_and_unrelated_sessions_are_excluded(self):
        self.write("root", [meta("r"), context("astra"), usage("r", "r1", 10)])
        self.write("child", [meta("c", "r", "/root/c"), context("sol"), usage("c", "c1", 20)])
        self.write("grandchild", [meta("g", "c", "/root/c/g"), context("luna"), usage("g", "g1", 30)])
        self.write("unrelated", [meta("u"), context("astra"), usage("u", "u1", 1000)])
        result = collect("r", self.root)
        self.assertEqual(result["thread_count"], 3)
        self.assertEqual(result["total_usage"]["input_tokens"], 60)

    def test_duplicate_store_copies_are_not_added_and_latest_complete_copy_wins(self):
        initial = [meta("r"), context("astra"), usage("r", "r1", 10)]
        self.write("copy-short", initial)
        self.write("copy-complete", [*initial, usage("r", "r2", 20)])
        result = collect("r", [self.root, self.root])
        self.assertEqual(result["thread_count"], 1)
        self.assertEqual(result["total_usage"]["input_tokens"], 30)

    def test_resumed_spawns_reusing_task_name_match_their_own_child_creation(self):
        def at(second, item):
            return {**item, "timestamp": f"2000-01-01T00:00:{second:02d}Z"}
        first = spawn("/root/investigation", "first")
        second = spawn("/root/investigation", "second")
        root_events = [at(0, meta("r")), context("astra"), usage("r", "r1", 10),
                       at(1, first[0]), at(3, first[1]), event("event_msg", {"type": "task_complete"})]
        self.write("root", root_events)
        self.write("first-worker", [at(2, meta("c1", "r", "/root/investigation")),
                                    context("sol"), usage("c1", "c1r", 20),
                                    event("event_msg", {"type": "task_complete"})])
        before = collect("r", self.root)
        self.write("root", [*root_events, context("astra"), usage("r", "r2", 30),
                            at(10, second[0]), at(12, second[1])])
        self.write("second-worker", [at(11, meta("c2", "r", "/root/investigation")),
                                     context("luna"), usage("c2", "c2r", 40)])
        after = collect("r", self.root)
        self.assertEqual(before["total_usage"]["input_tokens"], 30)
        self.assertEqual(after["total_usage"]["input_tokens"], 100)
        self.assertEqual(after["thread_count"], 3)
        self.assertEqual([item["observed_child"] for item in after["threads"][0]["successful_spawn_requests"]],
                         ["worker_1", "worker_2"])
        self.assertFalse(after["warnings"])

    def test_ambiguous_reused_paths_are_reported_without_invented_route(self):
        self.write("root", [meta("r"), context("astra"), usage("r", "r1", 10), *spawn()])
        self.write("first-worker", [meta("c1", "r", "/root/search"), context("sol"), usage("c1", "c1r", 20)])
        self.write("second-worker", [meta("c2", "r", "/root/search"), context("luna"), usage("c2", "c2r", 30)])
        result = collect("r", self.root)
        self.assertIsNone(result["threads"][0]["successful_spawn_requests"][0]["observed_child"])
        self.assertTrue(any("ambiguous child routing" in item for item in result["warnings"]))
        self.assertEqual(result["total_usage"]["input_tokens"], 60)

    def test_child_creation_time_survives_rollout_write_after_spawn_returns(self):
        call, output = spawn()
        call["timestamp"] = "2000-01-01T00:00:01Z"
        output["timestamp"] = "2000-01-01T00:00:03Z"
        self.write("root", [meta("r"), context("astra"), usage("r", "r1", 10), call, output])
        child_meta = meta("c", "r", "/root/search")
        child_meta["payload"]["timestamp"] = "2000-01-01T00:00:02Z"
        child_meta["timestamp"] = "2000-01-01T00:00:03.007Z"
        self.write("child", [child_meta, context("sol"), usage("c", "c1", 20)])
        result = collect("r", self.root)
        self.assertEqual(result["threads"][0]["successful_spawn_requests"][0]["observed_child"], "worker_1")
        self.assertFalse(result["warnings"])
        self.assertEqual(result["total_usage"]["input_tokens"], 30)

    def test_missing_child_and_unfinished_record_are_explicit(self):
        self.write("root", [meta("r"), context("astra"), usage("r", "r1", 10), *spawn()], trailing='{"unfinished":')
        result = collect("r", self.root)
        self.assertEqual(result["threads"][0]["malformed_lines"], 1)
        self.assertIsNone(result["threads"][0]["successful_spawn_requests"][0]["observed_child"])
        self.assertTrue(any("accounting is incomplete" in item for item in result["warnings"]))

    def test_missing_usage_or_model_is_not_silently_invented(self):
        self.write("root", [meta("r"), usage("r", "r1", 10)])
        self.write("child", [meta("c", "r", "/root/c")])
        result = collect("r", self.root)
        self.assertTrue(any("without an observed model" in item for item in result["warnings"]))
        self.assertTrue(any("no attributable per-response usage" in item for item in result["warnings"]))
        with self.assertRaises(ValueError):
            collect("does-not-exist", self.root)

    def test_model_switches_and_context_proxies_follow_record_order(self):
        self.write("root", [
            meta("r"), context("astra"), usage("r", "r1", 100),
            context("sol", "medium"), usage("r", "r2", 40),
            event("event_msg", {"type": "token_count", "info": {"model_context_window": 1000}}),
        ])
        result = collect("r", self.root)
        self.assertEqual(result["usage_by_model"]["astra"]["input_tokens"], 100)
        self.assertEqual(result["usage_by_model"]["sol"]["input_tokens"], 40)
        proxy = result["threads"][0]["context_proxy"]
        self.assertEqual(proxy["peak_request_input_tokens"], 100)
        self.assertEqual(proxy["last_request_input_tokens"], 40)
        self.assertEqual(proxy["reported_model_context_window"], 1000)

    def test_public_telemetry_omits_raw_ids_paths_and_message_content(self):
        self.write("root", [
            meta("private-thread"), context("astra"), usage("private-thread", "private-response", 10),
            event("response_item", {"type": "message", "content": "PRIVATE_CONVERSATION_SENTINEL"}),
        ])
        serialized = json.dumps(collect("private-thread", self.root))
        for private in ("private-thread", "private-response", "PRIVATE_CONVERSATION_SENTINEL", str(self.root)):
            self.assertNotIn(private, serialized)
        self.assertEqual(sanitize("/Users/example/project/file", ("/Users/example/project",)), "<private-path>/file")
        self.assertEqual(sanitize({"paths": ["/Users/example/file", "/home/example/file"]}),
                         {"paths": ["<user-home>/file", "<user-home>/file"]})

    def test_quota_snapshot_allowlists_both_rpc_and_rollout_shapes(self):
        expected = {"primary": {"used_percent": 7, "window_minutes": 10080, "resets_at": 123},
                    "limit_id": "codex", "spend_control_reached": False}
        for raw in (
            {"limitId": "codex", "spendControlReached": False,
             "primary": {"usedPercent": 7, "windowDurationMins": 10080, "resetsAt": 123}},
            {"limit_id": "codex", "spend_control_reached": False,
             "primary": {"used_percent": 7, "window_minutes": 10080, "resets_at": 123}},
        ):
            with self.subTest(shape=raw):
                raw.update(accountId="PRIVATE_ACCOUNT_SENTINEL", credits={"id": "PRIVATE_CREDIT_SENTINEL"})
                self.assertEqual(_quota_snapshot(raw), expected)


if __name__ == "__main__":
    unittest.main()
