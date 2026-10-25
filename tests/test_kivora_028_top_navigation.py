# -*- coding: utf-8 -*-
"""Regression tests for native Kodi top-tab focus and responsive switching."""
import os
import sys
import tempfile
import types
import unittest
from xml.etree import ElementTree as ET
from unittest.mock import patch

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_service_v2 import CinemaService
from cinema_screen_v2 import CinemaScreen,TOP_ACTIONS


class ImmediateTopNavigationTests(unittest.TestCase):
    def test_all_top_tab_ids_are_clickable_python_callbacks(self):
        expected={106:'home',101:'movies',102:'shows',103:'search',
                  104:'premieres',105:'genres',107:'settings'}
        self.assertEqual({k:TOP_ACTIONS[k] for k in expected},expected)
        for cid,target in expected.items():
            win=CinemaScreen.__new__(CinemaScreen)
            win.stack=[('home',None,401,0)]
            events=[]
            win.service=types.SimpleNamespace(take_home_refresh=lambda:None)
            win._refresh=lambda view,context=None,stack=True:events.append(
                ('screen',view,context,stack))
            win._screen=lambda view,context=None,stack=False:events.append(
                ('screen',view,context,stack))
            win._gear_menu=lambda:events.append(('settings',))
            win.onClick(cid)
            self.assertEqual(win._nav_focus_target,cid)
            if target=='settings':
                self.assertEqual(events,[('settings',)])
            elif target=='home':
                self.assertEqual(events,[('screen','home',None,False)])
                self.assertEqual(win.stack,[])
            else:
                self.assertEqual(events,[('screen',target,None,True)])

    def test_no_network_requests_on_switch_to_movies_series_or_premieres(self):
        calls=[]
        def fetch(*a,**kw):
            calls.append(a)
            raise AssertionError('must not call Webshare when clicking top tab')
        svc=CinemaService('token',fetch,None)
        snapshot={'_all_movies':[], '_all_shows':[], '_all_premieres':[]}
        svc.home_cache=snapshot
        svc._snapshot_age=1
        svc.home=lambda force=False: (_ for _ in ()).throw(
            AssertionError('blocking home() must never run on tab click'))
        for tab in ('movies','shows','premieres'):
            self.assertEqual(svc.browse(tab),[])
        self.assertEqual(calls,[])

    def test_movie_tab_renders_without_modal_block_or_web_requests(self):
        win=CinemaScreen.__new__(CinemaScreen)
        class Catalogue:
            token='token'
            last_diagnostics=''
            def home_fast(self):return {'_all_movies':[],'_all_shows':[]}
            def browse(self,view,*args):
                return []
        win.service=Catalogue()
        win.watch_store=None
        win.sort='date';win.quality='all';win.language='all';win.year='all'
        win.genre='all';win.catalog_limit=24;win.genre_limits={}
        win.setProperty=lambda *a:None
        win._loading=lambda *a: (_ for _ in ()).throw(
            AssertionError('tab is opening a blocking loading dialog'))
        win._filtered=lambda cards,keep_order=False:cards
        rows=[]
        win._fill=lambda *a,**k:rows.append(a)
        for tab in ('movies','shows'):
            win._screen(tab)
        self.assertEqual(len(rows),2)
        self.assertIn('FILMY',rows[0][0])
        self.assertIn('SERIÁLY',rows[1][0])

    def test_focus_remains_on_clicked_header_after_rail_fill(self):
        win=CinemaScreen.__new__(CinemaScreen)
        win._nav_focus_target=102
        win.rail_items=[[] for _ in range(13)]
        win.setProperty=lambda *a:None
        win._update_hero=lambda:None
        calls=[]
        class ListControl:
            def reset(self):pass
            def addItems(self,items):pass
        win.getControl=lambda cid:ListControl()
        win.setFocusId=lambda cid:calls.append(cid)
        win._fill('FIRST',[],'SECOND',[])
        self.assertEqual(calls,[102])
        self.assertIsNone(win._nav_focus_target)

    def test_background_refresh_can_repaint_movies_and_restore_tab_focus(self):
        win=CinemaScreen.__new__(CinemaScreen)
        win.mode='movies';win.context=None
        win._updating_home=False
        win.rail_items=[[] for _ in range(13)]
        win.service=types.SimpleNamespace(take_home_refresh=lambda:{'_all_movies':[]})
        win.getFocusId=lambda:101
        calls=[]
        win._screen=lambda *a,**k:calls.append(('refresh',a))
        win.setFocusId=lambda cid:calls.append(('focus',cid))
        win._update_hero=lambda:None
        win._apply_background_home()
        self.assertEqual(calls,[('refresh',('movies',None)),('focus',101)])
        self.assertFalse(win._updating_home)


class KodiTopControlsTests(unittest.TestCase):
    def test_all_top_buttons_exist_are_visible_and_navigable(self):
        tree=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
                                   '1080i','fckyo-cinema-v2.xml'))
        root=tree.getroot()
        ids=(106,101,102,103,104,105,107)
        for i,cid in enumerate(ids):
            btn=root.find(".//control[@id='%d']"%cid)
            self.assertIsNotNone(btn)
            self.assertEqual(btn.get('type'),'button')
            self.assertGreater(int(btn.findtext('width')),70)
            self.assertGreater(int(btn.findtext('height')),50)
            self.assertIsNone(btn.find('visible'))
            self.assertEqual(btn.findtext('onright'),str(ids[(i+1)%len(ids)]))
            self.assertEqual(btn.findtext('onleft'),str(ids[(i-1)%len(ids)]))
            self.assertEqual(btn.findall('ondown')[-1].text,'401')
        for rid in range(401,414):
            rail=root.find(".//control[@id='%d']"%rid)
            self.assertIsNotNone(rail)
            self.assertTrue(any(up.text in ('106','108') for up in rail.findall('onup')))


if __name__=='__main__':
    unittest.main()
