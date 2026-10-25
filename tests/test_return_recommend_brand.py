# -*- coding: utf-8 -*-
"""FCKYO 0.21: playback return, personal recommendations and modern brand UI."""
import os
import sys
import tempfile
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_user_state import WatchStore
from cinema_recommendations import recommendations


def card(name, ident,genre='Drama',rating=85,kind='movie',year='2024'):
    return {'title':name,'raw':name,'ident':ident,'year':year,'kind':kind,
            'genre':genre,'rating':rating,'rating_source':'ČSFD',
            'files':[{'ident':ident,'name':name+'.mkv'}]}


class WatchReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for module in ('xbmc','xbmcaddon','xbmcvfs'):
            if module not in sys.modules:
                sys.modules[module]=types.ModuleType(module)
        from service import WatchTracker
        cls.WatchTracker=WatchTracker

    def test_closing_started_film_reopens_fckyo_once(self):
        class Player:
            playing=False
            def isPlayingVideo(self): return self.playing
            def getTotalTime(self):return 3600
            def getTime(self):return 600
            def seekTime(self,t):pass
        with tempfile.TemporaryDirectory() as tmp:
            store=WatchStore(tmp)
            movie={'ident':'id1','name':'Film.2024.mkv','title':'Film',
                   'kind':'movie','year':'2024'}
            store.pending_play(movie)
            reopened=[]
            player=Player()
            tracker=self.WatchTracker(tmp,player=player,store=store,
                                      return_to_addon=lambda:reopened.append('cinema'))
            tracker.tick()  # Kodi has not started the stream yet.
            self.assertEqual(reopened,[])
            player.playing=True
            tracker.tick()
            player.playing=False
            tracker.tick()
            tracker.tick()
            self.assertEqual(reopened,['cinema'])
            self.assertEqual(len(store.continue_cards('movie')),1)

    def test_untracked_kodi_video_does_not_reopen_fckyo(self):
        class Player:
            playing=True
            def isPlayingVideo(self):return self.playing
            def getTotalTime(self):return 900
            def getTime(self):return 50
        with tempfile.TemporaryDirectory() as tmp:
            opened=[]
            player=Player()
            tracker=self.WatchTracker(tmp,player=player,
                                      return_to_addon=lambda:opened.append(1))
            tracker.tick()
            player.playing=False
            tracker.tick()
            self.assertEqual(opened,[])

    def test_reopen_uses_correct_addon_route(self):
        import service
        old=getattr(service.xbmc,'executebuiltin',None)
        calls=[]
        service.xbmc.executebuiltin=lambda cmd:calls.append(cmd)
        try:
            self.WatchTracker._return_to_addon()
        finally:
            if old is None:
                delattr(service.xbmc,'executebuiltin')
            else:
                service.xbmc.executebuiltin=old
        self.assertIn('plugin.video.fckyo/?action=cinematic_home',calls[0])


class RecommendationTests(unittest.TestCase):
    def test_genuine_verified_cards_only(self):
        good=card('Comedy','c','Komedie',91)
        phantom=dict(card('Phantom','p','Komedie',99),files=[])
        external=dict(card('Unverified','u','Drama',100),ident='')
        rec,weekly=recommendations({'_all_movies':[good,phantom,external]},
                                    limit=12,week=202643)
        self.assertEqual([x['title'] for x in rec],['Comedy'])
        self.assertEqual([x['title'] for x in weekly],['Comedy'])

    def test_favorites_genre_influences_suggestions(self):
        movie=card('Comedy','com','Comedy',85)
        thriller=card('Thriller','thr','Thriller',89)
        with tempfile.TemporaryDirectory() as root:
            store=WatchStore(root)
            liked=card('Favourite','fav','Comedy',90)
            liked['name']='Favourite.2024.mkv'
            store.toggle_favorite(liked)
            rec,weekly=recommendations({'_all_movies':[movie,thriller,liked]},
                                        store,limit=2,week=202643)
            self.assertEqual(rec[0]['title'],'Comedy')
            self.assertFalse(any(x['title']=='Favourite' for x in rec+weekly))

    def test_completed_titles_not_recommended(self):
        film=card('Watched','w','Horror',93)
        movie=dict(film,name='Watched.mkv',raw_title='Watched')
        with tempfile.TemporaryDirectory() as root:
            store=WatchStore(root)
            store.update_progress(movie,3590,3600)
            rec,weekly=recommendations({'_all_movies':[film]},store)
            self.assertEqual(rec,[])
            self.assertEqual(weekly,[])

    def test_weekly_rotates_in_a_repeatable_way(self):
        films=[card('Film %02d'%i,str(i),rating=75+i) for i in range(12)]
        first=recommendations({'_all_movies':films},week=202643)[1]
        second=recommendations({'_all_movies':films},week=202643)[1]
        self.assertEqual([x['ident'] for x in first],[x['ident'] for x in second])


class BrandAndNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
                         '1080i','fckyo-cinema-v2.xml')).getroot()
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as f:
            cls.screen=f.read()

    def test_kodi_header_uses_custom_generated_logo(self):
        images=self.skin.findall(".//control[@type='image']")
        self.assertTrue(any(i.findtext('texture')=='$INFO[Window.Property(cinema_brand)]'
                            for i in images))
        with open(os.path.join(ROOT,'build_repo.py'),encoding='utf8') as file:
            builder=file.read()
        self.assertIn('make_brand()',builder)
        self.assertIn('resources/icon.png',builder)

    def test_top_nav_has_clear_active_and_focus_indicators(self):
        for num in (100,101,102,103,104,105):
            self.assertIsNotNone(self.skin.find(".//control[@id='%d']"%num))
            matches=[i for i in self.skin.findall(".//control[@type='image']")
                     if 'Control.HasFocus(%d)'%num in (i.findtext('visible') or '')]
            self.assertGreaterEqual(len(matches),1)
        self.assertIn("self.setProperty('nav_active',nav)",self.screen)

    def test_webshare_popularity_shelves_are_removed_from_home(self):
        start=self.screen.index("        if view=='home':")
        end=self.screen.index("        elif view in ('movies'",start)
        segment=self.screen[start:end]
        self.assertNotIn('POPULÁRNÍ NA WEBSHARE',segment)
        self.assertIn('NEJLÉPE HODNOCENÉ FILMY · ČSFD',segment)
        self.assertIn('NEJLÉPE HODNOCENÉ SERIÁLY · ČSFD',segment)
        self.assertIn('TIPY PRO TEBE',segment)


if __name__=='__main__':
    unittest.main()
