# -*- coding: utf-8 -*-
"""Locally confirmed identities. A filename is never rewritten or trusted as AI output."""
import json
import os
import re
import threading
from urllib.parse import urlsplit
from novinky_catalogue import normalize, VIDEO_EXT
from cinema_content_filter import safe_file, safe_card


def file_ident(value):
    value=str(value or '').strip()
    if re.fullmatch(r'[A-Za-z0-9]{6,64}',value):
        return value
    parsed=urlsplit(value)
    if parsed.scheme not in ('https','http') or parsed.hostname not in ('webshare.cz','www.webshare.cz'):
        raise ValueError('Zadej odkaz na soubor Webshare nebo jeho identifikátor.')
    match=re.search(r'(?:^|/)file/([A-Za-z0-9]{6,64})(?:/|$)',parsed.path+'/' + parsed.fragment)
    if not match:
        raise ValueError('Odkaz neobsahuje identifikátor souboru Webshare.')
    return match.group(1)


def identity(value):
    if not isinstance(value,dict):
        raise ValueError('Chybí název filmu.')
    title=str(value.get('title') or '').strip()
    original=str(value.get('original') or '').strip()
    if not title or len(title)>150 or len(original)>150 or any(c in title+original for c in '\r\n[]<>'):
        raise ValueError('Zadej platný název bez formátovacích značek.')
    year=str(value.get('year') or '')
    if year and not re.fullmatch(r'(?:18|19|20|21)\d{2}',year):
        raise ValueError('Rok musí mít čtyři číslice, nebo zůstat prázdný.')
    result={'title':title,'original':original,'year':year,'kind':value.get('kind','movie')}
    if result['kind']=='episode':
        try:
            season=int(value['season']);episode=int(value['episode'])
        except (KeyError,TypeError,ValueError):
            raise ValueError('U seriálu zadej sérii a epizodu.')
        if not 0<=season<=99 or not 1<=episode<=999:
            raise ValueError('Neplatné číslo série nebo epizody.')
        result.update(season=season,episode=episode)
    elif result['kind']!='movie':
        raise ValueError('U seriálu je nutné potvrdit konkrétní epizodu.')
    if not safe_card(result):
        raise ValueError('Explicitní obsah není povolen.')
    return result


def eligible(file):
    return (isinstance(file,dict) and bool(file.get('ident')) and bool(file.get('name'))
            and bool(VIDEO_EXT.search(str(file.get('name') or '')))
            and safe_file(file) and all(str(file.get(k,'0'))!='1' for k in ('password','removed','copyrighted'))
            and str(file.get('available','1'))!='0')


class VisualIndex:
    def __init__(self,profile):
        self.path=os.path.join(profile,'visual-identities-v1.json') if profile else None
        self.lock=threading.RLock()
        self.entries={}
        if self.path:
            try:
                with open(self.path,encoding='utf8') as stream:
                    data=json.load(stream)
                if isinstance(data,dict):
                    for ident,entry in list(data.items())[:2000]:
                        if not isinstance(entry,dict) or not eligible(entry.get('file')):
                            continue
                        if entry['file']['ident']!=ident:
                            continue
                        try:
                            self.entries[ident]={'file':entry['file'],'identity':identity(entry.get('identity'))}
                        except ValueError:
                            continue
            except (OSError,ValueError,TypeError):
                pass

    def _write(self,entries):
        if not self.path:
            raise ValueError('Profil Kodi není dostupný; přiřazení nelze uložit.')
        os.makedirs(os.path.dirname(self.path),exist_ok=True)
        tmp=self.path+'.tmp'
        with open(tmp,'w',encoding='utf8') as stream:
            json.dump(entries,stream,ensure_ascii=False)
        os.replace(tmp,self.path)

    def confirm(self,file,match):
        if not eligible(file):
            raise ValueError('Soubor je blokovaný nebo nedostupný.')
        match=identity(match)
        # No session token, API key or model response is persisted here.
        saved={k:file[k] for k in ('ident','name','size','img','stripe','stripe_count',
                 'password','removed','available','adult','is_adult','category','copyrighted') if k in file}
        with self.lock:
            entries=dict(self.entries)
            if saved['ident'] not in entries and len(entries)>=2000:
                raise ValueError('Katalog obsahuje 2000 přiřazení; nejprve odstraň stará.')
            entries[saved['ident']]={'file':saved,'identity':match}
            self._write(entries)
            self.entries=entries

    def remove(self,ident):
        with self.lock:
            entries=dict(self.entries);entries.pop(ident,None)
            self._write(entries);self.entries=entries

    def all(self):
        with self.lock:
            return [dict(entry['file'],_kivora_identity=dict(entry['identity']))
                    for entry in self.entries.values()]

    def search(self,title,year='',season=None,episode=None):
        target=normalize(title)
        if not target:
            return []
        found=[]
        for file in self.all():
            match=file['_kivora_identity']
            titles=[normalize(match[k]) for k in ('title','original') if match.get(k)]
            if not any(n==target or len(target)>=3 and n.startswith(target+' ') for n in titles):
                continue
            if year and year!=match['year']:
                continue
            if season is not None and match.get('season')!=season:
                continue
            if episode is not None and match.get('episode')!=episode:
                continue
            if eligible(file):
                found.append(file)
        return found
