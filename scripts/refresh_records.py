#!/usr/bin/env python3
"""Regenerate publishable traces from private rollouts without changing usage snapshots.

An ended_at cutoff prevents later resumed turns appearing in an earlier run's
trace. Run output must still be reviewed for task-specific sensitive content.
"""
import argparse
import json
from pathlib import Path
from export_trace import export, redact_opaque

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--codex-home', type=Path, required=True)
    ap.add_argument('--private-root', type=Path, required=True)
    ap.add_argument('--prefix', default='', help='Only export run IDs starting with this prefix')
    args = ap.parse_args()
    metadata = {}
    for path in (ROOT / 'results').glob('*/run.json'):
        data = json.loads(path.read_text())
        if not path.parent.name.startswith(args.prefix):
            continue
        if data.get('ended_at') and data.get('root_thread_id'):
            metadata[path.parent] = data
    original_workspace = {m['root_thread_id']: args.private_root.resolve() / m['run_id'] / 'workspace'
                          for m in metadata.values() if not m.get('resume')}
    for directory, data in sorted(metadata.items()):
        root = data['root_thread_id']
        rows = export(root, args.codex_home.resolve(), original_workspace.get(root), until=data['ended_at'])
        (directory / 'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        events = directory / 'events.jsonl'
        if events.exists():
            lines = [json.dumps(redact_opaque(json.loads(line))) for line in events.read_text().splitlines() if line.strip()]
            events.write_text('\n'.join(lines)+'\n')
        print(f'{directory.name}: {len(rows)} evidence records')


if __name__ == '__main__':
    main()
