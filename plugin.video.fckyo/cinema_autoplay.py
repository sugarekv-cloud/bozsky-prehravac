# -*- coding: utf-8 -*-
"""Resolve exactly the next numbered Webshare series episode.

Never skip an unverified missing episode or guess a filename. The caller must
availability-check each candidate before attempting Kodi playback.
"""
from catalog_engine import file_score, release_details


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
    """Prefer a comparable resolution/CZ filename over an unrelated release."""
    valid=[f for f in (files or []) if isinstance(f,dict)
           and f.get('ident') and f.get('name')]
    if not valid:
        return None
    previous=release_details(previous_name)
    def rank(file):
        details=release_details(file.get('name'))
        resolution=details.get('resolution') or 0
        requested=previous.get('resolution') or 0
        target_lang=previous.get('language') or ''
        language=details.get('language') or ''
        # Prefer a known matching CZ-tagged file if the user chose one.
        same_language=(target_lang==language)
        same_resolution=(requested>0 and resolution==requested)
        return (int(same_language),int(same_resolution),
                -abs(resolution-requested) if requested else resolution,
                file_score(file))
    return max(valid,key=rank)
