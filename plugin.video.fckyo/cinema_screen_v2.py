# -*- coding: utf-8 -*-
"""Kodi-only TV navigator. All browsing lives in one WindowXMLDialog.

Settings stay inside the movie UI; only playing a selected file leaves it. Content lists are populated from real, availability-checked files.
"""
import os
import traceback
import xbmcgui
import xbmc

TOP_ACTIONS={
    101:'movies', 102:'shows', 103:'search', 104:'premieres',
    105:'genres', 107:'settings'
}
BACK_ACTIONS=(9,10,92,216)
ROW_IDS=tuple(range(401,414))
VERSION='0.20.0'


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
        for name,path in self.textures.items():
            self.setProperty('cinema_'+name,path)
        self.setProperty('app_version','v'+VERSION)
        self.setProperty('section_label','ÚVOD')
        self.setProperty('ui_status','Šipky = pohyb, OK = výběr, Zpět = předchozí obrazovka')
        self.setProperty('hero_title','FCKYO')
        self.setProperty('hero_info','Katalog ověřených souborů Webshare')
        self.setProperty('hero_plot','Nové filmy podle českých kinopremiér a jejich dostupnosti.')
        self.setProperty('hero_art','')
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
        d.create('FCKYO',text)
        return d

    def _fill(self,title1,cards1,title2,cards2,status='',extra_rows=()):
        rows=[(title1,cards1),(title2,cards2)]+list(extra_rows)
        while len(rows)<len(ROW_IDS):
            rows.append(('',[]))
        self.rail_items=[cards or [] for heading,cards in rows[:len(ROW_IDS)]]
        for index,(heading,cards) in enumerate(rows[:len(ROW_IDS)]):
            self.setProperty('row%d_heading'%(index+1),heading if cards else '')
        self.setProperty('ui_status',status or
            ('FCKYO '+VERSION+' · pouze tituly dostupné na Webshare'))
        for i,control_id in enumerate(ROW_IDS):
            lst=self.getControl(control_id)
            lst.reset()
            li=[]
            for c in self.rail_items[i]:
                item=xbmcgui.ListItem(label=str(c.get('title') or 'Bez názvu'))
                art={}
                if c.get('poster'):
                    art['poster']=c['poster']
                    art['thumb']=c['poster']
                if c.get('fanart'):
                    art['fanart']=c['fanart']
                if art:
                    item.setArt(art)
                item.setProperty('has_poster','yes' if c.get('poster') else '')
                item.setProperty('is_more','yes' if c.get('kind') in ('most_watched','load_more','catalog_open','catalog_more','csfd_ranked') else '')
                item.setProperty('quality',str(c.get('quality') or ''))
                item.setProperty('year',str(c.get('year') or ''))
                item.setProperty('progress',str(c.get('progress') or '0'))
                item.setProperty('is_resume','yes' if c.get('_continue') else '')
                li.append(item)
            if li:
                lst.addItems(li)
        try:
            self.setFocusId(next((rid for rid,cards in zip(ROW_IDS,self.rail_items) if cards),107))
        except RuntimeError:
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
        if not c and self.getFocusId()==108:
            c=self.featured_card
        if not c:
            self.featured_card=None
            self.setProperty('hero_title','FCKYO')
            self.setProperty('hero_info','FILMY · SERIÁLY · HLEDÁNÍ')
            self.setProperty('hero_plot','Vyber kategorii nebo titul.')
            self.setProperty('hero_art','')
            self.setProperty('hero_action','')
            return
        if c.get('kind') in ('movie','show'):
            self.featured_card=c
            self.setProperty('hero_action','yes')
        else:
            self.featured_card=None
            self.setProperty('hero_action','')
        self.setProperty('hero_title',str(c.get('title') or ''))
        text=[str(c.get('year') or ''),str(c.get('genre') or ''),
              str(c.get('quality') or '')]
        if c.get('rating') is not None:
            text.append('%s %s %%'%(c.get('rating_source') or 'ČSFD',c['rating']))
        self.setProperty('hero_info','  ·  '.join(x for x in text if x)[:155])
        self.setProperty('hero_plot',str(c.get('plot') or '')[:480])
        self.setProperty('hero_art',str(c.get('fanart') or c.get('poster') or ''))

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
        self.mode=view
        self.context=context
        self.setProperty('section_label',{
            'home':'DOMŮ','movies':'FILMY','shows':'SERIÁLY','premieres':'PREMIÉRY',
            'search':'VYHLEDÁVÁNÍ','seasons':'SÉRIE','episodes':'EPIZODY',
            'files':'VÝBĚR KVALITY',
             'most_watched':'NEJSLEDOVANĚJŠÍ',
              'genres':'ŽÁNRY','genre_titles':'ŽÁNROVÝ KATALOG',
              'catalog_all':'ÚPLNÝ KATALOG',
              'csfd_ranked':'NEJLEPŠÍ DLE ČSFD',
              'favorites':'OBLÍBENÉ'}.get(view,'KATALOG'))
        if not self.service.token:
            self._fill('PŘIHLÁŠENÍ K WEBSHARE',[
                tile('NASTAVIT ÚČET WEBSHARE','settings',
                     plot='Stiskni OK nebo ozubené kolečko vpravo nahoře.'),
            ],'NASTAVENÍ',[], 
                'Otevři ⚙ Nastavení pro přihlášení k Webshare.')
            return
        if view=='home':
            # Draw cached, previously verified titles immediately.
            home=self.service.home_fast()
            self.service.start_home_refresh()
            store=getattr(self,'watch_store',None)
            films=store.continue_cards('movie') if store else []
            series=store.continue_cards('show') if store else []
            favorites=store.favorite_cards() if store else []
            year=home.get('ranking_year') or __import__('datetime').date.today().year
            from cinema_rankings import csfd_only
            csfd_movies=csfd_only(home.get('_all_movies') or [],'movie',limit=30)
            csfd_shows=csfd_only(home.get('_all_shows') or [],'show',limit=30)
            web_movies=self._filtered(home.get('_webshare_movies') or [],
                                      keep_order=True)[:18]
            web_shows=self._filtered(home.get('_webshare_shows') or [],
                                     keep_order=True)[:18]
            if web_movies:
                web_movies.append(tile('+  CELÝ ŽEBŘÍČEK','most_watched',
                    catalog_kind='movie',plot='Popularita souborů, nikoli počet zhlédnutí'))
            if web_shows:
                web_shows.append(tile('+  CELÝ ŽEBŘÍČEK SERIÁLŮ','most_watched',
                    catalog_kind='show',plot='Popularita seriálových souborů Webshare'))
            if csfd_movies:
                csfd_movies.append(tile('+  ŽEBŘÍČEK ČSFD','csfd_ranked',
                    catalog_kind='movie'))
            if csfd_shows:
                csfd_shows.append(tile('+  SERIÁLY ČSFD','csfd_ranked',
                    catalog_kind='show'))
            top=(home.get('premieres') or [])+(home.get('movies') or [])
            shows=(home.get('shows') or [])+(home.get('classic_shows') or [])
            if not top:
                top=[tile('FILMY · OTEVŘÍT KATALOG','movies')]
            if not shows:
                shows=[tile('SERIÁLY · OTEVŘÍT KATALOG','shows')]
            rows=[
                ('POKRAČOVAT · FILMY',films),
                ('POKRAČOVAT · SERIÁLY',series),
                ('POPULÁRNÍ NA WEBSHARE · FILMY',web_movies),
                ('NEJLÉPE HODNOCENÉ NA ČSFD · FILMY',csfd_movies),
                ('POPULÁRNÍ NA WEBSHARE · SERIÁLY',web_shows),
                ('NEJLÉPE HODNOCENÉ NA ČSFD · SERIÁLY',csfd_shows),
                ('PREMIÉRY A NOVÉ FILMY',top),
                ('SERIÁLY NA WEBSHARE',shows),
                ('MOJE OBLÍBENÉ',favorites),
                ('FILMOVÉ HITY A KLASIKY',home.get('classics') or []),
                ('NEJLEPŠÍ FILMY ROKU %s'%year,home.get('best_movies_year') or []),
                ('NEJLEPŠÍ SERIÁLY VŠECH DOB',home.get('best_shows_all') or []),
                ('NEJLEPŠÍ SERIÁLY ROKU %s'%year,home.get('best_shows_year') or []),
            ]
            self._fill(rows[0][0],rows[0][1],rows[1][0],rows[1][1],
                       self.service.last_diagnostics+
                       ' · Webshare: popularita · ČSFD: hodnocení',
                       extra_rows=rows[2:])
        elif view in ('movies','shows','premieres'):
            load=self._loading('Řadím dostupné tituly…')
            try:
                ordered=self._filtered(self.service.browse(view,self.sort,
                    self.quality,self.language))
                if not ordered:
                    ordered=[tile('VYHLEDAT NÁZEV','search')]
                row_one=ordered[:24]
                if view in ('movies','shows'):
                    what='movie' if view=='movies' else 'show'
                    row_one.append(tile('+  VŠECHNY FILMY' if what=='movie' else
                                        '+  VŠECHNY SERIÁLY','catalog_open',
                                        catalog_kind=what,
                                        plot='Otevřít rozsáhlý katalog a načítat další tituly po dávkách.'))
                other_rows=[]
                if view in ('movies','shows'):
                    what='movie' if view=='movies' else 'show'
                    cached=self.service.home_fast()
                    source='_webshare_movies' if what=='movie' else '_webshare_shows'
                    popular=cached.get(source) or (
                        self.service.most_watched_movies(24,self.quality,self.language)
                        if what=='movie' else
                        self.service.most_watched_shows(24,self.quality,self.language))
                    from cinema_dedupe import identity
                    excluded={identity(c) for c in row_one
                              if c.get('kind') in ('movie','show')}
                    row_two=[c for c in self._filtered(popular,keep_order=True)
                             if identity(c) not in excluded][:24]
                    row_two.append(tile('+  CELÝ ŽEBŘÍČEK WEBSHARE',
                        'most_watched',catalog_kind=what))
                    heading='POPULÁRNÍ NA WEBSHARE · FILMY' if what=='movie' else 'POPULÁRNÍ NA WEBSHARE · SERIÁLY'
                    from cinema_rankings import csfd_only
                    records=cached.get('_all_movies') if what=='movie' else cached.get('_all_shows')
                    csfd=csfd_only(records or [],what,limit=35)
                    if csfd:
                        csfd=list(csfd)+[tile('+  CELÝ ŽEBŘÍČEK ČSFD',
                            'csfd_ranked',catalog_kind=what)]
                    other_rows=[('NEJLÉPE HODNOCENÉ NA ČSFD · FILMY' if what=='movie'
                                 else 'NEJLÉPE HODNOCENÉ NA ČSFD · SERIÁLY',csfd)]
                else:
                    row_two=ordered[24:48]
                    heading='DALŠÍ PREMIÉRY'
                self._fill('FILMY NA WEBSHARE' if view=='movies' else
                           'SERIÁLY NA WEBSHARE' if view=='shows' else
                           'PREMIÉRY PODLE ČSFD',row_one,heading,row_two,
                           'ŘAZENÍ: '+self.sort+' · KVALITA: '+self.quality+
                           ' · JAZYK: '+self.language,extra_rows=other_rows)
            finally:load.close()
        elif view=='genres':
            from cinema_genres import GENRES
            cards=[tile('🎭  '+name,'genre_open',genre_name=name,
                        plot='Vyhledat ověřené filmy a seriály: '+name)
                   for name in GENRES]
            self._fill('VYBER ŽÁNR · FILMY',cards[:12],
                       'VYBER ŽÁNR · SERIÁLY',cards[12:],
                       'Žánry podle filmových metadat, jen ověřené soubory Webshare')
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
                self._fill('VŠECHNY FILMY · WEBSHARE' if kind=='movie' else
                           'VŠECHNY SERIÁLY · WEBSHARE',items,'',[],
                           '%d ověřených titulů · dostupné soubory · '
                           'další stránky na požádání'%len(cards))
            finally:load.close()
        elif view=='most_watched':
            kind=context if context in ('movie','show') else 'movie'
            load=self._loading('Načítám popularitu z Webshare…')
            try:
                fetch=(self.service.most_watched_movies if kind=='movie' else
                       self.service.most_watched_shows)
                ranked=self._filtered(fetch(self.popular_limit,self.quality,self.language),
                                      keep_order=True)[:self.popular_limit]
                done=(self.service._most_watched_done if kind=='movie'
                      else getattr(self.service,'_show_popularity',{}).get('done',False))
                items=list(ranked)
                if not done:
                    items.append(tile('+  NAČÍST DALŠÍ','load_more',catalog_kind=kind))
                if not items:
                    items=[tile('ŽÁDNÉ OVĚŘENÉ TITULY','none')]
                self._fill('WEBSHARE · POPULÁRNÍ '+(
                           'FILMY' if kind=='movie' else 'SERIÁLY'),items,'',[],
                           '%d titulů · popularita souborů, ne počty zhlédnutí'%len(ranked))
            finally:
                load.close()
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
                found=self.service.search(query)
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
            xbmcgui.Dialog().notification('FCKYO',
                'Nastavení bylo zavřeno, zkus otevřít přehrávač znovu.',
                xbmcgui.NOTIFICATION_WARNING)

    def _gear_menu(self):
        selected=xbmcgui.Dialog().select('⚙  Nastavení FCKYO',[
            'Nastavení doplňku a přihlášení Webshare',
            'Filtry a řazení katalogu',
            'Načíst další tituly a aktualizovat Webshare',
            'Moje oblíbené',
            'Nejlépe hodnocené podle ČSFD'
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

    def onFocus(self,control_id):
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
            xbmcgui.Dialog().notification('FCKYO',
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

    def _play_saved(self,card):
        """Resume a real, previously played Webshare file at its stored time."""
        if not card.get('ident') or not card.get('name'):
            return
        self.destination=self.make_url(
            action='play',from_cinema='1',ident=card['ident'],name=card['name'],
            title=card.get('title') or '',raw_title=card.get('raw_title') or card.get('raw') or '',
            kind=card.get('kind') or 'movie',year=card.get('year') or '',
            poster=card.get('poster') or '',fanart=card.get('fanart') or '',
            season=card.get('season') or '',episode=card.get('episode') or '',
            resume=str(card.get('position') or 0))
        self.is_play=True
        self.close()

    def onAction(self,action):
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
            if command=='settings':
                self._gear_menu()
            else:
                self._refresh(command)
            return
        c=self._selected(control_id)
        if not c:return
        kind=c.get('kind')
        if kind=='none':
            return
        if c.get('_continue'):
            self._play_saved(c)
        elif kind in ('movies','shows','premieres','search','most_watched','csfd_ranked','favorites'):
            if kind=='most_watched':
                self.popular_limit=24
            self._refresh(kind)
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
            self._screen('most_watched')
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
            self.destination=self.make_url(
                action='play',from_cinema='1',
                ident=c['ident'],name=c['raw'],
                title=parent.get('title') or '',raw_title=parent.get('raw') or parent.get('title') or '',
                kind=parent.get('kind') or 'movie',
                year=parent.get('file_year') or parent.get('year') or '',
                poster=parent.get('poster') or '',fanart=parent.get('fanart') or '',
                plot=parent.get('plot') or '',genre=parent.get('genre') or '',
                quality=c.get('quality') or '',
                season=str(season or ''),episode=str(episode or ''))
            self.is_play=True
            self.close()


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
        win.close()
        del win
