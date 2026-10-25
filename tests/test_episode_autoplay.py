# -*- coding: utf-8 -*-
"""Autoplay exactly one consecutive, availability-verified episode on Kodi end."""
import os
import sys
import tempfile
import types
import unittest
from urllib.parse import urlsplit, parse_qs
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_autoplay import next_episode_key, select_release
from cinema_user_state import WatchStore


class NextEpisodeSelectionTests(unittest.TestCase):
    def test_immediately_following_episode(self):
        seasons={1:{1:[{'ident':'a'}],2:[{'ident':'b'}],
                    3:[{'ident':'c'}]},2:{1:[{'ident':'d'}]}}
        self.assertEqual(next_episode_key(seasons,1,1),(1,2))
        self.assertEqual(next_episode_key(seasons,1,3),(2,1))
        self.assertIsNone(next_episode_key(seasons,2,1))

    def test_episode_gap_cannot_skip_episode_three(self):
        self.assertIsNone(next_episode_key(
            {1:{1:[{}],2:[{}],4:[{}]},2:{1:[{}]}},1,2))
        self.assertIsNone(next_episode_key({3:{2:[{}]}},2,8))
        self.assertIsNone(next_episode_key({1:{2:[{}]}},1,0))

    def test_quality_and_language_preference(self):
        releases=[
            {'ident':'a','name':'Show.S01E02.2160p.WEB-DL.mkv'},
            {'ident':'b','name':'Show.S01E02.1080p.CZ.WEB-DL.mkv'},
            {'ident':'c','name':'Show.S01E02.720p.CZ.mkv'}
        ]
        chosen=select_release(releases,'Show.S01E01.1080p.CZ.WEB-DL.mkv')
        self.assertEqual(chosen['ident'],'b')
        self.assertIsNone(select_release([],'Show.S01E01.mkv'))

    def test_pending_and_resume_preserve_original_title(self):
        with tempfile.TemporaryDirectory() as root:
            store=WatchStore(root)
            source={'ident':'id1','name':'Breaking.Bad.S02E01.mkv',
                    'title':'Perníkový táta','raw_title':'Breaking Bad',
                    'original':'Breaking Bad','kind':'show',
                    'season':'2','episode':'1'}
            store.pending_play(source)
            pending=store.pop_pending()
            self.assertEqual(pending['original'],'Breaking Bad')
            store.update_progress(pending,350,2600)
            resumed=store.continue_cards('show')[0]
            self.assertEqual(resumed['original'],'Breaking Bad')


def tracker_class():
    for name in ('xbmc','xbmcaddon','xbmcvfs'):
        if name not in sys.modules:
            sys.modules[name]=types.ModuleType(name)
    from service import WatchTracker
    return WatchTracker


class Player:
    def __init__(self):
        self.playing=False
        self.position=0
        self.total=1800
    def isPlayingVideo(self):
        return self.playing
    def getTotalTime(self):
        return self.total
    def getTime(self):
        return self.position
    def seekTime(self,position):
        self.position=position


class AutoplayTrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=WatchStore(self.temp.name)
        self.player=Player()
        self.next=[]
        self.returned=[]
        self.enabled=True
        tracker=tracker_class()
        self.tracker=tracker(self.temp.name,player=self.player,store=self.store,
                             play_next=lambda item:self.next.append(item),
                             return_to_addon=lambda:self.returned.append(True),
                             autoplay_enabled=lambda:self.enabled)

    def start(self,kind='show',season='1',episode='3'):
        self.store.pending_play({'ident':'id3','name':'Show.S01E03.1080p.mkv',
                                 'title':'Show','raw_title':'Show','kind':kind,
                                 'season':season,'episode':episode})
        self.player.playing=True
        self.player.position=150
        self.tracker.tick()

    def finish(self,ended=False,stopped=False):
        self.player.playing=False
        self.tracker._ended=ended
        self.tracker._stopped=stopped
        self.tracker.tick()

    def test_natural_ending_autoplays_once(self):
        self.start()
        self.player.position=1799
        self.tracker.tick()
        self.finish(ended=True)
        self.tracker.tick()
        self.assertEqual(len(self.next),1)
        self.assertEqual(self.returned,[])
        self.assertEqual(self.next[0]['episode'],'3')
        self.assertEqual(self.store.continue_cards('show'),[])

    def test_manual_stop_at_99_percent_does_not_autoplay(self):
        self.start()
        self.player.position=1790
        self.tracker.tick()
        self.finish(stopped=True)
        self.assertEqual(self.next,[])
        self.assertEqual(len(self.returned),1)

    def test_movie_never_autoplays(self):
        self.start(kind='movie',season='',episode='')
        self.finish(ended=True)
        self.assertEqual(self.next,[])
        self.assertEqual(self.returned,[True])

    def test_series_with_missing_episode_number_returns_home(self):
        self.start(episode='')
        self.finish(ended=True)
        self.assertEqual(self.next,[])
        self.assertEqual(self.returned,[True])

    def test_autoplay_can_be_disabled(self):
        self.start()
        self.enabled=False
        self.finish(ended=True)
        self.assertEqual(self.next,[])
        self.assertEqual(self.returned,[True])

    def test_failed_autoplay_falls_back_to_home(self):
        self.start()
        def fail(item):
            raise RuntimeError('Kodi cannot start stream')
        self.tracker.play_next=fail
        self.finish(ended=True)
        self.assertEqual(self.returned,[True])

    def test_built_in_url_is_encoded_without_secrets(self):
        import service
        commands=[]
        old=getattr(service.xbmc,'executebuiltin',None)
        service.xbmc.executebuiltin=lambda value:commands.append(value)
        try:
            self.tracker._play_next_episode({
                'kind':'show','title':'Perníkový táta',
                'raw_title':'Breaking Bad','season':'2','episode':'4',
                'name':'Breaking.Bad.S02E04.1080p.CZ.mkv'})
        finally:
            if old is None:
                delattr(service.xbmc,'executebuiltin')
            else:
                service.xbmc.executebuiltin=old
        self.assertEqual(len(commands),1)
        self.assertTrue(commands[0].startswith('PlayMedia(plugin://plugin.video.fckyo/?'))
        path=commands[0][len('PlayMedia('):-1]
        query=parse_qs(urlsplit(path).query)
        self.assertEqual(query['action'],['autoplay_episode'])
        self.assertEqual(query['raw_title'],['Breaking Bad'])
        self.assertEqual(query['episode'],['4'])
        self.assertNotIn('token',query)


class AutoplayIntegrationTests(unittest.TestCase):
    def test_plugin_route_resolves_only_checked_next_episodes(self):
        with open(os.path.join(PLUGIN,'fckyo.py'),encoding='utf8') as file:
            contents=file.read()
        self.assertIn("params['action'] == 'autoplay_episode'",contents)
        self.assertIn("next_episode_key(seasons,season,episode)",contents)
        self.assertIn("client.episode_variants(show,new_season,new_episode)",contents)
        self.assertIn("play(playback)",contents)
        self.assertIn("ActivateWindow(Videos,plugin://plugin.video.fckyo/",contents)

    def test_setting_is_opt_out_and_default_enabled(self):
        root=ET.parse(os.path.join(PLUGIN,'resources','settings.xml')).getroot()
        node=root.find(".//setting[@id='autoplay_next_episode']")
        self.assertIsNotNone(node)
        self.assertEqual(node.get('type'),'bool')
        self.assertEqual(node.get('default'),'true')


if __name__=='__main__':
    unittest.main()
