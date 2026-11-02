# -*- coding: utf-8 -*-
"""Single-purpose Kodi fullscreen detail dialog for verified KIVORA titles.

No network work or PlayMedia happens while the nested dialog is active.
The caller handles playback only after this window has closed.
"""
import xbmcgui

BACK_ACTIONS=(9,10,92,216)

def _meta(card):
    parts=[]
    year=str(card.get('year') or card.get('file_year') or '').strip()
    if year:
        parts.append(year)
    genre=str(card.get('genre') or '').strip()
    if genre:
        parts.append(genre[:70])
    rating=card.get('rating')
    source=str(card.get('rating_source') or '').casefold()
    if source in ('čsfd','csfd','czdb'):
        try:
            value=round(float(rating))
            if 0<value<=100:
                parts.append('ČSFD %d %%'%value)
        except (TypeError,ValueError,OverflowError):
            pass
    return '   ·   '.join(parts)[:170]

class CinemaDetail(xbmcgui.WindowXMLDialog):
    def onInit(self):
        card=self.card
        texture_map={
            'background':'background',
            'fade':'fade',
            'cta_focus':'cta_focus',
            'cta':'cta',
            'button':'button'
        }
        for key,target in texture_map.items():
            self.setProperty('detail_'+key,self.textures.get(target,''))
        self.setProperty('detail_title',str(card.get('title') or 'Bez názvu')[:170])
        self.setProperty('detail_meta',_meta(card))
        self.setProperty('detail_plot',str(self.description or
            'Český popis z ČSFD zatím není k dispozici.')[:2200])
        self.setProperty('detail_quality',(
            'DOSTUPNÉ VERZE  ·  '+str(card.get('quality'))[:60])
            if card.get('quality') else 'VYBER VERZI PRO PŘEHRÁNÍ')
        self.setProperty('detail_art',str(card.get('fanart') or ''))
        self.setProperty('detail_poster',str(card.get('poster') or ''))
        self.setProperty('detail_primary',
            'VYBRAT EPIZODU' if card.get('kind')=='show' else 'VYBRAT VERZI')
        try:
            self.setFocusId(301)
        except (RuntimeError,TypeError,AttributeError):
            pass

    def onClick(self,control_id):
        commands={301:'open',302:'trailer',303:'favorite',304:'back'}
        if control_id in commands:
            self.result=commands[control_id]
            self.close()

    def onAction(self,action):
        if action.getId() in BACK_ACTIONS:
            self.result='back'
            self.close()

def choose_detail(addon,textures,card,description):
    if not isinstance(card,dict) or card.get('kind') not in ('movie','show'):
        return 'back'
    window=CinemaDetail('fckyo-detail-v1.xml',addon.getAddonInfo('path'),
                        'Default','1080i')
    window.card=card
    window.textures=textures
    window.description=description
    window.result='back'
    try:
        window.doModal()
        return window.result
    finally:
        # Dispose before opening series/stream catalogue. Never start player
        # within a second active WindowXMLDialog on Android TV.
        del window
