# -*- coding: utf-8 -*-
"""FCKYO 0.20 startup speed, asynchronous home refresh and genre browsing."""
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from xml.etree import ElementTree as ET
from unittest.mock import patch

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_genres import GENRES,genre_matches,genre_cards
from cinema_service_v2 import CinemaService
from cinema_rankings import csfd_only


def sample(kind,title,ident,genre='Komedie',rating_source='ČSFD'):
    return {'kind':kind,'title':title,'raw':title,
            'ident':ident,'year':'2024','genre':genre,
            'rating':90,'rating_source':rating_source,
            'files':[{'ident':ident,'name':title+'.2024.1080p.mkv'}]}


class GenresTests(unittest.TestCase):
    def test_all_requested_genres_are_exposed(self):
        for label in ('Komedie','Horor','Sci-Fi','Dokumentární','Krimi',
                      'Dobrodružný','Romantický','Sportovní'):
            self.assertIn(label,GENRES)
        self.assertGreaterEqual(len(GENRES),20)

    def test_czech_and_english_metadata_aliases(self):
        film=sample('movie','Comedy Movie','a',genre='Comedy, Romance')
        self.assertTrue(genre_matches(film,'Komedie'))
        self.assertTrue(genre_matches(film,'Romantický'))
        self.assertFalse(genre_matches(film,'Horor'))
        sf=sample('movie','SF Film','s','Sci-Fi, Thriller')
        self.assertTrue(genre_matches(sf,'Sci-Fi'))
        horror=sample('show','Scary','h',['Drama','Horror'])
        self.assertTrue(genre_matches(horror,'Horor'))
        self.assertTrue(genre_matches(horror,'Drama'))

    def test_only_available_metadata_verified_cards_are_listed(self):
        films=[sample('movie','Funny','f','Comedy'),
               sample('show','Funny Show','s','Komedie'),
               {'kind':'movie','title':'Ghost','ident':'bad',
                'genre':'Komedie','files':[]}]
        self.assertEqual(len(genre_cards(films,'Komedie')),2)
        self.assertEqual(len(genre_cards(films,'Horor')),0)

    def test_csfd_series_ranking_ignores_imdb_scores(self):
        shows=[sample('show','Real ČSFD','s','Drama','ČSFD'),
               sample('show','IMDb only','i','Drama','IMDb')]
        self.assertEqual([c['title'] for c in csfd_only(shows,'show')],
                         ['Real ČSFD'])


class InstantHomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def make(self,fetch):
        return CinemaService('test',fetch,None,profile=self.tmp.name)

    def test_stale_verified_snapshot_opens_without_any_network_call(self):
        calls=[]
        service=self.make(lambda *args,**kwargs:calls.append(args))
        stale={'_dedupe_v1':True,'premieres':[],'movies':[sample(
               'movie','Old Film','a')], 'shows':[]}
        with io.open(service.cache_path,'w',encoding='utf8') as f:
            json.dump({'saved':time.time()-86400*30,'home':stale},f)
        loaded=service.home_fast()
        self.assertEqual(loaded['movies'][0]['title'],'Old Film')
        self.assertEqual(calls,[])
        self.assertGreater(service._snapshot_age,86400)

    def test_first_install_returns_empty_skeleton_instantly(self):
        calls=[]
        service=self.make(lambda *args,**kwargs:calls.append(args))
        home=service.home_fast()
        self.assertEqual(home['movies'],[])
        self.assertEqual(home['_all_shows'],[])
        self.assertEqual(calls,[])

    def test_fresh_popularity_cache_skips_background_thread(self):
        svc=self.make(lambda *a,**k:[])
        svc.home_cache={'_dedupe_v1':True,'_webshare_movies':[],
                        '_webshare_shows':[]}
        svc._snapshot_age=15
        self.assertFalse(svc.start_home_refresh())
        self.assertFalse(svc._background_started)

    def test_worker_publishes_snapshot_only_after_both_rankings(self):
        svc=self.make(lambda *a,**k:[])
        ready=threading.Event()
        def build(clone,force=False):
            self.assertTrue(force)
            ready.set()
            return {'_dedupe_v1':True,'premieres':[],'movies':[],
                    'shows':[sample('show','Series','s')],
                    '_all_movies':[],'_all_shows':[]}
        with patch.object(CinemaService,'home',build), \
             patch.object(CinemaService,'most_watched_movies',
                          lambda self,n:[]), \
             patch.object(CinemaService,'most_watched_shows',
                          lambda self,n:[sample('show','Popular','pop')]):
            self.assertTrue(svc.start_home_refresh())
            self.assertTrue(ready.wait(5))
            self.assertTrue(svc._background_done.wait(5))
        result=svc.take_home_refresh()
        self.assertNotIn('_webshare_shows',result)
        self.assertEqual(svc.home_cache['shows'][0]['title'],'Series')
        self.assertIsNone(svc.take_home_refresh())

    def test_series_popularity_filters_movies_and_uses_rating_order(self):
        called=[]
        class Available:
            def check_groups(self,groups,max_workers=6):return groups
        def fetch(token,offset,term,sort='recent'):
            called.append((term,offset,sort))
            if term=='S01E':
                return [{'ident':'ep1',
                         'name':'Breaking.Bad.S01E01.1080p.mkv',
                         'size':'1000000000'},
                        {'ident':'movie','name':'Interstellar.2014.1080p.mkv',
                         'size':'1000000000'}],2
            return [],0
        service=CinemaService('token',fetch,Available(),profile=self.tmp.name)
        cards=service.most_watched_shows(1)
        self.assertEqual(len(cards),1)
        self.assertEqual(cards[0]['kind'],'show')
        self.assertEqual(called[0],('S01E',0,'rating'))
        service.most_watched_shows(1)
        self.assertEqual(len(called),1)


class TvNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as f:
            cls.screen_code=f.read()
        cls.skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
                                       '1080i','fckyo-cinema-v2.xml')).getroot()

    def test_genre_tab_and_13_shelves_exist(self):
        self.assertIsNotNone(self.skin.find(".//control[@id='105']"))
        self.assertIn("105:'genres'",self.screen_code)
        self.assertIn("view=='genre_titles'",self.screen_code)
        self.assertIn("kind=='genre_more'",self.screen_code)
        for id in range(401,414):
            rail=self.skin.find(".//control[@id='%d']"%id)
            self.assertIsNotNone(rail)
            self.assertEqual(rail.findall('ondown')[-1].text,str(id))

    def test_top_navigation_skips_unpopulated_shelves(self):
        for id in (101,102,103,104,105,107,108):
            button=self.skin.find(".//control[@id='%d']"%id)
            downs=button.findall('ondown')
            self.assertGreater(len(downs),12)
            self.assertTrue(any(link.text=='413' for link in downs))
        gear=self.skin.find(".//control[@id='107']")
        self.assertEqual(gear.findtext('onleft'),'105')

    def test_home_screen_has_no_blocking_dialog_or_webshare_call(self):
        start=self.screen_code.index("        if view=='home':")
        end=self.screen_code.index("        elif view in ('movies'",start)
        method=self.screen_code[start:end]
        self.assertIn('home_fast()',method)
        self.assertIn('start_home_refresh()',method)
        self.assertNotIn('most_watched_movies(',method)
        self.assertNotIn('self._loading(',method)
        self.assertIn("NEJLÉPE HODNOCENÉ SERIÁLY · ČSFD",method)
        self.assertIn("TIPY PRO TEBE",method)


if __name__=='__main__':
    unittest.main()
