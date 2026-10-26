# -*- coding: utf-8 -*-
"""Visual layout regressions for the KIVORA 0.34 cinematic TV redesign."""
import os
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
XML=os.path.join(PLUGIN,'resources','skins','Default','1080i','fckyo-cinema-v2.xml')

class FullScreenStreamingUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ET.parse(XML).getroot()
        cls.all_images=cls.root.findall(".//control[@type='image']")

    def images(self,texture):
        return [x for x in self.all_images if x.findtext('texture')==
                '$INFO[Window.Property(%s)]'%texture]

    def test_hero_backdrop_covers_tv_and_only_one_poster_fallback(self):
        art=self.images('hero_art')
        poster=self.images('hero_poster')
        scrim=self.images('cinema_fade')
        self.assertEqual(len(art),1)
        self.assertEqual(len(poster),1)
        self.assertEqual(len(scrim),1)
        self.assertGreaterEqual(int(art[0].findtext('width')),1500)
        self.assertGreaterEqual(int(poster[0].findtext('width')),1000)
        self.assertGreaterEqual(int(scrim[0].findtext('width')),1800)
        self.assertEqual(poster[0].findtext('aspectratio'),'scale')
        self.assertIn('String.IsEmpty(Window.Property(hero_art))',
                      poster[0].findtext('visible'))
        controls=list(self.root.find('controls'))
        self.assertLess(controls.index(art[0]),controls.index(scrim[0]))
        self.assertLess(controls.index(poster[0]),controls.index(scrim[0]))

    def test_icon_only_sidebar_gives_space_back_to_movie_rows(self):
        for cid in (201,202,203,204,205,206,207,208):
            ctrl=self.root.find(".//control[@id='%d']"%cid)
            self.assertEqual(ctrl.get('type'),'button')
            self.assertLessEqual(int(ctrl.findtext('width')),75)
            self.assertTrue(ctrl.findtext('description'))
            self.assertEqual(ctrl.findtext('label').strip(),'')
        rail=self.root.find(".//control[@id='610']")
        self.assertLessEqual(int(rail.findtext('left')),120)
        self.assertGreaterEqual(int(rail.findtext('width')),1770)
        self.assertGreaterEqual(int(rail.findtext('height')),430)

    def test_flyout_sidebar_tooltips_only_for_focused_icon(self):
        for cid in (201,202,203,204,205,206,207,208):
            found=[x for x in self.root.findall(".//control[@type='label']")
                   if x.findtext('visible')=='Control.HasFocus(%d)'%cid
                   and int(x.findtext('left') or 0)>=90]
            self.assertTrue(found,'No floating label for %s'%cid)

    def test_wide_artwork_rows_have_natural_poster_fallback_and_gradient(self):
        portrait={403,404,408,411,412,413}
        for cid in range(401,414):
            rail=self.root.find(".//control[@id='%d']"%cid)
            self.assertGreaterEqual(int(rail.findtext('width')),1750)
            for slot in ('itemlayout','focusedlayout'):
                lay=rail.find(slot)
                posters=[img for img in lay.findall("control[@type='image']")
                         if img.findtext('texture')=='$INFO[ListItem.Art(poster)]']
                self.assertGreaterEqual(len(posters),1)
                self.assertTrue(any(img.findtext('aspectratio')=='keep' for img in posters))
                if cid not in portrait:
                    self.assertTrue(any(img.findtext('texture')==
                         '$INFO[Window.Property(cinema_cardfade)]'
                         for img in lay.findall("control[@type='image']")))
                    self.assertGreater(int(lay.get('width')),int(lay.get('height')))
                else:
                    self.assertGreater(int(lay.get('height')),int(lay.get('width')))
                self.assertIsNotNone(lay.find("control[@type='progress']"))

    def test_top_navigation_and_play_detail_stay_clickable(self):
        for cid in (106,101,102,103,104,105,109,107,108,110):
            ctrl=self.root.find(".//control[@id='%d']"%cid)
            self.assertIsNotNone(ctrl)
            self.assertEqual(ctrl.get('type'),'button')
        self.assertEqual(self.root.find(".//control[@id='109']").findtext('label'),'BLUEY')
        self.assertIn('PŘEHRÁT',self.root.find(".//control[@id='108']").findtext('label'))
        self.assertIn('DETAIL',self.root.find(".//control[@id='110']").findtext('label'))

    def test_no_double_top_focus_indicator(self):
        duplicated=[x for x in self.all_images
                    if x.findtext('top')=='19'
                    and x.findtext('height')=='3']
        self.assertFalse(duplicated)

    def test_release_uses_fresh_gradients_and_real_metadata(self):
        addon=ET.parse(os.path.join(PLUGIN,'addon.xml')).getroot()
        self.assertEqual(addon.get('version'),'0.36.0')
        with open(os.path.join(PLUGIN,'cinematic_home.py'),encoding='utf8') as f:
            generator=f.read()
        self.assertIn('stream_v9_',generator)
        self.assertIn("kind == 'cardfade'",generator)
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as f:
            logic=f.read()
        self.assertIn('if rating>0:',logic)
        self.assertIn("VERSION='0.36.0'",logic)


if __name__=='__main__':
    unittest.main()
