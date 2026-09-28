#!/usr/bin/env python3
"""Functional heldout evaluator; never place this/evaluator data in model workspaces."""
import argparse, json, pathlib, shutil, subprocess, tempfile, time
p=argparse.ArgumentParser()
p.add_argument('workspace',type=pathlib.Path)
p.add_argument('--workstream',choices=['a','b'],required=True)
p.add_argument('--stage',type=int,choices=range(1,9),required=True)
p.add_argument('--json-output',type=pathlib.Path)
a=p.parse_args()
base=pathlib.Path(__file__).resolve().parent
started=time.monotonic()
with tempfile.TemporaryDirectory(prefix='sustained-evaluate-') as temporary:
    candidate=pathlib.Path(temporary)/'candidate'
    shutil.copytree(a.workspace.resolve(),candidate,ignore=shutil.ignore_patterns('.git','node_modules'))
    # Candidate edits cannot weaken the original compatibility suite.
    shutil.rmtree(candidate/'test',ignore_errors=True)
    shutil.copytree(base.parent/'fixtures/current/test',candidate/'test')
    try:
        original=subprocess.run(['node','--test','test/*.test.ts'],cwd=candidate,capture_output=True,text=True,timeout=90)
    except subprocess.TimeoutExpired as e:
        def decoded(value): return value.decode(errors='replace') if isinstance(value,bytes) else (value or '')
        original=subprocess.CompletedProcess(e.cmd,124,decoded(e.stdout),decoded(e.stderr)+'\nPristine compatibility checks exceeded the fixed90-second timeout.')
    try:
        functional=subprocess.run(['node',str(base/'sustained_cases.mjs'),str(candidate),a.workstream,str(a.stage)],cwd=candidate,capture_output=True,text=True,timeout=45)
        try: detail=json.loads(functional.stdout)
        except json.JSONDecodeError: detail={'passed':False,'parse_error':True,'stdout':functional.stdout,'stderr':functional.stderr}
        functional_code=functional.returncode
    except subprocess.TimeoutExpired as e:
        functional_code=124
        detail={'passed':False,'timeout_seconds':45,'error':'Functional checks exceeded the fixed timeout.'}
    def clean(text):return text.replace(str(candidate),'<WORKSPACE>').replace(temporary,'<EVALUATION>')
    report={'workstream':a.workstream,'stage':a.stage,'passed':original.returncode==0 and functional_code==0 and detail.get('passed') is True,'functional':detail,'compatibility':{'exit_code':original.returncode,'stdout':clean(original.stdout),'stderr':clean(original.stderr)},'functional_exit_code':functional_code,'wall_seconds':round(time.monotonic()-started,3)}
report['repair_feedback']={'workstream':a.workstream,'stage':a.stage,'failed_checks':[{'name':x.get('name'),'error':str(x.get('error',''))[:1800]} for x in detail.get('tests',[]) if not x.get('passed')],'functional_error':detail.get('error'),'compatibility_exit_code':original.returncode,'compatibility_failure_tail':clean(original.stdout[-4000:]+original.stderr[-2000:]) if original.returncode else ''}
encoded=json.dumps(report,indent=2)+'\n'
if a.json_output:
    a.json_output.parent.mkdir(parents=True,exist_ok=True)
    a.json_output.write_text(encoded)
print(encoded,end='')
raise SystemExit(0 if report['passed'] else 1)
