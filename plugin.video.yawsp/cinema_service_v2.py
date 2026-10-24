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
from cinema_search_v3 import (MOVIE_SEEDS, SHOW_SEEDS, candidate_names,
                              query_plan, matching_files, seed_batch, localized_title)


class CinemaService:
    def __init__(self, token, fetch, availability, catalogue=None, calendar=None, profile=None):
        self.token=token
        self.fetch=fetch
        self.availability=availability
        self.metadata=catalogue
        self.calendar=calendar
        self.home_cache=None
        self.cache_path=os.path.join(profile,'cinema-v2-home.json') if profile else None
        from cinema_artwork import Artwork
        self.artwork=Artwork(profile, budget=12)
        self.search_cache={}
        self.series_cache={}
        self.last_diagnostics=''
        self.hits_path=os.path.join(profile,'cinema-v3-hits.json') if profile else None

    def _decorate(self, group, metadata=None):
        if metadata:
            group['metadata']=metadata
        elif self.metadata:
            group['metadata']=self.metadata.lookup(group['title'],group.get('year',''))
        entry=card(group)
        if not entry.get('poster'):
            # Only enrich an already confirmed Webshare file-backed title.
            candidates=[entry.get('original') or '',group['title']]
            for title in candidates:
                if not title:
                    continue
                art=self.artwork.lookup(title,entry.get('year') or '',
                                        kind=group.get('kind','movie'))
                if art:
                    entry['poster']=art.get('poster','')
                    entry['fanart']=entry.get('fanart') or art.get('fanart','')
                    break
        return entry

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
        for e in candidates[:14]:
            title=e['title']
            original=e.get('original') or ''
            md=self.metadata.lookup(title) if self.metadata else None
            aliases=[]
            for n in (title,original,(md or {}).get('original',''),
                      (md or {}).get('title','')):
                if n and normalize(n) not in {normalize(a) for a in aliases}:
                    aliases.append(n)
            found=[]
            api_failed=False
            for alias in aliases[:2]:
                page=collect_pages(self.fetch,self.token,alias,max_pages=1)
                if page is None:
                    api_failed=True
                    break
                found.extend(page)
                if len(found)>55:
                    break
            if api_failed:
                self.last_diagnostics='Webshare neodpovídá; premiéry nelze ověřit'
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
        # Broader candidate pool improves rating shelves; still checked on Webshare.
        movies=verified_groups(movies,self.availability,maximum=24,checked=65)
        shows=verified_groups(shows,self.availability,maximum=24,checked=65)
        add_metadata(movies,self.metadata,maximum=22)
        add_metadata(shows,self.metadata,maximum=22)
        self.last_diagnostics=('Webshare dotazy: %d, videosoubory: %d, '
            'ověřené filmy: %d, seriály: %d' %
            (stats['queries'],stats['video_files'],len(movies),len(shows)))
        return ([self._decorate(g,g.get('metadata')) for g in movies],
                [self._decorate(g,g.get('metadata')) for g in shows])

    def _discover_hits(self, movie_batch=6, show_batch=2):
        """Incrementally search classic titles, retaining confirmed Webshare hits."""
        cache={'movies_next':0,'shows_next':0,'entries':{}}
        if self.hits_path:
            try:
                with io.open(self.hits_path,'r',encoding='utf8') as handle:
                    stored=json.load(handle)
                if isinstance(stored,dict) and isinstance(stored.get('entries'),dict):
                    cache=stored
            except (OSError,ValueError,TypeError):
                pass
        now=time.time()
        valid={}
        for key,item in cache.get('entries',{}).items():
            if not isinstance(item,dict):
                continue
            age=now-float(item.get('time',0))
            ttl=86400 if item.get('files') else 7200
            if 0<=age<ttl:
                valid[key]=item
        cache['entries']=valid
        for kind,seeds,batch,offset_key in (
                ('movie',MOVIE_SEEDS,movie_batch,'movies_next'),
                ('show',SHOW_SEEDS,show_batch,'shows_next')):
            offset=int(cache.get(offset_key,0) or 0)
            sampled=seed_batch(seeds,offset,batch)
            for title,original,year in sampled:
                key=kind+':'+normalize(title)
                if key in valid:
                    continue
                aliases=candidate_names(title,{'original':original})
                hits=[]
                error=False
                for alias in aliases[:3]:
                    page=collect_pages(self.fetch,self.token,alias,
                                       max_pages=1,sort='rating')
                    if page is None:
                        error=True
                        continue
                    hits.extend(matching_files(page,aliases,kind=kind,
                            year=year if kind=='movie' else None))
                    if hits:
                        break
                # No negative cache on Webshare errors.
                if error and not hits:
                    continue
                valid[key]={'time':now,'kind':kind,'year':year,'title':title,
                    'original':original,'files':list({
                       f['ident']:{k:f[k] for k in ('ident','name','size','img',
                              'available','removed','copyrighted','adult') if k in f}
                       for f in hits if f.get('ident')}.values())[:30]}
            cache[offset_key]=(offset+len(sampled))%len(seeds)
        if self.hits_path:
            try:
                with io.open(self.hits_path+'.tmp','w',encoding='utf8') as handle:
                    json.dump(cache,handle,ensure_ascii=False)
                os.replace(self.hits_path+'.tmp',self.hits_path)
            except (OSError,TypeError):
                pass
        raw={'movie':[],'show':[]}
        for item in valid.values():
            kind=item.get('kind')
            if kind not in raw or not item.get('files'):
                continue
            aliases=candidate_names(item['title'],{'original':item['original']})
            for g in groups(item['files'],kind):
                matches=matching_files(g['files'],aliases,kind=kind,
                              year=item['year'] if kind=='movie' else None)
                if not matches:
                    continue
                g['files']=matches
                g['best']=matches[0]
                g['seed_title']=item['title']
                g['seed_original']=item['original']
                if kind=='show':
                    g['year']=str(item['year'])
                raw[kind].append(g)
        movies=verified_groups(raw['movie'],self.availability,maximum=30,checked=45)
        shows=verified_groups(raw['show'],self.availability,maximum=18,checked=30)
        for listing in (movies,shows):
            if self.metadata:
                for g in listing[:22]:
                    title=g['seed_title']
                    data=self.metadata.lookup(title,
                        str(g['year']) if g['group_kind']=='movie' else '')
                    if not data:
                        data=self.metadata.lookup(g['seed_original'])
                    if data:
                        g['metadata']=data
        for listing in (movies, shows):
            for g in listing:
                if not g.get('metadata'):
                    g['metadata']=localized_title(g['title'],g['kind'],g.get('year'))
        if self.metadata:
            self.metadata.save()
        return ([self._decorate(g,g.get('metadata')) for g in movies],
                [self._decorate(g,g.get('metadata')) for g in shows])

    @staticmethod
    def _add_ranked_shelves(home):
        """Build the four lists from existing checked cards (no invented films)."""
        from cinema_rankings import create_shelves
        movie_cards=((home.get('premieres') or [])+(home.get('movies') or [])
                     +(home.get('classics') or []))
        show_cards=(home.get('shows') or [])+(home.get('classic_shows') or [])
        home.update(create_shelves(movie_cards,show_cards))
        return home

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
                    isinstance(cached.get('home'),dict) and
                    'classics' in cached['home']):
                    self.home_cache=cached['home']
                    self._add_ranked_shelves(self.home_cache)
                    self.last_diagnostics='Katalog načten z ověřené 8minutové mezipaměti'
                    return self.home_cache
            except (OSError,ValueError,TypeError):
                pass
        premieres=self._premieres(9)
        recent,shows=self._from_webshare()
        classics,classic_shows=self._discover_hits()
        seen={normalize(c['raw']) for c in premieres}
        additional=[c for c in recent if normalize(c['raw']) not in seen]
        self.home_cache=self._add_ranked_shelves({
            'premieres':premieres,
            'movies':additional or recent,
            'shows':shows,
            'classics':classics,
            'classic_shows':classic_shows
        })
        if self.cache_path and (premieres or recent or shows or classics or classic_shows):
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
        """Search Czech/original titles and release variants, validate files."""
        term=(query or '').strip()
        if not term:
            return []
        key=normalize(term)
        if key in self.search_cache:
            cards=self.search_cache[key]
            return [c for c in cards if kind=='all' or c['kind']==kind]
        md=self.metadata.lookup(term) if self.metadata else None
        names=candidate_names(term,md)
        matches={}
        successful=0
        # Short, bounded calls; searching Czech titles is followed by the
        # original title and dot-separated release filenames when necessary.
        for index,attempt in enumerate(query_plan(term,md,limit=10)):
            page=collect_pages(self.fetch,self.token,attempt,
                               max_pages=3 if index==0 else (2 if index<4 else 1),
                               sort='rating' if index<4 else 'recent')
            if page is None:
                continue
            valid=matching_files(page,names)
            for f in valid:
                matches[str(f['ident'])]=f
            if valid:
                successful+=1
            if successful>=2 or (successful and len(matches)>=80):
                break
        combined=[]
        for mode in ('movie','show'):
            candidates=groups(list(matches.values()),mode)
            candidates=verified_groups(candidates,self.availability,
                                       maximum=50,checked=90)
            add_metadata(candidates,self.metadata,maximum=25)
            for g in candidates:
                # The Avengers (2012) metadata must not overwrite Endgame.
                if md and normalize(g['title']) in {normalize(n) for n in names}:
                    if not g['year'] or not md.get('year') or str(g['year'])==str(md['year']):
                        g['metadata']=md
                if not g.get('metadata'):
                    g['metadata']=localized_title(g['title'],mode,g.get('year'))
                combined.append(self._decorate(g,g.get('metadata')))
        combined.sort(key=lambda c:(0 if normalize(c['raw'])==key else 1,
                      normalize(c['title']),str(c.get('year') or '')))
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
            self.series_cache[key]=grouped_episodes(entries+existing,raw,
                aliases=(original,) if original else ())
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
