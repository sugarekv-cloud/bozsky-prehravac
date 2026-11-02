# -*- coding: utf-8 -*-
"""Regression for actual 2026-11-02 Android TV screenshot and Netflix library."""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
XML=ROOT/'plugin.video.fckyo/resources/skins/Default/1080i/fckyo-cinema-v2.xml'
SCREEN=ROOT/'plugin.video.fckyo/cinema_screen_v2.py'

class ScreenshotLibraryRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ET.parse(XML).getroot()

    def test_three_rows_have_room_in_1080p_catalogue(self):
        shelf=self.root.find(".//control[@id='610']")
        self.assertIsNotNone(shelf)
        self.assertGreaterEqual(int(shelf.findtext('height')),855)
        anims=shelf.findall('animation')
        self.assertTrue(any('layout_mode' in (a.get('condition') or '') and
                            '-392' in (a.get('end') or '') for a in anims))
        groups=[c for c in shelf if c.get('type')=='group']
        self.assertEqual(len(groups),13)
        height=int(groups[0].findtext('height'))
        gap=int(shelf.findtext('itemgap'))
        self.assertLessEqual(height*3+gap*2,int(shelf.findtext('height')))

    def test_no_title_or_metadata_collides_with_next_shelf(self):
        for ident in range(401,414):
            rail=self.root.find(".//control[@id='%s']"%ident)
            self.assertEqual(int(rail.findtext('height')),220)
            for mode in ('itemlayout','focusedlayout'):
                lay=rail.find(mode)
                self.assertEqual((int(lay.get('width')),int(lay.get('height'))),(292,218))
                labels={x.findtext('label'):x for x in lay.findall("control[@type='label']")
                        if x.findtext('label') in (
                            '$INFO[ListItem.Property(year)]',
                            '$INFO[ListItem.Property(quality)]')}
                self.assertEqual(len(labels),2)
                title=[x for x in lay.findall("control[@type='label']")
                       if x.findtext('label')=='$INFO[ListItem.Label]' and x.findtext('top')=='169']
                self.assertEqual(len(title),1)
                self.assertLess(int(title[0].findtext('top'))+int(title[0].findtext('height')),
                                int(labels['$INFO[ListItem.Property(year)]'].findtext('top'))+1)
                for x in labels.values():
                    self.assertLessEqual(int(x.findtext('top'))+int(x.findtext('height')),
                                         int(lay.get('height')))
                for image in lay.findall("control[@type='image']"):
                    if image.findtext('texture') in ('$INFO[ListItem.Art(poster)]',
                                                     '$INFO[ListItem.Art(fanart)]'):
                        self.assertEqual(image.findtext('aspectratio'),'scale')
                        self.assertEqual(image.findtext('width'),'286')

    def test_no_unverified_quality_strings_or_nested_long_details(self):
        code=SCREEN.read_text(encoding='utf-8')
        self.assertIn('quality_badge(c.get(\'quality\'))',code)
        self.assertIn("'layout_mode','browse' if browse else 'hero'",code)
        self.assertIn("'shows':'SERIÁLY'",code)
        overlay=self.root.find(".//control[@type='image'][visible='String.IsEqual(Window.Property(layout_mode),browse)']")
        self.assertIsNotNone(overlay, 'Browse mode should hide old movie hero')
        self.assertIn("browse_title",ET.tostring(self.root,encoding='unicode'))

if __name__=='__main__':
    unittest.main()
