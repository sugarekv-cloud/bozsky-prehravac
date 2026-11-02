# -*- coding: utf-8 -*-
"""KIVORA Webshare search: title intent, category cache and real result paging.

These tests use deterministic in-memory Webshare responses. No credentials,
external requests, or simulated unavailable movies are used.
"""
from pathlib import Path
import sys
import time
import unittest

PLUGIN=Path(__file__).resolve().parents[1]/'plugin.video.fckyo'
sys.path.insert(0,str(PLUGIN))
from cinema_search_v3 import search_intent,query_plan
from cinema_service_v2 import CinemaService


def media(ident,name):
    return {'ident':ident,'name':name,'size':'4500000000',
            'password':'0','available':'1','removed':'0'}


class Available:
    def check_groups(self,groups,max_workers=6):
        return [g for g in groups if g.get('files')]


class SearchQualityTests(unittest.TestCase):
    def setUp(self):
        self.fetches=[]

    def make_service(self,source):
        def fetch(token,offset,query,sort='recent'):
            self.fetches.append((query,offset,sort))
            return source(token,offset,query,sort)
        svc=CinemaService('test-only-session',fetch,Available())
        svc.artwork.lookup=lambda *a,**kw:None
        return svc

    def test_movie_year_and_episode_input_are_recognized(self):
        self.assertEqual(search_intent('Duna (2021)'),('Duna','2021',None,None))
        self.assertEqual(search_intent('The.Matrix.1999'),('The Matrix','1999',None,None))
        self.assertEqual(search_intent('Stranger Things S01E02'),
                         ('Stranger Things','',1,2))
        self.assertEqual(search_intent('Stranger.Things.1x03'),
                         ('Stranger.Things','',1,3))
        self.assertEqual(search_intent('Show S02 E009'),
                         ('Show','',2,9))

    def test_direct_episode_search_never_shows_wrong_episode(self):
        files=[media('e1','Stranger.Things.S01E01.1080p.CZ.mkv'),
               media('e2','Stranger.Things.S01E02.1080p.CZ.mkv'),
               media('e3','Stranger.Things.S01E03.2160p.CZ.mkv')]
        def source(token,offset,query,sort):
            return (files,len(files)) if 'stranger' in query.lower() else ([],0)
        svc=self.make_service(source)
        rows=svc.search('Stranger Things S01E02',kind='show')
        self.assertEqual(len(rows),1)
        self.assertEqual([f['ident'] for f in rows[0]['files']],['e2'])
        self.assertTrue(any(q=='Stranger Things' for q,_,_ in self.fetches))
        self.assertTrue(any('S01E02' in q for q,_,_ in self.fetches))

    def test_episode_dot_alt_notation(self):
        files=[media('1','Mystery.Show.2x01.1080p.mkv'),
               media('2','Mystery.Show.2x03.720p.CZ.mkv')]
        svc=self.make_service(lambda t,o,q,s:(files,2))
        result=svc.search('Mystery Show 2x03',kind='show')
        self.assertEqual([f['ident'] for f in result[0]['files']],['2'])

    def test_movie_search_does_not_hide_series_with_same_name(self):
        files=[media('movie','Matrix.1999.1080p.CZ.mkv'),
               media('episode','Matrix.S01E01.1080p.CZ.mkv')]
        svc=self.make_service(lambda t,o,q,s:(files,2))
        movies=svc.search('Matrix',kind='movie')
        shows=svc.search('Matrix',kind='show')
        self.assertEqual([f['ident'] for c in movies for f in c['files']],['movie'])
        self.assertEqual([f['ident'] for c in shows for f in c['files']],['episode'])
        self.assertEqual(len(svc.search_cache),2)
        previous=len(self.fetches)
        self.assertEqual(svc.search('Matrix',kind='show'),shows)
        self.assertEqual(len(self.fetches),previous)

    def test_cached_search_is_refreshed_after_five_minutes(self):
        state={'ident':'one'}
        def fetch(t,o,q,s):
            return [media(state['ident'],'Example.Title.2022.1080p.mkv')],1
        svc=self.make_service(fetch)
        first=svc.search('Example Title',kind='movie')
        self.assertEqual(first[0]['ident'],'one')
        cached=len(self.fetches)
        state['ident']='two'
        self.assertEqual(svc.search('Example Title',kind='movie')[0]['ident'],'one')
        self.assertEqual(len(self.fetches),cached)
        svc.search_cache_time[('example title','movie')]=time.time()-301
        again=svc.search('Example Title',kind='movie')
        self.assertEqual(again[0]['ident'],'two')
        self.assertGreater(len(self.fetches),cached)

    def test_czech_and_original_aliases_are_queried_early(self):
        plan=query_plan('Zelená míle',limit=12)
        self.assertEqual(plan[:2],['Zelená míle','The Green Mile'])
        self.assertIn('the.green.mile',plan)
        self.assertLess(plan.index('The Green Mile'),
                        plan.index('the.green.mile'))


if __name__=='__main__':
    unittest.main()
