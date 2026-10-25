# -*- coding: utf-8 -*-
"""Visual-only Netflix-inspired 0.31 refresh, without regressing Kodi controls."""
import os
import sys
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)


class NetflixPosterLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default',
            '1080i','fckyo-cinema-v2.xml')).getroot()
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as f:
            cls.screen=f.read()

    def test_thirteen_rows_support_landscape_and_portrait_cards(self):
        portrait={403,404,408,411,412,413}
        for id in range(401,414):
            rail=self.skin.find(".//control[@id='%d']"%id)
            self.assertIsNotNone(rail)
            self.assertEqual(rail.get('type'),'list')
            self.assertEqual(rail.findtext('orientation'),'horizontal')
            self.assertGreaterEqual(int(rail.findtext('width')),1560)
            for form in ('itemlayout','focusedlayout'):
                tile=rail.find(form)
                w,h=int(tile.get('width')),int(tile.get('height'))
                self.assertEqual((w,h),(239,354) if id in portrait else (359,259))
                posters=[x for x in tile.findall("control[@type='image']")
                         if x.findtext('texture')=='$INFO[ListItem.Art(poster)]']
                self.assertEqual(len(posters),1)
                self.assertEqual(posters[0].findtext('aspectratio'),'keep')
            self.assertGreater(1610 / int(rail.find('itemlayout').get('width')),4)

    def test_focus_is_never_drawn_on_nonfocused_cards(self):
        for id in range(401,414):
            control=self.skin.find(".//control[@id='%d']"%id)
            focused=control.find('focusedlayout')
            outlines=[x for x in focused.findall("control[@type='image']")
                      if x.findtext('texture')==
                         '$INFO[Window.Property(cinema_focus)]']
            self.assertGreaterEqual(len(outlines),1)
            self.assertTrue(all(x.findtext('visible')=='Control.HasFocus(%d)'%id
                                for x in outlines))
            self.assertEqual(control.findall('ondown')[-1].text,str(id))

    def test_rating_and_resume_bar_remain_visible_on_poster(self):
        for id in range(401,414):
            control=self.skin.find(".//control[@id='%d']"%id)
            for form in ('itemlayout','focusedlayout'):
                layout=control.find(form)
                self.assertEqual(len(layout.findall("control[@type='progress']")),1)
                self.assertIn('ListItem.Property(rating_label)',
                              ET.tostring(layout,encoding='unicode'))
                self.assertIn('ListItem.Label',
                              ET.tostring(layout,encoding='unicode'))

    def test_full_bleed_banner_has_vignette_and_original_poster_fallback(self):
        photos=self.skin.findall(".//control[@type='image']")
        get=lambda prop:[c for c in photos if c.findtext('texture')==
                 '$INFO[Window.Property(%s)]'%prop]
        banner=get('hero_art');fade=get('cinema_fade');poster=get('hero_poster')
        self.assertEqual(len(banner),1)
        self.assertEqual(len(fade),1)
        self.assertEqual(len(poster),1)
        self.assertGreaterEqual(int(banner[0].findtext('width')),1100)
        self.assertGreaterEqual(int(banner[0].findtext('height')),400)
        self.assertEqual(poster[0].findtext('aspectratio'),'scale')

    def test_section_tabs_and_sidebar_ids_are_all_preserved(self):
        import cinema_screen_v2
        required={106:'home',101:'movies',102:'shows',103:'search',
                  104:'premieres',105:'genres',109:'bluey',107:'settings',
                  201:'home',208:'recommendations'}
        for cid,view in required.items():
            self.assertEqual(cinema_screen_v2.TOP_ACTIONS[cid],view)
            self.assertIsNotNone(self.skin.find(".//control[@id='%d']"%cid))
        self.assertIn("('TIPY NA SLEDOVÁNÍ',personal)",self.screen)
        self.assertIn("elif view=='recommendations':",self.screen)

    def test_dark_look_is_new_versioned_texture(self):
        with open(os.path.join(PLUGIN,'cinematic_home.py'),encoding='utf8') as f:
            code=f.read()
        self.assertIn('stream_v7_',code)
        self.assertIn('int(7+3*h)',code)
        self.assertIn('int(17+6*top',code)


if __name__=='__main__':
    unittest.main()
