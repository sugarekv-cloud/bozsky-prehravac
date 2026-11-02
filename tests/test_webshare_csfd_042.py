# -*- coding: utf-8 -*-
"""Deep Webshare pagination and honest, failure-tolerant ČSFD display."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
import requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugin.video.fckyo'))
from cinema_service_v2 import CinemaService
from cinema_rankings import honest_ranked_shelf,csfd_only
from csfd_metadata import Catalogue


def file(ident,name):
    return {'ident':str(ident),'name':name,'size':'6000000000',
            'password':'0','available':'1','removed':'0'}


class Available:
    def check_groups(self,groups,max_workers=6):
        return [g for g in groups if g.get('files')]


def card(ident,title,rating=None,source=None,kind='movie'):
    f=file(ident,title+'.2022.1080p.mkv')
    return {'kind':kind,'raw':title,'title':title,'year':'2022',
            'ident':ident,'files':[f],'rating':rating,'rating_source':source}


class DeepWebshareTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.last_offset=0

    def test_scans_all_pages_of_relevant_alias_progressively_without_reset(self):
        def fetch(token,offset,query,sort='recent'):
            self.calls.append((query,offset))
            if query!='The Green Mile':
                return [],0
            # The match is on page 17; pages 0..16 are full of 100 other
            # file names, not selectable for the requested film.
            if offset<1700:
                return [file('%s:%d'%(offset,i),
                             'Other.Movie.%s.%03d.1080p.mkv'%(offset,i))
                        for i in range(100)],1701
            if offset==1700:
                return [file('green','The.Green.Mile.1999.2160p.CZ.mkv')],1701
            return [],1701
        svc=CinemaService('stub',fetch,Available())
        svc.artwork.lookup=lambda *args,**kw:None
        found=svc.search('Zelená míle',kind='movie')
        self.assertEqual(found,[])
        self.assertTrue(svc.search_has_more('Zelená míle','movie'))
        for _ in range(9):
            if not svc.search_has_more('Zelená míle','movie'):
                break
            found=svc.search('Zelená míle',kind='movie',more=True)
        self.assertEqual([x['ident'] for x in found],['green'])
        self.assertIn(('The Green Mile',1700),self.calls)
        offsets=[off for term,off in self.calls if term=='The Green Mile']
        self.assertEqual(offsets,sorted(set(offsets)))
        self.assertFalse(svc.search_has_more('Zelená míle','movie'))

    def test_subsequent_page_result_merge_deduplicates_file_ident(self):
        def fetch(token,offset,query,sort='recent'):
            if query!='Matrix':
                return [],0
            if offset==0:
                values=[file('id1','Matrix.1999.1080p.CZ.mkv')]
                return values+[file('noise%d'%i,'Other.Title.2025.1080p.mkv')
                               for i in range(99)],201
            if offset==100:
                return [file('id1','Matrix.1999.1080p.CZ.mkv')]+[
                    file('other%d'%i,'Another.Title.2024.mkv')
                    for i in range(99)],201
            return [file('id2','Matrix.1999.2160p.CZ.mkv')],201
        svc=CinemaService('stub',fetch,Available())
        svc.artwork.lookup=lambda *a,**k:None
        results=svc.search('Matrix','movie')
        for _ in range(4):
            if not svc.search_has_more('Matrix','movie'): break
            results=svc.search('Matrix','movie',more=True)
        self.assertTrue(results)
        self.assertEqual({f['ident'] for f in results[0]['files']},{'id1','id2'})


class CsfdReliabilityTests(unittest.TestCase):
    def test_empty_csfd_section_displays_real_imdb_not_fake_csfd(self):
        source=[card('a','A',95,'IMDb'),card('b','B',80,'IMDb'),
                card('c','C',None,None)]
        label,ranked=honest_ranked_shelf(source,'movie')
        self.assertEqual(label,'IMDb')
        self.assertEqual([c['ident'] for c in ranked],['a','b'])
        self.assertEqual(csfd_only(source,'movie'),[])
        source.append(card('d','D',91,'ČSFD'))
        label,ranked=honest_ranked_shelf(source,'movie')
        self.assertEqual(label,'ČSFD')
        self.assertEqual([c['ident'] for c in ranked],['d'])

    def test_no_scores_shows_only_verified_webshare_without_rating(self):
        source=[card('a','A',None,None),{'title':'Unknown IMDb','rating':99,
                                        'rating_source':'IMDb','kind':'movie'}]
        label,ranked=honest_ranked_shelf(source,'movie')
        self.assertEqual(label,'KATALOG WEBSHARE')
        self.assertEqual([c['ident'] for c in ranked],['a'])

    def test_transient_czdb_outage_is_not_saved_as_negative_and_recovers(self):
        with tempfile.TemporaryDirectory() as td:
            state={'up':False}
            def get(url,**kwargs):
                if not state['up']:
                    raise requests.ConnectionError('unreachable')
                response=Mock()
                response.json.return_value={'results':[{
                  'title':'Zelená míle','year':1999,'uid':'2294',
                  'rating':'92%','poster':'https://example.com/img.jpg'
                }]}
                return response
            db=Catalogue(td,transport=get)
            self.assertIsNone(db.lookup('Zelená míle','1999'))
            self.assertNotIn(db._key('Zelená míle','1999'),db._cache)
            state['up']=True
            db._service_retry_at=time.time()-1
            entry=db.lookup('Zelená míle','1999')
            self.assertEqual(entry['rating'],92)
            self.assertEqual(entry['rating_source'],'ČSFD')

    def test_bulk_enrichment_preserves_metadata_outside_request_budget(self):
        with tempfile.TemporaryDirectory() as td:
            db=Catalogue(td,transport=lambda *args,**kw:None)
            db.lookup=lambda title,year='':{'title':title,'rating':90,
                                            'rating_source':'ČSFD'}
            groups=[{'title':'First','year':'1999','metadata':None},
                    {'title':'Second','year':'2022',
                     'metadata':{'title':'Second','rating':83}}]
            db.lookup_many(groups,max_new=1)
            self.assertEqual(groups[0]['metadata']['rating'],90)
            self.assertEqual(groups[1]['metadata']['rating'],83)


if __name__=='__main__':
    unittest.main()
