# -*- coding: utf-8 -*-
"""Smoke and regression tests for Kodi's independent catalogue helpers."""
import os
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','plugin.video.fckyo')))

from available_catalog import matching_movies,localize_groups,names_for
from search_catalog import grouped
from ws_availability import Availability


def movie(ident,title):
    return {'ident':ident,'name':title,'password':'0','size':'4000000000'}

class WebshareCatalogTests(unittest.TestCase):
    def test_missing_webshare_file_never_creates_title(self):
        self.assertEqual(localize_groups([{'title':'Film','files':[],'best':None}]),[])

    def test_exact_title_and_year(self):
        f=[movie('a','Pokus.2025.1080p.CZ.mkv'),
           movie('b','Pokus.2021.1080p.mkv'),
           movie('c','Jiny.Film.2025.2160p.mkv')]
        self.assertEqual([x['ident'] for x in matching_movies(f,['Pokus'],'2025')],['a'])

    def test_locked_removed_and_trailers_excluded(self):
        f=[movie('a','Zkouska.2025.1080p.mkv'),
           movie('b','Zkouska.2025.trailer.mkv'),
           dict(movie('c','Zkouska.2025.4K.mkv'),password='1'),
           dict(movie('d','Zkouska.2025.4K.mkv'),removed='1')]
        self.assertEqual([x['ident'] for x in matching_movies(f,['Zkouska'],'2025')],['a'])

    def test_localized_names_only_for_file_backed_items(self):
        g={'title':'Original Title','year':'2025','kind':'movie',
           'files':[movie('x','Original.Title.2025.2160p.mkv')],
           'best':movie('x','Original.Title.2025.2160p.mkv'),
           'metadata':{'title':'Český název','uid':'1234'}, 'strength':1.0}
        groups=localize_groups([g])
        self.assertEqual(groups[0]['metadata']['title'],'Český název')
        self.assertEqual(len(groups[0]['files']),1)

    def test_search_rejects_unrelated_filenames(self):
        f=[movie('a','Interstellar.2014.1080p.mkv'),
           movie('b','Batman.2022.2160p.mkv')]
        self.assertEqual(len(grouped(f,'Interstellar')['movies']),1)

    def test_czech_alias_for_english_title(self):
        f=[movie('a','Original.Title.2025.1080p.mkv')]
        self.assertEqual(len(grouped(f,'Český název',('Original Title',))['movies']),1)

class AvailabilityTests(unittest.TestCase):
    class Response:
        def __init__(self,exists='1',downloadable='1'):
            self.content=('<response><status>OK</status><exists>%s</exists>'
                          '<downloadable>%s</downloadable></response>'%(exists,downloadable)).encode()
        def raise_for_status(self):
            pass

    def test_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            a=Availability(d,transport=lambda *args,**kwargs:self.Response('0','0'))
            self.assertEqual(a.check_files([movie('a','X.2025.mkv')]),[])

    def test_only_downloadable(self):
        with tempfile.TemporaryDirectory() as d:
            def request(url,data,timeout):
                return self.Response('1','0') if data['ident']=='bad' else self.Response('1','1')
            a=Availability(d,transport=request)
            f=[movie('bad','Film.2025.4K.mkv'),movie('good','Film.2025.1080p.mkv')]
            verified=a.check_files(f)
            self.assertEqual([x['ident'] for x in verified],['good'])

if __name__=='__main__':
    unittest.main()
