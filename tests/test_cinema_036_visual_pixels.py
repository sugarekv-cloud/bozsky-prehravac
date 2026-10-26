# -*- coding: utf-8 -*-
"""Pixel, spacing and focus audit for the *actual* Kodi skin configuration.

Tests validate real generated texture pixels with Pillow and declarative XML.
They are not screenshots from a running Kodi/Android TV installation.
"""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from xml.etree import ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugin.video.fckyo'
SKIN = PLUGIN / 'resources/skins/Default/1080i/fckyo-cinema-v2.xml'
NAV_IDS = (106, 101, 102, 103, 104, 105, 109, 107)
HORIZONTAL = (401, 402, 405, 406, 407, 409, 410)
VERTICAL = (403, 404, 408, 411, 412, 413)


class CinemaRenderedAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ET.parse(SKIN).getroot()
        # xbmcgui is provided by Kodi on TV; a stub is enough for texture generation.
        if 'xbmcgui' not in sys.modules:
            sys.modules['xbmcgui'] = types.ModuleType('xbmcgui')
        if not hasattr(sys.modules['xbmcgui'], 'WindowXMLDialog'):
            sys.modules['xbmcgui'].WindowXMLDialog = type('WindowXMLDialog', (), {})
        sys.path.insert(0, str(PLUGIN))
        cls._temp = tempfile.TemporaryDirectory()
        home = importlib.import_module('cinematic_home')
        cls.paths = home.ensure_textures(cls._temp.name)

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def sample(self, name, x, y):
        with Image.open(self.paths[name]) as im:
            return im.convert('RGBA').getpixel((x, y))

    def test_generated_png_textures_are_readable_and_correctly_sized(self):
        expected = {'background': (128, 72), 'fade': (256, 72),
                    'focus': (2, 2), 'cta': (2, 2), 'cta_focus': (2, 2),
                    'button': (2, 2), 'nav_hover': (2, 2),
                    'cardfade': (128, 84), 'tile': (128, 72)}
        for key, size in expected.items():
            with self.subTest(texture=key), Image.open(self.paths[key]) as im:
                self.assertEqual(im.size, size)
                self.assertEqual(im.mode, 'RGBA')
                im.verify()

    def test_red_focus_and_play_buttons_have_distinct_pixels(self):
        self.assertEqual(self.sample('focus', 0, 0), (229, 9, 20, 255))
        self.assertEqual(self.sample('cta', 0, 0), (215, 13, 25, 255))
        self.assertEqual(self.sample('cta_focus', 0, 0), (245, 28, 43, 255))
        self.assertNotEqual(self.sample('button', 0, 0),
                            self.sample('cta', 0, 0))

    def test_artwork_fade_preserves_hero_readability(self):
        top_left = self.sample('fade', 0, 0)
        top_right = self.sample('fade', 255, 0)
        bottom_right = self.sample('fade', 255, 71)
        self.assertGreater(top_left[3], 230)
        self.assertLess(top_right[3], 60)
        self.assertGreater(bottom_right[3], 245)

    def test_title_gradient_is_semitransparent_over_artwork(self):
        top = self.sample('cardfade', 60, 0)
        bottom = self.sample('cardfade', 60, 83)
        self.assertLess(top[3], 12)
        self.assertGreater(bottom[3], 235)

    def test_movie_card_tile_has_transparent_corners_and_solid_center(self):
        self.assertLess(self.sample('tile', 0, 0)[3], 10)
        center = self.sample('tile', 64, 35)
        self.assertEqual(center[3], 255)
        self.assertLess(max(center[:3]), 40)

    def test_background_and_secondary_navigation_are_dark(self):
        for name, x, y in [('background', 25, 30), ('nav_hover', 0, 0)]:
            pix = self.sample(name, x, y)
            self.assertLess(max(pix[:3]), 55)
            self.assertGreater(pix[3], 220)

    def test_main_navigation_positions_do_not_overlap(self):
        controls = []
        for cid in NAV_IDS:
            c = self.root.find(".//control[@id='%s']" % cid)
            self.assertIsNotNone(c)
            left, top, width, height = (int(c.findtext(n)) for n in
                                        ('left','top','width','height'))
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            self.assertGreaterEqual(left, 0)
            self.assertGreaterEqual(top, 0)
            self.assertLessEqual(left+width, 1920)
            self.assertLessEqual(top+height, 1080)
            controls.append((cid, left, top, width, height))
        for i, a in enumerate(controls):
            for b in controls[i+1:]:
                x_overlap = max(a[1], b[1]) < min(a[1]+a[3], b[1]+b[3])
                y_overlap = max(a[2], b[2]) < min(a[2]+a[4], b[2]+b[4])
                self.assertFalse(x_overlap and y_overlap,
                                 'Overlapping navigation: %s and %s' % (a[0],b[0]))

    def test_all_rail_card_geometry_fits_1920_wide_screen(self):
        for cid in HORIZONTAL + VERTICAL:
            row = self.root.find(".//control[@id='%s']" % cid)
            for tag in ('itemlayout', 'focusedlayout'):
                item = row.find(tag)
                cw, ch = int(item.get('width')), int(item.get('height'))
                self.assertGreaterEqual(cw, 170)
                self.assertGreaterEqual(ch, 190)
                for c in item.findall('control'):
                    left = c.findtext('left')
                    top = c.findtext('top')
                    width = c.findtext('width')
                    height = c.findtext('height')
                    if not all((left, top, width, height)):
                        continue
                    try:
                        x, y, w, h = map(int, (left, top, width, height))
                    except ValueError:
                        continue
                    self.assertGreater(w, 0, (cid,tag,'width'))
                    self.assertGreater(h, 0, (cid,tag,'height'))
                    self.assertGreaterEqual(x, 0, (cid,tag,'left'))
                    self.assertGreaterEqual(y, 0, (cid,tag,'top'))
                    # Focus borders may deliberately spill by up to 6px.
                    self.assertLessEqual(x+w, cw+6, (cid,tag,'x overflow'))
                    self.assertLessEqual(y+h, ch+6, (cid,tag,'y overflow'))

    def test_kodi_window_geometry_and_version_label(self):
        window = self.root
        self.assertEqual(window.findtext('defaultcontrol'), '401')
        self.assertEqual(window.findtext('coordinates/system'), '1')
        for name in ('hero_title', 'hero_info', 'hero_plot', 'app_version'):
            prop = 'Window.Property(%s)' % name
            self.assertTrue(any(prop in (c.findtext('label') or '')
                                for c in self.root.findall('.//control')),
                            'Missing user-visible %s property' % name)

    def test_poster_fallback_is_hidden_while_true_fanart_exists(self):
        backdrop = self.root.find(".//control[@type='image'][texture='$INFO[Window.Property(hero_art)]']")
        poster = self.root.find(".//control[@type='image'][texture='$INFO[Window.Property(hero_poster)]']")
        self.assertIn('!String.IsEmpty(Window.Property(hero_art))', backdrop.findtext('visible'))
        self.assertIn('String.IsEmpty(Window.Property(hero_art))', poster.findtext('visible'))

if __name__ == '__main__':
    unittest.main()
