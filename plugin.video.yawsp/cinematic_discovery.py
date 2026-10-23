# -*- coding: utf-8 -*-
"""Webshare search-backed discovery for the cinema home.

The /api/search/ endpoint documents 'what' as a search phrase. An empty
query is NOT a reliable feed of new uploads. Always use nonblank queries.
All cards still come from real file identities returned by Webshare.
"""
from datetime import date
from novinky_catalogue import VIDEO_EXT, parse_video_name


def queries_for_home(today=None):
    year=(today or date.today()).year
    return (
        ('new',str(year),'recent'),
        ('new',str(year-1),'recent'),
        ('new','1080p','recent'),
        ('popular','1080p','rating'),
        ('popular','S01E','recent'),
    )


def discover(token, search_page, today=None, limit=350):
    """Gather real video files using nonempty queries; report why empty.

    The API fetcher is injected for deterministic tests and compatibility
    with the existing add-on login/session.
    """
    recent=[]
    popular=[]
    seen_new=set()
    seen_pop=set()
    stats={'queries':0, 'responses':0, 'results':0, 'video_files':0,
           'errors':0, 'movie_candidates':0, 'show_candidates':0}
    for target,term,sort in queries_for_home(today):
        stats['queries']+=1
        try:
            files,_ = search_page(token,0,term,sort=sort)
        except Exception:
            stats['errors']+=1
            continue
        if files is None:
            stats['errors']+=1
            continue
        stats['responses']+=1
        stats['results']+=len(files)
        dest = recent if target=='new' else popular
        seen = seen_new if target=='new' else seen_pop
        for f in files:
            if not isinstance(f,dict):
                continue
            ident=str(f.get('ident') or '')
            filename=f.get('name') or ''
            if not ident or ident in seen or not VIDEO_EXT.search(filename):
                continue
            if str(f.get('password') or '0')=='1':
                continue
            if str(f.get('removed') or '0')=='1':
                continue
            p=parse_video_name(filename)
            if not p:
                continue
            seen.add(ident)
            dest.append(f)
            stats['video_files']+=1
            if p['kind']=='movie':
                stats['movie_candidates']+=1
            else:
                stats['show_candidates']+=1
            if len(dest)>=limit:
                break
    return recent,popular,stats


def empty_message(stats, final_movie_count, final_show_count):
    if final_movie_count or final_show_count:
        return 'Filmy potvrzené na Webshare · OK otevře výběr kvality'
    if not stats['responses']:
        return 'Webshare neodpovídá na vyhledávání. Ověř připojení a přihlášení.'
    if not stats['video_files']:
        return 'Webshare vyhledávání nenašlo odpovídající video. Použij Hledat.'
    if not stats['movie_candidates'] and not stats['show_candidates']:
        return 'Webshare našel soubory, ale nerozpoznal jejich názvy.'
    return ('Byly nalezeny názvy souborů, ale jejich aktuální dostupnost '
            'nebyla potvrzena. Použij Hledat.')
