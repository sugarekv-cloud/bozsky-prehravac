# -*- coding: utf-8 -*-
"""Catalog presentation and release-name parsing for Kodi; no Kodi dependency.

Real Webshare filenames are inconsistent: spaces, dots, commas, brackets,
CZ dabing, CZ subtitles, 2160p, 1080p, WEB-DL, x265, episodes S01E02.
A filename is a hint, never verified information about audio tracks.
"""
import re
from novinky_catalogue import (normalize, resolution, is_czech_audio_marked,
                                is_hdr, quality_score)

EXT = re.compile(r'\.(?:mkv|mp4|avi|m4v|mov|webm|wmv|ts|mpg|mpeg)$', re.I)
LANG_CZ = re.compile(
    r'(?<![a-z0-9])(?:cz|cze|czech|cesky|cestina|czdab|czdub|'
    r'cz[ ._-]*dabing|cesky[ ._-]*dabing|czech[ ._-]*dub|cz[ ._-]*audio|'
    r'cz[ ._-]*sk|czsk)(?![a-z0-9])', re.I)
CZ_SUBS = re.compile(
    r'(?<![a-z0-9])(?:cz[ ._-]*sub(?:s|titles)?|czech[ ._-]*sub(?:s|titles)?|'
    r'cz[ ._-]*titulky|ceske[ ._-]*titulky|titulky)(?![a-z0-9])', re.I)
AUDIO_EXPLICIT = re.compile(r'(?i)(?:cz[ ._-]*dabing|cz[ ._-]*dub|'
                            r'czech[ ._-]*dub|cesky[ ._-]*dabing|cz[ ._-]*audio)')
SOURCE = [
    ('Remux', r'(?i)\bremux\b'),
    ('Blu-ray', r'(?i)(?:blu[ ._-]*ray|bdrip|brrip|bdremux)'),
    ('WEB-DL', r'(?i)web[ ._-]*dl'),
    ('WEBRip', r'(?i)(?:webrip|web[ ._-]*rip)'),
    ('HDTV', r'(?i)hdtv'),
    ('DVD', r'(?i)(?:dvd[ ._-]*rip|dvdrip)'),
    ('CAM', r'(?i)\b(?:cam|telesync|tsrip|hdcam)\b'),
]
CODEC = [
    ('AV1',r'(?i)\bav1\b'),
    ('HEVC',r'(?i)(?:x265|h[ ._-]*265|hevc)'),
    ('H.264',r'(?i)(?:x264|h[ ._-]*264|avc)'),
    ('XviD',r'(?i)\bxvid\b'),
]
RES = re.compile(r'(?<!\d)(2160p|1080[pi]|720p|480p|4320p)(?!\d)',re.I)
YEAR = re.compile(r'(?<!\d)((?:19|20)\d{2})(?!\d)')


def release_details(name):
    name = str(name or '')
    # Explicit resolution is stronger than the tag "4K remaster".
    m = RES.search(name)
    if m:
        res = int(re.match(r'\d+',m.group(1)).group())
    elif re.search(r'(?i)(?<!\w)(?:4k|uhd)(?!\w)',name):
        res = 2160
    else:
        res = resolution(name)
    source = next((text for text,pattern in SOURCE if re.search(pattern,name)),'')
    codec = next((text for text,pattern in CODEC if re.search(pattern,name)),'')
    tag = 'HDR' if is_hdr(name) else ''
    if re.search(r'(?i)(?<!\w)(?:dovi|dolby[ ._-]*vision|dv)(?!\w)', name):
        tag='Dolby Vision'
    if CZ_SUBS.search(name) and not AUDIO_EXPLICIT.search(name):
        lang = 'CZ titulky'
    elif LANG_CZ.search(name) or is_czech_audio_marked(name):
        lang = 'CZ (název)'
    elif re.search(r'(?i)\bmulti\b|\bdual\b',name):
        lang = 'MULTi / DUAL (?)'
    else:
        lang = 'Jazyk ?'
    try:
        return {'resolution':res,'source':source,'codec':codec,
                'hdr':tag,'language':lang}
    except (ValueError, TypeError):
        return {'resolution':0,'source':source,'codec':codec,
                'hdr':tag,'language':lang}


def prefers_cz(file):
    return release_details(file.get('name',''))['language']=='CZ (název)'


def file_score(file):
    d=release_details(file.get('name',''))
    src={'Remux':80,'Blu-ray':65,'WEB-DL':50,'WEBRip':35,
         'HDTV':20,'DVD':15,'CAM':-350}.get(d['source'],0)
    try:
        size=int(file.get('size') or 0)
    except (ValueError, TypeError):
        size=0
    return (d['resolution']*10 + (260 if prefers_cz(file) else 0) +
            (35 if d['hdr'] else 0)+src+min(size//(1024**3),60))


def file_label(file):
    d=release_details(file.get('name',''))
    qual='4K' if d['resolution']==2160 else ('%sp'%d['resolution'] if d['resolution'] else 'SD / ?')
    tags=[qual]
    tags.extend(x for x in (d['hdr'],d['source'],d['codec'],d['language']) if x)
    try:
        gb=int(file.get('size') or 0)/(1024**3)
        if gb>.1:
            tags.append('%.1f GB'%gb)
    except (ValueError, TypeError):
        pass
    return '  ·  '.join(tags)


def sort_files(files):
    return sorted(files,key=file_score,reverse=True)


def is_visible(group, quality='all', language='all', hdr=False, year='all'):
    files=group.get('files') or []
    if year not in ('all','') and str(group.get('year') or '')!=str(year):
        # Some filenames do not contain a year; do not silently classify them.
        return False
    for f in files:
        d=release_details(f.get('name',''))
        if quality=='4k' and d['resolution']<2160:
            continue
        if quality=='1080' and d['resolution']<1080:
            continue
        if quality=='720' and d['resolution']<720:
            continue
        if language=='cz' and not prefers_cz(f):
            continue
        if hdr and not d['hdr']:
            continue
        return True
    return False


SORT_LABELS={'recent':'Nejnovější na Webshare','title':'Abecedně A–Z',
             'year':'Podle roku vydání','quality':'Nejvyšší kvalita',
             'rating':'Hodnocení ČSFD','size':'Největší soubory'}
QUALITY_LABELS={'all':'Všechny kvality','720':'720p a vyšší',
                '1080':'Full HD a vyšší','4k':'Pouze 4K'}
LANG_LABELS={'all':'Všechny jazyky','cz':'Označení CZ (není ověřený dabing)'}


def sort_groups(groups, sort='recent'):
    if sort=='recent':
        return list(groups)
    if sort=='title':
        return sorted(groups,key=lambda g:normalize((g.get('metadata') or {}).get('title') or g['title']))
    if sort=='year':
        return sorted(groups,key=lambda g:int((g.get('metadata') or {}).get('year') or g.get('year') or 0),reverse=True)
    if sort=='quality':
        return sorted(groups,key=lambda g:file_score(g['best']),reverse=True)
    if sort=='rating':
        return sorted(groups,key=lambda g:((g.get('metadata') or {}).get('rating') or -1),reverse=True)
    if sort=='size':
        return sorted(groups,key=lambda g:max((int(f.get('size') or 0) for f in g.get('files',[])),default=0),reverse=True)
    return list(groups)


def filter_groups(groups,quality='all',language='all',hdr=False,year='all'):
    return [g for g in groups if is_visible(g,quality,language,hdr,year)]
