# -*- coding: utf-8 -*-
"""KIVORA 0.27: direct title searches cannot be starved by background Tips."""
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

PLUGIN=os.path.abspath(os.path.join(os.path.dirname(__file__),'..',
                                    'plugin.video.fckyo'))
sys.path.insert(0,PLUGIN)
from cinema_service_v2 import CinemaService,WebshareSearchUnavailable


def file(ident,name):
    return {'ident':ident,'name':name,'size':'1000000000',
            'password':'0','available':'1'}


class Availability:
    def check_groups(self,groups,max_workers=6):
        return [x for x in groups if x.get('files')]


class ForegroundSearchTests(unittest.TestCase):
    def tearDown(self):
        CinemaService._foreground_search.clear()

    def test_czech_title_finds_verified_original_in_bounded_calls(self):
        calls=[]
        def fetch(token,offset,term,sort='recent'):
            calls.append((term,offset,sort))
            if term=='The Green Mile':
                return [file('green','The.Green.Mile.1999.1080p.mkv')],1
            return [],0
        svc=CinemaService('token',fetch,Availability())
        svc.artwork.lookup=lambda *a,**k:None
        found=svc.search('Zelená míle')
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['ident'],'green')
        self.assertLessEqual(len(calls),11)
        self.assertFalse(CinemaService._foreground_search.is_set())

    def test_empty_search_has_small_bounded_query_budget(self):
        calls=[]
        svc=CinemaService('token',lambda t,o,q,sort='recent':
                          (calls.append((o,q)) or ([],0)),Availability())
        self.assertEqual(svc.search('Imaginary Film Nobody Has Heard Of'),[])
        self.assertLessEqual(len(calls),11)
        self.assertNotIn('imaginary film nobody has heard of',svc.search_cache)

    def test_network_outage_is_not_misreported_as_no_movies(self):
        calls=[]
        good={'ok':False}
        def fetch(token,offset,term,sort='recent'):
            calls.append(term)
            if good['ok'] and term=='The Green Mile':
                return [file('green','The.Green.Mile.1999.1080p.mkv')],1
            return ([],0) if good['ok'] else (None,0)
        svc=CinemaService('token',fetch,Availability())
        svc.artwork.lookup=lambda *a,**k:None
        with self.assertRaises(WebshareSearchUnavailable):
            svc.search('Zelená míle')
        self.assertFalse(CinemaService._foreground_search.is_set())
        self.assertEqual(svc.search_cache,{})
        good['ok']=True
        self.assertEqual(svc.search('Zelená míle')[0]['ident'],'green')

    def test_background_yields_when_user_is_searching(self):
        calls=[]
        svc=CinemaService('token',lambda *a,**k:
                          (calls.append(1) or ([],0)),Availability())
        CinemaService._foreground_search.set()
        finished=threading.Event()
        worker=threading.Thread(target=lambda:
            (svc._fetch_background('token',0,'unused'),finished.set()),
            daemon=True)
        worker.start()
        self.assertFalse(finished.wait(.18))
        self.assertEqual(calls,[])
        CinemaService._foreground_search.clear()
        self.assertTrue(finished.wait(2))
        self.assertEqual(calls,[1])

    def test_tips_cannot_start_parallel_first_run_discovery(self):
        with tempfile.TemporaryDirectory() as profile:
            svc=CinemaService('token',lambda *a,**k:([],0),
                              Availability(),profile=profile)
            self.assertFalse(svc.start_tips_refresh())
            self.assertFalse(svc._tips_loading)
            svc.home_cache={'_all_movies':[{
                'kind':'movie','title':'Demo','raw':'Demo','ident':'known',
                'files':[file('known','Demo.2024.mkv')]}],
                '_all_shows':[]}
            svc._background_started=True
            svc._background_done.clear()
            self.assertFalse(svc.start_tips_refresh())

    def test_tips_reuse_home_without_running_second_full_discovery(self):
        with tempfile.TemporaryDirectory() as profile:
            svc=CinemaService('token',lambda *a,**k:([],0),
                              Availability(),profile=profile)
            known={'kind':'movie','title':'Demo','raw':'Demo','ident':'known',
                   'files':[file('known','Demo.2024.mkv')]}
            svc.home_cache={'_all_movies':[known],'_all_shows':[]}
            def fail_home(self,force=False):
                raise AssertionError('duplicate expensive home discovery')
            def fake_catalog(self,kind,requested=24,sort='date',
                             quality='all',language='all'):
                self.assert_no_network=True
                return ([known] if kind=='movie' else []),False
            with patch.object(CinemaService,'home',fail_home), \
                 patch.object(CinemaService,'full_catalog',fake_catalog):
                self.assertTrue(svc.start_tips_refresh())
                self.assertTrue(svc._tips_done.wait(3))
            self.assertEqual(svc.take_tips_refresh()[0]['ident'],'known')


class MovieSearchErrorPageTests(unittest.TestCase):
    def test_error_page_offers_retry_with_preserved_query(self):
        if 'xbmcgui' not in sys.modules:
            module=types.ModuleType('xbmcgui')
            module.WindowXMLDialog=type('WindowXMLDialog',(),{})
            sys.modules['xbmcgui']=module
        from cinema_screen_v2 import CinemaScreen
        win=CinemaScreen.__new__(CinemaScreen)
        class FailedSearch:
            token='present'
            def search(self,term):
                raise WebshareSearchUnavailable('Webshare offline')
        win.service=FailedSearch()
        win.setProperty=lambda *a:None
        win._loading=lambda *a:types.SimpleNamespace(close=lambda:None)
        history=[]
        win._fill=lambda *args,**k:history.append(args)
        win._screen('search','Zelená míle')
        cards=history[0][1]
        self.assertEqual(cards[0]['kind'],'search_retry')
        self.assertEqual(cards[0]['search_text'],'Zelená míle')
        self.assertIn('Webshare offline',history[0][-1])


if __name__=='__main__':
    unittest.main()
