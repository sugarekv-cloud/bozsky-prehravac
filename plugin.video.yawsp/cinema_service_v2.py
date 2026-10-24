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
from cinema_dedupe import (consolidate, unify_sections, unique_home_rails,
                           identity)
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
        self.feed=None
        self._feed_force=False

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

    def refresh_catalogue(self):
        """Explicit user-triggered refresh; never runs in the background."""
        self.home_cache=None
        self.search_cache.clear()
        self._feed_force=True
        if self.cache_path:
            try:
                os.remove(self.cache_path)
            except OSError:
                pass

    def _discover_hits(self, movie_batch=7, show_batch=3):
        """Gradually reconcile public film metadata against real Webshare files.

        Each launch refreshes only a small group of titles; the growing feed
        index persists across sessions. Unverified metadata never makes a card.
        """
        from cinema_feed_v4 import CatalogFeed
        if self.feed is None and self.hits_path:
            self.feed=CatalogFeed(os.path.dirname(self.hits_path))
        film_feed={'movie':[],'show':[]}
        if self.feed is not None:
            try:
                # First import populates two pages/type; later imports are
                # incremental and can be forced by a deliberate UI command.
                sizes=self.feed.sizes()
                first=not any(sizes.values())
                film_feed=self.feed.refresh(force=self._feed_force,
                                           pages_per_kind=2 if first else 1)
            except Exception:
                import traceback
                traceback.print_exc()
        self._feed_force=False
        # Retain the evergreen reference seeds so Green Mile/Avengers continue
        # working even when Cinemeta is temporarily offline.
        def seeds_for(kind, curated, opening):
            dynamic=[]
            metadata={}
            for item in film_feed.get(kind,[]):
                if not isinstance(item,dict):
                    continue
                try:
                    title=item['name']
                    year=int(item['year'])
                except (KeyError,ValueError,TypeError):
                    continue
                dynamic.append((title,item.get('original') or title,year))
                metadata[(normalize(title),year)]=item
            candidates=list(curated[:opening])
            remaining_static=list(curated[opening:])
            # Interleave established classics with the large downloaded feed
            # so new movies never starve perennial favourites.
            for pos in range(0,max(len(dynamic),len(remaining_static)*3),8):
                candidates.extend(dynamic[pos:pos+8])
                candidates.extend(remaining_static[:3])
                del remaining_static[:3]
            candidates.extend(remaining_static)
            seen=set()
            result=[]
            for title,original,year in candidates:
                ident=(normalize(title),year)
                if ident not in seen:
                    seen.add(ident)
                    result.append((title,original,year))
            return result,metadata
        movie_seeds,movie_meta=seeds_for('movie',MOVIE_SEEDS,6)
        show_seeds,show_meta=seeds_for('show',SHOW_SEEDS,4)
        cache={'movies_next':0,'shows_next':0,'entries':{}}
        if self.hits_path:
            try:
                with io.open(self.hits_path,'r',encoding='utf8') as handle:
                    loaded=json.load(handle)
                if isinstance(loaded,dict) and isinstance(loaded.get('entries'),dict):
                    cache=loaded
            except (OSError,ValueError,TypeError):
                pass
        now=time.time()
        valid={}
        for key,item in cache.get('entries',{}).items():
            if not isinstance(item,dict):
                continue
            try:
                age=now-float(item.get('time',0))
            except (ValueError,TypeError):
                continue
            ttl=86400 if item.get('files') else 7200
            if 0<=age<ttl:
                valid[key]=item
        cache['entries']=valid
        for kind,seeds,batch,index_key in (
            ('movie',movie_seeds,movie_batch,'movies_next'),
            ('show',show_seeds,show_batch,'shows_next')):
            if not seeds:
                continue
            position=int(cache.get(index_key) or 0) % len(seeds)
            sampled=seed_batch(seeds,position,batch)
            for title,original,year in sampled:
                key=kind+':'+normalize(title)+'@'+str(year)
                if key in valid:
                    continue
                names=candidate_names(title,{'original':original})
                hits=[]
                error=False
                for alias in names[:3]:
                    page=collect_pages(self.fetch,self.token,alias,max_pages=1,sort='rating')
                    if page is None:
                        error=True
                        continue
                    hits.extend(matching_files(page,names,kind=kind,
                                  year=year if kind=='movie' else None))
                    if hits:
                        break
                if error and not hits:
                    continue
                fields=('ident','name','size','img','available',
                        'removed','copyrighted','adult')
                files=list({f['ident']:{k:f[k] for k in fields if k in f}
                            for f in hits if f.get('ident')}.values())[:25]
                valid[key]={'time':now,'kind':kind,'year':year,'title':title,
                            'original':original,'files':files}
            cache[index_key]=(position+len(sampled))%len(seeds)
        cache['entries']=valid
        if self.hits_path:
            try:
                with io.open(self.hits_path+'.tmp','w',encoding='utf8') as handle:
                    json.dump(cache,handle,ensure_ascii=False)
                os.replace(self.hits_path+'.tmp',self.hits_path)
            except (OSError,TypeError):
                pass
        raw={'movie':[],'show':[]}
        seen_groups={'movie':set(),'show':set()}
        for item in valid.values():
            kind=item.get('kind')
            if kind not in raw or not item.get('files'):
                continue
            aliases=candidate_names(item['title'],{'original':item['original']})
            try:
                entry_year=int(item['year'])
            except (TypeError,ValueError):
                continue
            feed_meta=(movie_meta if kind=='movie' else show_meta).get(
                       (normalize(item['title']),entry_year))
            for g in groups(item['files'],kind):
                matches=matching_files(g['files'],aliases,kind=kind,
                              year=entry_year if kind=='movie' else None)
                if not matches:
                    continue
                dedupe=(normalize(g['title']),g.get('year') if kind=='movie' else '')
                if dedupe in seen_groups[kind]:
                    continue
                seen_groups[kind].add(dedupe)
                g['files']=matches
                g['best']=matches[0]
                g['seed_title']=item['title']
                g['seed_original']=item['original']
                g['feed_meta']=feed_meta
                if kind=='show':
                    g['year']=str(entry_year)
                raw[kind].append(g)
        # Availability checks are bounded, still never show stale positives
        # unless Webshare's existence endpoint confirms one file.
        movies=verified_groups(raw['movie'],self.availability,maximum=48,checked=85)
        shows=verified_groups(raw['show'],self.availability,maximum=32,checked=55)
        for listing,budget in ((movies,15),(shows,8)):
            for index,g in enumerate(listing):
                data=None
                if self.metadata and index<budget:
                    data=self.metadata.lookup(g['seed_title'],
                            str(g['year']) if g['kind']=='movie' else '')
                    if not data:
                        data=self.metadata.lookup(g['seed_original'])
                if not data:
                    feed=g.get('feed_meta') or {}
                    if feed:
                        data={'title':feed.get('name') or g['seed_title'],
                              'original':feed.get('original') or g['seed_original'],
                              'year':str(feed.get('year') or g['year']),
                              'poster':feed.get('poster') or '',
                              'fanart':feed.get('background') or '',
                              'plot':feed.get('plot') or '',
                              'genres':feed.get('genres') or [],
                              'rating':feed.get('imdb_rating'),
                              'rating_source':'IMDb'}
                    else:
                        data=localized_title(g['title'],g['kind'],g.get('year'))
                        if not data:
                            data={'title':g['seed_title'],
                                  'original':g['seed_original'],
                                  'year':str(g['year'])}
                g['metadata']=data
        if self.metadata:
            self.metadata.save()
        return ([self._decorate(g,g.get('metadata')) for g in movies],
                [self._decorate(g,g.get('metadata')) for g in shows])

    @staticmethod
    def _add_ranked_shelves(home):
        """One verified card per title, with all its available file variants."""
        from cinema_rankings import create_shelves
        unify_sections(home)
        movies=consolidate((home.get('premieres') or [])+
                           (home.get('movies') or [])+
                           (home.get('classics') or []))
        shows=consolidate((home.get('shows') or [])+
                          (home.get('classic_shows') or []))
        # These unallocated lists power full Filmy / Seriály browsing.
        home['_all_movies']=movies
        home['_all_shows']=shows
        home['_all_premieres']=list(home.get('premieres') or [])
        home.update(create_shelves(movies,shows))
        unique_home_rails(home)
        home['_dedupe_v1']=True
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
                    cached['home'].get('_dedupe_v1') is True):
                    self.home_cache=cached['home']
                    self.last_diagnostics='Katalog načten z ověřené 8minutové mezipaměti'
                    return self.home_cache
            except (OSError,ValueError,TypeError):
                pass
        premieres=self._premieres(9)
        recent,shows=self._from_webshare()
        classics,classic_shows=self._discover_hits()
        if self.feed is not None:
            try:
                counts=self.feed.sizes()
                self.last_diagnostics+=(' · Databáze kandidátů: %d filmů, %d seriálů' %
                    (counts['movie'],counts['show']))
            except (KeyError,TypeError,AttributeError):
                pass
        seen={normalize(c['raw']) for c in premieres}
        additional=[c for c in recent if normalize(c['raw']) not in seen]
        self.home_cache=self._add_ranked_shelves({
            'premieres':premieres,
            'movies':additional or recent,
            'shows':shows,
            'classics':classics,
            'classic_shows':classic_shows,
            'feed_v4':True
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
        home=self.home()
        source=(home.get('_all_premieres',[]) if view=='premieres'
                else home.get('_all_shows',[]) if view=='shows'
                else home.get('_all_movies',[]))
        filtered=[c for c in source if choose_files(c.get('files',[]),
                                                    quality,language)]
        return sort_cards(consolidate(filtered),sort)

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
        combined=consolidate(combined)
        combined.sort(key=lambda c:(0 if normalize(c['raw'])==key else 1,
                      normalize(c['title']),str(c.get('year') or '')))
        self.search_cache[key]=combined
        return [c for c in combined if kind=='all' or c['kind']==kind]

    def files(self, card, quality='all', language='all'):
        # On title selection, find ALL variants of the movie; broad discovery
        # typically discovers only one copy of each quality.
        candidates=list(card.get('files') or [])
        aliases=list(dict.fromkeys([card.get('raw') or '',
                    card.get('original') or '']+list(card.get('aliases') or [])))
        for name in aliases[:5]:
            if name:
                fetched=collect_pages(self.fetch,self.token,name,max_pages=4)
                if fetched:
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
            aliases=list(card.get('aliases') or [])
            if original:
                aliases.append(original)
            self.series_cache[key]=grouped_episodes(entries+existing,raw,
                aliases=tuple(aliases))
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
