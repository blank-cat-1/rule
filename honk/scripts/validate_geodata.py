#!/usr/bin/env python3
"""Fail closed if a routing/DNS category is absent or a redundant clone returns."""
import argparse,pathlib,re
from geo_builder import geo_entries,fields

REMOVED={'mig-cn-domain','mig-cn-ip','mig-google-ip','mig-netflix-ip','mig-private-domain'}
def validate_assets(config,directory):
 assets={kind:geo_entries((directory/(kind+'.dat')).read_bytes()) for kind in ['geosite','geoip']}
 counts={kind:0 for kind in assets}
 for kind,code in re.findall(r'\b(geosite|geoip):\s*([\w!@-]+)',config):
  if kind=='geoip' and code=='private':continue # Native built-in set.
  category,_,attribute=code.lower().partition('@')
  if category not in assets[kind]:raise ValueError('referenced '+kind+' category missing: '+category)
  records=[v for k,v in fields(assets[kind][category]) if k==2]
  if not records:raise ValueError('empty '+kind+' category: '+category)
  if attribute:
   attrs=[]
   for record in records:
    for k,v in fields(record):
     if k==3:attrs.extend(value.decode().lower() for field,value in fields(v) if field==1)
   if attribute not in attrs:raise ValueError('referenced geosite attribute missing: '+code)
  counts[kind]+=1
 for kind,entries in assets.items():
  if REMOVED&entries.keys():raise ValueError('redundant migration categories remain in '+kind)
  custom=directory/('custom-'+kind+'.dat')
  if custom.exists():
   if REMOVED&geo_entries(custom.read_bytes()).keys():raise ValueError('redundant custom category remains')
 print('PASS: all referenced Geo categories/attributes present; redundant categories absent')
 return counts
def main():
 root=pathlib.Path(__file__).resolve().parents[1]
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=pathlib.Path,default=root/'config.dae');ap.add_argument('--dat',type=pathlib.Path,default=root/'dat');a=ap.parse_args()
 validate_assets(a.config.read_text('utf-8'),a.dat)
if __name__=='__main__':main()
