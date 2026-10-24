# -*- coding: utf-8 -*-
"""Incremental Cinemeta discovery feed: metadata only, never playable content.

Two modest catalog pages per category are downloaded on first launch; later
refreshes page forward. Webshare confirmation happens separately. No account
credentials, tokens or stream URLs are ever sent to or read from Cinemeta.
"""
import io
import json
import os
import re
import time
import requests
from novinky_catalogue import normalize

CATALOG_SOURCES=(
    'https://cinemeta-catalogs.strem.io/top',
    'https://v3-cinemeta.strem.io',
)
KIND_MAP={'movie':'movie','show':'series'}
MAX_ITEMS=650
REFRESH_SECONDS=3600 * 12
RETRY_SECONDS=3600
ART_FIELDS=('poster','background')
_SAFE_URL=re.compile(r'^https://[A-Za-z0-9][A-Za-z0-9.:-]+/',re.I)
_YEAR=re.compile(r'(?:19|20)\d{2}')


def parse_catalog(data, kind):
    """Strictly convert third-party JSON into a list of bounded film seeds."""
    if not isinstance(data,dict) or not isinstance(data.get('metas'),list):
        return []
    result=[]
    seen=set()
    for raw in data['metas'][:150]:
        if not isinstance(raw,dict):
            continue
        title=str(raw.get('name') or '').strip()[:160]
        if not title or len(title)<2:
            continue
        year_match=_YEAR.search(str(raw.get('year') or raw.get('releaseInfo') or
                                raw.get('released') or ''))
        if not year_match:
            continue
        year=int(year_match.group())
        if year<1900 or year>2099:
            continue
        key=normalize(title)+'@'+str(year)
        if key in seen:
            continue
        seen.add(key)
        poster=str(raw.get('poster') or '')
        background=str(raw.get('background') or '')
        def art(url):
            return url[:750] if _SAFE_URL.match(url) else ''
        result.append({
            'name':title, 'year':year, 'kind':kind,
            'original':str(raw.get('original') or title).strip()[:160],
            'poster':art(poster), 'background':art(background),
            'id':str(raw.get('imdb_id') or raw.get('id') or '')[:45],
        })
    return result


class CatalogFeed:
    def __init__(self, profile=None, transport=None):
        self.path=os.path.join(profile,'cinema-v4-feed.json') if profile else None
        self.transport=transport or requests.get
        self.data={'movie':[], 'show':[], 'next':{'movie':0,'show':0},
                   'checked':{}, 'source':''}
        if self.path:
            try:
                with io.open(self.path,'r',encoding='utf8') as f:
                    loaded=json.load(f)
                if isinstance(loaded,dict) and isinstance(loaded.get('next'),dict):
                    for kind in KIND_MAP:
                        if isinstance(loaded.get(kind),list):
                            self.data[kind]=loaded[kind][:MAX_ITEMS]
                        self.data['next'][kind]=int(loaded['next'].get(kind) or 0)
                    if isinstance(loaded.get('checked'),dict):
                        self.data['checked']=loaded['checked']
                    self.data['source']=str(loaded.get('source') or '')
            except (OSError,ValueError,TypeError):
                pass

    def _page(self, kind, skip):
        tail='/catalog/%s/top'%KIND_MAP[kind]
        suffix='.json' if skip==0 else '/skip=%d.json'%skip
        preferred=self.data.get('source')
        sources=([preferred]+[s for s in CATALOG_SOURCES if s!=preferred]
                 if preferred in CATALOG_SOURCES else CATALOG_SOURCES)
        for source in sources:
            try:
                response=self.transport(source+tail+suffix,timeout=(3,5))
                response.raise_for_status()
                payload=response.json()
                if not isinstance(payload,dict) or not isinstance(payload.get('metas'),list):
                    continue
                self.data['source']=source
                return parse_catalog(payload,kind),len(payload['metas'])
            except (requests.RequestException,ValueError,TypeError,AttributeError):
                continue
        return None,None

    def refresh(self, force=False, pages_per_kind=1):
        """Import up to 100+ records/page into a persistent bounded title index."""
        now=time.time()
        changed=False
        for kind in KIND_MAP:
            last=float(self.data['checked'].get(kind) or 0)
            if not force and now-last<REFRESH_SECONDS:
                continue
            # If a source is unreachable, retry next hour, not on every UI open.
            any_success=False
            for _ in range(max(1,min(int(pages_per_kind),3))):
                skip=max(0,int(self.data['next'][kind]))
                new,count=self._page(kind,skip)
                if new is None:
                    break
                any_success=True
                previous={(normalize(v['name']),int(v['year'])):v
                          for v in self.data[kind]
                          if isinstance(v,dict) and v.get('name') and v.get('year')}
                for item in new:
                    previous.setdefault((normalize(item['name']),int(item['year'])),item)
                self.data[kind]=list(previous.values())[-MAX_ITEMS:]
                # Stremio pages are typically 100 results. Advance by the
                # actual count so small/partial pages cannot endlessly repeat.
                self.data['next'][kind]=skip+count if count else 0
                if count==0:
                    self.data['next'][kind]=0
                    break
                changed=True
            self.data['checked'][kind]=now if any_success else now-(REFRESH_SECONDS-RETRY_SECONDS)
        if changed:
            self.save()
        return {kind:list(self.data[kind]) for kind in KIND_MAP}

    def save(self):
        if not self.path:
            return
        try:
            folder=os.path.dirname(self.path)
            if not os.path.isdir(folder):
                os.makedirs(folder)
            temp=self.path+'.tmp'
            with io.open(temp,'w',encoding='utf8') as out:
                json.dump(self.data,out,ensure_ascii=False,separators=(',',':'))
            os.replace(temp,self.path)
        except (OSError,TypeError):
            pass

    def sizes(self):
        return {kind:len(self.data[kind]) for kind in KIND_MAP}
