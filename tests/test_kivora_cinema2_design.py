# -*- coding: utf-8 -*-
"""KIVORA Cinema 2.0 UI contract checks; no Kodi runtime necessary."""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT/'plugin.video.fckyo/resources/skins/Default/1080i/fckyo-cinema-v2.xml'
DETAIL=ROOT/'plugin.video.fckyo/resources/skins/Default/1080i/fckyo-detail-v1.xml'
SCREEN=ROOT/'plugin.video.fckyo/cinema_screen_v2.py'
DETAIL_MODULE=ROOT/'plugin.video.fckyo/cinema_details.py'

class Cinema2DesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skin=ET.parse(SKIN).getroot()
        cls.detail=ET.parse(DETAIL).getroot()

    def test_hero_has_remote_actions_and_no_invisible_tv_trailer(self):
        for ident in ('108','110','112','113'):
            self.assertIsNotNone(self.skin.find(".//control[@id='%s']"%ident))
        for ident in ('112','113'):
            button=self.skin.find(".//control[@id='%s']"%ident)
            self.assertEqual(button.findtext('visible'),
                             'String.IsEqual(Window.Property(hero_media_action),yes)')
            self.assertIsNotNone(button.find('onright'))
            self.assertIsNotNone(button.find('onleft'))
        code=SCREEN.read_text(encoding='utf-8')
        self.assertIn("if control_id==112:",code)
        self.assertIn("if control_id==113:",code)
        self.assertIn("self._set_hero_property('hero_media_action','')",code)
        self.assertIn("self._set_hero_property('hero_media_action','yes')",code)

    def test_year_and_quality_are_in_every_card_at_same_baseline(self):
        for ident in range(401,414):
            list_control=self.skin.find(".//control[@id='%s']"%ident)
            self.assertIsNotNone(list_control)
            for kind in ('itemlayout','focusedlayout'):
                layout=list_control.find(kind)
                year=[x for x in layout.findall("control[@type='label']")
                      if x.findtext('label')=='$INFO[ListItem.Property(year)]']
                quality=[x for x in layout.findall("control[@type='label']")
                         if x.findtext('label')=='$INFO[ListItem.Property(quality)]']
                self.assertEqual(len(year),1,(ident,kind,'year'))
                self.assertEqual(len(quality),1,(ident,kind,'quality'))
                self.assertEqual(year[0].findtext('top'),quality[0].findtext('top'))
                self.assertLessEqual(int(quality[0].findtext('top'))+
                                     int(quality[0].findtext('height')),
                                     int(layout.get('height')))

    def test_fullscreen_detail_has_content_and_navigation(self):
        ids={c.get('id') for c in self.detail.findall(".//control[@type='button']")}
        self.assertTrue({'301','302','303','304'}.issubset(ids))
        text=DETAIL.read_text(encoding='utf-8')
        self.assertIn('detail_plot',text)
        self.assertIn('detail_poster',text)
        self.assertIn('detail_meta',text)
        self.assertNotIn('PlayMedia(',DETAIL_MODULE.read_text(encoding='utf-8'))
        self.assertIn("choose_detail(self.addon,self.textures",SCREEN.read_text(encoding='utf-8'))

    def test_header_and_hero_fit_1080p_screen(self):
        text=SKIN.read_text(encoding='utf-8')
        self.assertIn('premium',text.lower() if 'premium' in text.lower() else
                      'KIVORA CINEMA 2.0: premium')
        for i in (112,113):
            item=self.skin.find(".//control[@id='%d']"%i)
            self.assertLessEqual(int(item.findtext('left'))+
                                 int(item.findtext('width')),1920)
            self.assertLessEqual(int(item.findtext('top'))+
                                 int(item.findtext('height')),1080)

if __name__=='__main__':
    unittest.main()
