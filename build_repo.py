#!/usr/bin/env python3
'''Generate a Kodi repository website ready for GitHub Pages.
Usage: python build_repo.py --owner YOUR_GITHUB_USER --output site
'''
import argparse
import hashlib
import html
from pathlib import Path
import shutil
import zipfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
PLUGIN_ID='plugin.video.fckyo'
REPO_ID='repository.bozskyprehravac'
REPO_NAME='KIVORA repozitář'
GITHUB_REPO='bozsky-prehravac'

def zip_folder(path, target):
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(path.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc') and p.resolve()!=target.resolve():
                z.write(p,p.relative_to(path.parent).as_posix())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--owner',required=True,help='GitHub user or organization account')
    ap.add_argument('--output',default='site')
    args=ap.parse_args()
    owner=args.owner.strip()
    if not owner or not all(x.isalnum() or x=='-' for x in owner):
        ap.error('Invalid GitHub account name')
    base=f'https://{owner.lower()}.github.io/{GITHUB_REPO}/'
    out=(HERE/args.output).resolve()
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    (out/'.nojekyll').write_text('',encoding='utf-8')
    plugin=HERE/PLUGIN_ID
    # Render the original logo into every published addon/repository ZIP.
    from tools.create_brand import make_brand
    from tools.create_genre_icons import make_genre_icons
    make_brand()
    genre_art=make_genre_icons()
    assert len(genre_art)==24 and all(p.is_file() and p.stat().st_size>1000
                                      for p in genre_art)
    plugxml=ET.parse(plugin/'addon.xml').getroot()
    version=plugxml.get('version')
    assert plugxml.get('id')==PLUGIN_ID and version
    plugin_file=out/PLUGIN_ID/f'{PLUGIN_ID}-{version}.zip'
    zip_folder(plugin,plugin_file)
    shutil.copy2(plugin/'resources/icon.png',out/PLUGIN_ID/'icon.png')
    # Generate the Kodi repository addon with a real, owner-specific Pages URL.
    repoxml=f'''<?xml version="1.0" encoding="UTF-8"?>
<addon id="{REPO_ID}" name="{REPO_NAME}" version="1.0.0" provider-name="KIVORA – komunitní repozitář">
  <requires><import addon="xbmc.addon" version="12.0.0"/></requires>
  <extension point="xbmc.addon.repository">
    <dir>
      <info compressed="false">{base}addons.xml</info>
      <checksum>{base}addons.xml.md5</checksum>
      <datadir>{base}</datadir>
      <hashes>false</hashes>
    </dir>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="cs_CZ">Aktualizace doplňku KIVORA</summary>
    <description lang="cs_CZ">Neoficiální aktualizace doplňku KIVORA pro Kodi.</description>
    <platform>all</platform>
  </extension>
</addon>
'''
    repodir=out/REPO_ID
    repodir.mkdir()
    (repodir/'addon.xml').write_text(repoxml,encoding='utf-8')
    shutil.copy2(plugin/'resources/icon.png',repodir/'icon.png')
    repo_file=repodir/f'{REPO_ID}-1.0.0.zip'
    zip_folder(repodir,repo_file) # Careful: repo zip is within folder; see safeguard below.
    shutil.copy2(repo_file,out/repo_file.name)
    reporoot=ET.fromstring(repoxml)
    addons=ET.Element('addons')
    addons.append(reporoot)
    addons.append(plugxml)
    xmlbytes=b'<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(addons,encoding='utf-8')
    (out/'addons.xml').write_bytes(xmlbytes)
    (out/'addons.xml.md5').write_text(hashlib.md5(xmlbytes).hexdigest(),encoding='ascii')
    (out/'index.html').write_text(f'''<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>KIVORA – Kodi repozitář</title>
<style>body{{font:18px system-ui;background:#0c1420;color:#f2e6d2;max-width:800px;margin:5em auto;padding:1em}}a{{color:#ffcc66}}h1{{font-size:2.2em}}</style><h1>KIVORA</h1><p>Neoficiální doplněk Kodi s kalendářem filmových premiér a vyhledáváním přes Webshare.</p><p><a href="{html.escape(repo_file.name)}">Instalovat KIVORA repozitář do Kodi</a></p><p><a href="{PLUGIN_ID}/{PLUGIN_ID}-{version}.zip">Stáhnout KIVORA {version} (ruční aktualizace)</a></p><p>Pokud Kodi nenabízí aktualizaci: Doplňky → Moje doplňky → Video doplňky → KIVORA → Verze / Aktualizovat → zvolit KIVORA repozitář. Doplňky původně instalované ručně ze ZIPu mohou mít aktualizace připnuté k původnímu zdroji. Samotný ZIP lze použít nouzově, ale automatické aktualizace pak nemusí fungovat.</p><p>Následně v Kodi: Nastavení → Doplňky → Instalovat ze ZIP → Instalovat z repozitáře → KIVORA repozitář.</p><small>Komunitní doplněk KIVORA · Licence AGPL-3.0 · Žádná videa nejsou součástí doplňku.</small></html>''',encoding='utf-8')
    ET.parse(out/'addons.xml')
    ET.parse(out/REPO_ID/'addon.xml')
    with zipfile.ZipFile(repo_file) as z:
        assert z.testzip() is None
        assert f'{REPO_ID}/addon.xml' in z.namelist()
    with zipfile.ZipFile(plugin_file) as z:
        assert z.testzip() is None
        assert f'{PLUGIN_ID}/addon.xml' in z.namelist()
    print(f'Published directory: {out}')
    print(f'Expected GitHub Pages URL after deployment: {base}')
    print(f'Repository ZIP: {out/repo_file.name}')
    print(f'Addon ZIP: {plugin_file}')

if __name__=='__main__':main()
