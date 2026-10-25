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
    107:'settings'
}
BACK_ACTIONS=(9,10,92,216)
ROW_IDS=(401,402,403,404,405,406,407)
VERSION='0.17.0'


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
                item.setProperty('is_more','yes' if c.get('kind') in ('most_watched','load_more','catalog_open','catalog_more') else '')
                item.setProperty('quality',str(c.get('quality') or ''))
                item.setProperty('year',str(c.get('year') or ''))
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
        selected=[]
        for c in cards:
            if c.get('kind') not in ('movie','show'):
                selected.append(c)
                continue
            if self.year!='all' and str(c.get('year') or '')!=self.year:
                continue
            if self.genre!='all' and self.genre.casefold() not in (
                    c.get('genre') or '').casefold():
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
              'catalog_all':'ÚPLNÝ KATALOG'}.get(view,'KATALOG'))
        if not self.service.token:
            self._fill('PŘIHLÁŠENÍ K WEBSHARE',[
                tile('NASTAVIT ÚČET WEBSHARE','settings',
                     plot='Stiskni OK nebo ozubené kolečko vpravo nahoře.'),
            ],'NASTAVENÍ',[], 
                'Otevři ⚙ Nastavení pro přihlášení k Webshare.')
            return
        if view=='home':
            load=self._loading('Načítám dostupné filmy a česká metadata…')
            try:
                home=self.service.home()
                # Each card has already been allocated to one home category.
                # Combine remaining new releases without repeating other rails.
                top=home['premieres']+home['movies']
                bottom=home['shows']+home.get('classic_shows',[])
                if not top:
                    top=[tile('HLEDAT FILM','search'),tile('FILMY','movies')]
                if not bottom:
                    bottom=[tile('HLEDAT SERIÁL','search'),
                            tile('SERIÁLY','shows')]
                year=home.get('ranking_year') or __import__('datetime').date.today().year
                def shelf(items):
                    # An empty ranking is hidden instead of repeating
                    # identical placeholder cards in several home rows.
                    return items or []
                extra=[
                    ('FILMOVÉ HITY A KLASIKY · OVĚŘENO NA WEBSHARE',
                     home.get('classics') or []),
                    ('NEJLEPŠÍ FILMY VŠECH DOB · ČSFD / IMDb',shelf(home.get('best_movies_all'))),
                    ('NEJLEPŠÍ FILMY ROKU %s · ČSFD / IMDb'%year,shelf(home.get('best_movies_year'))),
                    ('NEJLEPŠÍ SERIÁLY VŠECH DOB · ČSFD / IMDb',shelf(home.get('best_shows_all'))),
                    ('NEJLEPŠÍ SERIÁLY ROKU %s · ČSFD / IMDb'%year,shelf(home.get('best_shows_year'))),
                ]
                self._fill('PREMIÉRY A DALŠÍ FILMY NA WEBSHARE' if home['premieres'] else
                           'DOSTUPNÉ FILMY',top,
                           'DOSTUPNÉ SERIÁLY',
                           bottom,self.service.last_diagnostics +
                           ' · Žebříčky pouze z hodnocených dostupných titulů',extra_rows=extra)
            finally:load.close()
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
                if view=='movies':
                    from cinema_dedupe import identity
                    seen={identity(c) for c in row_one if c.get('kind')=='movie'}
                    popular=self._filtered(self.service.most_watched_movies(
                        24,self.quality,self.language),keep_order=True)
                    row_two=[c for c in popular if identity(c) not in seen][:24]
                    row_two.append(tile('+  ZOBRAZIT CELÝ ŽEBŘÍČEK',
                        'most_watched',plot='Otevřít žebříček filmů. '
                        'Další výsledky se načtou až při stisknutí +.'))
                    heading='NEJSLEDOVANĚJŠÍ'
                else:
                    row_two=ordered[24:48]
                    heading='DALŠÍ SERIÁLY' if view=='shows' else 'DALŠÍ PREMIÉRY'
                self._fill('FILMY NA WEBSHARE' if view=='movies' else
                           'SERIÁLY NA WEBSHARE' if view=='shows' else
                           'PREMIÉRY PODLE ČSFD',row_one,heading,row_two,
                           'ŘAZENÍ: '+self.sort+' · KVALITA: '+self.quality+
                           ' · JAZYK: '+self.language)
            finally:load.close()
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
            load=self._loading('Načítám pořadí popularity z Webshare…')
            try:
                ranked=self._filtered(self.service.most_watched_movies(
                    self.popular_limit,self.quality,self.language),
                    keep_order=True)[:self.popular_limit]
                items=list(ranked)
                if self.service.most_watched_has_more():
                    items.append(tile('+  NAČÍST DALŠÍ FILMY','load_more',
                        plot='Postupně načítat další ověřené filmy z Webshare.'))
                if not items:
                    items=[tile('ŽÁDNÉ DOSTUPNÉ FILMY','none')]
                self._fill('NEJSLEDOVANĚJŠÍ · ŽEBŘÍČEK FILMŮ',items,'',[],
                           '%d ověřených filmů · pořadí podle popularity '
                           'vyhledávání Webshare, nikoli počtu zhlédnutí'%len(ranked))
            finally:load.close()
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
            'Načíst další tituly a aktualizovat Webshare'
        ])
        if selected==0:
            self._open_settings()
        elif selected==1:
            self._filters()
        elif selected==2:
            self.service.refresh_catalogue()
            self.stack=[]
            self._screen('home')

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

    def onAction(self,action):
        if action.getId() in BACK_ACTIONS:
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
            if chosen and chosen.get('kind')=='movie':
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
        if kind in ('movies','shows','premieres','search','most_watched'):
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
            # Preserve old player and account handling, do not autoplay a card.
            self.destination=self.make_url(action='play',ident=c['ident'],name=c['raw'])
            self.is_play=True
            self.close()


def launch(addon,profile,get_url,token,search_page,
           metadata_factory,calendar_factory,revalidate_callback):
    from cinema_service_v2 import CinemaService
    from ws_availability import Availability
    from cinematic_home import ensure_textures
    metadata=metadata_factory() if addon.getSetting('smart_metadata')!='false' else None
    service=CinemaService(token,search_page,Availability(profile),
                          metadata,calendar_factory(),profile=profile)
    win=CinemaScreen('fckyo-cinema-v2.xml',addon.getAddonInfo('path'),'Default','1080i')
    win.service=service
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
