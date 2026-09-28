#!/usr/bin/env python3
"""Summarize only the faithful campaign, counting each full session once."""
import argparse,json
from pathlib import Path
from summarize import estimate
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--prefix',required=True);a=p.parse_args()
 rows=[]
 for path in sorted((ROOT/'results').glob(f'{a.prefix}-*/telemetry.json')):
  out=path.parent;run=json.loads((out/'run.json').read_text());t=json.loads(path.read_text())
  if not run.get('task','').startswith('sustained-'):continue
  root=next(x for x in t['threads'] if x['thread']=='root')
  stages=run['stages']; passed=lambda stage:bool(stage['attempts'] and stage['attempts'][-1].get('passed'))
  row={'extends_run_id':run.get('extends_run_id'),'run_id':run['run_id'],'workstream':run['task'],'policy':run['policy'],'status':run['status'],'stages_attempted':len(stages),'stages_passed_first_attempt':sum(bool(s['attempts'][0].get('passed')) for s in stages),'stages_passed_after_repairs':sum(passed(s) for s in stages),'repairs':sum(max(0,len(s['attempts'])-1) for s in stages),'all_work_passed':len(stages)==8 and all(passed(s) for s in stages) and run['status']=='completed','credit_estimate':estimate(t['usage_by_model'])['total'],'elapsed_seconds':run['elapsed_seconds'],'peak_parent_input':root['context_proxy']['peak_request_input_tokens'],'workers':t['thread_count']-1,'parent_tool_counts':root['tool_call_counts'],'root_compactions':root['compaction_count'],'worker_compactions':sum(x['compaction_count'] for x in t['threads'] if x['thread']!='root'),'actual_models':sorted(t['usage_by_model']),'usage':t['total_usage'],'accounting_warnings':t['warnings']}
  meters={k:json.loads((out/f'quota-{k}.json').read_text()) for k in ['before','after','settled'] if (out/f'quota-{k}.json').exists()}
  row['quota']=meters;rows.append(row)
 superseded={r['extends_run_id'] for r in rows if r.get('extends_run_id')}
 rows=[r for r in rows if r['run_id'] not in superseded]
 comparisons=[]
 for stream in ['sustained-a','sustained-b']:
  matching={r['policy']:r for r in rows if r['workstream']==stream}
  if 'default' not in matching:continue
  base=matching['default']
  for policy in ['rory','rory-long']:
   if policy not in matching:continue
   alt=matching[policy]; c={'workstream':stream,'policy':policy,'quality':f"{alt['stages_passed_after_repairs']}/8 versus {base['stages_passed_after_repairs']}/8"}
   for metric in ['credit_estimate','elapsed_seconds','peak_parent_input']:
    change=(alt[metric]/base[metric]-1)*100;c[metric+'_percent_change']=change
    c[metric+'_outcome']='WIN' if change<=-10 else 'LOSS' if change>=10 else 'UNRESOLVED'
   if not alt['all_work_passed'] or not base['all_work_passed']:
    c['credit_estimate_outcome']='QUALITY LOSS' if base['all_work_passed'] and not alt['all_work_passed'] else 'NOT COMPARABLE AT EQUAL COMPLETION'
   comparisons.append(c)
 result={'schema_version':1,'superseded_cumulative_snapshots':sorted(superseded),'note':'Two feature streams from one project; descriptive local comparisons, not statistical generalization. Credits are pricing-derived, not subscription measurements. Main snapshots are cumulative and counted once per session.','runs':rows,'comparisons':comparisons,'unique_execution_credit_estimate':sum(r['credit_estimate'] for r in rows)}
 target=ROOT/'results'/f'{a.prefix}-summary.json';target.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'comparisons':comparisons,'runs':[{k:v for k,v in r.items() if k not in ['quota','usage','parent_tool_counts']} for r in rows]},indent=2))
if __name__=='__main__':main()
