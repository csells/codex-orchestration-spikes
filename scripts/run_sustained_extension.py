#!/usr/bin/env python3
"""Finish the three original B arms; never rerun the completed A arms.

Original records remain intact. The resumed long arm's final telemetry is
cumulative; only its increase over the saved five-stage baseline counts toward
this extension's budget. All B arms restart transport after stage five. Caps
are checked between requests, so a final in-flight request can cross the credit
or rounded account-meter threshold. No supervising or grading model is used.
"""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shutil
import time

from run_sustained import (ROOT, PersistentSession, bucket_identity, collect,
                          digest, estimate, evaluate, export, increases,
                          instruction, now, patch, quota, redact_opaque,
                          sanitize, write_json)

ADDITIONAL_CREDIT_CAP = 650
SESSION_SECONDS = 3600
TURN_SECONDS = 600
QUOTA_POINTS = 10


def additional_credit(cumulative, baseline):
    delta = cumulative - baseline
    if delta < -1e-7:
        raise ValueError("Cumulative accounting fell below the preserved baseline")
    return max(0.0, delta)


def meter_stop_reason(first, latest):
    if bucket_identity(first) != bucket_identity(latest):
        return "quota window or bucket changed"
    if increases(first, latest) >= QUOTA_POINTS:
        return "extension observed quota-point cap reached"
    return None


def validate_original(prefix, private, home):
    original_campaign = ROOT / 'results' / f'{prefix}-campaign' / 'campaign.json'
    campaign = json.loads(original_campaign.read_text())
    for name, expected in campaign['input_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError(f'Original frozen input changed: {name}')
    run_id = f'{prefix}-b-rory-long'
    source = ROOT / 'results' / run_id
    run = json.loads((source / 'run.json').read_text())
    if run['status'] != 'capped' or [r['stage'] for r in run['stages']] != list(range(1, 6)):
        raise ValueError('Expected the original capped B-long run at stage five')
    if not all(r['attempts'][-1].get('passed') for r in run['stages']):
        raise ValueError('The five preserved baseline stages must have passed')
    workspace = private / run_id / 'workspace'
    if (workspace / 'AGENTS.md').read_text() != instruction('rory-long'):
        raise ValueError('Resumed workspace instructions changed')
    baseline = json.loads((source / 'telemetry.json').read_text())
    current = collect(run['root_thread_id'], home / 'sessions')
    # Do not overwrite a historical snapshot with newly discovered usage.
    if current['total_usage'] != baseline['total_usage'] or current['usage_by_model'] != baseline['usage_by_model']:
        raise ValueError('Current B-long usage differs from the preserved baseline')
    if abs(estimate(baseline['usage_by_model'])['total'] - run['credit_estimate']['total']) > 1e-7:
        raise ValueError('Baseline credit estimate does not match its telemetry')
    return campaign, source, run, workspace


def run_extension(args):
    home = args.codex_home.resolve()
    private = args.private_root.resolve()
    original_campaign, source, baseline_run, resumed_workspace = validate_original(args.prefix, private, home)
    order = [f'{args.prefix}-b-rory-long-completed', f'{args.prefix}-b-rory', f'{args.prefix}-b-default']
    campaign_dir = ROOT / 'results' / f'{args.prefix}-extension-campaign'
    if campaign_dir.exists() or any((ROOT / 'results' / run_id).exists() for run_id in order):
        raise ValueError('Extension output already exists; refusing duplicate runs or overwritten records')
    campaign_dir.mkdir(parents=True)
    manifest = dict(original_campaign['input_sha256'])
    manifest['scripts/run_sustained_extension.py'] = digest(Path(__file__).resolve())
    extension_protocol = ROOT / 'specs/plans/0003-complete-frozen-comparison.md'
    manifest[str(extension_protocol.relative_to(ROOT))] = digest(extension_protocol)
    meta = {'started_at': now(), 'order': order, 'input_sha256': manifest,
            'extends_campaign': f'{args.prefix}-campaign', 'account_coordination': args.account_coordination,
            'supervision': args.supervision, 'completed_sessions': [],
            'hard_caps': {'additional_credit_estimate': ADDITIONAL_CREDIT_CAP, 'session_active_seconds': SESSION_SECONDS,
                          'turn_seconds': TURN_SECONDS, 'observed_quota_points': QUOTA_POINTS},
            'budget_semantics': 'Check before each request; a request already in flight may cross a threshold.',
            'transport_boundary': 'One close/resume after stage five in every original B arm; root ID preserved.',
            'accounting': 'Long-completed includes original stages 1-5. Add only its incremental credits to original campaign spend.'}
    write_json(campaign_dir / 'campaign.json', meta)

    def meter(label):
        value = quota(codex_home=home)
        write_json(campaign_dir / f'quota-{label}.json', value)
        return value

    first = meter('initial')
    print('EXTENSION CALIBRATION: 60-second idle observation; no trial request active', flush=True)
    time.sleep(60)
    latest = meter('idle-end')
    spent = 0.0
    stop = meter_stop_reason(first, latest)
    for index, (policy, run_id) in enumerate(zip(['rory-long', 'rory', 'default'], order), 1):
        if stop or spent >= ADDITIONAL_CREDIT_CAP:
            break
        out = ROOT / 'results' / run_id
        raw = private / run_id
        raw.mkdir(parents=True, exist_ok=False)
        baseline_credit = baseline_run['credit_estimate']['total'] if index == 1 else 0.0
        prior_active_seconds = 0.0
        if index == 1:
            shutil.copytree(source, out)
            workspace = resumed_workspace
            run = deepcopy(baseline_run)
            run.update({'run_id': run_id, 'status': 'running', 'extends_run_id': baseline_run['run_id'],
                        'extension_started_at': now(), 'baseline_credit_estimate': baseline_credit,
                        'baseline_stage_count': 5,
                        'baseline_artifact_sha256': {p.name: digest(p) for p in source.iterdir() if p.is_file()}})
            for name in ['quota-before.json', 'quota-after.json', 'quota-settled.json']:
                if (out / name).exists():
                    (out / name).rename(out / f'baseline-{name}')
            prior_active_seconds = (datetime.fromisoformat(baseline_run['ended_at']) -
                                    datetime.fromisoformat(baseline_run['started_at'])).total_seconds()
            first_stage = 6
            total_elapsed = baseline_run['elapsed_seconds']
        else:
            out.mkdir()
            workspace = raw / 'workspace'
            shutil.copytree(ROOT / 'fixtures/current', workspace)
            (workspace / 'AGENTS.md').write_text(instruction(policy))
            (out / 'AGENTS.md.txt').write_text(instruction(policy))
            run = {'run_id': run_id, 'task': 'sustained-b', 'policy': policy, 'started_at': now(),
                   'status': 'running', 'stages': [], 'baseline_credit_estimate': 0.0, 'baseline_stage_count': 0}
            first_stage = 1
            total_elapsed = 0.0
        run.update({'account_coordination': args.account_coordination, 'supervision': args.supervision,
                    'transport_boundary_after_stage': 5, 'transport_events': []})
        clean = lambda text: sanitize(text, workspace, home, private)
        save = lambda path, data: path.write_text(clean(json.dumps(redact_opaque(data), indent=2)) + '\n')
        save(out / 'run.json', run)
        definition = json.loads((ROOT / 'tasks/sustained-b/metadata.json').read_text())
        prompts = [ROOT / entry['prompt_file'] for entry in definition['stages']]
        if len(prompts) != 8:
            raise ValueError('Expected the original eight B prompts')
        latest = meter(f'{index}-before')
        save(out / 'quota-before.json', latest)
        stop = meter_stop_reason(first, latest)
        current_credit = baseline_credit
        start = time.monotonic()
        extension_turn_seconds = 0.0
        root_id = baseline_run['root_thread_id'] if index == 1 else None
        session = None

        def remaining_seconds():
            return SESSION_SECONDS - prior_active_seconds - (time.monotonic() - start)

        def cap_reason():
            if remaining_seconds() <= 0:
                return 'active-session time cap reached'
            if spent + additional_credit(current_credit, baseline_credit) >= ADDITIONAL_CREDIT_CAP:
                return 'extension additional-credit cap reached'
            return stop

        print(f'EXTENSION BLOCK {index}/3 START {run_id} stage={first_stage}', flush=True)
        try:
            if cap_reason():
                run['status'] = 'capped'
                run['stop_reason'] = cap_reason()
            else:
                session = PersistentSession(home, workspace, raw).start()
                if index == 1:
                    actual = session.resume_thread(root_id)
                    if actual != root_id:
                        raise RuntimeError('Resume changed the original root thread ID')
                    run['transport_events'].append({'after_stage': 5, 'closed_at': baseline_run['ended_at'],
                                                    'resumed_at': now(), 'root_thread_id': root_id,
                                                    'interruption': 'Original campaign budget cap; pause excluded from active-session time.'})
                else:
                    root_id = session.start_thread(model='gpt-6-astra')
                run['root_thread_id'] = root_id
                for stage in range(first_stage, 9):
                    if cap_reason():
                        run['status'] = 'capped'; run['stop_reason'] = cap_reason(); break
                    # Match the original capped long arm's transport boundary.
                    if stage == 6 and first_stage == 1:
                        session.close()
                        closed_at = now()
                        session = PersistentSession(home, workspace, raw).start()
                        if session.resume_thread(root_id) != root_id:
                            raise RuntimeError('Transport restart changed the root thread ID')
                        run['transport_events'].append({'after_stage': 5, 'closed_at': closed_at,
                                                        'resumed_at': now(), 'root_thread_id': root_id,
                                                        'interruption': 'Matched stage-five transport restart.'})
                    prompt_file = prompts[stage - 1]
                    prompt = prompt_file.read_text()
                    record = {'stage': stage, 'prompt_sha256': digest(prompt_file), 'attempts': []}
                    (out / f'{stage:02d}-prompt.txt').write_text(prompt)
                    for attempt in range(2):
                        if cap_reason():
                            run['status'] = 'capped'; run['stop_reason'] = cap_reason(); break
                        print(f'EXTENSION BLOCK {index}/3 STAGE {stage}/8 ATTEMPT {attempt+1}', flush=True)
                        result = session.run_turn(prompt, timeout=min(TURN_SECONDS, max(1, int(remaining_seconds()))))
                        save(out / f'{stage:02d}-{attempt+1}-turn.json', result)
                        (out / f'{stage:02d}-{attempt+1}-answer.txt').write_text(clean(result.get('answer', '')))
                        total_elapsed += result['elapsed_seconds']
                        extension_turn_seconds += result['elapsed_seconds']
                        report = collect(root_id, home / 'sessions')
                        current_credit = estimate(report['usage_by_model'])['total']
                        attempt_record = {'attempt': attempt+1, 'elapsed_seconds': result['elapsed_seconds'],
                                          'status': result['status'], 'cumulative_credit_estimate': current_credit,
                                          'extension_credit_estimate': additional_credit(current_credit, baseline_credit)}
                        if result.get('timed_out') or result['status'] != 'completed':
                            attempt_record['runtime_failed'] = True
                            record['attempts'].append(attempt_record)
                            run['status'] = 'runtime-failed'; break
                        validation = evaluate(workspace, 'b', stage)
                        save(out / f'{stage:02d}-{attempt+1}-validation.json', validation)
                        attempt_record['passed'] = validation['exit_code'] == 0
                        record['attempts'].append(attempt_record)
                        print(f'EXTENSION BLOCK {index}/3 STAGE {stage}/8 CHECK passed={attempt_record["passed"]} credits={current_credit:.3f}', flush=True)
                        latest = meter(f'{index}-stage-{stage}-attempt-{attempt+1}')
                        stop = meter_stop_reason(first, latest)
                        if attempt_record['passed'] or attempt == 1 or cap_reason():
                            break
                        prompt = ('The external acceptance checks for this stage failed. Fix the failures within the existing requested scope, run relevant checks, and summarize the repair. Do not change prior constraints. This is the single repair opportunity for this stage.\n\n' +
                                  json.dumps(validation['report'].get('repair_feedback', validation['report']), indent=2))
                        (out / f'{stage:02d}-repair-prompt.txt').write_text(clean(prompt))
                    run['stages'].append(record)
                    run['elapsed_seconds'] = round(total_elapsed, 3)
                    save(out / 'run.json', run)
                    if run['status'] in ('runtime-failed', 'capped'):
                        break
                else:
                    run['status'] = 'completed'
        except Exception as exc:
            run['status'] = 'runtime-failed'
            run['error'] = f'{type(exc).__name__}: {exc}'
        finally:
            if session is not None:
                session.close()
        run['ended_at'] = now()
        run['extension_elapsed_seconds'] = round(extension_turn_seconds, 3)
        run['active_session_elapsed_seconds'] = round(prior_active_seconds + time.monotonic() - start, 3)
        if root_id is not None:
            report = collect(root_id, home / 'sessions')
            save(out / 'telemetry.json', report)
            trace = export(root_id, home, workspace, until=run['ended_at'])
            (out / 'trace.jsonl').write_text(''.join(clean(json.dumps(row)) + '\n' for row in trace))
            run['credit_estimate'] = estimate(report['usage_by_model'])
        else:
            run['credit_estimate'] = {'by_model': {}, 'total': 0.0}
        run['additional_credit_estimate'] = additional_credit(run['credit_estimate']['total'], baseline_credit)
        run['usage_scope'] = 'Persisted full tree after transport shutdown; failed/interrupted requests may have unreported provider usage.'
        spent += run['additional_credit_estimate']
        (out / 'changes.patch').write_text(clean(patch(ROOT / 'fixtures/current', workspace)))
        save(out / 'run.json', run)
        latest = meter(f'{index}-after')
        save(out / 'quota-after.json', latest)
        print(f'EXTENSION BLOCK {index}/3 FINISHED status={run["status"]}; settling 60s', flush=True)
        time.sleep(60)
        latest = meter(f'{index}-settled')
        save(out / 'quota-settled.json', latest)
        meta['completed_sessions'].append({'run_id': run_id, 'status': run['status'],
                                          'credit_estimate': run['credit_estimate']['total'],
                                          'baseline_credit_estimate': baseline_credit,
                                          'additional_credit_estimate': run['additional_credit_estimate']})
        meta['additional_execution_credit_estimate'] = spent
        write_json(campaign_dir / 'campaign.json', meta)
        stop = meter_stop_reason(first, latest)
    meta['ended_at'] = now()
    meta['additional_execution_credit_estimate'] = spent
    if stop or spent >= ADDITIONAL_CREDIT_CAP:
        meta['stop_reason'] = stop or 'extension additional-credit cap reached'
    write_json(campaign_dir / 'campaign.json', meta)
    print(f'EXTENSION FINISHED {len(meta["completed_sessions"])}/3 blocks; additional credits={spent:.3f}', flush=True)
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-test', action='store_true', help='Run synthetic transport/accounting checks; no model calls')
    ap.add_argument('--prefix', default='faithful')
    ap.add_argument('--private-root', type=Path)
    ap.add_argument('--codex-home', type=Path)
    ap.add_argument('--account-coordination', choices=['confirmed', 'unconfirmed'], default='unconfirmed')
    ap.add_argument('--supervision', choices=['quiet', 'active'], default='active')
    args = ap.parse_args()
    if args.self_test:
        self_test()
    elif args.private_root is None or args.codex_home is None:
        ap.error('--private-root and --codex-home are required for a real extension')
    else:
        run_extension(args)


def self_test():
    """Exercise all extension arms against a fake transport, never a provider."""
    import tempfile
    from types import SimpleNamespace
    from unittest.mock import patch as mock_patch
    import sys

    with tempfile.TemporaryDirectory(prefix='sustained-extension-selftest-') as directory:
        root = Path(directory)
        source = root / 'results/test-b-rory-long'
        source.mkdir(parents=True)
        private = root / 'private'
        workspace = private / 'test-b-rory-long/workspace'
        workspace.mkdir(parents=True)
        (workspace / 'AGENTS.md').write_text('synthetic instructions')
        (root / 'fixtures/current').mkdir(parents=True)
        (root / 'fixtures/current/fixture.txt').write_text('synthetic fixture')
        task = root / 'tasks/sustained-b'
        task.mkdir(parents=True)
        (root / 'specs/plans').mkdir(parents=True)
        (root / 'specs/plans/0003-complete-frozen-comparison.md').write_text('synthetic extension protocol')
        for stage in range(1, 9):
            (task / f'{stage}.txt').write_text(f'stage {stage}')
        write_json(task / 'metadata.json', {'stages': [{'prompt_file': f'tasks/sustained-b/{stage}.txt'} for stage in range(1, 9)]})
        baseline = {'run_id': 'test-b-rory-long', 'task': 'sustained-b', 'policy': 'rory-long',
                    'root_thread_id': 'root-1', 'status': 'capped', 'elapsed_seconds': 5,
                    'started_at': '2026-01-01T00:00:00+00:00', 'ended_at': '2026-01-01T00:00:05+00:00',
                    'credit_estimate': {'total': 50},
                    'stages': [{'stage': stage, 'attempts': [{'passed': True}]} for stage in range(1, 6)]}
        write_json(source / 'run.json', baseline)
        preserved = (source / 'run.json').read_bytes()
        counts = {'root-1': 5}
        events = []
        checks = {}

        class FakeSession:
            def __init__(self, home, cwd, rawdir):
                self.root_id = None
            def start(self):
                return self
            def start_thread(self, model):
                self.root_id = f'root-{len(counts)+1}'
                counts[self.root_id] = 0
                events.append(('start', self.root_id, 0))
                return self.root_id
            def resume_thread(self, root_id):
                self.root_id = root_id
                events.append(('resume', root_id, counts[root_id]))
                return root_id
            def run_turn(self, prompt, timeout):
                assert 0 < timeout <= TURN_SECONDS
                counts[self.root_id] += 1
                return {'status': 'completed', 'answer': 'synthetic answer', 'timed_out': False, 'elapsed_seconds': 1}
            def close(self):
                events.append(('close', self.root_id, counts.get(self.root_id)))

        def fake_collect(root_id, sessions):
            return {'usage_by_model': {'synthetic_credits': counts[root_id]*10}}

        def fake_evaluate(cwd, stream, stage):
            key = (cwd.parent.name, stage)
            checks[key] = checks.get(key, 0) + 1
            failed = key == ('test-b-rory', 2) and checks[key] == 1
            return {'exit_code': int(failed), 'report': {'repair_feedback': 'synthetic failure'}, 'stderr': ''}

        meter = {'buckets': {'codex': {'primary': {'used_percent': 1, 'resets_at': 9999}}}}
        replacements = {'ROOT': root, 'PersistentSession': FakeSession,
                        'validate_original': lambda *a: ({'input_sha256': {}}, source, baseline, workspace),
                        'instruction': lambda policy: 'synthetic instructions', 'collect': fake_collect,
                        'evaluate': fake_evaluate, 'quota': lambda **kw: deepcopy(meter),
                        'estimate': lambda usage: {'by_model': {}, 'total': usage['synthetic_credits']},
                        'export': lambda *a, **kw: [{'kind': 'synthetic'}], 'patch': lambda *a: ''}
        with mock_patch.multiple(sys.modules[__name__], **replacements), mock_patch.object(time, 'sleep', lambda seconds: None):
            result = run_extension(SimpleNamespace(prefix='test', private_root=private,
                                                  codex_home=root/'home', account_coordination='unconfirmed', supervision='quiet'))
        assert len(result['completed_sessions']) == 3
        assert [counts[f'root-{i}'] for i in (1, 2, 3)] == [8, 9, 8]
        assert result['additional_execution_credit_estimate'] == 200
        assert [entry['additional_credit_estimate'] for entry in result['completed_sessions']] == [30, 90, 80]
        assert [(e[1], e[2]) for e in events if e[0] == 'resume'] == [('root-1', 5), ('root-2', 6), ('root-3', 5)]
        for name in ('test-b-rory-long-completed', 'test-b-rory', 'test-b-default'):
            run = json.loads((root / 'results' / name / 'run.json').read_text())
            assert run['status'] == 'completed' and len(run['stages']) == 8
            assert len(run['transport_events']) == 1 and run['transport_boundary_after_stage'] == 5
        assert (source / 'run.json').read_bytes() == preserved
        reset = deepcopy(meter); reset['buckets']['codex']['primary']['resets_at'] += 1
        capped = deepcopy(meter); capped['buckets']['codex']['primary']['used_percent'] += 10
        assert meter_stop_reason(meter, reset) and meter_stop_reason(meter, capped)
        try:
            additional_credit(49, 50)
        except ValueError:
            pass
        else:
            raise AssertionError('Negative incremental accounting was accepted')
    print('EXTENSION SELF-TEST PASSED: three arms, one repair, same-root resumes, preserved baseline, no double counting.', flush=True)


if __name__ == '__main__':
    main()
