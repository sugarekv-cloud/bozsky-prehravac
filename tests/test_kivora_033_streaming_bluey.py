# -*- coding: utf-8 -*-
"""KIVORA 0.33: two Netflix-style shelf formats and dedicated playable Bluey tab."""
import json
import os
import sys
import tempfile
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)

if 'xbmcgui' not in sys.modules:
    gui=types.ModuleType('xbmcgui')
    gui.WindowXMLDialog=type('WindowXMLDialog',(),{})
    sys.modules['xbmcgui']=gui
elif not hasattr(sys.modules['xbmcgui'],'WindowXMLDialog'):
    sys.modules['xbmcgui'].WindowXMLDialog=type('WindowXMLDialog',(),{})
if 'xbmc' not in sys.modules:
    sys.modules['xbmc']=types.ModuleType('xbmc')

from cinema_screen_v2 import CinemaScreen,TOP_ACTIONS
from cinema_service_v2 import CinemaService


def show(name,ident,kind='show'):
    return dict(title=name,raw=name,kind=kind,ident=ident,year='2018',
                poster='https://example.test/'+ident+'.jpg',
                files=[dict(ident=ident,name='Bluey.S01E01.mkv')])


class BlueyCatalogueTests(unittest.TestCase):
    def test_bluey_matching_excludes_movies_and_similarly_named_series(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=CinemaService('token',lambda *a,**kw:([],0),None,profile=folder)
            pool=[show('Bluey','real'),show('Blueyland','other'),
                  show('Bluey','movie','movie'),show('Mr Bluey','other2')]
            found=svc.bluey_cards({'_all_shows':pool})
            self.assertEqual([x['ident'] for x in found],['real'])

    def test_async_bluey_search_persists_verified_series(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=CinemaService('token',lambda *a,**kw:([],0),None,profile=folder)
            called=[]
            def fetch(query,kind='all'):
                called.append((query,kind))
                return [show('Bluey','verified'),show('Unrelated Film','bad','movie')]
            svc.search=fetch
            self.assertTrue(svc.start_bluey_refresh())
            self.assertTrue(svc._bluey_done.wait(5))
            result=svc.take_bluey_refresh()
            self.assertEqual([c['ident'] for c in result],['verified'])
            self.assertEqual(called,[('Bluey','show')])
            reopened=CinemaService('token',lambda *a,**kw:([],0),None,
                                   profile=folder)
            self.assertEqual(reopened.bluey_cards()[0]['ident'],'verified')
            with open(svc._bluey_path,encoding='utf8') as stream:
                saved=json.load(stream)
            self.assertEqual(saved['cards'][0]['kind'],'show')

    def test_bluey_tab_paints_real_series_not_fake_episode_links(self):
        win=CinemaScreen.__new__(CinemaScreen)
        class Service:
            token='valid'
            def home_fast(self):return {'_all_movies':[],'_all_shows':[]}
            def bluey_cards(self,home=None):return [show('Bluey','available')]
            def start_bluey_refresh(self,force=False):return False
        win.service=Service()
        win.addon=types.SimpleNamespace(
            getAddonInfo=lambda key:'/tmp/kivora')
        win.setProperty=lambda *a:None
        win._home_catalogue=lambda:{'_all_movies':[],'_all_shows':[]}
        rendered=[]
        win._fill=lambda *args,**kw:rendered.append(args)
        win._screen('bluey')
        self.assertEqual(len(rendered),1)
        self.assertEqual(rendered[0][0],'BLUEY · SERIÁL')
        self.assertEqual(rendered[0][1][0]['ident'],'available')
        self.assertEqual(rendered[0][1][0]['kind'],'show')
        win._selected=lambda cid=None:rendered[0][1][0]
        called=[]
        win._refresh=lambda *a:called.append(a)
        win.onClick(401)
        self.assertEqual(called,[('seasons',rendered[0][1][0])])

    def test_empty_bluey_tab_offers_search_and_retry_not_fake_stream(self):
        win=CinemaScreen.__new__(CinemaScreen)
        class Service:
            token='valid'
            def home_fast(self):return {'_all_movies':[],'_all_shows':[]}
            def bluey_cards(self,home=None):return []
            def start_bluey_refresh(self,force=False):return True
        win.service=Service()
        win.addon=types.SimpleNamespace(getAddonInfo=lambda key:'/tmp/kivora')
        win.setProperty=lambda *a:None
        win._home_catalogue=lambda:{'_all_movies':[],'_all_shows':[]}
        rows=[]
        win._fill=lambda *args,**kw:rows.append(args)
        win._screen('bluey')
        self.assertEqual(rows[0][0],'BLUEY · DĚTSKÝ SERIÁL')
        self.assertEqual(rows[0][1][0]['kind'],'bluey_retry')
        self.assertEqual(rows[0][3][0]['kind'],'bluey_search')
        self.assertTrue(rows[0][1][0]['poster'].endswith('kids.png'))


class StreamingSkinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
            '1080i','fckyo-cinema-v2.xml')).getroot()

    def test_bluey_tab_is_clickable_via_kodi_header(self):
        self.assertEqual(TOP_ACTIONS[109],'bluey')
        button=self.root.find(".//control[@id='109']")
        self.assertEqual(button.get('type'),'button')
        self.assertEqual(button.findtext('label'),'BLUEY')
        self.assertEqual(button.findtext('onleft'),'105')
        self.assertEqual(button.findtext('onright'),'107')
        self.assertEqual(self.root.find(".//control[@id='105']").findtext('onright'),'109')
        self.assertEqual(self.root.find(".//control[@id='107']").findtext('onleft'),'109')

    def test_landscape_and_portrait_rows_both_preserve_progress_and_focus(self):
        portrait={403,404,408,411,412,413}
        for rid in range(401,414):
            rail=self.root.find(".//control[@id='%s']"%rid)
            layout=rail.find('itemlayout')
            focus=rail.find('focusedlayout')
            dims=(int(layout.get('width')),int(layout.get('height')))
            self.assertEqual(dims,(239,354) if rid in portrait else (359,259))
            self.assertEqual(dims,(int(focus.get('width')),int(focus.get('height'))))
            self.assertIsNotNone(layout.find("control[@type='progress']"))
            self.assertIsNotNone(focus.find("control[@type='progress']"))
            posters=[x for x in layout.findall("control[@type='image']")
                     if x.findtext('texture')=='$INFO[ListItem.Art(poster)]']
            self.assertGreaterEqual(len(posters),1)
            self.assertTrue(any(p.findtext('aspectratio')=='keep' for p in posters))
        banner=[x for x in self.root.findall(".//control[@type='image']")
                if x.findtext('texture')=='$INFO[Window.Property(hero_art)]']
        self.assertGreaterEqual(int(banner[0].findtext('width')),1300)

    def test_hero_has_distinct_play_and_detail_controls(self):
        play=self.root.find(".//control[@id='108']")
        detail=self.root.find(".//control[@id='110']")
        self.assertIn('PŘEHRÁT',play.findtext('label'))
        self.assertIn('DETAIL',detail.findtext('label'))
        self.assertEqual(detail.findtext('onleft'),'108')
        self.assertEqual(play.findtext('onright'),'110')

    def test_new_version_and_cached_textures(self):
        addon=ET.parse(os.path.join(PLUGIN,'addon.xml')).getroot()
        self.assertEqual(addon.get('version'),'0.35.0')
        with open(os.path.join(PLUGIN,'cinematic_home.py'),encoding='utf8') as f:
            src=f.read()
        self.assertIn('stream_v8_',src)


if __name__=='__main__':
    unittest.main()
