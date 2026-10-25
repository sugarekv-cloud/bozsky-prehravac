# -*- coding: utf-8 -*-
"""Verify KIVORA 0.26 recommendations are actual movies/series and skin is usable."""
import io
import json
import os
import sys
import tempfile
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)

from cinema_service_v2 import CinemaService
from cinema_recommendations import recommendations


def media(title,ident,kind='movie',poster='https://example.test/poster.jpg'):
    return {'title':title,'raw':title,'kind':kind,
            'year':'2024','ident':ident,'genre':'Drama','rating':82,
            'rating_source':'ČSFD','poster':poster,
            'files':[{'ident':ident,'name':title+'.2024.1080p.mkv'}]}


class RealTipsTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def service(self):
        return CinemaService('testtoken',lambda *a,**k:([],0),None,
                             profile=self.directory.name)

    def test_saved_verified_tips_populate_an_otherwise_empty_home(self):
        svc=self.service()
        saved=media('Film, který opravdu existuje','verified-id')
        with io.open(svc.tips_path,'w',encoding='utf8') as stream:
            json.dump({'saved':1,'cards':[saved]},stream)
        svc=self.service()
        result=svc.tips_snapshot({'_all_movies':[],'_all_shows':[]})
        films,weekly=recommendations(result,limit=12)
        self.assertEqual([f['ident'] for f in films],['verified-id'])
        self.assertEqual([f['ident'] for f in weekly],['verified-id'])
        self.assertEqual(films[0]['poster'],saved['poster'])

    def test_tips_background_discovery_returns_available_movie_and_series(self):
        original=CinemaService.full_catalog
        def verified(self,kind,requested=24,sort='date',quality='all',language='all'):
            return [media('Film ABC','movie-id','movie') if kind=='movie'
                    else media('Seriál XYZ','show-id','show')],False
        CinemaService.full_catalog=verified
        try:
            svc=self.service()
            svc.home_cache={'_all_movies':[media('Cached movie','cached-film')],
                            '_all_shows':[]}
            self.assertTrue(svc.start_tips_refresh())
            self.assertTrue(svc._tips_done.wait(5))
            cards=svc.take_tips_refresh()
            self.assertEqual({c['ident'] for c in cards},{'movie-id','show-id'})
            home=svc.tips_snapshot({'_all_movies':[],'_all_shows':[]})
            films,weekly=recommendations(home,limit=10)
            self.assertEqual({x['ident'] for x in films},{'movie-id','show-id'})
            again=self.service()
            self.assertEqual(len(again._tips_cards),2)
        finally:
            CinemaService.full_catalog=original

    def test_no_fabricated_media_for_empty_catalogue(self):
        svc=self.service()
        self.assertEqual(recommendations(svc.tips_snapshot({'_all_movies':[],
                                                            '_all_shows':[]})),
                         ([],[]))

    def test_current_home_cards_plus_external_tips_merge_without_duplicates(self):
        svc=self.service()
        same=media('True movie','same')
        svc._tips_cards=[same]
        result=svc.tips_snapshot({'_all_movies':[same], '_all_shows':[]})
        self.assertEqual(len(result['_all_movies']),1)


class MovieTipsPageTests(unittest.TestCase):
    def test_tips_page_actually_lists_verified_film_art(self):
        if 'xbmcgui' not in sys.modules:
            ui=types.ModuleType('xbmcgui')
            ui.WindowXMLDialog=type('WindowXMLDialog',(),{})
            sys.modules['xbmcgui']=ui
        if 'xbmc' not in sys.modules:
            sys.modules['xbmc']=types.ModuleType('xbmc')
        from cinema_screen_v2 import CinemaScreen
        win=CinemaScreen.__new__(CinemaScreen)
        movie=media('Název filmu','file123')
        class Service:
            token='test'
            last_diagnostics=''
            def home_fast(self):return {'_all_movies':[],'_all_shows':[]}
            def start_home_refresh(self):return False
            def tips_snapshot(self,home):
                return dict(home,_all_movies=[movie])
            def start_tips_refresh(self,force=False):return False
        win.service=Service()
        win.watch_store=None
        win.setProperty=lambda *args:None
        captured=[]
        win._fill=lambda *args,**kwargs:captured.append((args,kwargs))
        win._screen('recommendations')
        self.assertEqual(captured[0][0][1][0]['title'],'Název filmu')
        self.assertEqual(captured[0][0][1][0]['ident'],'file123')
        self.assertEqual(captured[0][0][1][0]['poster'],movie['poster'])

    def test_home_has_tips_as_first_shelf(self):
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as f:
            source=f.read()
        home=source[source.index("        if view=='home':"):
                    source.index("        elif view=='recommendations':")]
        self.assertIn("tips_snapshot(home)",home)
        self.assertIn("tips_bootstrap()",home)
        self.assertLess(home.index("('TIPY NA SLEDOVÁNÍ',personal)"),
                        home.index("('NEJLÉPE HODNOCENÉ FILMY · ČSFD'"))


class CinemaSkinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
                                       '1080i','fckyo-cinema-v2.xml')).getroot()

    def test_tips_are_second_in_sidebar_and_not_truncated(self):
        home=self.skin.find(".//control[@id='201']")
        tips=self.skin.find(".//control[@id='208']")
        following=self.skin.find(".//control[@id='202']")
        self.assertLess(int(home.findtext('top')),int(tips.findtext('top')))
        self.assertLess(int(tips.findtext('top')),int(following.findtext('top')))
        self.assertEqual(tips.findtext('label'),'TIPY PRO TEBE')
        self.assertEqual(home.findtext('ondown'),'208')
        self.assertEqual(tips.findtext('onup'),'201')

    def test_portrait_posters_are_not_cropped_as_landscape(self):
        for id in range(401,414):
            row=self.skin.find(".//control[@id='%d']"%id)
            for layout_type in ('itemlayout','focusedlayout'):
                layout=row.find(layout_type)
                self.assertEqual(layout.get('width'),'330')
                posters=[image for image in layout.findall("control[@type='image']")
                         if image.findtext('texture')=='$INFO[ListItem.Art(poster)]']
                self.assertEqual(len(posters),1)
                self.assertEqual(posters[0].findtext('aspectratio'),'keep')
                self.assertIn('String.IsEmpty(ListItem.Art(fanart))',
                              posters[0].findtext('visible'))

    def test_large_banner_does_not_stretch_movie_poster(self):
        hero=self.skin.findall(".//control[@type='image']")
        fallback=[i for i in hero if i.findtext('texture')==
                   '$INFO[Window.Property(hero_poster)]']
        self.assertEqual(len(fallback),1)
        self.assertEqual(fallback[0].findtext('aspectratio'),'keep')
        photo=[i for i in hero if i.findtext('texture')==
               '$INFO[Window.Property(hero_art)]']
        self.assertEqual(len(photo),1)
        self.assertGreater(int(photo[0].findtext('width')),900)


if __name__=='__main__':
    unittest.main()
