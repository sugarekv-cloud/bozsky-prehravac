# -*- coding: utf-8 -*-
"""KIVORA v0.24 rebrand, sidebar icons, recommendations and deeper search."""
import os
import sys
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)

from cinema_search_v3 import cached_title_aliases, query_plan


class KivoraSearchTests(unittest.TestCase):
    def test_czech_title_search_finds_saved_original_title(self):
        verified={'_all_movies':[
            {'kind':'movie','title':'Zelená míle','raw':'The Green Mile',
             'original':'The Green Mile','ident':'file-id',
             'files':[{'ident':'file-id','name':'The.Green.Mile.1999.mkv'}]}
        ]}
        aliases=cached_title_aliases('Zelená míle',verified)
        self.assertIn('The Green Mile',aliases)
        self.assertIn('The Green Mile',query_plan('Zelená míle',limit=5))

    def test_no_unrelated_cached_aliases_are_mixed_in(self):
        home={'_all_movies':[
            {'kind':'movie','title':'Titanic','raw':'Titanic',
             'original':'Titanic','ident':'a','files':[{'ident':'a'}]},
            {'kind':'movie','title':'The Green Mile','raw':'The Green Mile',
             'original':'The Green Mile','ident':'b','files':[{'ident':'b'}]}
        ]}
        self.assertEqual(cached_title_aliases('Avengers',home),[])

    def test_real_webshare_results_still_required(self):
        with open(os.path.join(PLUGIN,'cinema_service_v2.py'),encoding='utf8') as f:
            source=f.read()
        self.assertIn('cached_title_aliases(title,self.home_fast())',source)
        self.assertIn('verified_groups(candidates,self.availability',source)
        self.assertIn('max_pages=4 if index==0',source)

    def test_discovery_is_larger_not_unbounded(self):
        from cinema_service_v2 import CinemaService
        self.assertEqual(CinemaService._discover_hits.__defaults__,(18,10))


class KivoraDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skin=ET.parse(os.path.join(PLUGIN,'resources','skins','Default','1080i',
                                       'fckyo-cinema-v2.xml')).getroot()
        cls.addon=ET.parse(os.path.join(PLUGIN,'addon.xml')).getroot()
        with open(os.path.join(PLUGIN,'cinema_screen_v2.py'),encoding='utf8') as f:
            cls.screen=f.read()
        with open(os.path.join(ROOT,'tools','create_brand.py'),encoding='utf8') as f:
            cls.brand=f.read()

    def test_upgrade_preserves_kodi_technical_identifier(self):
        self.assertEqual(self.addon.get('id'),'plugin.video.fckyo')
        self.assertEqual(self.addon.get('name'),'KIVORA')
        self.assertEqual(self.addon.get('version'),'0.27.0')

    def test_all_sidebar_entries_have_graphic_icon_files(self):
        for cid in range(201,209):
            self.assertIsNotNone(self.skin.find(".//control[@id='%d']"%cid))
            image=[node for node in self.skin.findall(".//control[@type='image']")
                   if node.findtext('texture')==
                      '$INFO[Window.Property(side_icon_%d)]'%cid]
            self.assertEqual(len(image),1)
        self.assertIn('make_menu_icons()',self.brand)
        self.assertIn('win.icon_paths=',self.screen)
        self.assertIn("208:'recommendations'",self.screen)

    def test_tips_have_dedicated_side_entry_and_home_shelf(self):
        self.assertIn("elif view=='recommendations':",self.screen)
        self.assertIn("'TIPY NA SLEDOVÁNÍ',personal",self.screen)
        self.assertIn('TIPY NA TENTO TÝDEN',self.screen)

    def test_home_and_category_shelves_are_not_webshare_popularity_rankings(self):
        home_start=self.screen.index("        if view=='home':")
        home_end=self.screen.index("        elif view=='recommendations':",home_start)
        home=self.screen[home_start:home_end]
        self.assertNotIn('POPULÁRNÍ NA WEBSHARE',home)
        self.assertNotIn('NEJSLEDOVANĚJŠÍ NA WEBSHARE',home)
        self.assertIn('NEJLÉPE HODNOCENÉ FILMY · ČSFD',home)
        self.assertIn('TIPY NA SLEDOVÁNÍ',home)
        self.assertIn('OBJEVIT DALŠÍ FILMY',self.screen)
        self.assertIn('PROCHÁZET SERIÁLY',self.screen)

    def test_previous_repo_install_path_is_preserved(self):
        with open(os.path.join(ROOT,'build_repo.py'),encoding='utf8') as f:
            build=f.read()
        self.assertIn("REPO_ID='repository.bozskyprehravac'",build)
        self.assertIn("PLUGIN_ID='plugin.video.fckyo'",build)
        self.assertIn("REPO_NAME='KIVORA repozitář'",build)


if __name__=='__main__':
    unittest.main()
