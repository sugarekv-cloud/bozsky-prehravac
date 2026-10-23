# -*- coding: utf-8 -*-
# Module: default
# Author: cache-sk
# Created on: 10.5.2020
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

import io
import os
import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs
import requests.cookies
from xml.etree import ElementTree as ET
import hashlib
from md5crypt import md5crypt
import traceback
import json
import unidecode
import re
import zipfile
import uuid

try:
    from urllib import urlencode
    from urlparse import parse_qsl, urlparse
except ImportError:
    from urllib.parse import urlencode
    from urllib.parse import parse_qsl, urlparse

try:
    from xbmc import translatePath
except ImportError:
    from xbmcvfs import translatePath

BASE = 'https://webshare.cz'
API = BASE + '/api/'
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"
HEADERS = {'User-Agent': UA, 'Referer':BASE}
REALM = ':Webshare:'
CATEGORIES = ['','video','images','audio','archives','docs','adult']
SORTS = ['','recent','rating','largest','smallest']
SEARCH_HISTORY = 'search_history'
NONE_WHAT = '%#NONE#%'
BACKUP_DB = 'D1iIcURxlR'

_url = sys.argv[0]
_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()
_session = requests.Session()
_session.headers.update(HEADERS)
_profile = translatePath( _addon.getAddonInfo('profile'))
try:
    _profile = _profile.decode("utf-8")
except:
    pass

def get_url(**kwargs):
    return '{0}?{1}'.format(_url, urlencode(kwargs, 'utf-8'))

def api(fnct, data):
    response = _session.post(API + fnct + "/", data=data)
    return response

def is_ok(xml):
    status = xml.find('status').text
    return status == 'OK'

def popinfo(message, heading=_addon.getAddonInfo('name'), icon=xbmcgui.NOTIFICATION_INFO, time=3000, sound=False): #NOTIFICATION_WARNING NOTIFICATION_ERROR
    xbmcgui.Dialog().notification(heading, message, icon, time, sound=sound)

def login():
    username = _addon.getSetting('wsuser')
    password = _addon.getSetting('wspass')
    if username == '' or password == '':
        popinfo(_addon.getLocalizedString(30101), sound=True)
        _addon.openSettings()
        return
    response = api('salt', {'username_or_email': username})
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        salt = xml.find('salt').text
        try:
            encrypted_pass = hashlib.sha1(md5crypt(password.encode('utf-8'), salt.encode('utf-8'))).hexdigest()
            pass_digest = hashlib.md5(username.encode('utf-8') + REALM + encrypted_pass.encode('utf-8')).hexdigest()
        except TypeError:
            encrypted_pass = hashlib.sha1(md5crypt(password.encode('utf-8'), salt.encode('utf-8')).encode('utf-8')).hexdigest()
            pass_digest = hashlib.md5(username.encode('utf-8') + REALM.encode('utf-8') + encrypted_pass.encode('utf-8')).hexdigest()
        response = api('login', {'username_or_email': username, 'password': encrypted_pass, 'digest': pass_digest, 'keep_logged_in': 1})
        xml = ET.fromstring(response.content)
        if is_ok(xml):
            token = xml.find('token').text
            _addon.setSetting('token', token)
            return token
        else:
            popinfo(_addon.getLocalizedString(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
            _addon.openSettings()
    else:
        popinfo(_addon.getLocalizedString(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
        _addon.openSettings()

def revalidate():
    token = _addon.getSetting('token')
    if len(token) == 0:
        if login():
            return revalidate()
    else:
        response = api('user_data', { 'wst': token })
        xml = ET.fromstring(response.content)
        status = xml.find('status').text
        if is_ok(xml):
            vip = xml.find('vip').text
            if vip != '1':
                popinfo(_addon.getLocalizedString(30103), icon=xbmcgui.NOTIFICATION_WARNING)
            return token
        else:
            if login():
                return revalidate()

def todict(xml, skip=[]):
    result = {}
    for e in xml:
        if e.tag not in skip:
            value = e.text if len(list(e)) == 0 else todict(e,skip)
            if e.tag in result:
                if isinstance(result[e.tag], list):
                    result[e.tag].append(value)
                else:
                    result[e.tag] = [result[e.tag],value]
            else:
                result[e.tag] = value
    #result = {e.tag:(e.text if len(list(e)) == 0 else todict(e,skip)) for e in xml if e.tag not in skip}
    return result
            
def sizelize(txtsize, units=['B','KB','MB','GB']):
    if txtsize:
        size = float(txtsize)
        if size < 1024:
            size = str(size) + units[0]
        else:
            size = size / 1024
            if size < 1024:
                size = str(int(round(size))) + units[1]
            else:
                size = size / 1024
                if size < 1024:
                    size = str(round(size,2)) + units[2]
                else:
                    size = size / 1024
                    size = str(round(size,2)) + units[3]
        return size
    return str(txtsize)
    
def labelize(file):
    if 'size' in file:
        size = sizelize(file['size'])
    elif 'sizelized' in file:
        size = file['sizelized']
    else:
        size = '?'
    label = file['name'] + ' (' + size + ')'
    return label
    
def tolistitem(file, addcommands=[]):
    label = labelize(file)
    listitem = xbmcgui.ListItem(label=label)
    if 'img' in file:
        listitem.setArt({'thumb': file['img']})
    listitem.setInfo('video', {'title': label})
    listitem.setProperty('IsPlayable', 'true')
    commands = []
    commands.append(( _addon.getLocalizedString(30211), 'RunPlugin(' + get_url(action='info',ident=file['ident']) + ')'))
    commands.append(( _addon.getLocalizedString(30212), 'RunPlugin(' + get_url(action='download',ident=file['ident']) + ')'))
    if addcommands:
        commands = commands + addcommands
    listitem.addContextMenuItems(commands)
    return listitem

def ask(what):
    if what is None:
        what = ''
    kb = xbmc.Keyboard(what, _addon.getLocalizedString(30007))
    kb.doModal() # Onscreen keyboard appears
    if kb.isConfirmed():
        return kb.getText() # User input
    return None
    
def loadsearch():
    history = []
    try:
        if not os.path.exists(_profile):
            os.makedirs(_profile)
    except Exception as e:
        traceback.print_exc()
    
    try:
        with io.open(os.path.join(_profile, SEARCH_HISTORY), 'r', encoding='utf8') as file:
            fdata = file.read()
            file.close()
            try:
                history = json.loads(fdata, "utf-8")
            except TypeError:
                history = json.loads(fdata)
    except Exception as e:
        traceback.print_exc()

    return history
    
def storesearch(what):
    if what:
        size = int(_addon.getSetting('shistory'))

        history = loadsearch()

        if what in history:
            history.remove(what)

        history = [what] + history
        
        if len(history)>size:
            history = history[:size]

        try:
            with io.open(os.path.join(_profile, SEARCH_HISTORY), 'w', encoding='utf8') as file:
                try:
                    data = json.dumps(history).decode('utf8')
                except AttributeError:
                    data = json.dumps(history)
                file.write(data)
                file.close()
        except Exception as e:
            traceback.print_exc()

def removesearch(what):
    if what:
        history = loadsearch()
        if what in history:
            history.remove(what)
            try:
                with io.open(os.path.join(_profile, SEARCH_HISTORY), 'w', encoding='utf8') as file:
                    try:
                        data = json.dumps(history).decode('utf8')
                    except AttributeError:
                        data = json.dumps(history)
                    file.write(data)
                    file.close()
            except Exception as e:
                traceback.print_exc()

def dosearch(token, what, category, sort, limit, offset, action):
    response = api('search',{'what':'' if what == NONE_WHAT else what, 'category':category, 'sort':sort, 'limit': limit, 'offset': offset, 'wst':token, 'maybe_removed':'true'})
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        
        if offset > 0: #prev page
            listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30206))
            listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
            xbmcplugin.addDirectoryItem(_handle, get_url(action=action, what=what, category=category, sort=sort, limit=limit, offset=offset - limit if offset > limit else 0), listitem, True)
            
        for file in xml.iter('file'):
            item = todict(file)
            commands = []
            commands.append(( _addon.getLocalizedString(30214), 'Container.Update(' + get_url(action='search',toqueue=item['ident'], what=what, offset=offset) + ')'))
            listitem = tolistitem(item,commands)
            xbmcplugin.addDirectoryItem(_handle, get_url(action='play',ident=item['ident'],name=item['name']), listitem, False)
        
        try:
            total = int(xml.find('total').text)
        except:
            total = 0
            
        if offset + limit < total: #next page
            listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30207))
            listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
            xbmcplugin.addDirectoryItem(_handle, get_url(action=action, what=what, category=category, sort=sort, limit=limit, offset=offset+limit), listitem, True)
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)

def search(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + _addon.getLocalizedString(30201))
    token = revalidate()
    
    updateListing=False
    
    if 'remove' in params:
        removesearch(params['remove'])
        updateListing=True
        
    if 'toqueue' in params:
        toqueue(params['toqueue'],token)
        updateListing=True
    
    what = None
    
    if 'what' in params:
        what = params['what']
    
    if 'ask' in params:
        slast = _addon.getSetting('slast')
        if slast != what:
            what = ask(what)
            if what is not None:
                storesearch(what)
            else:
                updateListing=True

    if what is not None:
        if 'offset' not in params:
            _addon.setSetting('slast',what)
        else:
            _addon.setSetting('slast',NONE_WHAT)
            updateListing=True
        
        category = params['category'] if 'category' in params else CATEGORIES[int(_addon.getSetting('scategory'))]
        sort = params['sort'] if 'sort' in params else SORTS[int(_addon.getSetting('ssort'))]
        limit = int(params['limit']) if 'limit' in params else int(_addon.getSetting('slimit'))
        offset = int(params['offset']) if 'offset' in params else 0
        dosearch(token, what, category, sort, limit, offset, 'search')
    else:
        _addon.setSetting('slast',NONE_WHAT)
        history = loadsearch()
        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30205))
        listitem.setArt({'icon': 'DefaultAddSource.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search',ask=1), listitem, True)
        
        #newest
        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30208))
        listitem.setArt({'icon': 'DefaultAddonsRecentlyUpdated.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search',what=NONE_WHAT,sort=SORTS[1]), listitem, True)
        
        #biggest
        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30209))
        listitem.setArt({'icon': 'DefaultHardDisk.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search',what=NONE_WHAT,sort=SORTS[3]), listitem, True)
        
        for search in history:
            listitem = xbmcgui.ListItem(label=search)
            listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
            commands = []
            commands.append(( _addon.getLocalizedString(30213), 'Container.Update(' + get_url(action='search',remove=search) + ')'))
            listitem.addContextMenuItems(commands)
            xbmcplugin.addDirectoryItem(_handle, get_url(action='search',what=search,ask=1), listitem, True)
    xbmcplugin.endOfDirectory(_handle, updateListing=updateListing)

def queue(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + _addon.getLocalizedString(30202))
    token = revalidate()
    updateListing=False
    
    if 'dequeue' in params:
        response = api('dequeue_file',{'ident':params['dequeue'],'wst':token})
        xml = ET.fromstring(response.content)
        if is_ok(xml):
            popinfo(_addon.getLocalizedString(30106))
        else:
            popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        updateListing=True
    
    response = api('queue',{'wst':token})
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        for file in xml.iter('file'):
            item = todict(file)
            commands = []
            commands.append(( _addon.getLocalizedString(30215), 'Container.Update(' + get_url(action='queue',dequeue=item['ident']) + ')'))
            listitem = tolistitem(item,commands)
            xbmcplugin.addDirectoryItem(_handle, get_url(action='play',ident=item['ident'],name=item['name']), listitem, False)
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    xbmcplugin.endOfDirectory(_handle,updateListing=updateListing)

def toqueue(ident,token):
    response = api('queue_file',{'ident':ident,'wst':token})
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        popinfo(_addon.getLocalizedString(30105))
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)

def history(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + _addon.getLocalizedString(30203))
    token = revalidate()
    updateListing=False
    
    if 'remove' in params:
        remove = params['remove']
        updateListing=True
        response = api('history',{'wst':token})
        xml = ET.fromstring(response.content)
        ids = []
        if is_ok(xml):
            for file in xml.iter('file'):
                if remove == file.find('ident').text:
                    ids.append(file.find('download_id').text)
        else:
            popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        if ids:
            rr = api('clear_history',{'ids[]':ids,'wst':token})
            xml = ET.fromstring(rr.content)
            if is_ok(xml):
                popinfo(_addon.getLocalizedString(30104))
            else:
                popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    
    if 'toqueue' in params:
        toqueue(params['toqueue'],token)
        updateListing=True
    
    response = api('history',{'wst':token})
    xml = ET.fromstring(response.content)
    files = []
    if is_ok(xml):
        for file in xml.iter('file'):
            item = todict(file, ['ended_at', 'download_id', 'started_at'])
            if item not in files:
                files.append(item)
        for file in files:
            commands = []
            commands.append(( _addon.getLocalizedString(30213), 'Container.Update(' + get_url(action='history',remove=file['ident']) + ')'))
            commands.append(( _addon.getLocalizedString(30214), 'Container.Update(' + get_url(action='history',toqueue=file['ident']) + ')'))
            listitem = tolistitem(file, commands)
            xbmcplugin.addDirectoryItem(_handle, get_url(action='play',ident=file['ident'],name=file['name']), listitem, False)
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    xbmcplugin.endOfDirectory(_handle,updateListing=updateListing)
    
def settings(params):
    _addon.openSettings()
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())

def infonize(data,key,process=str,showkey=True,prefix='',suffix='\n'):
    if key in data:
        return prefix + (key.capitalize() + ': ' if showkey else '') + process(data[key]) + suffix
    return ''

def fpsize(fps):
    x = round(float(fps),3)
    if int(x) == x:
       return str(int(x))
    return str(x)
    
def getinfo(ident,wst):
    response = api('file_info',{'ident':ident,'wst': wst})
    xml = ET.fromstring(response.content)
    ok = is_ok(xml)
    if not ok:
        response = api('file_info',{'ident':ident,'wst': wst, 'maybe_removed':'true'})
        xml = ET.fromstring(response.content)
        ok = is_ok(xml)
    if ok:
        return xml
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        return None

def info(params):
    token = revalidate()
    xml = getinfo(params['ident'],token)
    
    if xml is not None:
        info = todict(xml)
        text = ''
        text += infonize(info, 'name')
        text += infonize(info, 'size', sizelize)
        text += infonize(info, 'type')
        text += infonize(info, 'width')
        text += infonize(info, 'height')
        text += infonize(info, 'format')
        text += infonize(info, 'fps', fpsize)
        text += infonize(info, 'bitrate', lambda x:sizelize(x,['bps','Kbps','Mbps','Gbps']))
        if 'video' in info and 'stream' in info['video']:
            streams = info['video']['stream']
            if isinstance(streams, dict):
                streams = [streams]
            for stream in streams:
                text += 'Video stream: '
                text += infonize(stream, 'width', showkey=False, suffix='')
                text += infonize(stream, 'height', showkey=False, prefix='x', suffix='')
                text += infonize(stream,'format', showkey=False, prefix=', ', suffix='')
                text += infonize(stream,'fps', fpsize, showkey=False, prefix=', ', suffix='')
                text += '\n'
        if 'audio' in info and 'stream' in info['audio']:
            streams = info['audio']['stream']
            if isinstance(streams, dict):
                streams = [streams]
            for stream in streams:
                text += 'Audio stream: '
                text += infonize(stream, 'format', showkey=False, suffix='')
                text += infonize(stream,'channels', prefix=', ', showkey=False, suffix='')
                text += infonize(stream,'bitrate', lambda x:sizelize(x,['bps','Kbps','Mbps','Gbps']), prefix=', ', showkey=False, suffix='')
                text += '\n'
        text += infonize(info, 'removed', lambda x:'Yes' if x=='1' else 'No')
        xbmcgui.Dialog().textviewer(_addon.getAddonInfo('name'), text)

def getlink(ident,wst,dtype='video_stream'):
    #uuid experiment
    duuid = _addon.getSetting('duuid')
    if not duuid:
        duuid = str(uuid.uuid4())
        _addon.setSetting('duuid',duuid)
    data = {'ident':ident,'wst': wst,'download_type':dtype,'device_uuid':duuid}
    #TODO password protect
    #response = api('file_protected',data) #protected
    #xml = ET.fromstring(response.content)
    #if is_ok(xml) and xml.find('protected').text != 0:
    #    pass #ask for password
    response = api('file_link',data)
    xml = ET.fromstring(response.content)
    if is_ok(xml):
        return xml.find('link').text
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        return None

def play(params):
    token = revalidate()
    link = getlink(params['ident'],token)
    if link is not None:
        #headers experiment
        headers = _session.headers
        if headers:
            headers.update({'Cookie':'wst='+token})
            link = link + '|' + urlencode(headers)
        listitem = xbmcgui.ListItem(label=params['name'],path=link)
        listitem.setProperty('mimetype', 'application/octet-stream')
        xbmcplugin.setResolvedUrl(_handle, True, listitem)
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())

def join(path, file):
    if path.endswith('/') or path.endswith('\\'):
        return path + file
    else:
        return path + '/' + file

def download(params):
    token = revalidate()
    where = _addon.getSetting('dfolder')
    if not where or not xbmcvfs.exists(where):
        popinfo('set folder!', sound=True)#_addon.getLocalizedString(30101)
        _addon.openSettings()
        return
        
    local = os.path.exists(where)
        
    normalize = 'true' == _addon.getSetting('dnormalize')
    notify = 'true' == _addon.getSetting('dnotify')
    every = _addon.getSetting('dnevery')
    try:
        every = int(re.sub(r'[^\d]+', '', every))
    except:
        every = 10
        
    try:
        link = getlink(params['ident'],token,'file_download')
        info = getinfo(params['ident'],token)
        name = info.find('name').text
        if normalize:
            name = unidecode.unidecode(name)
        bf = io.open(os.path.join(where,name), 'wb') if local else xbmcvfs.File(join(where,name), 'w')
        response = _session.get(link, stream=True)
        total = response.headers.get('content-length')
        if total is None:
            popinfo(_addon.getLocalizedString(30301) + name, icon=xbmcgui.NOTIFICATION_WARNING, sound=True)
            bf.write(response.content)
        elif not notify:
            popinfo(_addon.getLocalizedString(30302) + name)
            bf.write(response.content)
        else:
            popinfo(_addon.getLocalizedString(30302) + name)
            dl = 0
            total = int(total)
            pct = total / 100
            lastpop=0
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                bf.write(data)
                done = int(dl / pct)
                if done % every == 0 and lastpop != done:
                    popinfo(str(done) + '% - ' + name)
                    lastpop = done
        bf.close()
        popinfo(_addon.getLocalizedString(30303) + name, sound=True)
    except Exception as e:
        #TODO - remove unfinished file?
        traceback.print_exc()
        popinfo(_addon.getLocalizedString(30304) + name, icon=xbmcgui.NOTIFICATION_ERROR, sound=True)

def loaddb(dbdir,file):
    try:
        data = {}
        with io.open(os.path.join(dbdir, file), 'r', encoding='utf8') as file:
            fdata = file.read()
            file.close()
            try:
                data = json.loads(fdata, "utf-8")['data']
            except TypeError:
                data = json.loads(fdata)['data']
        return data
    except Exception as e:
        traceback.print_exc()
        return {}

def db(params):
    token = revalidate()
    updateListing=False

    dbdir = os.path.join(_profile,'db')
    if not os.path.exists(dbdir):
        link = getlink(BACKUP_DB,token)
        dbfile = os.path.join(_profile,'db.zip')
        with io.open(dbfile, 'wb') as bf:
            response = _session.get(link, stream=True)
            bf.write(response.content)
            bf.flush()
            bf.close()
        with zipfile.ZipFile(dbfile, 'r') as zf:
            zf.extractall(_profile)
        os.unlink(dbfile)
    
    if 'toqueue' in params:
        toqueue(params['toqueue'],token)
        updateListing=True
    
    if 'file' in params and 'key' in params:
        data = loaddb(dbdir,params['file'])
        item = next((x for x in data if x['id'] == params['key']), None)
        if item is not None:
            for stream in item['streams']:
                commands = []
                commands.append(( _addon.getLocalizedString(30214), 'Container.Update(' + get_url(action='db',file=params['file'],key=params['key'],toqueue=stream['ident']) + ')'))
                listitem = tolistitem({'ident':stream['ident'],'name':stream['quality'] + ' - ' + stream['lang'] + stream['ainfo'],'sizelized':stream['size']},commands)
                xbmcplugin.addDirectoryItem(_handle, get_url(action='play',ident=stream['ident'],name=item['title']), listitem, False)
    elif 'file' in params:
        data = loaddb(dbdir,params['file'])
        for item in data:
            listitem = xbmcgui.ListItem(label=item['title'])
            if 'plot' in item:
                listitem.setInfo('video', {'title': item['title'],'plot': item['plot']})
            xbmcplugin.addDirectoryItem(_handle, get_url(action='db',file=params['file'],key=item['id']), listitem, True)
    else:
        if os.path.exists(dbdir):
            dbfiles = [f for f in os.listdir(dbdir) if os.path.isfile(os.path.join(dbdir, f))]
            for dbfile in dbfiles:
                listitem = xbmcgui.ListItem(label=os.path.splitext(dbfile)[0])
                xbmcplugin.addDirectoryItem(_handle, get_url(action='db',file=dbfile), listitem, True)
    xbmcplugin.addSortMethod(_handle,xbmcplugin.SORT_METHOD_LABEL)
    xbmcplugin.endOfDirectory(_handle, updateListing=updateListing)


# Organized search: title -> movies/shows -> episode -> quality -> manual play.
def _smart_cache_path(term):
    return os.path.join(_profile, 'search-' + hashlib.sha1(term.strip().lower().encode('utf-8')).hexdigest() + '.json')


def _smart_results(term):
    import time
    from smartsearch import variants as search_variants
    filename = _smart_cache_path(term)
    try:
        with io.open(filename, 'r', encoding='utf8') as handle:
            data = json.load(handle)
        if time.time() - float(data.get('time', 0)) < 900 and isinstance(data.get('files'), list):
            return data['files']
    except (OSError, ValueError, TypeError):
        pass
    token = revalidate()
    if not token:
        return None
    result = {}
    for q in search_variants(term)[:3]:
        try:
            response = _session.post(API + 'search/', data={
                'what': q, 'category': 'video', 'sort': 'rating', 'limit': 100,
                'offset': 0, 'wst': token, 'maybe_removed': 'true'}, timeout=15)
            response.raise_for_status()
            xml = ET.fromstring(response.content)
            if not is_ok(xml):
                continue
            for entry in xml.iter('file'):
                f = todict(entry)
                ident = f.get('ident')
                if ident and f.get('name') and ident not in result:
                    # Cache only public listing fields, not credentials or session tokens.
                    result[ident] = {k:f[k] for k in ('ident','name','size','img','password') if k in f}
        except Exception:
            traceback.print_exc()
    files = list(result.values())
    try:
        if not os.path.exists(_profile):
            os.makedirs(_profile)
        with io.open(filename, 'w', encoding='utf8') as handle:
            json.dump({'time':time.time(), 'files':files}, handle, ensure_ascii=False)
    except (OSError, TypeError):
        pass
    return files


def _smart_item(label, action, **params):
    li = xbmcgui.ListItem(label=label)
    li.setArt({'icon':'DefaultFolder.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action=action, **params), li, True)


def _smart_end(kind=None):
    if kind:
        xbmcplugin.setContent(_handle, kind)
    xbmcplugin.endOfDirectory(_handle)


def smart_search(params):
    from search_catalog import grouped
    term = params.get('what', '').strip()
    if params.get('catalogue') == '1':
        from smartsearch import csfd_lookup
        if not term:
            term = ask('')
        if not term:
            xbmcplugin.endOfDirectory(_handle)
            return
        entries = csfd_lookup(term, _session)
        if entries:
            index = xbmcgui.Dialog().select('ČSFD – vyber titul', [i['title'] for i in entries])
            if index < 0:
                xbmcplugin.endOfDirectory(_handle)
                return
            term = entries[index]['title']
        else:
            popinfo('ČSFD nedostupné – hledám podle napsaného názvu')
    xbmcplugin.setPluginCategory(_handle, 'Hledání filmů a seriálů')
    if not term:
        _smart_item('🔎  ZADAT NÁZEV FILMU NEBO SERIÁLU', 'smart_type')
        _smart_item('📂  Pokročilé hledání souborů', 'search')
        for old in loadsearch()[:10]:
            _smart_item('🕘  ' + old, 'smart_search', what=old)
        _smart_end()
        return
    storesearch(term)
    files = _smart_results(term)
    if files is None:
        _smart_end()
        return
    groups = grouped(files, term)
    _smart_item('🔎  NOVÉ HLEDÁNÍ', 'smart_type')
    if groups['movies']:
        _smart_item('🎬  FILMY  (%d titulů)' % len(groups['movies']), 'smart_category', what=term, kind='movie')
    if groups['shows']:
        _smart_item('📺  SERIÁLY  (%d titulů)' % len(groups['shows']), 'smart_category', what=term, kind='show')
    _smart_item('📁  Všechny odpovídající videosoubory', 'smart_raw', what=term)
    if not groups['movies'] and not groups['shows']:
        _smart_item('Žádné přesné shody – zkus jiný název', 'smart_type')
    _smart_end()


def smart_type(params):
    term = ask('')
    if term and term.strip():
        xbmc.executebuiltin('Container.Update(' + get_url(action='smart_search',what=term.strip()) + ')')
    xbmcplugin.endOfDirectory(_handle)


def smart_category(params):
    from search_catalog import grouped, compact_quality
    term, kind = params.get('what',''), params.get('kind','movie')
    xbmcplugin.setPluginCategory(_handle, ('Filmy' if kind=='movie' else 'Seriály') + ' / ' + term)
    data = _smart_results(term)
    if data is None:
        _smart_end()
        return
    for g in grouped(data,term)['movies' if kind=='movie' else 'shows']:
        title = g['title'] + (' ('+g['year']+')' if g['year'] and kind=='movie' else '')
        label = '%s  [COLOR gray]· %s · %s souborů[/COLOR]' % (title,compact_quality(g['best']),len(g['files']))
        li = xbmcgui.ListItem(label=label)
        if g['best'].get('img'):
            li.setArt({'thumb':g['best']['img']})
        li.setInfo('video', {'title':g['title']})
        action = 'smart_files' if kind=='movie' else 'smart_seasons'
        xbmcplugin.addDirectoryItem(_handle, get_url(action=action,what=term,title=g['title'],kind=kind,year=g['year']),li,True)
    _smart_end('movies' if kind=='movie' else 'tvshows')


def smart_seasons(params):
    from search_catalog import grouped,select_group,seasons
    term,title = params.get('what',''),params.get('title','')
    xbmcplugin.setPluginCategory(_handle,'Seriál / '+title)
    data = _smart_results(term)
    if data is None:
        _smart_end()
        return
    group = select_group(grouped(data,term),'show',title)
    if group:
        for season in seasons(group['files']):
            _smart_item('SÉRIE %d' % season, 'smart_episodes',what=term,title=title,season=season)
        _smart_item('📁  Všechny soubory seriálu', 'smart_files',what=term,title=title,kind='show')
    _smart_end('seasons')


def smart_episodes(params):
    from search_catalog import grouped,select_group,episodes,compact_quality
    term,title = params.get('what',''),params.get('title','')
    season = int(params.get('season',1))
    xbmcplugin.setPluginCategory(_handle,'%s / %d. série' % (title,season))
    data = _smart_results(term)
    if data is None:
        _smart_end()
        return
    group = select_group(grouped(data,term),'show',title)
    if group:
        for number,files in episodes(group['files'],season):
            li = xbmcgui.ListItem(label='%02d. epizoda  [COLOR gray]· %s · %s verzí[/COLOR]' % (number,compact_quality(files[0]),len(files)))
            xbmcplugin.addDirectoryItem(_handle, get_url(action='smart_files',what=term,title=title,kind='show',season=season,episode=number),li,True)
    _smart_end('episodes')


def smart_files(params):
    from search_catalog import grouped,select_group,variants,compact_quality
    term,title,kind = params.get('what',''),params.get('title',''),params.get('kind','movie')
    season,episode = params.get('season') or None,params.get('episode') or None
    flt = params.get('filter','all')
    xbmcplugin.setPluginCategory(_handle,'Vybrat kvalitu / '+title)
    data = _smart_results(term)
    if data is None:
        _smart_end()
        return
    group = select_group(grouped(data,term),kind,title,params.get('year',''))
    if group is None:
        _smart_item('Výsledky vypršely, spustit hledání znovu', 'smart_search',what=term)
        _smart_end()
        return
    _smart_item('⚙  FILTR: '+{'all':'Všechny','cz':'Označení CZ','4k':'Jen 4K','1080':'Minimálně 1080p'}.get(flt,'Všechny')+' – změnit',
                'smart_filter', what=term,title=title,kind=kind,year=group['year'],season=season or '',episode=episode or '')
    selected = variants(group['files'],season=season,episode=episode,filter_name=flt)
    for f in selected:
        li = tolistitem(f)
        li.setLabel('%s  |  %s' % (compact_quality(f),labelize(f)))
        xbmcplugin.addDirectoryItem(_handle,get_url(action='play',ident=f['ident'],name=f['name']),li,False)
    if not selected:
        _smart_item('Žádná verze nevyhovuje filtru – zobrazit všechny', 'smart_files',what=term,title=title,kind=kind,year=group['year'],season=season or '',episode=episode or '',filter='all')
    _smart_end('files')


def smart_filter(params):
    options = ['Všechny kvality a jazyky','Jen CZ podle názvu','Pouze 4K','Minimálně 1080p']
    selected = xbmcgui.Dialog().select('Filtrovat nabídku souborů', options)
    if selected >= 0:
        kwargs = {k:v for k,v in params.items() if k not in ('action','filter')}
        kwargs['filter'] = ('all','cz','4k','1080')[selected]
        xbmc.executebuiltin('Container.Update(' + get_url(action='smart_files',**kwargs) + ')')
    xbmcplugin.endOfDirectory(_handle)


def smart_raw(params):
    from search_catalog import visible_files,compact_quality,quality_score
    term=params.get('what','')
    xbmcplugin.setPluginCategory(_handle,'Všechny videosoubory / '+term)
    files=_smart_results(term)
    if files is None:
        _smart_end()
        return
    for f,p in sorted(visible_files(files,term),key=lambda x:quality_score(x[0]),reverse=True)[:150]:
        li=tolistitem(f)
        li.setLabel(compact_quality(f) + ' | ' + labelize(f))
        xbmcplugin.addDirectoryItem(_handle,get_url(action='play',ident=f['ident'],name=f['name']),li,False)
    _smart_end('files')

# SCC-style browse experience built on the official Webshare filename search.
# Webshare does not return an authoritative film catalogue or film premiere dates.
def novinky_search_page(token, offset=0, what=''):
    try:
        response = api('search', {'what': what, 'category': 'video', 'sort': 'recent',
                                  'limit': 100, 'offset': offset, 'wst': token,
                                  'maybe_removed': 'true'})
        response.raise_for_status()
        doc = ET.fromstring(response.content)
        if not is_ok(doc):
            popinfo('Webshare: vyhledávání se nezdařilo', icon=xbmcgui.NOTIFICATION_WARNING)
            return None, 0
        try:
            total = int(doc.findtext('total') or 0)
        except ValueError:
            total = 0
        found = [todict(f) for f in doc.iter('file')]
        if not found and what and ' ' in what:
            # Files are frequently named with periods instead of spaces.
            response = api('search', {'what': what.replace(' ', '.'), 'category':'video',
                                      'sort':'recent', 'limit':100, 'offset':offset,
                                      'wst':token, 'maybe_removed':'true'})
            response.raise_for_status()
            fallback = ET.fromstring(response.content)
            if is_ok(fallback):
                found = [todict(f) for f in fallback.iter('file')]
                try:
                    total = int(fallback.findtext('total') or 0)
                except ValueError:
                    total = 0
        return found, total
    except Exception:
        traceback.print_exc()
        popinfo('Webshare není dostupný. Zkontroluj připojení.', icon=xbmcgui.NOTIFICATION_WARNING)
        return None, 0


def novinky_item(label, action, art='DefaultFolder.png', **kwargs):
    li = xbmcgui.ListItem(label=label)
    li.setArt({'icon': art})
    xbmcplugin.addDirectoryItem(_handle, get_url(action=action, **kwargs), li, True)


def novinky_filters():
    xbmcplugin.setPluginCategory(_handle, 'Katalog / Filtry')
    quality = _addon.getSetting('smart_min_quality') or '0'
    only_cz = _addon.getSetting('smart_only_cz') == 'true'
    only_hdr = _addon.getSetting('smart_only_hdr') == 'true'
    genre = _addon.getSetting('smart_genre')
    rating = _addon.getSetting('smart_rating') or '0'
    sort = _addon.getSetting('smart_catalog_sort') or 'recent'
    qlabel = {'0': 'Všechny kvality', '720': 'Minimálně 720p',
              '1080': 'Minimálně 1080p', '2160': 'Pouze 4K'}.get(quality, quality)
    novinky_item('Minimální kvalita: ' + qlabel, 'novinky_set', setting='quality')
    novinky_item('Preferovat CZ označení souborů: ANO [COLOR gray](při řazení)[/COLOR]', 'novinky_filters')
    novinky_item('Pouze soubory s CZ označením: ' + ('ANO' if only_cz else 'NE'), 'novinky_set', setting='cz')
    novinky_item('Pouze HDR označené soubory: ' + ('ANO' if only_hdr else 'NE'), 'novinky_set', setting='hdr')
    novinky_item('Žánr ČSFD: ' + (genre or 'Všechny'), 'novinky_set', setting='genre')
    novinky_item('Minimální hodnocení ČSFD: ' + (rating + '%' if rating != '0' else 'Všechny'), 'novinky_set', setting='rating')
    novinky_item('Řazení souborů Webshare: ' + ('Podle hodnocení' if sort == 'rating' else 'Podle nahrání'), 'novinky_set', setting='sort')
    novinky_item('Metadata ČSFD: ' + ('Zapnuta' if _addon.getSetting('smart_metadata') != 'false' else 'Vypnuta'), 'novinky_set', setting='metadata')
    novinky_item('Zpět na Novinky', 'novinky')
    xbmcplugin.endOfDirectory(_handle)


def novinky_set(params):
    param = params.get('setting', '')
    if param == 'quality':
        opts = [('Všechny kvality', '0'), ('Minimálně 720p', '720'),
                ('Minimálně 1080p', '1080'), ('Pouze 4K', '2160')]
        result = xbmcgui.Dialog().select('Minimální kvalita', [label for label, val in opts])
        if result >= 0:
            _addon.setSetting('smart_min_quality', opts[result][1])
    elif param in ('cz', 'hdr', 'metadata'):
        key = {'cz':'smart_only_cz','hdr':'smart_only_hdr','metadata':'smart_metadata'}[param]
        _addon.setSetting(key, 'false' if _addon.getSetting(key) == 'true' else 'true')
    elif param == 'genre':
        genres = ['', 'Akční', 'Animovaný', 'Dobrodružný', 'Drama', 'Fantasy',
                  'Historický', 'Horor', 'Komedie', 'Krimi', 'Mysteriózní',
                  'Rodinný', 'Romantický', 'Sci-Fi', 'Thriller', 'Válečný',
                  'Western', 'Dokumentární', 'Životopisný', 'Hudební', 'Sportovní']
        selection = xbmcgui.Dialog().select('Žánr ČSFD', ['Všechny']+genres[1:])
        if selection >= 0:
            _addon.setSetting('smart_genre', genres[selection])
    elif param == 'rating':
        choices = ['0', '50', '60', '70', '75', '80', '85', '90']
        selection = xbmcgui.Dialog().select('Minimální hodnocení ČSFD',
                           ['Všechny'] + [v + '%' for v in choices[1:]])
        if selection >= 0:
            _addon.setSetting('smart_rating', choices[selection])
    elif param == 'sort':
        selection = xbmcgui.Dialog().select('Řadit katalog podle',
                                           ['Nově nahrané na Webshare', 'Hodnocení ČSFD'])
        if selection >= 0:
            _addon.setSetting('smart_catalog_sort', 'rating' if selection else 'recent')
    xbmc.executebuiltin('Container.Update(' + get_url(action='novinky_filters') + ')')


def novinky_menu(params):
    """Main Novinky catalogue now reflects *cinema premiere dates*, not Webshare uploads."""
    xbmcplugin.setPluginCategory(_handle, 'Božský přehrávač / Premiéry ČR')
    novinky_item('PRÁVĚ UVEDENÉ FILMY [COLOR gray](posledních 30 dní)[/COLOR]',
                 'premiere_list', view='recent30')
    novinky_item('PREMIÉRY ZA POSLEDNÍ TÝDEN', 'premiere_list', view='recent7')
    novinky_item('PREMIÉRY ZA POSLEDNÍ 3 MĚSÍCE', 'premiere_list', view='recent90')
    novinky_item('BRZY V KINECH [COLOR gray](příštích 30 dní)[/COLOR]',
                 'premiere_list', view='upcoming30')
    novinky_item('PŘIPRAVOVANÉ PREMIÉRY [COLOR gray](90 dní)[/COLOR]',
                 'premiere_list', view='upcoming90')
    novinky_item('PREMIÉRY PODLE MĚSÍCŮ', 'premiere_months')
    novinky_item('OBNOVIT FILMOVÝ KALENDÁŘ', 'premiere_list', view='recent30', force=1)
    novinky_item('WEB SHARE [COLOR gray](nové soubory – samostatně)[/COLOR]', 'novinky_files')
    novinky_item('HLEDAT FILM V ČSFD / NA WEB SHARE', 'catalog_search')
    novinky_item('FILTRY KVALITY / CZ / ŽÁNRU / HODNOCENÍ', 'novinky_filters')
    novinky_item('O KALENDÁŘI PREMIÉR', 'premiere_about')
    xbmcplugin.endOfDirectory(_handle)


def novinky_files_menu(params):
    """Legacy Webshare recent browser remains available but is not called 'premieres'."""
    xbmcplugin.setPluginCategory(_handle, 'Webshare / Nově nahrané soubory')
    if params.get('view') == 'years':
        from datetime import datetime
        for year in range(datetime.now().year, datetime.now().year - 8, -1):
            novinky_item('Soubory s rokem %s v názvu' % year,
                         'novinky_list', kind='movies', year=year, offset=0)
    else:
        novinky_item('NOVÉ FILMOVÉ SOUBORY', 'novinky_list', kind='movies', offset=0)
        novinky_item('NOVÉ EPIZODY', 'novinky_list', kind='episodes', offset=0)
        novinky_item('SERIÁLY S NOVÝM SOUBOREM', 'novinky_list', kind='shows', offset=0)
        novinky_item('VŠECHNY NOVÉ SOUBORY', 'novinky_list', kind='all', offset=0)
        novinky_item('ROKY PODLE NÁZVU SOUBORŮ', 'novinky_files', view='years')
    xbmcplugin.endOfDirectory(_handle)


def _premiere_client():
    from premiere_calendar import PremiereCalendar
    return PremiereCalendar(_profile)


def premiere_months(params):
    from datetime import date
    from premiere_calendar import next_month
    now = date.today()
    xbmcplugin.setPluginCategory(_handle, 'Kalendář premiér / Měsíce')
    month_names = ('leden','únor','březen','duben','květen','červen','červenec',
                   'srpen','září','říjen','listopad','prosinec')
    for offset in range(-6, 19):
        mon = next_month(now.year, now.month, offset)
        y, m = (int(x) for x in mon.split('-'))
        novinky_item('%s %d%s' % (month_names[m-1].capitalize(), y,
                     ' [COLOR gray]• tento měsíc[/COLOR]' if offset == 0 else ''),
                     'premiere_list', view='month', month=mon)
    xbmcplugin.endOfDirectory(_handle)


def premiere_list(params):
    """Calendar-first browse; Webshare login is not required to view cinema releases."""
    from datetime import date
    from premiere_calendar import select_events, nice_date
    allowed = ('recent7','recent30','recent90','upcoming30','upcoming90','month')
    view = params.get('view','recent30')
    if view not in allowed:
        view = 'recent30'
    month = params.get('month','')
    try:
        page = max(0, min(int(params.get('page',0)), 250))
    except (TypeError, ValueError):
        page = 0
    client = _premiere_client()
    events = client.load(force=params.get('force') == '1')
    all_items = select_events(events, view=view, month=month, today=date.today())
    xbmcplugin.setPluginCategory(_handle, 'České kinopremiéry / ' +
          (month if view == 'month' else view))
    xbmcplugin.setContent(_handle, 'movies')
    if not events:
        novinky_item('Kalendář se nepodařilo načíst. Zkusit znovu', 'premiere_list',
                     view=view, month=month, force=1)
        novinky_item('O zdroji kalendáře a připojení', 'premiere_about')
        xbmcplugin.endOfDirectory(_handle)
        return
    if client.stale:
        novinky_item('POZOR: zobrazen poslední uložený kalendář (server nedostupný)',
                     'premiere_list', view=view, month=month, force=1)
    page_size = 15
    start = page * page_size
    chosen = all_items[start:start+page_size]
    # Preserve filtering by genre/rating when metadata can be fetched.
    genre = _addon.getSetting('smart_genre')
    try:
        min_rating = int(_addon.getSetting('smart_rating') or '0')
    except ValueError:
        min_rating = 0
    with_metadata = _addon.getSetting('smart_metadata') != 'false' or bool(genre or min_rating)
    if with_metadata and chosen:
        catalogue = _csfd_client()
        groups = [{'title':x['title'], 'year':'', 'metadata':None} for x in chosen]
        catalogue.lookup_many(groups, max_new=len(groups))
        for item, group in zip(chosen, groups):
            item['metadata'] = group.get('metadata')
        if genre or min_rating:
            from csfd_metadata import passes_metadata_filter
            chosen = [x for x in chosen if passes_metadata_filter(x, genre, min_rating)]
    if page:
        novinky_item('◀ PŘEDCHOZÍ STRÁNKA', 'premiere_list', view=view,
                     month=month, page=page-1)
    for item in chosen:
        label = '%s  [COLOR gray]• %s (kino ČR)[/COLOR]' % (
                item['title'], nice_date(item['premiere']))
        li = xbmcgui.ListItem(label=label)
        info = {'title':item['title'], 'mediatype':'movie',
                'plot':'Premiéra v českých kinech: %s\nDistributor: %s\nKino jazyk: %s' % (
                       nice_date(item['premiere']),item['distributor'] or 'neuveden',
                       item['language'] or 'neuvedeno')}
        try:
            li.setInfo('video', info)
        except Exception:
            pass
        _attach_movie_metadata(li, {'title':item['title'], 'group_kind':'movie'}, item.get('metadata'))
        xbmcplugin.addDirectoryItem(_handle, get_url(action='premiere_title',
              title=item['title'], original=item['original'], date=item['premiere'],
              distributor=item['distributor'], language=item['language']), li, True)
    if not chosen:
        novinky_item('V tomto období nejsou položky odpovídající filtrům.', 'novinky_filters')
    if start+page_size < len(all_items):
        novinky_item('DALŠÍ PREMIÉRY ▶', 'premiere_list', view=view, month=month, page=page+1)
    xbmcplugin.endOfDirectory(_handle)


def premiere_title(params):
    from premiere_calendar import nice_date
    title = params.get('title','').strip()
    original = params.get('original','').strip()
    dt = params.get('date','')
    if not title:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    xbmcplugin.setPluginCategory(_handle, 'Kino premiéra / ' + title)
    date_label = nice_date(dt) if re.match(r'^\d{4}-\d{2}-\d{2}$',dt) else 'neuvedena'
    client = _csfd_client() if _addon.getSetting('smart_metadata') != 'false' else None
    metadata = client.lookup(title) if client else None
    if client:
        client.save()
    text = ('Premiéra v českých kinech: %s\nČeský název: %s\n'
            'Původní název: %s\nDistributor: %s\n'
            'Kino jazyková verze: %s\n\n'
            'Tento kalendář nesleduje dostupnost na Webshare.' % (
            date_label, title, original or 'neuveden',
            params.get('distributor') or 'neuveden',
            params.get('language') or 'neuvedena'))
    li = xbmcgui.ListItem(label='INFORMACE / ' + title)
    li.setInfo('video',{'title':title,'plot':text,'mediatype':'movie'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='premiere_info',title=title,
        original=original,date=dt,distributor=params.get('distributor',''),
        language=params.get('language','')), li, False)
    if metadata:
        mi = xbmcgui.ListItem(label='ČSFD | Plakát, popis, hodnocení')
        _attach_movie_metadata(mi, {'title':title,'group_kind':'movie'}, metadata)
        xbmcplugin.addDirectoryItem(_handle,
            get_url(action='catalog_info',title=title), mi, False)
    year = metadata.get('year','') if metadata else ''
    novinky_item('HLEDAT SOUBORY NA WEBSHARE [COLOR gray](vybrat kvalitu)[/COLOR]',
                 'novinky_detail', title=title, original=original, year=year, kind='movie')
    novinky_item('CHYTRÉ VYHLEDÁVÁNÍ – ČESKÝ NÁZEV', 'smart_search',what=title)
    if original and original.casefold() != title.casefold():
        novinky_item('CHYTRÉ VYHLEDÁVÁNÍ – ORIGINÁLNÍ NÁZEV',
                     'smart_search',what=original)
    xbmcplugin.endOfDirectory(_handle)


def premiere_info(params):
    from premiere_calendar import nice_date
    dt = params.get('date','')
    message = ('Český název: %s\nOriginální název: %s\nPremiéra v kinech ČR: %s\n'
              'Distributor: %s\nJazyková verze kina: %s\n\n'
              'Datum premiéry neznamená zveřejnění souboru na Webshare. '
              'Označení dabingu kina neověřuje zvukové stopy souboru.' % (
              params.get('title',''), params.get('original','') or 'neuveden',
              nice_date(dt) if re.match(r'^\d{4}-\d{2}-\d{2}$',dt) else 'neuvedeno',
              params.get('distributor','') or 'neuveden',
              params.get('language','') or 'neuvedena'))
    xbmcgui.Dialog().textviewer('Informace o kinopremiéře',message)
    xbmcplugin.endOfDirectory(_handle)


def premiere_about(params):
    xbmcgui.Dialog().textviewer('Božský přehrávač / zdroj premiér',
       'Novinky: skutečná data premiér filmů v českých kinech, nikoli Webshare uploady.\n'
       'Zdroj: https://www.fuxoft.cz/vyplody/premiery/premiery.ics\n'
       'Kalendář převádí data českých filmových distributorů a může obsahovat změny termínů.\n'
       'Automatická aktualizace každých 24 hodin; při výpadku se použije starší cache '
       '(maximálně 45 dnů).\n'
       'ČSFD plakáty, popisy a hodnocení jsou volitelně přes neoficiální CZDB.\n'
       'Na Webshare se vyhledává až po výběru filmu, přehrávání je pouze ruční.\n'
       'Filtry rozlišení/CZ/HDR platí pro videosoubory, nikoli filmové premiéry.')
    xbmcplugin.endOfDirectory(_handle)


def _csfd_client():
    from csfd_metadata import Catalogue
    return Catalogue(_profile)


def _attach_movie_metadata(li, group, metadata):
    """Video information and artwork shown natively in Kodi skin views."""
    from csfd_metadata import decorate_label
    li.setLabel(decorate_label(li.getLabel(), metadata))
    if not metadata:
        return
    data = {'title': metadata.get('title') or group.get('title', ''),
            'plot': metadata.get('plot', ''),
            'mediatype': 'episode' if group.get('group_kind') == 'episode' else
                         'tvshow' if group.get('group_kind') == 'show' else 'movie'}
    if metadata.get('year'):
        try:
            data['year'] = int(metadata['year'])
        except ValueError:
            pass
    if metadata.get('rating') is not None:
        data['rating'] = metadata['rating'] / 10.0
    if metadata.get('genres'):
        data['genre'] = ' / '.join(metadata['genres'])
    try:
        li.setInfo('video', data)
    except Exception:
        traceback.print_exc()
    art = {}
    if metadata.get('poster'):
        art.update({'poster':metadata['poster'], 'thumb':metadata['poster'],
                    'icon':metadata['poster']})
    if metadata.get('fanart'):
        art['fanart'] = metadata['fanart']
    if art:
        li.setArt(art)
    if metadata.get('csfd_url'):
        li.addContextMenuItems([('Zobrazit údaje ČSFD',
            'RunPlugin(' + get_url(action='catalog_info',title=group['title'],
                                 year=group.get('year','')) + ')')])


def catalog_info(params):
    title = params.get('title', '')
    if not title:
        return
    client = _csfd_client()
    data = client.lookup(title, params.get('year', ''))
    client.save()
    if not data:
        popinfo('Podrobnosti ČSFD nejsou dostupné', icon=xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(_handle)
        return
    details = [data['title'] + (' (' + data['year'] + ')' if data['year'] else '')]
    if data.get('original'):
        details.append('Originální název: ' + data['original'])
    if data.get('rating') is not None:
        details.append('Hodnocení ČSFD: %d %%' % data['rating'])
    if data.get('genres'):
        details.append('Žánry: ' + ', '.join(data['genres']))
    if data.get('plot'):
        details.append('\n' + data['plot'])
    if data.get('csfd_url'):
        details.append('\nČSFD: '+data['csfd_url'])
    xbmcgui.Dialog().textviewer('ČSFD / ' + title, '\n'.join(details))
    xbmcplugin.endOfDirectory(_handle)


def catalog_about(params):
    xbmcgui.Dialog().textviewer('O Božském přehrávači',
        'Nově přidané = soubory Webshare podle API sort=recent, nikoliv datum premiéry.\n'
        'Rok se nejprve odhaduje z názvu souboru.\n'
        'ČSFD metadata dodává nezávislá neoficiální služba CZDB; může být nedostupná.\n'
        'Plakáty, hodnocení a žánry se ukáží pouze při důvěryhodné shodě názvu a roku.\n'
        'Filtr žánru/hodnocení využívá metadata nejvýše prvních 24 titulů aktuální stránky.\n'
        'CZ a HDR jsou pouze značky v názvu souboru, skutečné zvukové stopy se neověřují.\n'
        'Spuštění zvoleného souboru je vždy ruční a vyžaduje účet Webshare.')
    xbmcplugin.endOfDirectory(_handle)


def catalog_search(params):
    """Use a title from the Czech catalogue, then browse real Webshare candidates."""
    query = params.get('title')
    if query is None:
        query = ask('')
    if not query:
        xbmcplugin.endOfDirectory(_handle)
        return
    xbmcplugin.setPluginCategory(_handle, 'Katalog ČSFD / ' + query)
    client = _csfd_client()
    data = client.lookup(query)
    client.save()
    if data:
        item = {'title':data['title'], 'year':data['year'], 'group_kind':'movie'}
        li = xbmcgui.ListItem(label=data['title'] + (' (%s)'%data['year'] if data['year'] else ''))
        _attach_movie_metadata(li, item, data)
        xbmcplugin.addDirectoryItem(_handle, get_url(action='novinky_detail',
            title=data['title'], year=data['year'], kind='movie', original=data.get('original','')), li, True)
        if data.get('original') and data['original'] != data['title']:
            li2 = xbmcgui.ListItem(label='Vyhledat na Webshare také: ' + data['original'])
            xbmcplugin.addDirectoryItem(_handle, get_url(action='smart_search', what=data['original']), li2, True)
    else:
        li = xbmcgui.ListItem(label='ČSFD metadata nejsou dostupná; vyhledat na Webshare: ' + query)
        xbmcplugin.addDirectoryItem(_handle, get_url(action='smart_search', what=query), li, True)
    xbmcplugin.endOfDirectory(_handle)


def novinky_list(params):
    from novinky_catalogue import build_groups, label_group
    kind = params.get('kind', 'all')
    if kind not in ('all', 'movies', 'episodes', 'shows'):
        kind = 'all'
    try:
        offset = min(20000, max(0, int(params.get('offset', 0))))
    except ValueError:
        offset = 0
    year = params.get('year', '')
    xbmcplugin.setPluginCategory(_handle, 'Novinky / ' + kind + (' / '+year if year else ''))
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    files, total = novinky_search_page(token, offset, year if year else '')
    if files is None:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    minimum = int(_addon.getSetting('smart_min_quality') or '0')
    only_cz = _addon.getSetting('smart_only_cz') == 'true'
    only_hdr = _addon.getSetting('smart_only_hdr') == 'true'
    groups = build_groups(files, kind=kind, minimum=minimum,
                          only_cz=only_cz, only_hdr=only_hdr, year=year)
    genre = _addon.getSetting('smart_genre')
    rating = int(_addon.getSetting('smart_rating') or '0')
    if _addon.getSetting('smart_metadata') != 'false' or genre or rating:
        from csfd_metadata import passes_metadata_filter
        client = _csfd_client()
        client.lookup_many(groups[:24], max_new=24)
        groups = [g for g in groups if passes_metadata_filter(g,genre,rating)]
    if _addon.getSetting('smart_catalog_sort') == 'rating':
        groups.sort(key=lambda g: ((g.get('metadata') or {}).get('rating') or -1), reverse=True)
    xbmcplugin.setContent(_handle, 'episodes' if kind == 'episodes' else 'tvshows' if kind == 'shows' else 'movies')
    if offset:
        novinky_item('◀ PŘEDCHOZÍ STRÁNKA', 'novinky_list', kind=kind, year=year,
                     offset=max(0, offset-100))
    for group in groups:
        variant = group['best']
        li = xbmcgui.ListItem(label=label_group(group))
        if variant.get('img'):
            li.setArt({'thumb': variant['img']})
        _attach_movie_metadata(li, group, group.get('metadata'))
        kind_of_group = group['group_kind']
        # Lists link to a new search, not to an ephemeral in-memory cache.
        action = 'novinky_show' if kind_of_group == 'show' else 'novinky_detail'
        dest_kind = 'episode' if kind_of_group == 'episode' else 'movie' if kind_of_group == 'movie' else 'series'
        xbmcplugin.addDirectoryItem(_handle,
            get_url(action=action, title=group['title'], year=group['year'],
                    kind=dest_kind, season=group['season'] or '',
                    episode=group['episode'] or ''), li, True)
    if not groups:
        novinky_item('Žádné odpovídající položky na této stránce. Změň filtry nebo přejdi dále.',
                     'novinky_filters')
    if offset+100 < total:
        novinky_item('DALŠÍ STRÁNKA ▶', 'novinky_list', kind=kind, year=year,
                     offset=offset+100)
    xbmcplugin.endOfDirectory(_handle)


def novinky_show(params):
    from novinky_catalogue import build_groups, label_group, normalize, parse_video_name
    title = params.get('title', '')
    if not title:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    try:
        offset = min(10000, max(0, int(params.get('offset', 0))))
    except ValueError:
        offset = 0
    xbmcplugin.setPluginCategory(_handle, 'Seriál / ' + title)
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    files, total = novinky_search_page(token, offset, title)
    if files is None:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    target = normalize(title)
    files = [f for f in files if normalize((parse_video_name(f.get('name')) or {}).get('title')) == target]
    groups = build_groups(files, kind='episodes',
        minimum=int(_addon.getSetting('smart_min_quality') or '0'),
        only_cz=_addon.getSetting('smart_only_cz') == 'true',
        only_hdr=_addon.getSetting('smart_only_hdr') == 'true')
    if _addon.getSetting('smart_metadata') != 'false':
        # One metadata item for the parent show instead of N requests per episode.
        catalogue = _csfd_client()
        show_meta = catalogue.lookup(title)
        catalogue.save()
        for group in groups:
            group['metadata'] = show_meta
    if offset:
        novinky_item('◀ PŘEDCHOZÍ STRÁNKA', 'novinky_show', title=title, offset=max(0, offset-100))
    for group in groups:
        li = xbmcgui.ListItem(label=label_group(group))
        if group['best'].get('img'):
            li.setArt({'thumb': group['best']['img']})
        _attach_movie_metadata(li, group, group.get('metadata'))
        xbmcplugin.addDirectoryItem(_handle, get_url(action='novinky_detail', title=group['title'],
              kind='episode', season=group['season'], episode=group['episode']), li, True)
    if not groups:
        novinky_item('Žádné jednotlivé epizody na této stránce; zkus běžné vyhledávání',
                     'smart_search', what=title)
    if offset+100 < total:
        novinky_item('DALŠÍ STRÁNKA ▶', 'novinky_show', title=title, offset=offset+100)
    xbmcplugin.endOfDirectory(_handle)


def novinky_detail(params):
    from novinky_catalogue import parse_video_name, normalize, sort_variants, matching, variant_label
    title = params.get('title', '')
    kind = params.get('kind', 'movie')
    year = params.get('year', '')
    season = params.get('season', '')
    episode = params.get('episode', '')
    xbmcplugin.setPluginCategory(_handle, 'Vybrat soubor / ' + title)
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    try:
        offset = min(10000, max(0, int(params.get('offset', 0))))
    except ValueError:
        offset = 0
    files, total = novinky_search_page(token, offset, title)
    if files is None:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return
    target = normalize(title)
    original = params.get('original','')
    if original and original != title:
        more, _ = novinky_search_page(token, 0, original)
        if more:
            ids = {f.get('ident') for f in files}
            files.extend(f for f in more if f.get('ident') not in ids)
    matches = []
    for f in files:
        i = parse_video_name(f.get('name', ''))
        if not i or normalize(i['title']) not in (target, normalize(original) if original else target):
            continue
        if year and i['year'] and i['year'] != year:
            continue
        if kind == 'episode':
            if i['kind'] != 'episode' or str(i['season']) != season or str(i['episode']) != episode:
                continue
        elif i['kind'] != 'movie':
            continue
        if f.get('password') == '1':
            continue
        matches.append(f)
    minimum = int(_addon.getSetting('smart_min_quality') or '0')
    only_cz = _addon.getSetting('smart_only_cz') == 'true'
    only_hdr = _addon.getSetting('smart_only_hdr') == 'true'
    matches = [f for f in matches if matching(f, parse_video_name(f['name']), minimum, only_cz, only_hdr)]
    seen = set()
    if _addon.getSetting('smart_metadata') != 'false':
        catalogue = _csfd_client()
        meta = catalogue.lookup(title, year)
        catalogue.save()
        if meta and meta.get('plot'):
            li_info = xbmcgui.ListItem(label='INFORMACE ČSFD | ' + meta.get('title', title))
            xbmcplugin.addDirectoryItem(_handle, get_url(action='catalog_info', title=title, year=year), li_info, False)
    if offset:
        novinky_item('◀ PŘEDCHOZÍ STRÁNKA', 'novinky_detail', title=title, kind=kind, year=year, season=season, episode=episode, offset=max(0, offset-100))
    for f in sort_variants(matches):
        if f['ident'] in seen:
            continue
        seen.add(f['ident'])
        li = tolistitem(f)
        li.setLabel(variant_label(f) + ' | ' + labelize(f))
        xbmcplugin.addDirectoryItem(_handle,
            get_url(action='play', ident=f['ident'], name=f['name']), li, False)
    if not seen:
        novinky_item('Nic nenalezeno. Zkus Smart Search nebo změň filtry.', 'smart_search', what=title)
    if offset + 100 < total:
        novinky_item('DALŠÍ SOUBORY ▶', 'novinky_detail', title=title, kind=kind, year=year, season=season, episode=episode, offset=offset+100)
    novinky_item('SMART SEARCH: zobrazit další varianty', 'smart_search', what=title)
    xbmcplugin.endOfDirectory(_handle)

def menu():
    # Calendar browse must work even if the Webshare account is not configured.
    # Actual Webshare operations call revalidate() when needed.
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name'))
    li = xbmcgui.ListItem(label='FILMOVÉ PREMIÉRY ČR | Kalendář · ČSFD · Webshare')
    li.setArt({'icon':'DefaultAddonsRecentlyUpdated.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='novinky'), li, True)
    li = xbmcgui.ListItem(label='VYHLEDAT FILM NEBO SERIÁL | Přehledné výsledky')
    li.setArt({'icon':'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='smart_search'), li, True)
    li = xbmcgui.ListItem(label='Hledat podle ČSFD (experimentální)')
    li.setArt({'icon':'DefaultVideoPlaylists.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='smart_search',catalogue=1), li, True)
    listitem = xbmcgui.ListItem(label='Pokročilé hledání · jednotlivé soubory')
    listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='search'), listitem, True)
    
    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30202))
    listitem.setArt({'icon': 'DefaultPlaylist.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='queue'), listitem, True)
    
    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30203))
    listitem.setArt({'icon': 'DefaultAddonsUpdates.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='history'), listitem, True)
    
    if 'true' == _addon.getSetting('experimental'):
        listitem = xbmcgui.ListItem(label='Backup DB')
        listitem.setArt({'icon': 'DefaultAddonsZip.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='db'), listitem, True)

    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30204))
    listitem.setArt({'icon': 'DefaultAddonService.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='settings'), listitem, False)

    xbmcplugin.endOfDirectory(_handle)

def router(paramstring):
    params = dict(parse_qsl(paramstring))
    if params:
        if params.get('action') == 'premiere_list':
            premiere_list(params)
        elif params.get('action') == 'premiere_months':
            premiere_months(params)
        elif params.get('action') == 'premiere_title':
            premiere_title(params)
        elif params.get('action') == 'premiere_info':
            premiere_info(params)
        elif params.get('action') == 'premiere_about':
            premiere_about(params)
        elif params.get('action') == 'novinky_files':
            novinky_files_menu(params)
        elif params.get('action') == 'catalog_search':
            catalog_search(params)
        elif params.get('action') == 'catalog_info':
            catalog_info(params)
        elif params.get('action') == 'catalog_about':
            catalog_about(params)
        elif params.get('action') == 'novinky':
            novinky_menu(params)
        elif params.get('action') == 'novinky_list':
            novinky_list(params)
        elif params.get('action') == 'novinky_show':
            novinky_show(params)
        elif params.get('action') == 'novinky_detail':
            novinky_detail(params)
        elif params.get('action') == 'novinky_filters':
            novinky_filters()
        elif params.get('action') == 'novinky_set':
            novinky_set(params)
        elif params.get('action') == 'smart_search':
            smart_search(params)
        elif params.get('action') == 'smart_type':
            smart_type(params)
        elif params.get('action') == 'smart_category':
            smart_category(params)
        elif params.get('action') == 'smart_seasons':
            smart_seasons(params)
        elif params.get('action') == 'smart_episodes':
            smart_episodes(params)
        elif params.get('action') == 'smart_files':
            smart_files(params)
        elif params.get('action') == 'smart_filter':
            smart_filter(params)
        elif params.get('action') == 'smart_raw':
            smart_raw(params)
        elif params['action'] == 'search':
            search(params)
        elif params['action'] == 'queue':
            queue(params)
        elif params['action'] == 'history':
            history(params)
        elif params['action'] == 'settings':
            settings(params)
        elif params['action'] == 'info':
            info(params)
        elif params['action'] == 'play':
            play(params)
        elif params['action'] == 'download':
            download(params)
        elif params['action'] == 'db':
            db(params)
        else:
            menu()
    else:
        menu()
