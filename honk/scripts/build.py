#!/usr/bin/env python3
"""Build honk native databases from local custom lists + public upstreams."""
import argparse,datetime,gzip,hashlib,json,pathlib,shutil,sys,tempfile
from geo_builder import build,download,geo_entries,field

HOME=pathlib.Path(__file__).resolve().parents[1]
def install_mihomo(folder):
 version='v1.19.33'
 release=json.loads(download('https://api.github.com/repos/MetaCubeX/mihomo/releases/tags/'+version))
 asset=next(a for a in release['assets'] if a['name']=='mihomo-linux-amd64-compatible-'+version+'.gz')
 data=download(asset['browser_download_url'])
 if asset.get('digest')!='sha256:'+hashlib.sha256(data).hexdigest():raise ValueError('Mihomo release digest mismatch')
 exe=folder/'mihomo';exe.write_bytes(gzip.decompress(data));exe.chmod(0o700)
 return exe
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mihomo',type=pathlib.Path);ap.add_argument('--cache',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,default=HOME/'dat');a=ap.parse_args()
 manifest=json.loads((HOME/'sources.json').read_text('utf-8'))
 with tempfile.TemporaryDirectory(prefix='honk-build-') as temp:
  work=pathlib.Path(temp);cache=work/'cache';cache.mkdir()
  for p in manifest['providers']+manifest['base_assets']:
   if 'local' in p:data=(HOME/p['local']).read_bytes()
   elif a.cache:data=(a.cache/p['file']).read_bytes()
   else:data=download(p['url'])
   p['sha256']=hashlib.sha256(data).hexdigest();(cache/p['file']).write_bytes(data)
  exe=a.mihomo.resolve() if a.mihomo else install_mihomo(work)
  report,parsed=build(manifest,cache,work/'candidate',exe,True)
  candidate=work/'candidate'
  # Separate custom databases contain only our migration categories; runtime
  # assets merge those categories with upstream categories for native honk.
  for kind in ['geosite','geoip']:
   all_entries=geo_entries((candidate/(kind+'.dat')).read_bytes())
   custom={k:v for k,v in all_entries.items() if k.startswith('mig-')}
   b=b''.join(field(1,v) for v in custom.values())
   (candidate/('custom-'+kind+'.dat')).write_bytes(b)
   assert geo_entries(b)==custom
  a.out.mkdir(parents=True,exist_ok=True)
  names=['geosite.dat','geoip.dat','custom-geosite.dat','custom-geoip.dat','rules-audit.json']
  for name in names:shutil.copy2(candidate/name,a.out/name)
  sums=[]
  for name in names:
   digest=hashlib.sha256((a.out/name).read_bytes()).hexdigest()
   sums.append(digest+'  '+name)
   if name.endswith('.dat'):(a.out/(name+'.sha256')).write_text(digest+'  '+name+'\n','utf-8')
  (a.out/'SHA256SUMS').write_text('\n'.join(sums)+'\n','utf-8')
  print('PASS:',len(parsed),'providers, all Geo records roundtrip-equal; no router operations')
if __name__=='__main__':main()
