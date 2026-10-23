# -*- coding: utf-8 -*-
"""Pure-Python grouping and safe filename matching for Kodi search navigation.

File names can hint at video quality or Czech audio; they do not prove either.
No accounts, session tokens, streams, or passwords are cached by this module.
"""
from difflib import SequenceMatcher
import re

from novinky_catalogue import (normalize, parse_video_name, quality_score,
                               resolution, is_czech_audio_marked, is_hdr)

_YEAR = re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')
_EP = re.compile(r'(?i)\bs\d{1,2}[ ._-]*e\d{1,3}\b')


def clean_query(query):
    """Remove year and episode when comparing a typed title to release names."""
    query = _EP.sub(' ', query or '')
    query = _YEAR.sub(' ', query)
    return normalize(query)


def match_strength(title, query):
    title = normalize(title)
    query = clean_query(query)
    if not title or not query:
        return 0.0
    if title == query:
        return 1.0
    if title.startswith(query + ' '):
        return .86
    if query in title.split() and len(query) >= 5:
        return .75
    if len(query) >= 5 and query in title:
        return .70
    return SequenceMatcher(None, title, query).ratio() * .8


def visible_files(files, query, aliases=()):
    """Require a strong title match; catalog entries always originate in Webshare."""
    results, seen = [], set()
    targets = [query] + list(aliases)
    for f in files:
        ident = str(f.get('ident') or '')
        if not ident or ident in seen:
            continue
        if str(f.get('password','0')) == '1' or str(f.get('removed','0')) == '1':
            continue
        if str(f.get('available','1')) == '0' or str(f.get('copyrighted','0')) == '1':
            continue
        parsed = parse_video_name(f.get('name', ''))
        if not parsed or max(match_strength(parsed['title'],t) for t in targets if t) < .70:
            continue
        seen.add(ident)
        results.append((f, parsed))
    return results


def grouped(files, query, aliases=()):
    movies, shows = {}, {}
    for f, parsed in visible_files(files, query, aliases):
        strength = max(match_strength(parsed['title'],t) for t in [query]+list(aliases) if t)
        if parsed['kind'] == 'movie':
            key = (normalize(parsed['title']), parsed['year'])
            bag = movies
        else:
            key = normalize(parsed['title'])
            bag = shows
        if key not in bag:
            bag[key] = {'title':parsed['title'], 'year':parsed['year'],
                        'files':[], 'best':f, 'strength':strength,
                        'kind':'movie' if bag is movies else 'show'}
        g = bag[key]
        g['files'].append(f)
        if quality_score(f) > quality_score(g['best']):
            g['best'] = f
        g['strength'] = max(g['strength'],strength)
    def ordered(groups):
        return sorted(groups.values(), key=lambda g:(g['strength'], len(g['files']), quality_score(g['best'])), reverse=True)
    return {'movies':ordered(movies), 'shows':ordered(shows)}


def select_group(groups, kind, title, year=''):
    target=normalize(title)
    source=groups.get('movies' if kind=='movie' else 'shows', [])
    for g in source:
        if normalize(g['title']) == target and (kind!='movie' or g['year']==year):
            return g
    return None


def seasons(files):
    return sorted({int(p['season']) for f in files for p in [parse_video_name(f.get('name'))]
                   if p and p.get('kind')=='episode' and p.get('season') is not None})


def episodes(files, season):
    groups={}
    for f in files:
        p=parse_video_name(f.get('name'))
        if not p or p['kind']!='episode' or p.get('season')!=int(season):
            continue
        n=int(p['episode'])
        groups.setdefault(n, []).append(f)
    return [(number,sorted(group,key=quality_score,reverse=True)) for number,group in sorted(groups.items())]


def variants(files, season=None, episode=None, filter_name='all'):
    selected=[]
    for f in files:
        p=parse_video_name(f.get('name'))
        if not p:
            continue
        if episode is not None and (p['kind']!='episode' or p['season']!=int(season) or p['episode']!=int(episode)):
            continue
        if filter_name=='cz' and not is_czech_audio_marked(f.get('name','')):
            continue
        if filter_name=='4k' and resolution(f.get('name',''))!=2160:
            continue
        if filter_name=='1080' and resolution(f.get('name',''))<1080:
            continue
        selected.append(f)
    return sorted(selected,key=quality_score,reverse=True)


def compact_quality(f):
    res=resolution(f.get('name',''))
    result='4K' if res==2160 else ('%dp'%res if res else 'Kvalita ?')
    if is_hdr(f.get('name','')):
        result+=' HDR'
    if is_czech_audio_marked(f.get('name','')):
        result+=' | CZ*'
    return result
