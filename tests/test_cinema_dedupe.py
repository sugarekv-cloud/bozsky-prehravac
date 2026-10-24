# -*- coding: utf-8 -*-
"""Regression tests for one poster per title and all original Webshare links."""
import os
import sys
import unittest

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
sys.path.insert(0,os.path.join(ROOT,'plugin.video.yawsp'))
from cinema_dedupe import consolidate, identity, unify_sections, unique_home_rails
from cinema_service_v2 import CinemaService
from cinema_catalog_v2 import grouped_episodes

def ws(ident,name):
    return {'ident':ident,'name':name,'size':'5500000000','available':'1'}

def card(name,year,ident,filename,kind='movie',title=None,original=None,rating=91):
    return {'kind':kind,'raw':name,'title':title or name,'original':original or '',
        'year':str(year or ''),'file_year':str(year or ''),'rating':rating,
        'rating_source':'ČSFD','ident':ident,'files':[ws(ident,filename)],
        'poster':'https://example.org/poster.png'}


class MergeTests(unittest.TestCase):
    def test_three_quality_versions_one_card(self):
        movies=[
            card('The Green Mile',1999,'a','The.Green.Mile.1999.720p.mkv',
                 title='Zelená míle',original='The Green Mile'),
            card('The Green Mile',1999,'b','The.Green.Mile.1999.1080p.CZ.mkv',
                 title='Zelená míle',original='The Green Mile'),
            card('Zelená míle',1999,'c','Zelena.Mile.1999.2160p.CZ.mkv')]
        result=consolidate(movies)
        self.assertEqual(len(result),1)
        self.assertEqual({f['ident'] for f in result[0]['files']},{'a','b','c'})
        self.assertEqual(result[0]['ident'],'c')
        self.assertIn('4K',result[0]['quality'])
        self.assertEqual(result[0]['title'],'Zelená míle')

    def test_shawshank_czech_original_merge(self):
        movies=[
            card('The Shawshank Redemption',1994,'e',
                 'The.Shawshank.Redemption.1994.1080p.mkv',
                 title='Vykoupení z věznice Shawshank',
                 original='The Shawshank Redemption'),
            card('Vykoupení z věznice Shawshank',1994,'f',
                 'Vykoupeni.z.veznice.Shawshank.1994.720p.mkv')]
        self.assertEqual(len(consolidate(movies)),1)

    def test_missing_year_only_attaches_if_unique_year(self):
        known=card('The Green Mile',1999,'a','The.Green.Mile.1999.1080p.mkv')
        unknown=card('The Green Mile',None,'b','The.Green.Mile.720p.mkv')
        result=consolidate([unknown,known])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['year'],'1999')
        self.assertEqual(len(result[0]['files']),2)

    def test_same_named_remake_is_not_merged(self):
        original=card('Dune',1984,'a','Dune.1984.1080p.mkv')
        remake=card('Dune',2021,'b','Dune.2021.2160p.mkv')
        unknown=card('Dune',None,'c','Dune.1080p.mkv')
        result=consolidate([original,remake,unknown])
        self.assertEqual(len(result),3)

    def test_series_episodes_are_grouped_but_remain_individual(self):
        files=[
            card('Breaking Bad',2008,'a','Breaking.Bad.S01E01.1080p.mkv',
                 kind='show',title='Perníkový táta',original='Breaking Bad'),
            card('Perníkový táta',2008,'b','Pernikovy.Tata.S01E02.720p.mkv',
                 kind='show',title='Perníkový táta',original='Breaking Bad')]
        result=consolidate(files)
        self.assertEqual(len(result),1)
        self.assertEqual(len(result[0]['files']),2)
        episodes=grouped_episodes(result[0]['files'],'Breaking Bad',
                                  aliases=tuple(result[0]['aliases']))
        self.assertEqual(list(episodes[1]),[1,2])

    def test_unverified_or_empty_cards_do_not_create_posters(self):
        no_files=card('Ghost',2020,'x','Ghost.2020.mkv')
        no_files['files']=[]
        self.assertEqual(consolidate([no_files]),[])


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.movie1=card('The Green Mile',1999,'a',
                         'The.Green.Mile.1999.720p.mkv',
                         title='Zelená míle',original='The Green Mile')
        self.movie2=card('Zelená míle',1999,'b',
                         'Zelena.Mile.1999.2160p.CZ.mkv')
        self.shaw=card('The Shawshank Redemption',1994,'c',
                       'The.Shawshank.Redemption.1994.1080p.mkv',
                       title='Vykoupení z věznice Shawshank',
                       original='The Shawshank Redemption')
        self.show=card('Breaking Bad',2008,'d',
                       'Breaking.Bad.S01E01.1080p.mkv',kind='show')

    def test_same_movie_not_repeated_across_any_home_rail(self):
        home={
            'premieres':[], 'movies':[self.movie1,self.shaw],
            'shows':[self.show],'classics':[self.movie2,self.shaw,self.movie1],
            'classic_shows':[self.show]}
        CinemaService._add_ranked_shelves(home)
        sections=('premieres','movies','shows','classics','classic_shows',
                  'best_movies_all','best_movies_year','best_shows_all','best_shows_year')
        seen=[]
        for section in sections:
            seen.extend(identity(c) for c in home.get(section,[]))
        self.assertEqual(len(seen),len(set(seen)))
        self.assertEqual(len(home['_all_movies']),2)
        green=next(x for x in home['_all_movies'] if
                   'green mile' in identity(x)[1])
        self.assertEqual({f['ident'] for f in green['files']},{'a','b'})

    def test_browse_includes_unallocated_ranking_films_with_all_variants(self):
        home={'premieres':[],'movies':[self.movie1,self.shaw],
              'shows':[self.show],'classics':[self.movie2],
              'classic_shows':[]}
        CinemaService._add_ranked_shelves(home)
        service=CinemaService(None,None,None)
        service.home_cache=home
        films=service.browse('movies')
        self.assertEqual(len(films),2)
        green=next(x for x in films if 'green mile' in identity(x)[1])
        self.assertEqual(len(green['files']),2)

    def test_year_ranking_does_not_repeat_alltime_ranking(self):
        current=card('Recent Movie',2026,'z','Recent.Movie.2026.1080p.mkv')
        home={'premieres':[],'movies':[current,self.shaw],
              'shows':[],'classics':[],'classic_shows':[]}
        CinemaService._add_ranked_shelves(home)
        year_ids={identity(c) for c in home['best_movies_year']}
        all_ids={identity(c) for c in home['best_movies_all']}
        self.assertTrue(year_ids)
        self.assertTrue(all_ids)
        self.assertFalse(year_ids & all_ids)

if __name__=='__main__':
    unittest.main()
