# -*- coding: utf-8 -*-
"""KIVORA 0.39 Cinema: verify the actual TV geometry and contextual navigation."""
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
SKIN=ROOT/'plugin.video.fckyo/resources/skins/Default/1080i/fckyo-cinema-v2.xml'
BRAND=ROOT/'tools/create_brand.py'
ADDON=ROOT/'plugin.video.fckyo/addon.xml'


class Cinema039LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ET.parse(SKIN).getroot()

    def image(self,texture):
        nodes=[node for node in self.root.findall(".//control[@type='image']")
               if node.findtext('texture')=='$INFO[Window.Property(%s)]'%texture]
        self.assertEqual(len(nodes),1,texture)
        return nodes[0]

    def control(self,ident):
        node=self.root.find(".//control[@id='%s']"%ident)
        self.assertIsNotNone(node,ident)
        return node

    def test_hero_and_shelves_do_not_intersect_vertically(self):
        hero=self.image('hero_art')
        fade=self.image('cinema_fade')
        shelf=self.control(610)
        shelf_top=int(shelf.findtext('top'))
        for image in (hero,fade):
            end=int(image.findtext('top'))+int(image.findtext('height'))
            self.assertLess(end,shelf_top)
        self.assertLessEqual(shelf_top,545)
        self.assertGreaterEqual(int(shelf.findtext('height')),500)

    def test_feature_story_and_actions_are_separated(self):
        title=self.image('cinema_brand')
        self.assertLessEqual(int(title.findtext('height')),70)
        controls=self.root.findall(".//control[@type='label']")
        hero=[c for c in controls if c.findtext('label')==
              '$INFO[Window.Property(hero_title)]'][0]
        description=[c for c in self.root.findall(".//control[@type='textbox']")
                     if c.findtext('label')==
                     '$INFO[Window.Property(hero_plot)]'][0]
        play=self.control(108)
        detail=self.control(110)
        self.assertLess(int(hero.findtext('top')),int(description.findtext('top')))
        self.assertLess(int(description.findtext('top'))+
                        int(description.findtext('height')),int(play.findtext('top')))
        self.assertEqual(play.findtext('top'),detail.findtext('top'))
        self.assertLess(int(play.findtext('top'))+int(play.findtext('height')),
                        int(self.control(610).findtext('top')))

    def test_secondary_navigation_only_draws_when_focused(self):
        sidebar=[self.control(cid) for cid in range(201,209)]
        self.assertTrue(all(x.get('type')=='button' for x in sidebar))
        images=[x for x in self.root.findall(".//control[@type='image']")
                if 'side_icon_' in (x.findtext('texture') or '')]
        self.assertEqual(len(images),8)
        for image in images:
            visible=image.findtext('visible')
            for cid in range(201,209):
                self.assertIn('Control.HasFocus(%s)'%cid,visible)
        # Navigation is always keyboard/remote reachable, even when icons are hidden.
        self.assertEqual(self.control(401).findtext('onleft'),'201')
        self.assertEqual(self.control(201).findtext('onright'),'401')

    def test_masthead_preserves_identity_and_balances_title(self):
        code=BRAND.read_text(encoding='utf-8')
        self.assertIn('god_portrait(410)',code)
        self.assertIn("d.text((186,30),'KIVORA'",code)
        self.assertIn("god.resize((136,136)",code)
        addon=ET.parse(ADDON).getroot()
        self.assertEqual(addon.get('id'),'plugin.video.fckyo')
        self.assertEqual(addon.get('name'),'KIVORA')
        self.assertEqual(addon.get('version'),'0.43.1')

    def test_remote_and_artwork_controls_remain_compatible(self):
        for cid in (101,102,103,104,105,106,107,108,109,110):
            self.assertEqual(self.control(cid).get('type'),'button')
        for cid in range(401,414):
            row=self.control(cid)
            self.assertEqual(row.get('type'),'list')
            for layout in ('itemlayout','focusedlayout'):
                self.assertIsNotNone(row.find(layout))
            self.assertIsNotNone(row.find('onup'))
            self.assertIsNotNone(row.find('ondown'))
            self.assertTrue(row.findtext('onleft'))
        self.assertEqual(self.control(109).findtext('label'),'BLUEY')


if __name__=='__main__':
    unittest.main()
