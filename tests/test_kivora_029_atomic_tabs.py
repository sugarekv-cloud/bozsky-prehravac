# -*- coding: utf-8 -*-
"""Reproduce screenshot regression: SERIÁLY selected but FILMY rows stay visible."""
import os
import sys
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
if 'xbmcgui' not in sys.modules:
    gui=types.ModuleType('xbmcgui')
    gui.WindowXMLDialog=type('WindowXMLDialog',(),{})
    sys.modules['xbmcgui']=gui
if 'xbmc' not in sys.modules:
    sys.modules['xbmc']=types.ModuleType('xbmc')
from cinema_screen_v2 import CinemaScreen


def verified(kind,ident):
    return dict(kind=kind,ident=ident,title='Series' if kind=='show' else 'Film',
                raw=ident,files=[dict(ident=ident,name=ident+'.1080p.mkv')],
                rating=90,rating_source='ČSFD')


class TabRenderingTests(unittest.TestCase):
    def window(self,source=None,error=False):
        window=CinemaScreen.__new__(CinemaScreen)
        cache=source if source is not None else {
            '_all_movies':[verified('movie','film')],
            '_all_shows':[verified('show','series')],
            '_all_premieres':[]}
        class Service:
            token='token'
            def home_fast(self):return cache
            def browse(self,view,sort='date',quality='all',language='all'):
                if error:
                    raise ValueError('Unexpected Webshare response on '+view)
                if view=='shows':
                    # Even a corrupt cache can contain movies among series.
                    return [verified('movie','wrong'),verified('show','series')]
                if view=='movies':
                    return cache.get('_all_movies',[])
                return cache.get('_all_premieres',[])
        window.service=Service()
        window.sort='date'
        window.quality='all'
        window.language='all'
        window.year='all'
        window.genre='all'
        window.rail_items=[[verified('movie','stale')]]+[[] for _ in range(12)]
        window.setProperty=lambda *a,**kw:None
        window._update_hero=lambda:None
        changes=[]
        window._fill=lambda *a,**kw:changes.append((a,kw))
        return window,changes

    def test_series_click_replaces_stale_film_ranked_shelves(self):
        win,rendered=self.window()
        win._screen('shows')
        self.assertEqual(len(rendered),1)
        fields,kw=rendered[0]
        self.assertIn('SERIÁLY',fields[0])
        self.assertIn('SERIÁLY',fields[2])
        self.assertNotIn('FILMY',fields[0])
        self.assertNotIn('FILMY',fields[2])
        shown=fields[3]
        self.assertEqual(shown[0]['kind'],'catalog_open')
        self.assertEqual(shown[0]['catalog_kind'],'show')
        self.assertTrue(all(c.get('kind') in ('show','catalog_open')
                            for c in shown))
        self.assertFalse(any(c.get('ident')=='wrong' for c in shown))

    def test_exception_during_series_catalogue_never_keeps_old_films(self):
        win,rendered=self.window(error=True)
        win._screen('shows')
        self.assertEqual(len(rendered),1)
        fields,_=rendered[0]
        self.assertIn('SERIÁLY',fields[0])
        self.assertEqual(fields[3][0]['catalog_kind'],'show')
        self.assertFalse(any(c.get('kind')=='movie' for c in fields[1]+fields[3]))

    def test_empty_series_cache_has_visible_specific_actions(self):
        win,rendered=self.window({
            '_all_movies':[verified('movie','film')],'_all_shows':[],
            '_all_premieres':[]},error=True)
        win._screen('shows')
        fields,_=rendered[0]
        self.assertIn('SERIÁLY',fields[0])
        self.assertEqual(fields[1][0]['kind'],'none')
        self.assertEqual(fields[3][0]['kind'],'catalog_open')
        self.assertEqual(fields[3][0]['catalog_kind'],'show')

    def test_film_tab_preserves_only_film_cards(self):
        win,rendered=self.window()
        win._screen('movies')
        fields,_=rendered[0]
        self.assertIn('FILMY',fields[0])
        self.assertEqual(fields[1][0]['kind'],'movie')
        self.assertEqual(fields[3][0]['catalog_kind'],'movie')

    def test_premieres_tab_never_inherits_old_ranked_films(self):
        win,rendered=self.window(error=True)
        win._screen('premieres')
        fields,_=rendered[0]
        self.assertEqual(fields[0],'FILMOVÉ PREMIÉRY')
        self.assertNotIn('ČSFD',fields[0])
        self.assertEqual(fields[1][0]['kind'],'none')

    def test_button_prevents_background_refocus_while_repainting(self):
        win,rendered=self.window(error=True)
        win.mode='movies'
        win.context=None
        win.stack=[]
        win._nav_focus_target=None
        win._switching_section=False
        win._refresh=lambda view,context=None,stack=True: (
            self.assertTrue(win._switching_section),
            win._screen(view,context))
        win.onClick(102)
        self.assertFalse(win._switching_section)
        self.assertEqual(win.mode,'shows')
        self.assertEqual(win._nav_focus_target,102)
        self.assertEqual(len(rendered),1)

    def test_header_in_skin_has_real_series_button(self):
        skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default','1080i',
                                   'fckyo-cinema-v2.xml')).getroot()
        tab=skin.find(".//control[@id='102']")
        self.assertEqual(tab.get('type'),'button')
        self.assertEqual(tab.findtext('label'),'SERIÁLY')


if __name__=='__main__':
    unittest.main()
