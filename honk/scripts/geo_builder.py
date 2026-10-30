#!/usr/bin/env python3
"""Build a reviewable honk rules candidate. Never deploys or reloads anything.

Requires Python 3.10+ and an official Mihomo executable for MRS decoding.
Public rule URLs only; node subscriptions are never fetched by this script.
"""
import argparse, collections, concurrent.futures, datetime, hashlib, ipaddress
import json, pathlib, re, shutil, subprocess, sys, urllib.request

def vi(n):
    b=bytearray()
    while n>127: b.append((n&127)|128); n>>=7
    b.append(n); return bytes(b)
def field(n,value):
    if isinstance(value,int): return vi(n<<3)+vi(value)
    if isinstance(value,str): value=value.encode('utf-8')
    return vi((n<<3)|2)+vi(len(value))+value
def varint(b,i):
    n=shift=0
    while True:
        if i>=len(b) or shift>63: raise ValueError('invalid protobuf varint')
        c=b[i]; i+=1; n|=(c&127)<<shift
        if c<128:return n,i
        shift+=7
def fields(b):
    i=0
    while i<len(b):
        k,i=varint(b,i); t=k&7
        if t==0:v,i=varint(b,i)
        elif t==2:
            n,i=varint(b,i);v=b[i:i+n]; i+=n
            if len(v)!=n:raise ValueError('truncated protobuf')
        elif t==1:v=b[i:i+8];i+=8
        elif t==5:v=b[i:i+4];i+=4
        else:raise ValueError('unsupported protobuf wire type')
        yield k>>3,v
def geo_entries(b):
    out={}
    for n,v in fields(b):
        if n==1:
            code=next(x.decode('utf-8').lower() for k,x in fields(v) if k==1)
            if code in out:raise ValueError('duplicate geo category')
            out[code]=v
    return out
def encode_domain(kind,value):
    return field(1,{'keyword':0,'regex':1,'suffix':2,'full':3}[kind])+field(2,value)
def domain_pattern(s):
    s=s.strip().lower()
    if not s:raise ValueError('empty domain')
    if s.startswith('+.') and '*' not in s:
        return 'suffix',s[2:]
    if s.startswith('.') and '*' not in s:
        return 'regex',r'^(?:[^.]+\.)+'+re.escape(s[1:])+r'$'
    if '*' in s or s.startswith('+.'):
        # A whole-label * consumes exactly one label. A leading + consumes
        # zero or more labels; a leading dot consumes one or more labels.
        prefix=''
        if s.startswith('+.'):prefix=r'(?:[^.]+\.)*';s=s[2:]
        elif s.startswith('.'):prefix=r'(?:[^.]+\.)+';s=s[1:]
        return 'regex','^'+prefix+r'\.'.join('[^.]+' if x=='*' else re.escape(x) for x in s.split('.'))+'$'
    return 'full',s
def parse_records(text,behavior):
    domains=[]; nets=[]; counts=collections.Counter(); flags=collections.Counter()
    for no,line in enumerate(text.splitlines(),1):
        line=line.strip()
        if not line or line.startswith(('#','//',';')):continue
        if behavior=='domain':
            kind,value=domain_pattern(line);domains.append((kind,value));counts[kind]+=1
        elif behavior=='ipcidr':
            net=ipaddress.ip_network(line,strict=False);nets.append(str(net));counts['ipv'+str(net.version)]+=1
        else:
            parts=[x.strip() for x in line.split(',')];typ=parts[0].upper()
            if len(parts)<2:raise ValueError('invalid classical rule at line '+str(no))
            value=parts[1]
            extra=parts[2:]
            if any(x.lower()!='no-resolve' for x in extra):
                raise ValueError('unsupported classical modifier at line '+str(no))
            flags.update(extra)
            if typ in ('DOMAIN','DOMAIN-SUFFIX','DOMAIN-KEYWORD','DOMAIN-REGEX'):
                kind={'DOMAIN':'full','DOMAIN-SUFFIX':'suffix','DOMAIN-KEYWORD':'keyword','DOMAIN-REGEX':'regex'}[typ]
                if kind=='regex':re.compile(value)
                domains.append((kind,value.lower() if kind!='regex' else value));counts[kind]+=1
            elif typ in ('IP-CIDR','IP-CIDR6'):
                net=ipaddress.ip_network(value,strict=False);nets.append(str(net));counts['ipv'+str(net.version)]+=1
            else:raise ValueError('unsupported rule type '+typ+' at line '+str(no))
    if not domains and not nets:raise ValueError('empty rule provider')
    return domains,nets,dict(counts),dict(flags)
def download(url):
    if not url.startswith('https://'):raise ValueError('HTTPS required')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'honk-rule-migration/1'}),timeout=90) as r:
                b=r.read(64*1024*1024+1)
                if len(b)>64*1024*1024:raise ValueError('download exceeds 64 MiB')
                return b
        except Exception:
            if attempt==2:raise
def build(manifest,cache,out,mihomo,offline=False):
    # Destination must not exist; a failed run can never alter accepted files.
    out.mkdir(parents=True,exist_ok=False)
    raw=out/'sources';raw.mkdir(); records={}; audit=[]; parsed={}
    def get(p):
        name=p['file']; src=cache/name
        b=src.read_bytes() if offline else download(p['url'])
        if offline and p.get('sha256') and hashlib.sha256(b).hexdigest()!=p['sha256']:
            raise ValueError('cached source checksum mismatch: '+name)
        (raw/name).write_bytes(b)
        return name,b
    sources=manifest['providers']+manifest['base_assets']
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for name,b in pool.map(get,sources):records[name]=b
    site=geo_entries(records['base-geosite.dat']); ip=geo_entries(records['base-geoip.dat'])
    for p in manifest['providers']:
        b=records[p['file']]
        if p['format']=='mrs':
            decoded=raw/(p['name']+'.txt')
            result=subprocess.run([str(mihomo),'convert-ruleset',p['behavior'],'mrs',str(raw/p['file']),str(decoded)],capture_output=True)
            if result.returncode:raise ValueError('MRS decoder failed for '+p['name'])
            text=decoded.read_text('utf-8-sig')
        else:text=b.decode('utf-8-sig')
        ds,ns,counts,flags=parse_records(text,p['behavior'])
        # Include every declared provider, even ones not used by traffic rules.
        cat=p['category']; sb=field(1,cat.upper()); ib=field(1,cat.upper())
        if cat in site or cat in ip:raise ValueError('category collides with upstream data')
        for kind,v in ds:sb+=field(2,encode_domain(kind,v))
        for v in ns:
            n=ipaddress.ip_network(v)
            ib+=field(2,field(1,n.network_address.packed)+field(2,n.prefixlen))
        if ds:site[cat]=sb
        if ns:ip[cat]=ib
        audit.append({'name':p['name'],'category':cat,'url':p['url'],'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'domain_count':len(ds),'cidr_count':len(ns),'types':counts,'flags':flags,'usage':p['usage']})
        parsed[p['name']]={'domains':ds,'cidrs':ns}
        (raw/(p['name']+'.normalized.json')).write_text(json.dumps(parsed[p['name']],ensure_ascii=False,indent=1),'utf-8')
    (out/'geosite.dat').write_bytes(b''.join(field(1,v) for v in site.values()))
    (out/'geoip.dat').write_bytes(b''.join(field(1,v) for v in ip.values()))
    # Read the produced binary back and compare every migrated record.
    rs=geo_entries((out/'geosite.dat').read_bytes());ri=geo_entries((out/'geoip.dat').read_bytes())
    for p in manifest['providers']:
        expected=parsed[p['name']];cat=p['category']
        if expected['domains']:
            actual=[]
            for k,b in fields(rs[cat]):
                if k==2:
                    d=dict(fields(b));actual.append((['keyword','regex','suffix','full'][d.get(1,0)],d[2].decode()))
            assert actual==expected['domains'],p['name']
        if expected['cidrs']:
            actual=[]
            for k,b in fields(ri[cat]):
                if k==2:
                    d=dict(fields(b));actual.append(str(ipaddress.ip_network((ipaddress.ip_address(d[1]),d[2]))))
            assert actual==expected['cidrs'],p['name']
    report={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'providers':audit,'validation':{'all_downloads_parsed':True,'all_binary_records_roundtrip_equal':True,'no_deployment':True},'assets':{n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ['geosite.dat','geoip.dat']}}
    (out/'rules-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
    return report,parsed
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=pathlib.Path,default=pathlib.Path(__file__).with_name('rules-manifest.json'))
    ap.add_argument('--mihomo',type=pathlib.Path,required=True,help='Path to official platform-specific Mihomo executable')
    ap.add_argument('--out',type=pathlib.Path,required=True,help='New candidate directory; must not already exist')
    ap.add_argument('--offline',action='store_true');ap.add_argument('--cache',type=pathlib.Path,default=pathlib.Path(__file__).with_name('sources'))
    args=ap.parse_args()
    try:
        report,_=build(json.loads(args.manifest.read_text('utf-8')),args.cache,args.out,args.mihomo.resolve(),args.offline)
        print('PASS:',len(report['providers']),'providers; candidate written to',args.out)
    except Exception as e:
        # URL bodies and arbitrary exception messages can contain credentials.
        print('FAILED:',type(e).__name__,'; no deployment performed. Inspect candidate sources locally.',file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()
