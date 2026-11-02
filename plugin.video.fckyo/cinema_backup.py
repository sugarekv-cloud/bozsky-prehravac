# -*- coding: utf-8 -*-
"""Portable KIVORA watch/favourites backup without Webshare credentials."""
import io
import json
import os
import time
from cinema_user_state import WatchStore, _safe, MAX_ENTRIES, MAX_FAVORITES

SCHEMA=1
MAX_BYTES=2*1024*1024

def _scrub(raw):
    if not isinstance(raw,dict):
        raise ValueError('Neplatný formát zálohy')
    clean={'watch':{},'favorites':{}}
    for section,limit in (('watch',MAX_ENTRIES),('favorites',MAX_FAVORITES)):
        entries=raw.get(section,{})
        if not isinstance(entries,dict):
            raise ValueError('Neplatný seznam položek')
        for key,value in list(entries.items())[:limit]:
            if not isinstance(key,str) or not isinstance(value,dict):
                continue
            if value.get('kind') not in ('movie','show'):
                continue
            item=_safe(value)
            if not item.get('title') or not item.get('ident') or not item.get('name'):
                continue
            if section=='watch':
                for name in ('position','total','updated'):
                    try:
                        item[name]=max(0,min(float(value.get(name) or 0),1e11))
                    except (TypeError,ValueError,OverflowError):
                        item[name]=0
                item['completed']=value.get('completed') is True
            else:
                try:
                    item['added']=max(0,float(value.get('added') or 0))
                except (ValueError,TypeError):
                    item['added']=0
            clean[section][key[:250]]=item
    return clean

def export_backup(profile,destination):
    store=WatchStore(profile)
    data=_scrub(store._data())
    package={'schema':SCHEMA,'type':'kivora-library',
             'created':int(time.time()),'data':data}
    encoded=json.dumps(package,ensure_ascii=False,separators=(',',':'))
    if len(encoded.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Záloha je příliš velká')
    directory=os.path.dirname(destination)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with io.open(destination,'w',encoding='utf-8') as stream:
        stream.write(encoded)
    return len(data['watch']),len(data['favorites'])

def import_backup(profile,source):
    if os.path.getsize(source)>MAX_BYTES:
        raise ValueError('Soubor je příliš velký')
    with io.open(source,'r',encoding='utf-8') as stream:
        package=json.load(stream)
    if not isinstance(package,dict) or package.get('type')!='kivora-library' or package.get('schema')!=SCHEMA:
        raise ValueError('Nepodporovaná záloha KIVORA')
    data=_scrub(package.get('data'))
    store=WatchStore(profile)
    store._write(store.path,data)
    return len(data['watch']),len(data['favorites'])
