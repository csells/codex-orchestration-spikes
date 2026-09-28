#!/usr/bin/env python3
"""Two-turn-per-arm forced-compaction diagnostic; --self-test makes no model calls.

Run separately from primary campaign quota intervals. Raw protocol stays private.
This tests one explicit native boundary, never natural session longevity.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from export_trace import export, redact_opaque
from persistent_session import PersistentSession, utc_now
from run_trial import sanitize
from summarize import estimate
from telemetry import collect

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'tasks' / 'compaction-probe'
MANIFEST = json.loads((TASK / 'manifest.json').read_text())
EXPECTED = MANIFEST['expected_answers']
STOCK = {row['sku']: int(row['on_hand']) for row in csv.DictReader((TASK / 'inventory.csv').read_text().splitlines())}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(workspace):
    result = {}
    for path in sorted(workspace.rglob('*')):
        name = str(path.relative_to(workspace))
        if path.is_symlink():
            result[name] = {'kind': 'symlink', 'target': os.readlink(path)}
        elif path.is_file():
            result[name] = {'kind': 'file', 'sha256': digest(path)}
        elif path.is_dir():
            result[name] = {'kind': 'directory'}
    return result


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'Duplicate JSON key: {key}')
        value[key] = item
    return value


def assess(answer, stage, before, after):
    expected = EXPECTED[stage - 1]
    try:
        value = json.loads(answer, object_pairs_hook=unique_object)
        parse_error = None
    except (ValueError, TypeError) as exc:
        value, parse_error = None, str(exc)
    obj = value if isinstance(value, dict) else {}
    schema = isinstance(value, dict) and set(value) == set(expected)
    integers = schema and all(type(value[k]) is int for k in
                              ('reserve_units', 'requested', 'allocated', 'deferred'))
    identity = all(obj.get(k) == expected[k] for k in ('batch', 'sku', 'requested'))
    arithmetic = bool(integers and identity and
                      obj['allocated'] == min(obj['requested'], max(0, STOCK[obj['sku']] - obj['reserve_units'])) and
                      obj['deferred'] == obj['requested'] - obj['allocated'])
    changes = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    checks = {
        'json_schema': schema, 'integer_numeric_fields': bool(integers),
        'request_identity': identity,
        'corrected_fact_retained': type(obj.get('reserve_units')) is int and obj['reserve_units'] == expected['reserve_units'],
        'arithmetic_consistent_with_reported_reserve': arithmetic,
        'expected_allocation': all(type(obj.get(k)) is int and obj[k] == expected[k]
                                   for k in ('allocated', 'deferred')),
        'workspace_unchanged': not changes,
    }
    return {'stage': stage, 'checks': checks, 'passed': all(checks.values()),
            'workspace_changes': changes, 'json_parse_error': parse_error, 'observed': value}


def root_compactions(report):
    return next(t['compaction_count'] for t in report['threads'] if t['thread'] == 'root')


def boundary(before, after):
    first, last = root_compactions(before), root_compactions(after)
    return {'before': first, 'after': last, 'delta': last - first,
            'native_event_observed': last > first,
            'specified_single_boundary': first == 0 and last == 1}


def instructions(condition):
    common, rule = (TASK / 'common.md').read_text(), (TASK / 'allocation-rule.md').read_text()
    initial = (TASK / 'initial.md').read_text()
    if condition == 'chat':
        return common, rule + '\n' + initial
    if condition == 'agents':
        return common + '\n' + rule, initial
    raise ValueError(f'Unknown condition: {condition}')


def run_condition(args, condition, frozen_hashes):
    run_id = f'{args.prefix}-forced-{condition}'
    out, raw = ROOT / 'results' / run_id, args.private_root / run_id
    out.mkdir(parents=True, exist_ok=False)
    raw.mkdir(parents=True, exist_ok=False)
    workspace = raw / 'workspace'
    workspace.mkdir()
    rules, first_prompt = instructions(condition)
    continuation = (TASK / 'continuation.md').read_text()
    shutil.copyfile(TASK / 'inventory.csv', workspace / 'inventory.csv')
    (workspace / 'AGENTS.md').write_text(rules)
    for name, text in [('AGENTS.md.txt', rules), ('01-prompt.txt', first_prompt), ('02-prompt.txt', continuation)]:
        (out / name).write_text(text)
    clean = lambda text: sanitize(text, workspace, args.codex_home, args.private_root)
    def save(name, value):
        (out / name).write_text(clean(json.dumps(redact_opaque(value), indent=2)) + '\n')
    initial_files = snapshot(workspace)
    run = {'run_id': run_id, 'task': 'compaction-probe', 'policy': f'forced-{condition}',
           'condition': condition, 'started_at': utc_now(), 'status': 'running',
           'model_requested': 'gpt-6-astra', 'reasoning_requested': 'high',
           'boundary_kind': 'explicit native forced compaction',
           'input_sha256': frozen_hashes, 'instructions_sha256': digest(workspace / 'AGENTS.md'),
           'turn_timeout_seconds': args.turn_timeout, 'compaction_timeout_seconds': args.compaction_timeout,
           'subscription_attribution': 'Not claimed; schedule outside primary meter intervals', 'stages': []}
    save('run.json', run)
    session, root_id, pre, post = None, None, None, None
    started = time.monotonic()
    print(f'START {run_id}: two user turns and one explicit compaction maximum', flush=True)
    try:
        session = PersistentSession(args.codex_home, workspace, raw)
        session.start()
        root_id = session.start_thread(model='gpt-6-astra')
        run['root_thread_id'] = root_id
        first = session.run_turn(first_prompt, timeout=args.turn_timeout)
        save('01-turn.json', first)
        (out / '01-answer.txt').write_text(clean(first['answer']))
        first_check = assess(first['answer'], 1, initial_files, snapshot(workspace))
        run['stages'].append(first_check)
        save('01-validation.json', first_check)
        if first['status'] != 'completed':
            raise RuntimeError(f'Initial turn status: {first["status"]}')
        pre = collect(root_id, args.codex_home / 'sessions')
        save('pre-compaction-telemetry.json', pre)
        compaction_started = time.monotonic()
        acknowledgment = session.compact()
        remaining = max(0, args.compaction_timeout - (time.monotonic() - compaction_started))
        completion = session.wait_for_compaction(timeout=remaining)
        save('compaction.json', {'acknowledgment': acknowledgment, 'completion': completion})
        if completion['status'] != 'completed':
            raise RuntimeError('Native compaction did not report completion before the cap')
        deadline = time.monotonic() + min(5, max(0, args.compaction_timeout - (time.monotonic() - compaction_started)))
        while True:
            post = collect(root_id, args.codex_home / 'sessions')
            if root_compactions(post) > root_compactions(pre) or time.monotonic() >= deadline:
                break
            time.sleep(0.1)
        save('post-compaction-telemetry.json', post)
        run['boundary'] = boundary(pre, post)
        if not run['boundary']['native_event_observed']:
            raise RuntimeError('No newly persisted native root compaction event; continuation not attempted')
        second = session.run_turn(continuation, timeout=args.turn_timeout)
        save('02-turn.json', second)
        (out / '02-answer.txt').write_text(clean(second['answer']))
        # Standard answer filename permits existing evidence readers to inspect the final output.
        (out / 'answer.txt').write_text(clean(second['answer']))
        second_check = assess(second['answer'], 2, initial_files, snapshot(workspace))
        run['stages'].append(second_check)
        save('02-validation.json', second_check)
        if second['status'] != 'completed':
            raise RuntimeError(f'Continuation status: {second["status"]}')
        run['status'] = 'completed'
    except Exception as exc:
        run['status'] = 'incomplete'
        run['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        if session is not None:
            try:
                session.close()
            except Exception as exc:
                run['status'] = 'incomplete'
                run['close_error'] = {'type': type(exc).__name__, 'message': str(exc)}
        run['ended_at'] = utc_now()
        run['elapsed_seconds'] = round(time.monotonic() - started, 3)
        run['exit_code'] = 0 if run['status'] == 'completed' else 1
        final_files = snapshot(workspace)
        run['workspace_changes'] = sorted(name for name in initial_files.keys() | final_files.keys()
                                          if initial_files.get(name) != final_files.get(name))
        if root_id is not None:
            try:
                final = collect(root_id, args.codex_home / 'sessions')
                save('telemetry.json', final)
                rows = export(root_id, args.codex_home, workspace, until=run['ended_at'])
                (out / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
                run['credit_estimate_total'] = estimate(final['usage_by_model'])['total']
                run['single_model'] = final['thread_count'] == 1
                run['compactions_final'] = root_compactions(final)
                if pre is not None and post is not None:
                    run['credit_estimate_compaction_increment'] = (estimate(post['usage_by_model'])['total']
                                                                  - estimate(pre['usage_by_model'])['total'])
                    run['compaction_usage_growth_observed'] = (post['total_usage']['total_tokens']
                                                               > pre['total_usage']['total_tokens'])
            except Exception as exc:
                run['evidence_error'] = {'type': type(exc).__name__, 'message': str(exc)}
                run['status'] = 'incomplete'
                run['exit_code'] = 1
        valid = (run['status'] == 'completed' and len(run['stages']) == 2 and run['stages'][0]['passed']
                 and run.get('boundary', {}).get('specified_single_boundary')
                 and run.get('compactions_final') == 1 and run.get('single_model'))
        validation = {'diagnostic_valid_for_retention': bool(valid),
                      'pre_boundary': run['stages'][0] if run['stages'] else None,
                      'post_boundary': run['stages'][1] if len(run['stages']) == 2 else None,
                      'passed': bool(valid and run['stages'][1]['passed']),
                      'interpretation': 'One forced boundary; no inference about natural compaction or durability rates.'}
        save('validation.json', validation)
        save('run.json', run)
    print(f'FINISHED {run_id}: {run["status"]}; retention diagnostic valid={validation["diagnostic_valid_for_retention"]}', flush=True)
    return run, validation


def self_test():
    """Exercise false-pass risks without creating a session or invoking Codex."""
    baseline = {'inventory.csv': {'sha256': 'fixed'}}
    for stage, expected in enumerate(EXPECTED, 1):
        assert assess(json.dumps(expected), stage, baseline, baseline)['passed']
    stale = dict(EXPECTED[1], reserve_units=3, allocated=26, deferred=1)
    result = assess(json.dumps(stale), 2, baseline, baseline)
    assert result['checks']['arithmetic_consistent_with_reported_reserve']
    assert not result['checks']['corrected_fact_retained'] and not result['passed']
    assert not assess(json.dumps(EXPECTED[0]), 1, baseline, {})['passed']
    assert not assess('```json\n' + json.dumps(EXPECTED[0]) + '\n```', 1, baseline, baseline)['passed']
    assert not assess(json.dumps(dict(EXPECTED[0], reserve_units=True)), 1, baseline, baseline)['passed']
    assert not assess('{"batch":"first","batch":"first"}', 1, baseline, baseline)['passed']
    assert not assess(json.dumps(dict(EXPECTED[0], extra='note')), 1, baseline, baseline)['passed']
    report = lambda count: {'threads': [{'thread': 'root', 'compaction_count': count}]}
    assert boundary(report(0), report(1))['specified_single_boundary']
    assert not boundary(report(0), report(0))['native_event_observed']
    assert not boundary(report(1), report(2))['specified_single_boundary']
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        (path / 'inventory.csv').write_text('initial')
        before = snapshot(path)
        (path / 'notes.txt').write_text('remembered rule')
        assert not assess(json.dumps(EXPECTED[0]), 1, before, snapshot(path))['passed']
    rule = (TASK / 'allocation-rule.md').read_text()
    for condition in ('chat', 'agents'):
        agents, initial = instructions(condition)
        assert (agents + initial).count(rule) == 1
        assert (rule in agents) == (condition == 'agents')
    followup = (TASK / 'continuation.md').read_text()
    assert 'reserve_units' not in followup and 'JSON' not in followup
    print('PASS: deterministic acceptance, stale corrected fact, immutable workspace, duplicate/schema rejection, native boundary, and instruction placement; no model calls')


def bounded_seconds(text):
    value = int(text)
    if not 1 <= value <= 180:
        raise argparse.ArgumentTypeError('Use 1 through 180 seconds; this diagnostic has a fixed ceiling')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--prefix')
    parser.add_argument('--private-root', type=Path)
    parser.add_argument('--codex-home', type=Path)
    parser.add_argument('--turn-timeout', type=bounded_seconds, default=180)
    parser.add_argument('--compaction-timeout', type=bounded_seconds, default=180)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.prefix or args.private_root is None or args.codex_home is None:
        parser.error('Execution requires --prefix, --private-root, and --codex-home')
    if Path(args.prefix).name != args.prefix or args.prefix in ('.', '..'):
        parser.error('--prefix must be a single filename component')
    args.private_root, args.codex_home = args.private_root.resolve(), args.codex_home.resolve()
    if args.private_root.is_relative_to(ROOT) or args.codex_home.is_relative_to(ROOT):
        parser.error('Keep raw runs and CODEX_HOME outside the public repository')
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sorted(TASK.iterdir()) if path.is_file()}
    for path in (Path(__file__).resolve(), ROOT / 'scripts/persistent_session.py', ROOT / 'scripts/telemetry.py', ROOT / 'scripts/export_trace.py'):
        hashes[str(path.relative_to(ROOT))] = digest(path)
    campaign = ROOT / 'results' / f'{args.prefix}-forced-pair'
    campaign.mkdir(parents=True, exist_ok=False)
    manifest = {'started_at': utc_now(), 'kind': 'paired forced-compaction diagnostic',
                'order': MANIFEST['condition_order'], 'input_sha256': hashes,
                'max_user_turns': 4, 'max_explicit_compactions': 2, 'results': []}
    (campaign / 'campaign.json').write_text(json.dumps(manifest, indent=2) + '\n')
    for condition in manifest['order']:
        run, validation = run_condition(args, condition, hashes)
        manifest['results'].append({'run_id': run['run_id'], 'status': run['status'],
                                    'validation': validation, 'credit_estimate_total': run.get('credit_estimate_total')})
        (campaign / 'campaign.json').write_text(json.dumps(manifest, indent=2) + '\n')
    manifest['ended_at'] = utc_now()
    manifest['status'] = 'completed' if all(row['status'] == 'completed' for row in manifest['results']) else 'incomplete'
    (campaign / 'campaign.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return 0 if manifest['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
