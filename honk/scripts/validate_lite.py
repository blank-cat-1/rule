#!/usr/bin/env python3
"""Validate the lite edition independently from the full group hierarchy."""
import argparse,pathlib,re,json
from make_lite import ROOT,span,generate

def block(s,name):a,b=span(s,name);return s[a:b]
def validate(full,lite):
 assert lite==generate(full),'lite config is stale; regenerate it'
 names=re.findall(r'(?m)^    ([\w-]+)\s*\{',block(lite,'group'));assert names==['Auto','Manual']
 assert 'policy: min_moving_avg' in block(lite,'group')
 assert 'default: Auto' in block(lite,'group')
 assert "filter: group('Auto')" in block(lite,'group')
 assert 'filter: name(direct)' in block(lite,'group')
 for regex in re.findall(r"regex: '([^']+)'",block(lite,'group')):re.compile(regex)
 for key in ['subscription','dns','global','assets','experimental']:assert block(full,key)==block(lite,key),key+' changed'
 assert 'ipversion_prefer: 4' in block(lite,'dns')
 assert 'qtype(aaaa) -> reject' not in block(lite,'dns')
 def active(s):return [line.strip() for line in block(s,'routing').splitlines()[1:-1] if line.strip() and not line.lstrip().startswith('#')]
 old=active(full);new=active(lite);assert len(old)==len(new)
 for before,after in zip(old,new):
  if '->' in before:
   condition,target=before.rsplit('->',1);condition2,target2=after.rsplit('->',1)
   assert condition==condition2,'rule condition or order changed'
   if target.strip() in ['direct','direct(must)','block']:assert target==target2,'DIRECT/REJECT semantics changed'
   else:assert target2.strip()=='Manual','proxy rule missed remapping'
  else:assert before.startswith('fallback: ') and after=='fallback: Manual'
 assert new[0]==old[0] and new[1]==old[1] and new[2]==old[2]
 return {'status':'PASS','groups':names,'maximum_depth':2,'rule_conditions_and_order_preserved':True,'direct_and_block_preserved':True,'dns_and_all_other_sections_unchanged':True,'all_proxy_rules_use_manual':True,'native_engine_executed':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--full',type=pathlib.Path,default=ROOT/'config.dae');ap.add_argument('--lite',type=pathlib.Path,default=ROOT/'config-lite.dae');ap.add_argument('--report',type=pathlib.Path);a=ap.parse_args()
 report=validate(a.full.read_text('utf-8-sig'),a.lite.read_text('utf-8-sig'))
 if a.report:a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 print('PASS: Auto/Manual only; all rule conditions, DNS, node subscriptions and Doona preserved')
if __name__=='__main__':main()
