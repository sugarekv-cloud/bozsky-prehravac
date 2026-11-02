# -*- coding: utf-8 -*-
"""Small, transparent set of broadcaster-distributed free live TV streams.

Stream URLs are fixed HTTPS CDN URLs associated with free-to-view channels.
No subscription circumvention, scraped pay-TV or dubious IPTV mirror.
The list can be edited on a future update after confirming broadcaster terms.
Availability and geoblocking can change. Kodi handles HLS bitrate selection.
"""
import io
import json
import os
from urllib.parse import urlparse

CHANNELS=(
    {
        'id':'ocko',
        'title':'ÓČKO',
        'group':'HUDEBNÍ',
        'plot':'Česká hudební televize. Živé vysílání z distribučního CDN; program se může měnit.',
        'url':'https://ocko-live-dash.ssl.cdn.cra.cz/cra_live2/ocko.stream.1.smil/playlist.m3u8',
        'website':'https://ocko.tv/zive',
    },
    {
        'id':'ocko_expres',
        'title':'ÓČKO EXPRES',
        'group':'HUDEBNÍ',
        'plot':'Současná elektronická hudba a videoklipy. Bezplatný stream veřejné distribuce.',
        'url':'https://ocko-live.ssl.cdn.cra.cz/channels/ocko_expres/playlist.m3u8',
        'website':'https://ocko.tv/zive',
    },
    {
        'id':'ocko_star',
        'title':'ÓČKO STAR',
        'group':'HUDEBNÍ',
        'plot':'Hudební hity a retro klipy. Bezplatné televizní vysílání.',
        'url':'https://ocko-live-dash.ssl.cdn.cra.cz/cra_live2/ocko_gold.stream.1.smil/playlist.m3u8',
        'website':'https://ocko.tv/zive',
    },
    {
        'id':'polar',
        'title':'TV POLAR',
        'group':'REGIONÁLNÍ',
        'plot':'Moravskoslezské regionální zpravodajství a publicistika. Živé vysílání.',
        'url':'https://stream.polar.cz/polar/polarlive-1/playlist.m3u8',
        'website':'https://polar.cz/jak-naladit',
    },
    {
        'id':'prahatv',
        'title':'PRAHA TV',
        'group':'REGIONÁLNÍ',
        'plot':'Regionální pořady, informace a zprávy z Prahy a okolí.',
        'url':'https://stream.polar.cz/prahatv/prahatvlive-1/playlist.m3u8',
        'website':'https://prahatv.eu/',
    },
)
CT_ADDON_ID='plugin.video.ivysilani.cz'
CT_PLUGIN_URL='plugin://plugin.video.ivysilani.cz/'
CT_TITLE='ČESKÁ TELEVIZE · iVysílání'
_FAVFILE='kivora-live-tv-favorites.json'


def channel(ident):
    return next((entry for entry in CHANNELS if entry['id']==str(ident)),None)


def playable_url(ident):
    """Resolve ONLY a whitelisted, trusted channel ID to its known HTTPS URL."""
    entry=channel(ident)
    if not entry:
        return ''
    address=entry['url']
    parsed=urlparse(address)
    if parsed.scheme!='https' or parsed.hostname not in (
        'ocko-live-dash.ssl.cdn.cra.cz','ocko-live.ssl.cdn.cra.cz',
        'stream.polar.cz',
    ):
        return ''
    if not parsed.path.endswith('.m3u8'):
        return ''
    return address


def favorites(profile):
    if not profile:
        return []
    path=os.path.join(profile,_FAVFILE)
    try:
        if os.path.getsize(path)>8192:
            return []
        with io.open(path,'r',encoding='utf8') as f:
            data=json.load(f)
        if not isinstance(data,list):
            return []
        return [x for x in dict.fromkeys(data) if channel(x)]
    except (OSError,ValueError,TypeError):
        return []


def toggle_favorite(profile,ident):
    """One local JSON file; save IDs only, never URL or streaming credentials."""
    if not profile or not channel(ident):
        return False
    chosen=favorites(profile)
    if ident in chosen:
        chosen.remove(ident)
    else:
        chosen.append(ident)
    try:
        if not os.path.isdir(profile):
            os.makedirs(profile)
        path=os.path.join(profile,_FAVFILE)
        temporary=path+'.tmp'
        with io.open(temporary,'w',encoding='utf8') as f:
            json.dump(chosen,f,ensure_ascii=False)
        os.replace(temporary,path)
        return ident in chosen
    except OSError:
        return False


def tv_cards(profile='',art_dir=''):
    fav=set(favorites(profile))
    def entry(info):
        artwork=os.path.join(art_dir,'live_'+info['id']+'.png') if art_dir else ''
        if artwork and not os.path.isfile(artwork):
            artwork=''
        return {'kind':'tv_channel','title':info['title'],'raw':info['title'],
                'ident':'tv:'+info['id'],'channel_id':info['id'],
                'genre':info['group'],'plot':info['plot'],
                'poster':artwork,'fanart':'',
                'quality':'ŽIVĚ · ZDARMA','is_favorite':info['id'] in fav}
    tiles=[entry(c) for c in CHANNELS]
    saved=[c for c in tiles if c['is_favorite']]
    return saved,tiles


def ct_card():
    return {'kind':'tv_addon','title':CT_TITLE,'ident':'tv:ct',
            'genre':'VEŘEJNOPRÁVNÍ',
            'plot':'Otevře samostatný doplněk iVysílání České televize. Instalace doplňku je potřeba zvlášť; některé pořady jsou geograficky omezené.',
            'quality':'ŽIVÁ TV · ARCHIV','poster':'','fanart':''}
