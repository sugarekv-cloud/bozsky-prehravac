# -*- coding: utf-8 -*-
"""FCKYO 0.22 regression: Home works, Tips always appears, cinematic UI."""
import os
import sys
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)

def screen_class():
    if 'xbmcgui' not in sys.modules:
        ui=types.ModuleType('xbmcgui')
        ui.WindowXMLDialog=type('WindowXMLDialog',(),{})
        sys.modules['xbmcgui']=ui
    if 'xbmc' not in sys.modules:
        sys.modules['xbmc']=types.ModuleType('xbmc')
    from cinema_screen_v2 import CinemaScreen
    return CinemaScreen

class HomeAndTipsTests(unittest.TestCase):
    def test_home_tab_and_sidebar_return_to_home_without_stack(self):
        for control in (106,201):
            window=screen_class().__new__(screen_class())
            window.stack=[('movies',None,401,6)]
            calls=[]
            window._screen=lambda *a,**k:calls.append((a,k))
            window.onClick(control)
            self.assertEqual(window.stack,[])
            self.assertEqual(calls,[ (('home',),{'stack':False}) ])

    def test_empty_cache_displays_a_real_tip_placeholder(self):
        window=screen_class().__new__(screen_class())
        class Service:
            token='test'
            last_diagnostics='Katalog aktualizován na pozadí'
            def home_fast(self):
                return {'_all_movies':[],'_all_shows':[],'movies':[],
                        'shows':[],'premieres':[],'classics':[],
                        'best_movies_year':[],'best_shows_year':[]}
            def start_home_refresh(self):return True
        window.service=Service()
        window.watch_store=None
        window.year='all'
        window.genre='all'
        window.quality='all'
        window.language='all'
        window.sort='date'
        window.setProperty=lambda *args:None
        captured=[]
        window._fill=lambda *args,**kwargs:captured.append((args,kwargs))
        window._screen('home')
        self.assertEqual(len(captured),1)
        args,options=captured[0]
        self.assertEqual(args[0],'TIPY NA SLEDOVÁNÍ')
        self.assertEqual(args[1][0]['kind'],'movies')
        self.assertEqual(args[2],'POKRAČOVAT VE SLEDOVÁNÍ')
        self.assertIn('TIPY NA TENTO TÝDEN',
                      [name for name,cards in options['extra_rows']])
        self.assertEqual(len(options['extra_rows']),10)

    def test_recommendations_support_previous_cache_format(self):
        from cinema_recommendations import recommendations
        film={'kind':'movie','ident':'film','title':'Zábavný film',
              'raw':'Zábavný film','genre':'Komedie','rating':83,
              'rating_source':'ČSFD','year':'2024',
              'files':[{'ident':'film','name':'Zabavny.film.mkv'}]}
        personal,weekly=recommendations({'movies':[film]},week=202643)
        self.assertEqual(personal[0]['ident'],'film')
        self.assertEqual(weekly[0]['ident'],'film')

class ModernSkinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default','1080i',
                                       'fckyo-cinema-v2.xml')).getroot()
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as file:
            cls.code=file.read()

    def test_full_portrait_artwork_rail_and_hero(self):
        for cid in range(401,414):
            row=self.skin.find(".//control[@id='%d']"%cid)
            layout=row.find('itemlayout')
            self.assertGreater(int(layout.get('height')),int(layout.get('width'))) if cid in (403,404,408,411,412,413) else self.assertGreater(int(layout.get('width')),int(layout.get('height')))
            art=[i for i in layout.findall("control[@type='image']")
                 if i.findtext('texture')=='$INFO[ListItem.Art(poster)]']
            self.assertEqual(len(art),1)
            self.assertGreater(int(art[0].findtext('height')),
                               int(art[0].findtext('width')))
            self.assertEqual(row.findtext('onleft'),'201')
        hero=next(i for i in self.skin.findall(".//control[@type='image']")
                  if i.findtext('texture')=='$INFO[Window.Property(hero_art)]')
        self.assertGreaterEqual(int(hero.findtext('height')),380)

    def test_real_sidebar_buttons_and_home_tab(self):
        for cid in (106,201,202,203,204,205,206,207):
            control=self.skin.find(".//control[@id='%d']"%cid)
            self.assertIsNotNone(control)
            self.assertEqual(control.get('type'),'button')
        self.assertIn("106:'home'",self.code)
        self.assertIn("201:'home'",self.code)
        self.assertIn("202:'continue'",self.code)

    def test_rating_or_recommendation_badge_on_each_card(self):
        for cid in range(401,414):
            card=self.skin.find(".//control[@id='%d']"%cid)
            for kind in ('itemlayout','focusedlayout'):
                xml=ET.tostring(card.find(kind),encoding='unicode')
                self.assertIn('ListItem.Property(rating_label)',xml)
        self.assertIn("art['thumb']=c.get('fanart') or c.get('poster')",
                      self.code)

if __name__=='__main__':
    unittest.main()
