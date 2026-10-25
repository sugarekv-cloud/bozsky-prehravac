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
import threading
from cinema_catalog_v2 import (groups,verified_groups,add_metadata,card,
    sort_cards,grouped_episodes,choose_files,collect_pages,matching_release)
from cinematic_discovery import discover
from novinky_catalogue import normalize, parse_video_name
from catalog_engine import file_label
from cinema_dedupe import (consolidate, unify_sections, unique_home_rails,
                           identity)
from cinema_search_v3 import (MOVIE_SEEDS, SHOW_SEEDS, candidate_names,
                              query_plan, matching_files, seed_batch, localized_title,
                               title_and_year)


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
        self._most_watched_cards=[]
        self._most_watched_idents=set()
        self._most_watched_source=0
        self._most_watched_offset=0
        self._most_watched_done=False
        self._browse_streams={}
        self._show_popularity={'cards':[],'idents':set(),'source':0,'offset':0,'done':False}
        self._background_done=threading.Event()
        self._background_started=False
        self._background_result=None
        self._snapshot_age=None
        self.tips_path=os.path.join(profile,'cinema-v2-verified-tips.json') if profile else None
        self._tips_cards=[]
        self._tips_saved=0
        self._tips_loading=False
        self._tips_done=threading.Event()
        self._tips_result=None
        self._tips_last_try=0
        if self.tips_path:
            try:
                with io.open(self.tips_path,'r',encoding='utf8') as file:
                    saved=json.load(file)
                if isinstance(saved,dict) and isinstance(saved.get('cards'),list):
                    self._tips_cards=consolidate(saved['cards'])[:150]
                    self._tips_saved=float(saved.get('saved') or 0)
            except (OSError,TypeError,ValueError):
                pass

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
        movies=verified_groups(movies,self.availability,maximum=45,checked=95)
        shows=verified_groups(shows,self.availability,maximum=38,checked=95)
        add_metadata(movies,self.metadata,maximum=22)
        add_metadata(shows,self.metadata,maximum=22)
        self.last_diagnostics=('Webshare dotazy: %d, videosoubory: %d, '
            'ověřené filmy: %d, seriály: %d' %
            (stats['queries'],stats['video_files'],len(movies),len(shows)))
        return ([self._decorate(g,g.get('metadata')) for g in movies],
                [self._decorate(g,g.get('metadata')) for g in shows])

    def refresh_catalogue(self):
        """Explicit user-triggered refresh; never runs in the background."""
        self._browse_streams={}
        self._show_popularity={'cards':[],'idents':set(),'source':0,'offset':0,'done':False}
        self._background_result=None
        self._background_done.clear()
        self._background_started=False
        self._most_watched_cards=[]
        self._most_watched_idents=set()
        self._most_watched_source=0
        self._most_watched_offset=0
        self._most_watched_done=False
        self.home_cache=None
        self.search_cache.clear()
        self._feed_force=True
        if self.cache_path:
            try:
                os.remove(self.cache_path)
            except OSError:
                pass

    def _discover_hits(self, movie_batch=18, show_batch=10):
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
        # Keep a single group per canonical film, but accumulate ALL quality
        # alternatives from different seeds and search-result pages.
        seen_groups={'movie':{},'show':{}}
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
                g['files']=matches
                g['best']=matches[0]
                g['seed_title']=item['title']
                g['seed_original']=item['original']
                g['feed_meta']=feed_meta
                if kind=='show':
                    g['year']=str(entry_year)
                dedupe=identity({'kind':kind,'raw':g['title'],
                    'title':item['title'],'original':item['original'],
                    'year':g.get('year') or str(entry_year)})
                previous=seen_groups[kind].get(dedupe)
                if previous is not None:
                    for f in matches:
                        if f.get('ident') not in {v.get('ident') for v in previous['files']}:
                            previous['files'].append(f)
                            from catalog_engine import file_score
                            if file_score(f)>file_score(previous['best']):
                                previous['best']=f
                    if not previous.get('feed_meta') and feed_meta:
                        previous['feed_meta']=feed_meta
                else:
                    seen_groups[kind][dedupe]=g
                    raw[kind].append(g)
        # Availability checks are bounded, still never show stale positives
        # unless Webshare's existence endpoint confirms one file.
        movies=verified_groups(raw['movie'],self.availability,maximum=110,checked=180)
        shows=verified_groups(raw['show'],self.availability,maximum=90,checked=150)
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

    def home(self, force=False):
        if self.home_cache is not None and not force:
            return self.home_cache
        # The short cache avoids repeating expensive ČSFD/Webshare calls
        # every time the user returns to the television home screen.
        if self.cache_path and not force:
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

    def home_fast(self):
        """Network-free verified homepage; even an expired snapshot displays."""
        if self.home_cache is not None:
            return self.home_cache
        if self.cache_path:
            try:
                with io.open(self.cache_path,'r',encoding='utf8') as handle:
                    payload=json.load(handle)
                home=payload.get('home')
                if isinstance(home,dict) and home.get('_dedupe_v1') is True:
                    self._snapshot_age=max(0,time.time()-float(payload.get('saved') or 0))
                    self.home_cache=home
                    self.last_diagnostics='Mezipaměť · kontrola novinek na pozadí'
                    return home
            except (OSError,ValueError,TypeError,AttributeError):
                pass
        self._snapshot_age=None
        self.last_diagnostics='První katalog se připravuje na pozadí'
        return {'premieres':[],'movies':[],'shows':[],'classics':[],
                'classic_shows':[],'_all_movies':[],'_all_shows':[],
                'best_movies_year':[],'best_shows_all':[],'best_shows_year':[]}

    def start_home_refresh(self, force=False):
        """Refresh Webshare outside the GUI; explicit retry may restart a finished worker."""
        if not self.token:
            return False
        if force and self._background_started and self._background_done.is_set():
            self.take_home_refresh()
            self._background_started=False
        if self._background_started:
            return False
        if (not force and self._snapshot_age is not None and self._snapshot_age<480
                and self.home_cache is not None):
            return False
        self._background_started=True
        self._background_done.clear()
        def worker():
            try:
                profile=os.path.dirname(self.cache_path) if self.cache_path else None
                clone=CinemaService(self.token,self.fetch,self.availability,
                                    self.metadata,self.calendar,profile)
                # One metadata/discovery pass only: no expensive popularity
                # searches blocking the requested ČSFD-first experience.
                home=clone.home(force=True)
                if clone.cache_path and (home.get('_all_movies') or home.get('_all_shows')):
                    with io.open(clone.cache_path+'.tmp','w',encoding='utf8') as out:
                        json.dump({'saved':time.time(),'home':home},out,ensure_ascii=False)
                    os.replace(clone.cache_path+'.tmp',clone.cache_path)
                self._background_result=home
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                self._background_done.set()
        threading.Thread(target=worker,name='fckyo-home-refresh',daemon=True).start()
        return True

    def take_home_refresh(self):
        """Consume a completed snapshot only on the UI thread."""
        if not self._background_done.is_set():
            return None
        self._background_done.clear()
        result=self._background_result
        self._background_result=None
        if result:
            self.home_cache=result
            self._snapshot_age=0
            self.last_diagnostics='Katalog aktualizován na pozadí'
        else:
            self.last_diagnostics='Katalog se nepodařilo obnovit – opakuj pokus v nabídce Tipy'
        return result

    def tips_snapshot(self, home=None):
        """Merge real verified film cards from home + persisted independent tips.

        No requests, no unverified metadata-only suggestions on Kodi GUI thread.
        """
        base=home if isinstance(home,dict) else self.home_fast()
        result=dict(base)
        cards=consolidate(self._tips_cards)
        if cards:
            result['_all_movies']=consolidate(
                (base.get('_all_movies') or [])+
                (base.get('movies') or [])+
                [c for c in cards if c.get('kind')=='movie'])
            result['_all_shows']=consolidate(
                (base.get('_all_shows') or [])+
                (base.get('shows') or [])+
                [c for c in cards if c.get('kind')=='show'])
        return result

    def start_tips_refresh(self,force=False):
        """Expand discoverable recommendations in a single worker, not GUI thread."""
        if not self.token or self._tips_loading:
            return False
        now=time.time()
        if not force and self._tips_cards and now-self._tips_saved<12*3600:
            return False
        if not force and now-self._tips_last_try<120:
            return False
        self._tips_last_try=now
        self._tips_loading=True
        self._tips_done.clear()
        self._tips_result=None

        def worker():
            try:
                profile=os.path.dirname(self.cache_path) if self.cache_path else None
                clone=CinemaService(self.token,self.fetch,self.availability,
                                    self.metadata,self.calendar,profile)
                # These are real, availability-verified Webshare groups. The
                # full_catalog method is bounded to four new search pages.
                movies,_=clone.full_catalog('movie',80)
                shows,_=clone.full_catalog('show',45)
                result=consolidate((movies or [])+(shows or []))
                if result:
                    if self.tips_path:
                        tmp=self.tips_path+'.tmp'
                        with io.open(tmp,'w',encoding='utf8') as file:
                            json.dump({'saved':time.time(),'cards':result[:150]},
                                      file,ensure_ascii=False)
                        os.replace(tmp,self.tips_path)
                    self._tips_result=result[:150]
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                self._tips_loading=False
                self._tips_done.set()
        threading.Thread(target=worker,name='kivora-verified-tips',daemon=True).start()
        return True

    def take_tips_refresh(self):
        if not self._tips_done.is_set():
            return None
        self._tips_done.clear()
        cards=self._tips_result
        self._tips_result=None
        if cards:
            self._tips_cards=consolidate(cards)
            self._tips_saved=time.time()
            self.last_diagnostics='Nové tipy z ověřeného katalogu jsou připraveny'
        return cards

    def most_watched_shows(self, count=24, quality='all', language='all'):
        """Popular Webshare series by file-rating search, not ČSFD ranking."""
        state=getattr(self,'_show_popularity',None)
        if state is None:
            state={'cards':[],'idents':set(),'source':0,'offset':0,'done':False}
            self._show_popularity=state
        queries=('S01E','S02E','S03E','S01','S02','1080p','720p')
        wanted=max(1,int(count))
        def eligible():
            return [c for c in state['cards']
                    if choose_files(c.get('files') or [],quality,language)]
        pages=0
        while len(eligible())<wanted and not state['done'] and pages<2:
            if state['source']>=len(queries):
                state['done']=True
                break
            try:
                files,total=self.fetch(self.token,state['offset'],
                                       queries[state['source']],sort='rating')
            except Exception:
                break
            if not isinstance(files,list):
                break
            pages+=1
            state['offset']+=100
            try:
                end=len(files)<100 or (bool(total) and state['offset']>=int(total))
            except (TypeError,ValueError):
                end=len(files)<100
            if end:
                state['source']+=1
                state['offset']=0
                state['done']=state['source']>=len(queries)
            distinct=[]
            for file in files:
                if not isinstance(file,dict) or not file.get('ident'):
                    continue
                key=str(file['ident'])
                if key not in state['idents']:
                    state['idents'].add(key)
                    distinct.append(file)
            candidates=groups(distinct,'show')
            if not candidates:
                continue
            valid=verified_groups(candidates,self.availability,maximum=35,checked=75)
            add_metadata(valid,self.metadata,maximum=12)
            cards=[self._decorate(g,g.get('metadata')) for g in valid]
            state['cards']=consolidate(state['cards']+cards)
        return eligible()[:wanted]

    def most_watched_has_more(self):
        """Whether another page of Webshare popularity results may exist."""
        return not self._most_watched_done

    def most_watched_movies(self, count=24, quality='all', language='all'):
        """Load checked movies progressively in Webshare's rating search order.

        This is a popularity proxy, not a measured view-count ranking.
        Never search with an empty term, and never fetch the whole index at once.
        """
        terms=('1080p','720p','2160p','DVDRip','WEB-DL')
        wanted=max(1,int(count))
        def filtered():
            return [c for c in self._most_watched_cards if
                    choose_files(c.get('files') or [],quality,language)]
        pages=0
        while (len(filtered())<wanted and not self._most_watched_done
               and pages<2):
            if self._most_watched_source>=len(terms):
                self._most_watched_done=True
                break
            term=terms[self._most_watched_source]
            try:
                files,total=self.fetch(self.token,self._most_watched_offset,
                                       term,sort='rating')
            except Exception:
                # Retry on the next explicit '+' click after an API failure.
                break
            if files is None or not isinstance(files,list):
                break
            pages+=1
            self._most_watched_offset+=100
            last_page=len(files)<100
            try:
                last_page=last_page or (bool(total) and
                    self._most_watched_offset>=int(total))
            except (ValueError,TypeError):
                pass
            if last_page:
                self._most_watched_source+=1
                self._most_watched_offset=0
                if self._most_watched_source>=len(terms):
                    self._most_watched_done=True
            distinct=[]
            for f in files:
                if not isinstance(f,dict) or not f.get('ident'):
                    continue
                ident=str(f['ident'])
                if ident not in self._most_watched_idents:
                    self._most_watched_idents.add(ident)
                    distinct.append(f)
            candidates=groups(distinct,'movie')
            if not candidates:
                continue
            verified=verified_groups(candidates,self.availability,
                                     maximum=48,checked=85)
            add_metadata(verified,self.metadata,maximum=16)
            cards=[self._decorate(group,group.get('metadata'))
                   for group in verified]
            # Keep original popularity order; combine quality and CZ/EN copies.
            self._most_watched_cards=consolidate(
                self._most_watched_cards+cards)
        return filtered()[:wanted]

    # Small predictable batches: using a nonempty filename query is required
    # by Webshare's search API. These are discovery queries, not a claim that
    # Webshare exposes an exhaustive movie/series database.
    FULL_CATALOG_QUERIES={
        'movie':(('1080p','rating'),('2160p','rating'),
                 ('720p','rating'),('WEB-DL','recent'),
                 ('BluRay','rating'),('2026','recent'),
                 ('2025','recent'),('2024','recent'),
                 ('DVDRip','rating')),
        'show':(('S01E','rating'),('S02E','rating'),
                ('S03E','recent'),('S04E','recent'),
                ('S01','recent'),('S02','recent'),
                ('1080p','rating'),('2026','recent'),
                ('2025','recent')),
    }

    def full_catalog(self, kind, requested=24, sort='date',
                     quality='all', language='all'):
        """On-demand verified film/series discovery, never a bulk preload.

        The cursor is independent per kind. Deduplicating by file ID before
        verifying and by film identity after verifying retains quality variants
        while keeping remakes distinct. A request fetches at most four pages.
        """
        if kind not in ('movie','show'):
            raise ValueError('Unsupported catalogue kind')
        wanted=max(1,min(int(requested),1500))
        if kind not in self._browse_streams:
            home=self.home()
            originals=(home.get('_all_movies') if kind=='movie'
                       else home.get('_all_shows')) or []
            # Seed with previously verified on-screen results at zero API cost.
            cards=consolidate(originals)
            self._browse_streams[kind]={
                'cards':cards,
                'idents':{str(f['ident']) for c in cards
                          for f in (c.get('files') or []) if f.get('ident')},
                'source':0,'offset':0,'done':False}
        stream=self._browse_streams[kind]
        queries=self.FULL_CATALOG_QUERIES[kind]

        def filtered():
            return [c for c in stream['cards']
                    if choose_files(c.get('files') or [],quality,language)]

        pages=0
        while len(filtered())<wanted and not stream['done'] and pages<4:
            if stream['source']>=len(queries):
                stream['done']=True
                break
            query,order=queries[stream['source']]
            try:
                files,total=self.fetch(self.token,stream['offset'],
                                       query,sort=order)
            except Exception:
                # Retry the SAME page next time; no accidental cursor advance.
                break
            if not isinstance(files,list):
                break
            pages+=1
            stream['offset']+=100
            try:
                end_of_query=(len(files)<100 or
                              bool(total) and stream['offset']>=int(total))
            except (TypeError,ValueError):
                end_of_query=(len(files)<100)
            if end_of_query:
                stream['source']+=1
                stream['offset']=0
                stream['done']=stream['source']>=len(queries)
            new=[]
            for file in files:
                if not isinstance(file,dict) or not file.get('ident'):
                    continue
                ident=str(file['ident'])
                if ident not in stream['idents']:
                    stream['idents'].add(ident)
                    new.append(file)
            candidates=groups(new,kind)
            if not candidates:
                continue
            # Confirm real files, never build a poster from metadata alone.
            checked=verified_groups(candidates,self.availability,
                                    maximum=48,checked=100)
            add_metadata(checked,self.metadata,maximum=12)
            # Limit slow external poster/ČSFD lookups to the first 12 per page;
            # all remaining verified files still appear immediately.
            additions=[self._decorate(g,g.get('metadata'))
                       if index<12 else card(g)
                       for index,g in enumerate(checked)]
            if additions:
                stream['cards']=consolidate(stream['cards']+additions)
            if len(stream['cards'])>=1500:
                stream['done']=True
        return (sort_cards(filtered(),sort)[:wanted],
                not stream['done'])

    def browse(self, view, sort='date', quality='all', language='all'):
        home=self.home()
        source=(home.get('_all_premieres',[]) if view=='premieres'
                else home.get('_all_shows',[]) if view=='shows'
                else home.get('_all_movies',[]))
        filtered=[c for c in source if choose_files(c.get('files',[]),
                                                    quality,language)]
        return sort_cards(consolidate(filtered),sort)

    def search(self, query, kind='all'):
        """Search both localized and original filenames, including older pages.

        A film can only appear after Webshare returned a matching file and the
        availability checker validated it. No metadata-only 'ghost' posters.
        """
        term=(query or '').strip()
        if not term:
            return []
        title,requested_year=title_and_year(term)
        key=normalize(term)
        if key in self.search_cache:
            cards=self.search_cache[key]
            return [c for c in cards if kind=='all' or c['kind']==kind]
        md=self.metadata.lookup(title,requested_year) if self.metadata else None
        from cinema_search_v3 import cached_title_aliases
        names=candidate_names(title,md)
        cached_aliases=cached_title_aliases(title,self.home_fast())
        names=list(dict.fromkeys(names+cached_aliases))
        plan=query_plan(title,md,limit=22)
        # Verified catalogue aliases enter early, ahead of punctuation variants.
        plan=list(dict.fromkeys(plan[:1]+cached_aliases+plan[1:]))[:24]
        matches={}
        # Ensure the English alias and individual franchise installments are
        # considered before giving attention to punctuation/spelling variants.
        core_count=min(len(names),len(plan))
        successful=0
        for index,attempt in enumerate(plan):
            # Scan beyond the first 100 broad Webshare hits to avoid a search
            # dominated by unrelated filenames or different resolutions.
            max_pages=4 if index==0 else 3 if index<core_count else 1
            page=collect_pages(self.fetch,self.token,attempt,
                               max_pages=max_pages,
                               sort='rating' if index<core_count else 'recent')
            if page is None:
                continue
            valid=matching_files(page,names,kind=None,year=requested_year)
            if requested_year:
                # Explicitly selecting a release year must not silently
                # attach an undated remake to another movie.
                valid=[f for f in valid if
                       (parse_video_name(f.get('name') or '') or {}).get('year')
                       ==requested_year]
            for entry in valid:
                matches[str(entry['ident'])]=entry
            if valid:
                successful+=1
            # Always attempt every core alias when feasible. For a generic
            # query, cap expensive round trips once plenty of releases exist.
            if len(matches)>=180:
                break
            if index>=min(core_count-1,12) and successful>=4 and len(matches)>=80:
                break
        combined=[]
        for mode in ('movie','show'):
            if kind in ('movie','show') and kind!=mode:
                continue
            candidates=groups(list(matches.values()),mode)
            candidates=verified_groups(candidates,self.availability,
                                       maximum=60,checked=120)
            add_metadata(candidates,self.metadata,maximum=25)
            for group in candidates:
                # A metadata match for Avengers (2012) must never relabel
                # Avengers: Endgame (2019) as the earlier release.
                if md and normalize(group['title']) in {normalize(n) for n in names}:
                    if (not group['year'] or not md.get('year') or
                            str(group['year'])==str(md['year'])):
                        group['metadata']=md
                if not group.get('metadata'):
                    group['metadata']=localized_title(
                        group['title'],mode,group.get('year'))
                combined.append(self._decorate(group,group.get('metadata')))
        combined=consolidate(combined)
        targets={normalize(x) for x in names}
        def rank(card):
            raw=normalize(card.get('raw') or '')
            original=normalize(card.get('original') or '')
            displayed=normalize(card.get('title') or '')
            exact=raw in targets or original in targets or displayed in targets
            specific=raw==normalize(title) or displayed==normalize(title)
            year_match=bool(requested_year and
                            str(card.get('file_year') or card.get('year') or '')
                            ==requested_year)
            try:
                rating=float(card.get('rating') or 0)
            except (ValueError,TypeError):
                rating=0
            return (0 if specific else 1,0 if exact else 1,
                    0 if year_match else 1,
                    -rating,displayed,str(card.get('year') or ''))
        combined.sort(key=rank)
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
