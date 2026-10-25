# -*- coding: utf-8 -*-
"""Top-rated shelves derived exclusively from validated Webshare cards.

ČSFD/CZDB rating is a ranking signal, never a source of playable titles.
This is a ranked subset of the indexed catalogue, NOT a claim to cover all
films/series in the world or every video file on Webshare.
"""
from datetime import date
from novinky_catalogue import normalize

SHELVES = ('best_movies_all', 'best_movies_year',
           'best_shows_all', 'best_shows_year')


def ranked_cards(cards, kind, year=None, limit=20):
    result=[]
    seen=set()
    for card in cards or []:
        if card.get('kind') != kind:
            continue
        # Must be a discovered Webshare item with a playable file identifier.
        if not card.get('ident') or not card.get('files'):
            continue
        try:
            rating = float(card.get('rating'))
        except (TypeError,ValueError):
            continue
        if not 0 < rating <= 100:
            continue
        if year is not None:
            try:
                if int(card.get('year') or 0)!=int(year):
                    continue
            except (TypeError,ValueError):
                continue
        key=normalize(card.get('raw') or card.get('title') or '')
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(card)
    return sorted(result,key=lambda c:(-float(c['rating']),
            normalize(c.get('title') or '')))[:limit]


def create_shelves(movies, shows, current_year=None, limit=20):
    year=current_year if current_year is not None else date.today().year
    return {
        'best_movies_all': ranked_cards(movies,'movie',limit=limit),
        'best_movies_year':ranked_cards(movies,'movie',year=year,limit=limit),
        'best_shows_all': ranked_cards(shows,'show',limit=limit),
        'best_shows_year':ranked_cards(shows,'show',year=year,limit=limit),
        'ranking_year':year,
        'ranking_basis':'Hodnocení ČSFD dostupných souborů Webshare'
    }

def csfd_only(cards, kind='movie', year=None, limit=35):
    """Rank *only* genuine ČSFD-sourced ratings of verified Webshare cards.

    IMDb scores and Webshare's search 'rating' order must not be relabeled ČSFD.
    """
    matching=[card for card in (cards or [])
              if str(card.get('rating_source') or '').strip().casefold()
                 in ('čsfd','csfd','czdb')]
    return ranked_cards(matching,kind,year=year,limit=limit)
