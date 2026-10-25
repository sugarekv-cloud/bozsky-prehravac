# -*- coding: utf-8 -*-
"""Lazy popularity shelf: verified titles, Webshare paging and UI controls."""
import os
import sys
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_service_v2 import CinemaService


class Availability:
    def check_groups(self,groups,max_workers=6):
        return groups


class PopularityTests(unittest.TestCase):
    def make_service(self,fetch):
        svc=CinemaService.__new__(CinemaService)
        svc.token='test'
        svc.fetch=fetch
        svc.availability=Availability()
        svc.metadata=None
        svc._most_watched_cards=[]
        svc._most_watched_idents=set()
        svc._most_watched_source=0
        svc._most_watched_offset=0
        svc._most_watched_done=False
        svc._decorate=lambda g,metadata=None: {
            'title':g['title'],'raw':g['title'],'kind':'movie',
            'year':g['year'],'file_year':g['year'],
            'ident':g['best']['ident'],'files':g['files']}
        return svc

    def test_page_fetch_is_incremental_and_cached(self):
        calls=[]
        def fetch(token,offset,term,sort='recent'):
            calls.append((offset,term,sort))
            if term=='1080p' and offset==0:
                return ([{'ident':str(i),'name':'The.Green.Mile.1999.1080p.mkv'}
                         for i in range(100)],200)
            if term=='1080p' and offset==100:
                return ([{'ident':'next','name':'The.Matrix.1999.1080p.mkv'}],200)
            return [],0
        service=self.make_service(fetch)
        self.assertEqual(len(service.most_watched_movies(1)),1)
        self.assertEqual(calls,[(0,'1080p','rating')])
        self.assertEqual(len(service.most_watched_movies(2)),2)
        self.assertEqual(calls[-1],(100,'1080p','rating'))
        service.most_watched_movies(2)
        self.assertEqual(len(calls),2)

    def test_not_verified_not_shown(self):
        def fetch(token,offset,term,sort='recent'):
            return ([{'ident':'a','name':'Movie.2020.1080p.mkv'}],1)
        service=self.make_service(fetch)
        service.availability.check_groups=lambda groups,max_workers=6: []
        self.assertEqual(service.most_watched_movies(2),[])

    def test_more_tile_and_skin(self):
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as f:
            code=f.read()
        self.assertIn("heading='POPULÁRNÍ NA WEBSHARE · FILMY'",code)
        self.assertIn("kind=='load_more'",code)
        self.assertIn("self.popular_limit+=24",code)
        root=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
                                   '1080i','fckyo-cinema-v2.xml')).getroot()
        for cid in ('401','402'):
            rail=root.find(".//control[@id='%s']"%cid)
            self.assertIn("ListItem.Property(is_more)",
                          ET.tostring(rail,encoding='unicode'))


if __name__=='__main__':
    unittest.main()
