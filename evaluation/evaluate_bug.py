#!/usr/bin/env python3
"""Evaluate a candidate with unchanged pre-fix tests and the upstream regression.
Usage: python3 evaluate_bug.py /absolute/path/to/candidate
No model calls. The regression and fake are from public upstream fix 5bd2b834.
"""
import json, pathlib, shutil, subprocess, sys, tempfile, time
candidate=pathlib.Path(sys.argv[1]).resolve()
eval_dir=pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='rory-bug-check-') as temp:
    target=pathlib.Path(temp)/'candidate'
    shutil.copytree(candidate,target,ignore=shutil.ignore_patterns('.git','node_modules'))
    # Use pristine tests from the frozen pre-fix fixture, not candidate-edited tests.
    shutil.rmtree(target/'test')
    shutil.copytree(eval_dir.parent/'fixtures/timeout-before/test',target/'test')
    started=time.monotonic()
    compatibility=subprocess.run(['node','--test','test/*.test.ts'],cwd=target,text=True,capture_output=True,timeout=30)
    shutil.copy2(eval_dir/'upstream-adapters.test.ts',target/'test/adapters.test.ts')
    shutil.copy2(eval_dir/'upstream-agy',target/'test/fakes/agy')
    regression=subprocess.run(['node','--test','--test-name-pattern=leaked worker','test/adapters.test.ts'],cwd=target,text=True,capture_output=True,timeout=20)
    result={'candidate':str(candidate),'compatibility_exit':compatibility.returncode,'regression_exit':regression.returncode,'wall_seconds':round(time.monotonic()-started,3),'compatibility_stdout':compatibility.stdout,'compatibility_stderr':compatibility.stderr,'regression_stdout':regression.stdout,'regression_stderr':regression.stderr}
    print(json.dumps(result,indent=2))
    sys.exit(0 if compatibility.returncode==regression.returncode==0 else 1)
