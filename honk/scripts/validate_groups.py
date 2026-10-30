#!/usr/bin/env python3
"""Validate generated group graph and native policy names without router access."""
import argparse,json,pathlib,re
from update_groups import ROOT,generate,group_span,REGIONS,EXCLUDE

def validate(text):
 start,end=group_span(text);expected,groups=generate()
 assert text[start:end]==expected,'group config differs from generator; regenerate with update_groups.py'
 names={g['name'] for g in groups};assert len(names)==len(groups)==34
 graph={g['name']:[] for g in groups}
 for g in groups:
  assert g['policy'] in ['select','min_moving_avg','loadbalance','fallback']
  for f in g['filters']:
   match=re.fullmatch(r"group\('([^']+)'\)",f)
   if match:
    name=match[1];assert name in names;graph[g['name']].append(name)
   else:
    for expr in re.findall(r"regex: '([^']+)'",f):re.compile(expr)
  if 'default' in g:assert g['default'] in graph[g['name']]
  assert g['final']=='block'
 def depth(n,path=()):
  assert n not in path,'group cycle'
  return 1+max([depth(child,path+(n,)) for child in graph[n]] or [0])
 maximum=max(depth(n) for n in names);assert maximum<=8
 routing=re.search(r'(?ms)^routing \{\n(.*?)^\}',text)[1]
 for target in re.findall(r'-> ([A-Za-z0-9_-]+)',routing):assert target in names|{'direct','block'}
 fallback=re.search(r'fallback: (\w+)',routing)[1];assert fallback=='Final'
 assert 'domain(geosite: mig-apple-push) -> HK' in routing
 assert 'dip(geoip: mig-apple-push) -> HK' in routing
 for region,(_,positive,negative) in REGIONS.items():
  examples={'HK':['🇭🇰香港1','HK-01','Hong Kong 1'],'JP':['🇯🇵日本东京1','JP-01','Japan 1'],'US':['🇺🇸美国1','US-01','United States 1'],'SG':['🇸🇬新加坡1','SG-01','Singapore 1']}
  for sample in examples[region]:assert re.search(positive,sample) and not re.search(negative,sample)
  assert re.search(EXCLUDE,'HK 剩余流量')
 for service in ['Proxy','AI','YouTube','Google','Github','Telegram','TikTok','Netflix','Wallet','Steam','Microsoft','OneDrive','Apple','Final']:
  for region in REGIONS:
   for suffix in ['','-Auto','-LoadBalance','-Fallback']:assert region+suffix in graph[service]
 return {'status':'PASS','groups':len(names),'maximum_depth':maximum,'service_selectors':14,'regional_groups':16,'shared_groups':4,'native_engine_executed':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=pathlib.Path,default=ROOT/'config.dae');ap.add_argument('--report',type=pathlib.Path)
 a=ap.parse_args();report=validate(a.config.read_text('utf-8-sig'))
 if a.report:a.report.write_text(json.dumps(report,indent=2),'utf-8')
 print('PASS:',report['groups'],'groups; depth',report['maximum_depth'],'; references, defaults and region filters valid')
if __name__=='__main__':main()
