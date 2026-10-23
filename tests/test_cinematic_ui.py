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

from cinematic_catalog import make_rows

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

    def test_no_unavailable_file(self):
        rows=make_rows([f('gone','Gone Film')],[],Checker(),Metadata())
        self.assertFalse(rows['new_movies'])

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
