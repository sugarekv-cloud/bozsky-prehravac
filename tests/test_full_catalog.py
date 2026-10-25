# -*- coding: utf-8 -*-
"""Incremental verified movie/series catalogues, no duplicate posters."""
import os
import sys
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_service_v2 import CinemaService


def f(ident,name):
    return {'ident':ident,'name':name,'size':'5000000000',
            'password':'0','available':'1'}


class Available:
    def check_groups(self,groups,max_workers=6):
        return groups


class FullCatalogueTests(unittest.TestCase):
    def service(self,fetch,home=None):
        svc=CinemaService('token',fetch,Available())
        svc.home_cache=home or {'_all_movies':[],'_all_shows':[]}
        svc._decorate=lambda g,metadata=None: {
            'ident':g['best']['ident'],'title':g['title'],
            'raw':g['title'],'year':g['year'],
            'kind':g['kind'],'files':g['files'],
            'poster':'','quality':''}
        return svc

    def test_deferred_fetch_and_cursor_only_moves_when_requested(self):
        calls=[]
        def fetch(token,offset,term,sort='recent'):
            calls.append((term,offset,sort))
            if term=='1080p' and offset==0:
                return [f(str(i),'The.Green.Mile.1999.1080p.mkv')
                        for i in range(100)],200
            if term=='1080p' and offset==100:
                return [f('matrix','The.Matrix.1999.1080p.mkv')],200
            return [],0
        svc=self.service(fetch)
        cards,more=svc.full_catalog('movie',1)
        self.assertEqual(len(cards),1)
        self.assertTrue(more)
        self.assertEqual(calls,[('1080p',0,'rating')])
        cards,more=svc.full_catalog('movie',2)
        self.assertEqual(len(cards),2)
        self.assertEqual(calls[-1],('1080p',100,'rating'))
        svc.full_catalog('movie',2)
        self.assertEqual(len(calls),2)
        self.assertEqual({c['raw'] for c in cards},
                         {'The Green Mile','The Matrix'})

    def test_seeded_verified_cards_need_no_initial_network_request(self):
        calls=[]
        home={'_all_movies':[{'ident':'known','title':'Known Film',
             'raw':'Known Film','year':'2024','kind':'movie',
             'files':[f('known','Known.Film.2024.1080p.mkv')]}],
             '_all_shows':[]}
        svc=self.service(lambda *a,**k:calls.append(a) or ([],0),home)
        cards,has_more=svc.full_catalog('movie',1)
        self.assertEqual(cards[0]['ident'],'known')
        self.assertTrue(has_more)
        self.assertEqual(calls,[])

    def test_series_paging_does_not_mix_into_movies(self):
        def fetch(token,offset,term,sort='recent'):
            if term=='S01E':
                return [f('ep','Better.Call.Saul.S01E01.1080p.mkv'),
                        f('film','Interstellar.2014.1080p.mkv')],2
            return [],0
        svc=self.service(fetch)
        shows,_=svc.full_catalog('show',1)
        self.assertEqual(len(shows),1)
        self.assertEqual(shows[0]['kind'],'show')
        self.assertEqual(shows[0]['ident'],'ep')
        self.assertEqual(svc._browse_streams['movie'] if 'movie' in
                         svc._browse_streams else None,None)

    def test_remake_years_are_distinct_titles(self):
        def fetch(token,offset,term,sort='recent'):
            if term=='1080p':
                return [f('old','Dune.1984.1080p.mkv'),
                        f('new','Dune.2021.1080p.mkv')],2
            return [],0
        svc=self.service(fetch)
        cards,_=svc.full_catalog('movie',2)
        self.assertEqual(len(cards),2)
        self.assertEqual({c['year'] for c in cards},{'1984','2021'})

    def test_unavailable_groups_never_become_catalogue_cards(self):
        svc=self.service(lambda *args,**kwargs:
                         ([f('unavailable','Ghost.Movie.2026.1080p.mkv')],1))
        svc.availability.check_groups=lambda groups,max_workers=6: []
        cards,_=svc.full_catalog('movie',5)
        self.assertEqual(cards,[])

    def test_transient_failure_retries_same_page(self):
        attempts=[]
        def fetch(token,offset,term,sort='recent'):
            attempts.append((term,offset))
            if len(attempts)==1:
                return None,0
            return [f('movie','The.Matrix.1999.1080p.mkv')],1
        svc=self.service(fetch)
        cards,more=svc.full_catalog('movie',1)
        self.assertEqual(cards,[])
        self.assertTrue(more)
        cards,_=svc.full_catalog('movie',1)
        self.assertEqual(len(cards),1)
        self.assertEqual(attempts[:2],[('1080p',0),('1080p',0)])

    def test_invalid_kind_rejected(self):
        svc=self.service(lambda *a,**k:([],0))
        with self.assertRaises(ValueError):
            svc.full_catalog('unknown',24)


class FullCatalogueUiTests(unittest.TestCase):
    def test_movie_and_series_sections_link_to_full_catalogue(self):
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),
                  encoding='utf8') as handle:
            text=handle.read()
        self.assertIn("'catalog_open'",text)
        self.assertIn("'catalog_more'",text)
        self.assertIn("self.catalog_limit+=24",text)
        self.assertIn("self._refresh('catalog_all'",text)
        self.assertIn("+  OBJEVIT DALŠÍ SERIÁLY",text)
        self.assertIn("+  OBJEVIT DALŠÍ FILMY",text)
        self.assertIn('identity(item)==marker',text)

    def test_plus_uses_same_poster_card_in_skin(self):
        path=os.path.join(PLUGIN,'resources','skins','Default','1080i',
                          'fckyo-cinema-v2.xml')
        root=ET.parse(path).getroot()
        first=root.find(".//control[@id='401']")
        self.assertIn('ListItem.Property(is_more)',
                      ET.tostring(first,encoding='unicode'))


if __name__=='__main__':
    unittest.main()
