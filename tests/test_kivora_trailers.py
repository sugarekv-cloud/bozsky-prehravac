# -*- coding: utf-8 -*-
"""Pure unit tests; no Kodi installation required."""
import os
import sys
import unittest
from urllib.parse import urlsplit,parse_qs
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','plugin.video.fckyo')))
from cinema_trailers import trailer_search_url

class TrailerTests(unittest.TestCase):
    def test_encoded_czech_title_and_year(self):
        url=trailer_search_url({'title':'Zelená míle','year':1999})
        self.assertEqual(urlsplit(url).scheme,'plugin')
        self.assertEqual(parse_qs(urlsplit(url).query)['q'][0],
                         'Zelená míle 1999 official trailer')
    def test_original_preferred_and_invalid_year_ignored(self):
        url=trailer_search_url({'title':'Překlad','original':'Original',
                                'year':'../../evil'})
        self.assertEqual(parse_qs(urlsplit(url).query)['q'][0],
                         'Original official trailer')
    def test_empty(self):
        self.assertEqual(trailer_search_url({}),'')
        self.assertEqual(trailer_search_url(None),'')

if __name__=='__main__':
    unittest.main()
