#!/usr/bin/env python3
"""Reproduce the observed root response-cost partition from public traces.

Uses token-usage record boundaries in the observed zero-compaction trace format.
This is a descriptive association, not a tool fee or avoidable-cost estimate.
No model calls, credentials, private rollouts, or network access are required.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

from summarize import RATES, estimate

ROOT = Path(__file__).resolve().parents[1]
RUNS = ('faithful-a-default', 'faithful-a-rory', 'faithful-a-rory-long',
        'faithful-b-default', 'faithful-b-rory', 'faithful-b-rory-long-completed')
COORDINATION = {'spawn_agent', 'send_message', 'wait_agent', 'followup_task'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(name):
    directory = ROOT / 'results' / name
    trace_path, telemetry_path = directory / 'trace.jsonl', directory / 'telemetry.json'
    telemetry = json.loads(telemetry_path.read_text())
    root = next(thread for thread in telemetry['threads'] if thread['thread'] == 'root')
    if root['actual_models'] != ['gpt-6-astra'] or root['compaction_count'] != 0:
        raise ValueError(f'{name}: this analysis requires an Astra root with no compaction')
    pending, records, seen = [], [], set()
    tool_counts, observed_usage = Counter(), Counter()
    for line_number, line in enumerate(trace_path.read_text().splitlines(), 1):
        row = json.loads(line)
        if row['thread'] != 'root':
            continue
        payload = row['payload']
        if row['kind'] == 'response_item' and payload.get('type') in ('function_call', 'custom_tool_call'):
            tool = payload['name']
            pending.append({'tool': tool, 'trace_line': line_number})
            tool_counts[tool] += 1
        elif row['kind'] == 'token_usage_record':
            identity = payload['response_hash']
            if identity in seen:
                if pending:
                    raise ValueError(f'{name}: duplicate usage boundary has unassigned calls')
                continue
            seen.add(identity)
            tools = {call['tool'] for call in pending}
            if not tools:
                category = 'answer_or_other_without_tool_call'
            elif tools == {'exec'}:
                category = 'exec'
            elif tools <= COORDINATION:
                category = 'coordination'
            else:
                raise ValueError(f'{name}: ambiguous or unsupported response interval: {sorted(tools)}')
            usage = payload['usage']
            observed_usage.update(usage)
            records.append({'response_hash': identity, 'usage_trace_line': line_number,
                            'calls_since_previous_usage_record': pending,
                            'category': category, 'tool_group': '+'.join(sorted(tools)) or 'none',
                            'credit_estimate': estimate({'gpt-6-astra': usage})['total'],
                            'usage': usage})
            pending = []
    if pending:
        raise ValueError(f'{name}: trailing tool calls have no recorded response usage')
    if len(records) != root['response_count']:
        raise ValueError(f'{name}: response count differs from independent telemetry')
    if dict(tool_counts) != root['tool_call_counts']:
        raise ValueError(f'{name}: tool counts differ from independent telemetry')
    if dict(observed_usage) != root['usage']:
        raise ValueError(f'{name}: summed usage differs from independent telemetry')
    categories = defaultdict(lambda: {'responses': 0, 'credit_estimate': 0.0})
    groups = defaultdict(lambda: {'responses': 0, 'credit_estimate': 0.0})
    for record in records:
        for aggregate, key in ((categories, record['category']), (groups, record['tool_group'])):
            aggregate[key]['responses'] += 1
            aggregate[key]['credit_estimate'] += record['credit_estimate']
    root_cost = estimate(root['usage_by_model'])['total']
    partition_cost = sum(value['credit_estimate'] for value in categories.values())
    if not math.isclose(partition_cost, root_cost, abs_tol=1e-9, rel_tol=0):
        raise ValueError(f'{name}: partition does not reconcile to root cost')
    whole = estimate(telemetry['usage_by_model'])['total']
    usage, rates = root['usage'], RATES['gpt-6-astra']
    return {
        'run_id': name,
        'source_sha256': {'trace.jsonl': digest(trace_path), 'telemetry.json': digest(telemetry_path)},
        'root_credit_estimate': root_cost, 'worker_credit_estimate': whole - root_cost,
        'full_tree_credit_estimate': whole, 'parent_responses': len(records),
        'parent_credit_components': {
            'uncached_input': (usage['input_tokens'] - usage['cached_input_tokens']) * rates['input'] / 1e6,
            'cached_input': usage['cached_input_tokens'] * rates['cached'] / 1e6,
            'output_including_reasoning': usage['output_tokens'] * rates['output'] / 1e6,
        },
        'partition_by_category': dict(categories), 'partition_by_tool_group': dict(groups),
        'checks': {'root_model_and_no_compaction': True, 'response_count_matches': True,
                   'tool_counts_match': True, 'all_usage_fields_match': True,
                   'no_mixed_exec_coordination_intervals': True, 'no_unassigned_calls': True,
                   'disjoint_cost_partition_reconciles': True},
        'response_intervals': records,
    }


def main():
    result = {
        'method': [
            'Use only root rows from each public trace, preserving their recorded order.',
            'Collect function_call/custom_tool_call records between consecutive root token_usage_record boundaries.',
            'Deduplicate usage by response_hash. Assign the entire recorded response charge to exec, coordination, or no-tool-call.',
            'Coordination means spawn_agent, send_message, wait_agent, or followup_task. No response charge is split across tools.',
            'Reject mixed exec/coordination intervals, unknown tools, unassigned calls, non-Astra roots, or compactions.',
            'Reconcile response count, tool counts, every usage field, and total estimated root cost with retained telemetry.',
        ],
        'interpretation': 'Association with recorded response intervals, not tool fees, isolated causal costs, or guaranteed avoidable overhead. Response costs include their entire input and output.',
        'scope': 'These six observed zero-compaction traces; not a generic parser for all provider logging formats.',
        'rates_per_million_tokens': RATES,
        'script_sha256': digest(Path(__file__).resolve()),
        'runs': [analyze(name) for name in RUNS],
    }
    destination = ROOT / 'verification' / 'sustained-cost-breakdown.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({row['run_id']: {'root': row['root_credit_estimate'],
                                     'workers': row['worker_credit_estimate'],
                                     'categories': row['partition_by_category']}
                      for row in result['runs']}, indent=2))


if __name__ == '__main__':
    main()
