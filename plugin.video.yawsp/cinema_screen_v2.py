# -*- coding: utf-8 -*-
"""Kodi-only TV navigator. All browsing lives in one WindowXMLDialog.

Only the voluntary fallback to the legacy menu and the actual player leave
this window. Content lists are populated from real, availability-checked files.
"""
import os
import traceback
import xbmcgui
import xbmc

TOP_ACTIONS={
    101:'movies', 102:'shows', 103:'search', 104:'premieres',
    105:'filters', 106:'classic', 107:'settings'
}
BACK_ACTIONS=(9,10,92,216)
ROW_IDS=(401,402)
VERSION='0.11.0'


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
        self.rail_items=[[],[]]
        for name,path in self.textures.items():
            self.setProperty('cinema_'+name,path)
        self.setProperty('app_version','v'+VERSION)
        self.setProperty('section_label','ÚVOD')
        self.setProperty('ui_status','Šipky = pohyb, OK = výběr, Zpět = předchozí obrazovka')
        self.setProperty('hero_title','BOŽSKÝ PŘEHRÁVAČ')
        self.setProperty('hero_info','Katalog ověřených souborů Webshare')
        self.setProperty('hero_plot','Nové filmy podle českých kinopremiér a jejich dostupnosti.')
        self.setProperty('hero_art','')
        try:
            self._screen('home',stack=False)
        except Exception:
            traceback.print_exc()
            self._fill('ZAČNĚTE VYHLEDÁVÁNÍM',[
                tile('HLEDAT FILM / SERIÁL','search'),
                tile('NASTAVENÍ WEBSHARE','settings'),
                tile('KLASICKÉ MENU','classic'),
            ],'DALŠÍ MOŽNOSTI',[], 'Webshare či ČSFD nyní neodpovídá.')

    def _loading(self,text):
        d=xbmcgui.DialogProgress()
        d.create('Božský přehrávač',text)
        return d

    def _fill(self,title1,cards1,title2,cards2,status=''):
        self.rail_items=[cards1 or [],cards2 or []]
        self.setProperty('row1_heading',title1)
        self.setProperty('row2_heading',title2)
        self.setProperty('ui_status',status or
            ('Božský přehrávač '+VERSION+' · pouze tituly dostupné na Webshare'))
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
                item.setProperty('quality',str(c.get('quality') or ''))
                item.setProperty('year',str(c.get('year') or ''))
                li.append(item)
            if li:
                lst.addItems(li)
        try:
            self.setFocusId(401 if cards1 else 402 if cards2 else 103)
        except RuntimeError:
            pass
        self._update_hero()

    def _selected(self,control_id=None):
        try:
            ident=control_id or self.getFocusId()
            if ident not in ROW_IDS:
                return None
            row=0 if ident==401 else 1
            position=self.getControl(ident).getSelectedPosition()
            if position<0:
                return None
            return self.rail_items[row][position]
        except (RuntimeError,IndexError,AttributeError):
            return None

    def _update_hero(self):
        c=self._selected()
        if not c:
            self.setProperty('hero_title','BOŽSKÝ PŘEHRÁVAČ')
            self.setProperty('hero_info','FILMY · SERIÁLY · HLEDÁNÍ')
            self.setProperty('hero_plot','Vyber kategorii nebo titul.')
            self.setProperty('hero_art','')
            return
        self.setProperty('hero_title',str(c.get('title') or ''))
        text=[str(c.get('year') or ''),str(c.get('genre') or ''),
              str(c.get('quality') or '')]
        if c.get('rating') is not None:
            text.append('ČSFD %s %%'%c['rating'])
        self.setProperty('hero_info','  ·  '.join(x for x in text if x)[:155])
        self.setProperty('hero_plot',str(c.get('plot') or '')[:480])
        self.setProperty('hero_art',str(c.get('fanart') or c.get('poster') or ''))

    def _refresh(self,view,context=None,stack=True):
        if stack:
            self.stack.append((self.mode,self.context))
        self._screen(view,context,stack=False)

    def _screen(self,view,context=None,stack=False):
        self.mode=view
        self.context=context
        self.setProperty('section_label',{
            'home':'DOMŮ','movies':'FILMY','shows':'SERIÁLY','premieres':'PREMIÉRY',
            'search':'VYHLEDÁVÁNÍ','seasons':'SÉRIE','episodes':'EPIZODY',
            'files':'VÝBĚR KVALITY'}.get(view,'KATALOG'))
        if view=='home':
            load=self._loading('Načítám dostupné filmy a česká metadata…')
            try:
                home=self.service.home()
                top=home['premieres'] or home['movies']
                bottom=home['shows'] or home['movies']
                if not top:
                    top=[tile('HLEDAT FILM','search'),tile('FILMY','movies')]
                if not bottom:
                    bottom=[tile('HLEDAT SERIÁL','search'),
                            tile('SERIÁLY','shows')]
                self._fill('ČESKÉ PREMIÉRY NA WEBSHARE' if home['premieres'] else
                           'DOSTUPNÉ FILMY',top,
                           'SERIÁLY' if home['shows'] else 'OBJEVIT DALŠÍ FILMY',
                           bottom,self.service.last_diagnostics)
            finally:load.close()
        elif view in ('movies','shows','premieres'):
            load=self._loading('Řadím dostupné tituly…')
            try:
                ordered=self.service.browse(view,self.sort,self.quality,self.language)
                if not ordered:
                    ordered=[tile('VYHLEDAT NÁZEV','search')]
                row_one=ordered[:16];row_two=ordered[16:32]
                self._fill('FILMY NA WEBSHARE' if view=='movies' else
                           'SERIÁLY NA WEBSHARE' if view=='shows' else
                           'PREMIÉRY PODLE ČSFD',row_one,'DALŠÍ TITULY',row_two,
                           'ŘAZENÍ: '+self.sort+' · KVALITA: '+self.quality+
                           ' · JAZYK: '+self.language)
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
                movies=[c for c in found if c['kind']=='movie']
                shows=[c for c in found if c['kind']=='show']
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
            view,ctx=self.stack.pop()
            self._screen(view,ctx)
        else:
            self.close()

    def _filters(self):
        choice=xbmcgui.Dialog().select('Katalog · filtrování a řazení',[
            'Řazení: '+self.sort,'Rozlišení: '+self.quality,
            'Jazyk: '+self.language,'Resetovat filtry'])
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
        else:
            self.sort='date';self.quality='all';self.language='all'
        self._screen(self.mode,self.context)

    def onFocus(self,control_id):
        self._update_hero()

    def onAction(self,action):
        if action.getId() in BACK_ACTIONS:
            self._go_back()
        else:
            self._update_hero()

    def onClick(self,control_id):
        if control_id in TOP_ACTIONS:
            command=TOP_ACTIONS[control_id]
            if command=='classic':
                self.destination=self.make_url(action='classic_menu')
                self.close()
            elif command=='settings':
                self.destination=self.make_url(action='settings')
                self.close()
            elif command=='filters':
                self._filters()
            else:
                self._refresh(command)
            return
        c=self._selected(control_id)
        if not c:return
        kind=c.get('kind')
        if kind=='none':
            return
        if kind in ('movies','shows','premieres','search'):
            self._refresh(kind)
        elif kind=='settings':
            self.destination=self.make_url(action='settings')
            self.close()
        elif kind=='classic':
            self.destination=self.make_url(action='classic_menu')
            self.close()
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
           metadata_factory,calendar_factory):
    from cinema_service_v2 import CinemaService
    from ws_availability import Availability
    from cinematic_home import ensure_textures
    metadata=metadata_factory() if addon.getSetting('smart_metadata')!='false' else None
    service=CinemaService(token,search_page,Availability(profile),
                          metadata,calendar_factory())
    win=CinemaScreen('bozsky-cinema-v2.xml',addon.getAddonInfo('path'),'Default','1080i')
    win.service=service
    win.textures=ensure_textures(profile)
    win.make_url=get_url
    win.destination=None
    win.is_play=False
    win.sort='date'
    win.quality='all'
    win.language='all'
    try:
        win.doModal()
        return win.destination,win.is_play
    finally:
        win.close()
        del win
