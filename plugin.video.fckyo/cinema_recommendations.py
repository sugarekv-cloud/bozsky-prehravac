# -*- coding: utf-8 -*-
"""Local, explainable recommendations from verified files and ČSFD ratings.

No metadata-only suggestions, no user profiling outside the Kodi device.
Weekly picks are deterministic for the week and exclude finished titles.
"""
from datetime import date
from cinema_dedupe import consolidate,identity
from cinema_rankings import csfd_only
from novinky_catalogue import normalize


def _genres(card):
    field=card.get('genre') or ''
    if isinstance(field,(tuple,list)):
        values=field
    else:
        values=str(field).replace(';',',').split(',')
    return {normalize(x) for x in values if normalize(x)}


def recommendations(home, watch_store=None, limit=18, week=None):
    """Return (personalized, weekly), both validated Webshare media cards."""
    all_cards=consolidate(
        (home.get('_all_movies') or [])+(home.get('_all_shows') or [])+
        (home.get('premieres') or [])+(home.get('classics') or []))
    candidates=[c for c in all_cards if
                c.get('kind') in ('movie','show') and
                c.get('ident') and c.get('files')]
    favorites=watch_store.favorite_cards() if watch_store else []
    continuations=watch_store.continue_cards() if watch_store else []
    history=(watch_store._data().get('watch',{}) if watch_store else {})
    already={identity(x) for x in (favorites+continuations)}
    for item in history.values():
        if item.get('completed'):
            already.add(identity(dict(item,raw=item.get('raw_title') or item.get('title'))))
    tastes={}
    for item in favorites+continuations:
        for genre in _genres(item):
            tastes[genre]=tastes.get(genre,0)+1
    scored=[]
    for card in candidates:
        if identity(card) in already:
            continue
        source=str(card.get('rating_source') or '').casefold()
        is_csfd=source in ('čsfd','csfd','czdb')
        try:
            rating=float(card['rating'])
        except (ValueError,TypeError,KeyError):
            rating=0
        if not 0<rating<=100:
            rating=0
        overlap=sum(tastes.get(g,0) for g in _genres(card))
        # Actual ČSFD scores take priority; verified but unscored titles are
        # fallback tips, never falsely labeled ČSFD or Webshare view counts.
        score=(rating if is_csfd else rating*.68 if rating else 48)
        score+=min(18,overlap*6)
        scored.append((score,rating,normalize(card.get('title') or ''),card))
    scored.sort(key=lambda item:(-item[0],-item[1],item[2]))
    personalized=[c for _,_,_,c in scored[:limit]]
    if week is None:
        today=date.today()
        week=today.isocalendar().year*100+today.isocalendar().week
    # Rotate weekly suggestions from top verified ČSFD films and series.
    rated=csfd_only(candidates,'movie',limit=75)+csfd_only(candidates,'show',limit=45)
    # Fill out short ČSFD subsets from other *verified* discovered titles.
    used={identity(c) for c in rated}
    rated+= [c for c in candidates if identity(c) not in used]
    rated=[c for c in consolidate(rated) if identity(c) not in already]
    if not rated:
        return personalized,[]
    offset=(int(week)*7)%len(rated)
    weekly=(rated[offset:]+rated[:offset])[:limit]
    return personalized,weekly
