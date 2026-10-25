# -*- coding: utf-8 -*-
"""Local FCKYO watch progress / favourites, free of Webshare tokens.

JSON files live in the add-on's Kodi profile. No remote sync or credentials.
Only verified video file identifiers can become entries.
"""
import io
import json
import os
import re
import time
import unicodedata

MAX_ENTRIES=200
MAX_FAVORITES=150


def _text(value,limit=350):
    return str(value or '').strip()[:limit]


def _norm(value):
    value=unicodedata.normalize('NFKD',_text(value))
    return re.sub(r'[^a-z0-9]+',' ',''.join(
        ch for ch in value.lower() if not unicodedata.combining(ch))).strip()


def watch_key(entry):
    kind=entry.get('kind') or 'movie'
    title=_norm(entry.get('raw_title') or entry.get('title'))
    if kind=='show':
        return 'show|%s|%s|%s'%(title,entry.get('season') or '0',
                                 entry.get('episode') or '0')
    return 'movie|%s|%s'%(title,entry.get('year') or '')


def _safe(entry):
    result={}
    for field in ('kind','title','raw_title','year','poster','fanart',
                  'plot','genre','quality','ident','name','season','episode',
                  'original'):
        if field in entry:
            result[field]=_text(entry[field],800 if field in ('poster','fanart') else 350)
    return result


class WatchStore:
    def __init__(self,profile):
        self.path=os.path.join(profile,'fckyo-watch-state-v1.json')
        self.pending=os.path.join(profile,'fckyo-playback-pending-v1.json')

    @staticmethod
    def _read(path):
        try:
            with io.open(path,'r',encoding='utf8') as f:
                data=json.load(f)
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError,TypeError):
            return {}

    @staticmethod
    def _write(path,data):
        directory=os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        tmp=path+'.tmp'
        with io.open(tmp,'w',encoding='utf8') as f:
            json.dump(data,f,ensure_ascii=False,separators=(',',':'))
        os.replace(tmp,path)

    def _data(self):
        data=self._read(self.path)
        return {'watch':data.get('watch',{}) if isinstance(data.get('watch'),dict) else {},
                'favorites':data.get('favorites',{}) if isinstance(data.get('favorites'),dict) else {}}

    def pending_play(self,params):
        if not params.get('ident') or not params.get('name'):
            return
        item=_safe(params)
        if item.get('kind') not in ('movie','show'):
            item['kind']='movie'
        item['created']=time.time()
        try:
            item['resume']=max(0,float(params.get('resume') or 0))
        except (ValueError,TypeError):
            item['resume']=0
        item['key']=watch_key(item)
        self._write(self.pending,item)

    def pop_pending(self):
        value=self._read(self.pending)
        try:
            os.remove(self.pending)
        except OSError:
            pass
        return value if time.time()-float(value.get('created') or 0)<90 else {}

    def update_progress(self,item,position,total,completed=False):
        if not item.get('ident') or not item.get('name'):
            return
        try:
            pos=max(0,float(position))
            duration=max(0,float(total))
        except (ValueError,TypeError):
            return
        if pos<15 and not completed:
            return
        data=self._data()
        entry=_safe(item)
        key=watch_key(entry)
        if not key.strip('|'):
            return
        finished=bool(completed or duration>0 and pos/duration>=0.94)
        entry.update({'position':round(pos,1),'total':round(duration,1),
                      'updated':time.time(),'completed':finished})
        data['watch'][key]=entry
        data['watch']=dict(sorted(data['watch'].items(),
             key=lambda v:float(v[1].get('updated') or 0),reverse=True)[:MAX_ENTRIES])
        self._write(self.path,data)

    def continue_cards(self,kind=None):
        result=[]
        entries=self._data()['watch'].values()
        for v in entries:
            if v.get('completed') or not v.get('ident') or not v.get('name'):
                continue
            if kind and v.get('kind')!=kind:
                continue
            position=float(v.get('position') or 0)
            total=float(v.get('total') or 0)
            if position<15:
                continue
            item=dict(v)
            item['_continue']=True
            item['raw']=item.get('raw_title') or item.get('title')
            item['files']=[{'ident':item['ident'],'name':item['name']}]
            item['progress']=min(99,int(position/total*100)) if total else 0
            if item.get('kind')=='show':
                item['plot']='S%sE%s · pokračovat v čase %s min'%(
                    str(item.get('season') or '1').zfill(2),
                    str(item.get('episode') or '1').zfill(2),
                    int(position//60))
            else:
                item['plot']='Pokračovat od %s min'%int(position//60)
            result.append(item)
        return sorted(result,key=lambda v:float(v.get('updated') or 0),
                      reverse=True)[:35]

    def toggle_favorite(self,item):
        if item.get('kind') not in ('movie','show') or not item.get('ident'):
            return False
        data=self._data()
        v=_safe(dict(item,raw_title=item.get('raw_title') or
                     item.get('raw') or item.get('title'),
                     name=item.get('name') or (item.get('files') or [{}])[0].get('name')))
        key=watch_key(v)
        if key in data['favorites']:
            del data['favorites'][key]
            enabled=False
        else:
            v['added']=time.time()
            data['favorites'][key]=v
            enabled=True
        data['favorites']=dict(sorted(data['favorites'].items(),
            key=lambda kv:float(kv[1].get('added') or 0),reverse=True)[:MAX_FAVORITES])
        self._write(self.path,data)
        return enabled

    def favorite_cards(self):
        result=[]
        for c in self._data()['favorites'].values():
            if c.get('ident') and c.get('name'):
                v=dict(c)
                v.update({'raw':c.get('raw_title') or c.get('title'),
                          'files':[{'ident':c['ident'],'name':c['name']}]})
                result.append(v)
        return result

    def mark_watched(self,item):
        key=watch_key(dict(item,raw_title=item.get('raw_title') or
                           item.get('raw') or item.get('title')))
        data=self._data()
        if key in data['watch']:
            data['watch'][key]['completed']=True
            self._write(self.path,data)

    def clear_progress(self,item):
        key=watch_key(dict(item,raw_title=item.get('raw_title') or
                           item.get('raw') or item.get('title')))
        data=self._data()
        if key in data['watch']:
            del data['watch'][key]
            self._write(self.path,data)
