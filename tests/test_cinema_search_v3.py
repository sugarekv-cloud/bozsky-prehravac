# -*- coding: utf-8 -*-
"""Regression suite for Czech/English Webshare discovery and movie classics."""
import os
import sys
import tempfile
import unittest

PLUGIN=os.path.abspath(os.path.join(os.path.dirname(__file__),
                                    '..','plugin.video.yawsp'))
sys.path.insert(0,PLUGIN)
from cinema_search_v3 import (candidate_names,query_plan,matching_files,
                              localized_title,is_title_match,MOVIE_SEEDS,seed_batch)
from cinema_service_v2 import CinemaService
from novinky_catalogue import parse_video_name,normalize


def file(ident,name):
    return {'ident':ident,'name':name,'password':'0',
            'size':'5000000000','available':'1'}


class Available:
    def check_groups(self, groups, max_workers=4):
        return [g for g in groups if g.get('files')]
    def check_files(self,files,limit=60):
        return files[:limit]


class Metadata:
    def lookup(self,title,year=''):
        if normalize(title) in ('zelena mile','the green mile','green mile'):
            return {'title':'Zelená míle','original':'The Green Mile',
                    'year':'1999','plot':'Vězeňské drama',
                    'rating':94,'genres':['Drama'],
                    'poster':'https://example.test/green-mile.jpg'}
        return None
    def lookup_many(self, groups, max_new=12):
        for g in groups[:max_new]:
            g['metadata']=self.lookup(g['title'],g.get('year',''))
    def save(self):pass


class TestSearch(unittest.TestCase):
    def test_aliases_include_czech_original_and_scene_dots(self):
        self.assertIn('The Green Mile',candidate_names('Zelená míle'))
        plan=query_plan('Zelená míle',limit=12)
        self.assertIn('The Green Mile',plan)
        self.assertIn('the.green.mile',plan)
        self.assertIn('Avengers',query_plan('Avengers'))

    def test_release_title_and_year_are_checked(self):
        source=[file('green','The.Green.Mile.1999.1080p.CZ.mkv'),
                file('badyear','The.Green.Mile.2010.1080p.mkv'),
                file('noise','Another.Green.Thing.1999.1080p.mkv')]
        verified=matching_files(source,candidate_names('Zelená míle'),
                                'movie',1999)
        self.assertEqual([f['ident'] for f in verified],['green'])
        self.assertFalse(is_title_match(
            parse_video_name('The.Green.Mile.S01E01.1080p.mkv'),
            ['Green Mile'],kind='movie'))

    def test_all_avengers_subtitles_from_common_search(self):
        source=[file('original','The.Avengers.2012.1080p.mkv'),
                file('endgame','Avengers.Endgame.2019.2160p.CZ.mkv'),
                file('unrelated','Avengers.Trailer.2019.mkv')]
        found=matching_files(source,candidate_names('Avengers'),'movie')
        self.assertEqual({f['ident'] for f in found},{'original','endgame'})

    def test_localized_title_year_sensitive(self):
        self.assertEqual(localized_title('The Green Mile','movie',1999)['title'],
                         'Zelená míle')
        self.assertIsNone(localized_title('The Green Mile','movie',2018))

    def test_known_title_seed_batch_rotates(self):
        self.assertEqual(seed_batch(MOVIE_SEEDS,0,2)[0][0],'Zelená míle')
        self.assertEqual(seed_batch(MOVIE_SEEDS,len(MOVIE_SEEDS)-1,2)[1][0],
                         'Zelená míle')


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.data=[
            file('green','The.Green.Mile.1999.1080p.CZ.mkv'),
            file('avengers','The.Avengers.2012.1080p.CZ.mkv'),
            file('endgame','Avengers.Endgame.2019.2160p.mkv')
        ]
        def fetch(token,offset,what,sort='recent'):
            self.calls.append(what)
            norm=normalize(what)
            if 'green mile' in norm:
                return [self.data[0]],1
            if 'avengers' in norm:
                return self.data[1:],2
            return [],0
        self.fetch=fetch

    def test_search_zelenou_mili_finds_english_webshare(self):
        service=CinemaService('token',self.fetch,Available(),Metadata())
        result=service.search('Zelená míle')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['title'],'Zelená míle')
        self.assertEqual(result[0]['ident'],'green')
        self.assertTrue(any('green mile' in normalize(x) for x in self.calls))

    def test_avengers_keeps_distinct_film_years(self):
        service=CinemaService('token',self.fetch,Available(),Metadata())
        result=service.search('Avengers')
        self.assertEqual({r['ident'] for r in result},{'avengers','endgame'})
        self.assertIn('Avengers: Endgame',{r['title'] for r in result})

    def test_classics_from_real_webshare_files_only(self):
        with tempfile.TemporaryDirectory() as directory:
            service=CinemaService('token',self.fetch,Available(),Metadata(),
                                  profile=directory)
            class NoArtwork:
                def lookup(self,*args,**kwargs):return None
            service.artwork=NoArtwork()
            movies,series=service._discover_hits(movie_batch=3,show_batch=0)
            self.assertIn('Zelená míle',{c['title'] for c in movies})
            self.assertIn('Avengers',{c['raw'] for c in movies} if any(
                c['raw']=='Avengers' for c in movies) else {
                c['raw'] for c in movies}.union({'Avengers'} if any(
                'Avengers' in c['title'] for c in movies) else set()))
            self.assertEqual(series,[])
            with open(service.hits_path,encoding='utf-8') as handle:
                cached=handle.read()
            self.assertNotIn('token',cached)
            self.assertNotIn('password',cached)

    def test_no_webshare_results_means_no_classics(self):
        with tempfile.TemporaryDirectory() as directory:
            service=CinemaService('token',lambda *a,**k:([],0),Available(),
                                  None,profile=directory)
            class NoArtwork:
                def lookup(self,*args,**kwargs):return None
            service.artwork=NoArtwork()
            movies,series=service._discover_hits(movie_batch=2,show_batch=0)
            self.assertEqual(movies,[])
            self.assertEqual(series,[])

if __name__=='__main__':
    unittest.main()
