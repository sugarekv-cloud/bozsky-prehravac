# -*- coding: utf-8 -*-
"""Kodi dialogs for choosing previews, confirming identities and managing the local index."""
import threading
import xbmcgui
from cinema_visual_index import eligible
from cinema_visual_recognition import fetch_file, preview_urls, recognize


def invalidate(service):
    service.search_cache.clear()
    service.search_cache_time.clear()
    service.search_scan.clear()
    service.series_cache.clear()
    service.suggestion_cache.clear()


def browse(service,dialog):
    text=dialog.input('Část názvu souboru (prázdné = poslední videa)')
    offset=0
    while True:
        page,total=service.fetch(service.token,offset,text,sort='recent')
        if page is None:
            raise ValueError('Webshare právě neodpovídá.')
        files=[f for f in page if eligible(f) and preview_urls(f)]
        items=[]
        for file in files:
            item=xbmcgui.ListItem(label=file['name'],label2='Náhled souboru · identifikátor '+file['ident'])
            item.setArt({'thumb':preview_urls(file)[0]})
            items.append(item)
        more=len(page)>=100 and (not total or offset+100<int(total))
        if more:
            items.append(xbmcgui.ListItem(label='Dalších 100 souborů'))
        if not items:
            dialog.ok('Náhledy Webshare','Na této stránce nejsou dostupné podporované náhledy.')
            return None
        selected=dialog.select('Vyber video podle náhledu',items,useDetails=True)
        if selected<0:return None
        if selected<len(files):return fetch_file(files[selected]['ident'],service.token)
        offset+=100


def edit_identity(dialog,proposal=None):
    proposal=proposal or {}
    title=dialog.input('Potvrzený název filmu / seriálu',defaultt=proposal.get('title','')).strip()
    if not title:return None
    year=dialog.input('Rok vydání (lze ponechat prázdné)',defaultt=proposal.get('year','')).strip()
    original=dialog.input('Původní název pro hledání (nepovinné)',defaultt=proposal.get('original','')).strip()
    selected=dialog.select('Typ videa',['Film','Konkrétní epizoda seriálu'],
                           preselect=1 if proposal.get('kind')=='series' else 0)
    if selected<0:return None
    match={'title':title,'year':year,'original':original,'kind':'movie' if selected==0 else 'episode'}
    if selected==1:
        season=dialog.input('Číslo série (0 = speciály)')
        episode=dialog.input('Číslo epizody')
        if not season or not episode:return None
        match.update(season=season,episode=episode)
    from cinema_visual_index import identity
    return identity(match)


def analyze(service,file,key):
    """Keep Kodi responsive; cancelled work never writes identities or opens dialogs."""
    running=getattr(service,'_visual_running',None)
    if running is not None and not running.is_set():
        raise ValueError('Předchozí rozpoznávání ještě dobíhá. Zkus to za chvíli.')
    done=threading.Event();cancel=threading.Event();result={}
    service._visual_running=done
    def worker():
        try:
            result['items']=recognize(file,key,cancelled=cancel.is_set)
        except ValueError as exc:
            result['error']=str(exc)
        except Exception:
            result['error']='Rozpoznávání se nepodařilo dokončit.'
        finally:
            done.set()
    progress=xbmcgui.DialogProgress()
    progress.create('KIVORA','Rozpoznávám vybrané náhledy…')
    threading.Thread(target=worker,daemon=True).start()
    try:
        while not done.wait(0.1):
            if progress.iscanceled():
                cancel.set();return None
        if progress.iscanceled():return None
        if 'error' in result:raise ValueError(result['error'])
        return result.get('items',[])
    finally:
        progress.close()


def identify(addon,service,file,dialog):
    # Refresh and verify selected file before any external AI request or indexing.
    if not service.availability.check_files([file],limit=1):
        raise ValueError('Soubor již není dostupný ke stažení.')
    while True:
        mode=dialog.select('Rozpoznání: '+file['name'],[
            'Rozpoznat náhledy pomocí AI (vyžaduje API klíč)',
            'Znám název – přiřadit ručně',
            'Zobrazit náhledy'])
        if mode<0:return None
        if mode!=2:break
        urls=preview_urls(file)
        if not urls:
            dialog.ok('KIVORA','Soubor nemá podporovaný náhled.')
        else:
            items=[]
            for i,url in enumerate(urls):
                item=xbmcgui.ListItem(label='Náhled' if i==0 else 'Pás snímků')
                item.setArt({'thumb':url});items.append(item)
            dialog.select('Náhledy vybraného souboru',items,useDetails=True)
    proposal=None
    if mode==0:
        key=addon.getSetting('visual_api_key').strip()
        if not key:
            dialog.ok('Nastavení obrazové AI',
                'Zadej vlastní OpenAI API klíč v nastavení doplňku → Rozpoznávání videí. '
                'Bez klíče lze použít ruční přiřazení.')
            addon.openSettings()
            return None
        if not dialog.yesno('Odeslat náhledy k rozpoznání?',
            'Vybrané náhledy budou odeslány do OpenAI API. Účet Webshare ani celé video se neodesílají. '
            'Použití API může čerpat placený kredit. Výsledek je odhad, který musíš potvrdit.'):
            return None
        proposals=analyze(service,file,key)
        if proposals is None:return None
        if not proposals:
            dialog.ok('Film nerozpoznán','Z náhledů nevznikl použitelný návrh. Nic nebylo přiřazeno.')
            return None
        selected=dialog.select('Možné shody – ověř podle videa',[
            p['title']+(' ('+p['year']+')' if p['year'] else '') for p in proposals])
        if selected<0:return None
        proposal=proposals[selected]
    match=edit_identity(dialog,proposal)
    if not match:return None
    caption=match['title']+(' ('+match['year']+')' if match['year'] else '')
    if match['kind']=='episode':caption+=' S%02dE%02d'%(match['season'],match['episode'])
    if not dialog.yesno('Uložit potvrzené přiřazení?',file['name']+' → '+caption+
                       '\nPotvrď jen pokud název a případná epizoda skutečně odpovídají videu.'):
        return None
    service.visual_index.confirm(file,match)
    invalidate(service)
    dialog.notification('KIVORA','Přiřazení uloženo; soubor lze hledat podle názvu.')
    return caption


def manage(service,dialog):
    files=service.visual_index.all()
    if not files:
        dialog.ok('Rozpoznané soubory','Zatím nemáš žádné potvrzené přiřazení.')
        return None
    selected=dialog.select('Potvrzená přiřazení',[
        f['_kivora_identity']['title']+' – '+f['name'] for f in files])
    if selected<0:return None
    file=files[selected]
    action=dialog.select(file['_kivora_identity']['title'],['Vyhledat titul','Odstranit chybné přiřazení'])
    if action==0:
        match=file['_kivora_identity'];query=match['title']
        if match['year']:query+=' ('+match['year']+')'
        if match['kind']=='episode':query+=' S%02dE%02d'%(match['season'],match['episode'])
        return query
    if action==1 and dialog.yesno('Odstranit přiřazení?',file['name']):
        service.visual_index.remove(file['ident']);invalidate(service)
    return None


def open_visual_search(addon,service):
    dialog=xbmcgui.Dialog()
    try:
        action=dialog.select('KIVORA · hledání podle náhledů',[
            'Procházet náhledy souborů na Webshare',
            'Vložit odkaz / identifikátor souboru',
            'Spravovat potvrzená přiřazení',
            'Nastavit API klíč pro obrazovou AI'])
        if action==3:
            addon.openSettings();return None
        if action==2:return manage(service,dialog)
        if action==0:
            file=browse(service,dialog)
        elif action==1:
            value=dialog.input('Odkaz na soubor Webshare nebo jeho identifikátor')
            if not value:return None
            file=fetch_file(value,service.token)
        else:return None
        if file:return identify(addon,service,file,dialog)
    except (ValueError,OSError) as exc:
        dialog.ok('KIVORA · rozpoznání videa',str(exc))
    return None
