#!/usr/bin/env python3
"""Deterministic six-session policy comparison; raw runtime traffic stays private."""
import argparse
import difflib
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone
from persistent_session import PersistentSession
from telemetry import collect, quota
from export_trace import export, redact_opaque
from run_trial import sanitize
from summarize import estimate

ROOT = Path(__file__).resolve().parents[1]
ORDER = [('a','default'), ('a','rory'), ('a','rory-long'), ('b','rory-long'), ('b','rory'), ('b','default')]

def now(): return datetime.now(timezone.utc).isoformat()
def write_json(path, value): path.write_text(json.dumps(value, indent=2)+'\n')
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def instruction(policy):
    common = (ROOT/'policies/sustained-common.md').read_text()
    if policy == 'default': return common
    filename = 'rory-v2.md' if policy == 'rory' else 'rory-long.md'
    rules = (ROOT/'policies'/filename).read_text().replace(
        "[If inheriting context forces the parent's model, state that here as a fact and what to do about it.]",
        'In this harness, use fork_turns=none to request a fresh worker with its explicitly selected model.')
    return common+'\n'+rules

def patch(original, workspace):
    result=[]
    paths={p.relative_to(original) for p in original.rglob('*') if p.is_file()} | {p.relative_to(workspace) for p in workspace.rglob('*') if p.is_file()}
    for rel in sorted(paths):
        if rel==Path('AGENTS.md') or any(x in rel.parts for x in ['.git','node_modules','__pycache__']): continue
        before, after=original/rel,workspace/rel
        try:
            a=before.read_text().splitlines(keepends=True) if before.exists() else []
            b=after.read_text().splitlines(keepends=True) if after.exists() else []
        except UnicodeDecodeError: continue
        if a!=b: result.extend(difflib.unified_diff(a,b,fromfile='a/'+str(rel),tofile='b/'+str(rel)))
    return ''.join(result)

def evaluate(workspace, stream, stage):
    command=['python3',str(ROOT/'evaluation/evaluate_sustained.py'),str(workspace),'--workstream',stream,'--stage',str(stage)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=180)
    try: report=json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Evaluator did not return JSON: exit={result.returncode}; {result.stderr[-1500:]}') from exc
    return {'exit_code':result.returncode,'report':report,'stderr':result.stderr}

def bucket_identity(meter):
    return {k: {window: (v.get(window) or {}).get('resets_at') for window in ['primary','secondary']} for k,v in meter['buckets'].items()}

def increases(first, last):
    values=[]
    for name, bucket in first['buckets'].items():
        for window in ['primary','secondary']:
            a,b=bucket.get(window),last['buckets'].get(name,{}).get(window)
            if a and b: values.append(b['used_percent']-a['used_percent'])
    return max(values,default=0)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--prefix',required=True)
    ap.add_argument('--private-root',type=Path,required=True)
    ap.add_argument('--codex-home',type=Path,required=True)
    ap.add_argument('--account-coordination',choices=['confirmed','unconfirmed'],default='unconfirmed')
    ap.add_argument('--supervision',choices=['quiet','active'],default='active')
    ap.add_argument('--start-at',type=int,default=0)
    args=ap.parse_args()
    home=args.codex_home.resolve(); private=args.private_root.resolve()
    campaign=ROOT/'results'/f'{args.prefix}-campaign'
    campaign.mkdir(parents=True,exist_ok=args.start_at>0)
    def meter(label):
        value=quota(codex_home=home)
        write_json(campaign/f'quota-{label}.json',value)
        return value
    manifest={str(p.relative_to(ROOT)):digest(p) for parent in [ROOT/'tasks/sustained-a',ROOT/'tasks/sustained-b'] for p in parent.rglob('*') if p.is_file()}
    for name in ['scripts/run_sustained.py','scripts/persistent_session.py','evaluation/evaluate_sustained.py','evaluation/sustained_cases.mjs','policies/sustained-common.md','policies/rory-v2.md','policies/rory-long.md','specs/plans/0002-faithful-sustained-comparison.md']:
        manifest[name]=digest(ROOT/name)
    meta={'started_at':now(),'order':ORDER,'input_sha256':manifest,'account_coordination':args.account_coordination,'supervision':args.supervision,'completed_sessions':[], 'hard_caps':{'turn_seconds':600,'session_seconds':3600,'credit_estimate':800,'observed_quota_points':10}}
    if args.start_at:
        previous=json.loads((campaign/'campaign.json').read_text())
        if previous['input_sha256'] != manifest: raise ValueError('Frozen inputs changed')
        meta=previous
        first=json.loads((campaign/'quota-initial.json').read_text())
    else:
        write_json(campaign/'campaign.json',meta)
        first=meter('initial')
        print('CALIBRATION: 60-second idle observation; no trial request active',flush=True)
        time.sleep(60)
        meter('idle-end')
    spent=sum(item['credit_estimate'] for item in meta['completed_sessions'])
    for index,(stream,policy) in enumerate(ORDER):
        if index < args.start_at: continue
        run_id=f'{args.prefix}-{stream}-{policy}'
        out=ROOT/'results'/run_id; out.mkdir()
        raw=private/run_id; raw.mkdir(parents=True)
        workspace=raw/'workspace'
        original=ROOT/'fixtures/current'
        shutil.copytree(original,workspace)
        (workspace/'AGENTS.md').write_text(instruction(policy))
        (out/'AGENTS.md.txt').write_text(instruction(policy))
        clean=lambda s: sanitize(s,workspace,home,private)
        save=lambda path, data: path.write_text(clean(json.dumps(redact_opaque(data),indent=2))+'\n')
        definition=json.loads((ROOT/f'tasks/sustained-{stream}/metadata.json').read_text())
        prompts=[ROOT/entry['prompt_file'] for entry in definition['stages']]
        if len(prompts)!=8: raise ValueError(f'Expected eight prompts, found {len(prompts)}')
        run={'run_id':run_id,'task':f'sustained-{stream}','policy':policy,'started_at':now(),'status':'running','account_coordination':args.account_coordination,'supervision':args.supervision,'stages':[]}
        save(out/'run.json',run)
        before=meter(f'{index+1}-before'); save(out/'quota-before.json',before)
        start=time.monotonic(); total_elapsed=0; current_credit=0
        print(f'BLOCK {index+1}/6 START {run_id}',flush=True)
        session=PersistentSession(home,workspace,raw).start()
        try:
            root_id=session.start_thread(model='gpt-6-astra')
            run['root_thread_id']=root_id
            for stage,prompt_file in enumerate(prompts,1):
                if time.monotonic()-start>=3600 or spent+current_credit>=800:
                    run['status']='capped'; break
                prompt=prompt_file.read_text()
                record={'stage':stage,'prompt_sha256':digest(prompt_file),'attempts':[]}
                (out/f'{stage:02d}-prompt.txt').write_text(prompt)
                for attempt in range(2):
                    print(f'BLOCK {index+1}/6 STAGE {stage}/8 ATTEMPT {attempt+1}',flush=True)
                    result=session.run_turn(prompt,timeout=min(600,max(1,3600-int(time.monotonic()-start))))
                    save(out/f'{stage:02d}-{attempt+1}-turn.json',result)
                    answer=result.get('answer',''); (out/f'{stage:02d}-{attempt+1}-answer.txt').write_text(clean(answer))
                    total_elapsed+=result['elapsed_seconds']
                    report=collect(root_id,home/'sessions')
                    current_credit=estimate(report['usage_by_model'])['total']
                    attempt_record={'attempt':attempt+1,'elapsed_seconds':result['elapsed_seconds'],'status':result['status'],'cumulative_credit_estimate':current_credit}
                    if result.get('timed_out') or result['status']!='completed':
                        attempt_record['runtime_failed']=True
                        record['attempts'].append(attempt_record)
                        run['status']='runtime-failed'; break
                    validation=evaluate(workspace,stream,stage)
                    save(out/f'{stage:02d}-{attempt+1}-validation.json',validation)
                    attempt_record['passed']=validation['exit_code']==0
                    record['attempts'].append(attempt_record)
                    print(f'BLOCK {index+1}/6 STAGE {stage}/8 CHECK passed={attempt_record["passed"]} credits={current_credit:.3f}',flush=True)
                    if attempt_record['passed'] or attempt==1 or spent+current_credit>=800: break
                    prompt='The external acceptance checks for this stage failed. Fix the failures within the existing requested scope, run relevant checks, and summarize the repair. Do not change prior constraints. This is the single repair opportunity for this stage.\n\n'+json.dumps(validation['report'].get('repair_feedback',validation['report']),indent=2)
                    (out/f'{stage:02d}-repair-prompt.txt').write_text(clean(prompt))
                run['stages'].append(record)
                run['elapsed_seconds']=round(total_elapsed,3)
                save(out/'run.json',run)
                if run['status']=='runtime-failed': break
            else: run['status']='completed'
        finally:
            session.close()
        run['ended_at']=now()
        report=collect(root_id,home/'sessions')
        save(out/'telemetry.json',report)
        trace=export(root_id,home,workspace,until=run['ended_at'])
        (out/'trace.jsonl').write_text(''.join(clean(json.dumps(row))+'\n' for row in trace))
        run['credit_estimate']=estimate(report['usage_by_model'])
        run['usage_scope']='Persisted full tree after transport shutdown; failed/interrupted requests may have unreported provider usage.'
        spent+=run['credit_estimate']['total']
        (out/'changes.patch').write_text(clean(patch(original,workspace)))
        save(out/'run.json',run)
        after=meter(f'{index+1}-after'); save(out/'quota-after.json',after)
        print(f'BLOCK {index+1}/6 FINISHED status={run["status"]}; settling 60s',flush=True)
        time.sleep(60)
        settled=meter(f'{index+1}-settled'); save(out/'quota-settled.json',settled)
        meta['completed_sessions'].append({'run_id':run_id,'credit_estimate':run['credit_estimate']['total'],'status':run['status']})
        write_json(campaign/'campaign.json',meta)
        if bucket_identity(first)!=bucket_identity(settled) or increases(first,settled)>=10 or spent>=800:
            meta['stop_reason']='campaign cap or quota reset reached'; break
    meta['ended_at']=now();meta['execution_credit_estimate']=spent
    write_json(campaign/'campaign.json',meta)
    print(f'CAMPAIGN FINISHED {len(meta["completed_sessions"])}/6 blocks; credits={spent:.3f}',flush=True)

if __name__=='__main__': main()
