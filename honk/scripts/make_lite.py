#!/usr/bin/env python3
"""Generate a regional manual/auto edition; never overwrite the full config."""
import argparse,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1]
EXCLUDE=r'(?i)(官网|剩余|流量|套餐|免费|订阅|到期时间|直连|Expire Date|Traffic|ExpireDate|排除)'

def span(text,name):
 m=re.search(r'(?m)^'+re.escape(name)+r'\s*\{',text)
 if not m:raise ValueError('missing block '+name)
 depth=0;quote=None;comment=False
 for i in range(m.end()-1,len(text)):
  c=text[i]
  if c=='\n':comment=False
  if comment:continue
  if quote:
   if c==quote:quote=None
   continue
  if c in "'\"":quote=c;continue
  if c=='#':comment=True;continue
  if c=='{':depth+=1
  if c=='}':
   depth-=1
   if depth==0:return m.start(),i+1
 raise ValueError('unclosed block '+name)

def generate(full):
 a,b=span(full,'group');section=full[a:b]
 entries=list(re.finditer(r'(?ms)^    ([\w-]+) \{\n(.*?)^    \}',section))
 removed=set()
 for entry in entries:
  policy=re.search(r'(?m)^\s*policy:\s*([\w-]+)',entry[2])
  if policy and policy[1] in ['loadbalance','load_balance','roundrobin','fallback']:
   removed.add(entry[1])
 assert removed,'full configuration contains no loadbalance/fallback groups'
 for entry in reversed(entries):
  if entry[1] in removed:section=section[:entry.start()]+section[entry.end():]
 for name in removed:
  section=re.sub(r"(?m)^[ \t]*filter: group\('"+re.escape(name)+r"'\)[ \t]*\r?\n",'',section)
 # Current defaults are Auto or Proxy and never target a removed group.
 for name in removed:
  assert not re.search(r'(?m)^\s*(default|final):\s*'+re.escape(name)+r'\s*$',section),'removed group used as default/final'
 result=full[:a]+section+full[b:]
 return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',type=pathlib.Path,default=ROOT/'config.dae');ap.add_argument('--output',type=pathlib.Path,default=ROOT/'config-lite.dae');a=ap.parse_args()
 if a.input.resolve()==a.output.resolve():raise SystemExit('Refusing to overwrite full configuration')
 result=generate(a.input.read_text('utf-8-sig'));a.output.write_text(result,'utf-8');print('Generated regional manual/auto config; full config unchanged; no deployment')
if __name__=='__main__':main()
