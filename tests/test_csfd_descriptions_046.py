# -*- coding: utf-8 -*-
"""KIVORA 0.46: descriptions from ČSFD-linked CZDB, not Cinemeta plots."""
import sys
import threading
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin.video.fckyo'))
from csfd_metadata import Catalogue,parse_entry
from cinema_catalog_v2 import card
from cinema_csfd_plot import csfd_plot
from cinema_service_v2 import CinemaService


def group(kind='movie',metadata=None):
    return {'title':'Zelená míle' if kind=='movie' else 'Bluey',
            'year':'1999' if kind=='movie' else '',
            'kind':kind, 'files':[{'ident':'one','name':'Example.1080p.mkv'}],
            'best':{'ident':'one','name':'Example.1080p.mkv','size':'3000000000'},
            'metadata':metadata}


class CsfdDescription046Tests(unittest.TestCase):
    def test_cinemeta_english_plot_never_masquerades_as_csfd(self):
        imdb={'title':'The Green Mile','year':'1999','rating':88,
              'rating_source':'IMDb','plot':'An English synopsis from Cinemeta'}
        item=card(group(metadata=imdb))
        self.assertEqual(item['plot'],'')
        self.assertEqual(item['plot_source'],'')
        self.assertEqual(item['rating_source'],'IMDb')

    def test_czdb_csfd_uid_provides_the_czech_film_plot(self):
        entry=parse_entry({'title':'Zelená míle','year':1999,'uid':'2294',
              'description':'Vězeňský dozorce se setká s neobyčejným odsouzencem.',
              'rating':'92 %'})
        self.assertEqual(entry['plot_source'],'ČSFD/CZDB')
        self.assertIn('vězeňský',entry['plot'].lower())
        item=card(group(metadata=entry))
        self.assertEqual(item['plot'],entry['plot'])
        self.assertEqual(item['plot_source'],'ČSFD/CZDB')

    def test_series_uses_same_csfd_plot_priority(self):
        entry={'uid':'999','year':'2018','title':'Bluey',
               'plot':'Příběhy malé fenky a její rodiny.',
               'rating_source':'ČSFD'}
        self.assertEqual(card(group('show',entry))['plot'],
                         'Příběhy malé fenky a její rodiny.')
        self.assertEqual(csfd_plot({'plot':'English overview',
                                    'rating_source':'IMDb'}),'')
        self.assertEqual(csfd_plot({'plot':'English overview',
                                    'rating_source':''}),'')
        self.assertEqual(csfd_plot({'plot':'Czech text',
                                    'rating_source':'ČSFD'}),'Czech text')

    def test_parser_sanitizes_html_and_multiline_synopsis(self):
        entry=parse_entry({'title':'Film','uid':'101','plot':
                           '<p>První věta.</p>  Další\n věta.'})
        self.assertEqual(entry['plot'],'První věta. Další věta.')

    def test_local_cache_is_consulted_before_fallback_for_movie_and_show(self):
        class Client:
            def __init__(self): self.access=[]
            def peek(self,title,year=''):
                self.access.append((title,year))
                return {'uid':'3','plot':'Český děj z ČSFD.'}
        svc=CinemaService.__new__(CinemaService)
        svc.metadata=Client()
        svc.home_cache={'_all_movies':[],'_all_shows':[]}
        self.assertEqual(svc._cached_description('Zelená míle','1999','movie'),
                         'Český děj z ČSFD.')
        self.assertEqual(svc._cached_description('Bluey','2018','show'),
                         'Český děj z ČSFD.')
        self.assertEqual(svc.metadata.access,[('Zelená míle','1999'),('Bluey','')])

    def test_background_worker_fetches_only_verified_file_backed_cards(self):
        finished=threading.Event()
        class Client:
            def __init__(self):self.requests=[]
            def peek(self,title,year=''): return None
            def lookup(self,title,year=''):
                self.requests.append((title,year))
                return {'plot':'Český popis','uid':'100'}
            def save(self): finished.set()
        svc=CinemaService.__new__(CinemaService)
        svc.metadata=Client()
        svc.home_cache={'_all_movies':[],'_all_shows':[]}
        cards=[
            {'kind':'movie','raw':'Zelená míle','year':'1999',
             'ident':'1','files':[{'ident':'1','name':'Green.Mile.mkv'}]},
            {'kind':'show','raw':'Bluey','year':'2018',
             'ident':'2','files':[{'ident':'2','name':'Bluey.S01E01.mkv'}]},
            {'kind':'movie','raw':'Unknown','ident':'',
             'files':[]},
        ]
        self.assertTrue(svc.start_csfd_description_refresh(cards))
        self.assertTrue(finished.wait(5),'CZDB worker did not finish')
        self.assertEqual(set(svc.metadata.requests),
                         {('Zelená míle','1999'),('Bluey','')})
        self.assertFalse(svc.start_csfd_description_refresh(cards))

    def test_ui_uses_cached_csfd_plot_for_banner_and_detail(self):
        source=(ROOT/'plugin.video.fckyo/cinema_screen_v2.py').read_text(
            encoding='utf-8')
        self.assertIn("plot=self._csfd_description(c)",source)
        self.assertIn("self._csfd_description(selected))",source)
        self.assertNotIn('Film nebo seriál je dostupný · zvol si jazyk',source)
        self.assertIn('start_csfd_description_refresh',source)


if __name__=='__main__':
    unittest.main()
