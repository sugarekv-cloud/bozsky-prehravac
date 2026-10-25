# -*- coding: utf-8 -*-
"""Ensure the larger featured movie panel stays usable by TV remote."""
import os
import sys
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUG=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUG)


def get_screen():
    if 'xbmcgui' not in sys.modules:
        gui=types.ModuleType('xbmcgui')
        gui.WindowXMLDialog=type('WindowXMLDialog',(),{})
        sys.modules['xbmcgui']=gui
    if 'xbmc' not in sys.modules:
        sys.modules['xbmc']=types.ModuleType('xbmc')
    from cinema_screen_v2 import CinemaScreen
    return CinemaScreen


class FeaturedMovieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=os.path.join(PLUG,'resources','skins','Default','1080i',
                          'fckyo-cinema-v2.xml')
        cls.window=ET.parse(path).getroot()

    def test_banner_action_opens_selected_film(self):
        screen=get_screen().__new__(get_screen())
        film={'kind':'movie','title':'Test','files':[{'ident':'film'}]}
        screen.featured_card=film
        actions=[]
        screen._refresh=lambda *args:actions.append(args)
        screen.onClick(108)
        self.assertEqual(actions,[('files',(film,None,None))])

    def test_banner_action_opens_series(self):
        screen=get_screen().__new__(get_screen())
        show={'kind':'show','title':'Show'}
        screen.featured_card=show
        actions=[]
        screen._refresh=lambda *args:actions.append(args)
        screen.onClick(108)
        self.assertEqual(actions,[('seasons',show)])

    def test_banner_renders_only_for_available_movie_or_show(self):
        screen=get_screen().__new__(get_screen())
        film={'kind':'movie','title':'Cinema','year':'2024','plot':'Drama',
              'quality':'4K','fanart':'https://example.test/bg.jpg'}
        props={}
        screen.featured_card=None
        screen._selected=lambda:film
        screen.setProperty=lambda k,v:props.__setitem__(k,v)
        screen._update_hero()
        self.assertEqual(screen.featured_card,film)
        self.assertEqual(props['hero_action'],'yes')
        screen._selected=lambda:None
        screen.getFocusId=lambda:108
        screen._update_hero()
        self.assertEqual(props['hero_title'],'Cinema')
        screen.getFocusId=lambda:101
        screen._update_hero()
        self.assertEqual(props['hero_action'],'yes')

    def test_banner_xml_is_large_and_remote_focusable(self):
        banner=self.window.find(".//control[@id='108']")
        self.assertIsNotNone(banner)
        self.assertEqual(banner.get('type'),'button')
        self.assertEqual(banner.findtext('onup'),'106')
        self.assertEqual(banner.findtext('ondown'),'401')
        self.assertIn('hero_action',banner.findtext('visible'))
        image=next(node for node in self.window.findall(".//control[@type='image']")
                   if node.findtext('texture')=='$INFO[Window.Property(hero_art)]')
        self.assertGreaterEqual(int(image.findtext('height')),290)


if __name__=='__main__':
    unittest.main()
