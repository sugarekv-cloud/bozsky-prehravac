# -*- coding: utf-8 -*-
"""Regression tests for the new Kodi cinema screen without a Kodi installation."""
import os
import sys
import tempfile
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUG=os.path.join(ROOT,'plugin.video.yawsp')
sys.path.insert(0,PLUG)

from cinematic_catalog import make_rows, webshare_image_url
from cinematic_discovery import discover, empty_message, queries_for_home

def f(ident,title,kind='movie'):
    suffix='S01E03' if kind=='show' else '2025'
    return {'ident':ident,'name':title+'.'+suffix+'.1080p.CZ.mkv',
            'size':'4000000000','password':'0'}

class Checker:
    def check_groups(self, groups, max_workers=4):
        return [g for g in groups if any(x['ident']!='gone' for x in g['files'])]

class Metadata:
    def lookup_many(self, groups, max_new=5):
        for g in groups:
            g['metadata']={'title':'Český název: '+g['title'],
                           'poster':'https://example.test/poster.jpg',
                           'plot':'Český popis','rating':79,'genres':['Drama']}
    def save(self):
        pass

class DataTests(unittest.TestCase):
    def test_never_uses_metadata_to_invent_movie(self):
        rows=make_rows([],[],Checker(),Metadata())
        self.assertEqual(rows['new_movies'],[])
        self.assertEqual(rows['discover'],[])

    def test_webshare_movies_are_posters_and_titles(self):
        rows=make_rows([f('a','Movie Title'),f('b','Other Movie')],
                       [],Checker(),Metadata())
        self.assertEqual(len(rows['new_movies']),2)
        self.assertTrue(rows['new_movies'][0]['title'].startswith('Český název'))
        self.assertTrue(rows['new_movies'][0]['poster'].startswith('https:'))
        self.assertEqual(rows['new_movies'][0]['kind'],'movie')

    def test_shows_get_different_click_target(self):
        rows=make_rows([f('a','Film'),f('b','My Show','show')],
                       [],Checker())
        self.assertEqual(len(rows['discover']),1)
        self.assertEqual(rows['discover'][0]['kind'],'show')
        self.assertEqual(rows['discover_title'],'SERIÁLY K OBJEVENÍ')

    def test_webshare_relative_preview_url(self):
        self.assertEqual(webshare_image_url('/thumb/movie.png'),
                         'https://webshare.cz/thumb/movie.png')
        self.assertEqual(webshare_image_url('//static.webshare.cz/movie.png'),
                         'https://static.webshare.cz/movie.png')
        self.assertEqual(webshare_image_url('plugin://untrusted/logo'),'')

    def test_webshare_artwork_only_for_filebacked_title(self):
        video=f('a','Cinema')
        video['img']='/thumb/film.jpg'
        rows=make_rows([video],[],Checker())
        self.assertEqual(rows['new_movies'][0]['poster'],
                         'https://webshare.cz/thumb/film.jpg')

    def test_no_unavailable_file(self):
        rows=make_rows([f('gone','Gone Film')],[],Checker(),Metadata())
        self.assertFalse(rows['new_movies'])


class DiscoveryTests(unittest.TestCase):
    def test_home_never_uses_empty_search_term(self):
        self.assertTrue(all(term for _,term,_ in queries_for_home()))
        received=[]
        def service(token,offset,term,sort='recent'):
            received.append((term,sort))
            return [{'ident':'f_'+term,'name':'Cinema Movie 2025 1080p CZ.mkv'}],1
        recent,popular,stats=discover('sample-session',service)
        self.assertTrue(recent)
        self.assertTrue(popular)
        self.assertGreater(stats['movie_candidates'],0)
        self.assertTrue(all(q[0] for q in received))

    def test_empty_api_results_explain_reason(self):
        recent,popular,stats=discover('sample-session',lambda token,offset,term,sort='recent':([],0))
        self.assertEqual(recent,[])
        self.assertEqual(popular,[])
        self.assertIn('nenašlo',empty_message(stats,0,0))

    def test_auth_failure_is_not_reported_as_missing_movies(self):
        _,_,stats=discover('sample-session',lambda token,offset,term,sort='recent':(None,0))
        self.assertEqual(stats['responses'],0)
        self.assertIn('neodpovídá',empty_message(stats,0,0))

    def test_navigation_tiles_have_no_movie_posters(self):
        if 'xbmcgui' not in sys.modules:
            fake=types.ModuleType('xbmcgui')
            fake.WindowXMLDialog=type('WindowXMLDialog',(),{})
            sys.modules['xbmcgui']=fake
        from cinematic_home import _fallback_card
        fake_addon=type('Addon',(),{'getAddonInfo':lambda self,name:'/tmp/test'})()
        result=_fallback_card(fake_addon,'KATALOG FILMŮ','plugin://menu/')
        self.assertEqual(result['poster'],'')
        self.assertEqual(result['kind'],'link')


class WindowLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=os.path.join(PLUG,'resources','skins','Default','1080i','bozsky-cinema.xml')
        cls.window=ET.parse(cls.path).getroot()

    def test_two_horizontal_poster_rails(self):
        controls=self.window.findall('.//control')
        ids={node.get('id') for node in controls}
        self.assertTrue({'401','402','101','102','103','104','105','106','107'}.issubset(ids))
        for name in ('401','402'):
            ctrl=next(node for node in controls if node.get('id')==name)
            self.assertEqual(ctrl.findtext('orientation'),'horizontal')
            self.assertIsNotNone(ctrl.find('focusedlayout'))
            self.assertIsNotNone(ctrl.find('itemlayout'))

    def test_remote_navigation_has_back_and_header(self):
        with open(os.path.join(PLUG,'cinematic_home.py'),encoding='utf-8') as handle:
            code=handle.read()
        self.assertIn('BACK_ACTIONS',code)
        self.assertIn('novinky_detail',code)
        self.assertIn('novinky_show',code)
        self.assertIn('self.close()',code)

    def test_skin_xml_is_local_to_plugin(self):
        self.assertEqual(self.window.tag,'window')
        self.assertIn('bozsky-cinema.xml', os.listdir(os.path.dirname(self.path)))
        with open(self.path,encoding='utf8') as source:
            self.assertIn('row1_heading',source.read())

class GeneratedTextureTests(unittest.TestCase):
    def test_png_generated_without_nonstandard_packages(self):
        # xbmcgui is not available in CI; minimal stub just for pure texture function.
        if 'xbmcgui' not in sys.modules:
            fake=types.ModuleType('xbmcgui')
            fake.WindowXMLDialog=type('WindowXMLDialog',(),{})
            sys.modules['xbmcgui']=fake
        from cinematic_home import ensure_textures
        with tempfile.TemporaryDirectory() as td:
            files=ensure_textures(td)
            self.assertEqual(set(files),{'background','fade','focus','button'})
            for path in files.values():
                with open(path,'rb') as handle:
                    self.assertEqual(handle.read(8),b'\x89PNG\r\n\x1a\n')

if __name__=='__main__':
    unittest.main()
