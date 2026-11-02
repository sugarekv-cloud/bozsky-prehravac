# -*- coding: utf-8 -*-
"""KIVORA 0.43: Webshare typo suggestions and complete incremental search.

Mock data never claims that any real Webshare file is available.
"""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin.video.fckyo'))
from cinema_search_v3 import episode_query_plan,search_suggestions
from cinema_service_v2 import CinemaService


def f(ident,name):
    return {'ident':str(ident),'name':name,'size':'4000000000',
            'password':'0','available':'1','removed':'0'}


class Availability:
    def check_groups(self,groups,max_workers=6):
        return [g for g in groups if g.get('files')]


def service(fetch,suggest=None):
    svc=CinemaService('token',fetch,Availability(),suggest_fetch=suggest)
    svc.artwork.lookup=lambda *a,**k:None
    return svc


class SmartSearch043Tests(unittest.TestCase):
    def test_episode_qualifiers_come_before_unfiltered_series(self):
        plan=episode_query_plan('Stranger Things',1,2,limit=18)
        self.assertTrue(plan)
        self.assertIn('S01E02',plan[0])
        self.assertIn('Stranger Things',plan[0])
        self.assertIn('Stranger Things',plan)
        self.assertTrue(any('1x02' in entry for entry in plan))

    def test_no_false_episode_result_even_from_targeted_api_query(self):
        calls=[]
        def fetch(t,offset,query,sort='recent'):
            calls.append(query)
            if 'Stranger Things' not in query:
                return [],0
            return [f('bad','Stranger.Things.S01E03.2160p.CZ.mkv'),
                    f('good','Stranger.Things.S01E02.1080p.CZ.mkv')],2
        svc=service(fetch)
        result=svc.search('Stranger Things S01E02',kind='show')
        self.assertEqual([x['ident'] for x in result[0]['files']],['good'])
        self.assertIn('S01E02',calls[0])

    def test_misspelling_suggests_real_query_without_faking_movie(self):
        proposed=search_suggestions('Avengrs')
        self.assertIn('Avengers',proposed)
        proposed2=search_suggestions('Strnger Things',
                          remote=['Stranger.Things.S01E01.1080p.mkv'])
        self.assertIn('Stranger Things',proposed2)
        self.assertEqual(search_suggestions('a'),[])

    def test_suggestion_api_is_lazy_cached_and_never_affects_availability(self):
        calls=[]
        def suggest(token,title,limit):
            calls.append((title,limit))
            return ['Avengers.2012.1080p.mkv']
        svc=service(lambda *a,**kw:([],0),suggest=suggest)
        self.assertEqual(svc.search('Avengrs'),[])
        self.assertTrue(svc.suggestions('Avengrs'))
        self.assertEqual(svc.suggestions('Avengrs'),svc.suggestions('Avengrs'))
        self.assertEqual(calls,[('Avengrs',8)])
        self.assertEqual(svc.search_cache.get(('avengrs','all')),[])

    def test_all_deep_candidates_get_verified_over_followup_batches(self):
        calls=[]
        def fetch(t,offset,query,sort='recent'):
            if query!='Matrix':
                return [],0
            calls.append(offset)
            if offset==0:
                return [f(i,'Matrix.Movie.%03d.2022.1080p.CZ.mkv'%i)
                        for i in range(100)],151
            if offset==100:
                return [f(i,'Matrix.Movie.%03d.2022.1080p.CZ.mkv'%i)
                        for i in range(100,151)],151
            return [],151
        svc=service(fetch)
        cards=svc.search('Matrix',kind='movie')
        for _ in range(8):
            if not svc.search_has_more('Matrix','movie'):
                break
            cards=svc.search('Matrix',kind='movie',more=True)
        self.assertFalse(svc.search_has_more('Matrix','movie'))
        # Every distinct title is preserved, not just first 28 or 65.
        seen={x['ident'] for x in cards}
        self.assertEqual(len(seen),151)
        self.assertIn('150',seen)
        self.assertIn(100,calls)
        self.assertEqual(calls,sorted(set(calls)))
        progress=svc.search_progress('Matrix','movie')
        self.assertGreaterEqual(progress['pages'],2)
        self.assertEqual(progress['pending'],0)

    def test_czech_quality_is_priority_within_same_title(self):
        svc=service(lambda t,o,q,s:(
            [f('en4k','Matrix.1999.2160p.EN.mkv'),
             f('cz1080','Matrix.1999.1080p.CZ.mkv'),
             f('dub4k','Matrix.1999.2160p.CZDAB.mkv')],3))
        result=svc.search('Matrix',kind='movie')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['files'][0]['ident'],'dub4k')

    def test_session_count_is_bounded(self):
        svc=service(lambda *a,**kw:([],0))
        for i in range(11):
            svc.search('Mystery Film Title %s'%i)
        self.assertLessEqual(len(svc.search_scan),8)


if __name__=='__main__':
    unittest.main()
