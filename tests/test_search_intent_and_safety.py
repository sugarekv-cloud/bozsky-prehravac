"""Search regressions using synthetic files, without live Webshare access."""
import unittest
from test_search_043_suggestions import service, f
from cinema_search_v3 import search_intent, search_suggestions, is_title_match


class SearchIntentTests(unittest.TestCase):
    def test_czech_and_english_selectors(self):
        for query in ('Bluey 2. série 3. díl', 'Bluey 2 rada 3 dil',
                      'Bluey season 2 episode 3', 'Bluey S02E03', 'Bluey 2x03'):
            with self.subTest(query=query):
                self.assertEqual(search_intent(query), ('Bluey', '', 2, 3))
        for query in ('Bluey S02', 'Bluey 2. série', 'Bluey season 2'):
            self.assertEqual(search_intent(query), ('Bluey', '', 2, None))
        self.assertEqual(search_intent('Duna (2021)'), ('Duna', '2021', None, None))
        self.assertEqual(search_intent('1917'), ('1917', '', None, None))

    def test_season_search_excludes_other_seasons(self):
        calls=[]
        def fetch(token, offset, query, sort='recent'):
            calls.append(query)
            return [f('a', 'Bluey.S02E01.1080p.CZ.mkv'),
                    f('b', 'Bluey.S02E03.1080p.CZ.mkv'),
                    f('c', 'Bluey.S01E03.1080p.CZ.mkv')], 3
        cards=service(fetch).search('Bluey 2. série', kind='show')
        self.assertIn('S02', calls[0])
        self.assertEqual({file['ident'] for card in cards for file in card['files']}, {'a', 'b'})

    def test_correction_keeps_episode_and_year(self):
        self.assertIn('Stranger Things S02E03', search_suggestions('Strnger Things 2. série 3. díl'))
        self.assertIn('Avengers (2012)', search_suggestions('Avengrs (2012)'))

    def test_suggestions_filter_raw_and_flagged_content(self):
        self.assertEqual(search_suggestions('Example Movi', remote=[
            'Example Movie XXX 2024.mkv',
            {'value':'Example Movie', 'adult':'1'}]), [])
        home={'_all_movies':[{'title':'Example Movie', 'ident':'1',
                              'adult':'1', 'files':[f('1','Example.Movie.2024.mkv')]}]}
        self.assertEqual(search_suggestions('Example Movi', home=home), [])

    def test_short_titles_require_exact_match(self):
        self.assertTrue(is_title_match({'title':'Up','kind':'movie'}, ['Up']))
        self.assertFalse(is_title_match({'title':'Up in the Air','kind':'movie'}, ['Up']))
        self.assertFalse(is_title_match({'title':'Give It','kind':'movie'}, ['It']))

    def test_remote_correction_searches_only_title(self):
        calls=[]
        svc=service(lambda *a,**k:([],0), lambda token,q,limit:calls.append(q) or [])
        svc.suggestions('Avengrs (2012)')
        self.assertEqual(calls, ['Avengrs'])

    def test_search_screen_preserves_relevance_despite_catalogue_sort(self):
        import sys, types
        if 'xbmcgui' not in sys.modules:
            module=types.ModuleType('xbmcgui')
            module.WindowXMLDialog=type('WindowXMLDialog',(),{})
            sys.modules['xbmcgui']=module
        from cinema_screen_v2 import CinemaScreen
        win=CinemaScreen.__new__(CinemaScreen)
        cards=[{'kind':'movie','title':'Matrix','year':'1999','rating':60,
                'files':[f('exact','Matrix.1999.1080p.CZ.mkv')]},
               {'kind':'movie','title':'Matrix Reloaded','year':'2003','rating':90,
                'files':[f('sequel','Matrix.Reloaded.2003.1080p.CZ.mkv')]}]
        win.service=types.SimpleNamespace(token='test',search=lambda query:cards)
        win.setProperty=lambda *a:None
        win._loading=lambda *a:types.SimpleNamespace(close=lambda:None)
        win.year=win.genre=win.quality=win.language='all'
        win.sort='rating'
        rendered=[]
        win._fill=lambda *args,**kwargs:rendered.append(args)
        win._screen('search','Matrix')
        self.assertEqual([c['title'] for c in rendered[0][1] if c['kind']=='movie'], ['Matrix','Matrix Reloaded'])


if __name__=='__main__':
    unittest.main()
