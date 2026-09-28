import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
const [workspace, stream, stageText] = process.argv.slice(2);
const stage = Number(stageText), results = [];
const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'sustained-functional-'));
async function test(name, fn) { try { await fn(); results.push({name, passed:true}); } catch (e) { results.push({name, passed:false, error:String(e.stack ?? e).replaceAll(temp,'<INPUT>').replaceAll(workspace,'<WORKSPACE>')}); } }
async function put(p, text) { await fs.mkdir(path.dirname(p),{recursive:true}); await fs.writeFile(p,text); }
async function snapshot(dir) { const found = {}; async function walk(p, rel='') { const st=await fs.lstat(p); if(st.isSymbolicLink()) found[rel]=['symlink',await fs.readlink(p)]; else if(st.isDirectory()){ found[rel]=['directory']; for(const name of (await fs.readdir(p)).sort()) await walk(path.join(p,name),path.join(rel,name)); }else found[rel]=['file',createHash('sha256').update(await fs.readFile(p)).digest('hex')]; } await walk(dir); return found; }
async function readOnly(fn) { const before=await snapshot(temp); const value=await fn(); assert.deepEqual(await snapshot(temp),before,'operation modified input files'); return value; }
async function errorCode(fn, code) { await assert.rejects(fn, e=>e?.code===code, `expected error code ${code}`); }
const cli=(file,args)=>spawnSync(process.execPath,[path.join(workspace,'src',file),...args],{cwd:workspace,encoding:'utf8',timeout:15000});
try {
 if(stream==='a') {
  let mod;
  await test('exports loadProfileBundle',async()=>{mod=await import(pathToFileURL(path.join(workspace,'src/profile-bundle.ts')));assert.equal(typeof mod.loadProfileBundle,'function');});
  if(mod?.loadProfileBundle) {
   const root=path.join(temp,'bundle'), file=path.join(root,'profiles.json');
   const parent='rounds: 2\ntimeoutMinutes: 7\nparticipants:\n  - adapter: claude\n    model: base-model\n  - adapter: codex\n    model: retained-model\njudge:\n  adapter: claude\n  model: original-judge\n';
   const child='rounds: 0\nparticipants:\n  - adapter: agy\n    model: child-model\n  - adapter: claude\n    model: replacement-model\n';
   await put(path.join(root,'configs/base.yaml'),parent); await put(path.join(root,'configs/child.yaml'),child);
   const manifest={version:1,profiles:{base:{config:'configs/base.yaml'}}};
   const save=()=>put(file,JSON.stringify(manifest)); await save();
   await test('relative YAML loading and read-only inputs',async()=>{const got=await readOnly(()=>mod.loadProfileBundle(file,'base'));assert.equal(got.rounds,2);assert.equal(got.participants[0].model,'base-model');assert.equal(got.judge.model,'original-judge');});
   await test('returned configurations are independently owned',async()=>{const first=await mod.loadProfileBundle(file,'base'); first.participants[0].model='MUTATED'; first.judge.model='MUTATED'; const second=await readOnly(()=>mod.loadProfileBundle(file,'base'));assert.equal(second.participants[0].model,'base-model');assert.equal(second.judge.model,'original-judge');});
   await test('unknown profile has declared error code',()=>errorCode(()=>mod.loadProfileBundle(file,'absent'),'UNKNOWN_PROFILE'));
   await test('invalid bundle envelope and selected profile errors',async()=>{for(const doc of ['{',JSON.stringify({version:2,profiles:{}}),JSON.stringify({version:1,profiles:[]}),JSON.stringify({version:1,profiles:{bad:4}})]){await put(file,doc);await errorCode(()=>mod.loadProfileBundle(file,'bad'),'INVALID_BUNDLE');}await save();});
   if(stage>=2) {
    manifest.profiles.child={extends:'base',config:'configs/child.yaml'};
    manifest.profiles.inherit={extends:'base'}; await save();
    await test(stage<4?'inheritance merges participant adapters':'corrected inheritance replaces entire participant list',async()=>{const got=await readOnly(()=>mod.loadProfileBundle(file,'child'));assert.equal(got.rounds,0);assert.equal(got.timeoutMinutes,7);assert.equal(got.judge.model,'original-judge');assert.deepEqual(got.participants.map(p=>p.adapter),stage<4?['claude','codex','agy']:['agy','claude']);assert.equal(got.participants.find(p=>p.adapter==='claude').model,'replacement-model');const inherited=await mod.loadProfileBundle(file,'inherit');assert.deepEqual(inherited.participants.map(p=>p.adapter),['claude','codex']);});
   }
   if(stage>=3) {
    manifest.profiles.inline={extends:'child',overrides:{rounds:3,judge:null,participants:[{adapter:'pi',model:'inline-model'},{adapter:'claude',model:'inline-claude'}]}};
    manifest.profiles.only={overrides:{rounds:4}}; await save();
    await test('inline precedence, judge removal, and participant policy',async()=>{const got=await readOnly(()=>mod.loadProfileBundle(file,'inline'));assert.equal(got.rounds,3);assert.equal(got.timeoutMinutes,7);assert.equal(got.judge,undefined);assert.deepEqual(got.participants.map(p=>p.adapter),stage<4?['claude','codex','agy','pi']:['pi','claude']);assert.equal(got.participants.find(p=>p.adapter==='claude').model,'inline-claude');assert.equal((await mod.loadProfileBundle(file,'only')).rounds,4);});
    await test('invalid overrides are not silently discarded',async()=>{manifest.profiles.bad={overrides:{unexpected:true}};await save();await errorCode(()=>mod.loadProfileBundle(file,'bad'),'INVALID_BUNDLE');manifest.profiles.bad={overrides:{rounds:1.5}};await save();await assert.rejects(()=>mod.loadProfileBundle(file,'bad'));delete manifest.profiles.bad;await save();});
   }
   if(stage>=4) {
    manifest.profiles.third={extends:'inline',overrides:{participants:[{adapter:'codex'},{adapter:'agy'}]}}; await save();
    await test('replacement applies through multiple inheritance levels',async()=>{const got=await readOnly(()=>mod.loadProfileBundle(file,'third'));assert.deepEqual(got.participants,[{adapter:'codex'},{adapter:'agy'}]);assert.equal(got.judge,undefined);});
   }
   if(stage>=5) {
    await test('default selection, explicit selection, and no-default error',async()=>{await errorCode(()=>mod.loadProfileBundle(file),'PROFILE_REQUIRED');manifest.defaultProfile='child';await save();assert.equal((await mod.loadProfileBundle(file)).rounds,0);assert.equal((await mod.loadProfileBundle(file,'base')).rounds,2);manifest.defaultProfile='missing';await save();await errorCode(()=>mod.loadProfileBundle(file),'UNKNOWN_PROFILE');manifest.defaultProfile='base';await save();});
    await test('cycles and dangling parent have bounded declared failures',async()=>{manifest.profiles.self={extends:'self'};manifest.profiles.loop1={extends:'loop2'};manifest.profiles.loop2={extends:'loop1'};manifest.profiles.dangling={extends:'missing'};await save();await errorCode(()=>mod.loadProfileBundle(file,'self'),'PROFILE_CYCLE');await errorCode(()=>mod.loadProfileBundle(file,'loop1'),'PROFILE_CYCLE');await errorCode(()=>mod.loadProfileBundle(file,'dangling'),'UNKNOWN_PROFILE');for(const key of ['self','loop1','loop2','dangling'])delete manifest.profiles[key];await save();});
   }
   if(stage>=6) {
    await put(path.join(temp,'outside.yaml'),parent); await put(path.join(temp,'bundle-other/outside.yaml'),parent);
    await fs.symlink(path.join(temp,'outside.yaml'),path.join(root,'escape.yaml'));
    await test('relative, realpath, and prefix-sibling escapes are rejected',async()=>{for(const config of ['../outside.yaml','../bundle-other/outside.yaml',path.join(temp,'outside.yaml'),'escape.yaml']){manifest.profiles.unsafe={config};await save();await readOnly(()=>errorCode(()=>mod.loadProfileBundle(file,'unsafe'),'UNSAFE_CONFIG_PATH'));}delete manifest.profiles.unsafe;await save();});
    await test('internal normalized and symlinked paths remain usable',async()=>{await fs.symlink(path.join(root,'configs/base.yaml'),path.join(root,'inside.yaml'));manifest.profiles.normal={config:'configs/../configs/base.yaml'};manifest.profiles.link={config:'inside.yaml'};await save();assert.equal((await readOnly(()=>mod.loadProfileBundle(file,'normal'))).rounds,2);assert.equal((await readOnly(()=>mod.loadProfileBundle(file,'link'))).rounds,2);});
   }
   if(stage>=7) {
    await test('render CLI outputs usable canonical YAML with no input writes',async()=>{const r=await readOnly(async()=>cli('profile-cli.ts',['--bundle',file,'--profile','child']));assert.equal(r.status,0,r.stderr);const configMod=await import(pathToFileURL(path.join(workspace,'src/config.ts')));assert.deepEqual(configMod.parseDebateConfig(r.stdout),await mod.loadProfileBundle(file,'child'));});
    await test('render CLI errors keep stdout empty and preserve error codes',async()=>{for(const args of [[],['--bundle',file,'--bogus'],['--bundle',file,'--profile','missing']]){const r=cli('profile-cli.ts',args);assert.equal(r.status,1,r.stderr);assert.equal(r.stdout,'');assert.ok(r.stderr.trim());if(args.includes('missing'))assert.match(r.stderr,/UNKNOWN_PROFILE/);}});
   }
   if(stage>=8) {
    await test('profile listing is sorted and does not load YAML/default',async()=>{const invalidPath={version:1,profiles:{z:{config:'missing-z.yaml'},a:{config:'missing-a.yaml'}}};const listing=path.join(root,'listing.json');await put(listing,JSON.stringify(invalidPath));assert.equal(typeof mod.listProfiles,'function');assert.deepEqual(await readOnly(()=>mod.listProfiles(listing)),['a','z']);const r=cli('profile-cli.ts',['--bundle',listing,'--list']);assert.equal(r.status,0,r.stderr);assert.deepEqual(JSON.parse(r.stdout),['a','z']);});
    await test('JSON rendering and mutually exclusive list flags',async()=>{const r=cli('profile-cli.ts',['--bundle',file,'--json']);assert.equal(r.status,0,r.stderr);assert.deepEqual(JSON.parse(r.stdout),await mod.loadProfileBundle(file));for(const args of [['--list','--json'],['--list','--profile','base']]){const bad=cli('profile-cli.ts',['--bundle',file,...args]);assert.equal(bad.status,1);assert.equal(bad.stdout,'');}});
   }
  }
 } else if(stream==='b') {
  let mod; await test('exports listDebates',async()=>{mod=await import(pathToFileURL(path.join(workspace,'src/catalog.ts')));assert.equal(typeof mod.listDebates,'function');});
  if(mod?.listDebates) {
   const root=path.join(temp,'debates');await fs.mkdir(root,{recursive:true});
   for(const id of ['debate-a','debate-b','debate-c','debate-d','debate-e'])await put(path.join(root,id,'debate.md'),`Transcript ${id}\n`);
   await put(path.join(root,'debate-a/final-report.md'),' final A\n\n'); await put(path.join(root,'debate-c/final-report.md'),'Final C');
   await put(path.join(root,'debate-a/respondeo.md'),'STATUS: NEEDS_INPUT\nold'); await put(path.join(root,'debate-a/respondeo-2.md'),'STATUS: NEEDS_INPUT\nold2'); await put(path.join(root,'debate-a/respondeo-10.md'),'\n STATUS: RESOLVED \nlatest');
   await put(path.join(root,'debate-b/respondeo.md'),'STATUS: NEEDS_INPUT\nquestion');await put(path.join(root,'debate-c/respondeo.md'),'Respondeo turn failed: timeout');await put(path.join(root,'debate-e/respondeo.md'),'STATUS: OTHER');
   await put(path.join(root,'ignore/me'),'unused');await put(path.join(root,'debate-file'),'not directory');
   await put(path.join(temp,'outside/debate.md'),'Outside transcript');await fs.symlink(path.join(temp,'outside'),path.join(root,'debate-linked'));
   await fs.symlink(path.join(temp,'outside/debate.md'),path.join(root,'debate-d/final-report.md'));
   await fs.symlink(path.join(temp,'outside/debate.md'),path.join(root,'debate-a/respondeo-99.md'));
   await test('catalog directory/regular-file rules and ordering',async()=>{const got=await readOnly(()=>mod.listDebates(root));assert.deepEqual(got.map(x=>x.id),stage<3?['debate-a','debate-b','debate-c','debate-d','debate-e']:['debate-e','debate-d','debate-c','debate-b','debate-a']);for(const x of got){assert.equal(x.path,path.join(root,x.id));assert.equal(x.hasTranscript,true);assert.equal(x.hasFinalReport,['debate-a','debate-c'].includes(x.id));}assert.deepEqual(await mod.listDebates(path.join(root,'missing')),[]);});
   if(stage>=2) {
    await test('highest numeric regular determination and strict status classification',async()=>{const got=await mod.listDebates(root);const byId=Object.fromEntries(got.map(x=>[x.id,x]));assert.equal(byId['debate-a'].determination,'respondeo-10.md');assert.equal(byId['debate-a'].status,'resolved');assert.equal(byId['debate-b'].status,'needs-input');assert.equal(byId['debate-c'].status,'failed');assert.equal(byId['debate-d'].status,'unjudged');assert.equal(byId['debate-d'].determination,null);assert.equal(byId['debate-e'].status,'unknown');assert.equal(typeof mod.classifyDetermination,'function');for(const text of ['', 'STATUS: resolved','STATUS: RESOLVED extra','intro\nSTATUS: RESOLVED'])assert.equal(mod.classifyDetermination(text),'unknown');assert.equal(mod.classifyDetermination('\n STATUS: RESOLVED \n'),'resolved');});
   }
   if(stage>=3) {
    await test('pagination and declared query validation',async()=>{assert.deepEqual((await mod.listDebates(root,{offset:1,limit:2})).map(x=>x.id),['debate-d','debate-c']);assert.deepEqual(await mod.listDebates(root,{limit:0}),[]);assert.equal((await mod.listDebates(root,{offset:4})).length,1);for(const options of [{offset:-1},{limit:1.5},{limit:'2'},{offset:Infinity}])await errorCode(()=>mod.listDebates(root,options),'INVALID_QUERY');});
   }
   if(stage>=4) {
    await test(stage<6?'initial scan-window filter semantics':'corrected filter-before-pagination semantics',async()=>{assert.deepEqual((await mod.listDebates(root,{status:'resolved',limit:1})).map(x=>x.id),stage<6?[]:['debate-a']);assert.deepEqual((await mod.listDebates(root,{hasFinalReport:true,offset:1,limit:1})).map(x=>x.id),stage<6?[]:['debate-a']);assert.deepEqual((await mod.listDebates(root,{status:'failed',hasFinalReport:true})).map(x=>x.id),['debate-c']);});
    await test('filter validation',async()=>{await errorCode(()=>mod.listDebates(root,{status:'invalid'}),'INVALID_QUERY');await errorCode(()=>mod.listDebates(root,{hasFinalReport:'yes'}),'INVALID_QUERY');});
   }
   if(stage>=5) {
    await test('exact safe artifact reading and absence',async()=>{assert.equal(typeof mod.readDebateArtifact,'function');assert.equal(await readOnly(()=>mod.readDebateArtifact(root,'debate-a','final-report')),' final A\n\n');assert.equal(await mod.readDebateArtifact(root,'debate-a','determination'),'\n STATUS: RESOLVED \nlatest');assert.equal(await mod.readDebateArtifact(root,'debate-a','transcript'),'Transcript debate-a\n');assert.equal(await mod.readDebateArtifact(root,'debate-none','transcript'),null);assert.equal(await mod.readDebateArtifact(root,'debate-b','final-report'),null);});
    await test('artifact traversal/symlink errors',async()=>{for(const id of ['../outside','debate-a/../debate-b','bad',''])await errorCode(()=>mod.readDebateArtifact(root,id,'transcript'),'INVALID_ID');await errorCode(()=>mod.readDebateArtifact(root,'debate-linked','transcript'),'UNSAFE_PATH');await errorCode(()=>mod.readDebateArtifact(root,'debate-d','final-report'),'UNSAFE_PATH');await errorCode(()=>mod.readDebateArtifact(root,'debate-a','arbitrary'),'INVALID_QUERY');});
   }
   if(stage>=7) {
    await test('catalog CLI JSON matches corrected API filters',async()=>{const r=await readOnly(async()=>cli('catalog-cli.ts',['--limit','1','--root',root,'--has-final-report','yes','--offset','1']));assert.equal(r.status,0,r.stderr);assert.deepEqual(JSON.parse(r.stdout),await mod.listDebates(root,{limit:1,offset:1,hasFinalReport:true}));const absent=cli('catalog-cli.ts',['--root',path.join(root,'missing')]);assert.equal(absent.status,0,absent.stderr);assert.deepEqual(JSON.parse(absent.stdout),[]);});
    await test('catalog CLI argument errors',async()=>{for(const args of [[],['--root'],['--root',root,'--wat'],['--root',root,'--has-final-report','maybe'],['--root',root,'--limit','-1']]){const r=cli('catalog-cli.ts',args);assert.equal(r.status,1,r.stderr);assert.equal(r.stdout,'');assert.match(r.stderr,/INVALID_QUERY/);}});
   }
   if(stage>=8) {
    await test('artifact CLI emits exact bytes and distinct absence exit',async()=>{const r=await readOnly(async()=>cli('catalog-cli.ts',['--root',root,'--id','debate-a','--artifact','final-report']));assert.equal(r.status,0,r.stderr);assert.equal(r.stdout,' final A\n\n');const missing=cli('catalog-cli.ts',['--root',root,'--id','debate-b','--artifact','final-report']);assert.equal(missing.status,2);assert.equal(missing.stdout,'');assert.match(missing.stderr,/NOT_FOUND/);});
    await test('artifact CLI conflicts and unsafe paths fail closed',async()=>{for(const tail of [['--id','debate-a'],['--artifact','transcript'],['--id','debate-a','--artifact','transcript','--limit','1'],['--id','../outside','--artifact','transcript'],['--id','debate-linked','--artifact','transcript']]){const r=cli('catalog-cli.ts',['--root',root,...tail]);assert.equal(r.status,1,r.stderr);assert.equal(r.stdout,'');assert.match(r.stderr,/(INVALID_QUERY|INVALID_ID|UNSAFE_PATH)/);}});
   }
  }
 }
} finally { await fs.rm(temp,{recursive:true,force:true}); }
console.log(JSON.stringify({workstream:stream,stage,passed:results.every(x=>x.passed),tests:results},null,2));
process.exitCode=results.every(x=>x.passed)?0:1;
