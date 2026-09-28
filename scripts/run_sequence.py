#!/usr/bin/env python3
"""Run the frozen five-turn pair, alternating condition order by stage.

Resumes a completed stage only from its retained metadata; never silently reruns
or overwrites a failed/incomplete attempt. Telemetry snapshots are cumulative.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--private-root', type=Path, required=True)
    ap.add_argument('--codex-home', type=Path, required=True)
    ap.add_argument('--prefix', default='sequence')
    args = ap.parse_args()
    private = args.private_root.resolve()
    home = args.codex_home.resolve()
    for stage in range(1, 6):
        policies = ['default', 'bounded-sol'] if stage % 2 else ['bounded-sol', 'default']
        for policy in policies:
            name = f'{args.prefix}-{policy}-{stage}'
            meta = ROOT / 'results' / name / 'run.json'
            if meta.exists():
                prior = json.loads(meta.read_text())
                if prior.get('exit_code') == 0 and not prior.get('timed_out'):
                    print(f'KEEP completed {name}', flush=True)
                    continue
                raise RuntimeError(f'Preserve incomplete/failed attempt {name}; review before continuing')
            cmd = [sys.executable, '-u', str(ROOT / 'scripts/run_trial.py'),
                   '--task', f'session-{stage}', '--policy', policy, '--run-id', name,
                   '--private-root', str(private), '--codex-home', str(home)]
            if stage > 1:
                first_name = f'{args.prefix}-{policy}-1'
                first = json.loads((ROOT / 'results' / first_name / 'run.json').read_text())
                cmd += ['--resume', first['root_thread_id'],
                        '--workspace', str(private / first_name / 'workspace')]
            completed = subprocess.run(cmd)
            if completed.returncode:
                raise RuntimeError(f'{name} failed; attempt retained for review')
    print('SEQUENCE pair complete', flush=True)


if __name__ == '__main__':
    main()
