# -*- coding: utf-8 -*-
"""Build trailer searches without network access or playback side effects."""
from urllib.parse import quote_plus

def trailer_search_url(card):
    if not isinstance(card,dict):
        return ''
    title=str(card.get('original') or card.get('title') or '').strip()
    if not title:
        return ''
    year=str(card.get('year') or '').strip()
    if year and (not year.isdigit() or len(year)!=4):
        year=''
    query=' '.join(filter(None,(title[:150],year,'official trailer')))
    return 'plugin://plugin.video.youtube/search/?q='+quote_plus(query)
