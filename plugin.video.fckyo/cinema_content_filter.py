# -*- coding: utf-8 -*-
"""Conservative, always-on explicit-content filter for KIVORA.

Protects every catalogue surface (films, series, searches, favorites,
recommendations and individual file variants). Uses Webshare's adult flag
plus strong filename/metadata signals. Does NOT blacklist the generic
word 'sex' (e.g. Sex Education) or age ratings such as 18 by themselves.
This is a best-effort classifier, not a guarantee for incorrectly tagged
files or unknown adult material.
"""
import re
import unicodedata

_EXPLICIT = re.compile(
    r'(?<![a-z0-9])(?:'
    r'xxx|porn(?:o|ography|ographic|ograficky|ograficke|ograficka)?|porna|pornografie|'
    r'pornhub|xvideos|xnxx|redtube|youporn|brazzers|'
    r'onlyfans|hentai|hardcore|hard[ ._-]*core|'
    r'gang[ ._-]*bang|blow[ ._-]*job|'
    r'sex[ ._-]*tape|sex[ ._-]*video|sexvideo|'
    r'adult[ ._-]*(?:movie|film|video|content)|'
    r'erotic(?:a)?|erotick[yae]|erotika|'
    r'uncensored[ ._-]*(?:porn|adult)|'
    r'18[ ._-]*plus[ ._-]*(?:xxx|porn)|'
    r'camgirl|webcam[ ._-]*porn'
    r')(?![a-z0-9])', re.I
)
_ADULT_GENRES = frozenset((
    'adult', 'porn', 'porno', 'pornography', 'pornografie',
    'erotic', 'erotica', 'erotika', 'eroticky', 'eroticky film',
    'sexual content', 'sexually explicit',
))


def folded(value):
    text=unicodedata.normalize('NFKD',str(value or '').casefold())
    text=''.join(char for char in text if not unicodedata.combining(char))
    return text


def explicit_text(value):
    return bool(_EXPLICIT.search(folded(value)))


def _adult_flag(value):
    return str(value or '').casefold().strip() in ('1','true','yes','adult','explicit')


def safe_file(file):
    if not isinstance(file,dict):
        return False
    if _adult_flag(file.get('adult')) or _adult_flag(file.get('is_adult')):
        return False
    if folded(file.get('category')).strip() in _ADULT_GENRES:
        return False
    return not any(explicit_text(file.get(key) or '') for key in ('name','filename','title'))


def safe_card(card):
    """Reject flagged titles and files; retain benign release alternatives."""
    if not isinstance(card,dict):
        return False
    if _adult_flag(card.get('adult')) or _adult_flag(card.get('is_adult')):
        return False
    for key in ('title','raw','original','name','genre'):
        if explicit_text(card.get(key) or ''):
            return False
    if folded(card.get('category')).strip() in _ADULT_GENRES:
        return False
    genres=card.get('genres') or []
    if isinstance(genres,str):
        genres=re.split(r'[,;|]',genres)
    genres=list(genres)+re.split(r'[,;|/]',str(card.get('genre') or ''))
    for genre in genres:
        if folded(genre).strip() in _ADULT_GENRES:
            return False
    # Synopses often mention sexuality in legitimate dramas; never scan plot.
    files=card.get('files')
    if files and not any(safe_file(f) for f in files):
        return False
    return True


def filter_cards(cards):
    """Return copies so that cached unfiltered Webshare state isn't mutated."""
    result=[]
    for card in cards or []:
        if not safe_card(card):
            continue
        files=card.get('files')
        if files:
            eligible=[f for f in files if safe_file(f)]
            if not eligible:
                continue
            if len(eligible)!=len(files):
                item=dict(card,files=eligible)
                if not any(str(f.get('ident'))==str(item.get('ident')) for f in eligible):
                    item['ident']=eligible[0].get('ident')
                result.append(item)
                continue
        result.append(card)
    return result
