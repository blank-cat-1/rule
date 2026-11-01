#!/usr/bin/env python3
"""Generate a separate two-group configuration; never overwrite the full config."""
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
 a,b=span(full,'group');names=set(re.findall(r'(?m)^    ([\w-]+)\s*\{',full[a:b]))
 groups='''group {
    # Auto: choose the lowest-latency healthy node from all regions.
    Auto {
        filter: !name(regex: 'EXCLUDE')
        policy: min_moving_avg
        tolerance: 20
        check_url: 'https://www.gstatic.com/generate_204'
        final: block
        interrupt_connections: true
    }
    # Manual: choose Auto, one eligible node, or explicit direct.
    Manual {
        filter: group('Auto')
        filter: !name(regex: 'EXCLUDE')
        filter: name(direct)
        policy: select
        default: Auto
        final: block
        interrupt_connections: true
    }
}'''.replace('EXCLUDE',EXCLUDE)
 result=full[:a]+groups+full[b:]
 x,y=span(result,'routing');routing=result[x:y]
 def target(m):return m[1]+('Manual' if m[2] in names else m[2])
 routing=re.sub(r'(->[ \t]*)([\w-]+)',target,routing)
 routing=re.sub(r'(fallback:[ \t]*)([\w-]+)',target,routing)
 result=result[:x]+routing+result[y:]
 # Retarget explicit proxy detours only if the full config contains them.
 # DNS actions and node/subscription URLs remain unchanged.
 for name in ['subscription','assets','dns']:
  try:x,y=span(result,name)
  except ValueError:continue
  text=result[x:y]
  text=re.sub(r'(?m)^([ \t]*route:[ \t]*)([\w-]+)([ \t]*(?:#.*)?)$',lambda m:m[1]+('Manual' if m[2] in names else m[2])+m[3],text)
  if name in ['dns','subscription']:text=re.sub(r'(->[ \t]*)([\w-]+)',target,text)
  result=result[:x]+text+result[y:]
 return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',type=pathlib.Path,default=ROOT/'config.dae');ap.add_argument('--output',type=pathlib.Path,default=ROOT/'config-lite.dae');a=ap.parse_args()
 if a.input.resolve()==a.output.resolve():raise SystemExit('Refusing to overwrite full configuration')
 result=generate(a.input.read_text('utf-8-sig'));a.output.write_text(result,'utf-8');print('Generated separate two-group config; full config unchanged; no deployment')
if __name__=='__main__':main()
