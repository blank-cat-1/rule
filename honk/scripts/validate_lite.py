#!/usr/bin/env python3
"""Keep all manual/auto region and service groups; remove only LB/fallback."""
import argparse,json,pathlib,re
from make_lite import ROOT,span,generate

def block(text,name):
 a,b=span(text,name);return text[a:b]
def entries(text):return dict(re.findall(r'(?ms)^    ([\w-]+) \{\n(.*?)^    \}',block(text,'group')))
def validate(full,lite):
 before=entries(full);after=entries(lite)
 removed={name for name,body in before.items() if re.search(r'(?m)^\s*policy:\s*(loadbalance|fallback)\s*$',body)}
 assert removed and set(after)==set(before)-removed
 assert set(removed)=={r+'-'+kind for r in ['HK','JP','US','SG'] for kind in ['LoadBalance','Fallback']}|{'LoadBalance'}
 graph={name:[] for name in after}
 for name,body in after.items():
  expected=before[name]
  for target in removed:
   expected=re.sub(r"(?m)^[ \t]*filter: group\('"+re.escape(target)+r"'\)[ \t]*\r?\n",'',expected)
  assert body==expected,'retained group changed: '+name
  refs=re.findall(r"group\('([^']+)'\)",body)
  assert all(ref in after for ref in refs),'dangling subgroup'
  graph[name]=refs
  default=re.search(r'(?m)^\s*default:\s*([\w-]+)',body)
  if default:assert default[1] in refs or 'name('+default[1]+')' in body
 for region in ['HK','JP','US','SG']:
  assert region in after and region+'-Auto' in after
  assert 'policy: select' in after[region]
  assert 'policy: min_moving_avg' in after[region+'-Auto']
 for key in ['subscription','dns','routing','global','assets','experimental']:
  assert block(full,key)==block(lite,key),key+' changed'
 assert 'ipversion_prefer: 4' in block(lite,'dns') and 'qtype(aaaa) -> reject' not in block(lite,'dns')
 def depth(name,path=()):
  assert name not in path,'group cycle'
  return 1+max([depth(child,path+(name,)) for child in graph[name]] or [0])
 maximum=max(depth(name) for name in graph);assert maximum<=8
 assert lite==generate(full)
 return {'status':'PASS','full_groups':len(before),'lite_groups':len(after),'removed_groups':sorted(removed),'maximum_depth':maximum,'retained_group_definitions_preserved':True,'all_non_group_sections_byte_equal':True,'native_engine_executed':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--full',type=pathlib.Path,default=ROOT/'config.dae');ap.add_argument('--lite',type=pathlib.Path,default=ROOT/'config-lite.dae');ap.add_argument('--report',type=pathlib.Path);a=ap.parse_args()
 report=validate(a.full.read_text('utf-8-sig'),a.lite.read_text('utf-8-sig'))
 if a.report:a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print('PASS: regions and services retained;',report['lite_groups'],'groups; only LB/fallback removed')
if __name__=='__main__':main()
