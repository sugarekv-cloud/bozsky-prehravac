# -*- coding: utf-8 -*-
"""Prepare cinema home rows only from real and verified Webshare results.

Kodi-free so it can be tested independently. Metadata is decoration, never
a source of imaginary films or episodes.
"""
from novinky_catalogue import build_groups
from catalog_engine import file_label


def _decorate(groups, catalogue, max_metadata=10):
    if catalogue and groups:
        catalogue.lookup_many(groups[:max_metadata], max_new=max_metadata)
    cards=[]
    for g in groups:
        file=g.get('best') or {}
        if not g.get('files') or not file.get('ident'):
            continue
        meta=g.get('metadata') or {}
        show=g.get('group_kind')=='show'
        year=meta.get('year') or g.get('year') or ''
        title=meta.get('title') or g.get('title') or ''
        cards.append({
            'title':title,
            'file_title':g['title'],
            'year':year,
            'file_year':g.get('year') or '',
            'plot':meta.get('plot') or
                    ('Dostupné soubory na Webshare. Vyberte konkrétní kvalitu.'
                     if not show else 'Vyberte sezónu a epizodu.'),
            'rating':meta.get('rating'),
            'genre':', '.join(meta.get('genres') or []),
            'poster':meta.get('poster') or file.get('img') or '',
            'fanart':meta.get('fanart') or '',
            'original':meta.get('original') or '',
            'quality':file_label(file),
            'kind':'show' if show else 'movie',
            'ident':file['ident'],
            'files':len(g['files']),
        })
    return cards


def make_rows(recent, popular, checker, catalogue=None, limit=12):
    """Return verified movies and shows (fallback: popular movies)."""
    recent=recent or []
    popular=popular or []
    movie=build_groups(recent, kind='movies')[:limit]
    shows=build_groups(recent+popular, kind='shows')[:limit]
    if not shows:
        shows=build_groups(popular, kind='movies')[:limit]
    # Fail closed: no downloadable Webshare candidate means no card.
    movie=checker.check_groups(movie,max_workers=4) if movie else []
    shows=checker.check_groups(shows,max_workers=4) if shows else []
    first=_decorate(movie,catalogue)
    second=_decorate(shows,catalogue)
    if catalogue:
        catalogue.save()
    return {
        'new_movies': first,
        'discover': second,
        'discover_title': 'SERIÁLY K OBJEVENÍ' if any(c['kind']=='show' for c in second)
            else 'OBLÍBENÉ FILMY NA WEBSHARE'
    }
