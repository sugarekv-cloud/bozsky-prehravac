# -*- coding: utf-8 -*-
"""Local KIVORA profiles. The legacy main profile keeps its existing files.

Profiles never contain Webshare usernames, passwords, access tokens or URLs.
All profile identifiers are generated locally, validated before filename use.
"""
import io
import json
import os
import re
import uuid

REGISTRY='kivora-profiles-v1.json'
MAX_PROFILES=8
_ID=re.compile(r'^[0-9a-f]{32}$')
MAIN={'id':'main','name':'Hlavní'}

def _path(directory):
    return os.path.join(directory,REGISTRY)

def _read(directory):
    try:
        with io.open(_path(directory),'r',encoding='utf-8') as stream:
            raw=json.load(stream)
    except (OSError,ValueError,TypeError):
        raw={}
    entries=[dict(MAIN)]
    seen={'main'}
    for p in (raw.get('profiles') or []) if isinstance(raw,dict) else []:
        if not isinstance(p,dict):
            continue
        ident=p.get('id')
        name=p.get('name')
        if not isinstance(ident,str) or not _ID.fullmatch(ident) or ident in seen:
            continue
        if not isinstance(name,str) or not name.strip():
            continue
        entries.append({'id':ident,'name':name.strip()[:36]})
        seen.add(ident)
        if len(entries)>=MAX_PROFILES:
            break
    active=raw.get('active') if isinstance(raw,dict) else 'main'
    if active not in seen:
        active='main'
    return {'active':active,'profiles':entries}

def _write(directory,data):
    if not os.path.isdir(directory):
        os.makedirs(directory)
    path=_path(directory)
    tmp=path+'.tmp'
    with io.open(tmp,'w',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,sort_keys=True)
    os.replace(tmp,path)

def list_profiles(directory):
    return _read(directory)['profiles']

def active_profile(directory):
    data=_read(directory)
    return next(p for p in data['profiles'] if p['id']==data['active'])

def add_profile(directory,name):
    if not isinstance(name,str):
        raise ValueError('Zadej název profilu.')
    name=' '.join(name.strip().split())[:36]
    if not name or any(ord(c)<32 for c in name):
        raise ValueError('Zadej platný název profilu.')
    data=_read(directory)
    if len(data['profiles'])>=MAX_PROFILES:
        raise ValueError('Maximální počet profilů je osm.')
    if any(p['name'].casefold()==name.casefold() for p in data['profiles']):
        raise ValueError('Profil s tímto názvem již existuje.')
    ident=uuid.uuid4().hex
    data['profiles'].append({'id':ident,'name':name})
    data['active']=ident
    _write(directory,data)
    return ident

def activate_profile(directory,ident):
    data=_read(directory)
    if ident not in (p['id'] for p in data['profiles']):
        raise ValueError('Neznámý profil.')
    data['active']=ident
    _write(directory,data)
    return active_profile(directory)

def delete_profile(directory,ident):
    data=_read(directory)
    if ident=='main' or ident==data['active']:
        raise ValueError('Hlavní nebo aktivní profil nelze smazat.')
    if ident not in (p['id'] for p in data['profiles']):
        raise ValueError('Neznámý profil.')
    data['profiles']=[p for p in data['profiles'] if p['id']!=ident]
    _write(directory,data)
    # Delete only the two known files, never arbitrary user-provided paths.
    for filename in ('fckyo-watch-state-v1-%s.json'%ident,
                     'fckyo-playback-pending-v1-%s.json'%ident):
        try:
            os.remove(os.path.join(directory,filename))
        except OSError:
            pass

def state_paths(directory):
    ident=active_profile(directory)['id']
    suffix='' if ident=='main' else '-'+ident
    return (os.path.join(directory,'fckyo-watch-state-v1%s.json'%suffix),
            os.path.join(directory,'fckyo-playback-pending-v1%s.json'%suffix))
