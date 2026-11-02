# -*- coding: utf-8 -*-
"""KIVORA Atelier / 0.39.0 visual-system and remote-navigation regression."""
from pathlib import Path
from xml.etree import ElementTree as ET
import sys
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugin.video.fckyo'
SKIN = PLUGIN / 'resources/skins/Default/1080i/fckyo-cinema-v2.xml'
sys.path.insert(0, str(ROOT))


def rgb(hex_argb):
    """Parse a standard Kodi ARGB colour."""
    return tuple(int(hex_argb[i:i+2], 16) for i in (2, 4, 6))


def contrast_ratio(first, second):
    def channel(value):
        value = value / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + .055) / 1.055) ** 2.4
    def luminance(color):
        return sum(channel(c) * w for c, w in zip(color, (.2126, .7152, .0722)))
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + .05) / (b + .05)


class AtelierTVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ET.parse(SKIN).getroot()

    def control(self, ident):
        node = self.root.find(".//control[@id='%s']" % ident)
        self.assertIsNotNone(node, 'Missing Kodi remote control %s' % ident)
        return node

    def test_unchanged_navigation_and_player_routes(self):
        for ident in (101, 102, 103, 104, 105, 106, 107, 108, 109, 110,
                      201, 202, 203, 204, 205, 206, 207, 208):
            self.assertEqual(self.control(ident).get('type'), 'button')
        for ident in range(401, 414):
            self.assertEqual(self.control(ident).get('type'), 'list')
            for tag in ('itemlayout', 'focusedlayout'):
                self.assertIsNotNone(self.control(ident).find(tag))
        self.assertIn('PŘEHRÁT', self.control(108).findtext('label'))
        self.assertEqual(self.control(109).findtext('label'), 'BLUEY')

    def test_light_primary_action_is_readable(self):
        play = self.control(108)
        self.assertEqual(play.findtext('texturenofocus'),
                         '$INFO[Window.Property(cinema_cta)]')
        self.assertEqual(play.findtext('texturefocus'),
                         '$INFO[Window.Property(cinema_cta_focus)]')
        foreground = rgb(play.findtext('textcolor'))
        self.assertGreaterEqual(contrast_ratio(foreground, (239, 231, 217)), 8)
        self.assertGreaterEqual(contrast_ratio(foreground, (255, 243, 218)), 8)

    def test_focus_is_unmistakable_but_does_not_cover_artwork(self):
        for ident in range(401, 414):
            focused = self.control(ident).find('focusedlayout')
            outlines = [image for image in focused.findall("control[@type='image']")
                        if image.findtext('texture') ==
                        '$INFO[Window.Property(cinema_focus)]']
            self.assertTrue(outlines, ident)
            self.assertTrue(all(image.findtext('visible') ==
                                'Control.HasFocus(%s)' % ident for image in outlines))
        for ident in (106, 101, 102, 103, 104, 105):
            tabs = [node for node in self.root.findall(".//control[@type='image']")
                    if node.findtext('visible') and
                    'Control.HasFocus(%s)' % ident in node.findtext('visible')
                    and node.findtext('top') == '87']
            self.assertEqual(len(tabs), 1, 'Missing refined tab focus %s' % ident)
            self.assertEqual(tabs[0].findtext('height'), '3')

    def test_hero_remains_above_shelves_and_preserves_plot(self):
        heading = [node for node in self.root.findall(".//control[@type='label']")
                   if node.findtext('label') ==
                   '$INFO[Window.Property(hero_title)]'][0]
        plot = [node for node in self.root.findall(".//control[@type='textbox']")
                if node.findtext('label') ==
                '$INFO[Window.Property(hero_plot)]'][0]
        shelves = self.control(610)
        self.assertLess(int(heading.findtext('top')), int(plot.findtext('top')))
        self.assertLess(int(plot.findtext('top')), int(shelves.findtext('top')))
        self.assertGreaterEqual(int(shelves.findtext('width')), 1770)

    def test_no_bright_red_or_purple_glows_in_skin(self):
        source = SKIN.read_text(encoding='utf-8')
        self.assertIn('KIVORA 0.39 / CINEMA', source)
        self.assertNotIn('FFE50914', source)
        self.assertIn('FFC9AA71', source)

    def test_24_genres_use_quiet_editorial_art(self):
        from tools.create_genre_icons import ART, background
        self.assertEqual(len(ART), 24)
        with background(0) as im:
            self.assertEqual(im.size, (320, 426))
            self.assertEqual(im.mode, 'RGBA')
            center = im.getpixel((160, 220))
            self.assertLess(max(center[:3]), 60)
        source = (ROOT / 'tools/create_genre_icons.py').read_text(encoding='utf-8')
        self.assertIn('BRASS=', source)
        self.assertNotIn('VIOLET=', source)

    def test_brand_is_retained_and_new_textures_are_versioned(self):
        brand = (ROOT / 'tools/create_brand.py').read_text(encoding='utf-8')
        self.assertIn('god_portrait', brand)
        textures = (PLUGIN / 'cinematic_home.py').read_text(encoding='utf-8')
        self.assertIn('stream_v10_', textures)
        self.assertIn('color = (201,170,113,255)', textures)
        metadata = ET.parse(PLUGIN / 'addon.xml').getroot()
        self.assertEqual(metadata.get('name'), 'KIVORA')
        self.assertEqual(metadata.get('version'), '0.39.0')


if __name__ == '__main__':
    unittest.main()
