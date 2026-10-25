# -*- coding: utf-8 -*-
"""FCKYO 0.19: separate ranking sources, focus visibility and real playback state."""
import os
import sys
import tempfile
import types
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_user_state import WatchStore,watch_key
from cinema_rankings import csfd_only

def video(title,ident,kind='movie',rating=90,source='ČSFD',year='2024'):
    return {'title':title,'raw':title,'kind':kind,'ident':ident,'year':year,
            'files':[{'ident':ident,'name':title+'.'+year+'.mkv'}],
            'rating':rating,'rating_source':source}


class RankingSourceTests(unittest.TestCase):
    def test_csfd_excludes_webshare_imdb_and_unknown_sources(self):
        records=[video('ČSFD film','a',source='ČSFD',rating=85),
                 video('IMDb film','b',source='IMDb',rating=99),
                 video('Webshare film','c',source='Webshare',rating=100),
                 video('Bez zdroje','d',source='',rating=97)]
        self.assertEqual([c['title'] for c in csfd_only(records)],
                         ['ČSFD film'])

    def test_only_verified_cards_qualify_for_csfd(self):
        empty=video('Ghost','x')
        empty['files']=[]
        self.assertFalse(csfd_only([empty]))


class WatchStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=WatchStore(self.temp.name)
        self.movie={'title':'Zelená míle','raw_title':'The Green Mile',
                    'ident':'file-green','name':'The.Green.Mile.1999.1080p.mkv',
                    'kind':'movie','year':'1999','poster':'https://example.test/green.jpg'}
        self.series={'title':'Perníkový táta','raw_title':'Breaking Bad',
                     'ident':'ep03','name':'Breaking.Bad.S02E03.mkv',
                     'kind':'show','season':'2','episode':'3'}

    def test_playback_intent_not_counted_as_playback(self):
        self.store.pending_play(self.movie)
        self.assertEqual(self.store.continue_cards(),[])
        self.assertEqual(self.store.pop_pending()['ident'],'file-green')
        self.assertEqual(self.store.pop_pending(),{})

    def test_movie_progress_is_saved_and_can_resume(self):
        self.store.update_progress(self.movie,900,3600)
        rows=self.store.continue_cards('movie')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['progress'],25)
        self.assertEqual(rows[0]['position'],900)
        self.assertTrue(rows[0]['_continue'])
        self.assertEqual(rows[0]['ident'],'file-green')
        self.assertEqual(rows[0]['poster'],self.movie['poster'])
        self.assertNotIn('password',str(self.store._read(self.store.path)))

    def test_finished_movies_leave_continue_rail(self):
        self.store.update_progress(self.movie,3500,3600)
        self.assertEqual(self.store.continue_cards('movie'),[])

    def test_separate_series_episodes_have_separate_progress(self):
        later=dict(self.series,ident='ep04',episode='4',name='Breaking.Bad.S02E04.mkv')
        self.assertNotEqual(watch_key(self.series),watch_key(later))
        self.store.update_progress(self.series,120,2400)
        self.store.update_progress(later,250,2400)
        self.assertEqual(len(self.store.continue_cards('show')),2)
        self.store.mark_watched(self.series)
        rows=self.store.continue_cards('show')
        self.assertEqual([c['ident'] for c in rows],['ep04'])
        self.store.clear_progress(later)
        self.assertEqual(self.store.continue_cards('show'),[])

    def test_favorites_are_persistent_and_toggle(self):
        card=dict(self.movie,raw='The Green Mile',
                  files=[{'ident':'file-green','name':self.movie['name']}])
        self.assertTrue(self.store.toggle_favorite(card))
        self.assertEqual(WatchStore(self.temp.name).favorite_cards()[0]['title'],
                         'Zelená míle')
        self.assertFalse(self.store.toggle_favorite(card))
        self.assertEqual(self.store.favorite_cards(),[])


class KodiWatchServiceTests(unittest.TestCase):
    def test_tracker_does_not_create_progress_without_player(self):
        import importlib
        if 'xbmc' not in sys.modules:
            sys.modules['xbmc']=types.ModuleType('xbmc')
        if 'xbmcaddon' not in sys.modules:
            sys.modules['xbmcaddon']=types.ModuleType('xbmcaddon')
        if 'xbmcvfs' not in sys.modules:
            sys.modules['xbmcvfs']=types.ModuleType('xbmcvfs')
        tracker=importlib.import_module('service').WatchTracker
        class Player:
            def __init__(self):
                self.playing=False;self.position=0;self.duration=0;self.seek=[]
            def isPlayingVideo(self):return self.playing
            def getTime(self):return self.position
            def getTotalTime(self):return self.duration
            def seekTime(self,position):self.seek.append(position)
        with tempfile.TemporaryDirectory() as root:
            state=WatchStore(root)
            player=Player()
            play={'title':'Film','raw_title':'Film','ident':'file',
                  'name':'Film.2024.mkv','kind':'movie','year':'2024'}
            state.pending_play(dict(play,resume=350))
            watch=tracker(root,player=player,store=state)
            watch.tick()
            self.assertEqual(state.continue_cards(),[])
            player.playing=True
            player.duration=2400;player.position=380
            watch.tick()
            self.assertEqual(player.seek,[350.0])
            self.assertEqual(len(state.continue_cards()),1)
            player.position=2380
            watch.tick()
            player.playing=False
            watch.tick()
            self.assertEqual(state.continue_cards(),[])


class NetflixSkinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=os.path.join(PLUGIN,'resources','skins','Default','1080i',
                          'fckyo-cinema-v2.xml')
        cls.root=ET.parse(path).getroot()

    def test_widescreen_backdrop_art_on_all_rows(self):
        for id in range(401,412):
            listcontrol=self.root.find(".//control[@id='%d']"%id)
            self.assertIsNotNone(listcontrol)
            item=listcontrol.find('itemlayout')
            self.assertGreaterEqual(int(item.get('width')),290)
            self.assertGreaterEqual(int(item.get('height')),200)
            self.assertTrue(listcontrol.findall('ondown'))
            self.assertEqual(listcontrol.findall('ondown')[-1].text,str(id))

    def test_only_active_row_draws_red_poster_frame(self):
        for id in range(401,412):
            listcontrol=self.root.find(".//control[@id='%d']"%id)
            focused=listcontrol.find('focusedlayout')
            outline=next(i for i in focused.findall("control[@type='image']")
                         if i.findtext('texture')=='$INFO[Window.Property(cinema_focus)]')
            self.assertEqual(outline.findtext('visible'),'Control.HasFocus(%d)'%id)

    def test_resume_overlay_exists_on_posters(self):
        for id in range(401,412):
            listcontrol=self.root.find(".//control[@id='%d']"%id)
            for variant in ('itemlayout','focusedlayout'):
                bar=listcontrol.find(variant).find("control[@type='progress']")
                self.assertIsNotNone(bar)
                self.assertEqual(bar.findtext('info'),'ListItem.Property(progress)')

    def test_addon_registers_background_service(self):
        root=ET.parse(os.path.join(PLUGIN,'addon.xml')).getroot()
        service=root.find("./extension[@point='xbmc.service']")
        self.assertIsNotNone(service)
        self.assertEqual(service.get('library'),'service.py')
        self.assertEqual(root.get('version'),'0.28.0')


if __name__=='__main__':
    unittest.main()
