# -*- coding: utf-8 -*-
"""Contract tests for film->Webshare reconciliation and unified Kodi navigation."""
import os
import sys
import unittest
from datetime import date,timedelta
from xml.etree import ElementTree as ET

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
sys.path.insert(0,os.path.join(ROOT,'plugin.video.fckyo'))

from cinema_catalog_v2 import (groups,grouped_episodes,collect_pages,
                               matching_release,sort_cards,choose_files)
from cinema_service_v2 import CinemaService

def ws(ident,filename):
    return {'ident':ident,'name':filename,'size':'3500000000',
            'password':'0','available':'1'}

class Available:
    def check_groups(self,groups,max_workers=4):
        return [g for g in groups if g.get('files')]
    def check_files(self,files,limit=48):
        return files[:limit]

class CzechMetadata:
    def lookup(self,title,year=''):
        if title in ('Český příběh','Czech Story'):
            return {'title':'Český příběh', 'original':'Czech Story',
                    'poster':'https://example.org/czech-poster.jpg',
                    'fanart':'', 'year':'2025','rating':85,
                    'genres':['Drama'],'plot':'Česká anotace'}
        return None
    def lookup_many(self,groups,max_new=12):
        for g in groups[:max_new]:
            g['metadata']=self.lookup(g['title'])
    def save(self):pass

class Calendar:
    def __init__(self):
        self.events=[{'title':'Český příběh','original':'Czech Story',
          'premiere':(date.today()-timedelta(days=180)).isoformat()}]
    def load(self):return self.events

class ArtworkTests(unittest.TestCase):
    def test_matching_poster_must_come_from_same_title_and_year(self):
        from cinema_artwork import select_poster
        result=select_poster({'metas':[
            {'name':'Different Movie','releaseInfo':'2025',
             'poster':'https://example.org/wrong.jpg'},
            {'name':'Czech Story','releaseInfo':'2025',
             'poster':'https://example.org/correct.jpg'}]},
             'Czech Story','2025')
        self.assertEqual(result['poster'],'https://example.org/correct.jpg')
        self.assertIsNone(select_poster({'metas':[
            {'name':'Czech Story','releaseInfo':'2001',
             'poster':'https://example.org/wrong-year.jpg'}]},
             'Czech Story','2025'))

    def test_poster_fallback_does_not_create_films(self):
        from cinema_artwork import Artwork
        class Response:
            def raise_for_status(self):pass
            def json(self):
                return {'metas':[{'name':'Czech Story','releaseInfo':'2025',
                         'poster':'https://example.org/correct.jpg'}]}
        art=Artwork(transport=lambda url,timeout:Response())
        self.assertEqual(art.lookup('Czech Story','2025')['poster'],
                         'https://example.org/correct.jpg')
        # No video cards are created just by this artwork lookup.


class DataLayer(unittest.TestCase):
    def test_czech_word_at_start_is_title_not_language_marker(self):
        from novinky_catalogue import parse_video_name
        p=parse_video_name('Czech.Story.2025.1080p.CZ.mkv')
        self.assertEqual(p['title'],'Czech Story')
        self.assertEqual(p['year'],'2025')

    def test_series_merges_cross_year_results(self):
        files=[ws('a','Some.Show.S01E01.2024.1080p.mkv'),
               ws('b','Some.Show.S03E12.2026.720p.CZ.mkv')]
        result=groups(files,'show')
        self.assertEqual(len(result),1)

    def test_series_season_and_episode_order(self):
        files=[ws('z','My.Show.S03E11.1080p.mkv'),
               ws('b','My.Show.S01E02.720p.mkv'),
               ws('c','My.Show.S01E01.1080p.mkv'),
               ws('d','My.Show.S01E01.2160p.mkv'),
               ws('a','My.Show.S02E02.1080p.mkv')]
        organized=grouped_episodes(files,'My Show')
        self.assertEqual(list(organized),[1,2,3])
        self.assertEqual(list(organized[1]),[1,2])
        self.assertEqual(len(organized[1][1]),2)
        self.assertEqual(organized[1][1][0]['ident'],'d')

    def test_paged_series_does_not_stop_at_first_100(self):
        calls=[]
        def fetch(token,offset,what,sort='recent'):
            calls.append(offset)
            if offset==0:
                return [ws(str(n),'My.Show.S01E%02d.1080p.mkv'%((n%50)+1))
                        for n in range(100)],250
            if offset==100:
                return [ws(str(n),'My.Show.S02E%02d.1080p.mkv'%((n%50)+1))
                        for n in range(100,200)],250
            return [ws(str(n),'My.Show.S03E%02d.1080p.mkv'%((n%50)+1))
                    for n in range(200,250)],250
        result=collect_pages(fetch,'test','My Show',max_pages=20)
        self.assertEqual(calls,[0,100,200])
        self.assertEqual(len(result),250)
        ordered=grouped_episodes(result,'My Show')
        self.assertEqual(list(ordered),[1,2,3])

    def test_matching_filters_wrong_movie_and_series(self):
        sample=[ws('a','Czech.Story.2025.1080p.mkv'),
                ws('b','Czech.Story.S01E01.1080p.mkv'),
                ws('c','Unrelated.Movie.2025.1080p.mkv')]
        matches=matching_release(sample,['Czech Story'],year='2025')
        self.assertEqual([x['ident'] for x in matches],['a'])

    def test_czech_catalog_seed_only_if_webshare_exists(self):
        def fetch(token,offset,title,sort='recent'):
            if title=='Czech Story':
                return [ws('id-1','Czech.Story.2025.1080p.CZ.mkv')],1
            return [],0
        service=CinemaService('token',fetch,Available(),CzechMetadata(),Calendar())
        cards=service._premieres()
        self.assertEqual(len(cards),1)
        self.assertEqual(cards[0]['title'],'Český příběh')
        self.assertIn('poster.jpg',cards[0]['poster'])
        self.assertEqual(cards[0]['ident'],'id-1')

    def test_csfd_without_webshare_creates_no_card(self):
        service=CinemaService('token',lambda *args,**kwargs:([],0),
                              Available(),CzechMetadata(),Calendar())
        self.assertEqual(service._premieres(),[])

    def test_search_matching_original_and_czech_title(self):
        def fetch(token,offset,title,sort='recent'):
            if title=='Czech Story':
                return [ws('web','Czech.Story.2025.1080p.mkv')],1
            return [],0
        service=CinemaService('token',fetch,Available(),CzechMetadata())
        results=service.search('Český příběh')
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['title'],'Český příběh')
        self.assertEqual(results[0]['kind'],'movie')

    def test_selection_keeps_only_matching_cz_quality(self):
        entries=[ws('a','Mystery.Film.2025.1080p.CZ.mkv'),
                 ws('b','Mystery.Film.2025.2160p.MULTi.mkv')]
        self.assertEqual(len(choose_files(entries,quality='4k',language='cz')),0)
        self.assertEqual(len(choose_files(entries,quality='all',language='cz')),1)

    def test_sort_rating_vs_alphabetically(self):
        a={'title':'Z', 'rating':80, 'files':[], 'year':'2020'}
        b={'title':'A', 'rating':70, 'files':[], 'year':'2026'}
        self.assertEqual(sort_cards([a,b],'title')[0]['title'],'A')
        self.assertEqual(sort_cards([a,b],'rating')[0]['title'],'Z')

class WindowContracts(unittest.TestCase):
    def test_v2_window_is_valid_and_has_both_rails(self):
        path=os.path.join(ROOT,'plugin.video.fckyo','resources','skins',
                          'Default','1080i','fckyo-cinema-v2.xml')
        tree=ET.parse(path).getroot()
        ids={e.attrib.get('id') for e in tree.findall('.//control')}
        self.assertTrue({'401','402','101','102','103','104','107'}<=ids)
        self.assertIn('105',ids)  # New native genre tab
        self.assertTrue({'106','201','202','203','204','205','206','207'}<=ids)
        gear=tree.find(".//control[@id='107']")
        self.assertGreaterEqual(int(gear.findtext('left')),1700)
        self.assertEqual(gear.findtext('onleft'),'109')
        with open(path,encoding='utf8') as xml:
            content=xml.read()
        self.assertIn('app_version',content)
        self.assertIn('hero_art',content)
        self.assertIn('String.IsEmpty',content)

    def test_all_details_stay_in_one_window(self):
        path=os.path.join(ROOT,'plugin.video.fckyo','cinema_screen_v2.py')
        with open(path,encoding='utf8') as f:
            s=f.read()
        for route in ("'movies'","'shows'","'search'","'seasons'",
                      "'episodes'","'files'"):
            self.assertIn(route,s)
        self.assertIn('self._go_back()',s)
        self.assertIn("action='play'",s)
        self.assertIn('self._gear_menu()',s)
        self.assertIn('self.addon.openSettings()',s)
        self.assertNotIn("command=='classic'",s)

if __name__=='__main__':
    unittest.main()
