# -*- coding: utf-8 -*-
"""Bluey searches must prefer Czech audio and never equate CZSUB with dubbing."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'plugin.video.fckyo'))
from cinema_service_v2 import CinemaService


def release(ident,name):
    return {'ident':ident,'name':name,'size':'2000000000',
            'password':'0','removed':'0','available':'1'}


class Available:
    def check_files(self,files,limit=30):
        return list(files[:limit])


def service(known,fetch):
    svc=CinemaService('test',fetch,Available())
    svc.seasons=lambda card:{1:{2:list(known)}}
    return svc


BLUEY={'kind':'show','title':'Bluey','raw':'Bluey','files':[]}


class BlueyCzechAudioTests(unittest.TestCase):
    def test_cz_dub_is_found_in_targeted_episode_search_and_ranked_first(self):
        queries=[]
        def fetch(token,offset,title,sort='recent'):
            queries.append(title)
            if title.endswith('CZDAB'):
                return [release('cz','Bluey.S01E02.1080p.CZDAB.mkv')],1
            return [release('en','Bluey.S01E02.2160p.EN.mkv')],1
        svc=service([release('en','Bluey.S01E02.2160p.EN.mkv')],fetch)
        rows=svc.episode_variants(BLUEY,1,2)
        self.assertEqual(rows[0]['ident'],'cz')
        self.assertEqual(len({x['ident'] for x in rows}),2)
        self.assertEqual(queries[0],'Bluey S01E02 CZDAB')

    def test_cz_subtitles_are_not_mistaken_for_czech_dubbing(self):
        calls=[]
        def fetch(t,offset,q,sort='recent'):
            calls.append(q)
            return [release('sub','Bluey.S01E02.CZSUB.2160p.mkv')],1
        svc=service([release('sub','Bluey.S01E02.CZSUB.2160p.mkv')],fetch)
        result=svc.episode_variants(BLUEY,1,2)
        self.assertEqual(result[0]['ident'],'sub')
        self.assertTrue(calls)

    def test_no_extra_network_requests_when_czech_audio_already_found(self):
        def fail(*args,**kwargs):
            self.fail('Already have Czech audio: no extra Webshare request')
        svc=service([release('cz','Bluey.S01E02.1080p.CZ.mkv')],fail)
        self.assertEqual(svc.episode_variants(BLUEY,1,2)[0]['ident'],'cz')

    def test_repeated_episode_reuses_15min_search_cache(self):
        calls=[]
        def fetch(t,offset,q,sort='recent'):
            calls.append(q)
            return [release('other','Not.Bluey.S01E02.CZ.mkv')],1
        svc=service([release('en','Bluey.S01E02.EN.mkv')],fetch)
        self.assertEqual(svc.episode_variants(BLUEY,1,2)[0]['ident'],'en')
        first=len(calls)
        self.assertEqual(first,4)
        self.assertEqual(svc.episode_variants(BLUEY,1,2)[0]['ident'],'en')
        self.assertEqual(len(calls),first)

    def test_episode_filter_rejects_other_seasons_and_series(self):
        def fetch(t,offset,q,sort='recent'):
            return [release('badseason','Bluey.S02E02.CZDAB.mkv'),
                    release('badtitle','Blueyland.S01E02.CZDAB.mkv'),
                    release('good','Bluey.S01E02.CZDAB.mkv')],3
        svc=service([release('en','Bluey.S01E02.EN.mkv')],fetch)
        results=svc.episode_variants(BLUEY,1,2)
        self.assertEqual([x['ident'] for x in results],['good','en'])

    def test_other_series_search_is_untouched(self):
        def fail(*args,**kwargs):
            self.fail('Non-Bluey must not trigger Bluey search')
        svc=service([release('en','Other.Show.S01E02.EN.mkv')],fail)
        card=dict(BLUEY,raw='Other Show',title='Other Show')
        self.assertEqual(svc.episode_variants(card,1,2)[0]['ident'],'en')


if __name__=='__main__':
    unittest.main()
