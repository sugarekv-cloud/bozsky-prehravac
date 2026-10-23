# -*- coding: utf-8 -*-
"""Film premieres in Czech cinemas from a public, renewable iCalendar feed.

Source: https://www.fuxoft.cz/vyplody/premiery/premiery.ics
The date describes a *cinema premiere*, NOT the file's availability on Webshare.
Independent of xbmc for testing. No login credentials are transmitted.
"""
import io
import json
import os
import re
import time
import unicodedata
from datetime import date, timedelta

import requests

CALENDAR_URL = 'https://www.fuxoft.cz/vyplody/premiery/premiery.ics'
CACHE_FILE = 'cinema-premieres-v1.json'
CACHE_TTL = 24 * 3600
MAX_BYTES = 5 * 1024 * 1024
MAX_EVENTS = 7000
MAX_STALE = 45 * 86400


def text_unescape(value):
    """Unescape RFC 5545 TEXT after unfolding."""
    value = str(value or '')
    return re.sub(r'\\([nN,;\\])', lambda m: '\n' if m.group(1).lower() == 'n' else m.group(1), value)


def unfold(raw):
    """Join folded ICS lines, including UTF-8 summaries."""
    value = raw.replace('\r\n', '\n').replace('\r', '\n').lstrip('\ufeff')
    out = []
    for line in value.split('\n'):
        if line.startswith((' ', '\t')) and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def ics_date(value):
    value = str(value or '').strip()
    if not re.match(r'^\d{8}(?:T\d{6}Z?)?$', value):
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def normalize(value):
    normalized = unicodedata.normalize('NFKD', str(value or ''))
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(
        c for c in normalized.lower() if not unicodedata.combining(c))).strip()


def split_title(summary):
    """Input: Czech title [Original title]; only the final square brackets count."""
    title = ' '.join(str(summary or '').split())
    m = re.match(r'^(.+?)\s*\[([^\[\]]{2,150})\]\s*$', title)
    if not m:
        return title, ''
    return m.group(1).strip(), m.group(2).strip()


def _event(props):
    dt = ics_date(props.get('DTSTART'))
    title, original = split_title(text_unescape(props.get('SUMMARY', '')))
    if not dt or len(title) < 2 or len(title) > 220:
        return None
    desc = text_unescape(props.get('DESCRIPTION', ''))
    distributor = ''
    language = ''
    for line in desc.split('\n'):
        line = line.strip()
        match = re.search(r'(?i)(?:^|\|\s*)distributor\s*:\s*([^|\n]+)', line)
        if match:
            distributor = match.group(1).strip()[:120]
        match = re.search(r'(?i)(?:^|\|\s*)jazyková\s+verze\s*:\s*([^|\n]+)', line)
        if match:
            language = match.group(1).strip()[:50]
    if not original:
        # Some calendars put the original title on an independent line.
        match = re.search(r'(?im)^\s*(?:originální|původní)\s+název\s*:\s*(.+)$', desc)
        if match:
            original = match.group(1).strip()[:160]
    return {'title': title, 'original': original, 'premiere': dt.isoformat(),
            'distributor': distributor, 'language': language,
            'source': 'Fuxoft/UFD'}


def parse_ics(raw):
    """Parse VCALENDAR/VEVENT; safe subset of RFC5545 sufficient for all-day dates."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig', errors='replace')
    if 'BEGIN:VCALENDAR' not in raw or 'BEGIN:VEVENT' not in raw:
        raise ValueError('Neplatný soubor iCalendar')
    events = []
    current = None
    seen = set()
    for line in unfold(raw):
        if line == 'BEGIN:VEVENT':
            current = {}
            continue
        if line == 'END:VEVENT':
            if current is not None:
                event = _event(current)
                if event:
                    key = (normalize(event['title']), event['premiere'])
                    if key not in seen:
                        seen.add(key)
                        events.append(event)
                        if len(events) >= MAX_EVENTS:
                            break
            current = None
            continue
        if current is None or ':' not in line:
            continue
        prop, value = line.split(':', 1)
        prop = prop.split(';', 1)[0].upper()
        if prop in ('DTSTART','SUMMARY','DESCRIPTION'):
            current[prop] = value
    if not events:
        raise ValueError('Kalendář neobsahuje žádné platné premiéry')
    return sorted(events, key=lambda item: (item['premiere'],normalize(item['title'])))


def select_events(items, view='recent30', month='', today=None):
    today = today or date.today()
    if view == 'recent7':
        start, end = today-timedelta(days=6), today
    elif view == 'recent30':
        start, end = today-timedelta(days=29), today
    elif view == 'recent90':
        start, end = today-timedelta(days=89), today
    elif view == 'upcoming30':
        start, end = today+timedelta(days=1), today+timedelta(days=30)
    elif view == 'upcoming90':
        start, end = today+timedelta(days=1), today+timedelta(days=90)
    elif view == 'month' and re.match(r'^\d{4}-(?:0[1-9]|1[0-2])$', month):
        start = date(int(month[:4]), int(month[5:7]), 1)
        end = date(start.year + (start.month == 12), 1 if start.month == 12 else start.month+1, 1)-timedelta(days=1)
    else:
        return []
    chosen = [item for item in items if start.isoformat() <= item['premiere'] <= end.isoformat()]
    return sorted(chosen, key=lambda x: (x['premiere'],normalize(x['title'])), reverse=view.startswith('recent'))


class PremiereCalendar:
    def __init__(self, profile, transport=None, clock=None):
        self.path = os.path.join(profile, CACHE_FILE)
        self.transport = transport or requests.get
        self.clock = clock or time.time
        self.error = ''
        self.stale = False
        self.fetched_at = 0

    def _read(self):
        try:
            with io.open(self.path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if data.get('version') == 1 and isinstance(data.get('items'),list):
                return data
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return None

    def _write(self, data):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + '.tmp'
            with io.open(tmp, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, separators=(',',':'))
            os.replace(tmp, self.path)
        except OSError:
            pass

    def load(self, force=False):
        cached = self._read()
        now = self.clock()
        if cached and not force and now - cached['time'] < CACHE_TTL:
            self.fetched_at = cached['time']
            return cached['items']
        try:
            response = self.transport(CALENDAR_URL,
                    timeout=(4,12), headers={'Accept':'text/calendar',
                    'User-Agent':'YAWsP-Premieres/0.6 (+Kodi; non-commercial)'})
            response.raise_for_status()
            if len(response.content) > MAX_BYTES:
                raise ValueError('Kalendář přesahuje povolenou velikost')
            events = parse_ics(response.content)
            self.fetched_at = now
            self._write({'version':1, 'time':now, 'items':events})
            return events
        except (requests.RequestException, ValueError, TypeError, UnicodeError) as exc:
            self.error = '%s' % exc
            if cached and now - cached['time'] <= MAX_STALE:
                self.stale = True
                self.fetched_at = cached['time']
                return cached['items']
            return []


def nice_date(iso):
    y, m, d = iso.split('-')
    return '%s.%s.%s' % (d,m,y)


def next_month(year, month, offset):
    index = year*12 + month-1 + offset
    return '%04d-%02d' % (index//12, index%12+1)
