# -*- coding: utf-8 -*-
"""Search v4 regressions for aliases, franchises, years and Webshare paging."""
import os
import sys
import unittest

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
PLUGIN=os.path.join(ROOT,'plugin.video.fckyo')
sys.path.insert(0,PLUGIN)
from cinema_search_v3 import title_and_year,candidate_names,query_plan
from cinema_service_v2 import CinemaService


def file(ident,name):
    return {'ident':ident,'name':name,'size':'5000000000',
            'password':'0','available':'1'}


class Available:
    def check_groups(self,groups,max_workers=6):
        return groups
    def check_files(self,files,limit=60):
        return files[:limit]


class SearchV4Tests(unittest.TestCase):
    def test_year_in_query_is_removed_before_search(self):
        self.assertEqual(title_and_year('Zelená míle (1999)'),('Zelená míle','1999'))
        self.assertEqual(title_and_year('The.Matrix.1999'),('The Matrix','1999'))
        self.assertEqual(title_and_year('Avengers'),('Avengers',''))

    def test_query_plan_explores_original_before_dotted_variants(self):
        plan=query_plan('Zelená míle',limit=6)
        self.assertIn('The Green Mile',plan[:3])
        self.assertIn('the.green.mile',query_plan('Zelená míle',limit=15))

    def test_czech_franchise_finds_english_parts(self):
        aliases=candidate_names('Pán prstenů')
        self.assertIn('The Lord of the Rings The Two Towers',aliases)
        self.assertIn('The Lord of the Rings The Return of the King',aliases)

    def test_english_sequel_without_czech_title_is_discovered(self):
        found=[]
        def fetch(token,offset,term,sort='recent'):
            found.append((term,offset))
            if 'two towers' in term.lower():
                return [file('two','The.Lord.of.the.Rings.The.Two.Towers.2002.1080p.mkv')],1
            return [],0
        svc=CinemaService('token',fetch,Available())
        class Art:
            def lookup(self,*args,**kwargs): return None
        svc.artwork=Art()
        result=svc.search('Pán prstenů')
        self.assertTrue(any('Two Towers' in c['title'] for c in result))
        self.assertTrue(any('two towers' in x[0].lower() for x in found))

    def test_deep_page_after_first_hundred_noise(self):
        calls=[]
        def fetch(token,offset,term,sort='recent'):
            calls.append((term,offset))
            if term=='The Green Mile':
                if offset==0:
                    return [file('n'+str(i),'Other.Movie.%d.1080p.mkv'%i)
                            for i in range(100)],101
                if offset==100:
                    return [file('hit','The.Green.Mile.1999.1080p.mkv')],101
            return [],0
        svc=CinemaService('token',fetch,Available())
        class Art:
            def lookup(self,*args,**kwargs):return None
        svc.artwork=Art()
        result=svc.search('Zelená míle')
        self.assertTrue(any(c['ident']=='hit' for c in result))
        self.assertIn(('The Green Mile',100),calls)

    def test_explicit_year_excludes_remakes_and_undated_files(self):
        calls=[]
        def fetch(token,offset,term,sort='recent'):
            calls.append(term)
            if 'dune' in term.lower():
                return [file('old','Dune.1984.1080p.mkv'),
                        file('new','Dune.2021.1080p.mkv'),
                        file('unknown','Dune.1080p.mkv')],3
            return [],0
        svc=CinemaService('token',fetch,Available())
        class Art:
            def lookup(self,*args,**kwargs):return None
        svc.artwork=Art()
        result=svc.search('Duna (2021)')
        self.assertEqual([c['ident'] for c in result],['new'])
        self.assertIn('Dune',calls)
        self.assertTrue(all(c.get('files') for c in result))


if __name__=='__main__':
    unittest.main()
