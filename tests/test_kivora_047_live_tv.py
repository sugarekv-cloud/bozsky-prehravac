# -*- coding: utf-8 -*-
"""KIVORA free-to-view live television regression suite.

No real broadcaster is contacted. Real stream reachability and geoblocking
require a Kodi/TV smoke test; unit tests verify safe source selection and UI.
"""
import io
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/'plugin.video.fckyo'
sys.path.insert(0,str(PLUGIN))
from cinema_live_tv import (
    CHANNELS,CT_ADDON_ID,CT_PLUGIN_URL,playable_url,channel,
    favorites,toggle_favorite,tv_cards,ct_card,
)
from cinema_navigation import save,consume,has_live_tv_return

SKIN=PLUGIN/'resources/skins/Default/1080i/fckyo-cinema-v2.xml'


class BroadcastDataTests(unittest.TestCase):
    def test_only_explicitly_allowlisted_free_broadcaster_endpoints(self):
        self.assertGreaterEqual(len(CHANNELS),5)
        self.assertEqual(len({entry['id'] for entry in CHANNELS}),len(CHANNELS))
        for entry in CHANNELS:
            url=playable_url(entry['id'])
            self.assertTrue(url.startswith('https://'),entry['id'])
            self.assertTrue(url.endswith('.m3u8'),entry['id'])
            self.assertEqual(entry['url'],url)
        for injected in ('https://some-paytv.example/live.m3u8',
                         'https://evil.example/playlist.m3u8',
                         'othervideo','https://sock/'):
            self.assertEqual(playable_url(injected),'')

    def test_valid_data_for_cards_and_czech_tv_addon(self):
        self.assertEqual(CT_ADDON_ID,'plugin.video.ivysilani.cz')
        self.assertEqual(CT_PLUGIN_URL,'plugin://plugin.video.ivysilani.cz/')
        for item in CHANNELS:
            self.assertEqual(channel(item['id']),item)
            self.assertTrue(item['plot'])
        self.assertEqual(ct_card()['kind'],'tv_addon')

    def test_favorite_roundtrip_and_no_stream_urls_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(favorites(tmp),[])
            ident=CHANNELS[0]['id']
            self.assertTrue(toggle_favorite(tmp,ident))
            self.assertEqual(favorites(tmp),[ident])
            favorites_cards,all_cards=tv_cards(tmp)
            self.assertEqual(len(all_cards),len(CHANNELS))
            self.assertEqual([c['channel_id'] for c in favorites_cards],[ident])
            file=Path(tmp)/'kivora-live-tv-favorites.json'
            saved=file.read_text(encoding='utf8')
            self.assertNotIn('.m3u8',saved)
            self.assertNotIn('https://',saved)
            self.assertFalse(toggle_favorite(tmp,ident))
            self.assertEqual(favorites(tmp),[])
            self.assertFalse(toggle_favorite(tmp,'unknown-channel'))

    def test_corrupt_and_oversized_favorite_cache_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'kivora-live-tv-favorites.json'
            p.write_text('{not JSON',encoding='utf-8')
            self.assertEqual(favorites(tmp),[])
            p.write_text('x'*10000,encoding='utf-8')
            self.assertEqual(favorites(tmp),[])

    def test_resume_hls_only_if_live_tv_was_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(has_live_tv_return(tmp))
            self.assertTrue(save(tmp,'live_tv',None,focus=401,index=2))
            self.assertTrue(has_live_tv_return(tmp))
            remembered=consume(tmp)
            self.assertEqual(remembered['view'],'live_tv')
            self.assertEqual(remembered['focus'],401)
            self.assertEqual(remembered['index'],2)
            self.assertFalse(has_live_tv_return(tmp))
            self.assertTrue(save(tmp,'movies',None))
            self.assertFalse(has_live_tv_return(tmp))


class LiveTvUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=ET.parse(SKIN).getroot()
        cls.source=(PLUGIN/'cinema_screen_v2.py').read_text(encoding='utf8')

    def test_tv_tab_is_in_main_menu_and_reachable_from_bluey(self):
        btn=self.doc.find(".//control[@id='111']")
        self.assertIsNotNone(btn)
        self.assertEqual(btn.findtext('label'),'ŽIVÁ TV')
        self.assertEqual(btn.findtext('onleft'),'109')
        self.assertEqual(btn.findtext('onright'),'107')
        bluey=self.doc.find(".//control[@id='109']")
        self.assertEqual(bluey.findtext('onright'),'111')
        gear=self.doc.find(".//control[@id='107']")
        self.assertEqual(gear.findtext('onleft'),'111')
        self.assertIn("111:'live_tv'",self.source)

    def test_login_not_required_for_live_tv(self):
        screen=self.source
        self.assertLess(screen.index("if view=='live_tv':\n            self._live_tv_screen()"),
                        screen.index("if not self.service.token:"))
        self.assertIn('self._live_tv_selected(c)',screen)
        self.assertIn('self._start_playback(stream)',screen)
        self.assertIn('self._live_tv_menu()',screen)

    def test_player_safety_and_return_handlers_are_present(self):
        service=(PLUGIN/'service.py').read_text(encoding='utf8')
        self.assertIn('has_live_tv_return(self.return_profile)',service)
        self.assertIn('self.return_to_addon()',service)
        self.assertIn("self.destination=CT_PLUGIN_URL",self.source)
        self.assertIn("self.is_play=False",self.source)
        self.assertIn("self._start_playback(stream)",self.source)

    def test_build_includes_generated_station_artwork(self):
        builder=(ROOT/'build_repo.py').read_text(encoding='utf8')
        generator=(ROOT/'tools/create_live_tv_icons.py').read_text(encoding='utf8')
        self.assertIn('make_live_tv_icons()',builder)
        self.assertIn('assert len(live_art)==5',builder)
        for record in CHANNELS:
            self.assertIn("'"+record['id']+"'",generator)


if __name__=='__main__':
    unittest.main()
