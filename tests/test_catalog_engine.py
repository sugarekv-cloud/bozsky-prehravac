# -*- coding: utf-8 -*-
"""Regression tests based on public Webshare filenames and scene naming conventions."""
import os
import sys
import unittest

sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..',
                                               'plugin.video.fckyo')))
from catalog_engine import (release_details, file_label, file_score,
                            filter_groups, sort_groups, sort_files, prefers_cz)
from novinky_catalogue import (parse_video_name, resolution, is_czech_audio_marked,
                              czech_language_tier, sort_variants, variant_label)
from smartsearch import variants

def file(i,name,gb=3):
    return {'ident':i,'name':name,'size':str(int(gb*1024**3))}

def group(title,year,files,meta=None):
    return {'title':title,'year':year,'files':files,
            'best':files[0], 'metadata':meta}

class FilenameTests(unittest.TestCase):
    def test_actual_webshare_cz_dabing(self):
        name='Murder Mystery (2019) CZ dabing ,WEB-DL,1080p,H264.DD5.1,.mkv'
        p=parse_video_name(name)
        self.assertEqual((p['title'],p['year'],p['kind']),
                         ('Murder Mystery','2019','movie'))
        d=release_details(name)
        self.assertEqual(d['resolution'],1080)
        self.assertEqual(d['source'],'WEB-DL')
        self.assertEqual(d['language'],'CZ dabing (název)')

    def test_actual_webshare_anime_episodic(self):
        name='Shingeki no Kyojin - 60 CZ [1080p].mkv'
        p=parse_video_name(name)
        self.assertEqual((p['kind'],p['season'],p['episode']),
                         ('episode',1,60))
        self.assertEqual(p['title'],'Shingeki no Kyojin')

    def test_4k_remastered_can_be_1080p(self):
        name='The Wolfman (2010) 4K Remastered Unrated DC 1080p 10bit Bluray x265 HEVC.mkv'
        self.assertEqual(release_details(name)['resolution'],1080)
        self.assertEqual(resolution(name),1080)

    def test_subtitles_are_not_dubbing(self):
        self.assertFalse(is_czech_audio_marked('Film.2025.CZSUB.1080p.mkv'))
        self.assertFalse(is_czech_audio_marked('Film.2025.MULTi.2160p.mkv'))
        self.assertFalse(prefers_cz(file('1','Film.2025.CZ.titulky.1080p.mkv')))
        self.assertTrue(prefers_cz(file('2','Film.2025.CZ.Dabing.1080p.mkv')))

    def test_cz_language_tiers_and_file_labels(self):
        fixtures={
            'Movie.2025.CZDAB.1080p.mkv':3,
            'Movie.2025.CZ.Dabing.1080p.mkv':3,
            'Movie.2025.Czech.Audio.1080p.mkv':3,
            'Movie.2025.CZSUB.CZ.Dabing.1080p.mkv':3,
            'Movie.2025.CZ.2160p.mkv':2,
            'Movie.2025.CZE.1080p.mkv':2,
            'Movie.2025.CZSUB.2160p.mkv':1,
            'Movie.2025.CZ.Subs.2160p.mkv':1,
            'Movie.2025.CZ.Titulky.2160p.mkv':1,
            'Movie.2025.Czech.Subtitles.2160p.mkv':1,
            'Movie.2025.EN.2160p.mkv':0,
            'Movie.2025.MULTi.2160p.mkv':0,
        }
        for name,tier in fixtures.items():
            with self.subTest(filename=name):
                self.assertEqual(czech_language_tier(name),tier)
                self.assertEqual(release_details(name)['audio_priority'],tier)
                self.assertEqual(is_czech_audio_marked(name),tier>=2)
        self.assertIn('CZ titulky',file_label(file('s','Movie.CZSUB.2160p.mkv')))
        self.assertIn('CZ titulky',variant_label(file('s','Movie.CZSUB.2160p.mkv')))
        self.assertIn('CZ dabing',variant_label(file('d','Movie.CZ.Dabing.1080p.mkv')))

    def test_dots_in_query(self):
        self.assertIn('murder.mystery',variants('Murder Mystery'))
        self.assertIn('Český název',variants('Český název'))

    def test_language_tags_and_codes(self):
        name='Film.2025.2160p.WEB-DL.HDR10.HEVC.CZ.mkv'
        d=release_details(name)
        self.assertEqual((d['resolution'],d['source'],d['codec']),
                         (2160,'WEB-DL','HEVC'))
        self.assertIn('CZ',file_label(file('1',name)))

class SortingTests(unittest.TestCase):
    def setUp(self):
        self.a=file('1','Film.2025.720p.CZ.mkv',2)
        self.b=file('2','Film.2025.2160p.WEB-DL.HEVC.mkv',14)
        self.c=file('3','Film.2025.1080p.CZ.Dabing.BluRay.mkv',9)

    def test_czech_dubbing_precedes_higher_resolution_foreign_release(self):
        ordered=sort_files([self.a,self.b,self.c])
        self.assertEqual([f['ident'] for f in ordered],['3','1','2'])
        self.assertGreater(file_score(self.c),file_score(self.b))

    def test_best_czech_quality_first_then_fallback_to_non_czech(self):
        fourth=file('4','Film.2025.2160p.CZ.WEB-DL.mkv',18)
        subtitles=file('5','Film.2025.2160p.CZSUB.WEB-DL.mkv',22)
        ordered=sort_files([subtitles,self.b,self.a,self.c,fourth])
        self.assertEqual(ordered[0]['ident'],'3')
        self.assertEqual([f['ident'] for f in ordered],['3','4','1','5','2'])
        self.assertFalse(prefers_cz(subtitles))

    def test_dubbing_first_then_cz_audio_subtitles_and_other(self):
        files=[
            file('foreign','Movie.2025.EN.2160p.mkv'),
            file('subs','Movie.2025.CZSUB.2160p.mkv'),
            file('probable','Movie.2025.CZ.2160p.mkv'),
            file('dub','Movie.2025.CZ.Dabing.1080p.mkv'),
            file('dub4k','Movie.2025.CZDAB.2160p.mkv'),
        ]
        expected=['dub4k','dub','probable','subs','foreign']
        self.assertEqual([f['ident'] for f in sort_files(files)],expected)
        self.assertEqual([f['ident'] for f in sort_variants(files)],expected)

    def test_filter_quality_and_cz(self):
        groups=[group('Film','2025',[self.a,self.b,self.c])]
        self.assertEqual(len(filter_groups(groups,'4k','cz')),0)
        self.assertEqual(len(filter_groups(groups,'1080','cz')),1)
        self.assertEqual(len(filter_groups(groups,'4k','all')),1)

    def test_year_and_rating_sort(self):
        g1=group('Starší','2020',[self.a],{'rating':90})
        g2=group('Novější','2026',[self.b],{'rating':60})
        self.assertEqual(sort_groups([g1,g2],'year')[0]['title'],'Novější')
        self.assertEqual(sort_groups([g1,g2],'rating')[0]['title'],'Starší')
        self.assertEqual(sort_groups([g2,g1],'title')[0]['title'],'Novější')

if __name__=='__main__':
    unittest.main()
