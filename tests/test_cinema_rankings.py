# -*- coding: utf-8 -*-
"""Test all four ranked sections and the scrollable six-rail TV home."""
import os
import sys
import unittest
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_rankings import create_shelves,ranked_cards
from cinema_service_v2 import CinemaService


def rated(title,kind,year,rating,ident):
    file={'ident':ident,'name':title+'.1080p.mkv'}
    return {'raw':title,'title':title,'kind':kind,'year':year,
            'rating':rating,'ident':ident,'files':[file]}


class RankingTests(unittest.TestCase):
    def test_four_independent_ranked_sections(self):
        films=[rated('Starý film','movie','1994',95,'a'),
               rated('Letošní film','movie','2026',84,'b'),
               rated('Nehodnocený film','movie','2026',None,'c')]
        shows=[rated('Starý seriál','show','2008',94,'d'),
               rated('Letošní seriál','show','2026',88,'e')]
        result=create_shelves(films,shows,current_year=2026)
        self.assertEqual([x['title'] for x in result['best_movies_all']],
                         ['Starý film','Letošní film'])
        self.assertEqual([x['title'] for x in result['best_movies_year']],
                         ['Letošní film'])
        self.assertEqual([x['title'] for x in result['best_shows_all']],
                         ['Starý seriál','Letošní seriál'])
        self.assertEqual([x['title'] for x in result['best_shows_year']],
                         ['Letošní seriál'])
        self.assertEqual(result['ranking_year'],2026)

    def test_no_webshare_does_not_create_ranked_cards(self):
        ghost=rated('Neexistující film','movie','2026',100,'')
        self.assertEqual(ranked_cards([ghost],'movie',year=2026),[])
        ghost['ident']='any'
        ghost['files']=[]
        self.assertEqual(ranked_cards([ghost],'movie'),[])

    def test_exclude_unknown_rating_and_wrong_year(self):
        items=[rated('Nesprávný rok','movie','2025',99,'a'),
               rated('Neznámé skóre','movie','2026',None,'b'),
               rated('Skóre','movie','2026',82,'c')]
        self.assertEqual([c['raw'] for c in ranked_cards(items,'movie',2026)],
                         ['Skóre'])

    def test_dedupe_same_title_even_if_multiple_quality_files(self):
        cards=[rated('Stejný film','movie','2026',79,'a'),
               rated('STEJNY FILM','movie','2026',91,'b')]
        result=ranked_cards(cards,'movie',2026)
        self.assertEqual(len(result),1)

    def test_cache_migration_uses_current_year(self):
        home={'premieres':[],'movies':[rated('A','movie','2026',85,'a')],
              'shows':[rated('B','show','2026',90,'b')]}
        CinemaService._add_ranked_shelves(home)
        self.assertIn('best_movies_year',home)
        self.assertIn('best_shows_year',home)

class ScrollableSkinTests(unittest.TestCase):
    def test_seven_rows_in_scrollable_grouplist(self):
        path=os.path.join(PLUGIN,'resources','skins','Default','1080i',
                          'fckyo-cinema-v2.xml')
        root=ET.parse(path).getroot()
        container=root.find(".//control[@id='610']")
        self.assertIsNotNone(container)
        self.assertEqual(container.get('type'),'grouplist')
        self.assertEqual(container.findtext('orientation'),'vertical')
        ids={x.get('id') for x in container.findall('.//control')}
        self.assertTrue({str(x) for x in range(401,408)} <= ids)
        headings=[x.findtext('label') for x in container.findall(".//control[@type='label']")]
        self.assertTrue(all(any('row%d_heading'%i in (h or '') for h in headings)
                            for i in range(1,8)))

    def test_rankings_do_not_replace_main_tabs_or_gear(self):
        path=os.path.join(PLUGIN,'resources','skins','Default','1080i',
                          'fckyo-cinema-v2.xml')
        root=ET.parse(path).getroot()
        ids={x.get('id') for x in root.findall('.//control')}
        self.assertTrue({'101','102','103','104','107'} <= ids)
        self.assertIn('106',ids)

if __name__=='__main__':
    unittest.main()
