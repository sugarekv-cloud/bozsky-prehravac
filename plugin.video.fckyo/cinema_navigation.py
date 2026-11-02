# -*- coding: utf-8 -*-
"""One-shot return to the KIVORA shelf after video playback.

The Kodi WindowXMLDialog must close *before* PlayMedia on Android TV: keeping
it active triggered native player/window crashes. Persist only safe, minimal
navigation metadata, then reopen the dialog on player Stop/End via the
existing service. Never store streaming URLs, credentials or Webshare tokens.
"""
import io
import json
import os
import time

FILENAME='navigation-return-v1.json'
MAX_AGE=12*3600  # A film may last longer than 2 hours.
MAX_SIZE=65536
MAX_DEPTH=6
ALLOWED_VIEWS=frozenset((
    'home','movies','shows','bluey','premieres','search',
    'recommendations','favorites','genres','genre_titles','seasons',
    'episodes','most_watched','csfd_ranked','catalog_all','tips',
))
CARD_FIELDS=frozenset((
    'title','raw','raw_title','original','kind','ident','year','file_year',
    'poster','fanart','plot','genre','rating','rating_source','aliases',
    'season','episode','files','name','size','available','removed',
    'password','quality','_continue','position','resume',
    'catalog_kind','genre_name','search_text',
))
FILE_FIELDS=frozenset(('ident','name','size','available','removed','password'))


def _path(profile):
    if not profile:
        return None
    return os.path.join(profile,FILENAME)


def _clean(value,depth=0,filename=False):
    """Whitelisted JSON model. No URLs, cookies, auth objects or stream links."""
    if depth>MAX_DEPTH:
        return None
    if value is None or isinstance(value,(bool,int,float)):
        return value
    if isinstance(value,str):
        return value[:600] if not filename else value[:240]
    if isinstance(value,(tuple,list)):
        return [_clean(v,depth+1,filename) for v in value[:30]]
    if isinstance(value,dict):
        allowed=FILE_FIELDS if filename else CARD_FIELDS
        safe={}
        for k,v in value.items():
            if k not in allowed:
                continue
            # Webshare's password flag is numeric, never store a credential.
            if k=='password':
                safe[k]='1' if str(v)=='1' else '0'
            elif k=='files':
                safe[k]=[_clean(f,depth+1,True) for f in (v or [])[:12]
                         if isinstance(f,dict)]
            else:
                safe[k]=_clean(v,depth+1)
        return safe
    return None


def save(profile,view,context,stack=(),focus=None,index=0):
    """Atomically persist the browse position immediately before PlayMedia."""
    path=_path(profile)
    if not path or view not in ALLOWED_VIEWS:
        return False
    snapshot={
        'version':1, 'timestamp':time.time(), 'view':view,
        'context':_clean(context),
        'stack':[
            [str(entry[0]),_clean(entry[1]),entry[2],entry[3]]
            for entry in (stack or [])[-8:]
            if (isinstance(entry,(list,tuple)) and len(entry)==4
                and entry[0] in ALLOWED_VIEWS)
        ],
        'focus':focus if isinstance(focus,int) else None,
        'index':max(0,min(int(index or 0),1000)),
    }
    data=json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))
    if len(data.encode('utf8'))>MAX_SIZE:
        # Drop the oldest breadcrumb levels; keep the current screen.
        snapshot['stack']=[]
        data=json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))
    if len(data.encode('utf8'))>MAX_SIZE:
        snapshot['context']=None
        snapshot['view']='home'
        data=json.dumps(snapshot,ensure_ascii=False,separators=(',',':'))
    try:
        if not os.path.isdir(profile):
            os.makedirs(profile)
        temp=path+'.tmp'
        with io.open(temp,'w',encoding='utf8') as stream:
            stream.write(data)
        os.replace(temp,path)
        return True
    except (OSError,ValueError,TypeError):
        return False


def discard(profile):
    path=_path(profile)
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def consume(profile):
    """Restore at most once after Stop/End; ignore old or corrupt snapshots."""
    path=_path(profile)
    if not path:
        return None
    try:
        if os.path.getsize(path)>MAX_SIZE:
            return None
        with io.open(path,'r',encoding='utf8') as stream:
            data=json.load(stream)
        if (data.get('version')!=1 or data.get('view') not in ALLOWED_VIEWS
                or not 0<=time.time()-float(data.get('timestamp',0))<MAX_AGE):
            return None
        stack=[]
        for entry in data.get('stack') or []:
            if (isinstance(entry,list) and len(entry)==4
                    and entry[0] in ALLOWED_VIEWS):
                stack.append(tuple(entry))
        return {'view':data['view'],'context':data.get('context'),
                'stack':stack,'focus':data.get('focus'),
                'index':data.get('index',0)}
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return None
    finally:
        discard(profile)
