#!/usr/bin/env node
// Reproduce pre-registered workflow findings with upstream fake CLIs only.
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
const source = resolve(process.argv[2]);
const temp = mkdtempSync(join(tmpdir(), 'rory-audit-check-'));
const records = [];
try {
  const config = join(temp, 'config.yaml');
  writeFileSync(config, ''); // Explicit, judge-less config; never user config.
  for (const [name, determination, mode, answer] of [
    ['fallback-judge', 'STATUS: RESOLVED\nSettled.', '--finalize', 'Final deliverable.'],
    ['unresolved-stdout', 'STATUS: NEEDS_INPUT\nQuestion.', '--continue', 'STATUS: NEEDS_INPUT\nStill open.'],
    ['malformed-status-accepted', 'There is no status declaration here.', '--finalize', 'Final deliverable.'],
    ['explicit-needs-input-blocked', 'STATUS: NEEDS_INPUT\nQuestion.', '--finalize', 'Final deliverable.'],
  ]) {
    const dir=join(temp,name);
    mkdirSync(join(dir,'raw'),{recursive:true});
    writeFileSync(join(dir,'debate.md'),'# Debate\n\n## Task\n\nAssess the design.\n## Proposal — One\n\nA proposal.\n');
    writeFileSync(join(dir,'respondeo.md'),determination);
    const envelope=join(dir,'envelope.json');
    writeFileSync(envelope,JSON.stringify({is_error:false,result:answer}));
    const argv=join(dir,'argv.txt');
    const flags=mode==='--continue'?[mode,'Human answer']:[mode];
    const result=spawnSync(process.execPath,[join(source,'src/index.ts'),...flags,'--debate',dir,'--config',config],{
      cwd:temp,encoding:'utf8',timeout:10000,
      env:{PATH:join(source,'test/fakes')+':/usr/bin:/bin',XDG_CONFIG_HOME:join(temp,'xdg'),FAKE_STDOUT_FILE:envelope,FAKE_ARGV_FILE:argv},
    });
    const expectedCode=name==='explicit-needs-input-blocked'?1:0;
    assert.equal(result.status,expectedCode,result.stderr);
    if(name==='fallback-judge') assert.match(readFileSync(argv,'utf8'),/opus/);
    if(name==='unresolved-stdout') assert.match(result.stdout,/respondeo-2\.md/);
    if(name==='malformed-status-accepted') assert.match(result.stdout,/final-report\.md/);
    const clean=s=>s.replaceAll(temp,'<TEMP>');
    records.push({name,exit_code:result.status,stdout:clean(result.stdout),stderr:clean(result.stderr)});
  }
  console.log(JSON.stringify({all_probes_passed:true,records},null,2));
} finally { rmSync(temp,{recursive:true,force:true}); }
