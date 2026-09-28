#!/usr/bin/env python3
"""Summarize completed related-work sessions without adding cumulative snapshots."""
import argparse
import json
from pathlib import Path
from summarize import estimate

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default='sequence')
    args = ap.parse_args()
    sessions = []
    for policy in ['default', 'bounded-sol']:
        stages = []
        previous_credit = 0
        previous_input = 0
        for stage in range(1,6):
            folder = ROOT / 'results' / f'{args.prefix}-{policy}-{stage}'
            metadata = json.loads((folder / 'run.json').read_text())
            report = json.loads((folder / 'telemetry.json').read_text())
            validation = json.loads((folder / 'validation.json').read_text()) if (folder / 'validation.json').exists() else None
            credit = estimate(report['usage_by_model'])['total']
            root = next(t for t in report['threads'] if t['thread'] == 'root')
            stages.append({
                'stage': stage, 'run_id': folder.name,
                'elapsed_seconds': metadata['elapsed_seconds'],
                'credits_cumulative': credit,
                'credits_increment': credit-previous_credit,
                'full_tree_input_cumulative': report['total_usage']['input_tokens'],
                'full_tree_input_increment': report['total_usage']['input_tokens']-previous_input,
                'root_last_request_input_tokens': root['context_proxy']['last_request_input_tokens'],
                'root_peak_request_input_tokens_cumulative': root['context_proxy']['peak_request_input_tokens'],
                'root_compactions_cumulative': root['compaction_count'],
                'all_thread_compactions_cumulative': sum(t['compaction_count'] for t in report['threads']),
                'worker_count_cumulative': report['thread_count']-1,
                'validation': validation,
            })
            previous_credit = credit
            previous_input = report['total_usage']['input_tokens']
        graded = all(s['validation'] is not None for s in stages)
        sessions.append({
            'policy': policy, 'stages': stages,
            'credits_total': stages[-1]['credits_cumulative'],
            'elapsed_seconds_total': round(sum(s['elapsed_seconds'] for s in stages),3),
            'root_peak_request_input_tokens': stages[-1]['root_peak_request_input_tokens_cumulative'],
            'root_compactions': stages[-1]['root_compactions_cumulative'],
            'all_thread_compactions': stages[-1]['all_thread_compactions_cumulative'],
            'workers_total': stages[-1]['worker_count_cumulative'],
            'score': sum(s['validation']['score'] for s in stages) if graded else None,
            'max_score': 34,
            'stages_passed': sum(bool(s['validation']['passed']) for s in stages) if graded else None,
            'constraint_retained': stages[-1]['validation'].get('constraint_retained') if graded else None,
        })
    result = {'prefix': args.prefix,
              'method': 'Final snapshot for cumulative costs; stage increments by subtraction; elapsed time summed across turns. Context values are provider input footprints, not exact occupancy.',
              'sessions': sessions}
    output = ROOT / 'results' / f'{args.prefix}-summary.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({s['policy']: {k:v for k,v in s.items() if k != 'stages'} for s in sessions}, indent=2))


if __name__ == '__main__':
    main()
