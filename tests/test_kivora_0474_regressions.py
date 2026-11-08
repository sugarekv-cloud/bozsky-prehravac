"""Behavior and geometry regressions for the TV layout and cached results."""
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin.video.fckyo'))
from cinema_content_filter import safe_card, safe_file, filter_cards
from cinema_catalog_v2 import grouped_episodes, card
from cinema_search_v3 import matching_files
from cinema_service_v2 import CinemaService

class FilterAndSeriesTests(unittest.TestCase):
    def test_all_search_and_file_surfaces_use_same_filter(self):
        good={'ident':'ok','name':'Bluey.S01E01.CZ.mkv'}
        for fields in ({'adult':True},{'adult':'yes'},{'is_adult':'true'},
                       {'category':'adult'},{'name':'Bluey.S01E01.Pornhub.mkv'}):
            bad=dict(good,ident='bad');bad.update(fields)
            with self.subTest(fields=fields):
                self.assertFalse(safe_file(bad))
                self.assertEqual(matching_files([bad,good],['Bluey'],'show'),[good])
                rows=CinemaService.__new__(CinemaService).file_rows([bad,good])
                self.assertEqual([r['ident'] for r in rows],['ok'])
                result=filter_cards([{'title':'Bluey','files':[bad,good],'ident':'bad'}])
                self.assertEqual(result[0]['ident'],'ok')

    def test_adult_metadata_survives_card_conversion(self):
        f={'ident':'a','name':'Title.2025.mkv'}
        for metadata in ({'adult':True},{'is_adult':True},{'genres':['Adult']}):
            c=card({'title':'Title','kind':'movie','best':f,'files':[f],
                    'metadata':metadata})
            self.assertFalse(safe_card(c))

    def test_legitimate_titles_and_synopses_remain(self):
        self.assertTrue(safe_card({'title':'Sex Education','plot':'A story about pornography.'}))
        self.assertFalse(safe_card({'title':'Film','genre':'Drama / Adult'}))
        self.assertFalse(safe_file({'name':'Pornografický.film.mkv'}))

    def test_duplicate_seeds_do_not_inflate_episode_versions(self):
        one={'ident':'a','name':'Bluey.S02E10.1080p.mkv'}
        other={'ident':'b','name':'Bluey.S02E02.720p.mkv'}
        wrong={'ident':'c','name':'Other.S02E01.mkv'}
        result=grouped_episodes([one,other,dict(one),wrong],'Bluey')
        self.assertEqual(list(result[2]),[2,10])
        self.assertEqual(len(result[2][10]),1)

class LayoutBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=ET.parse(ROOT/'plugin.video.fckyo/resources/skins/Default/1080i/fckyo-cinema-v2.xml').getroot()

    def test_header_has_safe_margin_and_nonintersecting_buttons(self):
        right=0
        for ident in (106,101,102,103,104,105,109,111,107):
            c=self.root.find(".//control[@id='%s']"%ident)
            x,y,w,h=[int(c.findtext(k)) for k in ('left','top','width','height')]
            self.assertGreaterEqual(y,48)
            self.assertLessEqual(y+h,112)
            self.assertGreaterEqual(x,right)
            self.assertLessEqual(x+w,1872)
            right=x+w

    def test_title_year_quality_have_separate_rectangles(self):
        for ident in range(401,414):
            row=self.root.find(".//control[@id='%s']"%ident)
            for kind in ('itemlayout','focusedlayout'):
                layout=row.find(kind)
                labels=layout.findall("control[@type='label']")
                title=next(c for c in labels if c.find('scroll') is not None)
                year=next(c for c in labels if c.findtext('label')=='$INFO[ListItem.Property(year)]')
                quality=next(c for c in labels if c.findtext('label')=='$INFO[ListItem.Property(quality)]')
                self.assertLessEqual(int(title.findtext('top'))+int(title.findtext('height')),int(year.findtext('top')))
                self.assertLessEqual(int(year.findtext('left'))+int(year.findtext('width')),int(quality.findtext('left')))

    def test_hint_does_not_overlap_hero_buttons(self):
        hint=next(c for c in self.root.findall('./controls/control') if (c.findtext('label') or '').startswith('OK  VÝBĚR'))
        for ident in (108,110,112,113):
            c=self.root.find(".//control[@id='%s']"%ident)
            self.assertLessEqual(int(c.findtext('left'))+int(c.findtext('width')),int(hint.findtext('left')))

class SeriesNavigationTests(unittest.TestCase):
    def screen(self):
        import types
        from unittest.mock import Mock
        for module in ('xbmc','xbmcgui'):
            if module not in sys.modules:
                sys.modules[module]=types.ModuleType(module)
        if not hasattr(sys.modules['xbmcgui'],'WindowXMLDialog'):
            sys.modules['xbmcgui'].WindowXMLDialog=type('WindowXMLDialog',(),{})
        from cinema_screen_v2 import CinemaScreen
        win=CinemaScreen.__new__(CinemaScreen)
        win.setProperty=Mock()
        win._fill=Mock()
        win._loading=Mock(return_value=Mock())
        win.service=Mock(token='test')
        win.quality=win.language='all'
        return win

    def test_episode_and_season_keep_show_art_and_description(self):
        win=self.screen()
        show={'kind':'show','title':'Bluey','raw':'Bluey','year':2018,
              'poster':'poster.jpg','fanart':'fanart.jpg','genre':'Animovaný'}
        win.service.seasons.return_value={2:{10:[{'ident':'10'}],2:[{'ident':'2'}]}}
        win._screen('seasons',show)
        season=win._fill.call_args.args[1][0]
        self.assertEqual(season['poster'],'poster.jpg')
        win._screen('episodes',(show,2))
        episodes=win._fill.call_args.args[1]
        self.assertEqual([c['episode'] for c in episodes],[2,10])
        self.assertEqual(episodes[0]['fanart'],'fanart.jpg')
        self.assertEqual(episodes[0]['year'],'')
        win.service._cached_description.return_value='Český popis.'
        self.assertEqual(win._csfd_description(episodes[0]),'Český popis.')
        win.service._cached_description.assert_called_with('Bluey',2018,'show','')

    def test_episode_file_selection_keeps_series_tab_active(self):
        win=self.screen()
        win.service.episode_variants.return_value=[]
        win.service.file_rows.return_value=[]
        win._screen('files',({'kind':'show','title':'Bluey'},2,10))
        win.setProperty.assert_any_call('nav_active','shows')
        win.service.episode_variants.assert_called_once_with(
            {'kind':'show','title':'Bluey'},2,10,'all','all')
