# -*- coding: utf-8 -*-
"""Offline tests for incremental metadata feeds and Webshare-only discovery."""
import os
import sys
import tempfile
import unittest
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..',
                                               'plugin.video.fckyo')))
from cinema_feed_v4 import CatalogFeed,parse_catalog
from cinema_service_v2 import CinemaService
from novinky_catalogue import normalize


def m(title,year,ident,rating='8.1'):
    return {'name':title,'year':str(year),'imdb_id':ident,'imdbRating':rating,
            'poster':'https://example.org/poster.jpg',
            'background':'https://example.org/backdrop.jpg',
            'description':'Film', 'genre':['Drama']}
def ws(ident,name):
    return {'ident':ident,'name':name,'size':'5000000000','available':'1'}
class Response:
    def __init__(self,metas):
        self.metas=metas
    def raise_for_status(self): pass
    def json(self): return {'metas':self.metas}
class Verified:
    def check_groups(self,groups,max_workers=4):
        return [g for g in groups if g.get('files')]
    def check_files(self,files,limit=60):return files[:limit]


class FeedTests(unittest.TestCase):
    def test_title_and_rating_parser(self):
        rows=parse_catalog({'metas':[m('Alpha',2000,'tt01'),
              m('A',2000,'tt01'),m('Beta',2026,'tt02',''),{'name':'No year'}]},'movie')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['imdb_rating'],81.0)
        self.assertIsNone(rows[1]['imdb_rating'])

    def test_reject_non_https_artwork(self):
        row=m('Movie',2001,'tt01')
        row['poster']='file:///etc/passwd'
        result=parse_catalog({'metas':[row]},'movie')
        self.assertEqual(result[0]['poster'],'')

    def test_pagination_persists_cumulative_titles(self):
        calls=[]
        def get(url,timeout):
            calls.append(url)
            is_series='/series/' in url
            skip=100 if 'skip=100' in url else 0
            prefix='Series' if is_series else 'Movie'
            return Response([m(prefix+' %d'%i,2000+i%20,
                               'tt%d'%i) for i in range(skip,skip+100)])
        with tempfile.TemporaryDirectory() as folder:
            feed=CatalogFeed(folder,transport=get)
            one=feed.refresh(force=True,pages_per_kind=2)
            self.assertEqual(len(one['movie']),200)
            self.assertEqual(len(one['show']),200)
            self.assertTrue(any('skip=100.json' in url for url in calls))
            self.assertEqual(len(calls),4)
            again=CatalogFeed(folder,transport=get)
            self.assertEqual(again.sizes()['movie'],200)
            self.assertEqual(again.sizes()['show'],200)
            self.assertEqual(again.data['next']['movie'],200)

    def test_failed_source_uses_static_fallback(self):
        def bad(url,timeout):
            raise ValueError('No external API')
        with tempfile.TemporaryDirectory() as folder:
            feed=CatalogFeed(folder,transport=bad)
            self.assertEqual(feed.refresh(force=True)['movie'],[])


class DiscoveryTests(unittest.TestCase):
    def test_metadata_only_never_creates_playable_card(self):
        class Feed:
            def sizes(self):return {'movie':100,'show':100}
            def refresh(self,force=False,pages_per_kind=1):
                return {'movie':[dict(m('Invented Title',2024,'tt01'),
                           kind='movie',original='Invented Title')],
                        'show':[]}
        with tempfile.TemporaryDirectory() as folder:
            svc=CinemaService('token',lambda token,offset,what,sort='rating':([],0),
                              Verified(),profile=folder)
            svc.feed=Feed()
            movies,shows=svc._discover_hits(movie_batch=8,show_batch=0)
            self.assertEqual(movies,[])
            self.assertEqual(shows,[])

    def test_cinemeta_title_only_after_webshare_result(self):
        class Feed:
            def sizes(self):return {'movie':100,'show':0}
            def refresh(self,force=False,pages_per_kind=1):
                return {'movie':parse_catalog({'metas':[m('Big Great Movie',2020,'tt01')]},'movie'),
                        'show':[]}
        def fetch(token,offset,what,sort='rating'):
            if normalize(what)=='big great movie':
                return [ws('yes','Big.Great.Movie.2020.1080p.mkv')],1
            return [],0
        with tempfile.TemporaryDirectory() as folder:
            svc=CinemaService('token',fetch,Verified(),profile=folder)
            svc.feed=Feed()
            class Art:
                def lookup(self,*args,**kwargs):return {}
            svc.artwork=Art()
            movies,_=svc._discover_hits(movie_batch=7,show_batch=0)
            self.assertEqual([m['raw'] for m in movies],['Big Great Movie'])
            self.assertEqual(movies[0]['rating_source'],'IMDb')
            self.assertEqual(movies[0]['rating'],81.0)
            self.assertEqual(movies[0]['ident'],'yes')
            self.assertEqual(movies[0]['poster'],'https://example.org/poster.jpg')

    def test_forced_refresh_invalidates_old_home_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            svc=CinemaService('token',None,Verified(),profile=folder)
            svc.home_cache={'movies':[]}
            svc.refresh_catalogue()
            self.assertIsNone(svc.home_cache)
            self.assertTrue(svc._feed_force)

if __name__=='__main__':
    unittest.main()
