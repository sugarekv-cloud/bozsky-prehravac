# -*- coding: utf-8 -*-
"""Resolve exactly the next numbered Webshare series episode.

Never skip an unverified missing episode or guess a filename. The caller must
availability-check each candidate before attempting Kodi playback.
"""
from catalog_engine import file_score


def next_episode_key(seasons, season, episode):
    """Next SxxEyy, or next season E01, never silently jump a gap."""
    try:
        season,episode=int(season),int(episode)
    except (TypeError,ValueError):
        return None
    if season<0 or episode<1 or not isinstance(seasons,dict):
        return None
    current=seasons.get(season) or {}
    if episode+1 in current:
        return season,episode+1
    # An undiscovered E03 is not permission to skip directly to E04.
    if any(isinstance(n,int) and n>episode for n in current):
        return None
    future=seasons.get(season+1) or {}
    if 1 in future:
        return season+1,1
    return None


def select_release(files, previous_name=''):
    """Prefer a CZ-marked, high-quality release of the verified next episode."""
    valid=[f for f in (files or []) if isinstance(f,dict)
           and f.get('ident') and f.get('name')]
    if not valid:
        return None
    # Same preference as the manual selector: CZ-marked release first,
    # then its highest available quality. An earlier foreign-language
    # episode must not cause autoplay to skip a newly available CZ copy.
    return max(valid,key=file_score)
