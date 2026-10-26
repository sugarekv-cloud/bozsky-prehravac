# -*- coding: utf-8 -*-
"""Guard the 0.36.0 TV redesign against unusable or visually inconsistent Kodi XML.

This runs without Kodi: checks declarative geometry, interaction routing and artwork
fallback. A real Android TV smoke test is still required after installation.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugin.video.fckyo'
SKIN = PLUGIN / 'resources/skins/Default/1080i/fckyo-cinema-v2.xml'
LANDSCAPE = (401, 402, 405, 406, 407, 409, 410)
PORTRAIT = (403, 404, 408, 411, 412, 413)
ROWS = LANDSCAPE + PORTRAIT

class CinemaTV036Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ET.parse(SKIN).getroot()

    def control(self, ident):
        obj = self.root.find(".//control[@id='%s']" % ident)
        self.assertIsNotNone(obj, "Missing Kodi control %s" % ident)
        return obj

    def test_version_and_preserved_plugin_identity(self):
        addon = ET.parse(PLUGIN / 'addon.xml').getroot()
        self.assertEqual(addon.get('version'), '0.36.0')
        self.assertEqual(addon.get('id'), 'plugin.video.fckyo')
        self.assertEqual(addon.get('name'), 'Božský přehrávač')

    def test_remote_navigation_buttons_and_bluey(self):
        for ident in (101, 102, 103, 104, 105, 106, 107, 109, 108, 110):
            self.assertEqual(self.control(ident).get('type'), 'button')
        self.assertEqual(self.control(109).findtext('label'), 'BLUEY')
        self.assertIn('PŘEHRÁT', self.control(108).findtext('label'))
        self.assertIn('DETAIL', self.control(110).findtext('label'))

    def test_red_primary_action_is_not_same_as_secondary(self):
        play = self.control(108)
        detail = self.control(110)
        self.assertIn('cinema_cta', play.findtext('texturenofocus'))
        self.assertIn('cinema_cta_focus', play.findtext('texturefocus'))
        self.assertNotEqual(play.findtext('texturenofocus'), detail.findtext('texturenofocus'))

    def test_film_banner_and_legible_copy(self):
        hero = self.root.find(".//control[@type='image'][texture='$INFO[Window.Property(hero_art)]']")
        self.assertIsNotNone(hero)
        self.assertGreaterEqual(int(hero.findtext('width')), 1500)
        scrim = self.root.find(".//control[@type='image'][texture='$INFO[Window.Property(cinema_fade)]']")
        self.assertIsNotNone(scrim)
        self.assertGreaterEqual(int(scrim.findtext('width')), 1800)
        plot = self.root.find(".//control[@type='textbox'][label='$INFO[Window.Property(hero_plot)]']")
        self.assertIsNotNone(plot)
        self.assertGreaterEqual(int(plot.findtext('height')), 85)
        self.assertIn('false', plot.findtext('autoscroll'))

    def test_all_thirteen_rows_exist(self):
        for ident in ROWS:
            rail = self.control(ident)
            self.assertEqual(rail.findtext('orientation'), 'horizontal')
            self.assertGreaterEqual(int(rail.findtext('width')), 1750)
            self.assertIsNotNone(rail.find('itemlayout'))
            self.assertIsNotNone(rail.find('focusedlayout'))

    def test_landscape_and_portrait_cards_keep_correct_aspect(self):
        for ident in LANDSCAPE:
            item = self.control(ident).find('itemlayout')
            self.assertGreater(int(item.get('width')), int(item.get('height')))
        for ident in PORTRAIT:
            item = self.control(ident).find('itemlayout')
            self.assertGreater(int(item.get('height')), int(item.get('width')))

    def test_landscape_cards_show_titles_for_posters_or_backdrops(self):
        for ident in LANDSCAPE:
            rail = self.control(ident)
            for name in ('itemlayout', 'focusedlayout'):
                layout = rail.find(name)
                titles = [c for c in layout.findall("control[@type='label']")
                          if c.findtext('label') == '$INFO[ListItem.Label]']
                self.assertTrue(any('ListItem.Art(fanart)' in (c.findtext('visible') or '')
                                    and 'ListItem.Art(poster)' in (c.findtext('visible') or '')
                                    for c in titles), (ident, name))
                self.assertFalse(any(c.findtext('left') == '161' for c in layout),
                                 'Old split-card year label was not removed')

    def test_poster_fallback_and_shading(self):
        for ident in LANDSCAPE:
            for name in ('itemlayout', 'focusedlayout'):
                layout = self.control(ident).find(name)
                art = layout.findall("control[@type='image']")
                self.assertTrue(any(x.findtext('texture') == '$INFO[ListItem.Art(poster)]'
                                    and x.findtext('aspectratio') == 'keep' for x in art))
                gradients = [x for x in art if x.findtext('texture') ==
                             '$INFO[Window.Property(cinema_cardfade)]']
                self.assertEqual(len(gradients), 1)
                self.assertIn('ListItem.Art(poster)', gradients[0].findtext('visible'))

    def test_every_card_tracks_resume_progress(self):
        for ident in ROWS:
            for name in ('itemlayout', 'focusedlayout'):
                bar = self.control(ident).find(name).find("control[@type='progress']")
                self.assertIsNotNone(bar, (ident, name))
                self.assertEqual(bar.findtext('info'), 'ListItem.Property(progress)')

    def test_focus_and_remote_back_routing(self):
        for ident in ROWS:
            rail = self.control(ident)
            self.assertIsNotNone(rail.find('onup'))
            self.assertIsNotNone(rail.find('ondown'))
            self.assertTrue(rail.findtext('onleft'))
        for ident in (201, 202, 203, 204, 205, 206, 207, 208):
            self.assertEqual(self.control(ident).get('type'), 'button')

    def test_new_palette_and_refreshable_texture_cache(self):
        code = (PLUGIN / 'cinematic_home.py').read_text(encoding='utf8')
        self.assertIn("stream_v9_", code)
        self.assertIn("color = (229,9,20,255)", code)
        self.assertIn("kind == 'cta_focus'", code)
        self.assertIn("'cta':(2,2)", code)
        brand = (ROOT / 'tools/create_brand.py').read_text(encoding='utf8')
        self.assertIn('RED=(229,9,20)', brand)

    def test_show_search_and_playback_logic_intact(self):
        logic = (PLUGIN / 'cinema_screen_v2.py').read_text(encoding='utf8')
        for fragment in ("VERSION='0.36.0'", "'bluey_search'", "'genre_open'",
                         "'catalog_more'", "'file'", "'movie'", "'show'",
                         'self._play_saved(c)', "self._refresh('files'"):
            self.assertIn(fragment, logic)

if __name__ == '__main__':
    unittest.main()
