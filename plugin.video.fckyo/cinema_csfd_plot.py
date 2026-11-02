# -*- coding: utf-8 -*-
"""Only show a description as ČSFD/CZDB when its provenance is supported.

Cinemeta plot/overview is not a ČSFD synopsis, even if the same card has
a Webshare file and a ČSFD score from a different metadata source.
"""


def is_csfd_metadata(data):
    if not isinstance(data,dict):
        return False
    if data.get('uid') or 'csfd.cz/film/' in str(data.get('csfd_url') or ''):
        return True
    return str(data.get('plot_source') or data.get('rating_source') or '').strip().casefold() in (
        'čsfd', 'csfd', 'čsfd/czdb', 'czdb',
    )


def csfd_plot(data):
    """No English/Cinemeta substitution and no file-name masquerading as plot."""
    if not is_csfd_metadata(data):
        return ''
    value=data.get('plot') or ''
    if not isinstance(value,str):
        return ''
    value=' '.join(value.split())
    if not value or value.casefold().startswith((
            'soubor nalezen na webshare', 'film nebo seriál je dostupný',
            'popis tohoto titulu', 'popis z čsfd')):
        return ''
    return value[:1600]
