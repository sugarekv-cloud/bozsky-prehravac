# -*- coding: utf-8 -*-
"""Unified, release-backed film/series identity and poster de-duplication.

Merge alternate Webshare filenames and Czech/English catalogue names WITHOUT
merging distinct remakes or collapsing two different episodes. This module
accepts only cards that already contain verified file identifiers.
"""
from collections import OrderedDict
from novinky_catalogue import normalize
from catalog_engine import file_score, file_label
from cinema_search_v3 import MOVIE_SEEDS, SHOW_SEEDS


def _year(card):
    value=str(card.get('file_year') or card.get('year') or '').strip()
    return value if len(value)==4 and value.isdigit() else ''


def _names(card):
    items=[card.get('raw'),card.get('title'),card.get('original')]
    items.extend(card.get('aliases') or [])
    return {normalize(x) for x in items if normalize(x)}


# A fixed release year keeps similarly named remakes apart.
_SEED_NAMES={}
for _kind,_seeds in (('movie',MOVIE_SEEDS),('show',SHOW_SEEDS)):
    for _cz,_original,_release_year in _seeds:
        canonical=normalize(_original)
        for _name in (_cz,_original):
            _SEED_NAMES[(_kind,normalize(_name),str(_release_year) if
                         _kind=='movie' else '')]=canonical

# A missing release year is common in filename variants. Map an alias only
# if it corresponds to a single reference title; otherwise keep it ambiguous.
_ALIASES={}
for (_kind,_alias,_year),_canonical in _SEED_NAMES.items():
    _ALIASES.setdefault((_kind,_alias),set()).add(_canonical)
_UNAMBIGUOUS={key:next(iter(values)) for key,values in _ALIASES.items()
              if len(values)==1}


def _canonical_name(card):
    kind=card.get('kind') or 'movie'
    year=_year(card) if kind=='movie' else ''
    names=_names(card)
    # Favor an exact known title, not broad substring matching.
    for n in sorted(names):
        key=(kind,n,year)
        if key in _SEED_NAMES:
            return _SEED_NAMES[key]
    if not year:
        for n in sorted(names):
            if (kind,n) in _UNAMBIGUOUS:
                return _UNAMBIGUOUS[(kind,n)]
    original=normalize(card.get('original') or '')
    raw=normalize(card.get('raw') or '')
    return original or raw or normalize(card.get('title') or '')


def identity(card):
    """(kind, canonical title, known release year); no-video tiles are skipped."""
    return (card.get('kind') or 'movie',_canonical_name(card),
            _year(card) if card.get('kind')!='show' else '')


def _stronger(a,b):
    """Prefer actual metadata artwork and description over a blank screenshot."""
    def value(c):
        return (int(bool(c.get('poster')))*8 +
                int(bool(c.get('fanart')))*3 +
                int(bool(c.get('plot')) and
                    'Soubor nalezen' not in str(c.get('plot')))*4 +
                int(c.get('rating') is not None)*3 +
                int(bool(c.get('genre')))*2 +
                int(bool(c.get('original'))))
    return b if value(b)>value(a) else a


def _merge_into(existing, incoming):
    preferred=_stronger(existing,incoming)
    # Keep the display metadata from the best card and the rest as fallback.
    for field in ('title','poster','fanart','plot','genre','rating',
                  'rating_source','original','year','file_year','raw'):
        if preferred is incoming and incoming.get(field):
            existing[field]=incoming[field]
        elif not existing.get(field) and incoming.get(field):
            existing[field]=incoming[field]
    aliases=list(existing.get('aliases') or [])
    for a in [existing.get('raw'),existing.get('title'),
              existing.get('original'),incoming.get('raw'),
              incoming.get('title'),incoming.get('original')] + list(
              incoming.get('aliases') or []):
        if a and normalize(a) not in {normalize(v) for v in aliases}:
            aliases.append(a)
    existing['aliases']=aliases
    distinct={str(f['ident']):f for f in existing.get('files') or []
              if f.get('ident')}
    for f in incoming.get('files') or []:
        if f.get('ident'):
            distinct.setdefault(str(f['ident']),f)
    existing['files']=sorted(distinct.values(),key=file_score,reverse=True)
    if existing['files']:
        chosen=existing['files'][0]
        existing['ident']=chosen['ident']
        existing['quality']=file_label(chosen)
        existing['count']=len(existing['files'])
    return existing


def consolidate(cards):
    """One card per title+release year, retaining every distinct Webshare file.

    No-year entries merge into the sole dated version of the same title, but
    stay separate if several distinct film years exist (avoid remake mixing).
    """
    result=OrderedDict()
    for card in cards or []:
        if not isinstance(card,dict) or not card.get('ident') or not card.get('files'):
            continue
        kind,name,year=identity(card)
        if not name:
            continue
        key=(kind,name,year)
        if key in result:
            _merge_into(result[key],card)
        else:
            c=dict(card)
            c['files']=list(card.get('files') or [])
            c['aliases']=list(card.get('aliases') or [])
            result[key]=c
    # Attach an undated copy ONLY if there is exactly one dated version.
    by_title={}
    for key in result:
        by_title.setdefault(key[:2],[]).append(key)
    for key in list(result):
        if not key[2] and key in result:
            dated=[k for k in by_title.get(key[:2],[]) if k[2] and k in result]
            if len(dated)==1:
                _merge_into(result[dated[0]],result.pop(key))
    return list(result.values())


def unify_sections(home):
    """Give every title ONE shared card with all verified release files.

    Source membership is retained until shelf allocation. Different source
    collections may refer to a single shared object, never distinct copies.
    """
    sections=('premieres','movies','shows','classics','classic_shows')
    all_cards=[]
    for section in sections:
        all_cards.extend(home.get(section) or [])
    merged=consolidate(all_cards)
    # Exact file identity is useful for dated/undated or weakly named variants.
    by_ident={}
    for card in merged:
        for f in card['files']:
            by_ident.setdefault(str(f['ident']),card)
    by_key={identity(card):card for card in merged}
    for section in sections:
        found=[]
        seen=set()
        for c in home.get(section) or []:
            canonical=by_key.get(identity(c))
            if canonical is None:
                canonical=next((by_ident[str(f['ident'])] for f in c.get('files') or []
                                 if str(f.get('ident')) in by_ident),None)
            if canonical is None:
                continue
            cid=id(canonical)
            if cid not in seen:
                found.append(canonical)
                seen.add(cid)
        home[section]=found
    return home


def unique_home_rails(home):
    """Assign titles to seven home rows exactly once, including ranking rails.

    Rank years first so 2026 titles remain visible under 'this year' rather
    than being consumed by the broader all-time list. Empty rows are hidden
    by the Kodi XML layout.
    """
    sections=('premieres','best_movies_year','best_shows_year',
              'best_movies_all','best_shows_all','classics',
              'shows','classic_shows','movies')
    used=set()
    # Fixed priority is independent of on-screen row order.
    allocated={}
    for section in sections:
        allocated[section]=[]
        for c in home.get(section) or []:
            key=identity(c)
            if key not in used:
                used.add(key)
                allocated[section].append(c)
    # Do not steal films belonging to the latest-year shelf.
    for section,cards in allocated.items():
        home[section]=cards
    return home
