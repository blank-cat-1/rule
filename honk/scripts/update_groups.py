#!/usr/bin/env python3
"""Generate nested service/region groups; preserve all non-group settings."""
import argparse,json,pathlib,re

ROOT=pathlib.Path(__file__).resolve().parents[1]
REGIONS={
 'HK':('Hong Kong',r'(?i)(🇭🇰|HK|Hong[ _-]?Kong|香港|港)',r'台|日|韩|新|深|美'),
 'JP':('Japan',r'(?i)(🇯🇵|JP|Japan|日本|日)',r'港|台|韩|新|美'),
 'US':('United States',r'(?i)(🇺🇸|🇺🇲|US|United[ _-]?States|America|美国|美)',r'港|台|韩|新|日'),
 'SG':('Singapore',r'(?i)(🇸🇬|SG|Singapore|新加坡|坡|狮城)',r'台|日|韩|深|美'),
}
SERVICES={
 'Proxy':'HK-Auto','AI':'JP-Auto','YouTube':'US-Auto',
 'Google':'HK-Auto','Github':'HK-Auto','Telegram':'HK-Auto',
 'TikTok':'JP-Auto','Netflix':'SG-Auto','Wallet':'JP-Auto',
 'Steam':'HK-Auto','Microsoft':'JP-Auto','OneDrive':'JP-Auto',
 'Apple':'HK-Auto','Final':'Proxy',
}
EXCLUDE=r'(?i)(官网|剩余|流量|套餐|免费|订阅|到期时间|直连|Expire Date|Traffic|ExpireDate|排除)'

def group_span(text):
 m=re.search(r'(?m)^group\s*\{',text)
 if not m:raise ValueError('group section missing')
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
 raise ValueError('unclosed group section')

def generate():
 groups=[]
 def add(name,filters,policy,default=None,tolerance=None,comment=''):
  g={'name':name,'filters':filters,'policy':policy,'final':'block','comment':comment}
  if default:g['default']=default
  if tolerance is not None:g['tolerance']=tolerance
  groups.append(g)
 region_options=[r+suffix for r in REGIONS for suffix in ['-Auto','','-LoadBalance','-Fallback']]
 shared=region_options+['Auto','LoadBalance','Other','All']
 for name,default in SERVICES.items():
  options=([] if name=='Proxy' else ['Proxy'])+shared
  add(name,["group('"+g+"')" for g in options]+['name(direct)'],'select',default,
      comment='Choose a region policy or direct; Final is the unmatched-traffic selector.' if name=='Final' else 'Service selector')
 all_filter="!name(regex: '"+EXCLUDE+"')"
 for region,(label,positive,negative) in REGIONS.items():
  predicate="name(regex: '"+positive+"') && !name(regex: '"+negative+"') && "+all_filter
  for suffix,policy in [('', 'select'),('-Auto','min_moving_avg'),('-LoadBalance','loadbalance'),('-Fallback','fallback')]:
   add(region+suffix,[predicate],policy,tolerance=20 if suffix=='-Auto' else None,comment=label+' '+policy)
 union='(?i)('+ '|'.join(v[1][5:-1] for v in REGIONS.values())+')'
 add('Other',["!name(regex: '"+union+"') && "+all_filter],'select',comment='Nodes outside HK/JP/US/SG')
 for name,policy in [('All','select'),('Auto','min_moving_avg'),('LoadBalance','loadbalance')]:
  add(name,[all_filter],policy,tolerance=20 if name=='Auto' else None,comment='All eligible proxy nodes; direct excluded')
 lines=['group {']
 for g in groups:
  lines+=['    # '+g['comment'],'    '+g['name']+' {']
  lines+=['        filter: '+f for f in g['filters']]
  lines+=['        policy: '+g['policy']]
  if 'default' in g:lines+=['        default: '+g['default']]
  lines+=['        final: block','        interrupt_connections: true']
  if g['policy']!='select':lines += ["        check_url: 'https://www.gstatic.com/generate_204'"]
  if 'tolerance' in g:lines+=['        tolerance: '+str(g['tolerance'])]
  lines+=['    }']
 lines+=['}']
 return '\n'.join(lines),groups

def rewrite(source):
 start,end=group_span(source);group,metadata=generate()
 result=source[:start]+group+source[end:]
 # Apple Push remains pinned to the Hong Kong selector now that Proxy is global.
 result=result.replace('domain(geosite: mig-apple-push) -> Proxy','domain(geosite: mig-apple-push) -> HK')
 result=result.replace('dip(geoip: mig-apple-push) -> Proxy','dip(geoip: mig-apple-push) -> HK')
 return result,metadata

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--input',type=pathlib.Path,default=ROOT/'config.dae')
 ap.add_argument('--output',type=pathlib.Path,default=ROOT/'config.dae')
 ap.add_argument('--mapping',type=pathlib.Path,default=ROOT/'groups.json')
 args=ap.parse_args();result,metadata=rewrite(args.input.read_text('utf-8-sig'))
 args.output.write_text(result,'utf-8');args.mapping.write_text(json.dumps(metadata,ensure_ascii=False,indent=2),'utf-8')
 print('Generated',len(metadata),'groups; no deployment')
if __name__=='__main__':main()
