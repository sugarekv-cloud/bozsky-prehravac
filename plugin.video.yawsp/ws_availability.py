# -*- coding: utf-8 -*-
"""Check if a Webshare search result is still downloadable before showing a film."""
import io
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from xml.etree import ElementTree as ET
import requests

TTL_OK = 600
TTL_NO = 90

class Availability:
    def __init__(self, profile, transport=None):
        self.path = os.path.join(profile, 'ws-file-availability.json')
        self.transport = transport or requests.post
        self.lock = threading.RLock()
        self.cache = {}
        try:
            with io.open(self.path, 'r', encoding='utf-8') as h:
                value = json.load(h)
            if isinstance(value,dict):
                self.cache = value
        except (IOError, OSError, ValueError, TypeError):
            pass

    def _check(self, ident):
        now = time.time()
        with self.lock:
            cached = self.cache.get(ident)
            if isinstance(cached,dict) and now-float(cached.get('time',0)) < (TTL_OK if cached.get('ok') else TTL_NO):
                return bool(cached['ok'])
        ok = False
        try:
            response = self.transport('https://webshare.cz/api/file_exists/',
                                      data={'ident':ident}, timeout=(2,4))
            response.raise_for_status()
            root = ET.fromstring(response.content)
            ok = (root.findtext('status') == 'OK' and
                  root.findtext('exists') == '1' and
                  root.findtext('downloadable') == '1')
        except (requests.RequestException, ValueError, TypeError, ET.ParseError):
            ok = False
        with self.lock:
            self.cache[ident] = {'ok':ok, 'time':now}
        return ok

    def check_groups(self, groups, max_workers=4):
        """Retain only file-backed titles with a currently downloadable candidate."""
        groups = [g for g in groups if g.get('files')]
        candidates = []
        for g in groups:
            candidates.extend([str(f.get('ident')) for f in g['files'][:3] if f.get('ident')])
        candidates = list(dict.fromkeys(candidates))
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            pending = {pool.submit(self._check, ident):ident for ident in candidates}
            for job in as_completed(pending):
                try:
                    results[pending[job]] = job.result()
                except Exception:
                    results[pending[job]] = False
        filtered = []
        for g in groups:
            good = [f for f in g['files'] if results.get(str(f.get('ident'))) is True]
            if not good:
                continue
            output = dict(g)
            output['files'] = good
            output['best'] = good[0] if g.get('best',{}).get('ident') not in {f.get('ident') for f in good} else g['best']
            filtered.append(output)
        self.save()
        return filtered

    def check_files(self, files):
        """Check a few candidate files, return downloadable matches only."""
        good=[]
        for f in files[:3]:
            if f.get('ident') and self._check(str(f['ident'])):
                good.append(f)
        self.save()
        return good

    def save(self):
        now = time.time()
        valid = {k:v for k,v in self.cache.items() if isinstance(v,dict) and
                 now-float(v.get('time',0)) < (TTL_OK if v.get('ok') else TTL_NO)}
        if len(valid)>2500:
            valid = dict(sorted(valid.items(), key=lambda x:x[1]['time'],reverse=True)[:2500])
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + '.tmp'
            with io.open(tmp,'w',encoding='utf-8') as h:
                json.dump(valid,h,separators=(',',':'))
            os.replace(tmp,self.path)
        except OSError:
            pass
