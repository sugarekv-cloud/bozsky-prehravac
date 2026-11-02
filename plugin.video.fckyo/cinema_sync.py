# -*- coding: utf-8 -*-
"""Optional shared-folder sync for KIVORA profiles.

Kodi VFS handles SMB/NFS sources; local paths work in headless tests.
Only explicitly whitelisted watch metadata and favorites are transmitted.
The shared folder must be trusted; it is not encrypted by this add-on.
"""
import hashlib
import io
import json
import os
import time
import uuid
from urllib.parse import urlsplit

from cinema_backup import _scrub, MAX_BYTES
from cinema_profiles import active_profile,state_paths
from cinema_user_state import WatchStore,MAX_ENTRIES,MAX_FAVORITES

CONFIG='kivora-shared-sync-v1.json'
SCHEMA=1

def _json_file(path,default=None):
    try:
        with io.open(path,'r',encoding='utf-8') as stream:
            data=json.load(stream)
        return data if isinstance(data,dict) else (default or {})
    except (OSError,ValueError,TypeError):
        return default or {}

def _write_json(path,data):
    folder=os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    temp=path+'.tmp'
    with io.open(temp,'w',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,separators=(',',':'))
    os.replace(temp,path)

def configured_folder(root):
    data=_json_file(os.path.join(root,CONFIG))
    folder=data.get('folder')
    return folder if isinstance(folder,str) else ''

def set_folder(root,folder):
    if not isinstance(folder,str):
        raise ValueError('Neplatná sdílená složka.')
    folder=folder.strip()
    if folder and '://' in folder:
        uri=urlsplit(folder)
        if not uri.scheme or not uri.netloc or '@' in uri.netloc:
            raise ValueError('Nepoužívej v adrese složky vložené heslo.')
    if len(folder)>1024:
        raise ValueError('Příliš dlouhá cesta ke složce.')
    _write_json(os.path.join(root,CONFIG),{'folder':folder})

def _tomb_path(root,profile_id=None):
    return state_paths(root,profile_id)[0]+'.removed.json'

def note_favorite_change(root,key,enabled,profile_id=None):
    path=_tomb_path(root,profile_id)
    tomb=_json_file(path)
    if enabled:
        tomb.pop(key,None)
    else:
        tomb[str(key)[:250]]=time.time()
    _write_json(path,tomb)

def _remote_path(root,folder,profile_name=None):
    name=(profile_name if profile_name is not None else active_profile(root)['name']).casefold().strip().encode('utf-8')
    digest=hashlib.sha256(name).hexdigest()[:20]
    filename='kivora-library-%s-v1.json'%digest
    if '://' in folder:
        return folder.rstrip('/')+'/'+filename
    return os.path.join(folder,filename)

def _remote_read(path):
    if '://' in path:
        import xbmcvfs
        if not xbmcvfs.exists(path):
            return {}
        handle=xbmcvfs.File(path,'r')
        try:
            data=handle.read(MAX_BYTES+1)
        finally:
            handle.close()
        if isinstance(data,bytes):
            data=data.decode('utf-8')
    else:
        if not os.path.isfile(path):
            return {}
        if os.path.getsize(path)>MAX_BYTES:
            raise ValueError('Sdílená databáze je příliš velká.')
        with io.open(path,'r',encoding='utf-8') as stream:
            data=stream.read(MAX_BYTES+1)
    if len(data.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Sdílená databáze je příliš velká.')
    parsed=json.loads(data)
    if not isinstance(parsed,dict) or parsed.get('schema')!=SCHEMA or parsed.get('type')!='kivora-sync':
        raise ValueError('Neplatná sdílená databáze.')
    return parsed

def _remote_write(path,data):
    encoded=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    if len(encoded.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Sdílená databáze je příliš velká.')
    if '://' in path:
        import xbmcvfs
        tmp=path+'.%s.tmp'%uuid.uuid4().hex
        f=xbmcvfs.File(tmp,'w')
        try:
            f.write(encoded)
        finally:
            f.close()
        if not xbmcvfs.rename(tmp,path):
            # Some SMB implementations cannot rename over an existing file.
            if not xbmcvfs.copy(tmp,path):
                raise OSError('Sdílený soubor nelze uložit.')
            xbmcvfs.delete(tmp)
    else:
        _write_json(path,data)

def _valid_tombstones(value):
    result={}
    if isinstance(value,dict):
        for key,stamp in list(value.items())[:MAX_FAVORITES*2]:
            if not isinstance(key,str):
                continue
            try:
                stamp=float(stamp)
                if 0<stamp<1e11:
                    result[key[:250]]=stamp
            except (ValueError,TypeError,OverflowError):
                continue
    return result

def _merge(local,remote,local_deleted,remote_deleted):
    local=_scrub(local)
    remote=_scrub(remote)
    watch={}
    for source in (local['watch'],remote['watch']):
        for key,item in source.items():
            if key not in watch or float(item.get('updated') or 0)>float(watch[key].get('updated') or 0):
                watch[key]=item
    watch=dict(sorted(watch.items(),key=lambda kv:float(kv[1].get('updated') or 0),
                      reverse=True)[:MAX_ENTRIES])
    tomb=_valid_tombstones(local_deleted)
    for key,stamp in _valid_tombstones(remote_deleted).items():
        tomb[key]=max(stamp,tomb.get(key,0))
    favorites={}
    for source in (local['favorites'],remote['favorites']):
        for key,item in source.items():
            if key not in favorites or float(item.get('added') or 0)>float(favorites[key].get('added') or 0):
                favorites[key]=item
    for key,item in list(favorites.items()):
        if tomb.get(key,0)>=float(item.get('added') or 0):
            favorites.pop(key,None)
    # Obsolete deletions must not remove new favorites on the next sync.
    for key,item in favorites.items():
        if float(item.get('added') or 0)>tomb.get(key,0):
            tomb.pop(key,None)
    favorites=dict(sorted(favorites.items(),key=lambda kv:float(kv[1].get('added') or 0),
                          reverse=True)[:MAX_FAVORITES])
    tomb=dict(sorted(tomb.items(),key=lambda kv:kv[1],reverse=True)[:MAX_FAVORITES*2])
    return {'watch':watch,'favorites':favorites},tomb

def sync_now(root):
    folder=configured_folder(root)
    if not folder:
        raise ValueError('Nejprve nastav sdílenou složku.')
    active=active_profile(root)
    profile_id=active['id']
    path=_remote_path(root,folder,active['name'])
    store=WatchStore(root,profile_id)
    local=store._data()
    local_deleted=_json_file(_tomb_path(root,profile_id))
    remote=_remote_read(path)
    merged,tomb=_merge(local,remote.get('data',{}),local_deleted,remote.get('removed',{}))
    if merged!=local:
        store._write(store.path,merged)
    if tomb!=local_deleted:
        _write_json(_tomb_path(root,profile_id),tomb)
    _remote_write(path,{'schema':SCHEMA,'type':'kivora-sync','data':merged,'removed':tomb,
                        'synchronized':int(time.time())})
    return len(merged['watch']),len(merged['favorites'])
