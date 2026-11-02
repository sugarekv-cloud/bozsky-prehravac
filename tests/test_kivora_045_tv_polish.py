# -*- coding: utf-8 -*-
"""KIVORA 0.45: TV screenshots, visible years/focus, safe movies/shows."""
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin.video.fckyo'))
from cinema_content_filter import safe_card,safe_file,filter_cards
from cinema_catalog_v2 import acceptable
from cinema_service_v2 import CinemaService

SKIN=ROOT/'plugin.video.fckyo/resources/skins/Default/1080i/fckyo-cinema-v2.xml'


def mkfile(ident,name,**kwargs):
    return dict({'ident':ident,'name':name,'available':'1','password':'0'},**kwargs)


class ContentSafetyTests(unittest.TestCase):
    def test_explicit_filename_excluded_even_without_adult_flag(self):
        for suffix in ('XXX','porn','porno','OnlyFans','hentai','hardcore',
                       'sexvideo','erotica','gangbang'):
            with self.subTest(name=suffix):
                self.assertFalse(safe_file(mkfile('x','Bluey.S01E01.%s.mkv'%suffix)))
                self.assertFalse(acceptable(mkfile('x','Bluey.S01E01.%s.mkv'%suffix)))

    def test_webshare_adult_flag_and_metadata_adult_genre(self):
        self.assertFalse(safe_file(mkfile('x','Film.2025.mkv',adult='1')))
        self.assertFalse(safe_card({'kind':'show','title':'Show','genres':['Adult']}))
        self.assertFalse(safe_card({'kind':'movie','title':'Movie',
                                   'genre':'Drama, Erotický'}))

    def test_no_false_positives_for_mainstream_films(self):
        for name in ('Sex Education','American Pie','The Sex Lives of College Girls',
                     'The 40 Year Old Virgin','Bluey'):
            with self.subTest(name=name):
                self.assertTrue(safe_card({'title':name,'kind':'show'}))
        self.assertTrue(safe_file(mkfile('x','Sex.Education.S01E01.1080p.CZ.mkv')))

    def test_keeps_safe_release_and_eliminates_bad_variant(self):
        card={'title':'Film','kind':'movie','ident':'bad',
              'files':[mkfile('bad','Film.2025.XXX.mkv'),
                       mkfile('good','Film.2025.CZ.Dabing.mkv')]}
        out=filter_cards([card])
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]['ident'],'good')
        self.assertEqual([f['ident'] for f in out[0]['files']],['good'])
        self.assertEqual(card['ident'],'bad')
        self.assertEqual(len(card['files']),2)

    def test_filter_behaves_identically_for_movies_and_shows(self):
        for kind in ('movie','show'):
            cards=[{'title':'My Porno Show','kind':kind},
                   {'title':'Normal Movie','kind':kind,'files':[
                       mkfile('f','Normal.Movie.2025.1080p.mkv')]}]
            self.assertEqual(len(filter_cards(cards)),1)


class TvPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ET.parse(SKIN).getroot()

    def test_hero_has_useful_caption_and_no_redundant_choice_banner(self):
        text=SKIN.read_text(encoding='utf-8')
        self.assertNotIn('VÝBĚR KIVORA    /    DOPORUČUJEME',text)
        self.assertIn('ČESKÝ ZVUK PŘEDNOSTNĚ',text)

    def test_every_shelf_focus_overlay_is_above_art(self):
        for row_id in range(401,414):
            row=self.root.find(".//control[@id='%s']"%row_id)
            self.assertIsNotNone(row)
            focussed=row.find('focusedlayout')
            images=focussed.findall("control[@type='image']")
            highlights=[x for x in images if x.findtext('texture') ==
                        '$INFO[Window.Property(cinema_focus)]' and
                        x.findtext('height')=='3']
            self.assertTrue(highlights,row_id)
            self.assertEqual(highlights[-1].findtext('visible'),
                             'Control.HasFocus(%s)'%row_id)

    def test_years_fit_within_card_layouts_and_are_high_contrast(self):
        for row_id in range(401,414):
            row=self.root.find(".//control[@id='%s']"%row_id)
            for kind in ('itemlayout','focusedlayout'):
                item=row.find(kind)
                self.assertIsNotNone(item)
                year_labels=[node for node in item.findall("control[@type='label']")
                            if node.findtext('label') == '$INFO[ListItem.Property(year)]']
                self.assertEqual(len(year_labels),1,(row_id,kind))
                year=year_labels[0]
                self.assertLessEqual(int(year.findtext('top'))+
                                     int(year.findtext('height')),
                                     int(item.get('height')))
                self.assertNotIn('hide_caption',year.findtext('visible'))
                self.assertEqual(year.findtext('textcolor'),'FFCED2CF')

    def test_all_shelves_hide_unneeded_tip_captions(self):
        for row_id in range(401,414):
            row=self.root.find(".//control[@id='%s']"%row_id)
            item=row.find('itemlayout')
            labels=item.findall("control[@type='label']")
            self.assertTrue(any(x.findtext('label')=='$INFO[ListItem.Label]' and
                        x.findtext('top')=='169' for x in labels),row_id)

    def test_brand_generator_has_new_monogram(self):
        source=(ROOT/'tools/create_brand.py').read_text(encoding='utf-8')
        self.assertIn("d.text((240,17),'KIVORA'",source)
        self.assertIn("d.rounded_rectangle((26,38,196,208)",source)
        self.assertIn('god_portrait(410)',source)

    def test_taller_rail_viewport_to_reduce_clipping(self):
        shelf=self.root.find(".//control[@id='610']")
        self.assertGreaterEqual(int(shelf.findtext('height')),538)


if __name__=='__main__':
    unittest.main()
