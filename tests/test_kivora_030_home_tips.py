# -*- coding: utf-8 -*-
"""KIVORA 0.30: functional Home and populated Tips on real verified cached films."""
import os
import sys
import types
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
if 'xbmcgui' not in sys.modules:
    gui=types.ModuleType('xbmcgui')
    gui.WindowXMLDialog=type('WindowXMLDialog',(),{})
    sys.modules['xbmcgui']=gui
if 'xbmc' not in sys.modules:
    sys.modules['xbmc']=types.ModuleType('xbmc')

from cinema_screen_v2 import CinemaScreen
from cinema_service_v2 import CinemaService


def movie(name,ident,kind='movie'):
    return dict(title=name,raw=name,ident=ident,kind=kind,
                year='1999',genre='Drama',rating=92,rating_source='ČSFD',
                poster='https://example.test/'+ident+'.jpg',
                files=[{'ident':ident,'name':name+'.1999.1080p.mkv'}])


class DummyService:
    token='valid'
    last_diagnostics='loaded'
    def __init__(self,catalog=None):
        self.catalog=catalog or {'_all_movies':[], '_all_shows':[]}
        self.home_calls=0
        self.tips_calls=0
    def home_fast(self):return self.catalog
    def tips_snapshot(self,home):return home
    def start_home_refresh(self):self.home_calls+=1;return False
    def start_tips_refresh(self):self.tips_calls+=1;return False
    def take_home_refresh(self):return None


def screen(service):
    win=CinemaScreen.__new__(CinemaScreen)
    win.service=service
    win.watch_store=None
    win.mode='movies'
    win._switching_section=False
    win._nav_focus_target=None
    win.stack=[('movies',None,401,0)]
    win.featured_card=movie('Stale old movie','stale')
    win.setProperty=lambda *a,**kw:None
    rendered=[]
    win._fill=lambda *args,**kw:rendered.append((args,kw))
    return win,rendered


class HomeAndTipsAcceptanceTests(unittest.TestCase):
    def test_home_button_replaces_movie_shelves_with_home_and_real_tips(self):
        film=movie('Zelená míle','gm')
        svc=DummyService({'_all_movies':[film], '_all_shows':[]})
        win,pages=screen(svc)
        win.onClick(106)
        self.assertEqual(win.mode,'home')
        self.assertEqual(win.stack,[])
        self.assertEqual(len(pages),1)
        args,kw=pages[0]
        self.assertEqual(args[0],'TIPY NA SLEDOVÁNÍ')
        self.assertEqual(args[1][0]['ident'],'gm')
        self.assertEqual(args[1][0]['poster'],film['poster'])
        self.assertFalse(any(c.get('kind')=='tips_retry' for c in args[1]))
        self.assertEqual(svc.home_calls,1)
        self.assertEqual(svc.tips_calls,1)

    def test_home_merges_old_style_cached_movies_even_without_all_movies(self):
        m=movie('Forrest Gump','fg')
        svc=DummyService({'movies':[m], 'shows':[], '_all_movies':[],
                          '_all_shows':[]})
        win,rendered=screen(svc)
        win._screen('home')
        self.assertEqual(rendered[0][0][1][0]['ident'],'fg')

    def test_completed_and_favorite_movies_still_appear_as_real_tips(self):
        m=movie('Vykoupení z věznice Shawshank','shaw')
        svc=DummyService({'_all_movies':[m], '_all_shows':[]})
        win,rendered=screen(svc)
        class History:
            def favorite_cards(self):return [m]
            def continue_cards(self,kind=None):return []
            def _data(self):return {'watch':{}}
        win.watch_store=History()
        win._screen('recommendations')
        self.assertEqual(rendered[0][0][0],'DOPORUČUJEME PRO TEBE')
        self.assertEqual(rendered[0][0][1][0]['ident'],'shaw')
        self.assertNotEqual(rendered[0][0][1][0]['kind'],'tips_retry')

    def test_recommendations_work_without_any_cached_metadata_ratings(self):
        m=movie('Unrated real film','unrated')
        m.pop('rating')
        m.pop('rating_source')
        svc=DummyService({'_all_movies':[m], '_all_shows':[]})
        win,rendered=screen(svc)
        win._screen('recommendations')
        self.assertEqual(rendered[0][0][1][0]['ident'],'unrated')

    def test_empty_home_still_has_functional_search_and_movie_cards(self):
        win,rendered=screen(DummyService())
        win._screen('home')
        self.assertEqual(rendered[0][0][0],'TIPY NA SLEDOVÁNÍ')
        self.assertEqual([c['kind'] for c in rendered[0][0][1]],
                         ['movies','search','tips_retry'])

    def test_crashing_recommendation_history_cannot_kill_home(self):
        svc=DummyService({'_all_movies':[movie('One verified title','one')],
                          '_all_shows':[]})
        win,rendered=screen(svc)
        class BrokenHistory:
            def continue_cards(self,kind=None):
                raise RuntimeError('legacy history corrupted')
            def favorite_cards(self):
                raise RuntimeError('legacy history corrupted')
        win.watch_store=BrokenHistory()
        win._screen('home')
        self.assertEqual(rendered[0][0][1][0]['ident'],'one')


class HomeWorkerLifecycleTests(unittest.TestCase):
    def test_completed_worker_is_unlocked_and_cache_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=CinemaService('token',lambda *a,**kw:([],0),None,profile=folder)
            valid={'_all_movies':[movie('Film','f')], '_all_shows':[]}
            svc._background_started=True
            svc._background_done.set()
            svc._background_result=valid
            self.assertFalse(svc.start_home_refresh())
            self.assertFalse(svc._background_started)
            self.assertEqual(svc.home_fast()['_all_movies'][0]['ident'],'f')

    def test_transient_empty_result_does_not_discard_valid_index(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=CinemaService('token',lambda *a,**kw:([],0),None,profile=folder)
            svc.home_cache={'_all_movies':[movie('Good cached movie','g')],
                            '_all_shows':[]}
            svc._background_started=True
            svc._background_result={'_all_movies':[],'_all_shows':[]}
            svc._background_done.set()
            self.assertIsNone(svc.take_home_refresh())
            self.assertEqual(svc.home_cache['_all_movies'][0]['ident'],'g')


class NewTVCardVisualTests(unittest.TestCase):
    def test_each_rail_uses_large_full_height_posters_and_titles(self):
        skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
                                   '1080i','fckyo-cinema-v2.xml')).getroot()
        for rid in range(401,414):
            row=skin.find(".//control[@id='%d']"%rid)
            for name in ('itemlayout','focusedlayout'):
                layout=row.find(name)
                portraits=[c for c in layout.findall("control[@type='image']")
                           if c.findtext('texture')=='$INFO[ListItem.Art(poster)]']
                self.assertEqual(len(portraits),1)
                self.assertEqual(portraits[0].findtext('aspectratio'),'keep')
                self.assertEqual(portraits[0].findtext('width'),'222' if rid in (403,404,408,411,412,413) else '140')
                titles=[c for c in layout.findall("control[@type='label']")
                        if c.findtext('label')=='$INFO[ListItem.Label]']
                self.assertEqual(len(titles),1)
                self.assertGreaterEqual(int(titles[0].findtext('width')),150)

    def test_hero_fallback_uses_big_uncropped_poster(self):
        skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
                                   '1080i','fckyo-cinema-v2.xml')).getroot()
        hero=[c for c in skin.findall(".//control[@type='image']")
              if c.findtext('texture')=='$INFO[Window.Property(hero_poster)]']
        self.assertEqual(len(hero),1)
        self.assertEqual(hero[0].findtext('width'),'830')
        self.assertEqual(hero[0].findtext('aspectratio'),'scale')


if __name__=='__main__':
    unittest.main()
