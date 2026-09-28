#!/usr/bin/env python3
"""Verify public fixture hashes and reconstruct every published usage snapshot."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens','reasoning_output_tokens','total_tokens')


def main():
    fixtures = json.loads((ROOT / 'fixture-manifest.json').read_text())
    for entry in fixtures:
        actual = hashlib.sha256((ROOT / entry['path']).read_bytes()).hexdigest()
        if actual != entry['sha256']:
            raise ValueError(f"Fixture changed: {entry['path']}")
    checked = 0
    for path in sorted((ROOT / 'results').glob('*/telemetry.json')):
        telemetry = json.loads(path.read_text())
        trace = path.parent / 'trace.jsonl'
        if not trace.exists(): raise ValueError(f'Missing trace: {path.parent.name}')
        seen = set()
        observed = defaultdict(lambda: {key:0 for key in FIELDS})
        for line in trace.read_text().splitlines():
            row = json.loads(line)
            if row['kind'] != 'token_usage_record': continue
            payload = row['payload']
            identity = (row['thread'],payload['response_hash'])
            if identity in seen: continue
            seen.add(identity)
            for key in FIELDS: observed[row['thread']][key] += payload['usage'].get(key,0)
        expected = {t['thread']: t['usage'] for t in telemetry['threads']}
        if dict(observed) != expected: raise ValueError(f'Trace/telemetry mismatch: {path.parent.name}')
        checked += 1
    patterns = [
        rb'gh[pousr]_[A-Za-z0-9]{36,}', rb'github_pat_[A-Za-z0-9_]{20,}',
        rb'sk-[A-Za-z0-9_-]{30,}', rb'AKIA[0-9A-Z]{16}',
        rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        rb'gAAAA[A-Za-z0-9_-]{80,}={0,2}',
    ]
    for path in ROOT.rglob('*'):
        if not path.is_file() or any(part in ('.git','__pycache__','.venv','node_modules') for part in path.parts): continue
        contents = path.read_bytes()
        if any(re.search(pattern,contents) for pattern in patterns):
            raise ValueError(f'Credential-like or opaque content requires review: {path.relative_to(ROOT)}')
    print(json.dumps({'fixture_hashes_verified': len(fixtures), 'trace_snapshots_reconciled': checked,
                      'known_credential_and_opaque_patterns_found': 0,
                      'caveat': 'Pattern scan is not proof arbitrary data contains no secrets.'},indent=2))


if __name__ == '__main__':
    main()
