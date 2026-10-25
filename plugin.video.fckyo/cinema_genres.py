# -*- coding: utf-8 -*-
"""Genre aliases for already verified films/series with actual metadata.

Genre names are metadata (ČSFD/IMDb/Cinemeta), not Webshare search operators.
Unknown genres are deliberately not guessed from file names.
"""
import re
from novinky_catalogue import normalize

GENRES=(
    'Akční','Animovaný','Dobrodružný','Drama','Fantasy','Horor',
    'Komedie','Krimi','Rodinný','Romantický','Sci-Fi','Thriller',
    'Válečný','Dokumentární','Mysteriózní','Historický',
    'Hudební','Western','Sportovní','Životopisný','Katastrofický',
    'Psychologický','Dětský','Krátkometrážní'
)

ALIASES={
    'Akční':('akční','action'),
    'Animovaný':('animovaný','animation','anime'),
    'Dobrodružný':('dobrodružný','adventure'),
    'Drama':('drama',),
    'Fantasy':('fantasy',),
    'Horor':('horor','horror'),
    'Komedie':('komedie','comedy'),
    'Krimi':('krimi','crime','criminal'),
    'Rodinný':('rodinný','family'),
    'Romantický':('romantický','romance','romantic'),
    'Sci-Fi':('sci-fi','science fiction','sci fi'),
    'Thriller':('thriller','napínavý'),
    'Válečný':('válečný','war'),
    'Dokumentární':('dokumentární','documentary','documentary film'),
    'Mysteriózní':('mysteriózní','mystery'),
    'Historický':('historický','history','historical'),
    'Hudební':('hudební','music','musical'),
    'Western':('western',),
    'Sportovní':('sportovní','sport'),
    'Životopisný':('životopisný','biography','biographical'),
    'Katastrofický':('katastrofický','disaster'),
    'Psychologický':('psychologický','psychological'),
    'Dětský':('dětský','children','kids'),
    'Krátkometrážní':('krátkometrážní','short','short film'),
}


def genre_matches(card,genre):
    if genre in ('all','',None):
        return True
    if genre not in ALIASES:
        return False
    fields=card.get('genre') or ''
    if isinstance(fields,(tuple,list)):
        values=fields
    else:
        values=re.split(r'[,;/|]',str(fields))
    actual={normalize(str(v)).strip() for v in values if v}
    aliases={normalize(v) for v in ALIASES[genre]}
    return bool(actual & aliases)


def genre_cards(cards,genre):
    """Never manufacture cards from genre labels or unverified metadata."""
    return [card for card in cards or []
            if card.get('kind') in ('movie','show')
            and card.get('ident') and card.get('files')
            and genre_matches(card,genre)]
