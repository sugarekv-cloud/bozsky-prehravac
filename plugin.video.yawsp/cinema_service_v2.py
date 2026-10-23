# -*- coding: utf-8 -*-
"""Bridge between Webshare discovery, Czech film metadata and the cinema UI.

The cinema feed supplies order and artwork, never an unverified title.
The on-screen listings are guaranteed to have at least one checked file ident.
"""
from datetime import date, timedelta
import os
import io
import json
import time
from cinema_catalog_v2 import (groups,verified_groups,add_metadata,card,
    sort_cards,grouped_episodes,choose_files,collect_pages,matching_release)
from cinematic_discovery import discover
from novinky_catalogue import normalize
from catalog_engine import file_label


class CinemaService:
    def __init__(self, token, fetch, availability, catalogue=None, calendar=None, profile=None):
        self.token=token
        self.fetch=fetch
        self.availability=availability
        self.metadata=catalogue
        self.calendar=calendar
        self.home_cache=None
        self.cache_path=os.path.join(profile,'cinema-v2-home.json') if profile else None
        self.search_cache={}
        self.series_cache={}
        self.last_diagnostics=''

    def _decorate(self, group, metadata=None):
        if metadata:
            group['metadata']=metadata
        elif self.metadata:
            group['metadata']=self.metadata.lookup(group['title'],group.get('year',''))
        return card(group)

    def _premieres(self, maximum=10):
        if not self.calendar:
            return []
        try:
            events=self.calendar.load()
        except Exception:
            return []
        today=date.today()
        candidates=[]
        for e in events:
            try:
                when=date.fromisoformat(e['premiere'])
            except (KeyError,ValueError,TypeError):
                continue
            if today-timedelta(days=730) <= when <= today+timedelta(days=5):
                candidates.append(e)
        candidates.sort(key=lambda e:e['premiere'],reverse=True)
        # A cinema premiere does not imply a copy exists on Webshare.
        prepared=[]
        seen=set()
        for e in candidates[:25]:
            title=e['title']
            original=e.get('original') or ''
            md=self.metadata.lookup(title) if self.metadata else None
            aliases=[]
            for n in (title,original,(md or {}).get('original',''),
                      (md or {}).get('title','')):
                if n and normalize(n) not in {normalize(a) for a in aliases}:
                    aliases.append(n)
            found=[]
            for alias in aliases[:3]:
                page=collect_pages(self.fetch,self.token,alias,max_pages=1)
                if page is not None:
                    found.extend(page)
                if len(found)>55:
                    break
            matches=matching_release(found,aliases,kind='movie')
            if not matches:
                continue
            local=groups(matches,'movie')
            for g in local[:2]:
                # Avoid mixing a different film with a similar title.
                if g['year'] and md and md.get('year') and g['year'] != str(md['year']):
                    continue
                key=(normalize(g['title']),g['year'])
                if key in seen:
                    continue
                seen.add(key)
                g['metadata']=md
                g['premiere']=e['premiere']
                prepared.append(g)
            if len(prepared)>=maximum+5:
                break
        verified=verified_groups(prepared,self.availability,maximum=maximum,checked=maximum+5)
        if self.metadata:
            self.metadata.save()
        return [dict(self._decorate(g,g.get('metadata')),tag='premiere',premiere=g.get('premiere',''))
                for g in verified]

    def _from_webshare(self):
        new, popular,stats=discover(self.token,self.fetch)
        # Not just first 11: the first files can be unplayable, in a pack,
        # passworded, or have missing metadata. Inspect more candidates.
        movies=groups(new+popular,'movie')
        shows=groups(new+popular,'show')
        movies=verified_groups(movies,self.availability,maximum=16,checked=48)
        shows=verified_groups(shows,self.availability,maximum=16,checked=48)
        add_metadata(movies,self.metadata,maximum=14)
        add_metadata(shows,self.metadata,maximum=14)
        self.last_diagnostics=('Webshare dotazy: %d, videosoubory: %d, '
            'ověřené filmy: %d, seriály: %d' %
            (stats['queries'],stats['video_files'],len(movies),len(shows)))
        return ([self._decorate(g,g.get('metadata')) for g in movies],
                [self._decorate(g,g.get('metadata')) for g in shows])

    def home(self):
        if self.home_cache is not None:
            return self.home_cache
        # The short cache avoids repeating expensive ČSFD/Webshare calls
        # every time the user returns to the television home screen.
        if self.cache_path:
            try:
                with io.open(self.cache_path,'r',encoding='utf8') as handle:
                    cached=json.load(handle)
                if (isinstance(cached,dict) and
                    time.time()-float(cached.get('saved',0)) < 480 and
                    isinstance(cached.get('home'),dict)):
                    self.home_cache=cached['home']
                    self.last_diagnostics='Katalog načten z ověřené 8minutové mezipaměti'
                    return self.home_cache
            except (OSError,ValueError,TypeError):
                pass
        premieres=self._premieres(9)
        recent,shows=self._from_webshare()
        seen={normalize(c['raw']) for c in premieres}
        additional=[c for c in recent if normalize(c['raw']) not in seen]
        self.home_cache={
            'premieres':premieres,
            'movies':additional or recent,
            'shows':shows
        }
        if self.cache_path:
            try:
                with io.open(self.cache_path+'.tmp','w',encoding='utf8') as handle:
                    json.dump({'saved':time.time(),'home':self.home_cache},handle,
                              ensure_ascii=False)
                os.replace(self.cache_path+'.tmp',self.cache_path)
            except (OSError,TypeError):
                pass
        return self.home_cache

    def browse(self, view, sort='date', quality='all', language='all'):
        if view=='premieres':
            source=self.home()['premieres']
        elif view=='shows':
            source=self.home()['shows']
        else:
            source=self.home()['movies']
        filtered=[]
        for c in source:
            if choose_files(c['files'],quality,language):
                filtered.append(c)
        return sort_cards(filtered,sort)

    def search(self, query, kind='all'):
        term=(query or '').strip()
        if not term:
            return []
        key=normalize(term)
        if key in self.search_cache:
            cards=self.search_cache[key]
            return [c for c in cards if kind=='all' or c['kind']==kind]
        md=self.metadata.lookup(term) if self.metadata else None
        aliases=[]
        for x in (term,(md or {}).get('title',''),(md or {}).get('original','')):
            if x and normalize(x) not in {normalize(v) for v in aliases}:
                aliases.append(x)
        all_files=[]
        for term in aliases[:3]:
            found=collect_pages(self.fetch,self.token,term,max_pages=3)
            if found:
                all_files.extend(found)
        # Search is intentionally permissive for partial titles, but the
        # movie cards still need a valid verified Webshare file.
        cleaned=[]
        for f in all_files:
            from novinky_catalogue import parse_video_name
            p=parse_video_name(f['name'])
            if not p:
                continue
            name=normalize(p['title'])
            if any(normalize(a) in name or name in normalize(a)
                   for a in aliases if len(normalize(a))>=3):
                cleaned.append(f)
        combined=[]
        for mode in ('movie','show'):
            gr=groups(cleaned,mode)
            gr=verified_groups(gr,self.availability,maximum=40,checked=70)
            add_metadata(gr,self.metadata,maximum=12)
            for g in gr:
                # Use Czech metadata result when it matches the original title.
                if md and normalize(g['title']) in {normalize(n) for n in aliases}:
                    g['metadata']=md
                combined.append(self._decorate(g,g.get('metadata')))
        combined=sorted(combined,key=lambda c:(0 if normalize(c['raw'])==key else 1,
                               normalize(c['title'])))
        self.search_cache[key]=combined
        return [c for c in combined if kind=='all' or c['kind']==kind]

    def files(self, card, quality='all', language='all'):
        # On title selection, find ALL variants of the movie; broad discovery
        # typically discovers only one copy of each quality.
        candidates=list(card.get('files') or [])
        aliases=[card.get('raw') or '',card.get('original') or '']
        for name in aliases:
            if name:
                fetched=collect_pages(self.fetch,self.token,name,max_pages=4)
                candidates.extend(matching_release(fetched,aliases,'movie',
                                                    card.get('file_year') or ''))
        unique={f['ident']:f for f in candidates if f.get('ident')}
        return self.availability.check_files(
            choose_files(list(unique.values()),quality,language),limit=60)

    def seasons(self, card):
        raw=card['raw']
        key=normalize(raw)
        if key not in self.series_cache:
            # Full paged search by series title, rather than only episodes
            # returned by a broad home discovery query. 20*100 maximum.
            entries=collect_pages(self.fetch,self.token,raw,max_pages=20)
            if entries is None:
                entries=card.get('files') or []
            original=card.get('original') or ''
            if original and normalize(original)!=key:
                other=collect_pages(self.fetch,self.token,original,max_pages=8)
                if other:
                    entries.extend(other)
            existing=card.get('files') or []
            self.series_cache[key]=grouped_episodes(entries+existing,raw)
        return self.series_cache[key]

    def episode_variants(self, card, season, episode, quality='all', language='all'):
        found=self.seasons(card).get(season,{}).get(episode,[])
        return self.availability.check_files(
            choose_files(found,quality,language),limit=30)

    def file_rows(self, files, poster=''):
        rows=[]
        for f in files:
            rows.append({
                'kind':'file', 'title':file_label(f), 'raw':f['name'],
                'ident':f['ident'], 'files':[f], 'year':'','genre':'',
                'plot':f['name'], 'rating':None,'quality':file_label(f),
                'poster':poster, 'fanart':''
            })
        return rows
