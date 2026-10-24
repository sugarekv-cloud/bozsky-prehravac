# -*- coding: utf-8 -*-
"""Optional CZDB metadata adapter for YAWsP (no TMDb key, no Webshare credentials).

CZDB is an independent, unofficial API. Metadata is best-effort, not guaranteed.
Calls are bounded to selected files and results are cached in Kodi's profile dir.
"""
import io
import json
import os
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

import requests

CACHE_NAME = 'csfd-metadata-cache-v1.json'
TTL_POSITIVE = 7 * 86400
TTL_NEGATIVE = 30 * 60
CACHE_LIMIT = 1500
_LOCK = threading.RLock()


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in s.lower() if not unicodedata.combining(c))).strip()


def _get(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if v is not None and v != '' and v != []:
            return v
    return None


def _as_string(value):
    if isinstance(value, dict):
        return str(_get(value, 'name', 'nazev', 'title', 'text', 'value', 'url', 'src') or '')
    if isinstance(value, list):
        return _as_string(value[0]) if value else ''
    return str(value) if value is not None else ''


def _genres(value):
    if isinstance(value, str):
        values = re.split(r'\s*(?:,|/|\|)\s*', value)
    elif isinstance(value, list):
        values = [_as_string(v) for v in value]
    elif isinstance(value, dict):
        values = [_as_string(v) for v in value.values()]
    else:
        values = []
    return [s.strip() for s in values if s and s.strip()][:8]


def _rating(value):
    if isinstance(value, dict):
        value = _get(value, 'percentage', 'percent', 'ratingValue', 'value', 'score', 'rating')
    try:
        number = float(re.search(r'\d+(?:[.,]\d+)?', str(value or '')).group().replace(',', '.'))
        if not 0 <= number <= 100:
            return None
        # Ratings below 10 can be normalized only if schema explicitly says 0–10;
        # avoid silently labeling e.g. 4.8 stars as 4.8 percent.
        if 0 < number <= 10 and '%' not in str(value):
            return None
        return int(round(number))
    except (AttributeError, ValueError, TypeError):
        return None


def _image(value):
    if isinstance(value, list):
        return next((x for x in (_image(v) for v in value) if x), '')
    if isinstance(value, dict):
        value = _get(value, 'url', 'src', 'original', 'large', 'medium', 'image', 'poster')
    if isinstance(value, str):
        value = value.strip()
        if value.startswith('//'):
            value = 'https:' + value
        if value.startswith('https://') or value.startswith('http://'):
            return value[:1000]
    return ''


def _entries(payload, depth=0):
    """CZDB may return a single detail or grouped search hits."""
    if depth > 4 or payload is False or payload is None:
        return []
    if isinstance(payload, list):
        hits = []
        for e in payload[:60]:
            hits.extend(_entries(e, depth+1))
        return hits
    if isinstance(payload, dict):
        if any(k in payload for k in ('title', 'name', 'nazev', 'název', 'title_cz', 'csfd_id', 'uid')):
            return [payload]
        for key in ('results', 'result', 'data', 'movies', 'films', 'filmy', 'items', 'search', 'hits', 'records'):
            if key in payload:
                result = _entries(payload[key], depth+1)
                if result:
                    return result
        if len(payload) < 60:
            out = []
            for entry in payload.values():
                if isinstance(entry, (list, dict)):
                    out.extend(_entries(entry, depth+1))
            return out
    return []


def parse_entry(entry):
    if not isinstance(entry, dict):
        return None
    title = _as_string(_get(entry, 'title_cz', 'name_cz', 'nazev_cz', 'název', 'nazev', 'title', 'name', 'film_name', 'film'))
    original = _as_string(_get(entry, 'original_title', 'original_name', 'original', 'nazev_original', 'originalni_nazev', 'orig_title', 'title_original'))
    if not title and original:
        title = original
    if not title:
        return None
    y = _get(entry, 'year', 'rok', 'release_year', 'released', 'release_date', 'premiere')
    m = re.search(r'\b(?:19|20)\d{2}\b', _as_string(y))
    year = m.group() if m else ''
    uid = _as_string(_get(entry, 'uid', 'csfd_id', 'csfdId', 'id_csfd'))
    direct_url = _as_string(_get(entry, 'csfd_url', 'csfd', 'url'))
    if not uid:
        match = re.search(r'csfd\.cz/film/(\d+)', direct_url)
        uid = match.group(1) if match else ''
    if uid and not uid.isdigit():
        uid = ''
    poster = _image(_get(entry, 'poster', 'poster_url', 'posterUrl', 'image', 'img', 'obrazek', 'obrázek', 'thumbnail'))
    backdrop = _image(_get(entry, 'backdrop', 'fanart', 'background', 'backdrop_url'))
    description = _as_string(_get(entry, 'description', 'plot', 'overview', 'content', 'obsah', 'synopsis', 'anotace', 'text'))
    if len(description) > 1600:
        description = description[:1597]+'...'
    rating = _rating(_get(entry, 'rating', 'csfd_rating', 'rating_percent', 'rating_percentage', 'hodnoceni', 'hodnocení', 'score', 'percent'))
    genre = _genres(_get(entry, 'genres', 'genre', 'zanry', 'žánry', 'zanr', 'žánr', 'categories'))
    duration = _as_string(_get(entry, 'runtime', 'length', 'duration', 'stopaz', 'stopáž'))
    return {'title': title, 'original': original, 'year': year, 'poster': poster,
            'fanart': backdrop, 'plot': description, 'rating': rating,
            'genres': genre, 'runtime': duration, 'uid': uid,
            'csfd_url': ('https://www.csfd.cz/film/' + uid + '/' if uid else direct_url if 'csfd.cz/film/' in direct_url else '')}


def select_match(payload, title, year=''):
    target = norm(title)
    if not target or len(target) < 2:
        return None
    candidates = []
    for raw in _entries(payload):
        entry = parse_entry(raw)
        if not entry:
            continue
        similarity = max(SequenceMatcher(None, target, norm(n)).ratio()
                         for n in (entry['title'], entry['original']) if n)
        entryyear = entry['year']
        if year and entryyear and abs(int(year)-int(entryyear)) > 1:
            continue
        if similarity >= .70 or target in (norm(entry['title']),norm(entry['original'])):
            candidates.append((similarity + (.17 if year and entryyear == year else 0), entry))
    if not candidates:
        return None
    return max(candidates, key=lambda x:x[0])[1]


class Catalogue:
    def __init__(self, profile, transport=None):
        self.path = os.path.join(profile, CACHE_NAME)
        self.transport = transport or requests.get
        self._cache = None
        self._dirty = False
        self._service_down = False
        self._mutex = threading.RLock()

    def _load(self):
        with self._mutex:
            if self._cache is not None:
                return
            try:
                with io.open(self.path, 'r', encoding='utf-8') as h:
                    loaded = json.load(h)
                self._cache = loaded if isinstance(loaded, dict) else {}
            except (ValueError, OSError, TypeError):
                self._cache = {}

    def _key(self, title, year):
        return '%s@%s' % (norm(title)[:130], year or '')

    def lookup(self, title, year=''):
        self._load()
        key = self._key(title, year)
        with self._mutex:
            previous = self._cache.get(key)
            if isinstance(previous, dict):
                age = time.time()-previous.get('time', 0)
                if age < (TTL_POSITIVE if previous.get('metadata') else TTL_NEGATIVE):
                    return previous.get('metadata')
        with self._mutex:
            offline = self._service_down
        result = None if offline else self._fetch(title, year)
        with self._mutex:
            self._cache[key] = {'time': time.time(), 'metadata': result}
            self._dirty = True
        return result

    def _fetch(self, title, year):
        # Start with the public service's HTTPS root. Its API also documents HTTP;
        # try the /search variant if the root endpoint is unavailable.
        # Absolutely no Webshare credentials or tokens are sent to CZDB.
        endpoints = ('https://api.czdb.cz/', 'https://api.czdb.cz/search',
                     'http://api.czdb.cz/', 'http://api.czdb.cz/search')
        successful_http = False
        for endpoint in endpoints:
            with self._mutex:
                if self._service_down:
                    return None
            try:
                params = {'q': title}
                if year:
                    params['y'] = year
                response = self.transport(endpoint, params=params, timeout=2.5,
                                          headers={'Accept':'application/json', 'User-Agent':'YAWsP-SmartSearch/0.5'})
                response.raise_for_status()
                data = response.json()
                successful_http = True
                match = select_match(data, title, year)
                if match:
                    # Search responses may contain only minimal details.
                    if not match['plot'] and not match['poster'] and match['uid']:
                        try:
                            full = self.transport(endpoint, params={'uid':match['uid']}, timeout=2.5,
                                                  headers={'Accept':'application/json', 'User-Agent':'YAWsP-SmartSearch/0.5'})
                            full.raise_for_status()
                            detailed = select_match(full.json(), title, year)
                            if detailed:
                                match.update({k: v for k, v in detailed.items() if v not in ('', None, [])})
                        except (requests.RequestException, ValueError, TypeError):
                            pass
                    return match
                # Valid JSON response: the server is up but this title is not indexed.
                # Repeating an alternate path would add latency without any benefit.
                break
            except (requests.RequestException, ValueError, TypeError):
                continue
        if not successful_http:
            # Stop queuing more identical failing calls for the current menu page.
            with self._mutex:
                self._service_down = True
        return None

    def lookup_many(self, groups, max_new=16):
        self._load()
        unique = {}
        for group in groups:
            key = self._key(group['title'], group.get('year', ''))
            if key not in unique:
                unique[key] = (group['title'], group.get('year', ''))
        keys = list(unique)[:max_new]
        # Bound concurrency: don't hammer a third-party free API.
        results = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(self.lookup, *unique[k]): k for k in keys}
            for job in as_completed(jobs):
                try:
                    results[jobs[job]] = job.result()
                except Exception:
                    results[jobs[job]] = None
        for group in groups:
            group['metadata'] = results.get(self._key(group['title'], group.get('year', '')))
        self.save()
        return groups

    def save(self):
        with self._mutex:
            if not self._dirty:
                return
            self._dirty = False
            now = time.time()
            valid = {k:v for k,v in self._cache.items() if isinstance(v,dict) and
                     now-v.get('time',0) < (TTL_POSITIVE if v.get('metadata') else TTL_NEGATIVE)}
            if len(valid)>CACHE_LIMIT:
                valid = dict(sorted(valid.items(), key=lambda kv: kv[1]['time'], reverse=True)[:CACHE_LIMIT])
            self._cache = valid
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path+'.tmp'
                with io.open(tmp,'w',encoding='utf-8') as h:
                    json.dump(valid,h,ensure_ascii=False,separators=(',',':'))
                os.replace(tmp,self.path)
            except OSError:
                pass


def passes_metadata_filter(group, genre='', min_rating=0):
    meta = group.get('metadata') or {}
    if genre and not any(norm(x) == norm(genre) for x in meta.get('genres', [])):
        return False
    if min_rating and (meta.get('rating') is None or meta['rating'] < min_rating):
        return False
    return True


def decorate_label(label, metadata):
    if not metadata:
        return label
    details = []
    if metadata.get('rating') is not None:
        details.append('ČSFD %s %%' % metadata['rating'])
    if metadata.get('genres'):
        details.append(', '.join(metadata['genres'][:2]))
    return label + ('  [COLOR gray]• %s[/COLOR]' % ' • '.join(details) if details else '')
