# -*- coding: utf-8 -*-
"""Optional poster-only fallback: CSFD/CZDB has priority.

Cinemeta is queried only when a Webshare-confirmed card lacks real poster art.
It cannot create movie entries, change the Czech title or declare availability.
"""
import io
import json
import os
import re
import time
from difflib import SequenceMatcher
from urllib.parse import quote
import requests
from novinky_catalogue import normalize

def select_poster(payload, title, year=''):
    rows=payload.get('metas') if isinstance(payload,dict) else None
    if not isinstance(rows,list):
        return None
    target=normalize(title)
    possible=[]
    for row in rows[:20]:
        name=normalize(row.get('name') or '')
        if not name or not target:
            continue
        score=SequenceMatcher(None,target,name).ratio()
        if score<0.92:
            continue
        yeartext=str(row.get('releaseInfo') or row.get('year') or '')
        match=re.match(r'(?:19|20)\d{2}',yeartext)
        if year and match and abs(int(year)-int(match.group()))>1:
            continue
        poster=str(row.get('poster') or '')
        background=str(row.get('background') or '')
        if not poster.startswith('https://'):
            continue
        if background and not background.startswith('https://'):
            background=''
        possible.append((score,{'poster':poster[:1200],'fanart':background[:1200]}))
    return max(possible,key=lambda v:v[0])[1] if possible else None

class Artwork:
    def __init__(self, profile=None, transport=None, budget=12):
        self.path=os.path.join(profile,'cinema-artwork-v1.json') if profile else None
        self.transport=transport or requests.get
        self.budget=budget
        self.cache={}
        if self.path:
            try:
                with io.open(self.path,'r',encoding='utf8') as handle:
                    self.cache=json.load(handle)
            except (OSError,ValueError,TypeError):
                pass

    def lookup(self, title, year='', kind='movie'):
        key='%s|%s|%s'%(kind,normalize(title),year)
        cached=self.cache.get(key)
        now=time.time()
        if isinstance(cached,dict) and now-cached.get('time',0)<(7*86400 if cached.get('art') else 1200):
            return cached.get('art')
        if self.budget<=0:
            return None
        self.budget-=1
        media='series' if kind=='show' else 'movie'
        endpoint='https://v3-cinemeta.strem.io/catalog/%s/top/search=%s.json'%(media,quote(title,safe=''))
        art=None
        try:
            response=self.transport(endpoint,timeout=(2,3))
            response.raise_for_status()
            art=select_poster(response.json(),title,year)
        except (requests.RequestException,ValueError,TypeError,AttributeError):
            pass
        self.cache[key]={'time':now,'art':art}
        if self.path:
            try:
                os.makedirs(os.path.dirname(self.path),exist_ok=True)
                with io.open(self.path+'.tmp','w',encoding='utf8') as output:
                    json.dump(self.cache,output,ensure_ascii=False)
                os.replace(self.path+'.tmp',self.path)
            except (OSError,TypeError):
                pass
        return art
