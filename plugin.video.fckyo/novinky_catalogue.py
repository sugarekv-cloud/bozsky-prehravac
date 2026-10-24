# -*- coding: utf-8 -*-
"""Filename-based browser for Webshare 'recent' results.

No claim that Webshare's upload order or filename year equals a movie premiere.
Pure Python so it is unit-testable without Kodi.
"""
import re
import unicodedata
from datetime import date

VIDEO_EXT = re.compile(r'\.(?:mkv|mp4|avi|wmv|mov|m4v|ts|mpeg|mpg|webm)$', re.I)
EPISODE = re.compile(r'(?<!\w)(?:s(\d{1,2})[ ._-]*e(\d{1,3})|(\d{1,2})x(\d{1,3}))(?!\d)', re.I)
EPISODE_DASH = re.compile(r'(?i)\s+-\s+(\d{1,3})(?=\s+(?:cz|sk|en|eng|\[?(?:2160p|1080p|720p)))')
SEASON = re.compile(r'(?<!\w)(?:s(\d{1,2})|season[ ._-]*(\d{1,2})|serie[ ._-]*(\d{1,2}))(?!\w)', re.I)
YEAR = re.compile(r'(?<!\d)((?:19|20)\d\d)(?!\d)')
QUALITY = re.compile(r'(?<!\w)(2160p|4k|uhd|1080[pi]|720p|480p)(?!\w)', re.I)
RELEASE = re.compile(r'(?i)(?<!\w)(?:2160p|4k|uhd|1080[pi]|720p|480p|bluray|bdrip|brrip|webrip|web[ ._-]?dl|hdtv|dvdrip|x26[45]|h[ ._-]?26[45]|hevc|av1|hdr10?|dv|dovi|dolby[ ._-]?vision|ac3|eac3|ddp?5[ ._-]?1|aac|dts|atmos|remux|multi|czdub|czdab|czech|cz|sk|en|eng|dual|subs|titulky)(?!\w)')
BAD = re.compile(r'(?i)(?<!\w)(?:sample|trailer|teaser|featurette|extras?|behind[ ._-]?the[ ._-]?scenes)(?!\w)')


def normalize(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()


def resolution(name):
    """Prefer explicit 1080p/2160p over vague 4K-remastered labels."""
    value=name or ''
    explicit=re.search(r'(?<!\d)(2160p|1080[pi]|720p|480p)(?!\d)',value,re.I)
    if explicit:
        token=explicit.group(1).lower()
        return 2160 if token=='2160p' else 1080 if token.startswith('1080') else 720 if token=='720p' else 480
    return 2160 if re.search(r'(?i)(?<!\w)(?:4k|uhd)(?!\w)',value) else 0


def is_czech_audio_marked(name):
    """Only explicit Czech tags; MULTI/DUAL alone never proves CZ audio."""
    n=normalize(name)
    subtitles=bool(re.search(r'\b(?:czsub|czsubs|cz sub|cz subs|cz subtitles|'
                             r'czech subs|cz titulky|titulky|subtitles)\b',n))
    explicit=bool(re.search(r'\b(?:czdab|czdub|cz dabing|cz dub|'
                            r'czech dub|czech audio|cz audio|cesky dabing)\b',n))
    if subtitles and not explicit:
        return False
    return explicit or bool(re.search(r'\b(?:cz|cze|czech|cesky|cestina|czsk)\b',n))


def is_hdr(name):
    n = normalize(name)
    return bool(re.search(r'\b(?:hdr|hdr10|hdr10plus|dovi|dolby vision)\b', n))


def parse_video_name(filename):
    name = (filename or '').strip()
    if not name or BAD.search(name):
        return None
    stem = VIDEO_EXT.sub('', name)
    if not stem or len(stem) > 256:
        return None
    ep = EPISODE.search(stem)
    ep_dash = None if ep else EPISODE_DASH.search(stem)
    sea = None if ep or ep_dash else SEASON.search(stem)
    release = next((m for m in RELEASE.finditer(stem)
                    if m.start() > 0), None)
    # "Czech Story" can be a film title. A language tag at the very
    # beginning is not enough evidence that the filename has no title.
    marker = ep or ep_dash or sea or release
    early = stem[:marker.start()] if marker else stem
    # Year before release tags is usually the title year, unlike a year in a series episode date.
    yrs = list(YEAR.finditer(early))
    year = ''
    if yrs:
        match = yrs[-1]
        y = int(match.group(1))
        if 1900 <= y <= date.today().year + 2:
            year = str(y)
            early = early[:match.start()]
    title = re.sub(r'[._\[\]{}()]+', ' ', early)
    title = re.sub(r'[-]+', ' ', title)
    title = ' '.join(title.split()).strip(' _.-')
    # If a title has no year or technical marker but still ends in a video extension, show it.
    if len(normalize(title)) < 3 or not re.search(r'[a-zA-Z\u00c0-\u024f]', title):
        return None
    if re.fullmatch(r'(?i)(?:video|film|movie|serial|episode|capture|recording|untitled|sample|test|screenshot|clip)\s*\d*', title):
        return None
    season = int(ep.group(1) or ep.group(3)) if ep else (1 if ep_dash else int(next((x for x in sea.groups() if x), 0)) if sea else None)
    episode = int(ep.group(2) or ep.group(4)) if ep else int(ep_dash.group(1)) if ep_dash else None
    kind = 'episode' if ep or ep_dash else 'series' if sea else 'movie'
    return {'title':title, 'kind':kind, 'year':year, 'season':season, 'episode':episode}


def quality_score(file):
    name = file.get('name', '')
    try:
        size = int(file.get('size') or 0)
    except (ValueError, TypeError):
        size = 0
    return (resolution(name) * 10 + (220 if is_czech_audio_marked(name) else 0)
            + (60 if is_hdr(name) else 0) + min(size // (1024**3), 60))


def matching(file, item, minimum=0, only_cz=False, only_hdr=False, year=''):
    if int(minimum or 0) > resolution(file.get('name', '')):
        return False
    if only_cz and not is_czech_audio_marked(file.get('name', '')):
        return False
    if only_hdr and not is_hdr(file.get('name', '')):
        return False
    if year and item.get('year') != str(year):
        return False
    return True


def build_groups(files, kind='all', minimum=0, only_cz=False, only_hdr=False, year=''):
    """Preserves Webshare 'recent' first-seen ordering; returns title groups."""
    groups, order = {}, []
    seen_ids = set()
    for file in files:
        fid = file.get('ident')
        if not fid or fid in seen_ids or file.get('password') == '1':
            continue
        seen_ids.add(fid)
        item = parse_video_name(file.get('name'))
        if not item or not matching(file, item, minimum, only_cz, only_hdr, year):
            continue
        if kind == 'movies' and item['kind'] != 'movie':
            continue
        if kind == 'episodes' and item['kind'] != 'episode':
            continue
        if kind == 'shows' and item['kind'] not in ('episode', 'series'):
            continue
        # Distinguish a show card vs individual episode card.
        group_kind = 'show' if kind == 'shows' else item['kind']
        key = (group_kind, normalize(item['title']), item['year'],
               None if group_kind == 'show' else item['season'],
               None if group_kind == 'show' else item['episode'])
        if key not in groups:
            groups[key] = dict(item, group_kind=group_kind, files=[], best=None, count=0)
            order.append(key)
        groups[key]['files'].append(file)
        groups[key]['count'] += 1
        if groups[key]['best'] is None or quality_score(file) > quality_score(groups[key]['best']):
            groups[key]['best'] = file
    return [groups[key] for key in order]


def label_group(group):
    title = group['title']
    if group['group_kind'] == 'episode':
        title += ' · S%02dE%02d' % (group['season'], group['episode'])
    elif group['year']:
        title += ' (%s)' % group['year']
    best = group['best'] or {}
    res = resolution(best.get('name', ''))
    quality = '%sp' % res if res else 'bez označení'
    if is_czech_audio_marked(best.get('name', '')):
        quality += ' · CZ*'
    if is_hdr(best.get('name', '')):
        quality += ' · HDR'
    return '%s  [COLOR gray][%s | %s soub.] [/COLOR]' % (title, quality, group['count'])


def sort_variants(files):
    return sorted(files, key=quality_score, reverse=True)


def variant_label(file):
    name = file.get('name', '')
    res = resolution(name)
    parts = [('%d' % res + 'p') if res else 'Kvalita nezjištěna']
    if is_hdr(name):
        parts.append('HDR*')
    parts.append('CZ dabing?*' if is_czech_audio_marked(name) else 'Jazyk nezjištěn')
    return ' · '.join(parts)
