# -*- coding: utf-8 -*-
"""Kodi-only TV navigator. All browsing lives in one WindowXMLDialog.

Settings stay inside the movie UI; only playing a selected file leaves it. Content lists are populated from real, availability-checked files.
"""
import os
import traceback
import xbmcgui
import xbmc

TOP_ACTIONS={
    106:'home',101:'movies',102:'shows',103:'search',104:'premieres',
    105:'genres',107:'settings',
    201:'home',202:'continue',203:'favorites',204:'genres',
    205:'csfd_ranked',206:'premieres',207:'settings',208:'recommendations'
}
BACK_ACTIONS=(9,10,92,216)
ROW_IDS=tuple(range(401,414))
VERSION='0.32.0'


def tile(name,kind,**extra):
    entry={'title':name,'kind':kind,'poster':'','fanart':'',
           'plot':'','year':'','genre':'','rating':None,'quality':'','files':[]}
    entry.update(extra)
    return entry


class CinemaScreen(xbmcgui.WindowXMLDialog):
    def onInit(self):
        self.stack=[]
        self.mode='home'
        self.context=None
        self.rail_items=[[] for _ in ROW_IDS]
        self.popular_limit=24
        self.catalog_limit=24
        self.genre_limits={'movie':24,'show':24}
        self.featured_card=None
        self._updating_home=False
        self._switching_section=False
        self._nav_focus_target=None
        try:
            # Tracked by the playback service: retain the original screen
            # underneath fullscreen playback whenever Kodi permits it.
            xbmcgui.Window(10000).setProperty('kivora_window_open','yes')
        except (RuntimeError,AttributeError,TypeError):
            pass
        for name,path in self.textures.items():
            self.setProperty('cinema_'+name,path)
        self.setProperty('cinema_brand',getattr(self,'brand_path',''))
        for cid,icon_path in getattr(self,'icon_paths',{}).items():
            self.setProperty('side_icon_'+str(cid),icon_path)
        self.setProperty('app_version','v'+VERSION)
        self.setProperty('section_label','ÚVOD')
        self.setProperty('ui_status','Šipky = pohyb, OK = výběr, Zpět = předchozí obrazovka')
        self.setProperty('hero_title','KIVORA')
        self.setProperty('hero_info','Katalog ověřených souborů Webshare')
        self.setProperty('hero_plot','Nové filmy podle českých kinopremiér a jejich dostupnosti.')
        self.setProperty('hero_art','')
        self.setProperty('hero_poster','')
        self.setProperty('hero_action','')
        try:
            self._screen('home',stack=False)
        except Exception:
            traceback.print_exc()
            self._fill('ZAČNĚTE VYHLEDÁVÁNÍM',[
                tile('HLEDAT FILM / SERIÁL','search'),
                tile('NASTAVENÍ WEBSHARE','settings'),
            ],'DALŠÍ MOŽNOSTI',[], 'Webshare či ČSFD nyní neodpovídá.')

    def _loading(self,text):
        d=xbmcgui.DialogProgress()
        d.create('KIVORA',text)
        return d

    def _fill(self,title1,cards1,title2,cards2,status='',extra_rows=()):
        rows=[(title1,cards1),(title2,cards2)]+list(extra_rows)
        while len(rows)<len(ROW_IDS):
            rows.append(('',[]))
        self.rail_items=[cards or [] for heading,cards in rows[:len(ROW_IDS)]]
        for index,(heading,cards) in enumerate(rows[:len(ROW_IDS)]):
            self.setProperty('row%d_heading'%(index+1),heading if cards else '')
        self.setProperty('ui_status',status or
            ('KIVORA '+VERSION+' · pouze tituly dostupné na Webshare'))
        for i,control_id in enumerate(ROW_IDS):
            lst=self.getControl(control_id)
            lst.reset()
            li=[]
            for c in self.rail_items[i]:
                item=xbmcgui.ListItem(label=str(c.get('title') or 'Bez názvu'))
                art={}
                if c.get('poster'):
                    art['poster']=c['poster']
                if c.get('fanart'):
                    art['fanart']=c['fanart']
                if c.get('fanart') or c.get('poster'):
                    art['thumb']=c.get('fanart') or c.get('poster')
                # Preserve art provenance: display portrait covers contained,
                # while only proper wide backdrops are cropped to landscape.
                item_fanart=c.get('fanart') or ''
                if art:
                    item.setArt(art)
                item.setProperty('has_poster','yes' if c.get('poster') else '')
                item.setProperty('has_fanart','yes' if item_fanart else '')
                item.setProperty('is_more','yes' if c.get('kind') in ('most_watched','load_more','catalog_open','catalog_more','csfd_ranked','tips_retry') else '')
                item.setProperty('quality',str(c.get('quality') or ''))
                item.setProperty('year',str(c.get('year') or ''))
                item.setProperty('progress',str(c.get('progress') or '0'))
                item.setProperty('is_resume','yes' if c.get('_continue') else '')
                source=str(c.get('rating_source') or '').casefold()
                try:
                    label='ČSFD %d %%'%round(float(c.get('rating'))) if source in ('čsfd','csfd','czdb') else ''
                except (ValueError,TypeError):
                    label=''
                item.setProperty('rating_label',str(c.get('_tip') or label))
                li.append(item)
            if li:
                lst.addItems(li)
        # A header selection must remain focused after the rail redraw.
        # Previous implementation jumped to the first poster every time.
        focus_target=getattr(self,'_nav_focus_target',None)
        self._nav_focus_target=None
        if focus_target not in TOP_ACTIONS:
            focus_target=next((rid for rid,cards in zip(ROW_IDS,self.rail_items)
                               if cards),107)
        try:
            self.setFocusId(focus_target)
        except (RuntimeError,AttributeError):
            pass
        self._update_hero()

    def _selected(self,control_id=None):
        try:
            ident=control_id or self.getFocusId()
            if ident not in ROW_IDS:
                return None
            row=ROW_IDS.index(ident)
            position=self.getControl(ident).getSelectedPosition()
            if position<0:
                return None
            return self.rail_items[row][position]
        except (RuntimeError,IndexError,AttributeError):
            return None

    def _update_hero(self):
        c=self._selected()
        mode=getattr(self,'mode',None)
        wanted={'movies':'movie','shows':'show','premieres':'movie'}.get(mode)
        if not c and self.getFocusId() not in ROW_IDS:
            # Preserve an existing in-section banner while navigating menus.
            c=self.featured_card
        if c and wanted and c.get('kind')!=wanted:
            c=None
        if (not c or c.get('kind') not in ('movie','show')) and mode in (
                'home','recommendations','movies','shows','premieres'):
            c=next((card for row in getattr(self,'rail_items',[])
                    for card in row if card.get('kind') in ('movie','show')
                    and (not wanted or card.get('kind')==wanted)
                    and (card.get('fanart') or card.get('poster'))),None)
        if not c:
            self.featured_card=None
            self.setProperty('hero_title',{'shows':'SERIÁLY','movies':'FILMY',
                                          'premieres':'PREMIÉRY'}.get(mode,'KIVORA'))
            self.setProperty('hero_info','TVŮJ FILMOVÝ SVĚT · FILMY · SERIÁLY')
            self.setProperty('hero_plot','Objev film nebo seriál, vyber žánr nebo otevři Tipy.')
            self.setProperty('hero_art','')
            self.setProperty('hero_poster','')
            self.setProperty('hero_action','')
            return
        if c.get('kind') in ('movie','show'):
            self.featured_card=c
            self.setProperty('hero_action','yes')
        else:
            self.featured_card=None
            self.setProperty('hero_action','')
        self.setProperty('hero_title',str(c.get('title') or ''))
        genre=str(c.get('genre') or '').split(',')[:2]
        text=[str(c.get('year') or ''),', '.join(x.strip() for x in genre if x.strip())]
        source=str(c.get('rating_source') or '').casefold()
        if source in ('čsfd','csfd','czdb') and c.get('rating') is not None:
            try:
                text.append('ČSFD %d %%'%round(float(c['rating'])))
            except (ValueError,TypeError):
                pass
        self.setProperty('hero_info','  ·  '.join(x for x in text if x)[:115])
        self.setProperty('hero_plot',str(c.get('plot') or '')[:330])
        # Never stretch a vertical, low-res Webshare poster across the TV hero.
        self.setProperty('hero_art',str(c.get('fanart') or ''))
        self.setProperty('hero_poster',str(c.get('poster') or ''))

    def _refresh(self,view,context=None,stack=True):
        if stack:
            focus=None
            index=0
            try:
                focus=self.getFocusId()
                if focus in ROW_IDS:
                    index=max(0,self.getControl(focus).getSelectedPosition())
            except (RuntimeError,AttributeError):
                pass
            self.stack.append((self.mode,self.context,focus,index))
        self._screen(view,context,stack=False)

    @staticmethod
    def _catalog_problem(stage,exc):
        """Errors remain visible in the Kodi log, not silently stale on TV."""
        try:
            xbmc.log('KIVORA catalogue %s: %s: %s'%(stage,
                     type(exc).__name__,str(exc)),xbmc.LOGERROR)
        except (AttributeError,RuntimeError):
            pass

    def _home_catalogue(self):
        """Always deliver a typed, local, verified shelf map without network IO."""
        default={'_all_movies':[],'_all_shows':[],
                 'movies':[],'shows':[],'premieres':[],'classics':[],
                 'classic_shows':[]}
        try:
            source=self.service.home_fast()
            if not isinstance(source,dict):
                source={}
            home=dict(default,**source)
        except Exception as exc:
            self._catalog_problem('home snapshot',exc)
            home=dict(default)
        try:
            supplement=getattr(self.service,'tips_snapshot',None)
            if callable(supplement):
                merged=supplement(home)
                if isinstance(merged,dict):
                    home=merged
        except Exception as exc:
            self._catalog_problem('tips snapshot',exc)
        # Old caches sometimes only had "movies"/"shows", not _all_*.
        from cinema_dedupe import consolidate
        for kind,keys in (('movie',('_all_movies','movies','premieres','classics')),
                          ('show',('_all_shows','shows','classic_shows'))):
            found=[]
            for key in keys:
                found.extend([c for c in (home.get(key) or [])
                              if isinstance(c,dict) and c.get('kind')==kind
                              and c.get('ident') and c.get('files')])
            home[keys[0]]=consolidate(found)
        return home

    def _home_tips(self,home,store,limit=24):
        """Actual available movies, including rewatchable titles when needed."""
        from cinema_recommendations import recommendations
        films=(home.get('_all_movies') or [])+(home.get('_all_shows') or [])
        try:
            chosen,weekly=recommendations(home,store,limit=limit)
        except Exception as exc:
            self._catalog_problem('recommendations',exc)
            chosen,weekly=[],[]
        def fill(base,tag):
            from cinema_dedupe import consolidate,identity
            good=[c for c in base if isinstance(c,dict) and c.get('kind') in ('movie','show')
                  and c.get('ident') and c.get('files')]
            seen={identity(c) for c in good}
            for c in films:
                if (isinstance(c,dict) and c.get('kind') in ('movie','show')
                    and c.get('ident') and c.get('files') and identity(c) not in seen):
                    good.append(c)
                    seen.add(identity(c))
                if len(good)>=limit:break
            return [dict(c,_tip=tag) for c in consolidate(good)[:limit]]
        return fill(chosen,'TIP PRO TEBE'),fill(weekly,'TIP TÝDNE')

    def _schedule_home_discovery(self):
        # First paint always wins. A broken provider must not blank the UI.
        for name in ('start_home_refresh','start_tips_refresh'):
            try:
                callback=getattr(self.service,name,None)
                if callable(callback):
                    callback()
            except Exception as exc:
                self._catalog_problem(name,exc)

    def _render_primary_section(self,view):
        """Atomic, kind-strict TV shelf renderer for top menu tabs.

        Fetching, metadata enrichment and recommendations must not prevent a
        new tab from displaying. Only previously verified files are shown.
        """
        kind='show' if view=='shows' else 'movie'
        empty={'_all_movies':[],'_all_shows':[],'_all_premieres':[]}
        try:
            home=self.service.home_fast() or empty
            if not isinstance(home,dict):
                home=empty
        except Exception as exc:
            self._catalog_problem('home_fast',exc)
            home=empty
        try:
            available=self.service.browse(view,self.sort,
                                          self.quality,self.language)
        except Exception as exc:
            self._catalog_problem('browse '+view,exc)
            key=('_all_shows' if view=='shows' else
                 '_all_premieres' if view=='premieres' else '_all_movies')
            available=home.get(key) or []
        # The cache is not an authoritative source of classification; ensure
        # a movies shelf can never appear under the SERIÁLY tab.
        items=[c for c in (available or []) if isinstance(c,dict)
               and c.get('kind')==kind and c.get('ident') and c.get('files')]
        try:
            items=self._filtered(items)
        except Exception as exc:
            self._catalog_problem('filters '+view,exc)
            # Prefer at least verified results to an empty/stale screen.
        if view=='premieres':
            self._fill('FILMOVÉ PREMIÉRY',items[:24] or [
                       tile('PREMIÉRY SE AKTUALIZUJÍ','none')],
                       'DALŠÍ PREMIÉRY',items[24:48],
                       'Premiéry z ověřeného katalogu Webshare')
            return
        from cinema_rankings import csfd_only
        key='_all_shows' if view=='shows' else '_all_movies'
        try:
            ranked=csfd_only(home.get(key) or [],kind,limit=40)
        except Exception as exc:
            self._catalog_problem('csfd '+view,exc)
            ranked=[]
        prefix='SERIÁLY' if kind=='show' else 'FILMY'
        headline='NEJLÉPE HODNOCENÉ '+prefix+' · ČSFD'
        ranked=[c for c in ranked if isinstance(c,dict)
                and c.get('kind')==kind and c.get('ident') and c.get('files')]
        primary=ranked[:24]
        if primary:
            primary.append(tile('+ CELÝ ŽEBŘÍČEK ČSFD','csfd_ranked',
                                catalog_kind=kind))
        else:
            primary=[tile('ŽEBŘÍČEK ČSFD SE PŘIPRAVUJE','none')]
        browse_button=tile('+  OBJEVIT DALŠÍ SERIÁLY' if kind=='show'
                           else '+  OBJEVIT DALŠÍ FILMY','catalog_open',
                           catalog_kind=kind,
                           plot='Otevře knihovnu ověřených souborů Webshare.')
        discovered=[browse_button]+items[:35]
        # One guaranteed paint, no expensive recommendations lookup before it.
        browse_heading='PROCHÁZET SERIÁLY' if kind=='show' else 'PROCHÁZET FILMY'
        self._fill(headline,primary,browse_heading,discovered,
                   'Vyber titul nebo otevři úplnou knihovnu')

    def _filtered(self,cards,keep_order=False):
        from cinema_catalog_v2 import sort_cards,choose_files
        from cinema_genres import genre_matches
        selected=[]
        for c in cards:
            if c.get('kind') not in ('movie','show'):
                selected.append(c)
                continue
            if self.year!='all' and str(c.get('year') or '')!=self.year:
                continue
            if self.genre!='all' and not genre_matches(c,self.genre):
                continue
            if not choose_files(c.get('files') or [],self.quality,self.language):
                continue
            selected.append(c)
        return selected if keep_order else sort_cards(selected,self.sort)

    def _screen(self,view,context=None,stack=False):
        if view!=getattr(self,'mode',None):
            # A new section must not inherit the previous section's hero.
            self.featured_card=None
        self.mode=view
        self.context=context
        nav=view if view in ('home','movies','shows','premieres','search','genres') else (
            'shows' if view in ('seasons','episodes') else
            'movies' if view in ('files','catalog_all','csfd_ranked','most_watched') else
            'home')
        self.setProperty('nav_active',nav)
        self.setProperty('is_home','yes' if view=='home' else '')
        self.setProperty('section_label',{
            'home':'DOMŮ','movies':'FILMY','shows':'SERIÁLY','premieres':'PREMIÉRY',
            'search':'VYHLEDÁVÁNÍ','seasons':'SÉRIE','episodes':'EPIZODY',
            'files':'VÝBĚR KVALITY',
             'most_watched':'NEJSLEDOVANĚJŠÍ',
              'genres':'ŽÁNRY','genre_titles':'ŽÁNROVÝ KATALOG',
              'catalog_all':'ÚPLNÝ KATALOG',
              'csfd_ranked':'NEJLEPŠÍ DLE ČSFD',
              'favorites':'OBLÍBENÉ','recommendations':'TIPY NA SLEDOVÁNÍ'}.get(view,'KATALOG'))
        if not self.service.token:
            self._fill('PŘIHLÁŠENÍ K WEBSHARE',[
                tile('NASTAVIT ÚČET WEBSHARE','settings',
                     plot='Stiskni OK nebo ozubené kolečko vpravo nahoře.'),
            ],'NASTAVENÍ',[], 
                'Otevři ⚙ Nastavení pro přihlášení k Webshare.')
            return
        if view=='home':
            # Cinematic home is a real page, independent from worker success.
            home=self._home_catalogue()
            store=getattr(self,'watch_store',None)
            try:
                films=store.continue_cards('movie') if store else []
                series=store.continue_cards('show') if store else []
                favorites=store.favorite_cards() if store else []
            except Exception as exc:
                self._catalog_problem('watch lists',exc)
                films,series,favorites=[],[],[]
            from cinema_rankings import csfd_only
            all_movies=home.get('_all_movies') or []
            all_shows=home.get('_all_shows') or []
            csfd_movies=csfd_only(all_movies,'movie',limit=30)
            csfd_shows=csfd_only(all_shows,'show',limit=30)
            personal,weekly=self._home_tips(home,store,limit=24)
            # Show real films as soon as any verified movie is indexed.
            if not personal:
                personal=[
                    tile('OBJEVIT FILMY V KNIHOVNĚ','movies'),
                    tile('VYHLEDAT KONKRÉTNÍ FILM','search'),
                    tile('OBNOVIT TIPY A KATALOG','tips_retry')]
            if not weekly:
                weekly=list(personal)
            if csfd_movies:
                csfd_movies=list(csfd_movies)+[tile('+  CELÝ ŽEBŘÍČEK ČSFD',
                    'csfd_ranked',catalog_kind='movie')]
            if csfd_shows:
                csfd_shows=list(csfd_shows)+[tile('+  SERIÁLY NA ČSFD',
                    'csfd_ranked',catalog_kind='show')]
            latest=home.get('premieres') or all_movies[:18]
            shows=home.get('shows') or all_shows[:18]
            year=home.get('ranking_year') or __import__('datetime').date.today().year
            rows=[
                ('TIPY NA SLEDOVÁNÍ',personal),
                ('POKRAČOVAT VE SLEDOVÁNÍ',films+series),
                ('NEJLÉPE HODNOCENÉ FILMY · ČSFD',csfd_movies or [
                    tile('OTEVŘÍT FILMOVOU KNIHOVNU','movies')]),
                ('NEJLÉPE HODNOCENÉ SERIÁLY · ČSFD',csfd_shows or [
                    tile('OTEVŘÍT KATALOG SERIÁLŮ','shows')]),
                ('NOVÉ FILMY',latest or [tile('PROCHÁZET FILMY','movies')]),
                ('VYBER SI SERIÁL',shows or [tile('PROCHÁZET SERIÁLY','shows')]),
                ('TIPY NA TENTO TÝDEN',weekly),
                ('MOJE OBLÍBENÉ',favorites),
                ('FILMY PRO VEČER',all_movies[:24]),
                ('SERIÁLY PRO VEČER',all_shows[:24]),
                ('NEJLEPŠÍ FILMY ROKU %s · ČSFD'%year,
                    csfd_only(all_movies,'movie',year=year,limit=20)),
                ('NEJLEPŠÍ SERIÁLY ROKU %s · ČSFD'%year,
                    csfd_only(all_shows,'show',year=year,limit=20)),
            ]
            self._fill(rows[0][0],rows[0][1],rows[1][0],rows[1][1],
                       'DOMŮ  ·  tipy a ověřené filmy z Webshare',
                       extra_rows=rows[2:])
            self._schedule_home_discovery()
        elif view=='recommendations':
            home=self._home_catalogue()
            chosen,weekly=self._home_tips(
                home,getattr(self,'watch_store',None),limit=35)
            if not chosen:
                chosen=[tile('PROCHÁZET DOSTUPNÉ FILMY','movies'),
                        tile('VYHLEDAT FILM PODLE NÁZVU','search'),
                        tile('AKTUALIZOVAT TIPY','tips_retry')]
            if not weekly:
                weekly=list(chosen)
            self._fill('DOPORUČUJEME PRO TEBE',chosen,
                       'TIPY NA TENTO TÝDEN',weekly,
                       'Tipy vycházejí z dostupných filmů a seriálů')
            self._schedule_home_discovery()
        elif view in ('movies','shows','premieres'):
            # Always repaint the selected section, even when its catalogue is
            # unavailable. Never leave the previous tab's rows on screen.
            self._render_primary_section(view)
        elif view=='genres':
            from cinema_genres import GENRES, genre_icon_path
            # Every genre has a bundled image, not a Unicode glyph or an
            # external HTTP poster. Safe even when Webshare is unavailable.
            root=(self.addon.getAddonInfo('path')
                  if getattr(self,'addon',None) else os.path.dirname(__file__))
            cards=[tile(name,'genre_open',genre_name=name,
                        poster=genre_icon_path(root,name),
                        plot='Filmy a seriály žánru '+name)
                   for name in GENRES]
            self._fill('VYBER SI ŽÁNR',cards[:12],
                       'DALŠÍ FILMOVÉ ŽÁNRY',cards[12:],
                       '24 kategorií · vyber obrázek a otevři dostupné tituly')
        elif view=='genre_titles':
            from cinema_genres import genre_cards
            from cinema_dedupe import consolidate
            genre=context or 'Komedie'
            home=self.service.home_fast()
            film_pool=list(home.get('_all_movies') or [])
            show_pool=list(home.get('_all_shows') or [])
            for kind,pool in (('movie',film_pool),('show',show_pool)):
                stream=getattr(self.service,'_browse_streams',{}).get(kind)
                if stream:
                    pool.extend(stream['cards'])
            movies=self._filtered(genre_cards(consolidate(film_pool),genre))
            shows=self._filtered(genre_cards(consolidate(show_pool),genre))
            for kind,cards in (('movie',movies),('show',shows)):
                stream=getattr(self.service,'_browse_streams',{}).get(kind)
                if not stream or not stream.get('done'):
                    cards.append(tile('+  NAČÍST DALŠÍ '+(
                        'FILMY' if kind=='movie' else 'SERIÁLY'),'genre_more',
                        catalog_kind=kind,
                        plot='Prověří další soubory Webshare a jejich žánry'))
            self._fill(genre.upper()+' · FILMY',movies or
                       [tile('ZATÍM BEZ OVĚŘENÝCH FILMŮ','none')],
                       genre.upper()+' · SERIÁLY',shows or
                       [tile('ZATÍM BEZ OVĚŘENÝCH SERIÁLŮ','none')],
                       'Žánry podle ČSFD/Cinemeta · neověřené tituly skryty')
        elif view=='csfd_ranked':
            from cinema_rankings import csfd_only
            kind=context if context in ('movie','show') else 'movie'
            snapshot=self.service.home_fast()
            key='_all_movies' if kind=='movie' else '_all_shows'
            ranked=csfd_only(snapshot.get(key) or [],kind,limit=80)
            self._fill('ČSFD · NEJLÉPE HODNOCENÉ '+(
                       'FILMY' if kind=='movie' else 'SERIÁLY'),
                       ranked or [tile('ZATÍM BEZ OVĚŘENÉHO HODNOCENÍ ČSFD','none')],
                       '',[],'Jen skutečné hodnocení ČSFD a ověřené Webshare soubory')
        elif view=='continue':
            store=getattr(self,'watch_store',None)
            movies=store.continue_cards('movie') if store else []
            shows=store.continue_cards('show') if store else []
            self._fill('ROZKOUKANÉ FILMY',movies or [tile('ZATÍM ŽÁDNÝ ROZKOUKANÝ FILM','none')],
                       'ROZKOUKANÉ SERIÁLY',shows or [tile('ZATÍM ŽÁDNÝ ROZKOUKANÝ SERIÁL','none')],
                       'Pokračovat od uložené pozice přehrávání')
        elif view=='favorites':
            store=getattr(self,'watch_store',None)
            favorites=store.favorite_cards() if store else []
            self._fill('MOJE OBLÍBENÉ',favorites or
                       [tile('ZATÍM NIC V OBLÍBENÝCH','none')],
                       '',[],'Na plakátu stiskni kontextovou nabídku pro přidání nebo odebrání')
        elif view=='catalog_all':
            kind=context if context in ('movie','show') else 'movie'
            load=self._loading('Načítám další ověřené filmy…' if kind=='movie'
                               else 'Načítám další ověřené seriály…')
            try:
                cards,more=self.service.full_catalog(
                    kind,self.catalog_limit,self.sort,self.quality,self.language)
                cards=self._filtered(cards)
                items=list(cards)
                if more:
                    items.append(tile('+  NAČÍST DALŠÍ FILMY' if kind=='movie'
                                      else '+  NAČÍST DALŠÍ SERIÁLY',
                                      'catalog_more',catalog_kind=kind,
                                      plot='Další stránka Webshare se načte až po potvrzení.'))
                if not items:
                    items=[tile('NIC DALŠÍHO NENALEZENO','none')]
                self._fill('FILMOVÁ KNIHOVNA' if kind=='movie' else
                           'KNIHOVNA SERIÁLŮ',items,'',[],
                           '%d ověřených titulů · dostupné soubory · '
                           'další stránky na požádání'%len(cards))
            finally:load.close()
        elif view=='most_watched':
            # Old bookmark/cache compatibility. KIVORA no longer displays
            # Webshare rating as a film-viewing popularity chart.
            self._screen('catalog_all',context if context in ('movie','show')
                         else 'movie')
        elif view=='search':
            query=(context or '').strip()
            if not query:
                query=xbmcgui.Dialog().input('Hledat film nebo seriál')
            if not query or not query.strip():
                if self.stack:
                    self._go_back()
                else:
                    self._screen('home')
                return
            load=self._loading('Vyhledávám "'+query[:60]+'" na Webshare…')
            try:
                from cinema_service_v2 import WebshareSearchUnavailable
                try:
                    found=self.service.search(query)
                except WebshareSearchUnavailable as exc:
                    self._fill('VYHLEDÁVÁNÍ NENÍ DOSTUPNÉ',[
                        tile('OPAKOVAT HLEDÁNÍ: '+query,'search_retry',search_text=query),
                        tile('KONTROLOVAT ÚČET WEBSHARE','settings')],
                        'FILMY A SERIÁLY',[],str(exc))
                    return
                movies=self._filtered([c for c in found if c['kind']=='movie'])
                shows=self._filtered([c for c in found if c['kind']=='show'])
                self.context=query
                if not movies and not shows:
                    movies=[tile('ZKUSIT JINÝ NÁZEV','search')]
                self._fill('FILMY: '+query.upper(),movies,
                           'SERIÁLY: '+query.upper(),shows,
                           '%d filmů · %d seriálů · pouze dostupné na Webshare' %
                           (len([x for x in movies if x['kind']=='movie']),len(shows)))
            finally:load.close()
        elif view=='seasons':
            load=self._loading('Vyhledávám všechny dostupné série…')
            try:
                seasons=self.service.seasons(context)
                self._fill('SÉRIE · '+context['title'],[
                    tile('SÉRIE %02d (%d epizod)'%(n,len(eps)),
                         'season',season=n,show=context,
                         plot='Epizody seřazené podle čísla, nikoliv data nahrání.')
                    for n,eps in seasons.items()
                ] or [tile('ŽÁDNÉ ČÍSLOVANÉ EPIZODY','none')],
                    'VYBER SÉRII',[],
                    '%d sezón dohledaných z více stránek Webshare' %len(seasons))
            finally:load.close()
        elif view=='episodes':
            show,season=context
            seasons=self.service.seasons(show)
            eps=seasons.get(season,{})
            self._fill('%s · S%02d'%(show['title'],season),[
                tile('S%02dE%02d · %d verzí'%(season,n,len(files)),
                     'episode',show=show,season=season,episode=n,
                     quality=str(len(files))+' verzí',
                     plot='Vyber epizodu; potom zvol soubor a kvalitu.')
                for n,files in eps.items()
            ] or [tile('ŽÁDNÉ EPIZODY','none')],
                'SEŘAZENO PODLE ČÍSLA EPIZODY',[],
                'Série %d · %d epizod v dostupných výsledcích Webshare' %(season,len(eps)))
        elif view=='files':
            c,season,episode=context
            load=self._loading('Ověřuji jednotlivé kvality a jazykové verze…')
            try:
                if season is None:
                    files=self.service.files(c,self.quality,self.language)
                else:
                    files=self.service.episode_variants(
                        c,season,episode,self.quality,self.language)
                items=self.service.file_rows(files,poster=c.get('poster') or '')
                self._fill('VYBER SOUBOR · '+c['title'],items or [
                    tile('ŽÁDNÝ SOUBOR PRO TENTO FILTR','none')
                ],'KVALITU / CZ ZMĚNÍŠ V HORNÍ NABÍDCE',[],
                '%d ověřených verzí · přehrávání až po potvrzení souboru' %len(files))
            finally:load.close()

    def _go_back(self):
        if self.stack:
            previous=self.stack.pop()
            view,ctx=previous[:2]
            self._screen(view,ctx)
            if len(previous)==4:
                focus,index=previous[2:]
                if focus in ROW_IDS and self.rail_items[ROW_IDS.index(focus)]:
                    try:
                        self.setFocusId(focus)
                        self.getControl(focus).selectItem(min(
                            index,len(self.rail_items[ROW_IDS.index(focus)])-1))
                        self._update_hero()
                    except (RuntimeError,AttributeError):
                        pass
        else:
            self.close()

    def _open_settings(self):
        """Open the native add-on settings without leaving the cinematic window."""
        try:
            self.addon.openSettings()
            if self.addon.getSetting('wsuser') and self.addon.getSetting('wspass'):
                new_token=self.revalidate_callback()
            else:
                new_token=None
            self.service.token=new_token
            self.service.home_cache=None
            self.service.search_cache.clear()
            self.service.series_cache.clear()
            self.stack=[]
            self._screen('home')
        except Exception:
            traceback.print_exc()
            xbmcgui.Dialog().notification('KIVORA',
                'Nastavení bylo zavřeno, zkus otevřít přehrávač znovu.',
                xbmcgui.NOTIFICATION_WARNING)

    def _gear_menu(self):
        selected=xbmcgui.Dialog().select('⚙  Nastavení KIVORA',[
            'Nastavení doplňku a přihlášení Webshare',
            'Filtry a řazení katalogu',
            'Načíst další tituly a aktualizovat Webshare',
            'Moje oblíbené',
            'Nejlépe hodnocené podle ČSFD',
            'Vyhledat podle žánru',
            'Automatické pokračování seriálu: '+(
                'ZAPNUTO' if self.addon.getSetting('autoplay_next_episode')!='false'
                else 'VYPNUTO')
        ])
        if selected==0:
            self._open_settings()
        elif selected==1:
            self._filters()
        elif selected==2:
            self.service.refresh_catalogue()
            self.stack=[]
            self._screen('home')
        elif selected==3:
            self._refresh('favorites')
        elif selected==4:
            self._refresh('csfd_ranked')
        elif selected==5:
            self._refresh('genres')
        elif selected==6:
            enabled=self.addon.getSetting('autoplay_next_episode')!='false'
            self.addon.setSetting('autoplay_next_episode',
                                  'false' if enabled else 'true')
            xbmcgui.Dialog().notification('KIVORA',
                'Automatické další díly vypnuty' if enabled
                else 'Automatické další díly zapnuty')

    def _filters(self):
        choice=xbmcgui.Dialog().select('Katalog · filtrování a řazení',[
            'Řazení: '+self.sort,'Rozlišení: '+self.quality,
            'Jazyk: '+self.language,'Rok: '+self.year,
            'Žánr: '+self.genre,'Resetovat filtry'])
        if choice<0:return
        if choice==0:
            arr=['date','year','rating','title','quality']
            chosen=xbmcgui.Dialog().select('Řazení',[
                'Kinopremiéra / pořadí nahrání','Rok vydání ↓',
                'Hodnocení ČSFD ↓','Název A–Z','Kvalita'])
            if chosen>=0:self.sort=arr[chosen]
        elif choice==1:
            arr=['all','1080','4k']
            n=xbmcgui.Dialog().select('Rozlišení',['Vše','1080p+','4K'])
            if n>=0:self.quality=arr[n]
        elif choice==2:
            arr=['all','cz']
            n=xbmcgui.Dialog().select('Jazyk',['Vše','CZ v názvu souboru'])
            if n>=0:self.language=arr[n]
        elif choice==3:
            from datetime import date
            years=['all']+[str(v) for v in range(date.today().year,date.today().year-35,-1)]
            n=xbmcgui.Dialog().select('Rok vydání', ['Všechny roky']+years[1:])
            if n>=0:self.year=years[n]
        elif choice==4:
            genres=['all','Akční','Animovaný','Dobrodružný','Drama','Fantasy',
                    'Horor','Komedie','Krimi','Rodinný','Romantický','Sci-Fi',
                    'Thriller','Válečný','Dokumentární']
            n=xbmcgui.Dialog().select('Žánr ČSFD',['Všechny žánry']+genres[1:])
            if n>=0:self.genre=genres[n]
        elif choice==5:
            self.sort='date';self.quality='all';self.language='all'
            self.year='all';self.genre='all'
        # Rerender without leaving the cinematic window.
        self._screen(self.mode,self.context)

    def _apply_background_home(self):
        current_mode=getattr(self,'mode',None)
        if (current_mode not in ('home','recommendations','movies','shows','premieres')
                or getattr(self,'_updating_home',False)
                or getattr(self,'_switching_section',False)):
            return
        updated=self.service.take_home_refresh()
        take_tips=getattr(self.service,'take_tips_refresh',None)
        tips_updated=take_tips() if callable(take_tips) else None
        if not updated and not tips_updated:
            return
        focused=self.getFocusId()
        position=0
        try:
            if focused in ROW_IDS:
                position=max(0,self.getControl(focused).getSelectedPosition())
        except (RuntimeError,AttributeError):
            pass
        self._updating_home=True
        try:
            self._screen(current_mode,self.context)
        finally:
            self._updating_home=False
        if focused in TOP_ACTIONS:
            try:
                self.setFocusId(focused)
            except (RuntimeError,AttributeError):
                pass
        elif focused in ROW_IDS and self.rail_items[ROW_IDS.index(focused)]:
            try:
                self.setFocusId(focused)
                self.getControl(focused).selectItem(min(position,len(
                    self.rail_items[ROW_IDS.index(focused)])-1))
            except (RuntimeError,AttributeError):
                pass
        self._update_hero()

    def onFocus(self,control_id):
        self._apply_background_home()
        self._update_hero()

    def _last_filled_rail(self):
        """Return the lowest populated row; trailing shelves can be hidden."""
        return next((rid for rid,cards in
                     reversed(list(zip(ROW_IDS,self.rail_items))) if cards),None)

    def _poster_menu(self):
        card=self._selected()
        store=getattr(self,'watch_store',None)
        if not card or not store or card.get('kind') not in ('movie','show'):
            return
        actions=['Přidat / odebrat z oblíbených',
                 'Označit jako dokoukáno',
                 'Odebrat z rozkoukaných',
                 'Otevřít titul']
        selected=xbmcgui.Dialog().select(card.get('title') or 'Film',actions)
        if selected==0:
            enabled=store.toggle_favorite(card)
            xbmcgui.Dialog().notification('KIVORA',
                'Přidáno do oblíbených' if enabled else 'Odebráno z oblíbených')
            self._screen(self.mode,self.context)
        elif selected==1:
            store.mark_watched(card)
            self._screen(self.mode,self.context)
        elif selected==2:
            store.clear_progress(card)
            self._screen(self.mode,self.context)
        elif selected==3:
            if card.get('_continue'):
                self._play_saved(card)
            elif card.get('kind')=='movie':
                self._refresh('files',(card,None,None))
            else:
                self._refresh('seasons',card)

    def _start_playback(self,url):
        """Keep the film dialog alive below video, preserving scroll/focus."""
        builtin=getattr(xbmc,'executebuiltin',None)
        if callable(builtin):
            builtin('PlayMedia(%s)'%url)
        else:
            # Compatible fallback for minimal Kodi stubs.
            self.destination=url
            self.is_play=True
            self.close()

    def _play_saved(self,card):
        """Resume a real, previously played Webshare file at its stored time."""
        if not card.get('ident') or not card.get('name'):
            return
        url=self.make_url(
            action='play',from_cinema='1',ident=card['ident'],name=card['name'],
            title=card.get('title') or '',raw_title=card.get('raw_title') or card.get('raw') or '',
            kind=card.get('kind') or 'movie',year=card.get('year') or '',
            poster=card.get('poster') or '',fanart=card.get('fanart') or '',
            original=card.get('original') or '',
            season=card.get('season') or '',episode=card.get('episode') or '',
            resume=str(card.get('position') or 0))
        self._start_playback(url)

    def onAction(self,action):
        self._apply_background_home()
        if action.getId()==117:
            self._poster_menu()
        elif action.getId() in BACK_ACTIONS:
            self._go_back()
        elif action.getId()==4 and self.getFocusId()==self._last_filled_rail():
            # ACTION_MOVE_DOWN on final shelf must not send focus to the menu.
            self._update_hero()
            return
        else:
            self._update_hero()

    def onClick(self,control_id):
        if control_id==108:
            chosen=self.featured_card
            if chosen and chosen.get('_continue'):
                self._play_saved(chosen)
            elif chosen and chosen.get('kind')=='movie':
                self._refresh('files',(chosen,None,None))
            elif chosen and chosen.get('kind')=='show':
                self._refresh('seasons',chosen)
            return
        if control_id in TOP_ACTIONS:
            command=TOP_ACTIONS[control_id]
            self._nav_focus_target=control_id
            self._switching_section=True
            try:
                if command=='settings':
                    self._gear_menu()
                elif command=='home':
                    self.stack=[]
                    service=getattr(self,'service',None)
                    if service:
                        service.take_home_refresh()
                    self._screen('home',stack=False)
                elif command=='csfd_ranked':
                    self._refresh(command,'movie')
                else:
                    self._refresh(command)
            finally:
                self._switching_section=False
            return
        c=self._selected(control_id)
        if not c:return
        kind=c.get('kind')
        if kind=='none':
            return
        if c.get('_continue'):
            self._play_saved(c)
        elif kind in ('movies','shows','premieres','search','most_watched','csfd_ranked','favorites','genres'):
            if kind in ('most_watched','csfd_ranked'):
                if kind=='most_watched':
                    self.popular_limit=24
                self._refresh(kind,c.get('catalog_kind') or 'movie')
            else:
                self._refresh(kind)
        elif kind=='search_retry':
            self._refresh('search',c.get('search_text') or '')
        elif kind=='tips_retry':
            self._apply_background_home()
            if self.mode in ('home','recommendations'):
                self.service.start_home_refresh(force=True)
                new_tips=getattr(self.service,'start_tips_refresh',None)
                if callable(new_tips):
                    new_tips(force=True)
                xbmcgui.Dialog().notification('KIVORA',
                    'Doporučení se aktualizují na pozadí')
        elif kind=='genre_open':
            self.genre_limits={'movie':24,'show':24}
            self._refresh('genre_titles',c.get('genre_name'))
        elif kind=='genre_more':
            what=c.get('catalog_kind') or 'movie'
            self.genre_limits[what]+=24
            load=self._loading('Prověřuji další tituly Webshare…')
            try:
                self.service.full_catalog(what,self.genre_limits[what],
                                          self.sort,self.quality,self.language)
            finally:
                load.close()
            self._screen('genre_titles',self.context)
        elif kind=='catalog_open':
            self.catalog_limit=24
            self._refresh('catalog_all',c.get('catalog_kind') or 'movie')
        elif kind=='catalog_more':
            # After a new batch retain selection near the previous last movie,
            # not at the start of this long horizontal poster strip.
            from cinema_dedupe import identity
            previous=next((c for c in reversed(self.rail_items[0])
                           if c.get('kind') in ('movie','show')),None)
            marker=identity(previous) if previous else None
            self.catalog_limit+=24
            self._screen('catalog_all',self.context)
            try:
                if marker:
                    index=next((i for i,item in enumerate(self.rail_items[0])
                                if item.get('kind') in ('movie','show')
                                and identity(item)==marker),None)
                    if index is not None:
                        self.getControl(401).selectItem(index)
                self._update_hero()
            except (RuntimeError,AttributeError):
                pass
        elif kind=='load_more':
            previous=len(self.rail_items[0])-1
            self.popular_limit+=24
            self._screen('most_watched',self.context)
            try:
                self.getControl(401).selectItem(min(previous,
                    len(self.rail_items[0])-1))
                self._update_hero()
            except (RuntimeError,AttributeError):
                pass
        elif kind=='settings':
            self._open_settings()
        elif kind=='movie':
            self._refresh('files',(c,None,None))
        elif kind=='show':
            self._refresh('seasons',c)
        elif kind=='season':
            self._refresh('episodes',(c['show'],c['season']))
        elif kind=='episode':
            self._refresh('files',(c['show'],c['season'],c['episode']))
        elif kind=='file':
            # Hand off title/episode information only after explicit file choice.
            # The Kodi playback service saves real progress after video starts.
            parent,season,episode=self.context
            url=self.make_url(
                action='play',from_cinema='1',
                ident=c['ident'],name=c['raw'],
                title=parent.get('title') or '',raw_title=parent.get('raw') or parent.get('title') or '',
                kind=parent.get('kind') or 'movie',
                year=parent.get('file_year') or parent.get('year') or '',
                poster=parent.get('poster') or '',fanart=parent.get('fanart') or '',
                original=parent.get('original') or '',
                plot=parent.get('plot') or '',genre=parent.get('genre') or '',
                quality=c.get('quality') or '',
                season=str(season or ''),episode=str(episode or ''))
            self._start_playback(url)


def launch(addon,profile,get_url,token,search_page,
           metadata_factory,calendar_factory,revalidate_callback):
    from cinema_service_v2 import CinemaService
    from ws_availability import Availability
    from cinematic_home import ensure_textures
    from cinema_user_state import WatchStore
    metadata=metadata_factory() if addon.getSetting('smart_metadata')!='false' else None
    service=CinemaService(token,search_page,Availability(profile),
                          metadata,calendar_factory(),profile=profile)
    win=CinemaScreen('fckyo-cinema-v2.xml',addon.getAddonInfo('path'),'Default','1080i')
    win.service=service
    win.watch_store=WatchStore(profile)
    win.addon=addon
    win.revalidate_callback=revalidate_callback
    win.textures=ensure_textures(profile)
    win.brand_path=os.path.join(addon.getAddonInfo('path'),'resources','brand.png')
    names={201:'home',202:'continue',203:'favorite',204:'genres',
           205:'csfd',206:'premieres',207:'settings',208:'tips'}
    win.icon_paths={cid:os.path.join(addon.getAddonInfo('path'),'resources',
                    'icons',name+'.png') for cid,name in names.items()}
    win.make_url=get_url
    win.destination=None
    win.is_play=False
    win.sort='date'
    win.quality='all'
    win.language='all'
    win.year='all'
    win.genre='all'
    try:
        win.doModal()
        return win.destination,win.is_play
    finally:
        try:
            xbmcgui.Window(10000).clearProperty('kivora_window_open')
        except (RuntimeError,AttributeError,TypeError):
            pass
        win.close()
        del win
