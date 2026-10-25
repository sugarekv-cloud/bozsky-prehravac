# -*- coding: utf-8 -*-
"""Verify 24 illustrated genres are truly wired into Kodi and offline ZIP."""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent.parent
PLUGIN=ROOT/'plugin.video.fckyo'
sys.path.insert(0,str(PLUGIN))
from cinema_genres import GENRES,GENRE_ICON_SLUGS,genre_icon_path
from tools import create_genre_icons


class GenreArtworkTests(unittest.TestCase):
    def test_all_czech_genres_have_individual_offline_png_paths(self):
        self.assertEqual(len(GENRES),24)
        self.assertEqual(set(GENRE_ICON_SLUGS),set(GENRES))
        self.assertEqual(len(set(GENRE_ICON_SLUGS.values())),24)
        for name in GENRES:
            path=genre_icon_path('/kivora',name)
            self.assertTrue(path.endswith('.png'))
            self.assertIn('genre_icons',path)
            self.assertFalse(path.startswith('https://'))

    def test_generator_has_unique_art_for_every_genre(self):
        self.assertEqual(set(create_genre_icons.ART),set(GENRE_ICON_SLUGS.values()))
        with tempfile.TemporaryDirectory() as tmp:
            saved=create_genre_icons.DEST
            original=create_genre_icons.ART
            create_genre_icons.DEST=Path(tmp)
            create_genre_icons.ART={
                'comedy':'happy','horror':'skull','scifi':'planet'}
            try:
                paths=create_genre_icons.make_genre_icons()
            finally:
                create_genre_icons.DEST=saved
                create_genre_icons.ART=original
            self.assertEqual(len(paths),3)
            for path in paths:
                with Image.open(path) as image:
                    self.assertEqual(image.format,'PNG')
                    self.assertEqual(image.size,(320,426))
                    self.assertEqual(image.mode,'RGBA')
                    self.assertGreater(path.stat().st_size,3000)

    def test_kodi_genres_screen_renders_tap_and_remote_openable_posters(self):
        if 'xbmcgui' not in sys.modules:
            gui=types.ModuleType('xbmcgui')
            gui.WindowXMLDialog=type('WindowXMLDialog',(),{})
            sys.modules['xbmcgui']=gui
        if 'xbmc' not in sys.modules:
            sys.modules['xbmc']=types.ModuleType('xbmc')
        from cinema_screen_v2 import CinemaScreen
        win=CinemaScreen.__new__(CinemaScreen)
        win.addon=types.SimpleNamespace(
            getAddonInfo=lambda name:'/tmp/kivora-addon')
        win.setProperty=lambda *a:None
        displays=[]
        win._fill=lambda *args,**kwargs:displays.append(args)
        win._screen('genres')
        self.assertEqual(len(displays),1)
        first,first_cards,second,second_cards,status=displays[0]
        self.assertIn('ŽÁNR',first)
        self.assertEqual(len(first_cards),12)
        self.assertEqual(len(second_cards),12)
        all_cards=first_cards+second_cards
        self.assertEqual([c['title'] for c in all_cards],list(GENRES))
        self.assertTrue(all(c['kind']=='genre_open'
                            and c['poster'].endswith('.png')
                            and c['genre_name']==c['title'] for c in all_cards))

    def test_installer_generates_art_before_zipping_addon(self):
        script=(ROOT/'build_repo.py').read_text(encoding='utf8')
        self.assertIn('from tools.create_genre_icons import make_genre_icons',script)
        self.assertIn('genre_art=make_genre_icons()',script)
        self.assertLess(script.index('genre_art=make_genre_icons()'),
                        script.index('zip_folder(plugin,plugin_file)'))


if __name__=='__main__':
    unittest.main()
