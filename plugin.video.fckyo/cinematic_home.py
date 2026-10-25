# -*- coding: utf-8 -*-
"""TV-first, remote-friendly Kodi home window for Božský přehrávač.

Only navigates into the existing playback/search handlers. Playback remains
manual and Webshare credentials never leave the add-on.
"""
import os
import struct
import traceback
import zlib
import math

import xbmcgui

XML_NAME = 'bozsky-cinema.xml'
WINDOW_BUTTONS = {
    101: ('catalog_home', {'kind':'movie'}),
    102: ('catalog_home', {'kind':'show'}),
    103: ('smart_search', {}),
    104: ('novinky', {}),
    105: ('catalog_controls', {'kind':'movie'}),
    106: ('classic_menu', {}),
    107: ('settings', {}),
}
ROW_IDS = (401, 402)
BACK_ACTIONS = (9, 10, 92, 216)


def _chunk(name, data):
    return (struct.pack('>I', len(data)) + name + data +
            struct.pack('>I', zlib.crc32(name + data) & 0xffffffff))


def _rgba_png(path, width, height, kind):
    """Generate UI textures with Python stdlib; no external assets or PIL needed."""
    if os.path.isfile(path):
        return path
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            if kind == 'background':
                h = y / float(max(1,height-1))
                color = (int(7+5*h),int(9+5*h),int(20+12*h),255)
            elif kind == 'fade':
                a = int(250-220*x/float(max(1,width-1)))
                color = (7,9,20,a)
            elif kind in ('gear','gear_dark'):
                # Crisp 8-tooth settings icon with a transparent center.
                cx=(x-(width-1)/2.0)/(min(width,height))
                cy=(y-(height-1)/2.0)/(min(width,height))
                radial=math.hypot(cx,cy)
                theta=math.atan2(cy,cx)
                outer=0.39 if math.cos(8*theta)>0.28 else 0.305
                if 0.132 < radial <= outer:
                    color = (18,18,23,255) if kind=='gear_dark' else (238,238,241,255)
                else:
                    color = (0,0,0,0)
            elif kind == 'focus':
                color = (157,109,255,255)
            elif kind == 'chip':
                color = (8,10,21,220)
            elif kind == 'nav_hover':
                color = (43,35,72,235)
            elif kind == 'tile':
                # Rounded graphite surface with a subtle violet edge/glow.
                radius=8
                dx=max(radius-x,0,x-(width-radius-1))
                dy=max(radius-y,0,y-(height-radius-1))
                outside=(dx*dx+dy*dy)>radius*radius
                if outside:
                    color=(0,0,0,0)
                else:
                    top=1-y/float(max(1,height-1))
                    edge=(x<=1 or x>=width-2 or y<=1 or y>=height-2)
                    accent=max(0,1-math.hypot(x-width*.74,y-height*.20)/
                                        float(max(1,width)))
                    color=(int(19+12*top+10*accent),
                           int(22+7*top+5*accent),
                           int(37+16*top+25*accent),255)
                    if edge:
                        color=(63,55,91,230)
            else:
                color = (28,30,48,255)
            raw.extend(color)
    header = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    data = header + _chunk(b'IHDR',ihdr)
    data += _chunk(b'IDAT',zlib.compress(bytes(raw),6))
    data += _chunk(b'IEND',b'')
    tmp = path + '.tmp'
    with open(tmp,'wb') as f:
        f.write(data)
    os.replace(tmp,path)
    return path


def ensure_textures(profile):
    folder = os.path.join(profile, 'cinematic_ui')
    if not os.path.isdir(folder):
        os.makedirs(folder)
    specs = {'background':(128,72), 'fade':(256,72),
             'focus':(2,2), 'button':(2,2),
             'gear':(96,96), 'gear_dark':(96,96),
             'chip':(2,2),'nav_hover':(2,2),'tile':(128,72)}
    result = {}
    for kind,(w,h) in specs.items():
        result[kind] = _rgba_png(os.path.join(folder,'stream_v5_'+kind+'.png'),w,h,kind)
    return result


def _fallback_card(addon, label, target):
    return {'title':label,'file_title':'','year':'','poster':'','fanart':'',
        'plot':'Otevřít katalog, nastavení nebo vyhledávání.',
        'quality':'','genre':'','rating':None,'kind':'link','url':target,
        'original':'','files':0}


class CinemaWindow(xbmcgui.WindowXMLDialog):
    def onInit(self):
        textures = self.textures
        for kind,path in textures.items():
            self.setProperty('cinema_'+kind,path)
        self.setProperty('hero_title','KIVORA')
        self.setProperty('hero_info','Všechny dostupné filmy na jednom místě')
        self.setProperty('hero_plot','Pohyb šipkami • OK pro výběr • Zpět pro návrat')
        self.setProperty('hero_art','')
        self.setProperty('row1_heading',self.row1_heading)
        self.setProperty('row2_heading',self.row2_heading)
        self.setProperty('ui_status',self.status)
        for index,control_id in enumerate(ROW_IDS):
            row = self.cards[index]
            items = []
            for card in row:
                li=xbmcgui.ListItem(label=card.get('title',''))
                art = {}
                if card.get('poster'):
                    art.update({'poster':card['poster'], 'thumb':card['poster']})
                if card.get('fanart'):
                    art['fanart'] = card['fanart']
                if art:
                    li.setArt(art)
                li.setProperty('quality',card.get('quality') or '')
                li.setProperty('year',str(card.get('year') or ''))
                li.setProperty('kind',card.get('kind') or '')
                items.append(li)
            self.getControl(control_id).addItems(items)
        try:
            self.setFocusId(401 if self.cards[0] else 101)
        except (TypeError, RuntimeError):
            self.setFocusId(101)
        self._update_hero()

    def _selected_card(self):
        try:
            ctrl = self.getFocusId()
            if ctrl not in ROW_IDS:
                return None
            index = self.getControl(ctrl).getSelectedPosition()
            row = self.cards[0 if ctrl==401 else 1]
            return row[index] if 0 <= index < len(row) else None
        except (RuntimeError, AttributeError, IndexError):
            return None

    def _update_hero(self):
        card=self._selected_card()
        if not card:
            return
        self.setProperty('hero_title',card.get('title') or '')
        info=[str(card.get('year') or ''),card.get('genre') or '',
              card.get('quality') or '']
        rating=card.get('rating')
        if rating is not None:
            info.append('ČSFD %s %%'%rating)
        self.setProperty('hero_info','   ·   '.join(x for x in info if x)[:210])
        self.setProperty('hero_plot',(card.get('plot') or '')[:400])
        self.setProperty('hero_art',card.get('fanart') or
                         card.get('poster') or '')

    def _navigate(self, target):
        self.destination = target
        self.close()

    def onFocus(self, control_id):
        self._update_hero()

    def onAction(self, action):
        if action.getId() in BACK_ACTIONS:
            self.close()
            return
        self._update_hero()

    def onClick(self, control_id):
        if control_id in WINDOW_BUTTONS:
            action,params=WINDOW_BUTTONS[control_id]
            self._navigate(self.make_url(action=action,**params))
            return
        if control_id not in ROW_IDS:
            return
        card=self._selected_card()
        if not card:
            return
        if card.get('kind')=='link':
            self._navigate(card['url'])
            return
        if card['kind']=='show':
            self._navigate(self.make_url(action='novinky_show',
                                         title=card['file_title']))
        else:
            self._navigate(self.make_url(
                action='novinky_detail', title=card['file_title'],
                year=card.get('file_year') or '',
                original=card.get('original') or '',kind='movie'))


def launch(addon, profile, get_url, revalidate, search_page, catalogue_factory):
    """Return a plugin URL selected in cinematic UI, or None on Back."""
    from cinematic_catalog import make_rows
    from cinematic_discovery import discover, empty_message
    from ws_availability import Availability
    cards=[]
    status='Vyberte film nebo seriál; přehrání je vždy ruční'
    heading='NOVÉ SERIÁLY'
    top_heading='NOVĚ PŘIDANÉ FILMY NA WEBSHARE'
    if addon.getSetting('wsuser') and addon.getSetting('wspass'):
        progress=None
        try:
            progress=xbmcgui.DialogProgress()
            progress.create('Božský přehrávač', 'Načítám dostupné filmy z Webshare…')
            token=revalidate()
            if token:
                recent,popular,stats=discover(token,search_page)
                progress.update(55,'Ověřuji dostupnost videí a načítám plakáty…')
                checked=Availability(profile)
                metadata=(catalogue_factory() if addon.getSetting('smart_metadata')!='false' else None)
                groups=make_rows(recent,popular,checked,metadata,limit=11)
                cards=[groups['new_movies'],groups['discover']]
                heading=groups['discover_title']
                status=empty_message(stats,len(cards[0]),len(cards[1]))
                if (cards[0] or cards[1]) and not any(
                        c.get('poster') for row in cards for c in row):
                    status=('Videa na Webshare nalezena, ale zdroj neposkytl '
                            'plakáty ani náhledy. Vyberte film podle názvu.')
                if not cards[0] and cards[1]:
                    cards[0],cards[1]=cards[1],[]
                    top_heading=heading
                    heading='DALŠÍ DOPORUČENÍ'
            else:
                status='Webshare vyžaduje přihlášení. Otevřete Nastavení.'
        except Exception:
            traceback.print_exc()
            status='Načtení Webshare se nezdařilo. Zkuste Hledat nebo Nastavení.'
        finally:
            if progress is not None:
                progress.close()
    else:
        status='Nejdříve v Nastavení zadejte účet Webshare.'
    if not cards:
        cards=[[],[]]
    if not cards[0]:
        cards[0]=[_fallback_card(addon,'VYHLEDAT FILM',get_url(action='smart_search')),
                  _fallback_card(addon,'KATALOG FILMŮ',get_url(action='catalog_home',kind='movie')),
                  _fallback_card(addon,'NASTAVENÍ WEBSHARE',get_url(action='settings'))]
        top_heading='ZAČNĚTE VÝBĚREM'
    if not cards[1]:
        cards[1]=[_fallback_card(addon,'PROCHÁZET SERIÁLY',get_url(action='catalog_home',kind='show')),
                  _fallback_card(addon,'NOVINKY',get_url(action='novinky')),
                  _fallback_card(addon,'POKROČILÉ FILTRY',get_url(action='catalog_controls',kind='movie'))]
        heading='PROZKOUMEJTE DALŠÍ OBSAH'
    dialog=CinemaWindow(XML_NAME,addon.getAddonInfo('path'),'Default','1080i')
    dialog.cards=cards
    dialog.row1_heading=top_heading
    dialog.row2_heading=heading
    dialog.default_icon=os.path.join(addon.getAddonInfo('path'),'resources','icon.png')
    dialog.textures=ensure_textures(profile)
    dialog.make_url=get_url
    dialog.destination=None
    dialog.status=status
    try:
        dialog.doModal()
        return dialog.destination
    finally:
        dialog.close()
        del dialog
