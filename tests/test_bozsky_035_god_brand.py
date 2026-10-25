# -*- coding: utf-8 -*-
"""The Božský přehrávač rebrand changes only names and original god artwork."""
from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree as ET
from PIL import Image

ROOT=Path(__file__).resolve().parent.parent
PLUGIN=ROOT/'plugin.video.fckyo'


class DivineBrandingTests(unittest.TestCase):
    def test_chosen_kodi_name_and_permanent_technical_id(self):
        root=ET.parse(PLUGIN/'addon.xml').getroot()
        self.assertEqual(root.get('name'),'Božský přehrávač')
        self.assertEqual(root.get('version'),'0.35.0')
        self.assertEqual(root.get('id'),'plugin.video.fckyo')
        self.assertEqual(root.findtext(".//summary"),
                         'Božský přehrávač – filmy a seriály v Kodi')

    def test_generated_god_emblem_and_wordmark_are_not_empty(self):
        import sys
        sys.path.insert(0,str(ROOT))
        from tools import create_brand
        with tempfile.TemporaryDirectory() as temp:
            original=create_brand.MEDIA
            create_brand.MEDIA=Path(temp)
            try:
                brand,icon=create_brand.make_brand()
                self.assertTrue(brand.exists())
                self.assertTrue(icon.exists())
                with Image.open(brand) as image:
                    self.assertEqual(image.size,(1150,275))
                    self.assertEqual(image.mode,'RGBA')
                    self.assertIsNotNone(image.getbbox())
                with Image.open(icon) as image:
                    self.assertEqual(image.size,(512,512))
                    self.assertNotEqual(image.getpixel((256,175)),
                                        image.getpixel((0,0)))
                self.assertTrue((Path(temp)/'icons'/'home.png').exists())
            finally:
                create_brand.MEDIA=original

    def test_repository_name_matches_and_ids_are_unchanged(self):
        script=(ROOT/'build_repo.py').read_text(encoding='utf8')
        self.assertIn("REPO_ID='repository.bozskyprehravac'",script)
        self.assertIn("PLUGIN_ID='plugin.video.fckyo'",script)
        self.assertIn("REPO_NAME='Božský přehrávač – repozitář'",script)
        self.assertIn('Božský přehrávač',script)

    def test_real_navigation_and_bluey_preserved(self):
        skin=ET.parse(PLUGIN/'resources'/'skins'/'Default'/
                      '1080i'/'fckyo-cinema-v2.xml').getroot()
        self.assertIsNotNone(skin.find(".//control[@id='109']"))
        self.assertIsNotNone(skin.find(".//control[@id='108']"))
        self.assertIsNotNone(skin.find(".//control[@id='110']"))
        skin_images=skin.findall(".//control[@type='image']")
        self.assertEqual(len([item for item in skin_images if item.findtext(
          'texture')=='$INFO[Window.Property(cinema_brand)]']),1)


if __name__=='__main__':
    unittest.main()
