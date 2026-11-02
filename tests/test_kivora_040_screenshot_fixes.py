# -*- coding: utf-8 -*-
"""Screenshot-driven KIVORA 0.40.0 TV regression checks.

Android TV screenshot showed unreadable Play text, image-in-image covers,
titles hidden on top of video stills and an overlapping footer.
These checks inspect Kodi's real XML and generated-texture source,
not a simulated Android player.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'plugin.video.fckyo'
XML = ADDON / 'resources/skins/Default/1080i/fckyo-cinema-v2.xml'
LANDSCAPE = (401, 402, 405, 406, 407, 409, 410)


class ScreenshotFixes040Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skin = ET.parse(XML).getroot()

    def test_landscape_has_one_single_nonduplicated_image_fallback(self):
        for ident in LANDSCAPE:
            row = self.skin.find(".//control[@id='%s']" % ident)
            for kind in ('itemlayout', 'focusedlayout'):
                node = row.find(kind)
                images = node.findall("control[@type='image']")
                posters = [x for x in images if x.findtext('texture') ==
                           '$INFO[ListItem.Art(poster)]']
                self.assertEqual(len(posters), 1, (ident, kind))
                self.assertEqual(posters[0].findtext('aspectratio'), 'keep')
                self.assertEqual(posters[0].findtext('width'), '344')
                self.assertEqual(posters[0].findtext('height'), '196')

    def test_landscape_title_and_year_are_below_video_artwork(self):
        for ident in LANDSCAPE:
            row = self.skin.find(".//control[@id='%s']" % ident)
            for kind in ('itemlayout', 'focusedlayout'):
                layout = row.find(kind)
                titles = [x for x in layout.findall("control[@type='label']")
                          if x.findtext('label') == '$INFO[ListItem.Label]']
                self.assertTrue(titles, (ident, kind))
                self.assertTrue(any(int(x.findtext('top')) >= 205 for x in titles))
                years = [x for x in layout.findall("control[@type='label']")
                         if x.findtext('label') == '$INFO[ListItem.Property(year)]']
                self.assertEqual(len(years), 1)
                self.assertGreater(int(years[0].findtext('top')),
                                   int(titles[-1].findtext('top')))

    def test_play_has_light_text_and_explicit_button_background(self):
        play = self.skin.find(".//control[@id='108']")
        self.assertEqual(play.findtext('textcolor'), 'FFF8F8F5')
        self.assertEqual(play.findtext('texturefocus'),
                         '$INFO[Window.Property(cinema_cta_focus)]')
        backgrounds = [img for img in self.skin.findall(".//control[@type='image']")
                       if img.findtext('texture') ==
                       '$INFO[Window.Property(cinema_cta)]']
        self.assertEqual(len(backgrounds), 1)
        bg = backgrounds[0]
        for key in ('left', 'top', 'width', 'height'):
            self.assertEqual(bg.findtext(key), play.findtext(key))
        self.assertIn('hero_action', bg.findtext('visible'))
        tex = (ADDON / 'cinematic_home.py').read_text(encoding='utf-8')
        self.assertIn('color = (52,60,67,255)', tex)
        self.assertIn('color = (77,88,94,255)', tex)
        self.assertIn('stream_v11_', tex)

    def test_normal_home_does_not_put_status_over_second_row(self):
        statuses = [x for x in self.skin.findall(".//control[@type='label']")
                    if x.findtext('label') ==
                    '$INFO[Window.Property(ui_status)]']
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].findtext('visible'),
                         'String.IsEmpty(Window.Property(row1_heading))')

    def test_no_changes_to_remote_navigation_and_release_identity(self):
        addon = ET.parse(ADDON / 'addon.xml').getroot()
        self.assertEqual(addon.get('name'), 'KIVORA')
        self.assertEqual(addon.get('id'), 'plugin.video.fckyo')
        self.assertEqual(addon.get('version'), '0.40.0')
        for ident in (101, 102, 103, 104, 105, 106, 107, 108, 109, 110):
            self.assertIsNotNone(self.skin.find(".//control[@id='%s']" % ident))
        for ident in range(401,414):
            row=self.skin.find(".//control[@id='%s']" % ident)
            self.assertIsNotNone(row)
            self.assertTrue(row.findtext('onleft'))


if __name__ == '__main__':
    unittest.main()
