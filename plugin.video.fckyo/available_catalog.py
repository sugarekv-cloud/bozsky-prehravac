# -*- coding: utf-8 -*-
"""Catalog from Webshare search results only; CSFD metadata never creates a card."""
from novinky_catalogue import normalize, parse_video_name, quality_score

def names_for(title, original='', metadata=None):
    names = [title, original]
    if metadata:
        names.extend([metadata.get('title',''), metadata.get('original','')])
    result = []
    for n in names:
        if n and normalize(n) not in [normalize(x) for x in result]:
            result.append(n.strip())
    return result

def matching_movies(files, aliases, year=''):
    """Conservative title comparison: exclude trailers, series, locked and removed files."""
    targets = {normalize(t) for t in aliases if normalize(t)}
    seen = set()
    matched = []
    for f in files:
        ident = str(f.get('ident') or '')
        if not ident or ident in seen:
            continue
        if str(f.get('password','0')) == '1' or str(f.get('removed','0')) == '1':
            continue
        if str(f.get('available','1')) == '0' or str(f.get('copyrighted','0')) == '1':
            continue
        p = parse_video_name(f.get('name',''))
        if not p or p['kind'] != 'movie' or normalize(p['title']) not in targets:
            continue
        if year and p.get('year') and str(year) != p['year']:
            continue
        seen.add(ident)
        matched.append(f)
    return sorted(matched, key=quality_score, reverse=True)

def group_id(group):
    meta = group.get('metadata') or {}
    uid = meta.get('uid')
    if uid:
        return 'csfd-' + str(uid)
    return 'title-' + normalize(group['title']) + '@' + str(group.get('year') or '')

def localize_groups(groups):
    """Only merges file-backed groups; never synthesizes titles from CSFD results."""
    combined = {}
    order = []
    for g in groups:
        if not g.get('files'):
            continue
        ident = group_id(g)
        if ident not in combined:
            out = dict(g)
            out['id'] = ident
            out['files'] = []
            combined[ident] = out
            order.append(ident)
        dest = combined[ident]
        for f in g['files']:
            if f.get('ident') not in {v.get('ident') for v in dest['files']}:
                dest['files'].append(f)
        if quality_score(g['best']) > quality_score(dest['best']):
            dest['best'] = g['best']
        dest['strength'] = max(dest.get('strength',0),g.get('strength',0))
        if g.get('metadata') and not dest.get('metadata'):
            dest['metadata'] = g['metadata']
    return [combined[k] for k in order]

def find_group(groups, ident):
    return next((g for g in groups if g.get('id') == ident), None)

def display_name(group):
    meta = group.get('metadata') or {}
    return meta.get('title') or group.get('title','')
