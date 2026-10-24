# -*- coding: utf-8 -*-
"""Kodi-independent grouping for a CSFD-enriched, Webshare-backed catalog.

Titles/plot/art may come from Czech metadata. Cards NEVER come from metadata
alone: every card is backed by a verified Webshare ident.
"""
from collections import OrderedDict
from novinky_catalogue import normalize, parse_video_name, quality_score
from catalog_engine import file_label, file_score

def acceptable(f):
    if not f or not f.get('ident') or not f.get('name'):
        return False
    for key in ('password','removed','adult'):
        if str(f.get(key) or '0') == '1':
            return False
    if str(f.get('available') or '1') == '0':
        return False
    return bool(parse_video_name(f['name']))

def groups(files, kind):
    by_key = OrderedDict()
    seen = set()
    for f in files or []:
        if not acceptable(f) or f['ident'] in seen:
            continue
        seen.add(f['ident'])
        p = parse_video_name(f['name'])
        if kind == 'show' and p['kind'] not in ('episode','series'):
            continue
        if kind == 'movie' and p['kind'] != 'movie':
            continue
        # Show identities never contain year: retain seasons from different
        # file naming conventions and from separate search pages.
        key = (normalize(p['title']), p['year'] if kind=='movie' else '')
        if key not in by_key:
            by_key[key] = {'title':p['title'], 'year':p['year'] if kind=='movie' else '',
                           'group_kind':'show' if kind=='show' else 'movie',
                           'kind':kind, 'files':[], 'best':f, 'metadata':None}
        g=by_key[key]
        g['files'].append(f)
        if file_score(f) > file_score(g['best']):
            g['best'] = f
    return list(by_key.values())

def verified_groups(raw, availability, maximum=24, checked=65):
    """Bounded parallel checks; skip dead first files and keep searching."""
    result=[]
    candidates=raw[:checked]
    for pos in range(0,len(candidates),12):
        group=candidates[pos:pos+12]
        result.extend(availability.check_groups(group,max_workers=6))
        if len(result)>=maximum:
            break
    return result[:maximum]

def add_metadata(groups_list, client, maximum=12):
    if client and groups_list:
        client.lookup_many(groups_list[:maximum],max_new=maximum)
        client.save()
    return groups_list

def card(group, tag=''):
    from cinematic_catalog import webshare_image_url
    meta=group.get('metadata') or {}
    best=group['best']
    return {
        'title':meta.get('title') or group['title'],
        'raw':group['title'], 'year':meta.get('year') or group.get('year') or '',
        'file_year':group.get('year') or '',
        'poster':meta.get('poster') or webshare_image_url(best.get('img')),
        'fanart':meta.get('fanart') or '',
        'plot':meta.get('plot') or 'Soubor nalezen na Webshare. Vyber kvalitu a jazyk.',
        'genre':', '.join(meta.get('genres') or []),
        'rating':meta.get('rating'), 'rating_source':meta.get('rating_source') or 'ČSFD',
        'quality':file_label(best),
        'kind':group['kind'], 'tag':tag,'ident':best['ident'],
        'files':group['files'], 'original':meta.get('original') or '',
        'count':len(group['files'])
    }

def sort_cards(cards, key='date'):
    if key=='title':
        return sorted(cards,key=lambda c:normalize(c['title']))
    if key=='year':
        return sorted(cards,key=lambda c:int(c.get('year') or 0),reverse=True)
    if key=='rating':
        return sorted(cards,key=lambda c:c.get('rating') or -1,reverse=True)
    if key=='quality':
        return sorted(cards,key=lambda c:max([file_score(f) for f in c['files']] or [0]),reverse=True)
    return list(cards)

def grouped_episodes(files, title, aliases=()):
    """Sort by numeric season+episode, deduplicate different quality versions."""
    wanted={normalize(name) for name in (title,)+tuple(aliases) if name}
    result={}
    for f in files:
        if not acceptable(f):
            continue
        p=parse_video_name(f['name'])
        if p['kind']!='episode' or normalize(p['title']) not in wanted:
            continue
        k=(p['season'],p['episode'])
        result.setdefault(k,[]).append(f)
    output=OrderedDict()
    for (season,episode),variants in sorted(result.items()):
        output.setdefault(season,OrderedDict())[episode]=sorted(
            variants,key=file_score,reverse=True)
    return output

def choose_files(files, quality='all', language='all'):
    from catalog_engine import release_details, prefers_cz
    kept=[]
    seen=set()
    for f in files:
        if not acceptable(f) or f['ident'] in seen:
            continue
        seen.add(f['ident'])
        details=release_details(f['name'])
        if quality=='4k' and details['resolution']<2160:
            continue
        if quality=='1080' and details['resolution']<1080:
            continue
        if language=='cz' and not prefers_cz(f):
            continue
        kept.append(f)
    return sorted(kept,key=file_score,reverse=True)

def collect_pages(fetch, token, title, max_pages=5, sort='recent'):
    """Don't silently truncate a series after Webshare's first 100 results."""
    result=[]
    seen=set()
    for page in range(max_pages):
        files,total=fetch(token,page*100,title,sort=sort)
        if files is None:
            return None if page==0 else result
        for f in files:
            if f.get('ident') not in seen and acceptable(f):
                result.append(f)
                seen.add(f['ident'])
        if len(files)<100 or (total and (page+1)*100>=total):
            break
    return result

def matching_release(files, aliases, kind='movie', year=''):
    targets={normalize(a) for a in aliases if a}
    result=[]
    for f in files or []:
        if not acceptable(f):
            continue
        p=parse_video_name(f['name'])
        if normalize(p['title']) not in targets:
            continue
        if kind=='movie' and p['kind']!='movie':
            continue
        if kind=='show' and p['kind'] not in ('series','episode'):
            continue
        if year and p['year'] and str(year)!=p['year']:
            continue
        result.append(f)
    return result
